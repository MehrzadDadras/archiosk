"""
CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION, Section A - "Compress missing-
evidence notices."

Live Product Owner report: a River Action Stack answer's opening
caveat ("Not covered by this project's extracted evidence: <full
sentence>") was long enough to dominate the primary scan path, even
though the SAME detail already lives inside whichever ranked action's
own "uncertainty" field it belongs to. The fix adds an OPTIONAL,
model-provided `missing_evidence_summary` field (short, noun-phrase
style) used ONLY when a River Action Stack is present; ordinary
Q&A keeps the full sentence unchanged, and a River Action Stack answer
that didn't get a compact summary from the model still falls back to
the full sentence rather than silently dropping the caveat - "do not
suppress material uncertainty" is a safety property, not a cosmetic
default.

Run via:

    python -m unittest tests.test_ca1d_river_po02_evidence_compaction -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.project_qa import ProjectQAResult
from services.requirements_registry import RequirementsRegistry


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class MissingEvidenceSummaryParsingTests(unittest.TestCase):
    """Unit-level: services.project_qa.answer_project_question's own
    parsing of the new field, independent of the conversation layer."""

    def _run(self, payload: dict) -> ProjectQAResult:
        from services import project_qa

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(json.dumps(payload))
            return project_qa.answer_project_question(
                question="What should I do next?", document_filename="rfp.docx",
                candidate_requirements=[], governed_requirements=[], milestones=[],
            )

    def test_summary_is_parsed_when_present(self):
        result = self._run({
            "answer": "Do these.", "grounded_in": [], "needs_clarification": False,
            "not_covered": "The revised deadline date is not stated in the extracted text.",
            "missing_evidence_summary": "current extended submission deadline",
            "river_actions": [{"rank": 1, "action": "Confirm deadline"}],
        })
        self.assertEqual(result.missing_evidence_summary, "current extended submission deadline")
        self.assertEqual(result.not_covered, "The revised deadline date is not stated in the extracted text.")

    def test_empty_summary_string_parses_as_none(self):
        result = self._run({
            "answer": "Do these.", "grounded_in": [], "needs_clarification": False,
            "not_covered": "", "missing_evidence_summary": "",
            "river_actions": [{"rank": 1, "action": "Confirm deadline"}],
        })
        self.assertIsNone(result.missing_evidence_summary)

    def test_field_absent_entirely_parses_as_none(self):
        result = self._run({
            "answer": "A plain answer.", "grounded_in": ["Section 1"],
            "not_covered": "", "needs_clarification": False,
        })
        self.assertIsNone(result.missing_evidence_summary)


class ReplyTextCompactionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_river_po02_evidence_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-river-po02-evidence"

        with self.flask_app.app_context():
            db.session.add(User(username="pm_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="Proposal Submission Deadline is August 28.", category="schedule_milestone", confidence=0.6, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "pm_owner"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.set_project_owner(self.store.get(self.project_id), owner="pm_owner", actor="pm_owner")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ask(self, payload: dict, question: str = "What do you think I need to do next?"):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(json.dumps(payload))
            self.client.post(f"/projects/{self.project_id}/workspace/quick-start", data={"text": question})
        workspace = self.store.get(self.project_id)
        return workspace.project_conversation[-1]["text"]

    def test_river_action_stack_uses_the_compact_line_when_summary_provided(self):
        text = self._ask({
            "answer": "Prioritize the actions below.",
            "grounded_in": [], "needs_clarification": False,
            "not_covered": (
                "The revised Proposal Submission Deadline is not stated in the "
                "extracted text, and the full RFP Data Sheet has not been extracted."
            ),
            "missing_evidence_summary": "current extended submission deadline and full RFP Data Sheet",
            "river_actions": [{"rank": 1, "action": "Confirm the deadline"}],
        })
        self.assertIn("Missing evidence: current extended submission deadline and full RFP Data Sheet.", text)
        self.assertNotIn("Not covered by this project's extracted evidence:", text)

    def test_river_action_stack_falls_back_to_full_sentence_when_no_summary_given(self):
        # "Do not suppress material uncertainty" - a River Action Stack
        # answer that never got a compact summary from the model must
        # still surface the full caveat, not silently drop it.
        text = self._ask({
            "answer": "Prioritize the actions below.",
            "grounded_in": [], "needs_clarification": False,
            "not_covered": "The revised deadline date is not stated anywhere in the extracted evidence.",
            "river_actions": [{"rank": 1, "action": "Confirm the deadline"}],
        })
        self.assertIn(
            "Not covered by this project's extracted evidence: "
            "The revised deadline date is not stated anywhere in the extracted evidence.",
            text,
        )

    def test_ordinary_question_keeps_the_full_sentence_even_if_summary_present(self):
        # Compaction is explicitly scoped to River Action Stack answers
        # only (Section A: "For River Action Stack answers...") -
        # an ordinary factual question must be completely unaffected,
        # even in the hypothetical case a summary was supplied.
        text = self._ask({
            "answer": "The document does not name a specific vendor.",
            "grounded_in": [], "needs_clarification": False,
            "not_covered": "The vendor's name is not present anywhere in the extracted evidence.",
            "missing_evidence_summary": "vendor name",
        }, question="Who is the vendor?")
        self.assertIn(
            "Not covered by this project's extracted evidence: "
            "The vendor's name is not present anywhere in the extracted evidence.",
            text,
        )
        self.assertNotIn("Missing evidence:", text)

    def test_fully_covered_river_action_stack_answer_has_no_evidence_line_at_all(self):
        text = self._ask({
            "answer": "Prioritize the actions below.",
            "grounded_in": ["Section 3.1"], "needs_clarification": False,
            "not_covered": "", "missing_evidence_summary": "",
            "river_actions": [{"rank": 1, "action": "Confirm the deadline"}],
        })
        self.assertNotIn("Missing evidence:", text)
        self.assertNotIn("Not covered by this project's extracted evidence:", text)


if __name__ == "__main__":
    unittest.main()
