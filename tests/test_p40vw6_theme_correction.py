"""
CLAUDE-P40-VW6 - Correct Light, Dark, and Tinted Panel Rendering.

Product-owner browser observations on the VW3 per-panel Appearance
Matrix: Light panels showed untreated portions; Dark panels weren't
genuinely black, the Appearance popup let underlying text show
through, the workspace/Chat divider disappeared; Tinted panels were
inconsistently beige/gold rather than a uniform light navy-blue.

Root cause, diagnosed before changing anything (see the checkpoint
entry and commit message for the full investigation):

0. THE PRIMARY FINDING: tokens.css's own VW3-authored Dark-mode
   comment block ended with a stray Jinja-style `#}` instead of CSS's
   own `*/` (a copy-paste artifact - this codebase's .html templates
   close Jinja comments with `#}`, its .css files close comments with
   `*/`, and VW3 used the wrong one, present since the very first VW3
   commit, e4b241d). CSS comments only end at the FIRST real `*/` -
   `#}` is just more comment text - so the `:root {` meant to open the
   --dark-* token block was ITSELF swallowed inside the still-open
   comment, and every --dark-* declaration that followed was a bare,
   rule-less custom-property declaration with no enclosing `:root {}`
   - invalid CSS, silently dropped by every browser. Every
   var(--dark-canvas)/var(--dark-text-primary)/etc. reference in
   main.css's .appearance-dark rule was therefore resolving against
   tokens that WERE NEVER ACTUALLY DEFINED, collapsing --canvas/
   --surface-primary/--text-primary themselves to their inherited/
   initial value inside that scope (a fully specified CSS outcome, not
   a no-op) - explaining "the page background is not genuinely black"
   (fell through to the page's own light canvas behind whatever was
   still opaque) and "some text and internal panel layers do not
   receive the Dark treatment" far more completely than any single
   component-level gap could. Every VW3/VW4/VW5-era test that appeared
   to verify Dark mode's tokens passed anyway, because they all read
   tokens.css as PLAIN TEXT via regex, which has no concept of CSS
   comment syntax and matches `--dark-canvas: #1A1814;` whether it's
   real, live CSS or dead text inside an unterminated comment - why
   this went undetected across three prior stages. BrokenCommentGuard
   Tests below is the fix for that specific blind spot: it strips real
   CSS comments first, the way a browser would, before checking
   anything.
1. VW3's Tinted implementation ALSO never redefined the surface's
   token SCOPE - independent of finding #0 above, a genuine, separate
   architecture defect, not a symptom of the broken comment - it only
   ever swapped ONE element's own `background` per surface to
   --surface-secondary (Limestone, #E1D7C1 - a real, correct,
   UNRELATED token meaning "nav surfaces, grouped controls," never a
   dedicated Tinted palette). Every other element inside that surface
   reading --surface-primary/--border/--text-primary directly (finding
   cards, blank states, form controls, ...) kept rendering untinted
   Light values underneath - "some surfaces become tinted and others
   do not" was that coverage gap, and "the current tint is beige/gold"
   was --surface-secondary's own real meaning being reused as if it
   were the Tinted color.
2. --dark-canvas/--dark-surface-primary were ALSO a dark warm brown
   (#1A1814/#25221D) in the source text, never black, independent of
   whether the comment bug let them apply at all - "the page
   background is not genuinely black" was literal and correct on its
   own terms too.
3. Browsers never theme a bare <select>/<input>/<textarea>/<button>
   from surrounding page CSS - the existing font-family backstop rule
   (main.css's own header comment) never had a color equivalent, so
   any form control without its own explicit color styling (most
   visibly <select>, e.g. the VW1/VW4 "open a Document here" dropdown)
   rendered with the browser's native white-background/black-text
   chrome regardless of the chosen appearance mode - a real, additional
   share of "portions of the panel do not receive the Dark/Light/
   Tinted treatment," on top of finding #0.
4. The workspace/Chat divider used --border (mode-scoped, so it always
   matched whatever CHAT's own side happened to be) instead of a fixed
   token - two adjacent Dark surfaces produced two very-low-contrast
   dark-on-dark lines, technically present but not perceptible.
5. The Appearance popup's z-index (20) sat below the Display context
   menu's (40) with no real margin from other overlay values in the
   file - raised well above everything else, not changed from opaque
   (it always was: a solid var() background, never rgba).

Fix: tokens.css gained a corrected --dark-* family (genuine black
canvas/surface-primary) and a new --tint-* family (light navy-blue,
#D8E2F0 as the product owner specified, used directly as
--tint-surface-primary rather than diluted toward near-white) plus one
new --divider-strong token, deliberately never redefined by either
scope, for the one seam that can have a different mode on each side.
main.css's Tinted rule now redefines the full token set in the SAME
combined selector .appearance-dark already used - zero per-component
changes needed, the same benefit Dark always had. The global form-
control rule gained background-color/color/border-color defaults
(tokens, so they track whichever surface's scope they render inside).
The Chat divider now uses --divider-strong. The topbar popover z-index
is now 60 (above every other overlay value in the file).

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (this repo's established convention). No browser-
automation tool is actually connected in this session (confirmed
directly via tool search, consistent with every prior VW stage) -
verification here is structural CSS/JS/HTML source assertions plus a
real, non-simulated invocation of tools/check_contrast.py; the
required real-browser visual walkthrough is stated as a limitation in
the final report, not fabricated.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_APP_MENU_HTML_PATH = _REPO_ROOT / "templates" / "_app_menu.html"
_AUTH_SHELL_HTML_PATH = _REPO_ROOT / "templates" / "auth_shell.html"
_GATEWAY_SHELL_HTML_PATH = _REPO_ROOT / "templates" / "gateway_shell.html"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_CHECK_CONTRAST_PATH = _REPO_ROOT / "tools" / "check_contrast.py"

_SURFACE_SELECTORS = {
    "menu": ".workspace-topbar",
    "lists": ".launcher-panel",
    "display": ".app-main",
    # CLAUDE-P40-EYE1: the Toolbox surface's own painted root moved to
    # .workspace-right-column (the new full-height column containing
    # Toolbox AND Eye) - see that stage's own comment in main.css.
    "toolbox": ".workspace-right-column",
    "chat": ".chat-region",
}


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw6_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw6_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="vw6_owner", project_name="Riverside Terminal VW6 Workspace")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


# ---------------------------------------------------------------------------
# Five surface radio groups still present (VW3 preserved)
# ---------------------------------------------------------------------------

class FiveSurfaceRadioGroupsTests(_BaseTestCase):
    def test_global_appearance_choice_has_at_least_three_modes(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01 supersedes this class's own
        # "five independent surface radio groups" premise outright -
        # Appearance is now ONE global choice (Product Owner: "do not
        # allow panel-by-panel theme mixing"), so there is no longer a
        # per-surface id to check for each of the five former surfaces.
        # This asserts the ONE radio group still offers at least the
        # three modes this stage's own subject (Black/Midnight Blue)
        # covers - see test_p40vw8qa_approved_theme_set.py for the full,
        # exact five-choice (incl. Deep Forest/Deep Ocean) assertion.
        client = self._client_as("vw6_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for mode in ("light", "dark", "tinted"):
            self.assertIn(f'id="appearance-all-{mode}"', body, mode)


# ---------------------------------------------------------------------------
# The actual primary root cause: an unterminated CSS comment (a stray
# Jinja-style `#}` instead of `*/`) silently swallowed the entire
# --dark-* :root block since the very first VW3 commit. Every prior
# stage's own "verify the dark tokens" tests passed regardless, because
# they all read the CSS file as plain text via regex, which cannot
# distinguish real, live declarations from dead text inside a broken
# comment. These tests strip real CSS comments first (the way a
# browser actually parses the file) before checking anything, closing
# that specific blind spot for good.
# ---------------------------------------------------------------------------

class BrokenCommentGuardTests(unittest.TestCase):
    @staticmethod
    def _strip_css_comments(css: str) -> str:
        return re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def test_tokens_css_has_no_stray_jinja_comment_closer(self):
        # The exact character sequence that caused this - a CSS file
        # must never contain a Jinja "#}" comment closer at all.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("#}", tokens_css)

    def test_main_css_has_no_stray_jinja_comment_closer(self):
        main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("#}", main_css)

    def test_tokens_css_braces_balance_after_stripping_real_comments(self):
        # A regex text-match test (like most others in this file, and
        # like every dark-token test VW3/VW4/VW5 ever wrote) cannot
        # catch an unterminated comment - only a check that's aware of
        # actual CSS comment syntax can. Balanced braces AFTER comments
        # are removed is a real, if partial, proxy for "this file
        # parses the way its author intended," and is exactly the
        # check that would have caught this defect on day one.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        stripped = self._strip_css_comments(tokens_css)
        self.assertEqual(stripped.count("{"), stripped.count("}"),
                          "tokens.css has unbalanced braces once real CSS comments are removed")

    def test_main_css_braces_balance_after_stripping_real_comments(self):
        main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        stripped = self._strip_css_comments(main_css)
        self.assertEqual(stripped.count("{"), stripped.count("}"),
                          "main.css has unbalanced braces once real CSS comments are removed")

    def test_dark_token_declarations_survive_comment_stripping(self):
        # The specific, concrete proof that the bug this class guards
        # against is actually fixed: --dark-canvas (and every sibling
        # token) must still be present as a REAL declaration - inside
        # an actual rule block, not inside a comment - after comments
        # are stripped the way a browser would strip them.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        stripped = self._strip_css_comments(tokens_css)
        self.assertIn("--dark-canvas: #000000;", stripped)
        # CLAUDE-P40-VW8-QA (Approved Theme Set): warm off-white
        # (#E8E4DC, product-owner spec), not pure #FFFFFF - "Continue
        # using readable warm off-white foreground text on the dark
        # themes" superseded VW6's own original white-text choice.
        self.assertIn("--dark-text-primary: #E8E4DC;", stripped)
        # CLAUDE-P40-VW8-QA retuned --tint-surface-primary (see
        # TintedPaletteTests below for the live, non-hardcoded check) -
        # this test's own job is only "survives comment stripping as a
        # real declaration", so it just needs A value present, not the
        # specific one.
        self.assertRegex(stripped, r"--tint-surface-primary:\s*#[0-9a-fA-F]{6};")
        self.assertIn("--divider-strong: #756B57;", stripped)


# ---------------------------------------------------------------------------
# Genuine black Dark surface application
# ---------------------------------------------------------------------------

class DarkPaletteTests(unittest.TestCase):
    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_dark_canvas_is_literal_black(self):
        self.assertRegex(self.tokens_css, r"--dark-canvas:\s*#000000\s*;")

    def test_dark_surface_primary_is_literal_black(self):
        self.assertRegex(self.tokens_css, r"--dark-surface-primary:\s*#000000\s*;")

    def test_dark_text_primary_is_warm_off_white(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set) superseded this stage's
        # own original pure-white choice with a warm off-white
        # (#E8E4DC, product-owner spec, shared across Black/Midnight
        # Blue/Deep Forest).
        self.assertRegex(self.tokens_css, r"--dark-text-primary:\s*#E8E4DC\s*;")

    def test_no_leftover_warm_brown_dark_canvas(self):
        # The VW3 defect this stage fixes - the old "not genuinely black"
        # value must not still be present anywhere as the canvas/surface.
        self.assertNotIn("--dark-canvas: #1A1814", self.tokens_css)
        self.assertNotIn("--dark-surface-primary: #25221D", self.tokens_css)

    def test_all_five_surfaces_redefine_canvas_and_surface_primary_to_dark_black(self):
        rule_match = re.search(r"\.workspace-topbar\.appearance-dark,[^{]*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule_match, "no combined .appearance-dark rule found")
        body = rule_match.group(1)
        self.assertIn("--canvas: var(--dark-canvas);", body)
        self.assertIn("--surface-primary: var(--dark-surface-primary);", body)
        for selector in _SURFACE_SELECTORS.values():
            self.assertIn(f"{selector}.appearance-dark", self.main_css, selector)

    def test_dark_palette_passes_the_repos_own_contrast_checker(self):
        dark = dict(re.findall(r"(--dark-[a-zA-Z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css))
        rename = {
            "--dark-canvas": "--canvas", "--dark-surface-primary": "--surface-primary",
            "--dark-text-primary": "--text-primary", "--dark-text-secondary": "--text-secondary",
            "--dark-text-metadata": "--text-metadata",
            "--dark-seal-red": "--seal-red", "--dark-seal-red-tint": "--seal-red-tint",
            "--dark-machine-blue": "--machine-blue", "--dark-machine-blue-tint": "--machine-blue-tint",
            "--dark-highlight-orange": "--highlight-orange", "--dark-highlight-orange-tint": "--highlight-orange-tint",
            "--dark-accepted-green": "--accepted-green", "--dark-accepted-green-tint": "--accepted-green-tint",
            "--dark-attention-amber": "--attention-amber", "--dark-attention-amber-tint": "--attention-amber-tint",
            "--dark-failure-red": "--failure-red", "--dark-failure-red-tint": "--failure-red-tint",
            "--dark-risk-red": "--risk-red", "--dark-risk-red-tint": "--risk-red-tint",
        }
        lines = [":root {"]
        for src, dst in rename.items():
            self.assertIn(src, dark, f"{src} missing from tokens.css")
            lines.append(f"    {dst}: {dark[src]};")
        lines.append("}")
        with tempfile.TemporaryDirectory() as td:
            scratch = Path(td) / "dark_scratch.css"
            scratch.write_text("\n".join(lines), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(_CHECK_CONTRAST_PATH), str(scratch)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ALL PAIRINGS PASS", result.stdout)


# ---------------------------------------------------------------------------
# Consistent #D8E2F0 light navy Tinted application; old beige/gold removed
# ---------------------------------------------------------------------------

class TintedPaletteTests(unittest.TestCase):
    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_tint_surface_primary_is_the_specified_navy(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): Tinted ("Midnight
        # Blue") was turned from a LIGHT navy-grey daylight variant into
        # one of the three DARK appearance choices - #001426 (product-
        # owner spec), a solid, visibly saturated deep navy. This is a
        # deliberate reversal of this stage's own original "considerably
        # lighter" assertion (r > 200), not a regression - see tokens.css's
        # own updated comment for the full reasoning. Still verified as
        # genuinely blue (not grey/black) via a real RGB channel
        # comparison rather than a second hardcoded hex.
        match = re.search(r"--tint-surface-primary:\s*#([0-9a-fA-F]{6})\s*;", self.tokens_css)
        self.assertIsNotNone(match)
        r, g, b = (int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        self.assertGreater(b, r, "Tinted surface must read as blue, not warm/beige (blue channel > red channel)")
        self.assertLess(r, 40, "Tinted surface must be a genuinely dark navy, not a light daylight variant")

    def test_tint_canvas_is_the_specified_navy(self):
        match = re.search(r"--tint-canvas:\s*#([0-9a-fA-F]{6})\s*;", self.tokens_css)
        self.assertIsNotNone(match)
        r, g, b = (int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))
        self.assertGreater(b, r, "Tinted canvas must read as blue, not warm/beige (blue channel > red channel)")
        self.assertLess(r, 40, "Tinted canvas must be a genuinely dark navy, not a light daylight variant")

    def test_all_five_surfaces_redefine_to_the_same_tint_family(self):
        rule_match = re.search(r"\.workspace-topbar\.appearance-tinted,[^{]*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule_match, "no combined .appearance-tinted rule found")
        body = rule_match.group(1)
        self.assertIn("--surface-primary: var(--tint-surface-primary);", body)
        self.assertIn("--text-primary: var(--tint-text-primary);", body)
        self.assertIn("--border: var(--tint-border);", body)
        for selector in _SURFACE_SELECTORS.values():
            self.assertIn(f"{selector}.appearance-tinted", self.main_css, selector)

    def test_old_beige_gold_tint_mechanism_is_gone(self):
        # The VW3 defect: single-property rules swapping ONE element's
        # background straight to --surface-secondary (Limestone/beige)
        # as if it were a dedicated Tinted color. None of these narrow
        # rules should remain - the combined rule above replaces all of
        # them.
        for stale in (
            ".workspace-topbar.appearance-tinted { background: var(--surface-secondary); }",
            ".launcher-panel.appearance-tinted { background: var(--surface-secondary); }",
            ".workspace-pane-toolbox.appearance-tinted { background: var(--surface-secondary); }",
            ".app-main.appearance-tinted .workspace-pane-display {\n    background: var(--surface-secondary);\n}",
        ):
            self.assertNotIn(stale, self.main_css, stale)

    def test_tinted_scope_never_leaves_surface_secondary_pointing_at_the_old_beige_token(self):
        # --surface-secondary itself IS redefined inside the tinted
        # scope (to --tint-surface-secondary, a deeper navy) - it must
        # not still resolve to the untouched light Limestone value
        # anywhere inside that scope.
        rule_match = re.search(r"\.workspace-topbar\.appearance-tinted,[^{]*\{([^}]*)\}", self.main_css, re.S)
        self.assertIn("--surface-secondary: var(--tint-surface-secondary);", rule_match.group(1))

    def test_tint_palette_passes_the_repos_own_contrast_checker(self):
        tint = dict(re.findall(r"(--tint-[a-zA-Z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css))
        rename = {
            "--tint-canvas": "--canvas", "--tint-surface-primary": "--surface-primary",
            "--tint-text-primary": "--text-primary", "--tint-text-secondary": "--text-secondary",
            "--tint-text-metadata": "--text-metadata",
            "--tint-seal-red": "--seal-red", "--tint-seal-red-tint": "--seal-red-tint",
            "--tint-machine-blue": "--machine-blue", "--tint-machine-blue-tint": "--machine-blue-tint",
            "--tint-highlight-orange": "--highlight-orange", "--tint-highlight-orange-tint": "--highlight-orange-tint",
            "--tint-accepted-green": "--accepted-green", "--tint-accepted-green-tint": "--accepted-green-tint",
            "--tint-attention-amber": "--attention-amber", "--tint-attention-amber-tint": "--attention-amber-tint",
            "--tint-failure-red": "--failure-red", "--tint-failure-red-tint": "--failure-red-tint",
            "--tint-risk-red": "--risk-red", "--tint-risk-red-tint": "--risk-red-tint",
        }
        lines = [":root {"]
        for src, dst in rename.items():
            self.assertIn(src, tint, f"{src} missing from tokens.css")
            lines.append(f"    {dst}: {tint[src]};")
        lines.append("}")
        with tempfile.TemporaryDirectory() as td:
            scratch = Path(td) / "tint_scratch.css"
            scratch.write_text("\n".join(lines), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(_CHECK_CONTRAST_PATH), str(scratch)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ALL PAIRINGS PASS", result.stdout)


# ---------------------------------------------------------------------------
# Opaque Appearance popup, stacking above underlying content
# ---------------------------------------------------------------------------

class PopupOpacityAndStackingTests(unittest.TestCase):
    def setUp(self):
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_popup_background_is_a_solid_token_never_rgba(self):
        rule = re.search(r"\.workspace-layout-options,\s*\n\.workspace-appearance-options,\s*\n\.workspace-user-options\s*\{([^}]*)\}", self.main_css)
        self.assertIsNotNone(rule)
        body = rule.group(1)
        self.assertIn("background: var(--surface-primary);", body)
        self.assertNotIn("rgba(", body)

    def test_popup_z_index_is_above_the_display_context_menu(self):
        # CLAUDE-P40-VW7: the popup is no longer the file's single highest
        # z-index - the new Add Tag/Make Task selection toolbar (70) and
        # dialogs (80) legitimately need to paint over it too (a dialog
        # opened while the Appearance popup happens to be open must not
        # render underneath it), following this same rule's own stated
        # reasoning ("raised well above every other overlay ... so this
        # menu reliably paints over ... content regardless of what else
        # is open") one step further. What this test actually protects -
        # the popup staying strictly above the Display context menu (VW1)
        # - still holds and is asserted directly.
        popup_z = int(re.search(r"\.workspace-layout-options,.*?z-index:\s*(\d+)", self.main_css, re.S).group(1))
        self.assertGreater(popup_z, 40)  # strictly above the Display context menu (VW1)

    def test_display_context_menu_still_below_the_popup(self):
        context_menu_z = int(re.search(r"\.display-context-menu\s*\{[^}]*z-index:\s*(\d+)", self.main_css, re.S).group(1))
        popup_z = int(re.search(r"\.workspace-layout-options,.*?z-index:\s*(\d+)", self.main_css, re.S).group(1))
        self.assertLess(context_menu_z, popup_z)

    def test_conv_selection_toolbar_and_dialog_are_correctly_ordered_overlays(self):
        # CLAUDE-P40-VW7's own two new overlay layers - the selection
        # toolbar and the Add Tag/Make Task dialogs - sit strictly above
        # the layer below each (dialog > toolbar > Appearance popup >
        # Display context menu), mirroring this file's own established
        # "explicit, comfortable margin" stacking discipline rather than
        # reusing an existing tier. No longer asserted as the file's
        # global maximum - CLAUDE-P40-VW7A's UI Reference Mode badge
        # (z-index 100) deliberately sits one tier above the dialog, so
        # a reference badge is never hidden behind a popup/dialog while
        # inspecting one; see test_ui_reference_mode_badge_is_the_new_
        # top_overlay below for that invariant.
        popup_z = int(re.search(r"\.workspace-layout-options,.*?z-index:\s*(\d+)", self.main_css, re.S).group(1))
        toolbar_z = int(re.search(r"\.conv-selection-toolbar\s*\{[^}]*z-index:\s*(\d+)", self.main_css, re.S).group(1))
        dialog_z = int(re.search(r"\.conv-dialog\s*\{[^}]*z-index:\s*(\d+)", self.main_css, re.S).group(1))
        self.assertGreater(toolbar_z, popup_z)
        self.assertGreater(dialog_z, toolbar_z)

    def test_ui_reference_mode_badge_is_the_new_top_overlay(self):
        # CLAUDE-P40-VW7A: the reference-mode badge is a developer/QA
        # aid, not a normal application overlay - it needs to stay
        # visible even when inspecting a control inside an open dialog,
        # so it is deliberately the file's actual highest z-index now.
        all_z = [int(m) for m in re.findall(r"z-index:\s*(-?\d+)", self.main_css)]
        dialog_z = int(re.search(r"\.conv-dialog\s*\{[^}]*z-index:\s*(\d+)", self.main_css, re.S).group(1))
        badge_z = int(re.search(r"\.ui-reference-mode-active \[data-ui-ref\]::after\s*\{[^}]*z-index:\s*(\d+)", self.main_css, re.S).group(1))
        self.assertGreater(badge_z, dialog_z)
        self.assertEqual(badge_z, max(all_z), f"UI Reference Mode badge z-index {badge_z} is not the highest in the file (max={max(all_z)})")


# ---------------------------------------------------------------------------
# Workspace/Chat divider - explicit, mode-invariant token, visible in
# every combination
# ---------------------------------------------------------------------------

class DividerTests(unittest.TestCase):
    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_divider_strong_token_defined(self):
        self.assertRegex(self.tokens_css, r"--divider-strong:\s*#[0-9a-fA-F]{6}\s*;")

    def test_divider_strong_never_redefined_by_dark_or_tinted_scopes(self):
        # Deliberately mode-invariant - must not appear inside either
        # combined .appearance-dark/.appearance-tinted rule body.
        for combined_selector in (r"\.workspace-topbar\.appearance-dark,[^{]*\{([^}]*)\}",
                                   r"\.workspace-topbar\.appearance-tinted,[^{]*\{([^}]*)\}"):
            rule = re.search(combined_selector, self.main_css, re.S)
            self.assertIsNotNone(rule)
            self.assertNotIn("--divider-strong", rule.group(1))

    def test_chat_divider_uses_the_mode_invariant_token(self):
        rule = re.search(r"\.conversation-dock-resize-handle::before\s*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule)
        self.assertIn("var(--divider-strong)", rule.group(1))
        self.assertNotIn("var(--border);", rule.group(1))

    def test_divider_strong_has_adequate_contrast_against_all_three_backgrounds(self):
        divider_hex = re.search(r"--divider-strong:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css).group(1)
        light_bg = re.search(r"--surface-primary:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css).group(1)
        dark_bg = re.search(r"--dark-canvas:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css).group(1)
        tint_bg = re.search(r"--tint-canvas:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens_css).group(1)

        def rel_lum(hexcode):
            def lin(c):
                c = c / 255
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            h = hexcode.lstrip("#")
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

        def contrast(a, b):
            la, lb = rel_lum(a), rel_lum(b)
            hi, lo = max(la, lb), min(la, lb)
            return (hi + 0.05) / (lo + 0.05)

        for bg, label in ((light_bg, "light"), (dark_bg, "dark"), (tint_bg, "tint")):
            ratio = contrast(divider_hex, bg)
            self.assertGreaterEqual(ratio, 3.0, f"divider vs {label} background only {ratio:.2f}:1")


# ---------------------------------------------------------------------------
# Internal wrappers and empty states (esp. form controls) follow their
# parent surface mode
# ---------------------------------------------------------------------------

class InternalWrapperCoverageTests(_BaseTestCase):
    def test_global_form_control_backstop_sets_background_and_color(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        rule = re.search(r"button, input, select, textarea \{([^}]*)\}", css, re.S)
        self.assertIsNotNone(rule)
        body = rule.group(1)
        self.assertIn("background-color: var(--surface-primary);", body)
        self.assertIn("color: var(--text-primary);", body)
        self.assertIn("border-color: var(--border);", body)

    def test_division_picker_select_has_no_special_case_override_bypassing_the_backstop(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        # .display-division-picker (the VW1/VW4 dropdown) must not set
        # its own conflicting background/color that would defeat the
        # global backstop for this specific control.
        rule = re.search(r"\.display-division-picker\s*\{([^}]*)\}", css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotIn("background", rule.group(1))
        self.assertNotIn("color:", rule.group(1))

    def test_blank_display_division_has_no_background_of_its_own_inherits_parent_scope(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        rule = re.search(r"\.display-division-empty\s*\{([^}]*)\}", css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotIn("background", rule.group(1))


# ---------------------------------------------------------------------------
# Independent mixed-mode combinations remain independent (VW3 preserved)
# ---------------------------------------------------------------------------

class IndependentModeTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_all_five_former_surfaces_now_share_one_target_list(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01 supersedes this test's own
        # "independently wired" premise outright - Product Owner: "do
        # not allow panel-by-panel theme mixing." The five former
        # surface selectors still all exist as apply TARGETS (every one
        # of them still receives the appearance class), but there is no
        # longer a per-surface key/data-attribute distinguishing them -
        # one array, one mode, applied to all of them identically.
        start = self.html.index("CLAUDE-APPEARANCE-SIMPLIFY-01 (supersedes CLAUDE-P40-E3A Section")
        js = self.html[start:self.html.index("</script>", start)]
        for selector in _SURFACE_SELECTORS.values():
            self.assertIn(f"document.querySelector('{selector}')", js, selector)
        self.assertNotIn("data-appearance-target", js)

    def test_apply_mode_still_toggles_the_mutually_exclusive_classes(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): applyMode moved to
        # window.__applyStoredAppearanceMode (an earlier script block,
        # shared with the pre-paint pass - see that function's own
        # comment) and now toggles THREE classes (Deep Forest added a
        # 3rd dark theme), keyed off the current mode-value vocabulary
        # (black/midnight-blue/deep-forest, not the old dark/tinted).
        self.assertIn("window.__applyStoredAppearanceMode = function (el, mode)", self.html)
        self.assertIn("el.classList.toggle('appearance-dark', mode === 'black');", self.html)
        self.assertIn("el.classList.toggle('appearance-tinted', mode === 'midnight-blue');", self.html)
        self.assertIn("el.classList.toggle('appearance-deep-forest', mode === 'deep-forest');", self.html)


# ---------------------------------------------------------------------------
# Preference persistence and legacy compatibility unaffected
# ---------------------------------------------------------------------------

class PersistenceAndLegacyCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        start = self.html.index("CLAUDE-APPEARANCE-SIMPLIFY-01 (supersedes CLAUDE-P40-E3A Section")
        self.js = self.html[start:self.html.index("</script>", start)]

    def test_compat_mapping_extended_not_broken(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): the resolver moved to
        # window.__resolveStoredAppearanceMode (an earlier script block -
        # see that function's own comment for why) and the vocabulary/
        # default both changed (Black is now the default, not Light) -
        # but every legacy stored value ('dark'/'tinted', and the brief
        # interim 'graphite') still maps losslessly, the same guarantee
        # this test originally protected.
        self.assertIn("window.__resolveStoredAppearanceMode = function (stored)", self.html)
        self.assertIn("if (stored === 'dark' || stored === 'graphite') return 'black';", self.html)
        self.assertIn("if (stored === 'tinted') return 'midnight-blue';", self.html)
        self.assertIn("return 'black';", self.html)

    def test_persists_to_one_global_storage_key(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01 supersedes this test's own
        # "per-surface storage key" premise - Appearance persists under
        # ONE key now (beehive:appearance, no per-surface suffix), via
        # applyGlobalMode() (the direct successor to setSurfaceMode() -
        # same "exactly one place a mode is ever applied" discipline,
        # now global instead of per-surface). The FIVE now-retired
        # per-surface keys are still referenced, but only inside
        # __resolveGlobalAppearanceMode's own one-time migration logic
        # (an earlier script block), never written to again after that.
        self.assertIn("try { window.localStorage.setItem('beehive:appearance', mode); } catch (e) { /* ignore */ }", self.js)
        self.assertIn("function applyGlobalMode(mode, persist)", self.js)
        self.assertIn("window.__resolveGlobalAppearanceMode = function ()", self.html)


# ---------------------------------------------------------------------------
# VW4 Display Layout controls remain readable in every Menu/Display
# combination (token-based, no hardcoded colors)
# ---------------------------------------------------------------------------

class Vw4DisplayLayoutReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_stepper_and_apply_controls_use_only_tokens(self):
        for selector in (r"\.workspace-layout-stepper\s*\{([^}]*)\}", r"\.workspace-layout-apply\s*\{([^}]*)\}",
                         r"\.workspace-layout-quantity-value\s*\{([^}]*)\}"):
            rule = re.search(selector, self.main_css, re.S)
            self.assertIsNotNone(rule, selector)
            self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")

    def test_disabled_stepper_state_uses_only_tokens(self):
        rule = re.search(r"\.workspace-layout-stepper:disabled\s*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("var(--text-disabled)", rule.group(1))

    def test_display_layout_menu_lives_inside_menu_surface_scope(self):
        # The Display Layout <details> is a descendant of .workspace-
        # topbar in base.html, so it automatically inherits whichever
        # mode Menu is set to - confirmed structurally here.
        #
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the
        # Display Layout markup itself moved into the shared
        # templates/_app_menu.html partial ({% include %}d by base.html
        # inside .workspace-topbar, before #workspace-user-menu) - the
        # nesting proof now spans both files: the include site is still
        # between topbar-start and #workspace-user-menu in base.html's
        # own source, and the id itself lives inside the included file.
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        app_menu_html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")
        topbar_start = html.index('<div class="workspace-topbar">')
        topbar_end = html.index('id="workspace-user-menu"', topbar_start)
        self.assertIn('{% include "_app_menu.html" %}', html[topbar_start:topbar_end])
        self.assertIn('id="workspace-layout-menu"', app_menu_html)


# ---------------------------------------------------------------------------
# VW5 Sign-in / Gateway shell boundaries unchanged by this stage
# ---------------------------------------------------------------------------

class Vw5ShellBoundaryUnaffectedTests(_BaseTestCase):
    def test_auth_shell_still_has_no_appearance_matrix(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn("appearance-matrix", body)
        self.assertNotIn("workspace-appearance-menu", body)

    def test_gateway_shell_still_has_no_appearance_matrix(self):
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the
        # workspace-appearance-menu absence check is retired -
        # Appearance is now legitimately, deliberately shared onto
        # Gateway via the application menu bar (one global mode choice,
        # never per-surface). What this test actually guards - the OLD,
        # retired per-surface "matrix" UI (appearance-matrix) - never
        # existed on Gateway and still doesn't; that's the real invariant.
        client = self._client_as("vw6_owner", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("appearance-matrix", body)
        # CLAUDE-CA1D-GATEWAY-VISUAL-CONTINUITY-01 added the shared
        # deep-ocean background (landing-page) alongside gateway-shell -
        # unrelated to the appearance-matrix work this test guards.
        self.assertIn('class="gateway-shell landing-page"', body)

    def test_auth_shell_and_gateway_shell_templates_untouched_by_this_stage(self):
        auth_shell = _AUTH_SHELL_HTML_PATH.read_text(encoding="utf-8")
        gateway_shell = _GATEWAY_SHELL_HTML_PATH.read_text(encoding="utf-8")
        for html in (auth_shell, gateway_shell):
            self.assertNotIn("appearance-dark", html)
            self.assertNotIn("appearance-tinted", html)


# ---------------------------------------------------------------------------
# Actual document content is not recoloured
# ---------------------------------------------------------------------------

class DocumentContentNotRecolouredTests(unittest.TestCase):
    def test_no_filter_or_blend_mode_applied_anywhere_in_main_css(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("mix-blend-mode", css)
        # (?<!-) excludes backdrop-filter (a blur effect on the login
        # card, unrelated to recoloring) while still catching a real
        # bare `filter:` declaration.
        self.assertNotRegex(css, r"(?<!-)\bfilter:\s*(?!none)")

    def test_display_division_content_iframe_and_img_have_no_filter(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        rule = re.search(r"\.display-division-content iframe,\s*\n\.display-division-content img\s*\{([^}]*)\}", css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotIn("filter", rule.group(1))


class DeepOceanGlassMaterialTests(unittest.TestCase):
    """CLAUDE-DEEP-OCEAN-VISUAL-PARITY-01: Deep Ocean's own --ocean-*
    token family was already color-correct (a literal copy of
    .gateway-shell's own already-approved translucent palette) - what
    was missing was the backdrop-filter blur + box-shadow glow that
    make that palette actually READ as glass. Both new tokens are a
    literal copy of .gateway-shell .gateway-card-wide's own two
    properties, applied only to the genuinely floating/overlay
    surfaces (menu dropdowns, the pre-existing Display Layout/
    Appearance/Account popovers) plus a restrained glow-only treatment
    for the one bounded (non-floating) panel named in scope, the
    Composer dock."""

    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_new_tokens_are_a_literal_copy_of_the_gateway_reference(self):
        self.assertIn("--ocean-glass-blur: 14px;", self.tokens_css)
        self.assertIn("--ocean-glow: 0 24px 70px rgba(1, 8, 14, .5);", self.tokens_css)
        # The reference itself, unchanged - same literal values.
        idx = self.css.index(".gateway-shell .gateway-card-wide {")
        body = self.css[idx:idx + 300]
        self.assertIn("blur(14px)", body)
        self.assertIn("0 24px 70px rgba(1, 8, 14, .5)", body)

    def test_menu_dropdown_panels_get_the_glass_treatment_in_deep_ocean_only(self):
        idx = self.css.index(".workspace-topbar.appearance-deep-ocean .workspace-menubar-panel,")
        block = self.css[idx:self.css.index("}", idx)]
        self.assertIn("backdrop-filter: blur(var(--ocean-glass-blur));", block)
        self.assertIn("box-shadow: var(--ocean-glow);", block)
        # Every listed selector must itself carry the .appearance-deep-ocean
        # scope directly - never a bare, unscoped selector that would leak
        # the effect into every other appearance mode.
        header = self.css[idx:self.css.index("{", idx)]
        for selector in header.split(","):
            self.assertIn("appearance-deep-ocean", selector, selector)

    def test_composer_dock_gets_a_restrained_glow_only_no_blur(self):
        # The SAME selector text also opens the earlier, pre-existing
        # shared comma-list rule (tinted/dark/deep-forest/deep-ocean,
        # background-color only) - find the LATER, standalone occurrence
        # this stage added.
        idx = self.css.rindex(".chat-region.appearance-deep-ocean .conversation-dock-panel {")
        block = self.css[idx:self.css.index("}", idx)]
        self.assertIn("box-shadow: var(--ocean-glow);", block)
        self.assertNotIn("backdrop-filter", block)

    def test_other_appearance_modes_never_get_backdrop_filter_or_the_ocean_glow(self):
        # The dark/tinted/deep-forest equivalents of the same menu
        # dropdown/popover selectors must never pick up blur or glow -
        # this is a Deep-Ocean-only material, not a generic dark-mode one.
        for mode_class in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            self.assertNotIn(f".workspace-topbar.{mode_class} .workspace-menubar-panel", self.css)

    def test_no_other_appearance_mode_rule_gained_a_stray_backdrop_filter(self):
        # Structural guard: backdrop-filter/--ocean-glow anywhere in the
        # file must always sit inside a rule whose OWN selector line
        # mentions deep-ocean (either appearance-deep-ocean or the
        # pre-existing, unrelated .gateway-shell reference this stage
        # deliberately left untouched).
        for m in re.finditer(r"backdrop-filter: blur\(var\(--ocean-glass-blur\)\)|box-shadow: var\(--ocean-glow\)", self.css):
            selector_start = self.css.rfind("}", 0, m.start())
            rule_start = self.css.rfind("{", selector_start, m.start())
            selector_line = self.css[max(rule_start - 400, 0):rule_start]
            self.assertIn("appearance-deep-ocean", selector_line, self.css[m.start():m.start() + 60])


if __name__ == "__main__":
    unittest.main()
