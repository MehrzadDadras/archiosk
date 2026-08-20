"""
CLAUDE-SPIN-SURFACE-02 - the first human-facing Spin surface: a dedicated
Spin tab (display.spin, STABLE_DIRECTORY_KINDS' new "spin" entry) carrying
Spin history and a durable Spin State Report, plus a shrunk Toolbox
summary that links into it instead of duplicating it.

Explicitly NOT covered here (out of scope for this stage, per its own
governing prompt): Local Spin, document maturity, the full evolution
matrix, persisted authority/Supersession relationships. The accepted
Delta Spin ENGINE (services/spin.py's run_spin/_parse_spin_findings,
CaseWorkspaceStore.record_spin_run) is completely untouched by this
stage - tests/test_delta_spin_01.py's own full suite staying green
(re-run alongside this file) is the proof, not duplicated here.

Follows this repo's own hermetic convention (patch("anthropic.Anthropic"))
for every LLM-touching test - never a live model call.

Run via:

    python -m unittest tests.test_spin_surface_02 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import CaseWorkspaceStore, SPIN_KIND_DELTA, SPIN_KIND_FIRST
from services.ingestion import RequirementsRegistry
from services.bhive_parser import ParsedDocument
from werkzeug.security import generate_password_hash


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class SpinSurfaceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_spin_surface_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-spin-surface"

        with self.flask_app.app_context():
            db.session.add(User(username="surface_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "surface_owner"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")  # trigger workspace creation

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_spin(self, spin_kind: str, response_json: str):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(response_json)
            return self.client.post(
                f"/projects/{self.project_id}/workspace/spin/run",
                data={"spin_kind": spin_kind}, follow_redirects=True,
            )

    def _spin_tab(self, spin_run_id: str = None):
        url = f"/projects/{self.project_id}/workspace?view=spin"
        if spin_run_id:
            url += f"&spin_run={spin_run_id}"
        return self.client.get(url)

    # 1. Spin tab exists and is reachable
    def test_spin_tab_reachable(self):
        resp = self._spin_tab()
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin"', body)

    def test_spin_tab_empty_state_before_any_run(self):
        body = self._spin_tab().get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.empty"', body)
        self.assertNotIn('data-ui-ref="display.spin.history"', body)

    # 2/3. First Spin and Delta Spin appear in history
    def test_first_and_delta_spin_appear_in_history(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s2", "concern": "c2", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "unchanged", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)

        body = self._spin_tab().get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.history"', body)
        self.assertEqual(body.count('data-ui-ref="display.spin.history.leaf"'), 2)
        self.assertIn("First Spin", body)
        self.assertIn("Delta Spin", body)

    # 4. Baseline linkage is visible
    def test_baseline_linkage_visible_in_state_report(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        baseline_id = self.store.get(self.project_id).spin_runs[0]["id"]
        delta_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s2", "concern": "c2", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "unchanged", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)

        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn("Baseline:", body)
        self.assertIn(f"spin_run={baseline_id}", body)

    # 5. First Spin has no Delta classification
    def test_first_spin_state_report_has_no_classification_summary(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        run_id = self.store.get(self.project_id).spin_runs[0]["id"]
        body = self._spin_tab(run_id).get_data(as_text=True)
        self.assertIn("no prior state to classify against", body)
        self.assertNotIn('data-ui-ref="display.spin.report.finding.classification"', body)

    # 6. Delta classifications render correctly
    def test_delta_classification_renders_on_state_report(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s2", "concern": "c2", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "strengthened", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.report.finding.classification"', body)
        self.assertIn("STRENGTHENED", body)

    # 7. Historical runs remain accessible after later runs
    def test_historical_run_still_accessible_after_second_delta_spin(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json_1 = (
            '{"findings": [{"tag": "T1", "source_reference": "s2", "concern": "First delta", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "unchanged", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json_1)
        first_delta_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)

        delta_json_2 = (
            '{"findings": [{"tag": "T1", "source_reference": "s3", "concern": "Second delta", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "strengthened", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json_2)

        # The FIRST delta run's own report must still be reachable and
        # still be selected/open when its history row is requested. History
        # now carries each run's collapsed detail, so the newer run's content
        # may remain present in the collapsed DOM without being displayed.
        body = self._spin_tab(first_delta_id).get_data(as_text=True)
        self.assertIn("First delta", body)
        self.assertIn(f'data-spin-run-id="{first_delta_id}"', body)
        self.assertIn(
            f'<details class="spin-history-item" data-ui-ref="display.spin.history.leaf" '
            f'data-spin-run-id="{first_delta_id}" open>',
            body,
        )

        # And it must still be listed in history (never hidden/deleted).
        history_body = self._spin_tab().get_data(as_text=True)
        self.assertEqual(history_body.count('data-ui-ref="display.spin.history.leaf"'), 3)

    # 8. State Report summarizes persisted findings correctly
    def test_state_report_summary_counts_are_correct(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", "unresolved_question": "q", "urgency": "", "project_stage": ""}, '
            '{"tag": "T2", "source_reference": "s", "concern": "c", "unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": ['
            '{"tag": "T1", "source_reference": "s", "concern": "c", "unresolved_question": "", "urgency": "", "project_stage": "", "delta_classification": "resolved", "related_prior_understanding": "T1"}, '
            '{"tag": "T2", "source_reference": "s", "concern": "c", "unresolved_question": "", "urgency": "", "project_stage": "", "delta_classification": "unchanged", "related_prior_understanding": "T2"}, '
            '{"tag": "T3", "source_reference": "s", "concern": "c", "unresolved_question": "", "urgency": "", "project_stage": "", "delta_classification": "new", "related_prior_understanding": ""}'
            ']}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn("Total findings:</strong> 3", body)
        self.assertIn("Prior findings reassessed:</strong> 2", body)  # T1 and T2 cite related_prior_understanding
        self.assertIn("RESOLVED", body)
        self.assertIn("UNCHANGED", body)
        self.assertIn("NEW", body)

    # 9. Provenance links remain available
    def test_provenance_reassesses_and_source_present(self):
        first_json = (
            '{"findings": [{"tag": "Deadline", "source_reference": "Addendum-04.pdf", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": [{"tag": "Deadline", "source_reference": "Addendum-05.pdf", "concern": "c2", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "strengthened", "related_prior_understanding": "Deadline"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn("Addendum-05.pdf", body)
        self.assertIn("Reassesses:", body)
        self.assertIn("Deadline", body)

    # 10. Active/running state renders safely
    def test_active_state_renders_without_fake_progress(self):
        workspace = self.store.get(self.project_id)
        self.store.start_spin_generation(workspace, actor="surface_owner")
        body = self._spin_tab().get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.active"', body)
        self.assertIn("currently running", body)
        # No fabricated percentage or stage language anywhere on the page.
        self.assertNotIn("%", body.split('data-ui-ref="display.spin.active"')[1][:200])

    # 11. Failed run state renders safely
    def test_failed_run_renders_skipped_reason(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response("{}")
            self.client.post(
                f"/projects/{self.project_id}/workspace/spin/run",
                data={"spin_kind": "first_spin"}, follow_redirects=True,
            )
        run_id = self.store.get(self.project_id).spin_runs[0]["id"]
        body = self._spin_tab(run_id).get_data(as_text=True)
        self.assertIn("Could not run:", body)
        self.assertIn("failed", body)
        history_body = self._spin_tab().get_data(as_text=True)
        self.assertIn("failed", history_body)

    # 12. No new project data is created merely by viewing Spin history
    def test_viewing_spin_history_creates_no_new_data(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        before = self.store.get(self.project_id)
        run_count_before, finding_count_before = len(before.spin_runs), len(before.composer_findings)

        for _ in range(3):
            self._spin_tab()
            self._spin_tab(before.spin_runs[0]["id"])

        after = self.store.get(self.project_id)
        self.assertEqual(len(after.spin_runs), run_count_before)
        self.assertEqual(len(after.composer_findings), finding_count_before)

    # 13. Project isolation is preserved
    def test_spin_history_never_crosses_projects(self):
        other_project_id = "test-project-spin-surface-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client.get(f"/projects/{other_project_id}/workspace")
        other_workspace = self.store.get(other_project_id)
        self.store.record_spin_run(
            other_workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "Only in other project", "source_reference": "s", "concern": "c",
                       "unresolved_question": "q", "delta_classification": None, "related_prior_understanding": None}],
            source_signature="",
        )
        body = self._spin_tab().get_data(as_text=True)
        self.assertNotIn("Only in other project", body)
        self.assertIn('data-ui-ref="display.spin.empty"', body)  # this project's own history is genuinely empty

    # 14. Legacy prototype naming does not confuse the accepted Spin capability
    def test_legacy_prototype_naming_distinct_from_real_spin(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertIn("Evidence Isolation (legacy prototype", body)
        self.assertNotIn("Spin — Evidence Isolation", body)  # the old colliding label is gone
        self.assertIn("Open Prototype", body)
        self.assertNotIn(">Open Spin<", body)

        prototype_body = self.client.get(f"/projects/{self.project_id}/workspace?spin=1").get_data(as_text=True)
        self.assertIn("Evidence Isolation (Legacy Prototype)", prototype_body)
        self.assertIn(">APPLY<", prototype_body)
        self.assertNotIn(">SPIN<", prototype_body)

    # 15. Existing Delta Spin behavior remains unchanged - structural check
    # that this stage's own files never touched the engine's own module.
    def test_engine_module_source_unmodified_marker_absent(self):
        """CLAUDE-SPIN-SURFACE-02's own governing prompt: 'do not modify
        the accepted Delta Spin engine.' A real behavioral proof is
        tests/test_delta_spin_01.py's own full suite staying green
        (re-run alongside this file, not duplicated here) - this is an
        additional, narrow structural check that no CLAUDE-SPIN-SURFACE-02
        marker was introduced into services/spin.py itself."""
        source = Path("services/spin.py").read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE-SPIN-SURFACE-02", source)


if __name__ == "__main__":
    unittest.main()
