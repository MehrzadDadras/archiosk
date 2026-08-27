"""
CLAUDE-UNIFIED-READ-EXPERIMENT-01 - can one thread be read out of the containers
that already exist?

The experiment the Product Owner authorized: build the unified READ over the
existing containers - no schema change, no writes moved - and find out whether a
merged thread reads as one conversation while Case privacy still holds.

The two things that would kill the idea, tested first:

  1. If the merge cannot preserve Case privacy, it is dead on arrival. A
     cross-user Case-title disclosure has already happened in this codebase
     once; a unified read is exactly the shape of change that could cause it
     again.
  2. If the merge has to write anything, it is no longer a read, and it becomes
     a second source of truth about what was said.

Everything else is a question of whether the result is actually better.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest

from services.case_workspace import CaseWorkspaceStore
from services.unified_conversation import (
    SCOPE_CASE, SCOPE_PROJECT, case_ids_present, continuity_report,
    read_unified_conversation, scopes_present,
)


class _Project(unittest.TestCase):
    """One project, one reviewer, work spread across the containers."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unified-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.dir)
        self.ws = self.store.get_or_create("proj-unified")

        # Interleaved on purpose: the reviewer moved between the project level
        # and two Investigations, which is what makes the containers a slicing
        # artifact rather than a separation of genuinely unrelated work.
        self.store.add_message(self.ws, None, role="human",
                               text="What is the smoke control strategy here?", actor="mel")
        # created_by is required, not decorative: every new Case is
        # unconditionally PRIVATE, so a Case with no recorded creator is
        # invisible to everyone including its author. The first run of this
        # experiment merged 2 turns instead of 5 for exactly that reason - the
        # read was correct and the fixture was wrong.
        self.glazing = self.store.create_case(self.ws, title="Glazing support",
                                              objective="o", created_by="mel")
        self.store.add_message(self.ws, self.glazing["id"], role="human",
                               text="Is a C channel appropriate?", actor="mel")
        self.store.add_message(self.ws, None, role="human",
                               text="Back to the overall programme", actor="mel")
        self.damper = self.store.create_case(self.ws, title="Damper D-14",
                                             objective="o", created_by="mel")
        self.store.add_message(self.ws, self.damper["id"], role="human",
                               text="Does D-14 close on alarm?", actor="mel")
        self.store.save(self.ws)


class ItReadsAsOneThread(_Project):
    def test_every_turn_appears_once(self):
        entries = read_unified_conversation(self.store, self.ws, "mel")
        texts = [e["text"] for e in entries]
        self.assertEqual(len(texts), len(set(texts)), "a turn was duplicated by the merge")
        # Four turns: two project-level, one in each Case.
        self.assertEqual(len(entries), 4)

    def test_it_is_in_the_order_it_happened(self):
        entries = read_unified_conversation(self.store, self.ws, "mel")
        stamps = [e["created_at"] for e in entries]
        self.assertEqual(stamps, sorted(stamps))

    def test_the_thread_genuinely_crosses_containers(self):
        # The measurement. If it never alternates, the containers were holding
        # separate work and merging them buys nothing.
        report = continuity_report(read_unified_conversation(self.store, self.ws, "mel"))
        self.assertEqual(report["turns"], 4)
        self.assertEqual(report["containers"], 3)
        self.assertGreater(report["container_crossings"], 0)
        self.assertTrue(report["reads_as_one_thread"])

    def test_each_turn_still_knows_where_it_belongs(self):
        # Unified for the reader, not flattened: scope survives the merge, so a
        # caller can still say "this was about Glazing support".
        entries = read_unified_conversation(self.store, self.ws, "mel")
        self.assertEqual(scopes_present(entries), {SCOPE_PROJECT, SCOPE_CASE})
        glazing = next(e for e in entries if "C channel" in e["text"])
        self.assertEqual(glazing["scope"], SCOPE_CASE)
        self.assertEqual(glazing["case_title"], "Glazing support")
        overall = next(e for e in entries if "overall programme" in e["text"])
        self.assertEqual(overall["scope"], SCOPE_PROJECT)
        self.assertIsNone(overall["case_id"])

    def test_limit_keeps_the_most_recent_turns_in_order(self):
        entries = read_unified_conversation(self.store, self.ws, "mel", limit=2)
        self.assertEqual(len(entries), 2)
        self.assertIn("D-14", entries[-1]["text"])


class PrivacyIsNotWeakenedByMerging(_Project):
    """The condition that would kill the idea outright."""

    def setUp(self):
        super().setUp()
        # A second reviewer's PRIVATE Case, with real content in it.
        self.secret = self.store.create_case(
            self.ws, title="Confidential claim strategy", objective="o", created_by="other")
        self.store.add_message(self.ws, self.secret["id"], role="human",
                               text="Our exposure on the delay claim", actor="other")
        self.store.save(self.ws)

    def test_another_reviewers_private_turns_are_absent(self):
        entries = read_unified_conversation(self.store, self.ws, "mel")
        blob = " ".join(e.get("text", "") for e in entries)
        self.assertNotIn("exposure on the delay claim", blob)

    def test_not_even_the_private_case_title_leaks(self):
        # The exact failure that happened live: the TITLE disclosed, not the
        # content. A merged read hands every turn a case_title, so this is the
        # sharper version of the same risk.
        entries = read_unified_conversation(self.store, self.ws, "mel")
        titles = {e.get("case_title") for e in entries}
        self.assertNotIn("Confidential claim strategy", titles)

    def test_the_owner_still_sees_their_own_private_case(self):
        entries = read_unified_conversation(self.store, self.ws, "other")
        blob = " ".join(e.get("text", "") for e in entries)
        self.assertIn("exposure on the delay claim", blob)

    def test_visibility_comes_from_the_governed_gate_not_a_local_filter(self):
        # Filtering workspace.cases directly is the shortcut that caused the
        # live disclosure. Proven by behaviour: if the gate is bypassed, the
        # private Case appears.
        from unittest.mock import patch

        with patch.object(CaseWorkspaceStore, "visible_cases_for",
                          return_value=[]) as gate:
            entries = read_unified_conversation(self.store, self.ws, "mel")
        gate.assert_called_once()
        self.assertEqual(case_ids_present(entries), set(),
                         "Case turns appeared without consulting visible_cases_for")


class ItIsAReadAndNothingElse(_Project):
    def test_it_writes_no_file(self):
        from pathlib import Path

        before = {p: p.stat().st_mtime_ns for p in Path(self.dir).rglob("*") if p.is_file()}
        read_unified_conversation(self.store, self.ws, "mel")
        after = {p: p.stat().st_mtime_ns for p in Path(self.dir).rglob("*") if p.is_file()}
        self.assertEqual(before, after, "the unified read modified stored state")

    def test_it_does_not_mutate_the_records_it_reads(self):
        entries = read_unified_conversation(self.store, self.ws, "mel")
        for entry in entries:
            entry["text"] = "TAMPERED"
        reread = read_unified_conversation(self.store, self.ws, "mel")
        self.assertNotIn("TAMPERED", [e["text"] for e in reread])

    def test_no_scope_field_was_added_to_stored_messages(self):
        # The whole point of a read-time merge: the stored record is untouched,
        # so nothing has to be migrated and nothing can drift.
        read_unified_conversation(self.store, self.ws, "mel")
        stored = self.store.get("proj-unified")
        for message in stored.project_conversation:
            self.assertNotIn("scope", message)

    def test_developer_conversation_is_not_merged_in(self):
        # Application-scope turns live in the session and must never enter a
        # project record. Keeping them physically apart is precisely why a scope
        # TAG was judged insufficient, so this read does not reach for them.
        import inspect

        from services import unified_conversation

        import ast

        # DOCSTRINGS removed as well as comments. This module's own docstring
        # explains that developer turns "live in the session" - prose satisfying
        # an assertion about the absence of the very thing it describes.
        tree = ast.parse(inspect.getsource(unified_conversation))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                if node.body and isinstance(node.body[0], ast.Expr) \
                        and isinstance(getattr(node.body[0], "value", None), ast.Constant) \
                        and isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
        code = ast.unparse(tree)
        for leak in ["session", "developer_home_messages", "developer_home_chats"]:
            self.assertNotIn(leak, code)


class ItSurvivesTheAwkwardCases(_Project):
    def test_a_project_with_no_conversation_at_all(self):
        empty = self.store.get_or_create("proj-empty")
        self.assertEqual(read_unified_conversation(self.store, empty, "mel"), [])

    def test_an_empty_case_contributes_nothing(self):
        self.store.create_case(self.ws, title="Opened, never used", objective="o",
                               created_by="mel")
        self.store.save(self.ws)
        entries = read_unified_conversation(self.store, self.ws, "mel")
        self.assertEqual(len(entries), 4)

    def test_identical_timestamps_do_not_reshuffle_between_calls(self):
        first = [e["id"] for e in read_unified_conversation(self.store, self.ws, "mel")]
        second = [e["id"] for e in read_unified_conversation(self.store, self.ws, "mel")]
        self.assertEqual(first, second)

    def test_a_single_container_reports_honestly(self):
        # One Case, no project-level talk: the merge should NOT claim to have
        # united anything.
        solo = self.store.get_or_create("proj-solo")
        case = self.store.create_case(solo, title="Only one", objective="o", created_by="mel")
        self.store.add_message(solo, case["id"], role="human", text="one", actor="mel")
        self.store.save(solo)
        report = continuity_report(read_unified_conversation(self.store, solo, "mel"))
        self.assertEqual(report["container_crossings"], 0)
        self.assertFalse(report["reads_as_one_thread"])


if __name__ == "__main__":
    unittest.main()
