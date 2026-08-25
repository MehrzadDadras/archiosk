"""
CLAUDE-COMPOSER-DRAFT-ASSIST-01 - the pen beside the Composer.

Product Owner: "I want to write naturally first, then let GO help sharpen the
language without changing my meaning or taking control away from me... Do not
silently overwrite the user's draft."

TWO THINGS THIS FILE IS REALLY ABOUT

1. THE DRAFT IS NEVER OVERWRITTEN. Asserted structurally rather than by
   inspection: exactly two lines in draft_assist.js write to the textarea, both
   inside click handlers on buttons the reviewer pressed, and the route has no
   write path to a draft at all because it only reads a string and returns one.

2. NOTHING MAY BE ADDED TO THE TEXT. The real hazard in professional
   construction language is not clumsy rewriting - it is a model quietly
   inserting a dimension, a date, a drawing number or a commitment into text the
   reviewer then issues as an RFI. That instruction must be present, must be
   absolute, and must come FIRST in the prompt rather than as a trailing
   politeness, so it is what the model weighs the action instruction against.

Hermetic: the model call is spied. No test here reaches a network.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVICE = _REPO_ROOT / "services" / "draft_assist.py"
_JS = _REPO_ROOT / "static" / "js" / "draft_assist.js"
_MACROS = _REPO_ROOT / "templates" / "_macros.html"
_ROUTES = _REPO_ROOT / "routes" / "workspace.py"
_CSS = _REPO_ROOT / "static" / "css" / "main.css"


def _strip_js_comments(source: str) -> str:
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", source)


class TheDraftIsNeverOverwrittenTests(unittest.TestCase):
    def setUp(self):
        self.js = _strip_js_comments(_JS.read_text(encoding="utf-8"))

    def test_exactly_two_lines_write_to_the_draft(self):
        # If this count ever rises, someone has added a path that can change the
        # reviewer's text - which is the one thing this feature must not do.
        writes = re.findall(r"box\.value\s*=", self.js)
        self.assertEqual(len(writes), 2, "unexpected number of writes to the draft")

    def test_both_writes_sit_inside_a_click_handler(self):
        for match in re.finditer(r"box\.value\s*=", self.js):
            preceding = self.js[:match.start()]
            handler = preceding.rfind("addEventListener('click'")
            self.assertGreater(handler, 0, "a draft write outside a click handler")

    def test_the_proposal_renders_into_its_own_element_first(self):
        self.assertIn("proposalEl.textContent = data.proposal", self.js)

    def test_the_original_is_captured_for_comparison(self):
        # Captured at the moment of asking, so the comparison stays honest even
        # if the reviewer keeps typing while it works.
        self.assertIn("originalEl.textContent = draft", self.js)

    def test_insert_appends_below_and_keeps_the_original_verbatim(self):
        insert = self.js[self.js.index("insertBtn.addEventListener"):]
        insert = insert[:insert.index("});")]
        self.assertIn("box.value.replace", insert)
        self.assertIn("current.proposal", insert)

    def test_discarding_touches_nothing(self):
        discard = self.js[self.js.index("discardBtn.addEventListener"):]
        discard = discard[:discard.index("});")]
        self.assertNotIn("box.value", discard)

    def test_an_accepted_change_is_persisted_to_the_draft_store(self):
        # Without dispatching input, an accepted revision would not survive a
        # navigation - a quiet way to lose work the reviewer just approved.
        self.assertIn("box.dispatchEvent(new Event('input'", self.js)


class NothingMayBeAddedToTheTextTests(unittest.TestCase):
    def setUp(self):
        self.source = _SERVICE.read_text(encoding="utf-8")

    def test_the_no_invention_rule_is_absolute_and_first(self):
        from services.draft_assist import _SYSTEM_PROMPT

        self.assertIn("ABSOLUTE RULE", _SYSTEM_PROMPT)
        self.assertIn("overrides every other instruction", _SYSTEM_PROMPT)
        # It must precede the response-shape instruction: the model should weigh
        # the action against this, not discover it after being told what to emit.
        self.assertLess(_SYSTEM_PROMPT.index("ABSOLUTE RULE"),
                        _SYSTEM_PROMPT.index("Respond ONLY"))

    def test_the_specific_hazards_are_named(self):
        from services.draft_assist import _SYSTEM_PROMPT

        for hazard in ("dimension", "date", "drawing number", "specification section",
                       "code clause", "obligation", "admission", "recommendation"):
            self.assertIn(hazard, _SYSTEM_PROMPT, hazard)

    def test_certainty_is_preserved_in_both_directions(self):
        from services.draft_assist import _SYSTEM_PROMPT

        self.assertIn("do not turn a tentative observation into a firm conclusion",
                      _SYSTEM_PROMPT.lower())
        self.assertIn("do not soften a firm statement", _SYSTEM_PROMPT.lower())

    def test_recast_actions_forbid_inventing_references(self):
        from services.draft_assist import DRAFT_ACTIONS

        by_key = {a.key: a for a in DRAFT_ACTIONS}
        self.assertIn("Never invent", by_key["rfi"].instruction)
        self.assertIn("Never invent", by_key["meeting_note"].instruction)
        # A site observation must not acquire a cause or a fault it did not have.
        self.assertIn("No cause, no fault", by_key["observation"].instruction)

    def test_make_longer_will_not_pad_with_invention(self):
        from services.draft_assist import DRAFT_ACTIONS

        longer = next(a for a in DRAFT_ACTIONS if a.key == "longer")
        self.assertIn("Do not add new content to reach length", longer.instruction)


class CheckAmbiguityReportsRatherThanRewritesTests(unittest.TestCase):
    def test_it_is_marked_as_not_rewriting(self):
        from services.draft_assist import DRAFT_ACTIONS

        ambiguity = next(a for a in DRAFT_ACTIONS if a.key == "ambiguity")
        self.assertFalse(ambiguity.rewrites)
        self.assertIn("Do NOT rewrite", ambiguity.instruction)

    def test_every_other_action_does_rewrite(self):
        from services.draft_assist import DRAFT_ACTIONS

        for action in DRAFT_ACTIONS:
            if action.key != "ambiguity":
                self.assertTrue(action.rewrites, action.key)

    def test_replace_is_hidden_for_a_reporting_action(self):
        js = _strip_js_comments(_JS.read_text(encoding="utf-8"))
        self.assertIn("replaceBtn.hidden = !data.rewrites", js)

    def test_replace_refuses_even_if_the_button_were_reachable(self):
        # Belt and braces: hiding a control is presentation, so the handler
        # checks the flag too.
        js = _strip_js_comments(_JS.read_text(encoding="utf-8"))
        replace = js[js.index("replaceBtn.addEventListener"):]
        replace = replace[:replace.index("});")]
        self.assertIn("!current.rewrites", replace)


class TheActionVocabularyIsClosedTests(unittest.TestCase):
    def test_an_unknown_action_is_refused(self):
        from services.draft_assist import assist

        result = assist("some draft", "definitely-not-an-action")
        self.assertFalse(result.ran)
        self.assertIn("not an available draft action", result.reason)

    def test_the_action_never_becomes_a_free_text_instruction(self):
        # The action arrives from a form field. An open vocabulary would let a
        # caller pass arbitrary instructions to the model through it.
        source = _SERVICE.read_text(encoding="utf-8")
        self.assertIn("_ACTIONS_BY_KEY.get(", source)

    def test_every_action_the_product_owner_named_exists(self):
        from services.draft_assist import DRAFT_ACTIONS

        keys = {a.key for a in DRAFT_ACTIONS}
        for expected in ("clarify", "shorter", "longer", "formal", "direct", "rfi",
                         "observation", "meeting_note", "email", "grammar", "ambiguity"):
            self.assertIn(expected, keys, expected)

    def test_an_empty_draft_does_nothing(self):
        from services.draft_assist import assist

        result = assist("   ", "clarify")
        self.assertFalse(result.ran)
        self.assertIn("nothing in the draft", result.reason)

    def test_an_oversized_draft_is_refused_before_any_call(self):
        from services.draft_assist import MAX_DRAFT_CHARS, assist

        with patch("services.draft_assist.call_llm_json") as spy:
            result = assist("x" * (MAX_DRAFT_CHARS + 1), "clarify")
        self.assertFalse(result.ran)
        spy.assert_not_called()


class ThePolicyGateAppliesTests(unittest.TestCase):
    def setUp(self):
        self.routes = _ROUTES.read_text(encoding="utf-8")
        self.route = self.routes[self.routes.index("def composer_draft_assist"):]
        self.route = self.route[:self.route.index("\n@workspace_bp.route")]
        # The route's own docstring explains the require_approval behaviour by
        # name, so a raw scan would let the explanation of a prohibition satisfy
        # the test for it. Strip prose before asserting absence.
        code = re.sub(r'"""[\s\S]*?"""', "", self.route)
        self.code = re.sub(r"#[^\n]*", "", code)

    def test_it_uses_the_same_external_ai_resolver_as_everything_else(self):
        self.assertIn("_external_ai_status(workspace)", self.route)

    def test_a_non_allow_decision_refuses_and_says_nothing_was_sent(self):
        self.assertIn('if status != "allow"', self.route)
        self.assertIn("nothing was transmitted", self.route)

    def test_require_approval_is_not_silently_treated_as_allow(self):
        # A convenience must never be the thing that widens a security boundary.
        # "allow" is the only accepted status: there is no second branch letting
        # REQUIRE_APPROVAL through, and no approval token this route reads.
        self.assertNotIn("require_approval", self.code)
        self.assertNotIn("confirm", self.code)
        self.assertEqual(self.code.count('"allow"'), 1)

    def test_the_route_writes_nothing(self):
        for token in ("store.save(", "add_message", "create_case", "attach_source"):
            self.assertNotIn(token, self.code, token)


class TheAffordanceTests(unittest.TestCase):
    def setUp(self):
        self.macros = _MACROS.read_text(encoding="utf-8")
        self.js = _strip_js_comments(_JS.read_text(encoding="utf-8"))
        self.css = _CSS.read_text(encoding="utf-8")

    def test_the_pen_ships_hidden_and_follows_the_draft(self):
        button = re.search(r"<button[^>]*id=\"dock-composer-pen\"[^>]*>", self.macros, re.S)
        self.assertIsNotNone(button)
        self.assertIn("hidden", button.group(0))
        self.assertIn("pen.hidden = !hasText", self.js)

    def test_the_pen_only_exists_inside_a_project(self):
        # The route it calls is policy-gated per project; there is no workspace
        # to evaluate that against on the project-less Composer.
        block = self.macros[self.macros.index("dock-composer-pen") - 1200:]
        block = block[:block.index("dock-composer-pen") + 200]
        self.assertIn("{% if project_id %}", block)

    def test_one_component_serves_phone_and_desktop(self):
        self.assertEqual(self.macros.count('id="dock-composer-pen-sheet"'), 1)
        sheet_rules = re.findall(r"\.composer-pen-sheet\s*\{[^}]*\}", self.css)
        self.assertGreaterEqual(len(sheet_rules), 2, "no phone-specific treatment")

    def test_the_comparison_stacks_on_a_phone(self):
        phone = self.css[self.css.index("CLAUDE-COMPOSER-DRAFT-ASSIST-01"):]
        phone = phone[phone.index("@media (max-width: 640px)"):]
        self.assertIn("grid-template-columns: 1fr", phone)

    def test_the_sheet_clears_the_home_indicator(self):
        phone = self.css[self.css.index("CLAUDE-COMPOSER-DRAFT-ASSIST-01"):]
        phone = phone[phone.index("@media (max-width: 640px)"):]
        self.assertIn("safe-area-inset-bottom", phone)

    def test_escape_closes_without_touching_the_draft(self):
        self.assertIn("event.key === 'Escape'", self.js)


class FailureIsReassuringTests(unittest.TestCase):
    """A reviewer's first worry when this breaks is "what happened to my text"."""

    def test_every_failure_path_says_the_draft_is_untouched(self):
        js = _strip_js_comments(_JS.read_text(encoding="utf-8"))
        self.assertGreaterEqual(js.count("Your draft is untouched"), 2)

    def test_the_service_says_so_too(self):
        source = _SERVICE.read_text(encoding="utf-8")
        self.assertIn("Your draft is untouched", source)

    def test_a_failed_model_call_returns_a_reason_not_an_exception(self):
        from services.draft_assist import assist
        from services.llm_gateway import LLMCallOutcome

        with patch("services.draft_assist.call_llm_json",
                   return_value=LLMCallOutcome(ran=False, skipped_reason="no key")):
            result = assist("A draft.", "clarify")
        self.assertFalse(result.ran)
        self.assertIsNotNone(result.reason)


class ItActuallyWorksTests(unittest.TestCase):
    def test_a_successful_call_returns_the_proposal(self):
        from services.draft_assist import assist
        from services.llm_gateway import LLMCallOutcome

        with patch("services.draft_assist.call_llm_json",
                   return_value=LLMCallOutcome(
                       ran=True, parsed={"proposal": "Sharpened text.", "note": ""})):
            result = assist("rough text", "clarify")
        self.assertTrue(result.ran)
        self.assertEqual(result.proposal, "Sharpened text.")
        self.assertTrue(result.rewrites)

    def test_the_authors_draft_is_labelled_in_the_prompt(self):
        from services.draft_assist import assist
        from services.llm_gateway import LLMCallOutcome

        with patch("services.draft_assist.call_llm_json",
                   return_value=LLMCallOutcome(ran=True, parsed={"proposal": "x"})) as spy:
            assist("the rough draft", "rfi")
        prompt = spy.call_args.kwargs["user_prompt"]
        self.assertIn("THE AUTHOR'S DRAFT", prompt)
        self.assertIn("the rough draft", prompt)


if __name__ == "__main__":
    unittest.main()
