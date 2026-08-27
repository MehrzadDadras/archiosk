"""
CLAUDE-ATTRIBUTION-01 - a human turn must say who said it.

HOW THIS WAS FOUND, INCLUDING THE PART I GOT WRONG

I reported to the Product Owner that 46% of human conversation turns in the dev
registry had no `actor`, and called it live attribution decay. That number was
real and the conclusion was wrong.

99 of the 100 unattributed turns were the string "compare the mechanical
drawings against the specification" - a fixture from
tests/test_mobile_continuation_01.py, written the same day. TestingConfig does
not override REGISTRY_STORE_PATH, so it inherits instance/registry and every
test run wrote real workspace files into the dev registry.

Excluding that pollution: 118 real human turns, 1 unattributed. 0.8%, not 46%.

WHAT WAS ACTUALLY BROKEN

The measurement was contaminated; the contract genuinely was not sound.
`add_message` accepted role="human" with actor=None, so an unattributable human
turn was constructible - and a test constructed a hundred of them without
anything objecting. Every production caller already passes _reviewer(), so this
closes a hole rather than changing behaviour.

Constitutional invariant #3 is the reason: "every claim traces to its source and
originator." A human turn with no originator cannot.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore

_ROOT = Path(__file__).resolve().parent.parent


class AHumanTurnMustRecordItsActor(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="attribution-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.dir)
        self.ws = self.store.get_or_create("proj-attr")
        self.case = self.store.create_case(
            self.ws, title="C", objective="o", created_by="mel")

    def test_a_human_turn_without_an_actor_is_refused(self):
        with self.assertRaises(CaseWorkspaceError) as caught:
            self.store.add_message(self.ws, self.case["id"], role="human", text="hello")
        self.assertIn("actor", str(caught.exception))

    def test_an_empty_or_whitespace_actor_is_refused(self):
        # "" and "   " are the shapes a careless caller actually produces.
        for bad in ["", "   ", None]:
            with self.subTest(actor=bad):
                with self.assertRaises(CaseWorkspaceError):
                    self.store.add_message(self.ws, self.case["id"], role="human",
                                           text="hello", actor=bad)

    def test_it_is_refused_at_project_level_too(self):
        # case_id=None takes a different branch inside add_message; the rule
        # must not live on only one of them.
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(self.ws, None, role="human", text="hello")

    def test_nothing_is_written_when_it_is_refused(self):
        before = len(self.store.get("proj-attr").project_conversation)
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(self.ws, None, role="human", text="hello")
        self.assertEqual(len(self.store.get("proj-attr").project_conversation), before)

    def test_an_attributed_human_turn_is_accepted(self):
        message = self.store.add_message(
            self.ws, self.case["id"], role="human", text="hello", actor="mel")
        self.assertEqual(message["actor"], "mel")

    def test_a_system_reply_may_still_omit_it(self):
        # Deliberate, and not an oversight: there is exactly one reply
        # generator, and naming it would be noise - ConversationMessage's own
        # docstring says so. The rule is about HUMAN provenance.
        message = self.store.add_message(
            self.ws, self.case["id"], role="system", text="reply")
        self.assertIsNone(message["actor"])


class TheRuleLivesAtTheOneWriteChokePoint(unittest.TestCase):
    """A rule every future caller must remember is not a rule.

    Same reasoning visible_cases_for records for Case privacy, after a real
    disclosure caused by filtering the raw list directly.
    """

    def test_the_check_is_inside_add_message(self):
        source = (_ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        body = source[source.index("    def add_message("):]
        body = body[:body.index("\n    def ", 10)]
        self.assertIn('role == "human"', body)
        self.assertIn("CaseWorkspaceError", body)

    def test_every_production_caller_already_attributes_human_turns(self):
        # The rule closes a contract hole; it does not change behaviour. If a
        # route ever writes a human turn without an actor, that is a real defect
        # and this catches it before the store does.
        offenders = []
        for path in [_ROOT / "routes", _ROOT / "services"]:
            for py in path.rglob("*.py"):
                src = py.read_text(encoding="utf-8")
                for call in re.finditer(r"add_message\((?:[^()]|\([^()]*\))*\)", src, re.S):
                    text = call.group(0)
                    if 'role="human"' in text and "actor=" not in text:
                        offenders.append(py.name)
        self.assertEqual(offenders, [])


class TestsMustNotWriteIntoTheDevRegistry(unittest.TestCase):
    """The contamination that produced the false 46% reading.

    Not a style point: it made a real measurement untrustworthy, and it was only
    caught because the polluting string was distinctive enough to notice.
    """

    def test_the_testing_config_isolates_the_registry(self):
        import config

        default = config.BaseConfig.REGISTRY_STORE_PATH
        testing = getattr(config.TestingConfig, "REGISTRY_STORE_PATH", default)
        self.assertNotEqual(
            testing, default,
            "TestingConfig inherits REGISTRY_STORE_PATH, so every test run "
            "writes workspace files into instance/registry - the dev data. "
            "That is how a fixture string came to be 46% of the 'real' "
            "conversation record.")


if __name__ == "__main__":
    unittest.main()
