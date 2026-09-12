"""CLAUDE-GENERALIZATION-02 - what two more live addresses changed, pinned.

Three live subjects have now run: an industrial parcel in Etobicoke, a
commercial-residential parcel on a Toronto Avenue inside a Protected Major
Transit Station Area, and a split-zoned residential parcel in Mississauga. Each
found a defect the previous one could not, and every defect had the same shape:

    THE OUTPUT WAS MORE CONFIDENT THAN THE EVIDENCE, AND NOTHING LOOKED WRONG.

  - A site-specific exception existed and was reported as nothing at all,
    because the only exception statement the builder could emit was the one for
    "no exception".
  - The by-law was hard-coded to 569-2013 while the City's own record named
    266-2021 for that zone. Both citations read identically to a reviewer.
  - A hosting platform was on the OFFICIAL allowlist, so any individual's
    uploaded layer could have grounded AUTHORITY_SAYS.
  - A zone was reported ESTABLISHED / HIGH from an address-POINT query while two
    zones touched the parcel.
  - Heritage was reported as un-computable proximity when the layer was polygons
    and containment was computable all along.

Every test here pins one of those, and they are hermetic: no test in this file
reaches a network.
"""
from __future__ import annotations

import json
import unittest
import urllib.parse

from services import deterministic_spatial as spatial
from services import mississauga_planning_source as miss
from services import planning_authority as authority
from services import go_pdz_lifecycle as lifecycle
from services import go_pdz_validator as validator
from services import toronto_gate01
from services import toronto_planning_source as toronto


def _ring(x, y, size, clockwise=True):
    ring = [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]
    return ring if clockwise else list(reversed(ring))


class FakeArcGis:
    """Answers by URL shape, like the real services do."""

    def __init__(self, responses=None, names=None, catalogue=None):
        self.responses = responses or {}
        self.names = names or {}
        self.catalogue = catalogue
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if miss.CATALOGUE_URL in url:
            if self.catalogue is None:
                raise OSError("catalogue unavailable")
            return json.dumps(self.catalogue).encode("utf-8")
        if "/query?" in url:
            for key, payload in self.responses.items():
                if key in url:
                    return json.dumps(payload).encode("utf-8")
            return json.dumps({"features": []}).encode("utf-8")
        path = urllib.parse.urlparse(url).path
        for key, name in self.names.items():
            if key in path:
                return json.dumps({"name": name,
                                   "geometryType": "esriGeometryPolygon",
                                   "extent": {"spatialReference":
                                              {"latestWkid": 26917}}}).encode("utf-8")
        return json.dumps({"name": "Unknown"}).encode("utf-8")


NAMES = {"/Address/FeatureServer/0": "Address",
         "/Parcel/FeatureServer/0": "Parcel",
         "/2022_Zoning/FeatureServer/0": "Zoning",
         "/MississaugaOfficialPlan_2010_LandUse_Schedule_10/FeatureServer/1":
             "MississaugaOfficialPlan_2010_LandUse_Sch10"}

CATALOGUE = {"dataset": [
    {"title": "Zoning", "distribution": [
        {"accessURL": miss.ORG + "/2022_Zoning/FeatureServer/0"}]},
    {"title": "Parcels", "distribution": [
        {"accessURL": miss.ORG + "/Parcel/FeatureServer/0"}]}]}


class AHostingPlatformIsNotAnAuthority(unittest.TestCase):
    """The allowlist hole a live ArcGIS Online search exposed."""

    HOSTED = miss.ORG + "/2022_Zoning/FeatureServer/0/query"

    def test_unattested_hosted_geometry_cannot_ground_a_determination(self):
        classification = authority.classify_source(self.HOSTED)
        self.assertEqual(classification["source_class"], authority.CLASS_SECONDARY)

    def test_an_official_catalogue_attests_to_its_own_publications(self):
        classification = authority.classify_source(
            self.HOSTED, attested_by=miss.CATALOGUE_URL)
        self.assertEqual(classification["source_class"], authority.CLASS_OFFICIAL)
        self.assertEqual(classification["attested_by"], miss.CATALOGUE_URL)

    def test_a_non_official_catalogue_cannot_promote_anything(self):
        """Otherwise the attestation would be the hole, not the fix."""
        for catalogue in ("https://somebody.wordpress.com/datasets",
                          "https://lexology.com/list",
                          "https://services.arcgis.com/other/catalogue"):
            classification = authority.classify_source(
                self.HOSTED, attested_by=catalogue)
            self.assertEqual(classification["source_class"],
                             authority.CLASS_SECONDARY, catalogue)

    def test_the_attestation_is_recorded_on_the_authority(self):
        record = authority.authority_record(
            authority_id="X", issuing_authority="City", official_title="T",
            url=self.HOSTED, retrieved_at="2026-09-12T00:00:00Z",
            payload=b"{}", attested_by=miss.CATALOGUE_URL)
        self.assertEqual(record["source_class"], authority.CLASS_OFFICIAL)
        self.assertEqual(record["attested_by"], miss.CATALOGUE_URL)
        self.assertTrue(authority.may_satisfy_authority_says(record))

    def test_read_access_is_not_authority(self):
        """`live_reader(attested_by=...)` grants ACCESS; the record decides authority."""
        reader = toronto.live_reader(attested_by=miss.CATALOGUE_URL)
        self.assertIsNotNone(reader)
        unattested = authority.classify_source(self.HOSTED)["source_class"]
        self.assertEqual(unattested, authority.CLASS_SECONDARY,
                         "classification must not be changed by reader config")


class AbsenceOfGeometryIsNotAbsenceOfAuthority(unittest.TestCase):
    """Section 3/4. A PDF-only Official Plan still governs the site."""

    def test_source_types_separate_what_may_be_asserted(self):
        self.assertIn(authority.SOURCE_TYPE_MACHINE_READABLE,
                      authority.DETERMINISTIC_SOURCE_TYPES)
        for kind in (authority.SOURCE_TYPE_MAP_SCHEDULE,
                     authority.SOURCE_TYPE_CONSOLIDATED_DOCUMENT,
                     authority.SOURCE_TYPE_WEB_MAP,
                     authority.SOURCE_TYPE_POLICY_DOCUMENT):
            self.assertNotIn(kind, authority.DETERMINISTIC_SOURCE_TYPES)

    def test_a_document_authority_is_admitted_and_flagged(self):
        record = authority.authority_record(
            authority_id="TOR-OFFICIAL-PLAN", issuing_authority="City of Toronto",
            official_title="Official Plan", url="https://www.toronto.ca/op.pdf",
            retrieved_at="2026-09-12T00:00:00Z", payload=b"%PDF",
            source_type=authority.SOURCE_TYPE_MAP_SCHEDULE,
            basis_confidence="LOW", limitation="map schedules only")
        self.assertTrue(authority.may_satisfy_authority_says(record),
                        "a real Plan is an authority even without polygons")
        self.assertFalse(record["supports_deterministic_spatial"])
        self.assertEqual(record["basis_confidence"], "LOW")

    def test_the_contract_can_carry_a_document_designation_finding(self):
        """APPEARS_INSIDE / VISUAL_IMPRESSION exist for exactly this case."""
        from services.go_pdz_contract import SPATIAL_BASES, SPATIAL_RELATIONS
        self.assertIn("APPEARS_INSIDE", SPATIAL_RELATIONS)
        self.assertIn("VISUAL_IMPRESSION", SPATIAL_BASES)


class VR16CountsAuthoritiesNotCitations(unittest.TestCase):
    """It fired once per citation, so one deficient by-law reported six times."""

    def _document(self, authorities, statements):
        return {"contract": "GO-PDZ-1.0-ONEPAGE", "schema_version": "1.0",
                "gate": "GATE_01_ADDRESS_ONLY_ENVELOPE",
                "next_authorized_gate": "GATE_02_OWNER_PROGRAM_ENTRY",
                "subject": {"subject_id": "S", "address_as_given": "A",
                            "identity_confidence": "HIGH"},
                "authorities": authorities, "statements": statements,
                "site_specific_exceptions": [], "unresolved": [],
                "result_status": "GOVERNED_RESULT"}

    def test_one_deficient_authority_reports_once_however_often_it_is_cited(self):
        authorities = [{"authority_id": "A", "name": "By-law",
                        "authority_status": "IN_FORCE"}]
        statements = [{"statement_id": "S%d" % i, "kind": "AUTHORITY_SAYS",
                       "topic": "T", "text": "t", "authority_refs": ["A"],
                       "statement_status": "PROVISIONAL", "confidence": "MEDIUM",
                       "spatial_relation": "NOT_APPLICABLE",
                       "spatial_basis": "NONE", "conflict_refs": [],
                       "derived_from": []} for i in range(6)]
        outcome = validator.validate(self._document(authorities, statements))
        vr16 = [f for f in outcome["findings"] if f.get("rule_id") == "VR-16"]
        self.assertEqual(len(vr16), 1,
                         "six citations of one authority is one deficiency")

    def test_a_version_satisfies_the_rule_its_own_message_offers(self):
        authorities = [{"authority_id": "A", "name": "Official Plan",
                        "authority_status": "IN_FORCE",
                        "version_identifier": "June 2026 Consolidation"}]
        outcome = validator.validate(self._document(authorities, []))
        self.assertEqual([f for f in outcome["findings"]
                          if f.get("rule_id") == "VR-16"], [])

    def test_an_authority_with_neither_still_reports(self):
        authorities = [{"authority_id": "A", "name": "N",
                        "authority_status": "IN_FORCE"}]
        outcome = validator.validate(self._document(authorities, []))
        self.assertEqual(len([f for f in outcome["findings"]
                              if f.get("rule_id") == "VR-16"]), 1)


class AnExceptionMustFailClosed(unittest.TestCase):
    """The defect the second live subject exposed, pinned."""

    def _gathered(self, attributes, exception_outcome=None):
        return {"zoning": {"present": True, "attributes": attributes},
                "authority": {"record": {"authority_id": "TOR-BYLAW-266-2021"}},
                "exception": exception_outcome, "overlays": [], "resolved": {},
                "official_plan": None, "heritage_register": None}

    PRESENT = {"ZN_ZONE": "CR", "ZN_STRING": "CR 3.0 (x2219)", "ZBL_CHAPTER": "40",
               "ZBL_SECTION": "40.10", "ZN_EXCPTN": "Y", "ZN_EXCPTN_NO": 2219,
               "ZBL_EXCPTN": "900.11.10(2219)"}

    def test_an_unretrieved_exception_produces_an_unresolved_statement(self):
        statements = toronto_gate01._zoning_statements(self._gathered(
            self.PRESENT, {"acquired": False, "reason": "not published there"}))
        exception = [s for s in statements
                     if s["topic"] == "SITE_SPECIFIC_EXCEPTION"]
        self.assertEqual(len(exception), 1, "silence is not an option")
        self.assertEqual(exception[0]["statement_status"], "UNRESOLVED")
        self.assertIn("COULD NOT BE RETRIEVED", exception[0]["text"])
        self.assertIn("must NOT be applied", exception[0]["text"])

    def test_an_unretrieved_exception_fails_the_result_closed(self):
        exceptions = toronto_gate01._exceptions(self._gathered(
            self.PRESENT, {"acquired": False, "reason": "shell page"}))
        self.assertEqual(len(exceptions), 1)
        self.assertFalse(exceptions[0]["text_retrieved"])
        built = lifecycle.assemble(
            identity={"subject_id": "S", "address_as_given": "A",
                      "identity_confidence": "HIGH"},
            authority_records=[], statements=[],
            site_specific_exceptions=exceptions)
        self.assertEqual(built["document"]["result_status"], "UNRESOLVED")

    def test_no_exception_is_still_stated_explicitly(self):
        absent = dict(self.PRESENT, ZN_EXCPTN="N", ZN_EXCPTN_NO=None)
        statements = toronto_gate01._zoning_statements(self._gathered(absent))
        exception = [s for s in statements
                     if s["topic"] == "SITE_SPECIFIC_EXCEPTION"]
        self.assertEqual(len(exception), 1)
        self.assertEqual(exception[0]["statement_status"], "ESTABLISHED")


class TheCitationMustNameTheRightInstrument(unittest.TestCase):
    """Hard-coding 569-2013 was correct once and wrong immediately after."""

    def test_the_bylaw_comes_from_the_city_s_own_link(self):
        url, identifier, _title = toronto.zoning_bylaw_url_for(
            {"BYLAW_DOCLINK": "2021/law0266.pdf"})
        self.assertTrue(url.endswith("2021/law0266.pdf"))
        self.assertEqual(identifier, "TOR-BYLAW-266-2021")

    def test_a_missing_link_falls_back_without_inventing(self):
        url, identifier, _title = toronto.zoning_bylaw_url_for({})
        self.assertEqual(url, toronto.ZONING_BYLAW_URL)
        self.assertEqual(identifier, "TOR-ZBL-569-2013")

    def test_statements_cite_the_record_that_was_actually_acquired(self):
        gathered = {"zoning": {"present": True,
                               "attributes": {"ZN_ZONE": "CR", "ZN_STRING": "CR",
                                              "ZBL_CHAPTER": "40",
                                              "ZBL_SECTION": "40.10",
                                              "ZN_EXCPTN": "N"}},
                    "authority": {"record": {"authority_id": "TOR-BYLAW-266-2021"}},
                    "exception": None}
        for statement in toronto_gate01._zoning_statements(gathered):
            if statement["kind"] == "AUTHORITY_SAYS":
                self.assertEqual(statement["authority_refs"],
                                 ["TOR-BYLAW-266-2021"])

    def test_with_no_acquired_authority_nothing_is_established(self):
        """VR-19 would catch a dangling ref; better not to emit one."""
        gathered = {"zoning": {"present": True,
                               "attributes": {"ZN_ZONE": "CR", "ZN_STRING": "CR",
                                              "ZBL_CHAPTER": "40",
                                              "ZBL_SECTION": "40.10",
                                              "ZN_EXCPTN": "N"}},
                    "authority": {"record": None}, "exception": None}
        statements = toronto_gate01._zoning_statements(gathered)
        self.assertEqual(statements[0]["authority_refs"], [])
        self.assertEqual(statements[0]["statement_status"], "PROVISIONAL")


class AskAboutTheParcelNotTheDot(unittest.TestCase):
    """Split zoning: the third subject's defect."""

    SUBJECT = {"type": "Polygon",
               "coordinates": [[[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]]}

    def _reader(self, zone_features):
        return FakeArcGis(names=NAMES, catalogue=CATALOGUE, responses={
            "esriGeometryPolygon": {"features": zone_features},
            "esriGeometryPoint": {"features": zone_features[:1]}})

    def test_two_zones_touching_the_parcel_are_both_returned(self):
        zones = [{"attributes": {"ZONE_CODE": "RL-62"},
                  "geometry": {"rings": [_ring(-50, -50, 100)]}},
                 {"attributes": {"ZONE_CODE": "RL-61"},
                  "geometry": {"rings": [_ring(50, 50, 100)]}}]
        finding = miss.zoning_at(self.SUBJECT, {"x": 10, "y": 10},
                                 reader=self._reader(zones))
        self.assertEqual(finding["zone_count"], 2)
        self.assertTrue(finding["split"])

    def test_a_split_parcel_asserts_no_zone(self):
        gathered = {"resolved": {}, "zoning": {"present": True, "split": True,
                                               "zone_count": 2,
                                               "zones": [
                                                   {"attributes": {"ZONE_CODE": "RL-62"},
                                                    "token": {"spatial_relation":
                                                              "INTERSECTS"}},
                                                   {"attributes": {"ZONE_CODE": "RL-61"},
                                                    "token": {"spatial_relation":
                                                              "INTERSECTS"}}]},
                    "land_use": {}, "overlays": [], "heritage": {},
                    "authority": {}, "official_plan": {}, "publication": {}}
        from services import mississauga_gate01
        statements = mississauga_gate01._statements(gathered)
        zone = [s for s in statements if s["statement_id"] == "S-ZONE"][0]
        self.assertEqual(zone["statement_status"], "UNRESOLVED")
        self.assertEqual(zone["kind"], "PROPERTY_FACT")
        self.assertIn("no single zone", zone["text"])
        self.assertNotIn("authority_refs", zone)

    def test_a_split_parcel_raises_a_material_unresolved_issue(self):
        from services import mississauga_gate01
        issues = mississauga_gate01._unresolved(
            {"zoning": {"split": True}, "overlays": [],
             "attestation": {"attested": True}})
        split = [i for i in issues if i["issue_id"] == "U-SPLIT-ZONING"]
        self.assertEqual(len(split), 1)
        self.assertEqual(split[0]["materiality"], "MATERIAL")

    def test_one_zone_is_still_established(self):
        zones = [{"attributes": {"ZONE_CODE": "RL-62",
                                 "ZONE_DESCRIPTION": "Large Lot",
                                 "BYLAW": "0225-2007",
                                 "BASE_ZONE_DESIGNATION": "RL"},
                  "geometry": {"rings": [_ring(-50, -50, 300)]}}]
        finding = miss.zoning_at(self.SUBJECT, {"x": 10, "y": 10},
                                 reader=self._reader(zones))
        self.assertEqual(finding["zone_count"], 1)
        self.assertFalse(finding["split"])
        self.assertEqual(finding["zones"][0]["token"]["spatial_relation"],
                         spatial.RELATION_INSIDE)


class ProximityWasTheWrongQuestion(unittest.TestCase):
    """Mississauga's heritage layer is polygons, so containment is computable."""

    SUBJECT = {"type": "Polygon",
               "coordinates": [[[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]]}

    def _reader(self, features):
        return FakeArcGis(names=NAMES, catalogue=CATALOGUE,
                          responses={"esriGeometryPolygon": {"features": features}})

    def test_a_covering_heritage_polygon_is_computed_not_counted(self):
        covering = [{"attributes": {"HERC_DESCRIPTION": "LISTED"},
                     "geometry": {"rings": [_ring(-50, -50, 300)]}}]
        finding = miss.heritage_at(self.SUBJECT, reader=self._reader(covering))
        self.assertTrue(finding["checked"])
        self.assertEqual(len(finding["covering"]), 1)
        self.assertIn("deterministic", finding["basis"])

    def test_a_nearby_but_separate_polygon_does_not_cover(self):
        nearby = [{"attributes": {"HERC_DESCRIPTION": "LISTED"},
                   "geometry": {"rings": [_ring(500, 500, 50)]}}]
        finding = miss.heritage_at(self.SUBJECT, reader=self._reader(nearby))
        self.assertEqual(finding["covering"], [])
        self.assertEqual(finding["touching"], 1)


class TheTransformationIsRecordedNotHidden(unittest.TestCase):
    """Mississauga publishes its own layers in two different CRSs."""

    def test_an_upstream_reprojection_is_named_in_the_provenance(self):
        token = spatial.relate(
            {"crs": "EPSG:26917", "geometry": {
                "type": "Polygon", "coordinates": [_ring(0, 0, 10, False)]}},
            {"crs": "EPSG:26917", "geometry": {
                "type": "Polygon", "coordinates": [_ring(-50, -50, 200, False)]}},
            upstream_transformation=miss.TRANSFORMATION_NOTE)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["provenance"]["transformation"],
                         miss.TRANSFORMATION_NOTE)
        self.assertIn("publishing authority",
                      token["provenance"]["transformed_by"])

    def test_none_still_means_nothing_was_transformed(self):
        token = spatial.relate(
            {"crs": "EPSG:26917", "geometry": {
                "type": "Polygon", "coordinates": [_ring(0, 0, 10, False)]}},
            {"crs": "EPSG:26917", "geometry": {
                "type": "Polygon", "coordinates": [_ring(-50, -50, 200, False)]}})
        self.assertIsNone(token["provenance"]["transformation"])
        self.assertIsNone(token["provenance"]["transformed_by"])

    def test_a_crs_mismatch_is_still_refused(self):
        """Recording an upstream transform must not become licence to reproject."""
        token = spatial.relate(
            {"crs": "EPSG:3857", "geometry": {
                "type": "Polygon", "coordinates": [_ring(0, 0, 10, False)]}},
            {"crs": "EPSG:26917", "geometry": {
                "type": "Polygon", "coordinates": [_ring(-50, -50, 200, False)]}},
            upstream_transformation="claimed")
        self.assertEqual(token["spatial_relation"], spatial.RELATION_AMBIGUOUS)
        self.assertEqual(token["reason"], spatial.REASON_CRS_MISMATCH)


class TheSecondMunicipalityIsHermeticToo(unittest.TestCase):

    def test_no_reader_has_a_default(self):
        import inspect
        for name in ("verify_layer", "query_layer", "resolve_address", "zoning_at",
                     "land_use_at", "overlay_findings", "heritage_at",
                     "catalogue_attestation", "acquire_zoning_bylaw",
                     "acquire_official_plan", "acquire_geospatial_publication"):
            signature = inspect.signature(getattr(miss, name))
            parameter = signature.parameters.get("reader")
            self.assertIsNotNone(parameter, "%s must take a reader" % name)
            self.assertIs(parameter.default, inspect.Parameter.empty, name)

    def test_a_drifted_layer_name_is_refused(self):
        reader = FakeArcGis(names={"/2022_Zoning/FeatureServer/0": "Something Else"},
                            catalogue=CATALOGUE)
        with self.assertRaises(miss.LayerIdentityError):
            miss.verify_layer(miss.LAYER_ZONING, reader=reader)

    def test_an_unreadable_catalogue_leaves_the_platform_secondary(self):
        reader = FakeArcGis(names=NAMES, catalogue=None)
        attestation = miss.catalogue_attestation(reader=reader)
        self.assertFalse(attestation["attested"])
        self.assertIsNone(attestation["attested_by"])

    def test_an_unattested_publication_raises_a_material_issue(self):
        from services import mississauga_gate01
        issues = mississauga_gate01._unresolved(
            {"attestation": {"attested": False}, "overlays": [], "zoning": {}})
        flagged = [i for i in issues
                   if i["issue_id"] == "U-PUBLICATION-ATTESTATION"]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["materiality"], "MATERIAL")

    def test_the_parcel_is_found_by_attribute_join_not_geometry(self):
        reader = FakeArcGis(names=NAMES, catalogue=CATALOGUE, responses={
            "/Address/FeatureServer/0/query": {
                "features": [{"attributes": {"ADDR_ID": 1, "STNO": "5198",
                                             "STNAME": "MISSISSAUGA",
                                             "FULLNAME": "5198 MISSISSAUGA RD",
                                             "CITY_PIN": 4251200, "WARD": "W11"},
                              "geometry": {"x": 1.0, "y": 2.0}}]},
            "/Parcel/FeatureServer/0/query": {
                "features": [{"attributes": {"CITY_PIN": 4251200,
                                             "GIS_AREA": 1187.55},
                              "geometry": {"rings": [_ring(0, 0, 50)]}}]}})
        resolved = miss.resolve_address("5198 Mississauga Road, Mississauga",
                                        reader=reader)
        self.assertEqual(resolved["parcel_identifier"], "MISS-PIN-4251200")
        self.assertEqual(resolved["resolution_method"],
                         "attribute join on CITY_PIN")
        joined = [c for c in reader.calls if "CITY_PIN%3D4251200" in c]
        self.assertTrue(joined, "the parcel must be fetched by CITY_PIN")

    def test_the_street_suffix_is_dropped_the_way_this_city_stores_it(self):
        self.assertEqual(miss._split_address("5198 Mississauga Road, Mississauga"),
                         ("5198", "MISSISSAUGA"))
        self.assertEqual(miss._split_address("5198 Mississauga Rd"),
                         ("5198", "MISSISSAUGA"))
        for bad in (None, "", "Mississauga", "Mississauga Road", 5198):
            self.assertEqual(miss._split_address(bad), (None, None))


if __name__ == "__main__":
    unittest.main()
