"""CLAUDE-DRAFT-ASSIST-REACHABILITY-01 - the pen had nothing to click.

Reproduced live on 2026-09-22 in the real project Composer: the pen appeared,
the sheet opened, static/js/draft_assist.js was loaded and the route was live -
and `actionCount` in the rendered DOM was 0, against an `available_actions()`
that returns eleven. No request could ever be issued, so the Proposed side of
the comparison stayed empty forever.

THE CAUSE WAS JINJA SCOPING, not the feature. `draft_actions` was supplied by
app.py's inject_globals as a context global, and read inside a macro. Jinja
imports a macro file WITHOUT the calling context unless `with context` is
written, and every `{% import "_macros.html" as macros %}` in this codebase is
the plain form - so the loop iterated an undefined name.

WHY tests/test_composer_draft_assist_01.py DID NOT CATCH IT, which is the part
worth keeping: that file tests the service, the route and the shape of the
JavaScript. All three were correct. Nothing asserted that a human could reach
them. This file tests exactly that, against rendered HTML, because "the feature
works" and "the feature can be used" turned out to be different claims.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from services.draft_assist import DRAFT_ACTIONS


class TheActionsReachTheRenderedPage(unittest.TestCase):
    """Rendered markup, not source inspection - the gap was in the render."""

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp = Path(tempfile.mkdtemp(prefix="draft_assist_reach_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="reach-001", filename="Spec.pdf",
            ingested_at="2026-01-01T00:00:00+00:00"))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

    def _workspace_html(self) -> str:
        response = self.client.get("/projects/reach-001/workspace")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_every_draft_action_renders_a_button(self):
        """The defect, stated as the property that was missing."""
        html = self._workspace_html()
        rendered = set(re.findall(r'data-assist-action="([a-z_]+)"', html))
        expected = {action.key for action in DRAFT_ACTIONS}
        self.assertEqual(
            rendered, expected,
            "the pen sheet rendered no usable actions - a feature that cannot "
            "be asked for")

    def test_the_count_is_not_zero(self):
        """Stated separately and bluntly: zero is the shape of the bug."""
        html = self._workspace_html()
        self.assertGreater(len(re.findall(r'data-assist-action=', html)), 0)

    def test_the_pen_and_its_sheet_are_present_with_a_live_url(self):
        html = self._workspace_html()
        self.assertIn('id="dock-composer-pen"', html)
        self.assertIn('id="dock-composer-pen-sheet"', html)
        self.assertIn("/workspace/composer/draft-assist", html)

    def test_the_comparison_starts_hidden_so_an_empty_proposed_is_never_shown(self):
        """An empty Proposed box must not be reachable as a resting state."""
        html = self._workspace_html()
        compare = re.search(
            r'<div class="composer-pen-compare"[^>]*>', html)
        self.assertIsNotNone(compare)
        self.assertIn("hidden", compare.group(0))

    def test_the_client_script_is_actually_loaded(self):
        self.assertIn("js/draft_assist.js", self._workspace_html())


class TheMacroDoesNotDependOnContextGlobals(unittest.TestCase):
    """The rule that broke, asserted where it can be seen.

    `_macros.html` is imported WITHOUT context everywhere, so any name a macro
    reads must arrive as a parameter. This guards the next macro as much as this
    one.
    """

    def test_every_import_of_the_macro_file_is_the_plain_form(self):
        plain = with_context = 0
        for path in Path("templates").rglob("*.html"):
            text = path.read_text(encoding="utf-8")
            plain += len(re.findall(
                r'{%\s*import\s+"_macros\.html"\s+as\s+macros\s*%}', text))
            with_context += len(re.findall(
                r'{%\s*import\s+"_macros\.html"\s+as\s+macros\s+with\s+context\s*%}',
                text))
        self.assertGreater(plain, 0)
        self.assertEqual(
            with_context, 0,
            "an import gained 'with context'; if that is deliberate, this "
            "test and conversation_dock's draft_actions parameter should be "
            "revisited together")

    def test_conversation_dock_takes_draft_actions_as_a_parameter(self):
        macros = Path("templates/_macros.html").read_text(encoding="utf-8")
        signature = re.search(r"{%\s*macro conversation_dock\((.*?)\)\s*%}",
                              macros, re.S)
        self.assertIsNotNone(signature)
        self.assertIn("draft_actions", signature.group(1))

    def test_every_call_site_passes_it(self):
        """A macro parameter with a safe default is silent when forgotten."""
        for name in ("templates/case_workspace.html",
                     "templates/planning_composer.html"):
            text = Path(name).read_text(encoding="utf-8")
            calls = len(re.findall(r"macros\.conversation_dock\(", text))
            passes = len(re.findall(r"draft_actions=draft_actions", text))
            self.assertEqual(
                passes, calls,
                f"{name} calls conversation_dock {calls} time(s) but passes "
                f"draft_actions {passes} time(s)")


if __name__ == "__main__":
    unittest.main()
