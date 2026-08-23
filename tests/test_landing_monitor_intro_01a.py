"""CLAUDE-LANDING-MONITOR-01A - metallic hero centerpiece on the landing surface.

The Product Owner selected a "first monitor" concept image as the visual
target, then amended the mission with a LANDING PAGE PRESERVATION GATE:
the centre hero composition changes; the background is an accepted live
asset and is out of scope entirely.

These tests hold both halves of that.

  Centerpiece:
    * the hero is the REAL ARCHIOSK mark, not an invented symbol;
    * it is metallic, driven by a real gradient rather than a raster;
    * the wordmark is strengthened ADDITIVELY, leaving the accepted rule
      reversible;
    * the selected subtitle is shown;
    * nothing claims to be loading, because nothing is.

  Preservation gate:
    * every accepted background element still renders;
    * no selector this tranche added touches a background class;
    * the accepted wordmark arrival and prelude-streak motion survive
      unedited.

Pure rendering/static-asset assertions. No external boundary is reachable.
"""
import re
import unittest
from pathlib import Path

LANDING_CSS = Path("static/css/landing.css").read_text(encoding="utf-8")
LANDING_HTML = Path("templates/landing.html").read_text(encoding="utf-8")
MACROS = Path("templates/_macros.html").read_text(encoding="utf-8")

SECTION_MARKER = "CLAUDE-LANDING-MONITOR-01A -- CENTERPIECE ONLY"

# The one shared source for the mark geometry (templates/_macros.html).
MARK_LEFT_LIMB = "M12 8 L21 30 L7 58"
MARK_RIGHT_LIMB = "M52 8 L43 30 L57 58"

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

        self.client = app_module.create_app("testing").test_client()
        self.body = self.client.get("/").get_data(as_text=True)

    def test_anonymous_root_still_serves_the_one_accepted_landing(self):
        """No second landing architecture: same route, same page."""
        self.assertIn("landing-page", self.body)

    def test_existing_entry_controls_are_preserved(self):
        """Explore / Request Trial Access / Sign In, unchanged."""
        for ref in ("landing.explore", "landing.start-trial", "landing.sign-in"):
            self.assertIn('data-ui-ref="%s"' % ref, self.body)
        for href in ("/explore", "/start-trial", "/login"):
            self.assertIn('href="%s"' % href, self.body)

    def test_hero_emblem_is_the_real_archiosk_mark(self):
        self.assertIn("landing-emblem-mark", self.body)
        self.assertIn(MARK_LEFT_LIMB, self.body)
        self.assertIn(MARK_RIGHT_LIMB, self.body)

    def test_hero_geometry_comes_from_the_shared_macro_not_a_copy(self):
        """The mark must stay a single source; landing.html must not inline its own."""
        self.assertIn("archiosk_mark", LANDING_HTML)
        self.assertIn(MARK_LEFT_LIMB, MACROS)
        self.assertNotIn(MARK_LEFT_LIMB, LANDING_HTML)

    def test_hero_is_metallic_through_a_real_gradient(self):
        self.assertIn('id="landing-emblem-metal"', self.body)
        self.assertIn("linearGradient", self.body)
        css = _new_css_declarations()
        self.assertIn("stroke: url(#landing-emblem-metal)", css)
        self.assertIn("fill: url(#landing-emblem-metal)", css)

    def test_metal_ramp_alternates_highlight_and_shadow(self):
        """A flat ramp is a tint; metal needs the light to turn over."""
        stops = [int(m, 16) for m in re.findall(r'stop-color="#(\w\w)\w{4}"', self.body)]
        self.assertGreaterEqual(len(stops), 4, "expected a multi-stop metal ramp")
        self.assertGreater(max(stops) - min(stops), 0x50, "ramp must carry real contrast")

    def test_wordmark_is_strengthened_additively(self):
        """The accepted rule stays; strength is layered as a second class."""
        self.assertIn('class="landing-wordmark landing-wordmark-strong"', self.body)
        rule = _rule_body(_new_css_declarations(), ".landing-wordmark-strong")
        self.assertIn("font-weight: 700", rule)

    def test_selected_identity_line_is_shown(self):
        self.assertIn("Construction Procurement Ecosystem", self.body)

    def test_no_fake_loading_state_was_created(self):
        """The concept image shows a progress bar and a 'loading' caption.
        Nothing is loading at this point, so nothing may claim to be."""
        lowered = self.body.lower()
        for claim in ("loading", "progress-bar", "progressbar"):
            self.assertNotIn(claim, lowered, "landing must not imply progress: %r" % claim)

    def test_gradient_carrier_cannot_disturb_the_centred_column(self):
        rule = _rule_body(_new_css_declarations(), ".landing-emblem-defs")
        self.assertIn("width: 0", rule)
        self.assertIn("height: 0", rule)
        self.assertIn("position: absolute", rule)


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
    """The selected monitor image is a visual reference, NOT a page background."""

    def test_no_reference_image_was_embedded_anywhere(self):
        for haystack, label in ((LANDING_CSS, "landing.css"), (LANDING_HTML, "landing.html")):
            with self.subTest(file=label):
                # url(#...) is the in-page gradient reference, not an asset load.
                scrubbed = haystack.replace("url_for", "").replace("url(#", "")
                self.assertNotIn("url(", scrubbed, "%s must not load a raster background" % label)
                self.assertNotIn("data:image", haystack)

    def test_no_new_binary_asset_was_added_to_static(self):
        assets = [p.name for p in Path("static").iterdir() if p.is_file()]
        self.assertEqual(
            sorted(a for a in assets if a.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))),
            [], "the concept image must not be shipped as an asset",
        )


if __name__ == "__main__":
    unittest.main()
