"""
CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01 - bounded first slice: the Spin State
Report's per-finding structural composition (routes/workspace.py's own
`_SPIN_CLASSIFICATION_TREATMENT` / `_spin_finding_presentation` /
`_build_spin_state_report`'s new `presented_findings`), plus the resulting
template rendering (weight-tier class, `open` attribute, inline accent bar,
rank-ordering).

Explicitly NOT re-tested here: the accepted Delta Spin ENGINE
(services/spin.py) or the Spin Surface's own history/baseline/provenance
behavior - tests/test_delta_spin_01.py and tests/test_spin_surface_02.py
staying green alongside this file is that proof, not duplicated here. This
file covers only the NEW composition/presentation layer.

Follows this repo's own hermetic convention (patch("anthropic.Anthropic"))
for every LLM-touching test - never a live model call.

Run via:

    python -m unittest tests.test_bauhaus_spin_findings_01 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from routes.workspace import (
    _SPIN_CLASSIFICATION_TREATMENT,
    _SPIN_DEFAULT_TREATMENT,
    _build_spin_state_report,
    _spin_finding_presentation,
)
from services.case_workspace import (
    CaseWorkspaceStore,
    KNOWN_SPIN_DELTA_CLASSIFICATIONS,
    SPIN_KIND_DELTA,
    SPIN_KIND_FIRST,
)
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


class TreatmentTableTests(unittest.TestCase):
    """Pure logic, no Flask app needed."""

    def test_every_known_classification_has_its_own_treatment_entry(self):
        for classification in KNOWN_SPIN_DELTA_CLASSIFICATIONS:
            self.assertIn(
                classification, _SPIN_CLASSIFICATION_TREATMENT,
                f"{classification!r} has no explicit treatment - would silently "
                "fall back to the default, collapsing the 8-value vocabulary.",
            )

    def test_treatment_table_has_no_extra_unknown_classifications(self):
        self.assertEqual(
            set(_SPIN_CLASSIFICATION_TREATMENT.keys()), set(KNOWN_SPIN_DELTA_CLASSIFICATIONS)
        )

    def test_every_entry_has_the_full_required_shape(self):
        required_keys = {"rank", "weight_class", "accent", "bar_px", "border_style"}
        for classification, treatment in _SPIN_CLASSIFICATION_TREATMENT.items():
            self.assertEqual(set(treatment.keys()), required_keys, classification)

    def test_ranks_are_unique_across_all_classifications(self):
        ranks = [t["rank"] for t in _SPIN_CLASSIFICATION_TREATMENT.values()]
        self.assertEqual(len(ranks), len(set(ranks)))

    def test_only_two_non_default_accent_colors_are_used(self):
        # Product Owner constraint: color stays minimal, composition (scale/
        # order/border weight) carries the primary consequence signal.
        accents = {t["accent"] for t in _SPIN_CLASSIFICATION_TREATMENT.values()}
        self.assertEqual(accents, {"attention-amber", "machine-blue", "accepted-green"})

    def test_new_verification_gap_is_the_most_urgent_rank(self):
        self.assertEqual(_SPIN_CLASSIFICATION_TREATMENT["new_verification_gap"]["rank"], 0)
        self.assertEqual(
            _SPIN_CLASSIFICATION_TREATMENT["new_verification_gap"]["accent"], "attention-amber"
        )

    def test_unchanged_is_the_quietest_tier(self):
        treatment = _SPIN_CLASSIFICATION_TREATMENT["unchanged"]
        self.assertEqual(treatment["weight_class"], "spin-weight-quiet")
        self.assertEqual(treatment["bar_px"], 1)

    def test_resolved_gets_the_accepted_green_accent(self):
        self.assertEqual(_SPIN_CLASSIFICATION_TREATMENT["resolved"]["accent"], "accepted-green")

    def test_default_treatment_is_moderate_not_maximal(self):
        # A first_spin finding has nothing to be more/less consequential
        # relative to - treating it as maximally urgent would itself be
        # exactly the "louder = more severe" mistake the design corrected.
        self.assertEqual(_SPIN_DEFAULT_TREATMENT["weight_class"], "spin-weight-high")
        self.assertNotEqual(_SPIN_DEFAULT_TREATMENT["weight_class"], "spin-weight-max")


class SpinFindingPresentationTests(unittest.TestCase):
    def test_presentation_merges_treatment_without_losing_original_fields(self):
        finding = {"tag": "T1", "concern": "c", "delta_classification": "strengthened"}
        presented = _spin_finding_presentation(finding)
        self.assertEqual(presented["tag"], "T1")
        self.assertEqual(presented["concern"], "c")
        self.assertEqual(presented["rank"], 2)
        self.assertEqual(presented["weight_class"], "spin-weight-high")

    def test_presentation_never_mutates_the_original_finding_dict(self):
        finding = {"tag": "T1", "delta_classification": "new"}
        _spin_finding_presentation(finding)
        self.assertEqual(set(finding.keys()), {"tag", "delta_classification"})

    def test_missing_classification_falls_back_to_default_treatment(self):
        finding = {"tag": "T1"}
        presented = _spin_finding_presentation(finding)
        self.assertEqual(presented["rank"], _SPIN_DEFAULT_TREATMENT["rank"])
        self.assertEqual(presented["weight_class"], _SPIN_DEFAULT_TREATMENT["weight_class"])

    def test_unrecognized_classification_string_falls_back_to_default(self):
        finding = {"tag": "T1", "delta_classification": "not_a_real_value"}
        presented = _spin_finding_presentation(finding)
        self.assertEqual(presented["rank"], _SPIN_DEFAULT_TREATMENT["rank"])


class BuildSpinStateReportOrderingTests(unittest.TestCase):
    def test_presented_findings_are_sorted_by_rank_not_insertion_order(self):
        run_view = {
            "spin_kind": SPIN_KIND_DELTA,
            "findings": [
                {"tag": "A", "delta_classification": "unchanged"},       # rank 7
                {"tag": "B", "delta_classification": "new_verification_gap"},  # rank 0
                {"tag": "C", "delta_classification": "resolved"},        # rank 6
            ],
        }
        report = _build_spin_state_report(run_view)
        tags_in_order = [f["tag"] for f in report["presented_findings"]]
        self.assertEqual(tags_in_order, ["B", "C", "A"])

    def test_equal_rank_findings_keep_stable_relative_order(self):
        run_view = {
            "spin_kind": SPIN_KIND_DELTA,
            "findings": [
                {"tag": "First-new", "delta_classification": "new"},
                {"tag": "Second-new", "delta_classification": "new"},
            ],
        }
        report = _build_spin_state_report(run_view)
        tags_in_order = [f["tag"] for f in report["presented_findings"]]
        self.assertEqual(tags_in_order, ["First-new", "Second-new"])

    def test_first_spin_findings_all_get_the_default_treatment(self):
        run_view = {
            "spin_kind": SPIN_KIND_FIRST,
            "findings": [{"tag": "A"}, {"tag": "B"}],
        }
        report = _build_spin_state_report(run_view)
        for f in report["presented_findings"]:
            self.assertEqual(f["weight_class"], _SPIN_DEFAULT_TREATMENT["weight_class"])

    def test_underlying_findings_list_is_left_untouched(self):
        # Toolbox summary and other existing readers use run_view["findings"]
        # directly - it must stay exactly as it was, unsorted and unannotated.
        original_findings = [
            {"tag": "A", "delta_classification": "unchanged"},
            {"tag": "B", "delta_classification": "new_verification_gap"},
        ]
        run_view = {"spin_kind": SPIN_KIND_DELTA, "findings": original_findings}
        _build_spin_state_report(run_view)
        self.assertEqual([f["tag"] for f in original_findings], ["A", "B"])
        self.assertNotIn("rank", original_findings[0])


class SpinFindingTemplateRenderingTests(unittest.TestCase):
    """Route-level: confirm the actual HTML reflects the composition."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_bauhaus_spin_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-bauhaus-spin"

        with self.flask_app.app_context():
            db.session.add(User(username="bauhaus_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "bauhaus_owner"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")

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

    def test_max_and_high_tier_findings_render_open_quiet_tier_does_not(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": ['
            '{"tag": "Gap", "source_reference": "s", "concern": "c", "unresolved_question": "q", '
            '"urgency": "", "project_stage": "", "delta_classification": "new_verification_gap", "related_prior_understanding": ""}, '
            '{"tag": "Same", "source_reference": "s", "concern": "c", "unresolved_question": "", '
            '"urgency": "", "project_stage": "", "delta_classification": "unchanged", "related_prior_understanding": "T1"}'
            ']}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)

        self.assertIn('class="spin-finding spin-weight-max"', body)
        self.assertIn('class="spin-finding spin-weight-quiet"', body)
        # The max-tier <details> tag must carry the open attribute (between
        # its own class and its closing >); the quiet-tier one must not.
        max_block_start = body.index('class="spin-finding spin-weight-max"')
        max_block = body[max_block_start:body.index(">", max_block_start)]
        self.assertIn("open", max_block)

        quiet_block_start = body.index('class="spin-finding spin-weight-quiet"')
        quiet_block = body[quiet_block_start:body.index(">", quiet_block_start)]
        self.assertNotIn("open", quiet_block)

    def test_accent_bar_inline_style_reflects_classification(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "new_verification_gap", "related_prior_understanding": ""}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn("border-left:4px solid var(--attention-amber);", body)

    def test_findings_render_in_rank_order_not_model_output_order(self):
        first_json = (
            '{"findings": [{"tag": "A", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}, '
            '{"tag": "B", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        # Model returns "unchanged" (quiet, rank 7) BEFORE "new_verification_gap" (rank 0).
        delta_json = (
            '{"findings": ['
            '{"tag": "A", "source_reference": "s", "concern": "quiet-one", "unresolved_question": "", '
            '"urgency": "", "project_stage": "", "delta_classification": "unchanged", "related_prior_understanding": "A"}, '
            '{"tag": "B", "source_reference": "s", "concern": "urgent-one", "unresolved_question": "", '
            '"urgency": "", "project_stage": "", "delta_classification": "new_verification_gap", "related_prior_understanding": ""}'
            ']}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertLess(body.index("urgent-one"), body.index("quiet-one"))

    def test_full_classification_text_still_renders_verbatim(self):
        # Composition changes PRESENTATION only - the literal classification
        # value must still be visible in full, uppercased, as before.
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        delta_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "", "urgency": "", "project_stage": "", '
            '"delta_classification": "new_verification_gap", "related_prior_understanding": "T1"}]}'
        )
        self._run_spin(SPIN_KIND_DELTA, delta_json)
        delta_run_id = next(r["id"] for r in self.store.get(self.project_id).spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        body = self._spin_tab(delta_run_id).get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.report.finding.classification"', body)
        self.assertIn("NEW_VERIFICATION_GAP", body)

    def test_first_spin_findings_render_with_default_treatment_class(self):
        first_json = (
            '{"findings": [{"tag": "T1", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        run_id = self.store.get(self.project_id).spin_runs[0]["id"]
        body = self._spin_tab(run_id).get_data(as_text=True)
        self.assertIn('class="spin-finding spin-weight-high"', body)


if __name__ == "__main__":
    unittest.main()
