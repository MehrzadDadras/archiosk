"""CLAUDE-PLANNING-VISUAL-ACCEPTANCE-01 - the visual evidence acceptance test.

    A PARCEL BOUNDARY PROVES WHERE THE PROPERTY IS.
    A ZONING BOUNDARY PROVES WHICH REGULATORY GEOGRAPHY APPLIES.
    THEY ARE NOT INTERCHANGEABLE.

Fixtures A-H are section 13's, built from synthetic geometry so the acceptance
rules are proven on cases that can be constructed EXACTLY - including the ones a
real municipality may never serve on demand, like a parcel touching a zone
boundary or a visual that contradicts its own prose. A rule that can only be
tested when a City happens to serve the right property is not a rule that gets
tested.

NOTHING HERE REACHES THE NETWORK. The evaluator reads a finished result, so a
fixture IS a finished result. The live half - section 14 - is a recorded real
retrieval, never a request made from inside the suite.
"""
from __future__ import annotations

import unittest

from services import deterministic_spatial as spatial
from services import planning_acceptance as acceptance
from services import planning_visual

RETRIEVED_AT = "2026-09-14T12:00:00+00:00"


def square(x, y, size):
    """Clockwise exterior ring, the form `deterministic_spatial` expects."""
    return [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]


def polygon(ring):
    return {"type": "Polygon", "coordinates": [ring]}


PARCEL_RING = square(10, 10, 10)          # a small parcel
ZONE_RING = square(0, 0, 100)             # comfortably containing it
OTHER_ZONE_RING = square(100, 0, 100)     # adjacent, not containing
STRADDLE_RING = square(15, 0, 100)        # overlaps the parcel partially


def _token(relation, reason=None):
    return {"spatial_relation": relation, "reason": reason,
            "engine": spatial.ENGINE,
            "spatial_basis": (spatial.BASIS_DETERMINISTIC
                              if relation in (spatial.RELATION_INSIDE,
                                              spatial.RELATION_OUTSIDE,
                                              spatial.RELATION_INTERSECTS)
                              else spatial.BASIS_NONE)}


def result(*, parcel_geometry=None, zoning_geometry=None, zone_label="RD (f15.0; a550)",
           zone_code="RD", statements=None, token=None, exception_flagged=False,
           exception_record=None, zone_features=None, complete_provenance=True,
           exception_number=None):
    """One finished Planning & Zoning result, shaped as the runner emits it."""
    parcel_block = {
        "geometry": parcel_geometry,
        "source": "City of Toronto Property Boundary",
        "layer": "Property Boundary",
        "parcel_identifier": "PIN-0000-0001",
        "geometry_id": spatial.geometry_hash(parcel_geometry),
    }
    zoning_block = {
        "geometry": zoning_geometry,
        "source": "City of Toronto Zoning Area (cot_geospatial11/3)",
        "layer": "Zoning Area",
        "geometry_id": spatial.geometry_hash(zoning_geometry),
    }
    if complete_provenance:
        # What section 6 asks the EVIDENCE OBJECT to carry. Stated on the
        # fixture rather than assumed, so the target is explicit and the real
        # runner can be measured against it.
        parcel_block["spatial_reference"] = "EPSG:3857"
        zoning_block["spatial_reference"] = "EPSG:3857"
        zoning_block["feature_identifier"] = "ZONE-FEATURE-77"

    attributes = {"ZN_ZONE": zone_code, "ZN_STRING": zone_label}
    if exception_flagged:
        attributes["ZN_EXCPTN"] = "Y"
        attributes["ZN_EXCPTN_NO"] = exception_number or "5"

    retrieval = {
        "retrieved_at": RETRIEVED_AT,
        "zoning_attributes": attributes,
        "exception": exception_record,
        "visual_geometry": {"parcel": parcel_block, "zoning": zoning_block},
    }
    if zone_features is not None:
        retrieval["zone_features"] = zone_features
        retrieval["zone_features_examined"] = True

    return {
        "retrieval": retrieval,
        "document": {"statements": statements or []},
        "spatial_tokens": {"zoning_area": token},
    }


def zone_statement(text, **extra):
    record = {"statement_id": "S-ZONE", "kind": "AUTHORITY_SAYS",
              "topic": "ZONING_DESIGNATION", "spatial_layer": "zoning_area",
              "text": text}
    record.update(extra)
    return record


CONTAINED = ("The subject parcel lies within the City zoning polygon labelled "
             "RD (f15.0; a550).")


class FixtureA_SingleZoneNoException(unittest.TestCase):
    """Parcel fully inside one zoning polygon. The baseline PASS."""

    def setUp(self):
        self.result = result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            statements=[zone_statement(CONTAINED)])
        self.panels = planning_visual.panels_for(self.result["retrieval"])

    def test_it_passes(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["state"], acceptance.PASS,
                         acceptance.summarize(record))

    def test_the_relationship_is_within_a_single_zone(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["relationship"], acceptance.WITHIN_SINGLE_ZONE)

    def test_parcel_and_zoning_are_separate_evidence_identities(self):
        """Section 2. Different geometry, different provenance, different id."""
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertTrue(record["parcel"]["qualified"])
        self.assertTrue(record["zoning"]["qualified"])
        self.assertNotEqual(record["parcel"]["provenance"]["geometry_id"],
                            record["zoning"]["provenance"]["geometry_id"])

    def test_two_panels_are_drawn_and_they_are_distinguishable(self):
        """Section 3. Property geometry and regulatory geometry must not share
        an indistinguishable rendering."""
        kinds = [p["kind"] for p in self.panels]
        self.assertIn(planning_visual.PANEL_PARCEL, kinds)
        self.assertIn(planning_visual.PANEL_ZONING, kinds)
        zoning = [p for p in self.panels
                  if p["kind"] == planning_visual.PANEL_ZONING][0]
        self.assertTrue(zoning["drawn"])
        # The zone is the layer; the parcel is drawn over it as the subject.
        self.assertIn("pz-panel-layer", zoning["svg"])
        self.assertIn("pz-panel-subject", zoning["svg"])

    def test_no_provenance_field_is_missing(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["missing_provenance"], [])


class FixtureB_SingleZoneWithException(unittest.TestCase):
    """Parcel inside one zone carrying a site-specific exception, text known."""

    def setUp(self):
        self.result = result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            exception_flagged=True,
            exception_record={"acquired": True, "text": "Exception 5 text."},
            statements=[zone_statement(
                CONTAINED + " A site-specific exception (5) applies.")])
        self.panels = planning_visual.panels_for(self.result["retrieval"])

    def test_the_exception_is_reported_as_retrieved(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["exception_status"],
                         acceptance.EXCEPTION_RESOLVED)

    def test_it_passes(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["state"], acceptance.PASS,
                         acceptance.summarize(record))

    def test_the_exception_is_kept_separate_from_the_parent_zone(self):
        """Section 9. Parent RD (f15.0; a550), exception 5 - not one blob."""
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["zoning"]["zone_label"], "RD (f15.0; a550)")
        self.assertEqual(record["zoning"]["exception_identifier"], "5")


class FixtureC_MultipleZones(unittest.TestCase):
    """Parcel intersects two or more zoning polygons."""

    def setUp(self):
        # The shape `toronto_gate01` really emits: every intersecting feature,
        # each carrying its own qualification, label and exception state.
        self.features = [
            {"geometry": polygon(ZONE_RING), "qualified": True,
             "zone_label": "RD (f15.0; a550)", "zone_code": "RD",
             "spatial_relation": "INTERSECTS", "geometry_id": "sha256:zone-a",
             "feature_identifier": "77", "source_crs": "EPSG:3857",
             "source": "City of Toronto Zoning Area (cot_geospatial11/3)",
             "layer": "Zoning Area",
             "exception_status": acceptance.EXCEPTION_NONE},
            {"geometry": polygon(STRADDLE_RING), "qualified": True,
             "zone_label": "CR 2.5", "zone_code": "CR",
             "spatial_relation": "INTERSECTS", "geometry_id": "sha256:zone-b",
             "feature_identifier": "78", "source_crs": "EPSG:3857",
             "source": "City of Toronto Zoning Area (cot_geospatial11/3)",
             "layer": "Zoning Area",
             "exception_status": acceptance.EXCEPTION_NONE}]

    def test_an_unqualified_single_zone_claim_fails(self):
        """Section 5: the result must not be reduced to one zone silently."""
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            zone_features=self.features,
            statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_MULTIZONE_REDUCED,
                      [f["code"] for f in record["failures"]])

    def test_the_relationship_reports_multiple_zones(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            zone_features=self.features,
            statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["relationship"],
                         acceptance.INTERSECTS_MULTIPLE_ZONES)

    def test_multiple_zones_outrank_an_inside_token(self):
        """A parcel can sit INSIDE one of two overlapping polygons. Reporting
        WITHIN_SINGLE_ZONE there is true of the polygon and false of the
        property, which is the whole failure section 5 describes."""
        self.assertEqual(
            acceptance.zone_relationship(_token(spatial.RELATION_INSIDE),
                                         zone_count=2),
            acceptance.INTERSECTS_MULTIPLE_ZONES)

    def test_a_qualified_multi_zone_statement_is_accepted(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INTERSECTS),
            zone_features=self.features,
            statements=[zone_statement(
                "The subject parcel is covered by more than one zone polygon "
                "labelled RD (f15.0; a550); multi-zone analysis is required.",
                multi_zone_qualified=True)]))
        self.assertNotIn(acceptance.F_MULTIZONE_REDUCED,
                         [f["code"] for f in record["failures"]])


    def test_both_zones_are_rendered_as_their_own_panels(self):
        """Section 5 and 7. One panel would visually assert that a single regime
        covers the whole property - the same substitution section 15 forbids,
        committed with zoning geometry instead of parcel geometry."""
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INTERSECTS),
                      zone_features=self.features,
                      statements=[])
        panels = planning_visual.panels_for(base["retrieval"])
        zoning = [p for p in panels
                  if p["kind"] == planning_visual.PANEL_ZONING]
        self.assertEqual(len(zoning), 2, "a multi-zone parcel drew one zone")
        for drawn in zoning:
            with self.subTest(title=drawn["title"]):
                self.assertTrue(drawn["drawn"])
                # The parcel is drawn over EVERY zone, because what a reader
                # needs to see is which part of the property each zone reaches.
                self.assertIn("pz-panel-subject", drawn["svg"])

    def test_each_zone_keeps_its_own_label_and_identity(self):
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INTERSECTS),
                      zone_features=self.features, statements=[])
        panels = [p for p in planning_visual.panels_for(base["retrieval"])
                  if p["kind"] == planning_visual.PANEL_ZONING]
        self.assertEqual([p["zone_label"] for p in panels],
                         ["RD (f15.0; a550)", "CR 2.5"])
        self.assertEqual([p["evidence_ref"] for p in panels],
                         ["sha256:zone-a", "sha256:zone-b"])
        # And each panel says which of how many it is, so neither reads as
        # "the" zoning.
        for drawn in panels:
            with self.subTest(title=drawn["title"]):
                self.assertIn("of 2", drawn["title"])

    def test_neither_panel_is_drawn_from_the_parcel(self):
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INTERSECTS),
                      zone_features=self.features, statements=[])
        panels = planning_visual.panels_for(base["retrieval"])
        record = acceptance.evaluate(base, panels=panels)
        self.assertNotIn(acceptance.F_PARCEL_AS_ZONING,
                         [f["code"] for f in record["failures"]])

    def test_a_zone_the_engine_could_not_place_does_not_make_it_multi_zone(self):
        """"Touches a mapped edge" and "is split between two regimes" are
        different findings with different consequences. An unqualified feature
        is retained as evidence and excluded from the count."""
        features = [dict(self.features[0]),
                    dict(self.features[1], qualified=False,
                         spatial_relation="AMBIGUOUS")]
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            zone_features=features,
            statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["relationship"], acceptance.WITHIN_SINGLE_ZONE)
        self.assertEqual(record["zoning"]["zone_count"], 1)

    def test_a_failed_intersection_query_is_not_read_as_one_zone(self):
        """The silent reduction, in its last hiding place. An empty feature list
        from a FAILED query must not be read as "asked, and one zone applies"."""
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INSIDE),
                      statements=[zone_statement(CONTAINED)])
        base["retrieval"]["zone_features"] = []
        base["retrieval"]["zone_features_examined"] = False
        record = acceptance.evaluate(base)
        self.assertFalse(record["zoning"]["multi_zone_examined"],
                         "a failed query was reported as an examination")


class FixtureD_ZoningGeometryUnavailable(unittest.TestCase):
    """Parcel available, zoning geometry unavailable. MUST NOT SUBSTITUTE."""

    def setUp(self):
        self.result = result(
            parcel_geometry=polygon(PARCEL_RING), zoning_geometry=None,
            token=None, statements=[])
        self.panels = planning_visual.panels_for(self.result["retrieval"])

    def test_the_state_is_partial_not_fail(self):
        """Absence is a state; only substitution and contradiction fail."""
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["state"], acceptance.PARTIAL,
                         acceptance.summarize(record))

    def test_the_relationship_says_no_qualified_zone_geometry(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["relationship"],
                         acceptance.NO_QUALIFIED_ZONE_GEOMETRY)

    def test_no_zoning_panel_is_drawn_from_the_parcel(self):
        """THE GOVERNING RULE. The renderer must not fall back to the parcel."""
        self.assertEqual(
            [p for p in self.panels
             if p["kind"] == planning_visual.PANEL_ZONING], [])

    def test_the_parcel_panel_is_still_drawn_and_still_says_what_it_is(self):
        parcel = [p for p in self.panels
                  if p["kind"] == planning_visual.PANEL_PARCEL][0]
        self.assertTrue(parcel["drawn"])
        self.assertEqual(parcel["title"], "Subject parcel")

    def test_a_parcel_panel_relabelled_as_zoning_is_caught(self):
        """The substitution this whole module exists to prevent, staged."""
        panels = list(self.panels)
        panels[0] = dict(panels[0], title="Official zoning shape")
        record = acceptance.evaluate(self.result, panels=panels)
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_PARCEL_AS_ZONING,
                      [f["code"] for f in record["failures"]])

    def test_a_zoning_panel_drawn_from_the_parcel_geometry_is_caught(self):
        """The same substitution by IDENTITY rather than by title."""
        parcel_id = spatial.geometry_hash(polygon(PARCEL_RING))
        panels = [planning_visual.panel(
            planning_visual.PANEL_ZONING, polygon(PARCEL_RING),
            title="Applicable zoning", source="City of Toronto Zoning Area",
            layer="Zoning Area", evidence_ref=parcel_id)]
        record = acceptance.evaluate(self.result, panels=panels)
        self.assertIn(acceptance.F_PARCEL_AS_ZONING,
                      [f["code"] for f in record["failures"]])


class FixtureE_LabelWithoutBoundGeometry(unittest.TestCase):
    """Zone label available, geometry unbound. Must remain provisional."""

    def test_a_bounded_provisional_statement_is_partial_not_fail(self):
        """Section 8's acceptable form: designation stated, geometry not bound."""
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING), zoning_geometry=None,
            token=None,
            statements=[zone_statement(
                "City zoning records identify the property with the designation "
                "RD (f15.0; a550), but the regulatory zoning geometry has not "
                "been independently bound in this result.")]))
        self.assertEqual(record["state"], acceptance.PARTIAL,
                         acceptance.summarize(record))

    def test_a_containment_claim_without_geometry_fails(self):
        """Section 7: containment is only eligible when the relation supports it."""
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING), zoning_geometry=None,
            token=None, statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_CONTAINMENT_UNPROVEN,
                      [f["code"] for f in record["failures"]])


class FixtureF_VisualTextMismatch(unittest.TestCase):
    """Must fail. Every arm here is a section 10 automatic failure."""

    def test_prose_names_a_zone_the_evidence_does_not_carry(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            zone_label="RD (f15.0; a550)",
            token=_token(spatial.RELATION_INSIDE),
            statements=[zone_statement(
                "The subject parcel lies within the zone labelled CR 2.5.")]))
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_ZONE_LABEL_MISMATCH,
                      [f["code"] for f in record["failures"]])

    def test_prose_cites_an_exception_nothing_binds(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            statements=[zone_statement(
                CONTAINED + " A site-specific exception applies.")]))
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_EXCEPTION_UNBOUND,
                      [f["code"] for f in record["failures"]])

    def test_zoning_evidence_exists_but_no_zoning_panel_was_drawn(self):
        record = acceptance.evaluate(
            result(parcel_geometry=polygon(PARCEL_RING),
                   zoning_geometry=polygon(ZONE_RING),
                   token=_token(spatial.RELATION_INSIDE),
                   statements=[zone_statement(CONTAINED)]),
            panels=[])
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_ZONING_OMITTED,
                      [f["code"] for f in record["failures"]])

    def test_the_panel_and_the_evidence_cite_different_sources(self):
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INSIDE),
                      statements=[zone_statement(CONTAINED)])
        panels = planning_visual.panels_for(base["retrieval"])
        panels = [dict(p, source="Some other municipality") if
                  p["kind"] == planning_visual.PANEL_ZONING else p
                  for p in panels]
        record = acceptance.evaluate(base, panels=panels)
        self.assertIn(acceptance.F_PROVENANCE_DIVERGED,
                      [f["code"] for f in record["failures"]])

    def test_exception_status_differs_between_visual_and_prose(self):
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INSIDE),
                      exception_flagged=True, exception_record=None,
                      statements=[zone_statement(
                          CONTAINED + " A site-specific exception (5) applies.")])
        panels = planning_visual.panels_for(base["retrieval"])
        panels = [dict(p, exception_status=acceptance.EXCEPTION_RESOLVED)
                  if p["kind"] == planning_visual.PANEL_ZONING else p
                  for p in panels]
        record = acceptance.evaluate(base, panels=panels)
        self.assertIn(acceptance.F_EXCEPTION_STATUS_DIVERGED,
                      [f["code"] for f in record["failures"]])


class FixtureG_ExceptionTextUnavailable(unittest.TestCase):
    """Exception label present, exception text unavailable."""

    def setUp(self):
        self.result = result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            exception_flagged=True, exception_record={"acquired": False},
            statements=[zone_statement(
                CONTAINED + " A site-specific exception (5) applies and its "
                "text has not been retrieved.")])
        self.panels = planning_visual.panels_for(self.result["retrieval"])

    def test_the_state_preserves_the_unresolved_exception(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["state"],
                         acceptance.PASS_WITH_UNRESOLVED_EXCEPTION,
                         acceptance.summarize(record))

    def test_the_status_is_explicitly_unresolved(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["exception_status"],
                         acceptance.EXCEPTION_TEXT_UNRESOLVED)

    def test_an_unresolved_exception_is_never_silently_a_pass(self):
        """Section 9: parent-zone standards must not be applied as though the
        exception did not exist, so the state itself has to carry the doubt."""
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertNotEqual(record["state"], acceptance.PASS)


class FixtureH_AdjacentZoningOnly(unittest.TestCase):
    """A nearby zone must not be assigned merely because it is visually close."""

    def setUp(self):
        self.result = result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(OTHER_ZONE_RING),
            token=_token(spatial.RELATION_OUTSIDE),
            statements=[])
        self.panels = planning_visual.panels_for(self.result["retrieval"])

    def test_an_outside_relation_yields_no_qualified_zone_geometry(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["relationship"],
                         acceptance.NO_QUALIFIED_ZONE_GEOMETRY)

    def test_the_state_is_partial(self):
        record = acceptance.evaluate(self.result, panels=self.panels)
        self.assertEqual(record["state"], acceptance.PARTIAL)

    def test_claiming_containment_against_an_adjacent_zone_fails(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(OTHER_ZONE_RING),
            token=_token(spatial.RELATION_OUTSIDE),
            statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["state"], acceptance.FAIL)
        self.assertIn(acceptance.F_CONTAINMENT_UNPROVEN,
                      [f["code"] for f in record["failures"]])


class TheRelationshipProjectionBorrowsRatherThanReimplements(unittest.TestCase):
    """Section 4 said to use existing governed equivalents. It does."""

    def test_boundary_touch_comes_from_the_engines_own_reason(self):
        self.assertEqual(
            acceptance.zone_relationship(
                _token(spatial.RELATION_AMBIGUOUS, spatial.REASON_NEAR_BOUNDARY)),
            acceptance.BOUNDARY_TOUCH)

    def test_missing_geometry_is_not_reported_as_ambiguous(self):
        self.assertEqual(
            acceptance.zone_relationship(
                _token(spatial.RELATION_AMBIGUOUS, spatial.REASON_MISSING)),
            acceptance.NO_QUALIFIED_ZONE_GEOMETRY)

    def test_every_other_refusal_is_ambiguous(self):
        for reason in (spatial.REASON_CRS_MISMATCH, spatial.REASON_INVALID,
                       spatial.REASON_CONFLICTING,
                       spatial.REASON_MULTIPLE_PARCELS):
            with self.subTest(reason=reason):
                self.assertEqual(
                    acceptance.zone_relationship(
                        _token(spatial.RELATION_AMBIGUOUS, reason)),
                    acceptance.AMBIGUOUS)

    def test_no_second_spatial_engine_was_written(self):
        """The rule from CLAUDE.md: identify what already serves the purpose."""
        from pathlib import Path

        source = Path("services/planning_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("from services import deterministic_spatial", source)
        for reinvention in ("def relate(", "def _point_in_ring", "def _bbox",
                            "def geometry_hash"):
            with self.subTest(reinvention=reinvention):
                self.assertNotIn(reinvention, source)

    def test_the_five_states_are_exactly_the_ones_asked_for(self):
        self.assertEqual(
            {acceptance.WITHIN_SINGLE_ZONE, acceptance.INTERSECTS_MULTIPLE_ZONES,
             acceptance.BOUNDARY_TOUCH, acceptance.NO_QUALIFIED_ZONE_GEOMETRY,
             acceptance.AMBIGUOUS},
            {"WITHIN_SINGLE_ZONE", "INTERSECTS_MULTIPLE_ZONES", "BOUNDARY_TOUCH",
             "NO_QUALIFIED_ZONE_GEOMETRY", "AMBIGUOUS"})


class TheAcceptanceStatesBehaveAsSection12Describes(unittest.TestCase):

    def test_the_four_states_are_the_ones_asked_for(self):
        self.assertEqual(
            {acceptance.PASS, acceptance.PASS_WITH_UNRESOLVED_EXCEPTION,
             acceptance.PARTIAL, acceptance.FAIL},
            {"PASS", "PASS_WITH_UNRESOLVED_EXCEPTION", "PARTIAL", "FAIL"})

    def test_a_failure_always_outranks_an_incomplete_result(self):
        """Contradiction is worse than absence, and must not be masked by it."""
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING), zoning_geometry=None,
            token=None, statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["state"], acceptance.FAIL)

    def test_incomplete_provenance_is_partial_rather_than_fail(self):
        """Section 6. Unauditable is not the same as untrue."""
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            token=_token(spatial.RELATION_INSIDE),
            complete_provenance=False,
            statements=[zone_statement(CONTAINED)]))
        self.assertEqual(record["state"], acceptance.PARTIAL)
        self.assertIn("spatial_reference", record["missing_provenance"])

    def test_an_empty_result_does_not_raise(self):
        record = acceptance.evaluate({})
        self.assertEqual(record["state"], acceptance.PARTIAL)

    def test_every_failure_carries_its_own_evidence(self):
        record = acceptance.evaluate(result(
            parcel_geometry=polygon(PARCEL_RING), zoning_geometry=None,
            token=None, statements=[zone_statement(CONTAINED)]))
        for failure in record["failures"]:
            with self.subTest(code=failure["code"]):
                self.assertGreater(len(failure), 1,
                                   "a bare failure code tells the reader nothing")


class TheDisplayVocabularyIsReviewedSeparately(unittest.TestCase):
    """Section 11. Wording is reported, never folded into the evidence state."""

    def test_the_preferred_labels_are_recognised(self):
        review = acceptance.label_review(
            "Subject Parcel / Applicable Zoning / Site-Specific Exception / "
            "Official Zoning Source")
        self.assertEqual(review["missing"], [])

    def test_ambiguous_labels_are_reported(self):
        review = acceptance.label_review("Property Map and Zone Shape")
        self.assertEqual(sorted(review["discouraged_present"]),
                         ["Property Map", "Zone Shape"])

    def test_wording_does_not_change_the_acceptance_state(self):
        base = result(parcel_geometry=polygon(PARCEL_RING),
                      zoning_geometry=polygon(ZONE_RING),
                      token=_token(spatial.RELATION_INSIDE),
                      statements=[zone_statement(CONTAINED)])
        panels = planning_visual.panels_for(base["retrieval"])
        self.assertEqual(acceptance.evaluate(base, panels=panels)["state"],
                         acceptance.PASS)


class Section14_TheCassidyValidationCase(unittest.TestCase):
    """The real retrieval, pinned as a fixture rather than re-fetched.

    NOT A LIVE REQUEST. The suite is hermetic; this is what the City of Toronto
    actually served for 1 Cassidy Pl on 2026-09-14, recorded so the acceptance
    rules are exercised against a real result shape instead of only against
    shapes this file invented.

    THE STATEMENT KEYS ARE THE POINT. A finished GO-PDZ document carries
    topic / kind / statement_status / spatial_relation and NOT `spatial_layer`,
    which the runner uses internally. An earlier selector keyed on
    `spatial_layer` matched nothing here, leaving every prose check vacuously
    satisfied - a false PASS on every real result, which is the one outcome an
    acceptance test may never produce.

    The address is used only as a validation fixture. The capability is not
    hard-coded to it, which is what every other class in this file demonstrates.
    """

    #: Verbatim from the live retrieval.
    ZONE_LABEL = "RD (f15.0; a550) (x5)"
    ZONE_CODE = "RD"
    EXCEPTION_NUMBER = "5"
    PARCEL_IDENTIFIER = "TOR-PARCEL-5185650"

    ZONE_TEXT = ("The subject parcel lies within a zone labelled "
                 "'RD (f15.0; a550) (x5)' (zone code 'RD') on the City of "
                 "Toronto zoning mapping, Chapter 900, Section 900.3.10.")
    EXCEPTION_TEXT = ("A site-specific exception (5, 900.3.10(5)) applies to "
                      "this zone and ITS TEXT COULD NOT BE RETRIEVED.")

    def _result(self, **overrides):
        base = dict(
            parcel_geometry=polygon(PARCEL_RING),
            zoning_geometry=polygon(ZONE_RING),
            zone_label=self.ZONE_LABEL, zone_code=self.ZONE_CODE,
            token=_token(spatial.RELATION_INSIDE),
            exception_flagged=True, exception_record={"acquired": False},
            exception_number=self.EXCEPTION_NUMBER,
            statements=[
                # The REAL key set - note the absence of `spatial_layer`.
                {"statement_id": "S-ZONE", "kind": "AUTHORITY_SAYS",
                 "topic": "ZONING_DESIGNATION", "statement_status": "ESTABLISHED",
                 "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
                 "text": self.ZONE_TEXT},
                {"statement_id": "S-ZONE-EXCEPTION", "kind": "AUTHORITY_SAYS",
                 "topic": "SITE_SPECIFIC_EXCEPTION",
                 "statement_status": "PROVISIONAL",
                 "text": self.EXCEPTION_TEXT},
            ])
        base.update(overrides)
        return result(**base)

    def test_the_zone_statement_is_found_without_a_spatial_layer_field(self):
        """The regression the live run exposed."""
        found = acceptance._zoning_statements(self._result())   # noqa: SLF001
        self.assertTrue(found, "no zoning statement was selected from a REAL "
                               "document shape; every prose check would be "
                               "vacuously satisfied")
        self.assertIn("S-ZONE", [s["statement_id"] for s in found])
        self.assertIn("S-ZONE-EXCEPTION", [s["statement_id"] for s in found])

    def test_no_selected_statement_relies_on_spatial_layer(self):
        for statement in self._result()["document"]["statements"]:
            with self.subTest(statement=statement["statement_id"]):
                self.assertIsNone(statement.get("spatial_layer"))

    def test_the_exception_is_preserved_separately_from_the_parent_zone(self):
        """Section 9. Parent RD (f15.0; a550), exception x5 - and the City's own
        label carries both, so the two must be separable from one string."""
        record = acceptance.evaluate(self._result())
        self.assertEqual(record["zoning"]["zone_code"], "RD")
        self.assertEqual(record["zoning"]["exception_identifier"], "5")
        self.assertEqual(record["exception_status"],
                         acceptance.EXCEPTION_TEXT_UNRESOLVED)

    def test_containment_is_eligible_because_the_engine_proved_it(self):
        """Section 7. The live token was INSIDE, deterministically."""
        record = acceptance.evaluate(self._result())
        self.assertEqual(record["relationship"], acceptance.WITHIN_SINGLE_ZONE)
        self.assertNotIn(acceptance.F_CONTAINMENT_UNPROVEN,
                         [f["code"] for f in record["failures"]])

    def test_with_complete_provenance_it_reaches_the_exception_state(self):
        """What the live result WOULD be once section 6's fields are carried:
        PASS_WITH_UNRESOLVED_EXCEPTION, not PASS, because exception 5's text is
        genuinely unavailable from the City."""
        record = acceptance.evaluate(self._result())
        self.assertEqual(record["state"],
                         acceptance.PASS_WITH_UNRESOLVED_EXCEPTION,
                         acceptance.summarize(record))

    def test_the_live_result_is_partial_until_the_evidence_carries_its_crs(self):
        """MEASURED, NOT PREDICTED. The live run returned PARTIAL for exactly
        this reason: `retrieval.visual_geometry` carries no spatial reference
        and no zone feature identifier, so section 6's provenance cannot be
        audited end to end. Every other requirement was met."""
        record = acceptance.evaluate(self._result(complete_provenance=False))
        self.assertEqual(record["state"], acceptance.PARTIAL)
        self.assertIn("spatial_reference", record["missing_provenance"])
        self.assertEqual(record["failures"], [],
                         "the live result was incomplete, never contradictory")

    def test_the_capability_is_not_hard_coded_to_this_address(self):
        """Scanned on CODE, not on the file's characters.

        The fourteenth vocabulary false positive in this programme, and it was
        this test catching my own comment: the module records that its statement
        selector was corrected against a live Cassidy retrieval, which is
        PROVENANCE rather than hard-coding. Docstrings and comments are stripped
        so the assertion is about what the module BRANCHES ON.
        """
        import ast
        from pathlib import Path

        tree = ast.parse(
            Path("services/planning_acceptance.py").read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                first = (node.body or [None])[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add(id(first.value))

        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and id(n) not in docstrings]
        for specific in ("Cassidy", self.PARCEL_IDENTIFIER, "f15.0", "a550",
                         self.ZONE_CODE):
            with self.subTest(specific=specific):
                self.assertFalse(
                    [lit for lit in literals if specific in lit],
                    "%r is used in executable code, so the evaluator is bound "
                    "to one property" % specific)


if __name__ == "__main__":
    unittest.main()
