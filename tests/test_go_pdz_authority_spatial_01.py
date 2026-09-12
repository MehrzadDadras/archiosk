"""CLAUDE-GO-PDZ-AUTHORITY-01 / SPATIAL-01 / LIFECYCLE-01: the two blockers, closed.

GO-PDZ shipped as a contract with no producer: it required retrievable
authorities and deterministic geometry, and ARCHIOSK could supply neither. That
is why the blind 35 Taber run had to be performed outside the application. These
tests cover the two seams that close it, and the lifecycle that joins them.

What they defend, in the order the mistakes would be made:

1. **A SEARCH RESULT IS NOT AN AUTHORITY.** The allowlist is the whole point, and
   the interesting case is not the blog - it is the law-firm bulletin that is
   genuinely informative and still not the statute. `SourceClassification` keeps
   OFFICIAL / SECONDARY / REJECTED distinct, and `may_satisfy_authority_says`
   makes SECONDARY structurally incapable of grounding a claim.

2. **GO CONSUMES THE MAP; GO DOES NOT INVENT IT.** The spatial engine's most
   important property is what it refuses. Every section 10 edge condition has a
   named AMBIGUOUS outcome here, and `TheEngineRefusesWhatItCannotDecide` is the
   largest class because a planning result that guesses at a polygon with holes
   is worse than one that says it cannot tell - the first is indistinguishable
   from an answer.

3. **AN AUTHORITY IS NOT ITS PROSE.** A record with no retained representation
   and no hash is a paraphrase, and cannot be re-checked against the source.

4. **CURRENT IS NOT APPLICABLE.** `ADOPTED_NOT_IN_FORCE` exists because Toronto's
   OPA 804 is adopted and awaiting ministerial approval; binding it and ignoring
   it are both wrong.

Every fetcher and resolver is injected. Nothing here reaches a network.
"""
from __future__ import annotations

import unittest

from services import deterministic_spatial as spatial
from services import go_pdz_lifecycle as lifecycle
from services import planning_authority as authority
from services import go_pdz_validator as validator


def _square(x0, y0, size):
    return {"type": "Polygon", "coordinates": [[
        [x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size],
        [x0, y0]]]}


def _layer(geometry, crs="EPSG:26917", **extra):
    return dict({"crs": crs, "geometry": geometry, "source": "Official layer",
                 "version": "v2026.1"}, **extra)


class SourceClassification(unittest.TestCase):
    """OFFICIAL may ground a claim. SECONDARY may only help you find one."""

    def test_official_authority_hosts_are_recognised(self):
        for url in ("https://www.toronto.ca/legdocs/bylaws/569-2013.pdf",
                    "https://www.ontario.ca/laws/statute/90p13",
                    "https://ero.ontario.ca/notice/025-0702",
                    "https://trca.ca/planning-permits/",
                    "https://www.mississauga.ca/zoning"):
            with self.subTest(url=url):
                self.assertEqual(authority.classify_source(url)["source_class"],
                                 authority.CLASS_OFFICIAL)

    def test_an_informative_law_firm_bulletin_is_secondary_not_official(self):
        """The case that matters. Useful, accurate, and not the statute."""
        result = authority.classify_source(
            "https://mcmillan.ca/insights/ontarios-updated-2024-pps/")
        self.assertEqual(result["source_class"], authority.CLASS_SECONDARY)
        self.assertIn("never the governing authority", result["reason"])

    def test_listing_and_social_sources_are_rejected_outright(self):
        for url in ("https://www.realtor.ca/listing/12345",
                    "https://housesigma.com/on/x",
                    "https://medium.com/@someone/zoning"):
            with self.subTest(url=url):
                self.assertEqual(authority.classify_source(url)["source_class"],
                                 authority.CLASS_REJECTED)

    def test_an_unknown_host_defaults_to_discovery_only(self):
        result = authority.classify_source("https://example.invalid/zoning")
        self.assertEqual(result["source_class"], authority.CLASS_SECONDARY)

    def test_a_non_http_locator_is_refused(self):
        for url in ("file:///C:/secret.pdf", "ftp://host/x", "", None):
            with self.subTest(url=url):
                self.assertEqual(authority.classify_source(url)["source_class"],
                                 authority.CLASS_REJECTED)

    def test_a_hosting_platform_is_not_an_authority(self):
        """SUPERSEDED DELIBERATELY, BY MEASUREMENT (CLAUDE-GENERALIZATION-02).

        `.arcgis.com` was on the OFFICIAL list until a live probe searched
        ArcGIS Online for land use layers and got back results owned by
        `Loftuli59` and `userd9d9` beside municipal ones. Ownership cannot be
        inferred from the host: the same domain, over the same path shape,
        serves a city's authoritative zoning and a hobbyist's re-upload. Leaving
        it OFFICIAL let any individual's hosted layer ground AUTHORITY_SAYS -
        the exact failure this module's first line exists to prevent, admitted
        through its own allowlist.
        """
        for url in ("https://services.arcgis.com/x/FeatureServer/0/query",
                    "https://data.opendata.arcgis.com/datasets/zoning",
                    "https://someone.maps.arcgis.com/home/item.html?id=abc"):
            classification = authority.classify_source(url)
            self.assertEqual(classification["source_class"],
                             authority.CLASS_SECONDARY, url)
            self.assertIn("hosting platform", classification["reason"])

    def test_a_municipality_s_own_domain_is_still_official(self):
        """The hardening must not throw away the real authorities with it."""
        for url in ("https://gis.toronto.ca/arcgis/rest/services/x/MapServer/1",
                    "https://www.toronto.ca/legdocs/bylaws/2021/law0266.pdf",
                    "https://www.mississauga.ca/zoning"):
            self.assertEqual(
                authority.classify_source(url)["source_class"],
                authority.CLASS_OFFICIAL, url)

    def test_machine_readable_geometry_endpoints_are_flagged(self):
        result = authority.classify_source(
            "https://gis.toronto.ca/arcgis/rest/services/x/FeatureServer/0/query?f=geojson")
        self.assertTrue(result["machine_readable_geometry"])


class AcquisitionIsReadOnlyAndGated(unittest.TestCase):
    def test_a_rejected_host_is_never_fetched(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            return b"payload"

        out = authority.acquire(
            "https://www.realtor.ca/listing/1", fetcher=fetcher,
            authority_id="A1", issuing_authority="x", official_title="y",
            retrieved_at="2026-09-12")
        self.assertFalse(out["acquired"])
        self.assertEqual(calls, [], "classification precedes retrieval")

    def test_an_official_source_is_fetched_and_hashed(self):
        out = authority.acquire(
            "https://www.toronto.ca/legdocs/bylaw.pdf",
            fetcher=lambda _u: b"BY-LAW TEXT",
            authority_id="A1", issuing_authority="City of Toronto",
            official_title="Zoning By-law 569-2013", retrieved_at="2026-09-12",
            effective_date="2013-05-09",
            applicability=authority.APPLICABILITY_CURRENT)
        self.assertTrue(out["acquired"])
        self.assertTrue(out["record"]["provenance_hash"].startswith("sha256:"))
        self.assertTrue(authority.may_satisfy_authority_says(out["record"]))

    def test_a_failing_fetcher_is_a_result_not_a_raise(self):
        def boom(_url):
            raise RuntimeError("timeout")

        out = authority.acquire(
            "https://www.toronto.ca/x.pdf", fetcher=boom, authority_id="A1",
            issuing_authority="x", official_title="y", retrieved_at="2026-09-12")
        self.assertFalse(out["acquired"])
        self.assertIn("RuntimeError", out["reason"])

    def test_source_class_cannot_be_forged_by_the_caller(self):
        record = authority.authority_record(
            authority_id="A1", issuing_authority="Someone",
            official_title="A blog post",
            url="https://medium.com/@x/zoning", retrieved_at="2026-09-12",
            payload=b"words")
        self.assertEqual(record["source_class"], authority.CLASS_REJECTED)
        self.assertFalse(authority.may_satisfy_authority_says(record))


class AnAuthorityIsNotItsProse(unittest.TestCase):
    def test_a_record_without_bytes_or_representation_cannot_ground_a_claim(self):
        record = authority.authority_record(
            authority_id="A1", issuing_authority="City",
            official_title="Zoning By-law", url="https://www.toronto.ca/x",
            retrieved_at="2026-09-12", payload=None)
        self.assertIsNone(record["provenance_hash"])
        self.assertFalse(authority.may_satisfy_authority_says(record))

    def test_a_retained_pointer_is_sufficient_when_bytes_are_not_kept(self):
        record = authority.authority_record(
            authority_id="A1", issuing_authority="City",
            official_title="Zoning By-law", url="https://www.toronto.ca/x",
            retrieved_at="2026-09-12", payload=None,
            retained_representation="registry://sources/abc123")
        self.assertTrue(authority.may_satisfy_authority_says(record))


class TemporalDiscipline(unittest.TestCase):
    def test_adopted_but_not_in_force_is_its_own_state(self):
        record = authority.authority_record(
            authority_id="OPA804", issuing_authority="City of Toronto",
            official_title="Official Plan Amendment 804",
            url="https://www.toronto.ca/opa804", retrieved_at="2026-09-12",
            payload=b"x", applicability=authority.APPLICABILITY_ADOPTED_NOT_IN_FORCE)
        self.assertEqual(record["applicability"], "ADOPTED_NOT_IN_FORCE")
        self.assertEqual(
            lifecycle._applicability_to_authority_status(record["applicability"]),
            "ADOPTED_NOT_IN_FORCE")

    def test_adopted_not_in_force_cannot_carry_high_confidence(self):
        """The two halves meeting: the seam records the state, VR-07 enforces it."""
        document = _minimal_document()
        document["authorities"][0]["authority_status"] = "ADOPTED_NOT_IN_FORCE"
        fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
        self.assertIn("VR-07", fired)

    def test_amendment_history_is_retained_when_discoverable(self):
        record = authority.authority_record(
            authority_id="A1", issuing_authority="City", official_title="T",
            url="https://www.toronto.ca/x", retrieved_at="2026-09-12",
            payload=b"x", amendment_history=["By-law 447-2025"])
        self.assertEqual(record["amendment_history"], ["By-law 447-2025"])


class TheEngineDecidesWhatItCan(unittest.TestCase):
    """Exact answers inside the declared competence."""

    def test_a_parcel_wholly_within_a_layer_is_inside(self):
        token = spatial.relate(_layer(_square(10, 10, 5)),
                               _layer(_square(0, 0, 100)))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["spatial_basis"], spatial.BASIS_DETERMINISTIC)

    def test_a_parcel_clear_of_a_layer_is_outside(self):
        token = spatial.relate(_layer(_square(500, 500, 5)),
                               _layer(_square(0, 0, 100)))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_OUTSIDE)

    def test_a_parcel_crossing_a_boundary_intersects(self):
        token = spatial.relate(_layer(_square(95, 95, 20)),
                               _layer(_square(0, 0, 100)))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INTERSECTS)

    def test_a_layer_wholly_inside_the_parcel_still_intersects(self):
        """No edge crossing and no parcel vertex inside - and still not OUTSIDE."""
        token = spatial.relate(_layer(_square(0, 0, 100)),
                               _layer(_square(40, 40, 5)))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INTERSECTS)

    def test_every_decided_token_carries_full_provenance(self):
        token = spatial.relate(
            _layer(_square(10, 10, 5)), _layer(_square(0, 0, 100)),
            subject_source="Parcel fabric", layer_source="Zoning layer",
            layer_version="v2026.1")
        provenance = token["provenance"]
        for field in ("subject_geometry_source", "subject_geometry_id",
                      "layer_geometry_source", "layer_geometry_id",
                      "layer_version", "subject_crs", "layer_crs",
                      "transformation", "operation"):
            self.assertIn(field, provenance)
        self.assertTrue(provenance["subject_geometry_id"].startswith("sha256:"))
        self.assertIsNone(provenance["transformation"],
                          "no reprojection is ever performed silently")


class TheEngineRefusesWhatItCannotDecide(unittest.TestCase):
    """Section 10, one named refusal per condition. The refusals are the feature."""

    def _ambiguous(self, subject, layer, reason, **kwargs):
        token = spatial.relate(subject, layer, **kwargs)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_AMBIGUOUS)
        self.assertEqual(token["spatial_basis"], spatial.BASIS_NONE)
        self.assertEqual(token["reason"], reason)

    def test_missing_geometry(self):
        self._ambiguous(_layer(None), _layer(_square(0, 0, 10)),
                        spatial.REASON_MISSING)

    def test_invalid_geometry(self):
        unclosed = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]}
        self._ambiguous(_layer(unclosed), _layer(_square(0, 0, 10)),
                        spatial.REASON_INVALID)

    def test_crs_mismatch_is_never_silently_reprojected(self):
        self._ambiguous(_layer(_square(10, 10, 5), crs="EPSG:4326"),
                        _layer(_square(0, 0, 100), crs="EPSG:26917"),
                        spatial.REASON_CRS_MISMATCH)

    def test_unsupported_crs(self):
        self._ambiguous(_layer(_square(10, 10, 5), crs="EPSG:999999"),
                        _layer(_square(0, 0, 100), crs="EPSG:999999"),
                        spatial.REASON_CRS_UNSUPPORTED)

    def test_holes_are_no_longer_beyond_competence(self):
        """SUPERSEDED DELIBERATELY, BY MEASUREMENT (CLAUDE-TORONTO-LIVE-01).

        This test previously asserted that any polygon with a hole was refused.
        The first real subject retired it: the City of Toronto's authoritative
        zoning polygon governing 35 Taber Road is ONE exterior ring of 389
        vertices with FIVE holes. Refusing that refuses the ordinary municipal
        case rather than an exotic one, and the even-odd rule decides it exactly
        - so the engine was widened rather than the standard lowered.

        The refusal it replaced is not weakened anywhere: multipart geometry, CRS
        mismatch, invalid rings and boundary proximity are all still refused, a
        malformed hole is refused too, and `tests/test_toronto_live_adapters_01.py`
        pins the hole arithmetic including the case version 1 could not see at
        all - a parcel lying inside a hole is OUTSIDE the zone.
        """
        holed = {"type": "Polygon", "coordinates": [
            _square(0, 0, 1000)["coordinates"][0],
            _square(200, 200, 100)["coordinates"][0]]}
        token = spatial.relate(_layer(_square(600, 600, 20)), _layer(holed))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["spatial_basis"], spatial.BASIS_DETERMINISTIC)
        self.assertEqual(token["provenance"]["layer_hole_count"], 1)

    def test_multipart_geometry_is_no_longer_beyond_competence(self):
        """SUPERSEDED DELIBERATELY, BY MEASUREMENT (CLAUDE-TORONTO-LIVE-01).

        The first live run refused three of ten authority layers around the
        subject - the height overlay among them - and told the reader they "could
        not be determined". The City's polygons were fine; this engine declined
        them. Reporting an engine limit as a data ambiguity is worse than either
        problem alone, because it sends a reader looking for evidence that
        already exists.

        Containment against a union is not a question about intent: a subject is
        inside when it lies inside some part, and outside when it lies outside
        every part. What is still refused is what is genuinely undecidable -
        invalid rings, CRS mismatch, boundary proximity, and geometry that
        disagrees with itself.
        """
        multi = {"type": "MultiPolygon", "coordinates": [
            _square(0, 0, 10)["coordinates"], _square(50, 50, 10)["coordinates"]]}
        token = spatial.relate(_layer(_square(1, 1, 2)), _layer(multi))
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["provenance"]["layer_part_count"], 2)

        between = spatial.relate(_layer(_square(30, 30, 2)), _layer(multi))
        self.assertEqual(between["spatial_relation"], spatial.RELATION_OUTSIDE,
                         "the gap between two parts is not in the union")

    def test_a_vertex_on_the_boundary_is_too_close_to_call(self):
        """Two layers digitised at different epochs routinely 'touch'."""
        self._ambiguous(_layer(_square(0, 0, 50)), _layer(_square(0, 0, 100)),
                        spatial.REASON_NEAR_BOUNDARY)

    def test_conflicting_official_geometry(self):
        self._ambiguous(_layer(_square(10, 10, 5)), _layer(_square(0, 0, 100)),
                        spatial.REASON_CONFLICTING, conflicting_layers=True)

    def test_an_address_resolving_to_several_parcels(self):
        self._ambiguous(_layer(_square(10, 10, 5)), _layer(_square(0, 0, 100)),
                        spatial.REASON_MULTIPLE_PARCELS, subject_parcel_count=3)

    def test_a_non_vector_source(self):
        raster = {"type": "GeoTIFF", "coordinates": [[0, 0]]}
        self._ambiguous(_layer(raster), _layer(_square(0, 0, 10)),
                        spatial.REASON_NOT_VECTOR)

    def test_an_ambiguous_token_can_never_claim_deterministic_basis(self):
        for reason_case in (
                (_layer(None), _layer(_square(0, 0, 10))),
                (_layer(_square(10, 10, 5), crs="EPSG:4326"),
                 _layer(_square(0, 0, 100), crs="EPSG:26917"))):
            token = spatial.relate(*reason_case)
            self.assertNotEqual(token["spatial_basis"],
                                spatial.BASIS_DETERMINISTIC)


def _minimal_document():
    """A contract-shaped document with one in-force authority and one statement."""
    return {
        "contract": "GO-PDZ-1.0-ONEPAGE", "schema_version": "1.0",
        "gate": "GATE_01_ADDRESS_ONLY_ENVELOPE",
        "next_authorized_gate": "GATE_02_OWNER_PROGRAM_ENTRY",
        "subject": {"subject_id": "S1", "address_as_given": "1 Test Road",
                    "normalized_address": "1 Test Road", "parcel_identifier": "L1",
                    "municipality": "Testville", "identity_confidence": "HIGH"},
        "authorities": [{"authority_id": "A1", "name": "Test Zoning By-law",
                         "instrument": "Zoning By-law", "citation": "s.1",
                         "effective_date": "2020-01-01",
                         "authority_status": "IN_FORCE",
                         "retrieved_at": "2026-09-12",
                         "url": "https://www.toronto.ca/x"}],
        "statements": [{"statement_id": "ST1", "kind": "AUTHORITY_SAYS",
                        "topic": "ZONING", "text": "The parcel is zoned CC.",
                        "authority_refs": ["A1"],
                        "statement_status": "ESTABLISHED", "confidence": "HIGH",
                        "spatial_relation": "NOT_APPLICABLE",
                        "spatial_basis": "NONE", "conflict_refs": [],
                        "derived_from": []}],
        "site_specific_exceptions": [], "unresolved": [],
        "result_status": "GOVERNED_RESULT",
    }


def _official_record(authority_id="A1", **overrides):
    fields = dict(
        authority_id=authority_id, issuing_authority="City of Testville",
        official_title="Testville Zoning By-law 2020-01",
        url="https://www.toronto.ca/legdocs/zbl.pdf", retrieved_at="2026-09-12",
        payload=b"BY-LAW", effective_date="2020-01-01",
        applicability=authority.APPLICABILITY_CURRENT,
        provision_locator="s.7.2")
    fields.update(overrides)
    return authority.authority_record(**fields)


def _resolver(**overrides):
    base = {"subject_id": "SUBJ-TEST", "normalized_address": "1 Test Road",
            "parcel_identifier": "PLAN 1 LOT 1", "municipality": "Testville",
            "parcel_count": 1, "geometry": _square(10, 10, 5),
            "crs": "EPSG:26917", "source": "Testville parcel fabric"}
    base.update(overrides)
    return lambda _address: base


class TheLifecycleIsReachable(unittest.TestCase):
    """Section 11/12: address in, validated envelope out, on synthetic data."""

    def _statements(self):
        return [
            {"statement_id": "ST-ZONE", "kind": "AUTHORITY_SAYS",
             "topic": "ZONING", "text": "The parcel is zoned Community Commercial.",
             "authority_refs": ["A1"], "statement_status": "ESTABLISHED",
             "confidence": "HIGH"},
            {"statement_id": "ST-REG", "kind": "PROPERTY_FACT",
             "topic": "ENVIRONMENT",
             "text": "The parcel sits within the mapped regulated area.",
             "authority_refs": ["A1"], "statement_status": "PROVISIONAL",
             "confidence": "MEDIUM", "spatial_layer": "regulated_area"},
        ]

    def test_the_whole_path_produces_a_promotable_result(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()],
            statements=self._statements(),
            layers={"regulated_area": _layer(_square(0, 0, 100))})
        self.assertEqual(out["validation"]["error_count"], 0,
                         [f["rule_id"] + ": " + f["message"]
                          for f in out["validation"]["findings"]])
        self.assertTrue(out["promotable"])
        self.assertEqual(out["gate"], "GATE_01_ADDRESS_ONLY_ENVELOPE")

    def test_the_spatial_token_is_copied_from_the_engine_not_composed(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()],
            statements=self._statements(),
            layers={"regulated_area": _layer(_square(0, 0, 100))})
        statement = next(s for s in out["document"]["statements"]
                         if s["statement_id"] == "ST-REG")
        token = out["spatial_tokens"]["regulated_area"]
        self.assertEqual(statement["spatial_relation"], token["spatial_relation"])
        self.assertEqual(statement["spatial_basis"], token["spatial_basis"])
        self.assertEqual(statement["spatial_relation"], spatial.RELATION_INSIDE)

    def test_a_secondary_source_is_excluded_and_the_statement_fails(self):
        secondary = _official_record(
            authority_id="A1", url="https://mcmillan.ca/insights/pps-2024/")
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[secondary], statements=self._statements(),
            layers={"regulated_area": _layer(_square(0, 0, 100))})
        self.assertEqual(out["document"]["authorities"], [])
        self.assertEqual(out["excluded_authorities"][0]["source_class"],
                         authority.CLASS_SECONDARY)
        fired = {f["rule_id"] for f in out["validation"]["findings"]}
        self.assertIn("VR-19", fired)
        self.assertFalse(out["promotable"])

    def test_spatial_failure_degrades_rather_than_guessing(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(crs="EPSG:4326"),
            authority_records=[_official_record()],
            statements=self._statements(),
            layers={"regulated_area": _layer(_square(0, 0, 100))})
        statement = next(s for s in out["document"]["statements"]
                         if s["statement_id"] == "ST-REG")
        self.assertEqual(statement["spatial_relation"],
                         spatial.RELATION_AMBIGUOUS)
        self.assertEqual(statement["spatial_basis"], spatial.BASIS_NONE)
        self.assertEqual(out["spatial_tokens"]["regulated_area"]["reason"],
                         spatial.REASON_CRS_MISMATCH)

    def test_an_unknown_layer_degrades_to_ambiguous(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()],
            statements=self._statements(), layers={})
        statement = next(s for s in out["document"]["statements"]
                         if s["statement_id"] == "ST-REG")
        self.assertEqual(statement["spatial_relation"],
                         spatial.RELATION_AMBIGUOUS)

    def test_an_ambiguous_address_blocks_established_authority_claims(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(parcel_count=3),
            authority_records=[_official_record()],
            statements=self._statements(),
            layers={"regulated_area": _layer(_square(0, 0, 100))})
        self.assertEqual(out["identity"]["identity_confidence"], "UNRESOLVED")
        fired = {f["rule_id"] for f in out["validation"]["findings"]}
        self.assertIn("VR-02", fired)

    def test_a_failing_resolver_is_a_result_not_a_raise(self):
        def boom(_address):
            raise RuntimeError("gazetteer down")

        out = lifecycle.run(
            "1 Test Road", resolver=boom,
            authority_records=[_official_record()], statements=[], layers={})
        self.assertEqual(out["identity"]["identity_confidence"], "UNRESOLVED")

    def test_the_result_states_where_gate_01_stops(self):
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()], statements=[], layers={})
        self.assertIn("GATE_02_OWNER_PROGRAM_ENTRY", out["gate_stop"])

    def test_no_parameter_can_carry_an_owner_program(self):
        """A stronger guarantee than a validator rule: there is no such input."""
        import inspect
        parameters = set(inspect.signature(lifecycle.run).parameters)
        for forbidden in ("program", "units", "budget", "massing", "rooms",
                          "requirements", "options"):
            self.assertNotIn(forbidden, parameters)


class ExceptionFailsClosedThroughTheLifecycle(unittest.TestCase):
    """Section 4/7, end to end rather than only in the validator."""

    def test_an_unreadable_exception_forces_unresolved(self):
        exception = authority.unresolved_exception(
            "(x412)", indicated_by="Official zoning map annotation",
            missing_authority="Text of exception (x412), Chapter 900",
            development_effect="May displace CC height and setback standards",
            required_next_evidence="Exception text from the by-law office")
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()],
            statements=[{"statement_id": "ST-Z", "kind": "AUTHORITY_SAYS",
                         "topic": "ZONING", "text": "The parcel is zoned CC.",
                         "authority_refs": ["A1"],
                         "statement_status": "PROVISIONAL",
                         "confidence": "MEDIUM"}],
            layers={}, site_specific_exceptions=[exception])
        self.assertEqual(out["document"]["result_status"], "UNRESOLVED")
        fired = {f["rule_id"] for f in out["validation"]["findings"]}
        self.assertNotIn("VR-08", fired, "declaring UNRESOLVED satisfies VR-08")

    def test_parent_zone_standards_cannot_ride_past_it(self):
        exception = authority.unresolved_exception(
            "(x412)", indicated_by="map", missing_authority="text",
            development_effect="displaces height", required_next_evidence="text")
        out = lifecycle.run(
            "1 Test Road", resolver=_resolver(),
            authority_records=[_official_record()],
            statements=[{"statement_id": "ST-H", "kind": "AUTHORITY_SAYS",
                         "topic": "HEIGHT",
                         "text": "Maximum height is 14 metres.",
                         "authority_refs": ["A1"],
                         "statement_status": "ESTABLISHED",
                         "confidence": "HIGH"}],
            layers={}, site_specific_exceptions=[exception])
        fired = {f["rule_id"] for f in out["validation"]["findings"]}
        self.assertIn("VR-20", fired)
        self.assertFalse(out["promotable"])

    def test_the_unresolved_record_says_what_is_missing_and_what_it_changes(self):
        exception = authority.unresolved_exception(
            "(x412)", indicated_by="map", missing_authority="Chapter 900 text",
            development_effect="May displace height", required_next_evidence="text")
        for field in ("missing_authority", "development_effect",
                      "required_next_evidence"):
            self.assertTrue(exception[field])
        self.assertFalse(exception["text_retrieved"])
        self.assertIsNone(exception["authority_ref"])


class NoEgressAndNoNewDependency(unittest.TestCase):
    def test_nothing_reaches_a_network_by_default(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "services"
        for module in ("planning_authority.py", "deterministic_spatial.py",
                       "go_pdz_lifecycle.py"):
            source = (root / module).read_text(encoding="utf-8")
            for banned in ("requests.", "urllib.request", "urlopen", "httpx",
                           "socket."):
                self.assertNotIn(banned, source, module)

    def test_no_geospatial_dependency_was_added(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        requirements = (root / "requirements.txt").read_text(encoding="utf-8")
        for package in ("shapely", "geopandas", "pyproj", "fiona", "gdal"):
            self.assertNotIn(package, requirements.lower())
        source = (root / "services" / "deterministic_spatial.py").read_text(
            encoding="utf-8")
        self.assertNotIn("import shapely", source)


if __name__ == "__main__":
    unittest.main()
