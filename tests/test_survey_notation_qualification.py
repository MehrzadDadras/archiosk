"""Rule 4: printed notation constrains computation; era never fills gaps."""
import unittest

from services import survey_graph as sg


class SurveyNotationQualification(unittest.TestCase):
    def test_printed_quadrant_bearings(self):
        for text, expected in (("N 45 E", 45), ("S 30 E", 150),
                               ("S 20 W", 200), ("N 15 W", 345),
                               ("N 12°30'00\" E", 12.5)):
            with self.subTest(text=text):
                bearing = sg._bearing({"text": text, "certainty": "RECOVERED"})
                self.assertEqual(bearing["value_degrees"], expected)

    def test_unprinted_or_conflicting_angle_is_not_a_bearing(self):
        for text, numeric in (("b", 45), ("N 45 E", 80), ("N 95 E", 95)):
            with self.subTest(text=text):
                bearing = sg._bearing({"text": text, "value_degrees": numeric,
                                       "certainty": "RECOVERED"})
                self.assertIsNone(bearing["value_degrees"])
                self.assertEqual(bearing["text"], text)
        self.assertIsNone(sg._bearing(None))

    def test_radius_chord_do_not_choose_an_image_arc(self):
        # Same radius/chord permit minor and major branches. Image fractions
        # also do not establish a Euclidean coordinate frame or physical scale.
        result, reason = sg._arc_from_chord_and_radius(
            (.1, .2), (.8, .2), 153.76, 139.2, "right")
        self.assertIsNone(result)
        self.assertTrue(reason)

    def test_persisted_bearing_cannot_promote_weak_binding(self):
        bearing = sg._bearing({"text": "N 45 E", "certainty": "RECOVERED"})
        self.assertEqual(bearing["read_certainty"], "RECOVERED")
        self.assertEqual(bearing["bind_certainty"], "PARTIALLY_RECOVERED")
        bearing.update(bind_certainty="UNRESOLVED", bound_certainty="RECOVERED")
        self.assertIsNone(sg._azimuth_of({"bearing": bearing}))

    def test_missing_curve_parameters_remain_partial(self):
        segment = {"id": "C1", "kind": "arc", "radius": {"value": 10},
                   "chord": {"value": 5}}
        self.assertFalse(sg.segment_inputs(segment)["arc_defined"])
        self.assertFalse(sg.segment_inputs(segment)["computable"])

    def test_curve_family_preserves_alternatives_and_weak_binding(self):
        def parameter(text, value):
            return sg._dimension({"text": text, "value": value, "unit": "m", "certainty": "RECOVERED"})
        segment = {"radius": parameter("R 10", 10), "chord": parameter("C 10", 10)}
        result = sg.curve_constraints(segment)
        self.assertEqual(result["state"], "CONDITIONAL_ARC_FAMILY")
        self.assertAlmostEqual(result["minor_delta_degrees"], 60)
        self.assertAlmostEqual(result["major_delta_degrees"], 300)
        self.assertEqual(result["binding_certainty"], "PARTIALLY_RECOVERED")
        segment["chord"]["value"] = 21
        self.assertEqual(sg.curve_constraints(segment)["state"], "EVIDENCE_CONFLICT")
        segment["chord"]["value"] = 10
        segment["chord"]["unit"] = "ft"
        self.assertEqual(sg.curve_constraints(segment)["state"], "PARTIAL")
