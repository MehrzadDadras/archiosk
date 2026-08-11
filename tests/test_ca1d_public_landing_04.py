"""
CLAUDE-CA1D-PUBLIC-LANDING-04 - Living Knowledge Ocean: Convection +
Depth + Parallax.

Covers the rework of the ambient knowledge field (originally CLAUDE-CA1D-
PUBLIC-LANDING-01, Sections B3/C1-C3) from a single flat plane of
independently-drifting items into a three-layer depth model (near/mid/
far - size, brightness, and rise speed all vary by layer) plus a
restrained upward-convection metaphor (two named "vent" regions that
items can spawn near and rise through faster/tighter, inferred purely
through motion, never rendered as a graphic). Deliberately does not
change the total DOM node count (still 7 bubbles + 8 particles + 8
scripts + 5 terms = 28) - only how each item's depth/current membership
is chosen and expressed through CSS custom properties feeding the one
shared kfRise keyframe.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class KnowledgeFieldDepthConvectionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_css_defines_three_depth_tier_custom_properties_on_kf_item(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        item_rule_start = css.index(".kf-item {")
        item_rule_end = css.index("}", item_rule_start)
        item_rule = css[item_rule_start:item_rule_end]
        for prop in ("--kf-scale", "--kf-peak-opacity", "--kf-drift-1", "--kf-drift-2", "--kf-drift-3"):
            self.assertIn(prop, item_rule)

    def test_css_far_depth_tier_is_blurred(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        self.assertIn(".kf-depth-far", css)
        far_rule_start = css.index(".kf-depth-far {")
        far_rule_end = css.index("}", far_rule_start)
        self.assertIn("blur(", css[far_rule_start:far_rule_end])

    def test_keyframe_has_intermediate_meander_stops_not_a_single_linear_drift(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        keyframe_start = css.index("@keyframes kfRise")
        keyframe_end = css.index("}\n", css.index("100%", keyframe_start)) + 1
        keyframe = css[keyframe_start:keyframe_end]
        for stop in ("0%", "35%", "65%", "88%", "100%"):
            self.assertIn(stop, keyframe)
        # Depth-driven scale is composed into the transform at both ends.
        self.assertIn("scale(var(--kf-scale))", keyframe)
        self.assertIn("var(--kf-peak-opacity)", keyframe)

    def test_js_defines_named_depth_config_with_three_tiers(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("DEPTH_CONFIG", js)
        for tier in ("near:", "mid:", "far:"):
            self.assertIn(tier, js)

    def test_js_defines_named_vents_not_inlined_magic_numbers(self):
        """Section 8: architected so a future tranche could later drive
        VENTS by a live interaction without this tranche building that
        interaction - a named, reusable structure, not one-off inline
        constants scattered through spawn()."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("var VENTS", js)
        self.assertIn("IN_CURRENT_PROBABILITY", js)

    def test_js_bubbles_share_the_same_spawn_function_as_every_other_tier(self):
        """Section 7: bubbles must not be a separate decorative code
        path - exactly one spawn() definition, and the bubble loop calls
        it like every other tier."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertEqual(js.count("function spawn("), 1)
        self.assertIn("spawn('kf-bubble'", js)

    def test_total_element_counts_unchanged_from_the_previous_tranche(self):
        """Section 10: depth/convection must come from redistributing
        the existing population, never from adding more particles."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("for (var b = 0; b < 7; b++)", js)
        self.assertIn("for (var p = 0; p < 8; p++)", js)
        self.assertIn("for (var s = 0; s < 8; s++)", js)
        self.assertIn("for (var t = 0; t < 5; t++)", js)

    def test_reduced_motion_still_hides_the_whole_field(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-knowledge-field { display: none; }", reduced_motion_block)

    def test_js_still_skips_all_generation_under_reduced_motion(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        field_section = js[js.index("landing-knowledge-field"):js.index("DEPTH_CONFIG")]
        self.assertIn("reduceMotion", field_section)
        self.assertIn("return", field_section)


if __name__ == "__main__":
    unittest.main()
