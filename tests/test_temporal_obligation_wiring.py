"""
TemporalObligation route wiring.

services/case_workspace.py's TemporalObligation model (create/revise/
list/evaluate_temporal_condition) was fully built and tested at the
store layer but never reachable through any route - the real, tested
replacement for the old milestone lattice (dropped for being
non-functional: bhive_parser.py's _derive_milestones only ever produced
status="pending" for real projects). This covers the first route wiring:
workspace.create_temporal_obligation_route and its rendering in
case_workspace.html's "Key Dates" accordion.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import datetime
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class TemporalObligationWiringTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_temporal_obligation_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-temporal"

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
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Investigation", "objective": "x"},
        )
        self.case_id = self.store.get(self.project_id).cases[0]["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create(self, **overrides):
        data = {
            "title": "RFI response",
            "required_action": "Submit written response",
            "accepted_date": "2026-06-01",
        }
        data.update(overrides)
        return self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{self.case_id}/temporal-obligations",
            data=data,
        )

    def test_create_persists_a_real_obligation(self):
        self._create()
        obligations = self.store.temporal_obligations_for_project(self.store.get(self.project_id))
        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0]["title"], "RFI response")
        self.assertEqual(obligations[0]["origin_type"], "case")
        self.assertEqual(obligations[0]["origin_id"], self.case_id)
        self.assertEqual(obligations[0]["case_id"], self.case_id)

    def test_missing_required_field_is_rejected(self):
        resp = self._create(title="")
        obligations = self.store.temporal_obligations_for_project(self.store.get(self.project_id))
        self.assertEqual(len(obligations), 0)
        self.assertEqual(resp.status_code, 302)  # redirected back, not silently accepted

    def test_invalid_date_is_rejected(self):
        resp = self._create(accepted_date="not-a-date")
        obligations = self.store.temporal_obligations_for_project(self.store.get(self.project_id))
        self.assertEqual(len(obligations), 0)
        self.assertEqual(resp.status_code, 302)

    def test_cannot_create_against_a_case_you_cannot_see(self):
        other_client = self.flask_app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "owner2"
            sess["role"] = "admin"
        other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{self.case_id}/temporal-obligations",
            data={"title": "x", "required_action": "x", "accepted_date": "2026-06-01"},
        )
        obligations = self.store.temporal_obligations_for_project(self.store.get(self.project_id))
        self.assertEqual(len(obligations), 0)

    def test_key_dates_accordion_shows_created_obligation(self):
        # SUPERSEDED (CLAUDE-P40-E3A): Key Dates is project-wide Overview
        # content - it used to stay visible even while an Investigation
        # was open (P40-E2B's own invariant), but Overview and an open
        # Investigation are now mutually exclusive leaves (Section 4/5),
        # a deliberate, documented consequence of this stage's own
        # leaf-exclusivity model.
        self._create()
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("RFI response", body)
        self.assertIn("Key Dates (1)", body)

    def test_overdue_sorts_before_not_yet_due_regardless_of_creation_order(self):
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        next_year = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        # created in this order: future one first, overdue one second
        self._create(title="Future submittal", accepted_date=next_year)
        self._create(title="Overdue RFI", accepted_date=yesterday)

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        # overdue must render before the future one despite being created second
        self.assertLess(body.index("Overdue RFI"), body.index("Future submittal"))
        self.assertIn("review-state-overdue", body)
        self.assertIn("review-state-not-yet-due", body)


if __name__ == "__main__":
    unittest.main()
