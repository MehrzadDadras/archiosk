"""
CLAUDE-CA1D-INSTRUMENT-RAIL-01 -- smallest implementation tranche from the
Plan-Mode report's Section K: proves the four-part spatial model's three
in-scope pieces without widening into the deferred programme (terminal,
subagent orchestration detail, repository diagnostics, contextual-
suggestion trigger logic).

1. Persistent admin machinery has a legitimate peripheral home:
   routes/operations.py + templates/operations.html, admin-gated, reached
   from the same Lists admin branch as Security Department.
2. One quiet global machine fact lives in the top bar without clutter:
   the existing AI_CALLS_DISABLED (CLAUDE-P27-B) kill switch, rendered
   only for admins and only when set (never in the ordinary case).
3. One real transient execution state appears composer-adjacent and
   disappears when resolved: static/js/case_workspace.js sets
   #dock-composer-execution-status right before the chat composer's own
   classic (un-intercepted) form-POST fires.

Run via:

    python -m unittest tests.test_ca1d_instrument_rail_01 -v
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseInstrumentRailTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_instrument_rail_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="rail_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="rail_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                self.doc = ingest_upload(
                    _fake_file(b"founding content", "founding.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="rail_admin", project_name="CA1D Instrument Rail Test Project",
                )
        self.project_id = self.doc.project_id

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _admin_client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "rail_admin"
            sess["role"] = "admin"
        return client

    def _reader_client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "rail_reader"
            sess["role"] = "read_only"
        return client


class OperationsPageAccessTests(_BaseInstrumentRailTestCase):
    """D.1 -- persistent admin machinery has a legitimate peripheral home."""

    def test_unauthenticated_redirects_to_login(self):
        client = self.flask_app.test_client()
        response = client.get("/operations/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_read_only_user_forbidden(self):
        response = self._reader_client().get("/operations/")
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_operations_page_with_telemetry(self):
        response = self._admin_client().get("/operations/")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Operations", body)
        self.assertIn("System Telemetry", body)
        # services/diagnostics.py's TechnicalTelemetry fields, real values,
        # not placeholder text -- proves the previously-unwired backend
        # primitive is actually wired, not just referenced.
        self.assertIn("operations.department_home", body)

    def test_operations_leaf_reachable_from_lists_admin_branch_for_admin_only(self):
        # The Lists admin branch renders on any authenticated page; the
        # projects listing is the simplest one that exercises base.html's
        # portfolio-browsing branch (no project open).
        admin_body = self._admin_client().get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.operations"', admin_body)
        self.assertIn('href="/operations/"', admin_body)

        reader_body = self._reader_client().get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.operations"', reader_body)


class TopBarStatusLineTests(_BaseInstrumentRailTestCase):
    """D.2 -- one quiet global machine fact lives in the top bar without
    clutter: rendered only for admins, only when the kill switch is set."""

    def test_admin_sees_status_line_when_ai_calls_disabled(self):
        with patch.dict(os.environ, {"AI_CALLS_DISABLED": "true"}):
            body = self._admin_client().get("/operations/").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.status"', body)
        self.assertIn("AI calls disabled", body)

    def test_admin_sees_no_status_line_in_the_ordinary_case(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_CALLS_DISABLED", None)
            body = self._admin_client().get("/operations/").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.status"', body)

    def test_read_only_user_never_sees_status_line_even_when_disabled(self):
        with patch.dict(os.environ, {"AI_CALLS_DISABLED": "true"}):
            response = self._reader_client().get("/operations/")
        # read_only is forbidden from /operations/ itself; confirm via a
        # page a read_only user CAN reach that the line still never renders.
        self.assertEqual(response.status_code, 403)
        with patch.dict(os.environ, {"AI_CALLS_DISABLED": "true"}):
            body = self._reader_client().get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.status"', body)


class ComposerExecutionStripMarkupTests(_BaseInstrumentRailTestCase):
    """D.3 -- one real transient execution state can appear
    composer-adjacent (server-rendered as an empty aria-live span; the
    client JS in static/js/case_workspace.js populates and never persists
    it, so every fresh page load starts empty)."""

    def test_execution_status_span_present_and_empty_server_side(self):
        body = self._admin_client().get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('id="dock-composer-execution-status"', body)
        self.assertIn('data-ui-ref="chat.composer.execution-status"', body)
        self.assertIn(
            '<span class="composer-execution-status" id="dock-composer-execution-status" '
            'data-ui-ref="chat.composer.execution-status" aria-live="polite"></span>',
            body,
        )

    def test_execution_status_span_sits_inside_the_one_composer_form(self):
        """Regression guard: must stay inside .conversation-dock-composer,
        not become a second, detached status surface."""
        body = self._admin_client().get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        composer_start = body.index('class="conversation-input-form conversation-dock-composer"')
        composer_end = body.index("</form>", composer_start)
        self.assertIn("dock-composer-execution-status", body[composer_start:composer_end])


if __name__ == "__main__":
    unittest.main()
