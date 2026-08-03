"""
CLAUDE-P40-BRAND1 - Top-Left ARCHIOSK Brand Treatment.

No prior mark/medallion/icon of any kind existed anywhere in this
repository before this stage (grounded by direct search - no `.svg`
file, no inline `<svg>` beyond annotation-toolbar glyphs, no favicon),
so "reuse the same mark" meant designing ONE new deterministic
two-parabola "A" glyph (SVG quadratic-Bezier `Q` segments - literal
parabola arcs, not an approximation) as a single shared Jinja macro
(`archiosk_mark` in `templates/_macros.html`), then wiring it into the
existing top-left `menu.brand` link (`templates/base.html`) alongside
an enlarged "Archiosk" wordmark, while leaving `menu.context`'s own
breadcrumb untouched (already within the suggested secondary-text
range). Colored via a new `--brand-gold` token family (light + one
shared dark value reused across Black/Midnight Blue/Deep Forest, the
same convention already established for `--tabcolor-*`), verified with
`tools/check_contrast.py` at the STRICTER 4.5:1 normal-text floor
(this is small always-visible identity text, not an occasional badge).

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


class RepositoryGroundingTests(unittest.TestCase):
    """Section 1-style check: exactly one shared mark source exists, not
    a per-caller copy - the whole point of "one shared SVG/source"."""

    def test_svg_path_data_appears_exactly_once_in_macros(self):
        source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        needle = "M 14 90 Q 22 42 50 12"
        self.assertEqual(source.count(needle), 1)

    def test_no_second_copy_of_the_mark_path_anywhere_else_in_templates(self):
        needle = "M 14 90 Q 22 42 50 12"
        for path in (_REPO_ROOT / "templates").rglob("*.html"):
            if path == _MACROS_HTML_PATH:
                continue
            self.assertNotIn(needle, path.read_text(encoding="utf-8"), path)


class MacroGeometryTests(unittest.TestCase):
    def setUp(self):
        self.source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        start = self.source.index("{% macro archiosk_mark")
        end = self.source.index("{% endmacro %}", start)
        self.macro = self.source[start:end]

    def test_uses_two_quadratic_bezier_legs(self):
        self.assertEqual(self.macro.count(" Q "), 2)

    def test_legs_are_mirror_images_sharing_the_same_apex(self):
        # Both legs must terminate at the same apex point (a real "A"
        # shape needs its two strokes to actually meet at the top).
        self.assertIn("50 12", self.macro)
        self.assertEqual(self.macro.count("50 12"), 2)

    def test_includes_a_crossbar(self):
        self.assertIn(" L ", self.macro)

    def test_color_is_driven_entirely_by_currentcolor(self):
        self.assertIn('stroke="currentColor"', self.macro)
        # No caller-independent hardcoded color anywhere in the path/svg.
        self.assertNotIn("#", self.macro)

    def test_decorative_by_default(self):
        self.assertIn('aria-hidden="true"', self.macro)
        self.assertIn('focusable="false"', self.macro)

    def test_size_parameter_drives_width_and_height(self):
        self.assertIn('width="{{ size }}"', self.macro)
        self.assertIn('height="{{ size }}"', self.macro)

    def test_macro_declares_a_default_size_within_suggested_22_to_26px_range(self):
        match = re.search(r"macro archiosk_mark\(size=(\d+)", self.source)
        self.assertIsNotNone(match)
        self.assertTrue(22 <= int(match.group(1)) <= 26)


class HeaderMarkupTests(unittest.TestCase):
    def setUp(self):
        self.source = _BASE_HTML_PATH.read_text(encoding="utf-8")
        idx = self.source.index('data-ui-ref="menu.brand"')
        self.tag_start = self.source.rindex("<a", 0, idx)
        self.tag_end = self.source.index("</a>", idx) + len("</a>")
        self.element = self.source[self.tag_start:self.tag_end]

    def test_macros_imported(self):
        self.assertIn('{% import "_macros.html" as macros %}', self.source)

    def test_brand_link_calls_the_shared_macro(self):
        self.assertIn("macros.archiosk_mark(", self.element)

    def test_brand_link_is_a_single_anchor_no_nested_tab_stop(self):
        # Exactly one <a ...> open tag within this element's own markup -
        # the icon and wordmark share one link/tab-stop, never two.
        self.assertEqual(self.element.count("<a "), 1)
        self.assertEqual(self.element.count("</a>"), 1)

    def test_brand_link_has_accessible_name_covering_icon_and_text(self):
        self.assertIn('aria-label="Archiosk Home"', self.element)

    def test_brand_link_href_and_data_ui_ref_unchanged(self):
        self.assertIn("data-ui-ref=\"menu.brand\"", self.element)
        self.assertIn("url_for('portal.index')", self.element)

    def test_svg_mark_itself_carries_no_separate_ui_ref(self):
        # The mark must never become its own competing data-ui-ref -
        # only the outer link carries one, exactly once.
        self.assertEqual(self.element.count("data-ui-ref"), 1)

    def test_wordmark_text_present(self):
        self.assertIn(">Archiosk</span>", self.element)


class HeaderRenderingTests(unittest.TestCase):
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

    def test_brand_mark_renders_on_authenticated_pages(self):
        for url in ("/", "/projects", "/upload"):
            body = self.client.get(url).get_data(as_text=True)
            self.assertIn('class="archiosk-mark"', body, url)
            self.assertIn('aria-label="Archiosk Home"', body, url)

    def test_only_one_archiosk_mark_rendered_per_page(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertEqual(body.count('class="archiosk-mark"'), 1)

    def test_brand_link_navigates_home(self):
        body = self.client.get("/").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.brand"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn('href="/"', tag)

    def test_rendered_svg_mark_carries_no_separate_ui_ref(self):
        body = self.client.get("/").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.brand"')
        element = body[body.rindex("<a", 0, idx):body.index("</a>", idx) + len("</a>")]
        self.assertIn("<svg", element)
        self.assertEqual(element.count("data-ui-ref"), 1)


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

    def test_mark_element_has_no_independent_color_rule(self):
        # The SVG inherits color from .workspace-topbar-brand via
        # currentColor - .archiosk-mark itself must not set its own.
        body = _rule_body(self.css, ".archiosk-mark")
        self.assertNotIn("color:", body)

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
