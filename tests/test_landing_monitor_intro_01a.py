"""CLAUDE-LANDING-HERO-01A - vector centerpiece on the landing surface.

The Product Owner supplied an approved reference image and a LANDING PAGE
PRESERVATION GATE: the centre composition changes; the background is an
accepted live asset and is out of scope entirely.

An earlier attempt (CLAUDE-LANDING-MONITOR-01A) used the existing two-limb
archiosk_mark as the hero and a strengthened serif wordmark. Both were
reviewed live and rejected. These tests therefore assert not only what the
centerpiece IS, but what it must never silently become again.

  Centerpiece:
    * the hero is the purpose-drawn aerodynamic asset, NOT the archiosk_mark;
    * the wordmark is vector letterforms with a crossbar-less A, and no
      serif type is rendered in the hero;
    * both marks are real, well-formed, self-contained SVG assets;
    * no font dependency was introduced;
    * nothing claims to be loading, because nothing is.

  Preservation gate:
    * every accepted background element still renders;
    * no selector this tranche added touches a background class;
    * the accepted wordmark arrival and prelude-streak motion survive
      unedited, and the accepted stylesheet is an untouched prefix.

Pure rendering/static-asset assertions. No external boundary is reachable.
"""
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

LANDING_CSS = Path("static/css/landing.css").read_text(encoding="utf-8")
LANDING_HTML = Path("templates/landing.html").read_text(encoding="utf-8")
HERO_SVG = Path("static/img/archiosk-hero.svg").read_text(encoding="utf-8")
WORDMARK_SVG = Path("static/img/archiosk-wordmark.svg").read_text(encoding="utf-8")

SECTION_MARKER = "CLAUDE-LANDING-HERO-01A -- CENTERPIECE ONLY"

# The product's own bottleneck mark. It is NOT the hero, and the Product
# Owner rejected it in that role explicitly.
MARK_LEFT_LIMB = "M12 8 L21 30 L7 58"

# Everything the preservation gate names, as it appears on this surface.
BACKGROUND_CLASSES = (
    "landing-page",             # base gradient field
    "landing-field-canvas",     # particles / orbs
    "landing-knowledge-field",  # dotted field + multilingual floating words
    "landing-signal-streak",    # one-shot prelude
)


def _new_css_section() -> str:
    """Only the block this tranche appended, never the accepted file above it."""
    marker = LANDING_CSS.index(SECTION_MARKER)
    # Start at the comment OPENER, not at the marker inside it, so the
    # section header is a complete, strippable comment.
    return LANDING_CSS[LANDING_CSS.rindex("/*", 0, marker):]


def _new_css_declarations() -> str:
    """The appended block with CSS comments removed.

    The section's own prose names the things it forbids and the background
    assets it preserves, so a naive substring scan would match the
    documentation rather than the stylesheet.
    """
    return re.sub(r"/\*.*?\*/", " ", _new_css_section(), flags=re.S)


def _accepted_css() -> str:
    """Everything ABOVE this tranche's section: the accepted stylesheet."""
    marker = LANDING_CSS.index(SECTION_MARKER)
    return LANDING_CSS[: LANDING_CSS.rindex("/*", 0, marker)]


def _rule_body(css: str, selector: str) -> str:
    """The declarations of the first rule with this exact selector."""
    start = css.index(selector + " {") + len(selector) + 2
    return css[start: css.index("}", start)]


class CenterpieceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.body = app_module.create_app("testing").test_client().get("/").get_data(as_text=True)

    def test_anonymous_root_still_serves_the_one_accepted_landing(self):
        """No second landing architecture: same route, same page."""
        self.assertIn("landing-page", self.body)

    def test_existing_entry_controls_are_preserved(self):
        """Explore / Request Trial Access / Sign In, unchanged."""
        for ref in ("landing.explore", "landing.start-trial", "landing.sign-in"):
            self.assertIn('data-ui-ref="%s"' % ref, self.body)
        for href in ("/explore", "/start-trial", "/login"):
            self.assertIn('href="%s"' % href, self.body)

    def test_hero_and_wordmark_assets_are_both_served(self):
        self.assertIn("img/archiosk-hero.svg", self.body)
        self.assertIn("img/archiosk-wordmark.svg", self.body)
        self.assertIn("landing-emblem-img", self.body)
        self.assertIn("landing-wordmark-img", self.body)

    def test_hero_is_not_the_archiosk_mark(self):
        """The rejected substitution must not silently return."""
        self.assertNotIn(MARK_LEFT_LIMB, self.body)
        self.assertNotIn(MARK_LEFT_LIMB, HERO_SVG)
        self.assertNotIn("archiosk_mark", LANDING_HTML)

    def test_no_serif_wordmark_is_rendered_in_the_hero(self):
        """The h1 renders an image; the accepted serif rule paints no text."""
        self.assertIn("landing-wordmark-vector", self.body)
        rule = _rule_body(_new_css_declarations(), ".landing-wordmark-vector")
        self.assertIn("font-size: 0", rule)

    def test_page_name_is_still_real_accessible_text(self):
        """Turning the wordmark into an image must not cost the h1 its name."""
        self.assertIn('alt="Archiosk"', self.body)

    def test_selected_identity_line_is_shown(self):
        self.assertIn("Construction Procurement Ecosystem", self.body)

    def test_no_fake_loading_state_was_created(self):
        """The reference shows a progress bar and a 'loading' caption.
        Nothing is loading at this point, so nothing may claim to be."""
        lowered = self.body.lower()
        for claim in ("loading", "progress-bar", "progressbar"):
            self.assertNotIn(claim, lowered, "landing must not imply progress: %r" % claim)


class VectorAssetTests(unittest.TestCase):
    """Both marks must be genuine, self-contained, well-formed vector."""

    def test_both_assets_are_well_formed_xml(self):
        for path in ("static/img/archiosk-hero.svg", "static/img/archiosk-wordmark.svg"):
            with self.subTest(asset=path):
                ET.parse(path)

    def test_neither_asset_embeds_a_raster(self):
        for svg, label in ((HERO_SVG, "hero"), (WORDMARK_SVG, "wordmark")):
            with self.subTest(asset=label):
                self.assertNotIn("data:image", svg)
                self.assertNotIn("<image", svg)

    def test_both_assets_carry_their_own_metal_gradient(self):
        self.assertIn('id="ah-metal"', HERO_SVG)
        self.assertIn('id="aw-metal"', WORDMARK_SVG)

    def test_gradients_paint_in_user_space(self):
        """objectBoundingBox cannot paint zero-area paths, which silently
        erased H and I the first time this was drawn."""
        for svg, label in ((HERO_SVG, "hero"), (WORDMARK_SVG, "wordmark")):
            with self.subTest(asset=label):
                for gradient in re.findall(r"<linearGradient[^>]*>", svg):
                    self.assertIn('gradientUnits="userSpaceOnUse"', gradient)

    def test_wordmark_a_is_a_crossbar_less_upside_down_v(self):
        """The single letterform the Product Owner named explicitly."""
        paths = re.findall(r'<path d="([^"]+)"', WORDMARK_SVG)
        a_path = paths[0]
        points = re.findall(r"[ML](-?[\d.]+) (-?[\d.]+)", a_path)
        self.assertEqual(len(points), 3, "the A must be exactly two strokes")
        (x1, y1), (apex_x, apex_y), (x3, y3) = [(float(a), float(b)) for a, b in points]
        self.assertEqual(y1, y3, "both feet sit on the baseline")
        self.assertLess(apex_y, y1, "the apex is above the feet")
        self.assertAlmostEqual(apex_x, (x1 + x3) / 2, places=3, msg="apex is centred")
        self.assertGreater(x3 - x1, 60, "the A is wide")
        self.assertNotIn("H", a_path, "the A must carry no crossbar")

    def test_every_wordmark_letter_is_present(self):
        """H and I are pure vertical strokes and were lost once already."""
        letters = re.findall(r"<!-- ([A-Z]) -->", WORDMARK_SVG)
        self.assertEqual(letters, list("ARCHIOSK"))

    def test_no_font_dependency_was_introduced(self):
        """The reason the letterforms are drawn at all."""
        for text, label in ((LANDING_CSS, "landing.css"), (LANDING_HTML, "landing.html")):
            with self.subTest(file=label):
                self.assertNotIn("@font-face", text)
                self.assertNotIn("fonts.googleapis", text)
                self.assertNotIn("fonts.gstatic", text)
        fonts = [p.name for p in Path("static").rglob("*")
                 if p.is_file() and p.suffix.lower() in (".woff", ".woff2", ".ttf", ".otf")]
        self.assertEqual(fonts, [], "no font file may be shipped")


class PreservationGateTests(unittest.TestCase):
    """The background is an accepted live asset. This tranche must not touch it."""

    def setUp(self):
        import app as app_module

        self.body = app_module.create_app("testing").test_client().get("/").get_data(as_text=True)

    def test_every_accepted_background_element_still_renders(self):
        for cls in BACKGROUND_CLASSES:
            with self.subTest(background=cls):
                self.assertIn(cls, self.body)

    def test_both_background_scripts_are_still_loaded(self):
        self.assertIn("js/ocean_field.js", self.body)
        self.assertIn("js/landing.js", self.body)

    def test_no_selector_this_tranche_added_touches_the_background(self):
        """The strongest form of the gate: the new section cannot reach the
        background at all, so it cannot restyle, retime or suppress it."""
        css = _new_css_declarations()
        selectors = re.findall(r"(?:^|\})\s*([^{}@]+?)\s*\{", css)
        for selector in selectors:
            flat = " ".join(selector.split())
            for cls in BACKGROUND_CLASSES:
                with self.subTest(selector=flat, background=cls):
                    self.assertNotIn(
                        cls, flat,
                        "selector %r reaches accepted background asset .%s" % (flat, cls),
                    )

    def test_accepted_wordmark_arrival_is_unedited(self):
        """Timing, easing and delay of the accepted reveal, byte-for-byte."""
        self.assertIn(
            "animation: landingWordmarkArrival 1.9s cubic-bezier(0.18, 0.84, 0.22, 1) 1.3s forwards",
            _accepted_css(),
        )

    def test_accepted_prelude_streak_still_animates(self):
        accepted = _accepted_css()
        self.assertIn(
            "animation: landingSignalStreak1 .95s cubic-bezier(0.22, 0.61, 0.36, 1) 150ms forwards",
            accepted,
        )
        self.assertIn("@keyframes landingSignalStreak1", accepted)

    def test_new_section_is_purely_additive(self):
        """It appends. It never redefines an accepted animation."""
        new_keyframes = set(re.findall(r"@keyframes\s+(\w+)", _new_css_declarations()))
        accepted_keyframes = set(re.findall(r"@keyframes\s+(\w+)", _accepted_css()))
        self.assertEqual(
            new_keyframes & accepted_keyframes, set(),
            "an accepted animation was redefined rather than left alone",
        )

    def test_emblem_arrival_never_overlaps_the_prelude_streak(self):
        """The streak finishes ~1.1s; the emblem must start after it."""
        rule = _rule_body(_new_css_declarations(), ".landing-emblem")
        # The easing function contains spaces, so match up to `forwards`.
        delay = float(re.search(r"landingEmblemArrival.*?([\d.]+)s\s+forwards", rule).group(1))
        self.assertGreaterEqual(delay, 1.1, "emblem must not play over the accepted prelude")


class ReducedMotionTests(unittest.TestCase):
    def test_emblem_is_static_under_reduced_motion(self):
        css = _new_css_declarations()
        block = css[css.rindex("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-emblem", block)
        self.assertIn("animation: none !important", block)


class ReferenceImageTests(unittest.TestCase):
    """The reference image is a VISUAL REFERENCE, NOT a page background."""

    def test_no_reference_image_was_embedded_anywhere(self):
        for haystack, label in ((LANDING_CSS, "landing.css"), (LANDING_HTML, "landing.html")):
            with self.subTest(file=label):
                # url(#...) is an in-page gradient reference, not an asset load.
                scrubbed = haystack.replace("url_for", "").replace("url(#", "")
                self.assertNotIn("url(", scrubbed, "%s must not load a raster background" % label)
                self.assertNotIn("data:image", haystack)

    def test_no_raster_asset_was_added_to_static(self):
        raster = sorted(
            p.as_posix() for p in Path("static").rglob("*")
            if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        )
        self.assertEqual(raster, [], "the reference image must not be shipped as an asset")


if __name__ == "__main__":
    unittest.main()
