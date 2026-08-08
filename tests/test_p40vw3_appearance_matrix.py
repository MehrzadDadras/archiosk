"""
CLAUDE-P40-VW3 - Per-Panel Light, Dark, and Tinted Appearance Matrix.

Product-owner walkthrough correction: the Appearance menu used to offer
one checkbox per surface (Lists/Display/Toolbox/Chat), a binary plain-
vs-tinted choice, and Menu (the top bar) was not configurable at all.
This replaces it with a real selection matrix - five surfaces (Menu,
Lists, Display, Toolbox, Chat) x three mutually exclusive modes (Light,
Dark, Tinted) each, using radio semantics (one <input type=radio> group
per row), not checkboxes.

Previous appearance-state model: one localStorage key per surface
(`beehive:appearance:{lists,display,toolbox,chat}`), value exactly
'tinted' or 'plain' (or absent, meaning plain). Menu had no key at all
- it wasn't a configurable surface.

Compatibility mapping (verified in JS source below, since no browser
tool exists in this environment to observe it live): 'tinted' carries
over unchanged (same meaning, still exists). 'plain' or missing maps to
'light' - the new default, which renders identically to the old plain
state (no class added), so no reviewer's prior choice is silently
reinterpreted as something they didn't pick. Menu has no prior key to
migrate and defaults to 'light', the honest choice given it rendered
with no tint/dark treatment at all before this stage.

Dark mode is new this stage: static/css/tokens.css gained a --dark-*
token set (same hue family as the light palette, lightness inverted,
contrast-verified via tools/check_contrast.py - see that file's own
comment), and static/css/main.css gained a shared `.appearance-dark`
rule that redefines the STANDARD token names locally on whichever
surface's own root carries that class - every existing component rule
already written as var(--surface-primary)/var(--text-primary)/etc.
therefore repaints correctly with zero further changes, a scoped-
custom-property mechanism (not a second linked stylesheet, which
could only ever apply page-wide) chosen specifically because Menu/
Lists/Display/Toolbox/Chat must be independently mixed (e.g. Dark
Display with Light Lists and Tinted Toolbox).

No browser/rendering tool exists in this environment - CSS/JS source
assertions verify the structural facts a browser's cascade algorithm
and radio-group semantics would act on; HTML assertions verify
server-rendered markup. Stated honestly rather than skipped, matching
this repo's established convention.
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"
_TOKENS_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"

_SURFACES = ["menu", "lists", "display", "toolbox", "chat"]
# CLAUDE-P40-VW8-QA (Approved Theme Set): these are the UI-reference
# SUFFIXES rendered into each radio's id="appearance-{surface}-{suffix}"
# (light/dark/tinted retained unchanged through two label revisions -
# Dark->Black, Tinted->Midnight Blue - deep-forest is the one genuinely
# new suffix), not the stored mode VALUES (light/black/midnight-blue/
# deep-forest) - see templates/base.html's own (mode_value, mode_label,
# ref_suffix) comment for why these are deliberately different.
_MODES = ["light", "dark", "tinted", "deep-forest"]


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw3_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw3_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="vw3_owner", project_name="Riverside Terminal VW3 Workspace")
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

    def _appearance_html(self, body: str) -> str:
        start = body.index('id="workspace-appearance-menu"')
        end = body.index("</details>", start)
        return body[start:end]


# ---------------------------------------------------------------------------
# Matrix structure: five surfaces, three modes each, real radio semantics.
# ---------------------------------------------------------------------------

class MatrixStructureTests(_BaseTestCase):
    def test_five_surfaces_x_three_modes_all_present(self):
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        for surface in _SURFACES:
            for mode in _MODES:
                self.assertIn(f'id="appearance-{surface}-{mode}"', menu, f"{surface}/{mode}")

    def test_exactly_twentyfour_radio_inputs(self):
        # CLAUDE-P40-VW8-QA added a 6th row ("All") applying one mode to
        # all five surfaces at once (Section 5), and the Approved Theme
        # Set added a 4th mode (Deep Forest) - 5 surfaces x 4 modes (20)
        # + 1 All row x 4 modes (4) = 24.
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        self.assertEqual(menu.count('type="radio"'), 24)

    def test_each_surface_is_its_own_radio_group(self):
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        for surface in _SURFACES:
            self.assertEqual(menu.count(f'name="appearance-{surface}"'), 4, surface)

    def test_no_checkboxes_remain(self):
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        self.assertNotIn('type="checkbox"', menu)

    def test_menu_row_present_and_ordered_first(self):
        # CLAUDE-P40-VW8-QA's new "All" row sits above the five real
        # surfaces (Section 5 - a universal control, not a sixth
        # surface) - "Menu" is still the first SURFACE row, just no
        # longer the first scope="row" cell in the whole table.
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        row_scopes = [m.start() for m in re.finditer(r'scope="row"', menu)]
        self.assertGreaterEqual(len(row_scopes), 2)
        self.assertIn(">All<", menu[row_scopes[0]:row_scopes[0] + 30])
        self.assertIn(">Menu<", menu[row_scopes[1]:row_scopes[1] + 30])

    def test_rows_ordered_menu_lists_display_toolbox_chat(self):
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        positions = [menu.index(f'id="appearance-{s}-light"') for s in _SURFACES]
        self.assertEqual(positions, sorted(positions))

    def test_all_twentyfour_options_have_accessible_labels(self):
        # CLAUDE-P40-VW8-QA: 24 now - see
        # test_exactly_twentyfour_radio_inputs's own comment.
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        radio_aria_labels = re.findall(r'<input type="radio"[^>]*aria-label="[^"]+"', menu)
        self.assertEqual(len(radio_aria_labels), 24)

    def test_column_headers_light_black_midnight_blue_deep_forest(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): Dark relabeled Black
        # (a brief interim "Graphite" was itself corrected back to
        # Black), Tinted relabeled Midnight Blue, Deep Forest added.
        # CLAUDE-POSTCAMEL-P02-ST1: Light relabeled Titanium (mode_value/
        # ref_suffix stay 'light' - see base.html's own comment).
        client = self._client_as("vw3_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._appearance_html(body)
        self.assertIn(">Titanium<", menu)
        self.assertIn(">Black<", menu)
        self.assertIn(">Midnight Blue<", menu)
        self.assertIn(">Deep Forest<", menu)
        self.assertNotIn(">Dark<", menu)
        self.assertNotIn(">Tinted<", menu)
        self.assertNotIn(">Graphite<", menu)


# ---------------------------------------------------------------------------
# Preservation: existing gating, other menus, and menu-only-in-a-workspace
# behaviour untouched.
# ---------------------------------------------------------------------------

class PreservationTests(_BaseTestCase):
    def test_appearance_menu_still_only_within_a_workspace(self):
        client = self._client_as("vw3_owner", 1)
        workspace_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-appearance-menu"', workspace_body)
        for url in ("/", "/projects", "/upload"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn('id="workspace-appearance-menu"', body, url)

    def test_menu_surface_target_element_present_even_outside_a_workspace(self):
        # The Menu (topbar) surface itself renders on every authenticated
        # page (unlike the appearance control that sets it, which is
        # workspace-gated per the test above) - its stored preference
        # must still apply everywhere, not just inside a workspace.
        client = self._client_as("vw3_owner", 1)
        body = client.get("/").get_data(as_text=True)
        self.assertIn('class="workspace-topbar"', body)


# ---------------------------------------------------------------------------
# CSS: dark tokens exist, are contrast-verified, and are scoped per
# surface via .appearance-dark, not a page-wide swap.
# ---------------------------------------------------------------------------

class DarkTokenCssTests(unittest.TestCase):
    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_dark_neutral_tokens_defined(self):
        for name in (
            "--dark-canvas", "--dark-surface-primary", "--dark-surface-secondary",
            "--dark-surface-hover", "--dark-surface-selected", "--dark-border",
            "--dark-border-strong", "--dark-text-primary", "--dark-text-secondary",
            "--dark-text-metadata", "--dark-text-disabled",
        ):
            self.assertRegex(self.tokens_css, re.escape(name) + r"\s*:\s*#[0-9a-fA-F]{6}\s*;", name)

    def test_dark_accent_tokens_defined_for_all_seven_semantic_colors(self):
        for name in (
            "seal-red", "machine-blue", "highlight-orange", "accepted-green",
            "attention-amber", "failure-red", "risk-red",
        ):
            self.assertIn(f"--dark-{name}:", self.tokens_css, name)
            self.assertIn(f"--dark-{name}-tint:", self.tokens_css, name)

    def test_dark_palette_passes_the_repos_own_contrast_checker(self):
        # Real verification, not a restated assertion: builds a scratch
        # tokens file substituting the dark hexes into the STANDARD
        # token names check_contrast.py's REQUIRED_PAIRINGS actually
        # checks, and runs the real script against it (same technique
        # CLAUDE.md requires for any color change).
        import subprocess
        import sys as _sys
        import tempfile as _tempfile

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

        with _tempfile.TemporaryDirectory() as td:
            scratch = Path(td) / "dark_scratch.css"
            scratch.write_text("\n".join(lines), encoding="utf-8")
            checker = Path(__file__).resolve().parent.parent / "tools" / "check_contrast.py"
            result = subprocess.run(
                [_sys.executable, str(checker), str(scratch)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("ALL PAIRINGS PASS", result.stdout)

    def test_appearance_dark_rule_scopes_all_five_surfaces_not_root(self):
        # CLAUDE-P40-EYE1: the Toolbox surface's own painted root moved
        # from .workspace-pane-toolbox to .workspace-right-column (the
        # new full-height column containing Toolbox AND Eye) - Eye needs
        # the identical theme redefinition Toolbox already had, via
        # ordinary CSS custom-property inheritance from one shared
        # ancestor, so the class now lives one level up.
        rule_match = re.search(r"\.workspace-topbar\.appearance-dark,[^{]*\{[^}]*\}", self.main_css, re.S)
        self.assertIsNotNone(rule_match, "no combined .appearance-dark rule found")
        rule = rule_match.group(0)
        for selector in (
            ".workspace-topbar.appearance-dark", ".launcher-panel.appearance-dark",
            ".app-main.appearance-dark", ".workspace-right-column.appearance-dark",
            ".chat-region.appearance-dark",
        ):
            self.assertIn(selector, rule, selector)
        # Never redefined at :root - that would leak dark mode to every
        # surface at once, defeating independent per-surface mixing.
        self.assertNotRegex(self.main_css, r":root\s*\{[^}]*--dark-canvas")

    def test_appearance_dark_rule_redefines_the_standard_token_names(self):
        rule_match = re.search(r"\.workspace-topbar\.appearance-dark,[^{]*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule_match)
        body = rule_match.group(1)
        for standard_token in ("--canvas", "--surface-primary", "--text-primary", "--border", "--seal-red"):
            self.assertIn(f"{standard_token}: var(--dark-", body, standard_token)

    def test_menu_tinted_rule_added_this_stage(self):
        # SUPERSEDED (CLAUDE-P40-VW6): the single-property rule this test
        # originally checked for was VW3's own defect, not the fix - it
        # swapped only .workspace-topbar's OWN background to
        # --surface-secondary (Limestone/beige) without redefining the
        # surface's token scope, so nothing else inside Menu actually
        # tinted. VW6 replaced it with a full token-scope redefinition
        # (the same combined selector .appearance-dark already used) -
        # checked here as membership in that combined selector list,
        # using the new dedicated --tint-* family, not --surface-secondary.
        self.assertIn(".workspace-topbar.appearance-tinted,", self.main_css)
        rule_match = re.search(r"\.workspace-topbar\.appearance-tinted,[^{]*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule_match, "no combined .appearance-tinted rule found")
        self.assertIn("--surface-primary: var(--tint-surface-primary);", rule_match.group(1))

    def test_display_and_chat_inner_surfaces_have_dark_companions(self):
        self.assertIn(".app-main.appearance-dark .workspace-pane-display", self.main_css)
        self.assertIn(".chat-region.appearance-dark", self.main_css)
        self.assertIn(".chat-region.appearance-dark .conversation-dock-panel", self.main_css)


# ---------------------------------------------------------------------------
# JS: independent per-row wiring, no cross-surface bleed, compatibility
# mapping, and persistence across the existing localStorage boundary.
# ---------------------------------------------------------------------------

class AppearanceJsWiringTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def _appearance_script(self) -> str:
        start = self.html.index("CLAUDE-P40-E3A, Section 10; CLAUDE-P40-VW3: Appearance menu")
        end = self.html.index("</script>", start)
        return self.html[start:end]

    def test_all_five_surfaces_targeted(self):
        js = self._appearance_script()
        for surface in _SURFACES:
            self.assertIn(f"{surface}: document.querySelector(", js, surface)

    def test_menu_target_is_the_topbar(self):
        js = self._appearance_script()
        self.assertIn("menu: document.querySelector('.workspace-topbar')", js)

    def test_compat_mapping_legacy_and_current_values_resolve_correctly(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): the resolver moved to
        # window.__resolveStoredAppearanceMode, defined in an earlier
        # script block (right after .chat-region - see that block's own
        # comment for why) so this block now just references it rather
        # than declaring it inline. Default fallback is 'black' now, not
        # 'light' (Black is the new default for a missing/invalid
        # preference).
        self.assertIn("window.__resolveStoredAppearanceMode = function (stored)", self.html)
        self.assertIn("if (stored === 'dark' || stored === 'graphite') return 'black';", self.html)
        self.assertIn("if (stored === 'tinted') return 'midnight-blue';", self.html)
        self.assertIn("return 'black';", self.html)
        js = self._appearance_script()
        self.assertIn("var resolveStoredMode = window.__resolveStoredAppearanceMode;", js)

    def test_apply_mode_toggles_exactly_the_three_mutually_exclusive_classes(self):
        # A 4th theme (Deep Forest) added a 3rd toggled class - "exactly
        # two" became "exactly three," still mutually exclusive (each
        # condition checks a different mode value, so at most one is
        # ever true).
        self.assertIn("window.__applyStoredAppearanceMode = function (el, mode)", self.html)
        self.assertIn("el.classList.toggle('appearance-dark', mode === 'black');", self.html)
        self.assertIn("el.classList.toggle('appearance-tinted', mode === 'midnight-blue');", self.html)
        self.assertIn("el.classList.toggle('appearance-deep-forest', mode === 'deep-forest');", self.html)
        js = self._appearance_script()
        self.assertIn("var applyMode = window.__applyStoredAppearanceMode;", js)

    def test_each_surface_wired_independently_by_its_own_data_attribute(self):
        js = self._appearance_script()
        self.assertIn('document.querySelectorAll(\'[data-appearance-target="\' + key + \'"]\')', js)

    def test_change_handler_persists_to_the_same_per_surface_storage_key(self):
        # CLAUDE-P40-VW8-QA refactored the per-surface apply/persist
        # logic into one shared setSurfaceMode() function (so the new
        # All row and each individual radio call the same code path) -
        # the storage key FORMAT this test protects is unchanged.
        js = self._appearance_script()
        self.assertIn("try { window.localStorage.setItem('beehive:appearance:' + key, mode); } catch (e) { /* ignore */ }", js)
        self.assertIn("function setSurfaceMode(key, mode, persist)", js)

    def test_radio_checked_state_set_from_resolved_mode_not_hardcoded(self):
        js = self._appearance_script()
        self.assertIn("radio.checked = (radio.getAttribute('data-appearance-mode') === mode);", js)


if __name__ == "__main__":
    unittest.main()
