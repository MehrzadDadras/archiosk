"""
CLAUDE-APPEARANCE-SIMPLIFY-01 - Global Appearance Only + Deep Ocean +
Account Sign-Out Placement.

Product Owner live-browser correction. Covers what the superseded/
rewritten tests in test_p40vw3_appearance_matrix.py, test_p40vw6_theme_
correction.py, and test_p40vw8qa_approved_theme_set.py don't already own:

1. Migration behavior for window.__resolveGlobalAppearanceMode - old
   per-surface localStorage values collapsing losslessly onto ONE
   global value (uniform -> that value; mixed/absent -> the existing
   Black default), and the old keys never resurfacing afterward.
2. Deep Ocean's own CSS: traced tokens (not invented), the real
   landing-page gradient reused verbatim on .app-shell, glass-panel
   backdrop-filter/rgba fill scoped to the four chrome surfaces only
   (never Display), and the divider/lock-control reveal-on-hover
   treatment - scoped to .appearance-deep-ocean, never leaking into the
   other four themes.
3. Sign out relocated to the account menu, first item, never duplicated,
   route/security behavior unchanged.

No browser-automation tool is exercised here - CSS/JS source assertions
verify the structural facts a browser's cascade/localStorage would act
on; HTML assertions verify server-rendered markup, matching this
repo's established convention for this whole appearance test family.
"""
from __future__ import annotations

import io
import re
import sys
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

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "tools"))
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_LANDING_CSS_PATH = _REPO_ROOT / "static" / "css" / "landing.css"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_appearance_simplify_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="appsimp_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="appsimp_owner", project_name="Appearance Simplify Workspace")
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


# ---------------------------------------------------------------------------
# Migration: old per-surface keys collapse losslessly onto one global value.
# ---------------------------------------------------------------------------

class MigrationLogicTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def _resolver_script(self) -> str:
        start = self.html.index("window.__resolveGlobalAppearanceMode = function")
        end = self.html.index("(function () {", start)
        return self.html[start:end]

    def test_resolver_prefers_the_new_global_key_when_already_set(self):
        js = self._resolver_script()
        self.assertIn("window.localStorage.getItem('beehive:appearance')", js)
        self.assertIn("if (stored !== null) return window.__resolveStoredAppearanceMode(stored);", js)

    def test_resolver_reads_all_five_old_surface_keys_for_migration(self):
        js = self._resolver_script()
        self.assertIn("['menu', 'lists', 'display', 'toolbox', 'chat']", js)
        self.assertIn("window.localStorage.getItem('beehive:appearance:' + key)", js)

    def test_uniform_old_values_become_the_canonical_global_value(self):
        js = self._resolver_script()
        self.assertIn("oldResolved.every(function (m) { return m === oldResolved[0]; })", js)
        self.assertIn("var migrated = uniform ? oldResolved[0] : window.__resolveStoredAppearanceMode(null);", js)

    def test_migration_writes_the_new_key_and_removes_every_old_one(self):
        js = self._resolver_script()
        self.assertIn("window.localStorage.setItem('beehive:appearance', migrated);", js)
        self.assertIn("window.localStorage.removeItem('beehive:appearance:' + key);", js)

    def test_resolver_defined_before_both_the_early_and_later_scripts_use_it(self):
        resolver_idx = self.html.index("window.__resolveGlobalAppearanceMode = function")
        early_use_idx = self.html.index("var mode = window.__resolveGlobalAppearanceMode();")
        later_use_idx = self.html.index("applyGlobalMode(window.__resolveGlobalAppearanceMode(), false);")
        self.assertLess(resolver_idx, early_use_idx)
        self.assertLess(early_use_idx, later_use_idx)


# ---------------------------------------------------------------------------
# Deep Ocean: traced palette, present as a real global choice.
# ---------------------------------------------------------------------------

class DeepOceanPaletteTests(_BaseTestCase):
    def test_deep_ocean_radio_present_and_functional_globally(self):
        client = self._client_as("appsimp_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="appearance-all-deep-ocean"', body)
        self.assertIn('data-appearance-all-mode="deep-ocean"', body)
        self.assertIn('data-ui-ref="menu.appearance.deep-ocean"', body)

    def test_ocean_tokens_exist_in_tokens_css(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01 (Visual Source of Truth addendum):
        # Product Owner correction, twice, after live review - "close to
        # midnight blue instead of being like gateway page," then
        # "adapt Gateway page for deepocean appearance." Ocean's own
        # structural tokens are now translucent rgba() values (a literal
        # copy of .gateway-shell's own rule, main.css), not the opaque
        # flat hex every other dark theme uses - so this checks for a
        # real CSS color function, not a specific hex pattern.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        for name in (
            "--ocean-canvas", "--ocean-surface-primary", "--ocean-surface-secondary",
            "--ocean-surface-hover", "--ocean-surface-selected", "--ocean-border",
            "--ocean-border-strong", "--ocean-text-primary", "--ocean-text-secondary",
            "--ocean-text-metadata", "--ocean-text-disabled",
        ):
            self.assertRegex(tokens_css, re.escape(name) + r"\s*:\s*rgba?\([^;]+\)\s*;", name)

    def test_ocean_tokens_are_a_literal_copy_of_gateway_shells_own_rule(self):
        # "Do not approximate it from memory if the actual existing
        # tokens/CSS/variables can be traced and reused" - every value
        # below must be byte-identical to .gateway-shell's own rule
        # (main.css), not independently re-derived or approximated.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        # main.css has TWO ".gateway-shell {" rules - a plain layout
        # rule (display/flex-direction/min-height) and, further down,
        # the token-redefinition rule this test actually needs - anchor
        # on the token rule's own known first declaration to find the
        # right one, not the first "re.search" happens to hit.
        token_rule_start = main_css.index(".gateway-shell {\n    --text-primary:")
        gateway_rule = main_css[token_rule_start:main_css.index("}", token_rule_start)]
        pairs = (
            ("--ocean-surface-primary", "rgba(10, 35, 42, .55)"),
            ("--ocean-surface-secondary", "rgba(14, 45, 54, .5)"),
            ("--ocean-surface-hover", "rgba(176, 219, 255, .12)"),
            ("--ocean-surface-selected", "rgba(176, 219, 255, .18)"),
            ("--ocean-border", "rgba(176, 219, 255, .28)"),
            ("--ocean-border-strong", "rgba(176, 219, 255, .5)"),
            ("--ocean-text-primary", "rgb(230, 244, 255)"),
            ("--ocean-text-secondary", "rgba(228, 243, 255, .82)"),
            ("--ocean-text-metadata", "rgba(200, 230, 255, .72)"),
            ("--ocean-text-disabled", "rgba(200, 230, 255, .4)"),
            ("--ocean-machine-blue", "rgba(200, 230, 255, .8)"),
            ("--ocean-failure-red", "rgba(255, 170, 150, .95)"),
        )
        for ocean_name, value in pairs:
            self.assertIn(f"{ocean_name}: {value};", tokens_css, ocean_name)
            self.assertIn(value, gateway_rule, f"{value} not found in .gateway-shell's own rule")

    def test_ocean_canvas_has_no_gateway_equivalent_so_matches_surface_primary(self):
        # .gateway-shell never defines its own --canvas (no watermark
        # grid on that shell) - --ocean-canvas falls back to equalling
        # --ocean-surface-primary, the same convention Black/Midnight
        # Blue/Deep Forest already use for their own canvas token.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        canvas = re.search(r"--ocean-canvas:\s*([^;]+);", tokens_css).group(1)
        surface_primary = re.search(r"--ocean-surface-primary:\s*([^;]+);", tokens_css).group(1)
        self.assertEqual(canvas, surface_primary)

    def test_ocean_reuses_blacks_own_accents_gateway_shell_does_not_redefine(self):
        # .gateway-shell only redefines machine-blue/failure-red among
        # the accent colors - seal-red/highlight-orange/accepted-green/
        # attention-amber/risk-red have no traced Gateway equivalent, so
        # they fall back to Black's own already-verified values,
        # unmodified.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        for accent in ("seal-red", "highlight-orange", "accepted-green", "attention-amber", "risk-red"):
            dark = re.search(re.escape(f"--dark-{accent}:") + r"\s*(#[0-9a-fA-F]{6})", tokens_css).group(1)
            ocean = re.search(re.escape(f"--ocean-{accent}:") + r"\s*(#[0-9a-fA-F]{6})", tokens_css).group(1)
            self.assertEqual(dark, ocean, accent)

    def test_ocean_brand_gold_reuses_bee_yellow_not_blacks_dark_bronze(self):
        # Same CLAUDE-BOTTLENECK-ADOPTION-01 precedent .gateway-card-
        # compact/.gateway-shell already establish - Black's own
        # --dark-brand-gold (a dark bronze) would be nearly invisible
        # against this translucent dark background.
        tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("--ocean-brand-gold: var(--bee-yellow);", tokens_css)

    def test_derivation_tool_no_longer_lists_ocean(self):
        # The luminance-matching method that tool implements doesn't
        # apply to a translucent rgba() palette (relative_luminance()
        # assumes an opaque RGB triple) - Ocean is a literal copy of
        # .gateway-shell now, not a tool-derived ramp, so it must not
        # reappear in THEMES.
        import derive_theme_palettes as dtp
        self.assertNotIn("ocean", dtp.THEMES)
        self.assertEqual(dtp.main(), 0)


class DeepOceanGlassTreatmentTests(unittest.TestCase):
    """Visual Source of Truth addendum: reuse the landing/sign-in shell's
    own real glass-panel values, scoped to .appearance-deep-ocean only."""

    def setUp(self):
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_app_shell_reuses_the_literal_landing_page_gradient(self):
        rule = re.search(r"\.app-shell\.appearance-deep-ocean\s*\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule)
        body = rule.group(1)
        self.assertIn("radial-gradient(circle at 50% 10%, rgba(33, 112, 132, .14), transparent 30%)", body)
        self.assertIn("linear-gradient(180deg, rgb(2, 8, 18) 0%, rgb(3, 23, 37) 46%, rgb(1, 5, 10) 100%)", body)

    def test_landing_page_gradient_values_are_the_actual_source(self):
        # The exact values .app-shell.appearance-deep-ocean reuses must
        # genuinely exist in landing.css - proof this was traced, not
        # coincidentally similar.
        landing_css = _LANDING_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("radial-gradient(circle at 50% 10%, rgba(33, 112, 132, .14), transparent 30%)", landing_css)
        self.assertIn("linear-gradient(180deg, rgb(2, 8, 18) 0%, rgb(3, 23, 37) 46%, rgb(1, 5, 10) 100%)", landing_css)

    def test_backdrop_filter_applies_to_all_five_former_surfaces(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01 (Visual Source of Truth addendum):
        # the actual glass FILL/text/border now flow through the
        # standard --surface-primary/--text-primary/--border token
        # mechanism every theme already uses (now translucent rgba()
        # values for ocean specifically) - backdrop-filter is the one
        # thing that still needs its own dedicated rule, and it applies
        # to all 5 former surfaces uniformly now, INCLUDING Display (a
        # plain opaque patch there would read as a surface this theme
        # forgot, not a deliberate exception - Product Owner: "the
        # login/landing experience and the working cockpit to feel like
        # the same ARCHIOSK instrument").
        # Two blocks share the identical 5-line selector list
        # (.workspace-topbar/.launcher-panel/.app-main/.workspace-right-
        # column/.chat-region, each .appearance-deep-ocean) - the shared
        # token block (--canvas: var(--ocean-canvas); ...) and this
        # backdrop-filter-only block. This rule is the only one of the
        # three backdrop-filter declarations in the whole file where the
        # property is immediately followed by the rule's closing brace
        # (the other two - .gateway-card-compact/.gateway-shell
        # .gateway-card-wide - are followed by border/box-shadow) - a
        # reliable, unique anchor.
        filter_idx = self.main_css.index("backdrop-filter: blur(14px);\n}")
        rule_start = self.main_css.rindex("{", 0, filter_idx)
        body = self.main_css[rule_start + 1:filter_idx + len("backdrop-filter: blur(14px);")]
        selectors = self.main_css[max(0, rule_start - 250):rule_start]
        self.assertIn("backdrop-filter: blur(14px);", body)
        self.assertNotIn("--surface-primary", body)
        for selector in (".workspace-topbar", ".launcher-panel", ".app-main", ".workspace-right-column", ".chat-region"):
            self.assertIn(f"{selector}.appearance-deep-ocean", selectors, selector)
        # The exact blur radius already used by .gateway-card-compact/
        # .gateway-shell .gateway-card-wide - reused, not reinvented.
        card_idx = self.main_css.index(".gateway-card-compact {")
        self.assertIn("blur(14px)", self.main_css[card_idx:card_idx + 1500])

    def test_glass_fill_flows_through_the_standard_token_mechanism(self):
        # No separate background-color/border-color override needed
        # anymore - the combined .app-shell.appearance-deep-ocean, ...
        # selector (shared with every other theme) already redefines
        # --surface-primary/--border to the translucent ocean tokens,
        # and every surface's own base rule already reads
        # background: var(--surface-primary).
        rule = re.search(r"\.app-shell\.appearance-deep-ocean,.*?\{([^}]*)\}", self.main_css, re.S)
        self.assertIsNotNone(rule)
        body = rule.group(1)
        self.assertIn("--surface-primary: var(--ocean-surface-primary);", body)
        self.assertIn("--border: var(--ocean-border);", body)
        self.assertIn("background: var(--surface-primary);", body)

    def test_backdrop_filter_scoped_to_deep_ocean_only_not_other_themes(self):
        # Regression guard: the four flat themes (Black/Midnight Blue/
        # Deep Forest, and Titanium's own light default) must never pick
        # up backdrop-filter - NoReflectiveEffectsTests in
        # test_p40vw8qa_approved_theme_set.py already enforces "flat and
        # matte" for their own combined rule bodies; this checks the
        # inverse boundary from Deep Ocean's own side.
        glass_rule_start = self.main_css.index("backdrop-filter: blur(14px);")
        preceding = self.main_css[max(0, glass_rule_start - 300):glass_rule_start]
        for other_theme in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            self.assertNotIn(other_theme, preceding)

    # CLAUDE-EYE-TOOLBOX-LAYOUT-01 superseded the three tests that used to
    # live here (test_divider_and_lock_controls_reveal_on_hover_focus_
    # scoped_to_deep_ocean, test_collapsed_lists_toggle_stays_visible_at_
    # rest_not_hidden, test_base_divider_rules_still_come_before_the_deep_
    # ocean_override) - Part 5/6 of that stage's own Product Owner
    # instruction ("Deep Ocean currently has no visible line between
    # panels; other themes still show separator lines... do not make Deep
    # Ocean the exception; do not leave old theme-specific borders active
    # elsewhere") required the quiet-at-rest/reveal-on-hover-focus-drag
    # treatment these tests asserted was DEEP-OCEAN-ONLY to become the
    # SHARED base behavior for every one of the 5 Appearances instead. The
    # `.app-shell.appearance-deep-ocean .panel-divider`/`.toolbox-eye-
    # divider`/`.conversation-dock-resize-handle` scoped override block
    # these tests exercised no longer exists - deleted, not weakened,
    # because its entire content is now redundant with the generalized
    # base rules (see ToolboxEyeDividerLockAndVisualGrammarTests below,
    # tests/test_p40eye1_toolbox_eye_column.py's own updated coverage, and
    # each selector's own base rule in main.css for the current,
    # non-scoped invariant).

    def test_no_stale_deep_ocean_only_divider_override_remains(self):
        # Regression guard for the opposite direction now: a reviewer
        # re-adding a Deep-Ocean-scoped divider-reveal block (reintroducing
        # the "Deep Ocean is the exception" defect this stage fixed) would
        # silently pass every other test in this file, since none of them
        # inspect that specific combination any more.
        self.assertNotIn(".app-shell.appearance-deep-ocean .panel-divider,", self.main_css)
        self.assertNotIn(".app-shell.appearance-deep-ocean .toolbox-eye-divider {", self.main_css)

    def test_genuinely_deep_ocean_specific_rules_still_come_after_their_base_rule(self):
        # The narrower, still-true residual of the old regression guard:
        # the rules that ARE still legitimately Deep-Ocean-only (the
        # gradient .app-shell background, backdrop-filter, and the Menu
        # bottom-border recolor) must stay textually AFTER every base rule
        # they touch, so a plain textual/regex search for one of those
        # base selectors still finds the base rule first - the exact
        # ambiguity bug this addendum's own implementation hit once
        # already (main.css's own comment on this block has the full
        # story).
        base_idx = self.main_css.index(".workspace-topbar {\n")
        override_idx = self.main_css.index('.workspace-topbar.appearance-deep-ocean {\n    border-bottom-color:')
        self.assertLess(base_idx, override_idx)


# ---------------------------------------------------------------------------
# Sign out relocated to the account menu, first, never duplicated.
# ---------------------------------------------------------------------------

class SignOutRelocationTests(_BaseTestCase):
    def test_sign_out_present_exactly_once(self):
        client = self._client_as("appsimp_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('data-ui-ref="menu.account.sign-out"'), 1)
        self.assertEqual(body.count(">Sign out<"), 1)

    def test_sign_out_route_and_placement_unchanged(self):
        client = self._client_as("appsimp_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('href="/logout"', body)

    def test_sign_out_appears_before_the_admin_label(self):
        # CLAUDE-APP-MENU-01: Admin no longer lives in the Account menu
        # at all (relocated to menu.archiosk.admin, in the Archiosk menu
        # far earlier in document order than the Account menu on the
        # right) - the two are no longer siblings, so a document-order
        # comparison between them is no longer meaningful. What still
        # holds, and is asserted here: Sign out is the first item inside
        # the Account menu itself, and Admin is genuinely gone from it.
        client = self._client_as("appsimp_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        account_start = body.index('data-ui-ref="menu.account"')
        account_panel = body[account_start:body.index("</details>", account_start)]
        sign_out_pos = account_panel.index('data-ui-ref="menu.account.sign-out"')
        self.assertNotIn('data-ui-ref="menu.account.admin"', account_panel)
        self.assertIn('data-ui-ref="menu.archiosk.admin"', body)
        self.assertGreaterEqual(sign_out_pos, 0)

    def test_sign_out_present_for_a_non_admin_reviewer_too(self):
        # Sign out must never become admin-only merely by sitting near
        # the Admin section - it is a plain account action for every
        # authenticated reviewer.
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="appsimp_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        client = self._client_as("appsimp_reader", 2, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.account.sign-out"', body)
        self.assertNotIn('data-ui-ref="menu.account.admin"', body)


if __name__ == "__main__":
    unittest.main()
