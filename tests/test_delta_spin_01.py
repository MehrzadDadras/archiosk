"""
CLAUDE-DELTA-SPIN-01 - the first governed Delta Spin: a comprehensive,
change-aware project-intelligence pass, distinguished from an ordinary
Composer-emitted finding by provenance (services.case_workspace.SpinRun),
never a second finding type (see ComposerFinding's own docstring and
governance/specified-unbuilt/spin-project-intelligence-preview.md, which
this stage authorizes drawing on for the first time).

Covers: Spin availability/discoverability, the delta classification
vocabulary, authority preservation (non-binding status survives a Spin
the same way it survives ordinary Composer Q&A), resolved/indeterminate/
new-verification-gap finding behavior, cross-disciplinary propagation
text, provenance (spin_run_id/baseline linkage), repeated-run stability,
and project isolation. Follows this repo's own hermetic convention
(patch("anthropic.Anthropic")) for every LLM-touching test - never a
live model call.

Run via:

    python -m unittest tests.test_delta_spin_01 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    KNOWN_SPIN_DELTA_CLASSIFICATIONS,
    SPIN_DELTA_RESOLVED,
    SPIN_KIND_DELTA,
    SPIN_KIND_FIRST,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.ingestion import RequirementsRegistry
from services.bhive_parser import ParsedDocument
from services.spin import (
    _build_prompt,
    _parse_spin_findings,
    _select_comprehensive_document_evidence,
)
from werkzeug.security import generate_password_hash


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ParseSpinFindingsTests(unittest.TestCase):
    def test_valid_first_spin_item_has_no_classification(self):
        raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                "delta_classification": "resolved"}]  # model mistakenly supplied one anyway
        result = _parse_spin_findings(raw, spin_kind=SPIN_KIND_FIRST)
        self.assertIsNone(result[0]["delta_classification"])  # never carried for a first_spin

    def test_valid_delta_spin_item_keeps_classification(self):
        raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                "delta_classification": "resolved", "related_prior_understanding": "Earlier finding"}]
        result = _parse_spin_findings(raw, spin_kind=SPIN_KIND_DELTA)
        self.assertEqual(result[0]["delta_classification"], SPIN_DELTA_RESOLVED)
        self.assertEqual(result[0]["related_prior_understanding"], "Earlier finding")

    def test_unknown_classification_value_dropped_to_none(self):
        """The model's own JSON is read back, never trusted on faith - an
        invalid/hallucinated classification string must never be
        persisted as though it were a real closed-vocabulary value."""
        raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                "delta_classification": "definitely_fixed_trust_me"}]
        result = _parse_spin_findings(raw, spin_kind=SPIN_KIND_DELTA)
        self.assertIsNone(result[0]["delta_classification"])

    def test_indeterminate_is_a_real_first_class_value_never_dropped(self):
        raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                "delta_classification": "indeterminate"}]
        result = _parse_spin_findings(raw, spin_kind=SPIN_KIND_DELTA)
        self.assertEqual(result[0]["delta_classification"], "indeterminate")

    def test_item_missing_tag_is_dropped(self):
        self.assertEqual(_parse_spin_findings([{"concern": "c"}], spin_kind=SPIN_KIND_FIRST), [])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(_parse_spin_findings("not a list", spin_kind=SPIN_KIND_FIRST), [])
        self.assertEqual(_parse_spin_findings(None, spin_kind=SPIN_KIND_DELTA), [])

    def test_capped_at_max_spin_findings(self):
        from services.spin import _MAX_SPIN_FINDINGS

        raw = [{"tag": f"T{i}", "source_reference": "", "concern": "", "unresolved_question": ""}
               for i in range(_MAX_SPIN_FINDINGS + 5)]
        self.assertEqual(len(_parse_spin_findings(raw, spin_kind=SPIN_KIND_FIRST)), _MAX_SPIN_FINDINGS)

    def test_every_closed_vocabulary_value_round_trips(self):
        for value in KNOWN_SPIN_DELTA_CLASSIFICATIONS:
            raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                    "delta_classification": value}]
            result = _parse_spin_findings(raw, spin_kind=SPIN_KIND_DELTA)
            self.assertEqual(result[0]["delta_classification"], value)


class SelectComprehensiveDocumentEvidenceTests(unittest.TestCase):
    def test_changed_source_gets_larger_excerpt_allowance(self):
        many_excerpts = [f"row {i}" for i in range(100)]
        docs = [
            {"filename": "unchanged.pdf", "relative_path": "unchanged.pdf", "excerpts": many_excerpts, "added_at": "2026-01-01"},
            {"filename": "changed.pdf", "relative_path": "changed.pdf", "excerpts": many_excerpts, "added_at": "2026-06-01"},
        ]
        selected = _select_comprehensive_document_evidence(docs, changed_source_keys={"changed.pdf"})
        changed_entry = next(d for d in selected if d["filename"] == "changed.pdf")
        unchanged_entry = next(d for d in selected if d["filename"] == "unchanged.pdf")
        self.assertGreater(len(changed_entry["excerpts"]), len(unchanged_entry["excerpts"]))
        self.assertTrue(changed_entry["is_changed_since_baseline"])
        self.assertFalse(unchanged_entry["is_changed_since_baseline"])

    def test_changed_documents_sort_first(self):
        docs = [
            {"filename": "old-unchanged.pdf", "relative_path": "old-unchanged.pdf", "excerpts": ["x"], "added_at": "2026-06-01"},
            {"filename": "changed.pdf", "relative_path": "changed.pdf", "excerpts": ["x"], "added_at": "2026-01-01"},
        ]
        selected = _select_comprehensive_document_evidence(docs, changed_source_keys={"changed.pdf"})
        self.assertEqual(selected[0]["filename"], "changed.pdf")

    def test_bounded_at_max_documents(self):
        docs = [{"filename": f"d{i}.pdf", "relative_path": f"d{i}.pdf", "excerpts": ["x"], "added_at": "2026-01-01"}
                for i in range(50)]
        selected = _select_comprehensive_document_evidence(docs, changed_source_keys=None, max_documents=10)
        self.assertEqual(len(selected), 10)

    def test_no_changed_keys_still_returns_all_names_worth_of_documents(self):
        docs = [{"filename": f"d{i}.pdf", "relative_path": f"d{i}.pdf", "excerpts": ["x"], "added_at": "2026-01-01"}
                for i in range(5)]
        selected = _select_comprehensive_document_evidence(docs, changed_source_keys=None)
        self.assertEqual(len(selected), 5)


class PromptAuthorityPreservationTests(unittest.TestCase):
    """The prompt itself must carry every authority-preservation rule
    project_qa.BEHAVIORAL_CONTRACT already establishes (reused, not
    duplicated), plus the Spin-specific delta/cross-disciplinary rules -
    never flattened for convenience."""

    def test_delta_prompt_asks_for_classification_and_reassessment_field(self):
        prompt = _build_prompt(
            SPIN_KIND_DELTA, "rfp.pdf", [], [], [], prior_findings=[{"tag": "T", "concern": "c",
            "source_reference": "s", "unresolved_question": "q"}],
        )
        self.assertIn("delta_classification", prompt)
        self.assertIn("related_prior_understanding", prompt)
        self.assertIn("PRIOR PROJECT UNDERSTANDING", prompt)

    def test_first_spin_prompt_never_asks_for_classification(self):
        prompt = _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [])
        self.assertNotIn("delta_classification", prompt)

    def test_delta_prompt_with_no_prior_findings_says_so_honestly(self):
        prompt = _build_prompt(SPIN_KIND_DELTA, "rfp.pdf", [], [], [], prior_findings=[])
        self.assertIn("No prior Spin findings were recorded", prompt)

    def test_changed_source_marker_appears_in_prompt(self):
        docs = [{"filename": "addendum-4.pdf", "relative_path": "addendum-4.pdf", "excerpts": ["x"], "added_at": "2026-06-01"}]
        prompt = _build_prompt(
            SPIN_KIND_DELTA, "rfp.pdf", [], [], [], additional_document_evidence=docs,
            changed_source_keys={"addendum-4.pdf"},
        )
        self.assertIn("[NEW OR CHANGED SINCE BASELINE]", prompt)

    def test_behavioral_contract_carries_authority_rules_from_project_qa(self):
        from services.spin import BEHAVIORAL_CONTRACT

        self.assertIn("non-binding", BEHAVIORAL_CONTRACT)
        self.assertIn("never present it as a confirmed requirement", BEHAVIORAL_CONTRACT)
        self.assertIn("you never create one yourself", BEHAVIORAL_CONTRACT)

    def test_behavioral_contract_states_recency_never_upgrades_authority(self):
        from services.spin import BEHAVIORAL_CONTRACT

        self.assertIn("never means its", BEHAVIORAL_CONTRACT)
        self.assertIn("restricted/tenant-specific", BEHAVIORAL_CONTRACT)

    def test_behavioral_contract_asks_for_cross_disciplinary_consequence(self):
        from services.spin import BEHAVIORAL_CONTRACT

        self.assertIn("cross-disciplinary", BEHAVIORAL_CONTRACT)

    def test_behavioral_contract_never_authorizes_a_decision(self):
        from services.spin import BEHAVIORAL_CONTRACT

        self.assertIn("never authorized to decide", BEHAVIORAL_CONTRACT)


class RecordSpinRunStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_delta_spin_"))
        self.project_id = "test-project-delta-spin"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(
            self.project_id, register_document_source={"filename": "rfp.md"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_first_spin_persists_run_and_findings_with_no_classification(self):
        run = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                       "delta_classification": None, "related_prior_understanding": None}],
            source_signature="",
        )
        self.assertEqual(run["spin_kind"], SPIN_KIND_FIRST)
        self.assertEqual(len(run["finding_ids"]), 1)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.spin_runs), 1)
        self.assertEqual(len(workspace.composer_findings), 1)
        finding = workspace.composer_findings[0]
        self.assertEqual(finding["spin_run_id"], run["id"])
        self.assertIsNone(finding["delta_classification"])

    def test_delta_spin_finding_carries_classification_and_baseline_link(self):
        baseline = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "Height discrepancy", "source_reference": "s", "concern": "c",
                       "unresolved_question": "q", "delta_classification": None, "related_prior_understanding": None}],
            source_signature="",
        )
        workspace = self.store.get(self.project_id)
        delta = self.store.record_spin_run(
            workspace, spin_kind=SPIN_KIND_DELTA, actor="owner1",
            findings=[{"tag": "Height discrepancy", "source_reference": "s2", "concern": "resolved now",
                       "unresolved_question": "", "delta_classification": SPIN_DELTA_RESOLVED,
                       "related_prior_understanding": "Height discrepancy"}],
            source_signature="", baseline_spin_run_id=baseline["id"],
        )
        self.assertEqual(delta["baseline_spin_run_id"], baseline["id"])
        workspace = self.store.get(self.project_id)
        delta_finding = next(cf for cf in workspace.composer_findings if cf["spin_run_id"] == delta["id"])
        self.assertEqual(delta_finding["delta_classification"], SPIN_DELTA_RESOLVED)
        self.assertEqual(delta_finding["related_prior_understanding"], "Height discrepancy")

    def test_ran_false_persists_the_attempt_with_no_findings(self):
        """Honest-degrade contract, mirroring ProjectBriefingResult/
        ProjectQAResult - a Spin that could not actually call the model
        still gets a persisted, visible record, never silently dropped."""
        run = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[], source_signature="", ran=False, skipped_reason="No API key configured.",
        )
        self.assertFalse(run["ran"])
        self.assertEqual(run["skipped_reason"], "No API key configured.")
        self.assertEqual(run["finding_ids"], [])
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.composer_findings), 0)

    def test_unknown_classification_rejected_by_add_composer_finding_directly(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_composer_finding(
                self.workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
                delta_classification="not_a_real_value",
            )

    def test_latest_spin_run_for_resolves_most_recent_by_kind(self):
        first = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1", findings=[], source_signature="",
        )
        workspace = self.store.get(self.project_id)
        latest = self.store.latest_spin_run_for(workspace, spin_kind=SPIN_KIND_FIRST)
        self.assertEqual(latest["id"], first["id"])

    def test_latest_spin_run_for_returns_none_when_no_runs_exist(self):
        self.assertIsNone(self.store.latest_spin_run_for(self.workspace, spin_kind=SPIN_KIND_FIRST))

    def test_ordinary_composer_finding_unaffected_by_new_fields(self):
        """Backward compatibility: every existing add_composer_finding
        caller (ordinary chat) is completely unaffected by the new
        optional kwargs."""
        record = self.store.add_composer_finding(
            self.workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
        )
        self.assertIsNone(record["spin_run_id"])
        self.assertIsNone(record["delta_classification"])
        self.assertIsNone(record["related_prior_understanding"])

    def test_repeated_delta_spin_against_same_baseline_is_stable(self):
        """Idempotency/repeat-run stability: running Delta Spin twice
        against the SAME baseline never mutates the baseline itself and
        never corrupts state - each run is its own independent record."""
        baseline = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                       "delta_classification": None, "related_prior_understanding": None}],
            source_signature="",
        )
        workspace = self.store.get(self.project_id)
        delta_1 = self.store.record_spin_run(
            workspace, spin_kind=SPIN_KIND_DELTA, actor="owner1", findings=[], source_signature="",
            baseline_spin_run_id=baseline["id"],
        )
        workspace = self.store.get(self.project_id)
        delta_2 = self.store.record_spin_run(
            workspace, spin_kind=SPIN_KIND_DELTA, actor="owner1", findings=[], source_signature="",
            baseline_spin_run_id=baseline["id"],
        )
        self.assertNotEqual(delta_1["id"], delta_2["id"])
        workspace = self.store.get(self.project_id)
        baseline_reloaded = next(r for r in workspace.spin_runs if r["id"] == baseline["id"])
        self.assertEqual(baseline_reloaded["finding_ids"], baseline["finding_ids"])  # untouched
        self.assertEqual(len(workspace.spin_runs), 3)


class SpinRunProjectIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_delta_spin_iso_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_spin_runs_never_cross_projects(self):
        for pid in ("project-a", "project-b"):
            RequirementsRegistry(self.tmp_dir).save(
                ParsedDocument(project_id=pid, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
            )
        ws_a = self.store.get_or_create("project-a", register_document_source={"filename": "rfp.md"})
        self.store.get_or_create("project-b", register_document_source={"filename": "rfp.md"})

        self.store.record_spin_run(
            ws_a, spin_kind=SPIN_KIND_FIRST, actor="owner1",
            findings=[{"tag": "Only in A", "source_reference": "s", "concern": "c", "unresolved_question": "q",
                       "delta_classification": None, "related_prior_understanding": None}],
            source_signature="",
        )
        ws_a_reloaded = self.store.get("project-a")
        ws_b_reloaded = self.store.get("project-b")
        self.assertEqual(len(ws_a_reloaded.spin_runs), 1)
        self.assertEqual(len(ws_b_reloaded.spin_runs), 0)
        self.assertEqual(len(ws_a_reloaded.composer_findings), 1)
        self.assertEqual(len(ws_b_reloaded.composer_findings), 0)


class RunSpinRouteTests(unittest.TestCase):
    """Route-level: proves the real HTTP trigger, security-policy gate,
    baseline resolution, and Toolbox rendering all work end to end."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_delta_spin_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-delta-spin-route"

        with self.flask_app.app_context():
            db.session.add(User(username="spin_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "spin_owner"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")  # trigger workspace creation

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _run_spin(self, spin_kind: str, response_json: str, baseline_spin_run_id: str = None):
        data = {"spin_kind": spin_kind}
        if baseline_spin_run_id:
            data["baseline_spin_run_id"] = baseline_spin_run_id
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(response_json)
            return self.client.post(
                f"/projects/{self.project_id}/workspace/spin/run", data=data, follow_redirects=True,
            )

    def test_no_spin_yet_shows_empty_state_and_no_delta_button(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.spin"', body)
        self.assertIn('data-ui-ref="toolbox.spin.empty"', body)
        self.assertIn('data-ui-ref="toolbox.spin.run-first"', body)
        self.assertNotIn('data-ui-ref="toolbox.spin.run-delta"', body)

    def test_delta_spin_refused_with_no_baseline(self):
        resp = self._run_spin(
            SPIN_KIND_DELTA,
            '{"findings": []}',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("needs a completed First Spin", body)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.spin_runs), 0)  # refused before any run was attempted

    def test_first_spin_creates_run_with_no_classification_and_is_discoverable(self):
        response_json = (
            '{"findings": [{"tag": "Submission deadline", "source_reference": "Sec 3.1", '
            '"concern": "Deadline unclear", "unresolved_question": "What is the extended date?", '
            '"urgency": "", "project_stage": ""}]}'
        )
        resp = self._run_spin(SPIN_KIND_FIRST, response_json)
        body = resp.get_data(as_text=True)
        # CLAUDE-SPIN-SURFACE-02: the Toolbox now shows only a one-line
        # summary (kind + count) - full finding detail lives on the Spin
        # tab (display.spin), checked separately below.
        self.assertIn("First Spin", body)
        self.assertIn('data-ui-ref="toolbox.spin.latest-summary"', body)

        spin_tab_resp = self.client.get(f"/projects/{self.project_id}/workspace?view=spin")
        spin_tab_body = spin_tab_resp.get_data(as_text=True)
        self.assertIn("Submission deadline", spin_tab_body)
        self.assertNotIn("None", spin_tab_body)  # delta_classification is None - must never render literally

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.spin_runs), 1)
        self.assertTrue(workspace.spin_runs[0]["ran"])
        self.assertIsNone(workspace.composer_findings[0]["delta_classification"])

    def test_delta_spin_after_first_spin_carries_classification_and_provenance(self):
        first_json = (
            '{"findings": [{"tag": "Height discrepancy", "source_reference": "Drawing L03", '
            '"concern": "Clear height below minimum", "unresolved_question": "Will it be corrected?", '
            '"urgency": "", "project_stage": ""}]}'
        )
        self._run_spin(SPIN_KIND_FIRST, first_json)
        baseline_id = self.store.get(self.project_id).spin_runs[0]["id"]

        delta_json = (
            '{"findings": [{"tag": "Height discrepancy", "source_reference": "Drawing L03 Rev03", '
            '"concern": "Clear height now matches minimum", "unresolved_question": "", '
            '"urgency": "", "project_stage": "", "delta_classification": "resolved", '
            '"related_prior_understanding": "Height discrepancy"}]}'
        )
        resp = self._run_spin(SPIN_KIND_DELTA, delta_json)
        body = resp.get_data(as_text=True)
        self.assertIn("Delta Spin", body)  # Toolbox summary line still names the kind

        spin_tab_resp = self.client.get(f"/projects/{self.project_id}/workspace?view=spin")
        spin_tab_body = spin_tab_resp.get_data(as_text=True)
        self.assertIn("Delta Spin", spin_tab_body)
        self.assertIn("RESOLVED", spin_tab_body)
        self.assertIn("Reassesses", spin_tab_body)
        self.assertIn("Height discrepancy", spin_tab_body)

        workspace = self.store.get(self.project_id)
        delta_run = next(r for r in workspace.spin_runs if r["spin_kind"] == SPIN_KIND_DELTA)
        self.assertEqual(delta_run["baseline_spin_run_id"], baseline_id)
        delta_finding = next(cf for cf in workspace.composer_findings if cf["spin_run_id"] == delta_run["id"])
        self.assertEqual(delta_finding["delta_classification"], "resolved")

    def test_ordinary_chat_findings_never_mix_into_spin_sections(self):
        """Findings not produced by a Spin run must stay in the ordinary
        Findings panel, never appear grouped under a Spin run."""
        workspace = self.store.get(self.project_id)
        self.store.add_composer_finding(
            workspace, tag="Ordinary chat finding", source_reference="s", concern="c", unresolved_question="q",
        )
        response_json = (
            '{"findings": [{"tag": "Spin finding", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        resp = self._run_spin(SPIN_KIND_FIRST, response_json)
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.composer-findings"', body)
        self.assertIn("Ordinary chat finding", body)
        self.assertNotIn("Spin finding", body)  # Spin-produced findings never render inline in the Toolbox any more

        # The Toolbox (still rendered alongside Display on every page) may
        # legitimately still show "Ordinary chat finding" in its own
        # toolbox.composer-findings section - that co-presence is expected,
        # not a leak. What matters is that it's never grouped as a Spin
        # finding: display.spin.report.finding only ever wraps Spin-produced
        # findings.
        spin_tab_resp = self.client.get(f"/projects/{self.project_id}/workspace?view=spin")
        spin_tab_body = spin_tab_resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="display.spin.report.finding"', spin_tab_body)
        self.assertIn("Spin finding", spin_tab_body)

    def test_failed_spin_persists_honest_failure_record(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "" if k == "ANTHROPIC_API_KEY" else d):  # no API key configured
            MockClient.return_value.messages.create.return_value = _mock_response("{}")
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/spin/run",
                data={"spin_kind": "first_spin"}, follow_redirects=True,
            )
        self.assertEqual(resp.status_code, 200)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.spin_runs), 1)
        self.assertFalse(workspace.spin_runs[0]["ran"])
        self.assertEqual(workspace.composer_findings, [])

    def test_project_isolation_at_the_route_level(self):
        other_project_id = "test-project-delta-spin-route-other"
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
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertNotIn("Only in other project", body)


class NoOracleOrProjectSpecificLogicTests(unittest.TestCase):
    """Section: 'Do not hard-code North Bayview answers. North Bayview
    is the acceptance world, not the implementation logic.' Structural
    proof, not a style preference: the generation module's own source
    must contain no project-specific vocabulary and no reference to
    private fixture/oracle material of any kind."""

    def test_spin_module_names_no_specific_project_or_oracle_path(self):
        source = Path("services/spin.py").read_text(encoding="utf-8")
        lowered = source.lower()
        for forbidden in ("north bayview", "north-bayview", "oracle", "sallyport", "g2-data-room", "g2-oracle"):
            self.assertNotIn(forbidden, lowered, f"services/spin.py must not hard-code {forbidden!r}")

    def test_case_workspace_spin_additions_name_no_specific_project(self):
        source = Path("services/case_workspace.py").read_text(encoding="utf-8")
        lowered = source.lower()
        for forbidden in ("north bayview", "north-bayview", "oracle", "sallyport"):
            self.assertNotIn(forbidden, lowered, f"services/case_workspace.py must not reference {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
