"""CLAUDE-PROJECT-CHANGE-LANE-01 - a change question cannot become an evidence dump.

Asked live on 2026-09-22 in a real project: "what is new in this project if
anything has changed during this week". The reply was every evidence item in
the project, each qualified SOURCE_REFERENCE - not established as a project
fact, followed by screens of source text. The project's ledger held 82
governance events, none within seven days, and 17 sources, none added. The
honest answer was one sentence and the data for it was already stored.

THE REGRESSION THIS FILE EXISTS FOR is the last class in TheDumpCannotComeBack:
a weekly-change question, asked of a workspace that HAS evidence items, must
not produce a SOURCE_REFERENCE dump when the activity ledger already answers
it. That is the exact shape that shipped, so it is asserted directly rather
than implied by the happier tests above it.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services import project_change
from services.case_workspace import CaseWorkspaceStore


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class _Event:
    """The two attributes this projection reads off a GovernanceEvent."""

    def __init__(self, created_at, event_type="thing_happened"):
        self.created_at = created_at
        self.event_type = event_type


class TheWindowIsRecognisedOrRefused(unittest.TestCase):
    def test_the_live_question_resolves_to_a_week(self):
        self.assertEqual(
            project_change.window_for(
                "what is new in this project if anything has changed during this week"),
            project_change.WINDOW_WEEK)

    def test_today_and_month_are_recognised(self):
        self.assertEqual(project_change.window_for("any updates today"),
                         project_change.WINDOW_TODAY)
        self.assertEqual(project_change.window_for("has anything changed this month"),
                         project_change.WINDOW_MONTH)

    def test_a_vague_word_is_not_a_window(self):
        """"Recently" has no boundary, and inventing one would report a
        made-up period as fact."""
        self.assertIsNone(project_change.window_for("anything new recently?"))
        self.assertIsNone(project_change.window_for("what does the spec say"))

    def test_an_unknown_window_is_refused_rather_than_guessed(self):
        with self.assertRaises(ValueError):
            project_change.changes_since(_Workspace(), "fortnight")


class _Workspace:
    """A workspace shaped like the real one, for the projection's reads."""

    def __init__(self, sources=(), cases=(), findings=(), analyses=()):
        self.project_id = "proj-change"
        self.sources = list(sources)
        self.cases = list(cases)
        self.findings = list(findings)
        self.analyses = list(analyses)
        self.evidence_items = []


class AnEmptyWindowIsAnAnswer(unittest.TestCase):
    """The live case: a project with history, none of it this week."""

    def setUp(self):
        self.workspace = _Workspace(
            sources=[{"name": "Spec.pdf", "added_at": _iso(15)},
                     {"name": "Drawings.pdf", "added_at": _iso(40)}],
            cases=[{"created_at": _iso(20)}])
        self.events = [_Event(_iso(15)), _Event(_iso(30)), _Event(_iso(60))]

    def _change(self):
        return project_change.changes_since(
            self.workspace, project_change.WINDOW_WEEK, governance_events=self.events)

    def test_nothing_in_the_window_is_reported_as_no_change(self):
        change = self._change()
        self.assertFalse(change["changed"])
        self.assertEqual(change["total"], 0)
        self.assertEqual(change["counts"]["governance_events"], 0)
        self.assertEqual(change["counts"]["sources_added"], 0)

    def test_the_summary_says_so_in_one_sentence_result_first(self):
        summary = project_change.summarise(self._change())
        self.assertTrue(summary.startswith("No confirmed project changes were recorded this week."))
        self.assertIn("no governance events occurred", summary.lower())
        self.assertIn("no new sources were added", summary.lower())

    def test_it_still_says_when_the_project_was_last_touched(self):
        """An empty window should not leave the reader wondering."""
        summary = project_change.summarise(self._change())
        self.assertIn("most recent recorded activity", summary)

    def test_the_summary_contains_no_evidence_vocabulary(self):
        summary = project_change.summarise(self._change())
        for banned in ("SOURCE_REFERENCE", "not established as a project fact",
                       "Source says", "Evidence admission"):
            self.assertNotIn(banned, summary)


class RealChangesAreCounted(unittest.TestCase):
    def test_activity_inside_the_window_is_summarised_result_first(self):
        workspace = _Workspace(
            sources=[{"name": "Addendum 3.pdf", "added_at": _iso(2)}],
            cases=[{"created_at": _iso(1)}],
            findings=[{"created_at": _iso(3)}])
        change = project_change.changes_since(
            workspace, project_change.WINDOW_WEEK,
            governance_events=[_Event(_iso(1), "source_added"), _Event(_iso(400))])

        self.assertTrue(change["changed"])
        self.assertEqual(change["counts"]["sources_added"], 1)
        self.assertEqual(change["counts"]["governance_events"], 1)

        summary = project_change.summarise(change)
        self.assertTrue(summary.startswith("4 changes recorded this week:"))
        self.assertIn("Addendum 3.pdf", summary)

    def test_a_malformed_timestamp_is_ignored_not_counted(self):
        workspace = _Workspace(sources=[{"name": "Broken.pdf", "added_at": "not-a-date"}])
        change = project_change.changes_since(
            workspace, project_change.WINDOW_WEEK, governance_events=[])
        self.assertEqual(change["counts"]["sources_added"], 0)


class TheDumpCannotComeBack(unittest.TestCase):
    """The regression, against the real interpreter and a real store."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="change_lane_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-change")
        source = self.store.add_source(
            self.workspace, name="Old_Spec.pdf", file_path="/tmp/Old_Spec.pdf",
            kind="project_document")
        # Evidence EXISTS - this is what used to be dumped. Aged well outside
        # the window, exactly like the live project.
        for index in range(7):
            self.store.register_evidence_item(
                self.workspace, source_id=source["id"],
                evidence_class="extracted_evidence",
                content=f"Clause {index}: the contractor shall coordinate the works.",
                content_type="text", actor="tester")
        for record in self.workspace.sources:
            record["added_at"] = _iso(15)
        self.store.save(self.workspace)

    def test_a_weekly_change_question_is_answered_from_the_ledger(self):
        from services.conversation_interpreter import interpret_message

        result = interpret_message(
            "what is new in this project if anything has changed during this week",
            self.workspace, None, self.store, self.tmp, "reviewer", None)

        self.assertEqual(result.action_taken, "project_change_summary")
        self.assertTrue(result.reply_text.startswith(
            "No confirmed project changes were recorded this week."))

    def test_the_evidence_lane_is_never_entered_for_a_change_question(self):
        """The defect, stated as the property that must never hold again.

        ASSERTED BY SPY, NOT BY READING THE REPLY, and the distinction matters.
        A first version of this test checked that the answer contained no
        SOURCE_REFERENCE text - and it passed with the fix REVERTED, because a
        hermetic test has no model, so the un-fixed path degrades to
        'project_qa_unavailable' instead of producing the dump. It would have
        proved nothing about the defect it is named for.

        The dump is built by gather_project_evidence, which admits every
        evidence item in the project. So the real property is that a change
        question never reaches it. That fails honestly when the lane is removed.
        """
        from unittest.mock import patch

        import services.conversation_interpreter as interpreter

        self.assertEqual(len(self.workspace.evidence_items), 7)

        with patch.object(interpreter, "gather_project_evidence") as gather:
            reply = interpreter.interpret_message(
                "what is new in this project if anything has changed during this week",
                self.workspace, None, self.store, self.tmp, "reviewer", None).reply_text

        gather.assert_not_called()
        for banned in ("SOURCE_REFERENCE", "not established as a project fact",
                       "Evidence admission", "Source says (reference only)",
                       "the contractor shall coordinate"):
            self.assertNotIn(banned, reply,
                             "a project-activity question devolved into evidence retrieval")

    def test_a_document_question_does_still_enter_the_evidence_lane(self):
        """The other half: proof the spy above can actually observe a call."""
        from unittest.mock import patch

        import services.conversation_interpreter as interpreter

        with patch.object(interpreter, "gather_project_evidence") as gather:
            interpreter.interpret_message(
                "what does the specification say about concrete cover",
                self.workspace, None, self.store, self.tmp, "reviewer", None)

        gather.assert_called()

    def test_the_answer_is_short_because_the_ledger_answer_is_short(self):
        from services.conversation_interpreter import interpret_message

        reply = interpret_message(
            "what is new in this project if anything has changed during this week",
            self.workspace, None, self.store, self.tmp, "reviewer", None).reply_text
        self.assertLess(len(reply), 400, "a one-sentence answer grew into a report")

    def test_a_document_question_still_takes_the_ordinary_path(self):
        """The lane must be narrow: this must NOT be captured."""
        from services.conversation_interpreter import interpret_message

        result = interpret_message(
            "what does the specification say about concrete cover",
            self.workspace, None, self.store, self.tmp, "reviewer", None)
        self.assertNotEqual(result.action_taken, "project_change_summary")

    def test_nothing_was_written_by_answering(self):
        """A read-only projection must leave the workspace untouched."""
        from services.conversation_interpreter import interpret_message

        path = self.store._path_for(self.workspace.project_id)
        before = path.read_bytes()
        interpret_message(
            "has anything changed this week",
            self.workspace, None, self.store, self.tmp, "reviewer", None)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
