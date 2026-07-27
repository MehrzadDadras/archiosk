"""
CLAUDE-P08 - the governed Investigation worklist: InvestigationStep as an
AnalysisRun sibling, recording what was investigated, what evidence was
examined, what conclusion/uncertainty resulted - never the model's raw
reasoning tokens (there are none to hide; the Anthropic messages API
doesn't expose them for an ordinary text completion).

The proving case is the real Cedar Harbour fuel-autonomy run: this test
file feeds a mocked model response containing the ACTUAL discoveries
that run produced (contractual vs. physical verification, missing
commissioning evidence, uncertainty about CR-17's measurable criterion,
the suspiciously close adjudication timestamps, the $0 adjustment
despite a 72->96-hour scope change) and asserts every one of them
round-trips faithfully through InvestigationStep storage and into the
rendered page - proving the structure, not just its shape.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from markupsafe import escape

from services.bhive_parser import ParsedDocument
from services.case_workspace import (
    INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry

# The real Cedar Harbour discoveries from the live run this test proves
# the storage/render layer can faithfully preserve.
_REAL_ASSESSMENT = (
    "The reviewer's concern appears to be about the conflicting adjudication "
    "history: a 'Not Satisfied' finding and a subsequent 'Satisfied' finding "
    "both exist for the same requirement, occurring within milliseconds of "
    "each other. Contractually, this appears resolved via CR-17, but it is "
    "not yet verified by physical delivery or commissioning evidence."
)
_REAL_SUPPORTING_POINTS = [
    "Addendum 04 revised the autonomy requirement from 72 to 96 hours (ADD-04-2).",
    "CR-17, incorporated into the Executed Project Agreement, records the "
    "Proponent's confirmation that fuel capacity will be increased to meet "
    "the 96-hour requirement at no Contract Price adjustment.",
    "The prior 'Not Satisfied' adjudication was preserved, not overwritten, "
    "providing a clear audit trail of the conflict and its stated resolution.",
]
_REAL_OPEN_QUESTIONS = [
    "Has the increased fuel storage capacity actually been installed and "
    "verified through commissioning or inspection? The resolution is a "
    "contractual commitment, not confirmed physical compliance.",
    "Does CR-17 specify a minimum fuel volume, tank size, or other measurable "
    "metric, or is it only a general commitment to meet the 96-hour requirement?",
    "The two adjudications are recorded within milliseconds of each other, "
    "which is procedurally unusual and could indicate the resolution was not "
    "independently reviewed before being recorded.",
    "Increasing fuel storage capacity from 72 to 96 hours is a material scope "
    "change; a $0 cost adjustment claim deserves verification.",
]


class InvestigationStepStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_investigation_step_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_record_and_retrieve_a_step(self):
        step = self.store.record_investigation_step(
            self.workspace,
            case_id="case-1",
            step_kind=INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
            anchor={"anchor_type": "requirement", "anchor_id": "req-1"},
            question="Why is this like this?",
            triggered_by_actor="owner1",
            evidence_requested=["adjudication history"],
            evidence_examined_ids={"adjudication_ids": ["a1", "a2"]},
            ran=True,
            assessment="Looks resolved.",
            confidence=0.8,
            supporting_points=["CR-17"],
            open_questions=["Verified?"],
            needs_human_judgment=True,
            analysis_id="analysis-1",
        )
        self.assertEqual(step["step_kind"], INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION)
        self.assertIsNotNone(step["id"])

        steps = self.store.investigation_steps_for_case(self.workspace, "case-1")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["id"], step["id"])

        found = self.store.investigation_step_for_analysis(self.workspace, "analysis-1")
        self.assertEqual(found["id"], step["id"])

    def test_no_step_found_for_an_unrelated_analysis_id(self):
        self.assertIsNone(self.store.investigation_step_for_analysis(self.workspace, "nonexistent"))

    def test_a_skipped_step_is_still_recorded(self):
        step = self.store.record_investigation_step(
            self.workspace,
            case_id="case-1",
            step_kind=INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
            anchor={"anchor_type": "requirement", "anchor_id": "req-1"},
            question="Check this",
            triggered_by_actor="owner1",
            ran=False,
            skipped_reason="No ANTHROPIC_API_KEY configured.",
        )
        self.assertFalse(step["ran"])
        self.assertIsNone(step["analysis_id"])
        self.assertEqual(step["skipped_reason"], "No ANTHROPIC_API_KEY configured.")


class InvestigationWorklistFaithfulPreservationTests(unittest.TestCase):
    """Full route stack, real Cedar Harbour discoveries, mocked model."""

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_investigation_worklist_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-investigation-worklist"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "reviewer"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _seed_requirement(self):
        self.client.get(f"/projects/{self.project_id}/workspace")
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        requirement = self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier="ADD-04-2",
            text_reference=(
                "Building shall support 96 hours of autonomous operation without "
                "normal utility power for critical operations."
            ),
            created_by="reviewer",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome="Not Satisfied", adjudicator="reviewer",
            reasoning="Addendum 04 revises autonomy to 96 hours, but the Technical Submission proposes only 72.",
        )
        self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome="Satisfied", adjudicator="reviewer",
            reasoning="CR-17 resolves the conflict.",
        )
        return requirement

    def test_real_discoveries_round_trip_faithfully_into_the_step_and_the_page(self):
        requirement = self._seed_requirement()

        fake_block = MagicMock()
        fake_block.type = "text"
        import json
        fake_block.text = json.dumps({
            "assessment": _REAL_ASSESSMENT,
            "confidence": 0.72,
            "supporting_points": _REAL_SUPPORTING_POINTS,
            "open_questions": _REAL_OPEN_QUESTIONS,
            "needs_human_judgment": True,
        })
        fake_response = MagicMock()
        fake_response.content = [fake_block]

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = fake_response

            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={
                    "text": "Something is wrong here",
                    "anchor_type": "requirement",
                    "anchor_id": requirement["id"],
                    "anchor_description": "ADD-04-2",
                },
            )
            workspace = self.store.get(self.project_id)
            system_message = workspace.project_conversation[1]
            message_id = system_message["action_taken"].split(":", 1)[1]
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation",
            )

        self.assertEqual(resp.status_code, 302)
        case_id = resp.headers["Location"].rsplit("case=", 1)[1]

        # -- the stored InvestigationStep itself --
        workspace = self.store.get(self.project_id)
        steps = self.store.investigation_steps_for_case(workspace, case_id)
        self.assertEqual(len(steps), 1)
        step = steps[0]

        self.assertTrue(step["ran"])
        self.assertEqual(step["question"], "Something is wrong here")
        self.assertEqual(step["anchor"]["anchor_id"], requirement["id"])
        self.assertEqual(step["evidence_examined_ids"]["adjudication_ids"], [
            a["id"] for a in self.store.requirement_adjudications_for(workspace, requirement["id"])
        ])
        self.assertEqual(step["assessment"], _REAL_ASSESSMENT)
        self.assertAlmostEqual(step["confidence"], 0.72)
        self.assertEqual(step["supporting_points"], _REAL_SUPPORTING_POINTS)
        self.assertEqual(step["open_questions"], _REAL_OPEN_QUESTIONS)
        self.assertTrue(step["needs_human_judgment"])
        self.assertIsNotNone(step["analysis_id"])

        analysis = next(a for a in workspace.analyses if a["id"] == step["analysis_id"])
        self.assertEqual(analysis["engine_name"], "anthropic-requirement-investigation")

        # -- what actually renders on the Case Workspace page --
        page = self.client.get(f"/projects/{self.project_id}/workspace?case={case_id}")
        body = page.get_data(as_text=True)

        self.assertIn("How this was investigated", body)
        self.assertIn("Something is wrong here", body)
        # Every real discovery must survive the round trip - compared
        # against Jinja's own HTML-escaped rendering (str(escape(...))),
        # not the raw text, since e.g. "Proponent's" legitimately becomes
        # "Proponent&#39;s" in the page - that's correct escaping, not
        # data loss.
        for point in _REAL_SUPPORTING_POINTS:
            self.assertIn(str(escape(point)), body)
        for question in _REAL_OPEN_QUESTIONS:
            self.assertIn(str(escape(question)), body)
        self.assertIn("72%", body)
        self.assertIn("needs your judgment", body)
        # Evidence-examined counts, not raw model reasoning.
        self.assertIn("2 adjudication(s)", body)

    def test_no_investigation_step_subdisclosure_for_an_ordinary_mock_finding(self):
        """A drawing-analysis Finding (no real investigation behind it)
        must not show an empty/fabricated worklist entry."""
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Case A", "objective": "x"},
        )
        workspace = self.store.get(self.project_id)
        case = workspace.cases[0]

        from services.case_workspace import ANALYSIS_TRIGGER_USER_INITIATED, AnalysisTrigger
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="reviewer")
        source_id = workspace.sources[0]["id"] if workspace.sources else None
        if source_id:
            self.store.record_analysis(
                workspace, case_id=case["id"], source_ids=[source_id], objective="mock analysis",
                engine_name="mock-drawing-engine", engine_version="1.0",
                findings=[{"statement": "A mock finding.", "machine_confidence": 0.5, "source_id": source_id}],
                trigger=trigger,
            )
            page = self.client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
            body = page.get_data(as_text=True)
            self.assertIn("A mock finding.", body)
            self.assertNotIn("How this was investigated", body)


if __name__ == "__main__":
    unittest.main()
