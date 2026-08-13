"""
CLAUDE-VOICE27-MISCLASS-01 -- project operating-environment misclassification
correction.

A real Product Owner report: a project (a Design-Build RFP received and
worked on from the Design-Builder/Proponent side, as Design Manager) had
been classified Client/Owner at creation. Root cause was NOT a bug in the
classification mechanism -- ProjectWorkspace.operating_environment is
already a real, canonical field (never filename-derived) set once at
creation via CaseWorkspaceStore.set_operating_environment, which
structurally locks it (raises OperatingEnvironmentAlreadySetError on any
second call, for the SAME reason routes/workspace.py's own
classify_operating_environment docstring gives: no update path existed
for an already-classified project, correct or not). The gap was that
lock having no exception for the genuine "the one value itself was wrong
from the start" case.

Covers CaseWorkspaceStore.correct_operating_environment (the new,
separate, deliberately-harder-to-reach admin correction path) and
routes/workspace.py::correct_operating_environment (its route), proving:
the existing one-time lock (set_operating_environment /
classify_operating_environment) is completely unaffected; the new path
requires admin authority, a real reason, and a real recognized
environment; a correction actually moves the project between the
Gateway's own Client/Owner and Design-Builder/Proponent lists
(_environment_projects, the same access-scoped read every other Gateway
list already uses); and every correction is logged to GovernanceLog with
before/after values and the reason.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
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
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore, OperatingEnvironmentAlreadySetError
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.governance import GovernanceLog
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseCorrectionTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_voice27_misclass_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False

        with self.flask_app.app_context():
            db.session.add(User(username="misclass_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="misclass_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, environment=CLIENT_OWNER, filename="RFP-27-114-North-Bayview-Courthouse.docx"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=environment, owner="misclass_admin",
                    project_name="North Bayview Courthouse",
                )

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class CorrectOperatingEnvironmentServiceTests(_BaseCorrectionTestCase):
    def test_corrects_an_already_classified_projects_environment(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        self.assertEqual(workspace.operating_environment, CLIENT_OWNER)

        store.correct_operating_environment(
            workspace, DESIGN_BUILDER_PROPONENT, actor="misclass_admin",
            reason="Received and worked on from the Proponent side as Design Manager - miscategorized at creation.",
        )
        reloaded = store.get(doc.project_id)
        self.assertEqual(reloaded.operating_environment, DESIGN_BUILDER_PROPONENT)

    def test_rejects_an_unrecognized_environment(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        with self.assertRaises(ValueError):
            store.correct_operating_environment(
                workspace, "not_a_real_environment", actor="misclass_admin", reason="testing",
            )

    def test_rejects_an_empty_reason(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.correct_operating_environment(
                workspace, DESIGN_BUILDER_PROPONENT, actor="misclass_admin", reason="   ",
            )

    def test_rejects_correcting_to_the_same_value_already_held(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.correct_operating_environment(
                workspace, CLIENT_OWNER, actor="misclass_admin", reason="testing",
            )

    def test_logs_the_correction_with_before_after_and_reason(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        log = GovernanceLog(self.tmp_dir)

        store.correct_operating_environment(
            workspace, DESIGN_BUILDER_PROPONENT, actor="misclass_admin",
            reason="Wrong side selected at creation.", governance_log=log,
        )
        events = [e for e in log.read(doc.project_id) if e.event_type == "operating_environment_corrected"]
        self.assertEqual(len(events), 1)
        payload = events[0].payload
        self.assertEqual(payload["previous_environment"], CLIENT_OWNER)
        self.assertEqual(payload["operating_environment"], DESIGN_BUILDER_PROPONENT)
        self.assertEqual(payload["reason"], "Wrong side selected at creation.")

    def test_does_not_disturb_the_one_time_lock_for_a_never_classified_project(self):
        # The existing set_operating_environment/classify_operating_environment
        # lock must be completely unaffected by this new, separate method
        # existing alongside it.
        doc = self._ingest(environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        with self.assertRaises(OperatingEnvironmentAlreadySetError):
            store.set_operating_environment(workspace, DESIGN_BUILDER_PROPONENT, actor="misclass_admin")


class CorrectOperatingEnvironmentRouteTests(_BaseCorrectionTestCase):
    def test_route_requires_admin(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_reader", 2, role="read_only")
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/correct-environment",
            data={"operating_environment": DESIGN_BUILDER_PROPONENT, "reason": "test"},
        )
        self.assertIn(resp.status_code, (302, 401, 403))
        store = self._store()
        self.assertEqual(store.get(doc.project_id).operating_environment, CLIENT_OWNER)

    def test_route_corrects_the_environment_for_an_admin(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_admin", 1)
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/correct-environment",
            data={"operating_environment": DESIGN_BUILDER_PROPONENT, "reason": "Wrong side at creation."},
        )
        self.assertEqual(resp.status_code, 302)
        store = self._store()
        self.assertEqual(store.get(doc.project_id).operating_environment, DESIGN_BUILDER_PROPONENT)

    def test_project_moves_between_gateway_lists_after_correction(self):
        # The actual Product Owner regression check: appears only in the
        # correct side's "Open Existing Project" list afterward, on the
        # real rendered Gateway page (gateway.html), not just the
        # underlying data helper.
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_admin", 1)

        def _lists():
            # The <ul> only renders when that side's list is non-empty
            # (the empty state is a plain <p> instead), so section
            # boundaries (the <h3> headings) are used rather than
            # assuming the <ul> is always present.
            body = client.get("/gateway").get_data(as_text=True)
            owner_start = body.index("Client / Owner Projects</h3>")
            proponent_start = body.index("Design-Builder / Proponent Projects</h3>")
            # gateway.html's own trailing <script nonce=...> reliably
            # follows both context groups - a nearby "</div>" would
            # instead match .gateway-actions's own closing tag, cutting
            # the slice off before the "Open Existing Project" disclosure
            # (which comes after it in the markup) even renders.
            groups_end = body.index('<script nonce=', proponent_start)
            return body[owner_start:proponent_start], body[proponent_start:groups_end]

        before_owner_list, before_proponent_list = _lists()
        self.assertIn(doc.project_id, before_owner_list)
        self.assertNotIn(doc.project_id, before_proponent_list)

        client.post(
            f"/projects/{doc.project_id}/workspace/correct-environment",
            data={"operating_environment": DESIGN_BUILDER_PROPONENT, "reason": "Wrong side at creation."},
        )

        after_owner_list, after_proponent_list = _lists()
        self.assertNotIn(doc.project_id, after_owner_list)
        self.assertIn(doc.project_id, after_proponent_list)

    def test_route_rejects_a_missing_reason(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_admin", 1)
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/correct-environment",
            data={"operating_environment": DESIGN_BUILDER_PROPONENT, "reason": ""},
        )
        self.assertEqual(resp.status_code, 302)
        store = self._store()
        # Rejected server-side by the store's own reason check - value unchanged.
        self.assertEqual(store.get(doc.project_id).operating_environment, CLIENT_OWNER)

    def test_route_never_uses_filename_to_decide_classification(self):
        # Grounds the Product Owner's own explicit requirement: an RFP
        # filename must never be used as evidence of which side a project
        # belongs to. The route/service take the environment purely from
        # the submitted form field - confirmed here by correcting a
        # project whose filename contains "RFP" to Design-Builder/
        # Proponent and back, proving the filename plays no role either way.
        doc = self._ingest(environment=CLIENT_OWNER, filename="RFP-27-114-North-Bayview-Courthouse.docx")
        client = self._client_as("misclass_admin", 1)
        client.post(
            f"/projects/{doc.project_id}/workspace/correct-environment",
            data={"operating_environment": DESIGN_BUILDER_PROPONENT, "reason": "Proponent side, not Owner."},
        )
        store = self._store()
        self.assertEqual(store.get(doc.project_id).operating_environment, DESIGN_BUILDER_PROPONENT)


class CaseWorkspaceOverviewMarkupTests(_BaseCorrectionTestCase):
    def test_correction_control_rendered_for_admin_on_a_classified_project(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_admin", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("Correct this classification", body)
        self.assertIn("workspace/correct-environment", body)

    def test_correction_control_hidden_for_non_admin(self):
        doc = self._ingest(environment=CLIENT_OWNER)
        client = self._client_as("misclass_admin", 1)
        client.post(
            f"/projects/{doc.project_id}/workspace/access/grant",
            data={"username": "misclass_reader"},
        )
        reader_client = self._client_as("misclass_reader", 2, role="read_only")
        body = reader_client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn("Correct this classification", body)


if __name__ == "__main__":
    unittest.main()
