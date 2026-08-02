"""
Project-wide "Needs Attention": every unresolved Finding (not yet
"applied") across every non-archived Case the reviewer can see, not just
whichever Case happens to be open right now.

Real, recorded gap: the Cedar Harbour walkthrough asked for exactly this
("a central page that compiles all discrepancies within the project so
we can do the adjustment centrally... clicking on the highlighted issue
takes us to [it]") and it was never built - project_home_summary already
computed the *count* project-wide, but only as a number, and only on
Project Home; once any Case was open, visibility into every other Case's
unresolved work disappeared entirely.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import ANALYSIS_TRIGGER_USER_INITIATED, AnalysisTrigger, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class NeedsAttentionAggregationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_needs_attention_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-needs-attention"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.source = self.store.add_source(
            self.store.get(self.project_id), name="RFP.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_case_with_finding(self, title, created_by="owner1"):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": title, "objective": "x"},
        )
        workspace = self.store.get(self.project_id)
        case = next(c for c in workspace.cases if c["title"] == title)
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor=created_by)
        analysis = self.store.record_analysis(
            workspace, case_id=case["id"], source_ids=[self.source["id"]], objective="x",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": f"Finding for {title}", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        return case, analysis["finding_ids"][0]

    def test_unresolved_finding_in_a_different_case_is_surfaced(self):
        # SUPERSEDED (CLAUDE-P40-E3A): Needs Attention is project-wide
        # Overview content - it used to stay visible even while a
        # DIFFERENT Investigation was open (P40-E2B's own invariant), but
        # Overview and an open Investigation are now mutually exclusive
        # leaves (Section 4/5), a deliberate, documented consequence of
        # this stage's own leaf-exclusivity model. What this test still
        # protects - aggregation ACROSS every open Investigation, not
        # just one - is checked via Overview directly instead.
        case_a, _ = self._make_case_with_finding("Case A")
        case_b, _ = self._make_case_with_finding("Case B")

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Needs Attention (2)", body)
        self.assertIn("Finding for Case A", body)
        self.assertIn("Finding for Case B", body)

    def test_applied_finding_drops_out(self):
        case_a, finding_id = self._make_case_with_finding("Case A")
        workspace = self.store.get(self.project_id)
        self.client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct", "case_id": case_a["id"]},
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/disposition",
            data={"disposition": "Confirmed", "case_id": case_a["id"]},
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_a['id']}/apply", data={"confirm": "once"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Needs Attention (0)", body)
        self.assertIn("Nothing outstanding", body)

    def test_archived_case_findings_are_excluded(self):
        case_a, _ = self._make_case_with_finding("Case A")
        self.client.post(f"/projects/{self.project_id}/workspace/cases/{case_a['id']}/archive")
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Needs Attention (0)", body)

    def test_private_case_from_another_user_is_not_leaked(self):
        self._make_case_with_finding("Owner1's private case")
        other_client = self.flask_app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "owner2"
            sess["role"] = "admin"
        resp = other_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Needs Attention (0)", body)
        self.assertNotIn("Owner1's private case", body)


if __name__ == "__main__":
    unittest.main()
