"""
CLAUDE-CA1D-LANDING-BALANCE-01, Part B - rebalance the knowledge
field's horizontal distribution so activity isn't concentrated at the
far edges/corners while the true center reading zone stays protected.

Covers what was actually changed in static/js/landing.js's spawn()
logic: VENTS moved further toward the true edges with a lower
IN_CURRENT_PROBABILITY (softening the previous over-dense "hot spot"),
and a new equal-thirds AMBIENT_BANDS_LEFT model (outer edge/mid-field/
approaching-center) replacing the old single wide uniform-range band,
so the region just outside the protected center column reliably gets
populated instead of being left to thin uniform chance.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class KnowledgeFieldBalanceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def _js(self):
        return self.client.get("/static/js/landing.js").get_data(as_text=True)

    def test_vents_moved_toward_true_edges_with_lower_probability(self):
        js = self._js()
        self.assertIn("var VENTS = [{ xVw: 7 }, { xVw: 93 }]", js)
        self.assertIn("var IN_CURRENT_PROBABILITY = 0.3;", js)

    def test_three_equal_ambient_sub_bands_defined(self):
        js = self._js()
        self.assertIn("AMBIENT_BANDS_LEFT", js)
        bands_start = js.index("var AMBIENT_BANDS_LEFT")
        bands_end = js.index("];", bands_start)
        bands_block = js[bands_start:bands_end]
        # Three distinct sub-bands: outer edge, mid-field, approaching-center.
        self.assertEqual(bands_block.count("["), 4)  # outer array + 3 sub-arrays

    def test_innermost_ambient_band_reaches_close_to_but_never_inside_center(self):
        js = self._js()
        bands_start = js.index("var AMBIENT_BANDS_LEFT")
        bands_end = js.index("];", bands_start)
        bands_block = js[bands_start:bands_end]
        self.assertIn("CENTER_MIN_VW - 2", bands_block)

    def test_ambient_placement_mirrors_left_band_for_the_right_side(self):
        js = self._js()
        spawn_start = js.index("function spawn(")
        spawn_end = js.index("field.appendChild(el);", spawn_start)
        spawn_body = js[spawn_start:spawn_end]
        self.assertIn("pickAmbientLeftVw()", spawn_body)
        self.assertIn("100 - leftVw", spawn_body)

    def test_protected_center_column_unchanged(self):
        js = self._js()
        self.assertIn("var CENTER_MIN_VW = 30;", js)
        self.assertIn("var CENTER_MAX_VW = 70;", js)
        self.assertIn("clampOutsideCenter", js)

    def test_depth_and_convection_model_still_present_unchanged(self):
        """Section B4/B5: depth/parallax and the vent-convection concept
        must be preserved, not removed, while rebalancing."""
        js = self._js()
        for marker in ("DEPTH_CONFIG", "near:", "mid:", "far:", "inCurrent", "clampOutsideCenter"):
            self.assertIn(marker, js)

    def test_total_element_counts_still_unchanged(self):
        js = self._js()
        self.assertIn("for (var b = 0; b < 7; b++)", js)
        self.assertIn("for (var p = 0; p < 8; p++)", js)
        self.assertIn("for (var s = 0; s < 8; s++)", js)
        self.assertIn("for (var t = 0; t < 5; t++)", js)

    def test_knowledge_field_still_hidden_under_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-knowledge-field { display: none; }", reduced_motion_block)


if __name__ == "__main__":
    unittest.main()
