import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceStore, ProjectWorkspace
from services.bhive_parser import ParsedDocument
from services.requirements_registry import RequirementsRegistry
from services.developer_ccn import (
    CCN_STATUS_ACTIVE,
    CCN_STATUS_CANCELLED,
    attach_selected_object,
    handle_command,
    is_ccn_command,
)


class DeveloperModeCCNTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ccn_"))
        self.session = {}
        self.events = []

        class Audit:
            def append(_, **kwargs):
                self.events.append(kwargs)

        self.audit = Audit()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_native_command_lifecycle_is_not_project_mutation(self):
        self.assertTrue(is_ccn_command("/CCN Move the project selector"))
        result = handle_command(
            "/CCN Move the project selector to a dedicated interface",
            session=self.session, actor="admin", governance_log=self.audit, project_id="project-a",
        )
        self.assertEqual(result["action_taken"], "developer_ccn_started")
        self.assertEqual(self.session["developer_ccn"]["status"], CCN_STATUS_ACTIVE)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0]["event_type"], "developer_ccn_created")

        status = handle_command("/CCN status", session=self.session, actor="admin", governance_log=self.audit, project_id="project-a")
        self.assertIn("CCN:", status["reply_text"])
        compare = handle_command("/CCN compare", session=self.session, actor="admin", governance_log=self.audit, project_id="project-a")
        self.assertIn("current ARCHIOSK state", compare["reply_text"])

        finalized = handle_command("/CCN finalize", session=self.session, actor="admin", governance_log=self.audit, project_id="project-a")
        self.assertEqual(self.session["developer_ccn"]["status"], "finalized")
        self.assertIn("does not authorize implementation", finalized["reply_text"])

        # A cancelled context remains traceable but cannot receive selections.
        self.session["developer_ccn"]["status"] = CCN_STATUS_ACTIVE
        cancelled = handle_command("/CCN cancel", session=self.session, actor="admin", governance_log=self.audit, project_id="project-a")
        self.assertEqual(self.session["developer_ccn"]["status"], CCN_STATUS_CANCELLED)
        self.assertIn("No project or application mutation", cancelled["reply_text"])

    def test_selected_application_object_is_context_not_authorization(self):
        handle_command("/CCN inspect the Spin History", session=self.session, actor="admin", governance_log=self.audit, project_id="project-a")
        selected = attach_selected_object(
            session=self.session, object_type="ui_element", object_id="spin-history",
            label="Spin History", project_id="project-a", governance_log=self.audit,
        )
        self.assertEqual(selected["classification"], "INVESTIGATE")
        self.assertEqual(self.session["developer_ccn"]["selected_elements"][0]["label"], "Spin History")
        self.assertEqual(len(self.events), 2)
        self.assertEqual(self.events[-1]["event_type"], "developer_ccn_object_attached")

    def test_ccn_context_is_session_bound(self):
        handle_command("/CCN inspect this session", session=self.session, actor="admin", governance_log=self.audit)
        other_session = {}
        self.assertIsNone(other_session.get("developer_ccn"))
        self.assertNotIn("developer_ccn", other_session)

    def test_route_requires_developer_mode_and_keeps_project_context_isolated(self):
        import app as app_module

        app = app_module.create_app("testing")
        app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        for project_id in ("project-a", "project-b"):
            CaseWorkspaceStore(self.tmp).save(ProjectWorkspace(project_id=project_id, sources=[{"id": f"{project_id}-source"}]))
            RequirementsRegistry(self.tmp).save(ParsedDocument(project_id=project_id, filename=f"{project_id}.txt", ingested_at="2026-01-01T00:00:00+00:00"))

        client = app.test_client()
        with client.session_transaction() as sess:
            sess.update({"user_id": 1, "username": "admin", "role": "admin"})
        denied = client.post("/projects/project-a/workspace/quick-start", data={"text": "/CCN inspect this"})
        self.assertEqual(denied.status_code, 302)
        with client.session_transaction() as sess:
            self.assertNotIn("developer_ccn", sess)

        with client.session_transaction() as sess:
            sess["developer_mode"] = True
        client.post("/projects/project-a/workspace/quick-start", data={"text": "/CCN inspect the left rail"})
        client.post(
            "/projects/project-a/workspace/quick-start",
            data={"text": "Where is this implemented?", "anchor_type": "ui_element", "anchor_id": "left-rail", "anchor_description": "Project left rail"},
        )
        a = CaseWorkspaceStore(self.tmp).get("project-a")
        self.assertEqual(a.cases, [])
        self.assertEqual(a.project_conversation[-1]["developer_context"]["selected_elements"][0]["project_id"], "project-a")

        client.post("/projects/project-b/workspace/quick-start", data={"text": "What depends on this?"})
        b = CaseWorkspaceStore(self.tmp).get("project-b")
        self.assertEqual(b.project_conversation[-1]["developer_context"]["selected_elements"], [])


if __name__ == "__main__":
    unittest.main()
