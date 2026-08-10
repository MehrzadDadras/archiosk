"""
CLAUDE-CA1D-RIVER-PO-01 - Product Owner Sign-Off + Reusable River Action
Stack.

A live Product Owner review found a genuinely useful "what should I do
next" answer rendered as one dense explanatory paragraph - the wrong
information hierarchy for a question asking what deserves attention now.

This establishes River Action Stack as a reusable presentation contract
(Rank -> Action -> Expand -> Understand Why -> Inspect Evidence), fed by
a new OPTIONAL, semantically-gated `river_actions` field in
services/project_qa.py's own existing JSON schema - never a second
rendering subsystem, never RFP-specific. Reuses the existing
`subdisclosure` (<details>/<summary>) primitive for each item's own
independent expand/collapse.

Run via:

    python -m unittest tests.test_ca1d_river_po01_action_stack -v
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
from services.project_qa import _parse_river_actions
from services.requirements_registry import RequirementsRegistry


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class RiverActionParsingTests(unittest.TestCase):
    """Unit-level: the defensive backstop independent of prompt wording."""

    def test_items_are_sorted_by_rank_not_array_order(self):
        # CLAUDE-CA1D-RIVER-PO-01 (Section 7/G): "no prose-order
        # criticality" - array position must never stand in for rank.
        raw = [
            {"rank": 2, "action": "Second"},
            {"rank": 1, "action": "First"},
        ]
        parsed = _parse_river_actions(raw)
        self.assertEqual([a["action"] for a in parsed], ["First", "Second"])

    def test_malformed_items_are_dropped_not_rendered_blank(self):
        raw = [
            {"rank": 1, "action": "Real one"},
            {"rank": 2, "action": ""},  # empty heading - must be dropped
            {"rank": 3},  # no action key at all - must be dropped
            "not even a dict",
        ]
        parsed = _parse_river_actions(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["action"], "Real one")

    def test_hard_capped_regardless_of_model_output(self):
        raw = [{"rank": i, "action": f"Action {i}"} for i in range(1, 20)]
        parsed = _parse_river_actions(raw)
        self.assertLessEqual(len(parsed), 8)

    def test_non_list_input_yields_empty(self):
        self.assertEqual(_parse_river_actions(None), [])
        self.assertEqual(_parse_river_actions("not a list"), [])
        self.assertEqual(_parse_river_actions({}), [])

    def test_missing_rank_falls_back_to_insertion_position(self):
        raw = [{"action": "Only one"}]
        parsed = _parse_river_actions(raw)
        self.assertEqual(parsed[0]["rank"], 1)


class RiverActionStackRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_river_po01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-river-po01"

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

    def _ask(self, question, river_actions=None, grounded_in=None):
        payload = {
            "answer": "Here are the most consequential next moves." if river_actions else "A plain factual answer.",
            "grounded_in": grounded_in or [],
            "not_covered": "",
            "needs_clarification": False,
        }
        if river_actions is not None:
            payload["river_actions"] = river_actions
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(json.dumps(payload))
            return self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": question},
            )

    _THREE_ACTIONS = [
        {"rank": 1, "action": "Confirm the Proposal Submission Deadline", "rationale": "The date was extended.", "consequence": "Missing it ends eligibility.", "uncertainty": "Replacement date not in evidence.", "evidence": ["Revision note (Version 2.2)"]},
        {"rank": 2, "action": "Confirm the Proponent Representative", "rationale": "Required for formal correspondence.", "consequence": "Blocks communication with the Sponsors.", "uncertainty": "", "evidence": ["Section 3.1"]},
        {"rank": 3, "action": "Check the Mandatory Submission Requirements", "rationale": "Determines proposal completeness.", "consequence": "Incomplete submissions may be disqualified.", "uncertainty": "", "evidence": ["Schedule 3"]},
    ]

    def test_a_collapsed_default_shows_headings_not_explanatory_detail(self):
        """Section 15.A - the collapsed default must expose concise
        headings, not the rationale/consequence prose, on first render."""
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("1. Confirm the Proposal Submission Deadline", body)
        self.assertIn("2. Confirm the Proponent Representative", body)
        self.assertIn("3. Check the Mandatory Submission Requirements", body)
        # The detail text is present in the markup (progressive disclosure
        # is a CSS/native-<details> concern, not server-side omission -
        # see test_c below) but each item's own <details> must not carry
        # the `open` attribute, so it renders collapsed by default.
        idx = body.index("1. Confirm the Proposal Submission Deadline")
        tag_start = body.rindex("<details", 0, idx)
        tag = body[tag_start:body.index(">", tag_start)]
        self.assertNotIn("open", tag)

    def test_b_independent_disclosure_each_item_is_its_own_details_element(self):
        """Section 15.B - opening one action must not be coupled to any
        other - proven structurally: three independent <details>, not one
        shared container toggling all three."""
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        start = body.index('data-ui-ref="chat.river-action-stack"')
        end = body.index("</ol>", start)
        stack_html = body[start:end]
        self.assertEqual(stack_html.count("<details"), 3)

    def test_c_explanation_remains_accessible_in_the_markup(self):
        """Section 15.C - rationale/consequence/uncertainty are real,
        present, reachable content - not discarded server-side."""
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("The date was extended.", body)
        self.assertIn("Missing it ends eligibility.", body)
        self.assertIn("Replacement date not in evidence.", body)

    def test_d_evidence_preserved_and_attached_to_the_correct_action(self):
        """Section 15.D - each action's own evidence must appear inside
        THAT action's own disclosure, not merged into one flat list."""
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        idx1 = body.index("1. Confirm the Proposal Submission Deadline")
        idx2 = body.index("2. Confirm the Proponent Representative")
        segment_one = body[idx1:idx2]
        self.assertIn("Revision note (Version 2.2)", segment_one)
        self.assertNotIn("Section 3.1", segment_one)

    def test_e_variable_count_one_action(self):
        """Section 15.E - works with a single genuinely important item,
        not padded to a fixed count."""
        self._ask("What do you think I need to do next?", river_actions=[self._THREE_ACTIONS[0]])
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        start = body.index('data-ui-ref="chat.river-action-stack"')
        end = body.index("</ol>", start)
        self.assertEqual(body[start:end].count("<details"), 1)

    def test_e_variable_count_five_actions(self):
        five = self._THREE_ACTIONS + [
            {"rank": 4, "action": "Fourth", "rationale": "", "consequence": "", "uncertainty": "", "evidence": []},
            {"rank": 5, "action": "Fifth", "rationale": "", "consequence": "", "uncertainty": "", "evidence": []},
        ]
        self._ask("What do you think I need to do next?", river_actions=five)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        start = body.index('data-ui-ref="chat.river-action-stack"')
        end = body.index("</ol>", start)
        self.assertEqual(body[start:end].count("<details"), 5)

    def test_f_ordinary_answer_is_not_converted_into_a_river_action_stack(self):
        """Section 15.F - semantic restraint: river_actions absent/empty
        for an ordinary factual question must render nothing extra."""
        self._ask("What is the name of the RFP?", river_actions=[], grounded_in=["Cover page"])
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="chat.river-action-stack"', body)
        # And the ordinary Source-grounding disclosure still works exactly
        # as before, unaffected by this feature's own existence.
        self.assertIn("Source grounding", body)

    def test_g_rank_order_wins_over_json_array_order(self):
        """Section 15.G - an item appearing first in the model's own JSON
        array is not necessarily rendered first merely because of that
        position - only "rank" governs display order."""
        out_of_order = [
            {"rank": 3, "action": "Appears first in JSON, ranked last", "rationale": "", "consequence": "", "uncertainty": "", "evidence": []},
            {"rank": 1, "action": "Appears last in JSON, ranked first", "rationale": "", "consequence": "", "uncertainty": "", "evidence": []},
        ]
        self._ask("What do you think I need to do next?", river_actions=out_of_order)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        idx_first = body.index("Appears last in JSON, ranked first")
        idx_last = body.index("Appears first in JSON, ranked last")
        self.assertLess(idx_first, idx_last)

    def test_h_disclosure_controls_are_accessible(self):
        """Section 15.H - native <details>/<summary> carries correct
        accessible semantics for free; confirm the real markup uses it,
        not a div-based custom widget with no accessible state."""
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        idx = body.index("1. Confirm the Proposal Submission Deadline")
        summary_start = body.rindex("<summary", 0, idx)
        self.assertIn("<summary>1. Confirm the Proposal Submission Deadline</summary>", body[summary_start:summary_start + 200])

    def test_i_project_isolation_no_cross_project_leakage(self):
        """Section 15.I - a second project's own river_actions must never
        appear on the first project's page."""
        other_project_id = "test-project-river-po01-other"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=other_project_id, filename="other.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[],
        ))
        self.client.get(f"/projects/{other_project_id}/workspace")
        other_store = CaseWorkspaceStore(self.tmp_dir)
        other_store.set_project_owner(other_store.get(other_project_id), owner="pm_owner", actor="pm_owner")

        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)

        other_body = self.client.get(f"/projects/{other_project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="chat.river-action-stack"', other_body)
        self.assertNotIn("Confirm the Proposal Submission Deadline", other_body)

    def test_river_actions_persist_across_a_fresh_store_read(self):
        self._ask("What do you think I need to do next?", river_actions=self._THREE_ACTIONS)
        fresh_store = CaseWorkspaceStore(self.tmp_dir)
        reloaded = fresh_store.get(self.project_id)
        last = reloaded.project_conversation[-1]
        self.assertEqual(len(last["river_actions"]), 3)
        self.assertEqual(last["river_actions"][0]["action"], "Confirm the Proposal Submission Deadline")

    def test_greeting_never_produces_a_river_action_stack(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Thanks."},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        last = workspace.project_conversation[-1]
        self.assertEqual(last.get("river_actions", []), [])


if __name__ == "__main__":
    unittest.main()
