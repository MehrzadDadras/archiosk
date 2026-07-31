"""
CLAUDE-P38 -- workspace presentation/UX fixes from the product owner's
browser walkthrough (OBS-02, OBS-06, OBS-12, OBS-13, OBS-14). Wording,
layout, and compact-empty-state fixes only -- no governed behavior
changes, so these assert on rendered HTML rather than store state.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument
from services.case_workspace import AnalysisTrigger, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class WorkspacePresentationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_workspace_presentation_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-presentation"

        with self.flask_app.app_context():
            db.session.add(User(username="admin1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store.set_project_owner(self.store.get(self.project_id), owner="admin1", actor="admin1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _page(self):
        return self.client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)

    # -- OBS-02: Accepted Knowledge compact empty state ----------------------

    def test_accepted_knowledge_empty_state_is_compact_not_a_governance_essay(self):
        body = self._page()
        self.assertIn("No accepted project knowledge yet", body)
        self.assertIn("How Accepted Knowledge works", body)  # explanation moved behind help

    def test_accepted_knowledge_shows_findings_awaiting_and_applied_counts(self):
        workspace = self.store.get(self.project_id)
        case = self.store.create_case(workspace, title="Presentation Case", objective="x", created_by="admin1")
        source_id = next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")["id"]
        trigger = AnalysisTrigger(trigger_type="user_initiated", triggered_by_actor="admin1")
        self.store.record_analysis(
            workspace, case_id=case["id"], source_ids=[source_id], objective="x",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": "Datum inconsistency observed.", "machine_confidence": 0.7, "source_id": source_id}],
            trigger=trigger,
        )
        body = self._page()
        self.assertIn("1 awaiting review or disposition", body)
        self.assertIn("0 applied", body)

    # -- OBS-06: Sources card shows upload date -------------------------------

    def test_source_card_shows_added_date(self):
        body = self._page()
        workspace = self.store.get(self.project_id)
        source = next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")
        self.assertIn(f"added {source['added_at']}", body)

    # -- OBS-12: History summary/full toggle ----------------------------------

    def test_history_defaults_to_a_compact_summary(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Presentation Case", "objective": "x"},
        )
        body = self._page()
        self.assertIn("event(s) recorded", body)
        self.assertIn("Show full history", body)
        self.assertIn('id="history-full-toggle"', body)

    def test_history_accordion_status_shows_the_true_total_not_just_the_capped_list(self):
        # history_total_count, not len(recent_governance_events) (capped
        # at 25) - the accordion header must reflect the real total.
        body = self._page()
        self.assertIn("History (", body)

    # -- OBS-13: Layers control clarified -------------------------------------

    def test_layers_control_renamed_and_reframed(self):
        body = self._page()
        self.assertIn("Display Layers", body)
        self.assertIn("Show Risk / Opportunity badges", body)

    # -- OBS-14: lifecycle strip no longer claims a false current phase ------

    def test_lifecycle_strip_does_not_claim_a_current_phase(self):
        body = self._page()
        self.assertIn("Lifecycle (reference only", body)
        self.assertNotIn('lifecycle-stage current', body)

    def test_historic_record_removed_from_the_phase_list(self):
        body = self._page()
        self.assertNotIn("Historic Record", body)


if __name__ == "__main__":
    unittest.main()
