"""
CLAUDE-P40-BRAND1 - Top-Left ARCHIOSK Brand Treatment.

No prior mark/medallion/icon of any kind existed anywhere in this
repository before this stage (grounded by direct search - no `.svg`
file, no inline `<svg>` beyond annotation-toolbar glyphs, no favicon).
The mark itself went through one correction: the first version used
two quadratic-Bezier parabola legs; a product-owner correction replaced
it outright with a straight-line-only construction (curves are now an
explicit prohibited addition) - two mirrored, asymmetrical open angles
(a short rising arm, a longer leaning leg) whose inner vertices
deliberately do not touch (the "bottleneck"), plus one small filled dot
on the centreline just below the gap (the "grain" that passed through).
Built as a single shared Jinja macro (`archiosk_mark` in
`templates/_macros.html`), wired into the existing top-left `menu.brand`
link (`templates/base.html`) alongside an enlarged "Archiosk" wordmark,
while leaving `menu.context`'s own breadcrumb untouched (already within
the suggested secondary-text range). Colored via a `--brand-gold` token
family (light + one shared dark value reused across Black/Midnight
Blue/Deep Forest, the same convention already established for
`--tabcolor-*`), verified with `tools/check_contrast.py` at the
STRICTER 4.5:1 normal-text floor (this is small always-visible identity
text, not an occasional badge) - untouched by the geometry correction,
since only the SVG path data changed, not the color values.

No real browser tool exists in this environment - coverage here is
macro/template/CSS source and rendered-HTML structure, the same
practical ceiling this repo's prior stages have already established.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_APP_MENU_HTML_PATH = _REPO_ROOT / "templates" / "_app_menu.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_CHECK_CONTRAST_PATH = _REPO_ROOT / "tools" / "check_contrast.py"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(r"(?<![\w-])" + re.escape(selector) + r"(?![\w\-\":])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


class MarkRetirementTests(unittest.TestCase):
    """CLAUDE-LETTERMARK-PURGE-01 - the mark this file was written to guard
    no longer exists.

    What stood here: RepositoryGroundingTests (the path data appears exactly
    once, nowhere copied) and MacroGeometryTests (two straight-line paths, no
    curves, no crossbar, mirrored halves, a bottleneck gap that does not close,
    a filled dot below it, stroke ~5 units on a 64 viewBox). Fifteen tests, all
    asserting a shape.

    They were not weakened and they did not start failing. Their subject was
    retired by the Product Owner on 2026-08-30: at the sizes the mark actually
    shipped at - 16px beside the app menu, 36px on the sign-in card - it read
    as a bowtie next to the word "Archiosk", and the acceptance bar it had been
    held to was that it "must not collapse into an ambiguous X". That bar was
    met at 512px and not where it mattered.

    Deleting the file would have left nothing watching the space. So the
    geometry assertions are replaced by the inverse invariant: the mark stays
    gone, and it stays gone everywhere, including in CSS that would style a
    reintroduced one. Everything below this class - the topbar wordmark, its
    token scoping, and the contrast checks - is untouched and still governs.
    """

    def setUp(self):
        self.macros = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_the_macro_is_gone(self):
        self.assertNotIn("{% macro archiosk_mark", self.macros)

    def test_no_template_still_calls_it(self):
        templates = _REPO_ROOT / "templates"
        for path in templates.rglob("*.html"):
            body = re.sub(r"\{#.*?#\}", "", path.read_text(encoding="utf-8"), flags=re.S)
            self.assertNotIn("archiosk_mark(", body, str(path))

    def test_the_retired_path_data_appears_nowhere(self):
        # The mark's own geometry, verbatim. A reintroduction that copied the
        # old shape under a new name would still be the same bowtie.
        for needle in ("M12 8 L21 30 L7 58", "M52 8 L43 30 L57 58"):
            for path in (_REPO_ROOT / "templates").rglob("*.html"):
                self.assertNotIn(needle, path.read_text(encoding="utf-8"), str(path))

    def test_no_css_remains_to_style_a_reintroduced_mark(self):
        # Orphan rules are how a retired element quietly comes back looking
        # correct - the markup returns and the styling is already waiting.
        for selector in (".archiosk-mark", ".workspace-app-mark", ".gateway-logo"):
            self.assertNotIn(selector + " ", self.css)
            self.assertNotIn(selector + "{", self.css)
            self.assertNotIn(selector + " {", self.css)

    def test_the_wordmark_it_sat_beside_is_untouched(self):
        # The purge removed a symbol, not the brand. This is the assertion
        # that would catch an over-broad revert.
        self.assertIn(".workspace-topbar-brand", self.css)
        for path in ("auth_shell.html", "gateway_base.html"):
            body = (_REPO_ROOT / "templates" / path).read_text(encoding="utf-8")
            self.assertIn("<h1>Archiosk</h1>", body, path)


class HeaderMarkupTests(unittest.TestCase):
    """CLAUDE-APP-MENU-01 (Product Owner, explicit): "Archiosk is not a
    separate logo... render using the same font/size/weight/alignment/
    interaction as the neighboring menu items [File/Edit/View/...]." This
    retires CLAUDE-P40-BRAND1's own icon+enlarged-wordmark single-link
    treatment for base.html's authenticated topbar specifically - the
    mark/macro/gateway_shell.html's own separate pre-authentication brand
    treatment are completely untouched (see RepositoryGroundingTests/
    MacroGeometryTests above, still green - only THIS class's own base.html
    assertions changed). "Archiosk" is now the first entry in the new
    application menu bar (.workspace-menubar, data-ui-ref="menu.archiosk"),
    styled identically to File/Edit/View/etc. via the shared
    .workspace-topbar-btn class those already used - not a new rule of its
    own. Home-navigation (the former data-ui-ref="menu.brand" link) still
    exists, unchanged in behavior (same href, same aria-label) - just
    relocated inside the Archiosk menu's own panel as its first item
    (data-ui-ref="menu.archiosk.home"), since "Archiosk" itself is now a
    menu trigger, not a navigable link.

    CLAUDE-ARCHIOSK-IDENTITY-ACTIVITY-INDICATOR-01 (Product Owner,
    explicit) reintroduced archiosk_mark() into this same authenticated
    topbar afterward - but as .workspace-app-mark, a small, separate,
    stationary identity element sitting BEFORE the menu bar, decorative
    and non-interactive. This does not contradict CLAUDE-APP-MENU-01's
    own invariant above: the Archiosk MENU ITEM still carries no mark of
    its own (still plain .workspace-topbar-btn text, still no href on
    the mark, still never merged into the menu trigger's own summary) -
    only the narrower "the macro is never called anywhere in this
    topbar" premise changed, deliberately."""

    def setUp(self):
        self.source = _BASE_HTML_PATH.read_text(encoding="utf-8")
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the
        # Archiosk menu's own markup (menu.archiosk, menu.archiosk.home)
        # moved out of base.html's own source into the shared
        # templates/_app_menu.html partial ({% include %}d by base.html
        # AND gateway_shell.html) - assertions about that markup read
        # this file now, not base.html directly.
        self.app_menu_source = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_macros_imported(self):
        self.assertIn('{% import "_macros.html" as macros %}', self.source)

    def test_archiosk_menu_summary_uses_the_same_class_as_its_neighbors(self):
        idx = self.app_menu_source.index('data-ui-ref="menu.archiosk"')
        block = self.app_menu_source[idx:self.app_menu_source.index("</details>", idx)]
        summary_tag = block[block.index("<summary"):block.index(">", block.index("<summary")) + 1]
        self.assertIn('class="workspace-topbar-btn"', summary_tag)
        # No mark, no enlarged/bold wordmark class of its own.
        self.assertNotIn("archiosk_mark(", summary_tag)
        self.assertNotIn("workspace-topbar-brand-text", summary_tag)

    def test_the_menu_item_carries_no_mark_and_no_brand_link(self):
        # This file's original invariant was that "Archiosk" the MENU ITEM
        # carries no mark or enlarged-wordmark of its own.
        # CLAUDE-ARCHIOSK-IDENTITY-ACTIVITY-INDICATOR-01 later reintroduced the
        # mark BESIDE the menu (never inside it), and this test was widened to
        # allow that. CLAUDE-LETTERMARK-PURGE-01 retired the mark entirely, so
        # the assertion returns to its original, stricter form: the mark is not
        # in the menu item, and it is not beside it either.
        self.assertNotIn("archiosk_mark(", self.app_menu_source)
        self.assertNotIn('class="workspace-app-mark"', self.app_menu_source)
        self.assertNotIn('class="workspace-topbar-brand"', self.app_menu_source)
        archiosk_menu_idx = self.app_menu_source.index('data-ui-ref="menu.archiosk"')
        summary_start = self.app_menu_source.index("<summary", archiosk_menu_idx)
        summary_end = self.app_menu_source.index("</summary>", summary_start)
        self.assertNotIn("<svg", self.app_menu_source[summary_start:summary_end])

    def test_home_navigation_relocated_not_removed(self):
        idx = self.app_menu_source.index('data-ui-ref="menu.archiosk.home"')
        tag = self.app_menu_source[self.app_menu_source.rindex("<a", 0, idx):self.app_menu_source.index(">", idx) + 1]
        self.assertIn('aria-label="Archiosk Home"', tag)
        self.assertIn("url_for('portal.index')", tag)


class HeaderRenderingTests(unittest.TestCase):
    """See HeaderMarkupTests' own docstring - CLAUDE-APP-MENU-01 retires
    the rendered icon+wordmark link for base.html's authenticated topbar
    specifically; home-navigation itself still renders, relocated."""

    def setUp(self):
        import app as app_module
        from models import User, db
        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="brand1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "brand1_owner"
            sess["role"] = "admin"

    def test_no_brand_symbol_renders_on_any_authenticated_page(self):
        # CLAUDE-LETTERMARK-PURGE-01: asserted against real rendered pages,
        # not template source, because a symbol could reach the page through a
        # shell this file does not read.
        for url in ("/", "/projects", "/upload"):
            body = self.client.get(url).get_data(as_text=True)
            self.assertNotIn('class="archiosk-mark"', body, url)
            self.assertNotIn('class="workspace-app-mark"', body, url)
            self.assertNotIn('class="workspace-topbar-brand"', body, url)

    def test_archiosk_menu_renders_with_plain_text_label(self):
        body = self.client.get("/").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.archiosk"')
        block = body[idx:body.index("</details>", idx)]
        self.assertIn(">Archiosk</summary>", block)

    def test_home_navigation_still_renders_and_links_home(self):
        body = self.client.get("/").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.archiosk.home"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn('href="/"', tag)


class BrandCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_brand_link_is_a_flex_row(self):
        body = _rule_body(self.css, ".workspace-topbar-brand")
        self.assertIn("display: flex", body)

    def test_brand_text_reads_as_identity_not_a_breadcrumb(self):
        body = _rule_body(self.css, ".workspace-topbar-brand-text")
        self.assertIn("font-size: 1.2rem", body)
        self.assertIn("font-weight: 600", body)

    def test_brand_text_larger_than_context_breadcrumb(self):
        brand_body = _rule_body(self.css, ".workspace-topbar-brand-text")
        context_body = _rule_body(self.css, ".workspace-topbar-context")
        brand_size = float(re.search(r"font-size:\s*([\d.]+)rem", brand_body).group(1))
        context_size = float(re.search(r"font-size:\s*([\d.]+)rem", context_body).group(1))
        self.assertGreater(brand_size, context_size)

    def test_context_breadcrumb_left_within_prior_secondary_range(self):
        # Deliberately untouched by this stage - already 0.88rem/normal
        # weight, within the suggested 14-16px secondary range.
        body = _rule_body(self.css, ".workspace-topbar-context")
        self.assertIn("font-size: 0.88rem", body)
        self.assertNotIn("font-weight", body)

    def test_mark_colored_via_shared_currentcolor_token(self):
        body = _rule_body(self.css, ".workspace-topbar-brand")
        self.assertIn("var(--brand-gold)", body)

    def test_the_mark_rule_is_gone_entirely(self):
        # Was: .archiosk-mark must not set its own color, inheriting instead
        # via currentColor. CLAUDE-LETTERMARK-PURGE-01 removed the element, so
        # the stronger statement now holds - there is no rule at all.
        self.assertNotIn(".archiosk-mark", self.css)

    def test_brand_gold_redefined_in_the_shared_owned_surface_scoping_blocks(self):
        # .workspace-topbar is one of the "owned surface roots" that
        # locally redefines standard token names per Appearance further
        # down main.css (the same mechanism --text-primary/the semantic
        # accents already use) - --brand-gold must be redefined there
        # too, NOT via a separate .workspace-topbar.appearance-dark
        # .workspace-topbar-brand { color: ... } rule (that selector
        # string is a literal prefix of the real combined scoping
        # block's own selector, so an earlier such rule would shadow it
        # for any test/tool doing an unanchored .index() search - it did,
        # caught by tests/test_p40vw8qa_theme_foreground_contrast.py's
        # own PerSurfaceScopingCompletenessTests, fixed by redefining the
        # custom property itself instead).
        for marker, token in (
            (".workspace-topbar.appearance-dark,", "--dark-brand-gold"),
            (".workspace-topbar.appearance-tinted,", "--tint-brand-gold"),
            (".workspace-topbar.appearance-deep-forest,", "--forest-brand-gold"),
        ):
            idx = self.css.index(marker)
            block_start = self.css.index("{", idx)
            block_end = self.css.index("}", block_start)
            body = self.css[block_start:block_end]
            self.assertIn(f"--brand-gold: var({token})", body, marker)

    def test_no_shadowing_descendant_override_rule_reintroduced(self):
        # Guards against re-adding the exact shadowing pattern removed
        # above - .workspace-topbar-brand must get its per-Appearance
        # color purely from the redefined --brand-gold custom property,
        # never a second, competing color: rule.
        self.assertNotIn(".workspace-topbar.appearance-dark .workspace-topbar-brand", self.css)
        self.assertNotIn(".workspace-topbar.appearance-tinted .workspace-topbar-brand", self.css)
        self.assertNotIn(".workspace-topbar.appearance-deep-forest .workspace-topbar-brand", self.css)

    def test_header_height_not_increased_via_topbar_padding(self):
        body = _rule_body(self.css, ".workspace-topbar")
        self.assertIn("padding: 0.6rem 0", body)


class BrandTokenTests(unittest.TestCase):
    def setUp(self):
        self.tokens = _TOKENS_CSS_PATH.read_text(encoding="utf-8")

    def test_all_four_theme_variants_defined(self):
        for token in ("--brand-gold", "--dark-brand-gold", "--tint-brand-gold", "--forest-brand-gold"):
            self.assertRegex(self.tokens, re.escape(token) + r"\s*:\s*#[0-9a-fA-F]{6}\s*;")

    def test_dark_midnight_and_forest_share_the_same_value(self):
        # Established convention: Black/Midnight Blue/Deep Forest share
        # one dark accent value; only Light is independently tuned.
        def value_of(token):
            match = re.search(re.escape(token) + r"\s*:\s*(#[0-9a-fA-F]{6})\s*;", self.tokens)
            return match.group(1)

        self.assertEqual(value_of("--dark-brand-gold"), value_of("--tint-brand-gold"))
        self.assertEqual(value_of("--dark-brand-gold"), value_of("--forest-brand-gold"))


class ContrastComplianceTests(unittest.TestCase):
    def test_check_contrast_tool_passes_for_all_brand_gold_pairings(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("check_contrast", _CHECK_CONTRAST_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        tokens = module.parse_tokens(_TOKENS_CSS_PATH)
        brand_pairings = [p for p in module.REQUIRED_PAIRINGS if "brand-gold" in p[0]]
        self.assertEqual(len(brand_pairings), 4)
        for fg_name, bg_name, minimum, description in brand_pairings:
            ratio = module.contrast_ratio(tokens[fg_name], tokens[bg_name])
            self.assertGreaterEqual(ratio, minimum, description)


if __name__ == "__main__":
    unittest.main()
