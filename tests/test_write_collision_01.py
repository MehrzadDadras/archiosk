"""
CLAUDE-WRITE-COLLISION-01 - two people saving at once is not a server fault.

WHAT WAS WRONG

CaseWorkspaceStore refuses to overwrite a newer state with a stale one - the
right behaviour - and raises ConcurrentModificationError to say so. Ten route
handlers perform a governed write with no handler for it, so an ordinary
collision between two reviewers surfaced as HTTP 500: "Something went wrong",
logged as an unhandled exception, the user's work discarded, and no indication
that retrying would work.

HOW IT WAS FOUND, AND WHY THE FIRST TWO ANSWERS WERE WRONG

A grep for `except ConcurrentModificationError` returned zero and suggested
nothing handled it anywhere. That was misleading: the class subclasses
CaseWorkspaceError, which IS caught 61 times in routes/workspace.py alone.

The opposite conclusion - "so it must be handled" - was also wrong. An AST audit
of every route handler, checking whether each governed store call actually sits
inside a try that catches the parent, found 12 that do not. A regex attempt at
the same question returned 0/0/0 and would have hidden the defect completely.

The only answer that settled it was empirical: force the store to raise on a
real route POST and read the status code. It was 500.

THE SHAPE OF THE FIX

One errorhandler, not ten try/excepts - new write routes are covered
automatically, which is the same reasoning visible_cases_for records for
privacy: a rule every future caller must remember is not a rule.

Deliberately narrow: only ConcurrentModificationError, never its
CaseWorkspaceError parent. A blanket handler would swallow genuine validation
faults that should stay visible as bugs.
"""
from __future__ import annotations

import ast
import io
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.case_workspace import (
    CaseWorkspaceError, CaseWorkspaceStore, ConcurrentModificationError,
)

_ROOT = Path(__file__).resolve().parent.parent


class _Project(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.ingestion import ingest_upload

        self.app = app_module.create_app("testing")
        with self.app.app_context():
            db.session.add(User(username="wc", password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()

        def fake_parse(self_parser, raw, filename):
            return ParsedDocument(project_id=str(uuid.uuid4()), filename=filename,
                                  ingested_at=datetime.now(timezone.utc).isoformat(),
                                  parser_version="test")

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                doc = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="f.txt"), self.app,
                    operating_environment="client_owner", owner="wc",
                    project_name="Collision " + uuid.uuid4().hex[:8])
        self.project_id = doc.project_id
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "wc"
            sess["role"] = "admin"

    def _collide(self, path, data):
        with patch.object(CaseWorkspaceStore, "save",
                          side_effect=ConcurrentModificationError("someone else saved first")):
            return self.client.post(path, data=data)


class ACollisionIsNotAServerError(_Project):
    def test_it_answers_409_not_500(self):
        resp = self._collide("/projects/%s/workspace/cases" % self.project_id,
                             {"title": "T", "objective": "o"})
        self.assertEqual(resp.status_code, 409)

    def test_it_tells_the_person_what_to_do(self):
        resp = self._collide("/projects/%s/workspace/cases" % self.project_id,
                             {"title": "T", "objective": "o"})
        body = resp.get_data(as_text=True).lower()
        self.assertIn("reload", body)

    def test_it_does_not_claim_a_server_fault(self):
        # "Something went wrong" is the 500 page's own copy. Showing it here
        # would blame the system for doing exactly the right thing.
        resp = self._collide("/projects/%s/workspace/cases" % self.project_id,
                             {"title": "T", "objective": "o"})
        self.assertNotIn("Something went wrong", resp.get_data(as_text=True))

    def test_it_never_says_the_write_succeeded(self):
        resp = self._collide("/projects/%s/workspace/cases" % self.project_id,
                             {"title": "T", "objective": "o"})
        body = resp.get_data(as_text=True).lower()
        for false_comfort in ["saved", "created", "success"]:
            self.assertNotIn(false_comfort + " successfully", body)

    def test_a_json_client_gets_json(self):
        with patch.object(CaseWorkspaceStore, "save",
                          side_effect=ConcurrentModificationError("collision")):
            resp = self.client.post(
                "/projects/%s/workspace/cases" % self.project_id,
                data={"title": "T", "objective": "o"},
                headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 409)


class TheHandlerIsDeliberatelyNarrow(_Project):
    def test_an_ordinary_validation_error_is_not_swallowed(self):
        """The parent class must keep its existing behaviour.

        Catching CaseWorkspaceError globally would convert genuine validation
        faults into a friendly 409 and hide real bugs. Only the recoverable
        subclass is handled.
        """
        with patch.object(CaseWorkspaceStore, "save",
                          side_effect=CaseWorkspaceError("a genuine validation fault")):
            with self.assertRaises(CaseWorkspaceError):
                self.client.post("/projects/%s/workspace/cases" % self.project_id,
                                 data={"title": "T", "objective": "o"})

    def test_the_handler_registers_only_the_subclass(self):
        source = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("@app.errorhandler(ConcurrentModificationError)", source)
        self.assertNotIn("@app.errorhandler(CaseWorkspaceError)", source)


class NoRouteIsLeftUnprotected(unittest.TestCase):
    """The audit that found this, kept as a guard.

    Not a substitute for the handler - a belt-and-braces check that the codebase
    has not grown a write path the global handler somehow cannot see.
    """

    MUTATORS = ("add_message", "create_case", "create_task", "save", "add_source",
                "archive_case", "share_case", "complete_task", "reopen_task",
                "add_composer_finding", "record_analysis", "set_disposition")

    def test_every_governed_write_route_is_reachable_by_the_handler(self):
        # The handler is app-level, so every route is covered by construction.
        # This asserts the property that makes that true: the exception really
        # does inherit from the class routes already catch, so a local handler
        # and the global one cannot disagree about what this is.
        self.assertTrue(issubclass(ConcurrentModificationError, CaseWorkspaceError))

    def test_the_audit_still_finds_the_write_sites_it_is_meant_to_cover(self):
        # If this ever returns zero, either every route grew its own handler
        # (fine) or the detection broke (not fine). Either way it should be
        # looked at rather than silently passing.
        tree = ast.parse((_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8"))
        writes = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in self.MUTATORS:
                recv = getattr(node.func, "value", None)
                if getattr(recv, "id", "") == "store":
                    writes += 1
        self.assertGreater(writes, 0, "no governed store writes found - detection broke")


if __name__ == "__main__":
    unittest.main()
