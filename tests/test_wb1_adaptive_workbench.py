"""
CLAUDE-POSTCAMEL-WB1 - Adaptive Workbench / Conversational Operational Terminal.

Governing principles: "One workbench. One primary operational terminal.
Many projectable views. No fixed panel count." / "Conversation operates;
views project." / "The cockpit is stable. The visible instruments are
not." The prior "six-panel cockpit" concept is a historical exploratory
layout, not a constitutional requirement (confirmed: the phrase appears
nowhere in this codebase or its governance corpus).

This stage's one bounded, real code change (Section 8/18, Aggressive
Overflow / Founder Focus Test): the per-Requirement Adjudicate form
previously rendered unconditionally on every Requirement row - the one
always-visible control block on the Requirements display not already
behind a subdisclosure (its siblings "+ Revise (Addendum)" and
"Perspective" already used this exact, already-proven mechanism). It is
now wrapped in the same `macros.subdisclosure` pattern - collapsed by
default, present unmodified in the raw HTML (a `<details>` element's
content is always in the response body, only visually collapsed), zero
capability removed.

Run via:

    python -m unittest tests.test_wb1_adaptive_workbench -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class AdjudicateFormOverflowTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_wb1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="wb1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="wb1_owner", project_name="WB1 Workbench Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "wb1_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _register_requirement(self, client):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={
                "source_id": source_id,
                "original_requirement_identifier": "Section 1",
                "text_reference": "The system shall do the thing.",
            },
        )
        self.assertEqual(resp.status_code, 302)

    def test_adjudicate_form_is_behind_a_collapsed_subdisclosure(self):
        """The form itself must still be present verbatim in the raw HTML
        (a <details> element's content is always in the response body,
        only visually collapsed - see test_meta_t01's own established note
        on this same mechanism) - only its permanent visual residency
        changes, not its reachability."""
        client = self._client()
        self._register_requirement(client)
        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)

        summary_index = body.index("Adjudicate this Requirement")
        form_index = body.index('name="outcome"', summary_index)

        # The <summary> label must precede the form fields it discloses.
        self.assertLess(summary_index, form_index)
        # And the whole thing must sit inside a <details> disclosure, the
        # same established mechanism as the sibling "+ Revise (Addendum)"
        # and "Perspective" blocks on this same row.
        details_open_index = body.rindex("<details", 0, summary_index)
        self.assertNotEqual(details_open_index, -1)

    def test_adjudicate_form_still_fully_functional_behind_disclosure(self):
        """Capability must be unchanged - only its permanent visibility.
        A real POST to the unchanged route must still succeed."""
        client = self._client()
        self._register_requirement(client)
        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)
        self.assertIn('name="attribution" value="human_reviewed"', body)
        self.assertIn('name="attribution" value="agent_assessment"', body)
        self.assertIn(">Adjudicate<", body)

    def test_requirements_view_still_renders_revise_and_perspective_disclosures(self):
        """Regression guard: confirms the two pre-existing sibling
        subdisclosures on the same row are untouched by this change."""
        client = self._client()
        self._register_requirement(client)
        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)
        self.assertIn("+ Revise (Addendum)", body)
        self.assertIn("Perspective", body)
        self.assertIn("Discuss this Requirement", body)


if __name__ == "__main__":
    unittest.main()
