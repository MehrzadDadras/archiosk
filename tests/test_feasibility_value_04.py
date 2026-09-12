"""CLAUDE-FEASIBILITY-VALUE-04 - the evidence package must carry FACTS.

Probe 04 asked whether the compiler adds justified interpretive value. The first
two passes returned ZERO GO_INTERPRETS statements across ten live runs, and the
tempting conclusion was "the model appropriately declines to interpret".

An A/B settled it instead. Same address, same model, same budget:

    A  finished statement objects (the old builder)  ->  17 in, 17 out, 0 derivations
    B  the identical retrieval as raw attributes     ->  1 supported derivation, 3/3

Handing a model a nearly-finished document and asking for a document makes
transcription the cheapest correct answer. The interpretation was not absent; it
was suppressed by the shape of what the builder supplied - and that silence had
already been reported as a property of the model.

So these tests pin the property that fix depends on: `evidence_from_gate01`
forwards RETRIEVED ATTRIBUTES and never the runner's own prose.
"""
from __future__ import annotations

import json
import unittest

from services import feasibility_compiler as compiler


def _outcome(retrieval=None, statements=None, authorities=None, unresolved=None,
             tokens=None):
    return {
        "document": {
            "gate": "GATE_01_ADDRESS_ONLY_ENVELOPE",
            "subject": {"subject_id": "S-1", "address_as_given": "1 Test St",
                        "normalized_address": "1 Test St",
                        "parcel_identifier": "PARCEL-1",
                        "municipality": "Test City",
                        "identity_confidence": "HIGH"},
            "authorities": authorities or [],
            "statements": statements or [],
            "site_specific_exceptions": [],
            "unresolved": unresolved or [],
            "result_status": "GOVERNED_RESULT",
        },
        "identity": {"_crs": "EPSG:3857", "_geometry_source": "Test parcels",
                     "_parcel_count": 1},
        "spatial_tokens": tokens or {},
        "retrieval": retrieval or {},
    }


PROSE = [{"statement_id": "S-ZONE", "kind": "AUTHORITY_SAYS",
          "topic": "ZONING_DESIGNATION",
          "text": "The subject parcel lies within a zone labelled 'CR 3.0'.",
          "statement_status": "ESTABLISHED", "confidence": "HIGH"}]


class TheBuilderPassesFactsNotConclusions(unittest.TestCase):

    def test_no_pre_written_statement_object_reaches_the_model(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(statements=PROSE,
                     retrieval={"zoning_attributes": {"ZN_STRING": "CR 3.0",
                                                      "FSI_TOTAL": 3.0}}),
            investigation_id="INV-1")
        blob = compiler.canonical_evidence(evidence.for_model())
        self.assertNotIn("statement_id", blob,
                         "forwarding finished statements makes transcription the "
                         "cheapest correct answer")
        self.assertNotIn("statement_status", blob)
        self.assertNotIn("lies within a zone labelled", blob,
                         "the runner's own prose must not be the evidence")

    def test_the_raw_zone_attributes_do_reach_the_model(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"zoning_attributes": {
                "ZN_STRING": "CR 3.0 (c2.0; r2.5) SS2  (x2219)",
                "FSI_TOTAL": 3.0, "FSI_COMMERCIAL_USE": 2.0,
                "FSI_RESIDENTIAL_USE": 2.5, "ZN_EXCPTN": "Y",
                "ZN_EXCPTN_NO": 2219}}),
            investigation_id="INV-1")
        attributes = evidence.for_model()["zoning"]["attributes"]
        self.assertEqual(attributes["FSI_TOTAL"], 3.0)
        self.assertEqual(attributes["FSI_COMMERCIAL_USE"], 2.0)
        self.assertEqual(attributes["FSI_RESIDENTIAL_USE"], 2.5)
        self.assertEqual(attributes["ZN_EXCPTN_NO"], 2219)

    def test_noise_attributes_are_stripped(self):
        """OBJECTID and shape areas cost tokens and carry no planning meaning."""
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"zoning_attributes": {
                "ZN_ZONE": "CR", "OBJECTID": 891723, "Shape__Area": 1234.5,
                "SHAPE.LEN": 0, "MSLINK": 9, "ZN_FRONTAGE": -1.0}}),
            investigation_id="INV-1")
        attributes = evidence.for_model()["zoning"]["attributes"]
        self.assertEqual(attributes, {"ZN_ZONE": "CR"})

    def test_split_zoning_is_a_fact_the_model_can_see(self):
        """The third live subject's decisive condition."""
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"zoning": {
                "zone_count": 2, "split": True,
                "zones": [{"attributes": {"ZONE_CODE": "RL-62"}},
                          {"attributes": {"ZONE_CODE": "RL-61"}}]}}),
            investigation_id="INV-1")
        zoning = evidence.for_model()["zoning"]
        self.assertTrue(zoning["split_zoning"])
        self.assertEqual(zoning["zone_count"], 2)
        self.assertEqual([z["ZONE_CODE"] for z in zoning["zones"]],
                         ["RL-62", "RL-61"])

    def test_an_unretrieved_exception_is_a_fact_not_a_sentence(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"exception": {
                "acquired": False, "url": "https://www.toronto.ca/zoning/x.htm",
                "reason": "the page does not contain exception 2219"}}),
            investigation_id="INV-1")
        exception = evidence.for_model()["zoning"]["site_specific_exception"]
        self.assertFalse(exception["acquired"])
        self.assertIn("2219", exception["reason"])

    def test_overlay_attributes_survive_and_absence_is_marked(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"overlays": [
                {"layer_name": "Zoning Height Overlay", "present": True,
                 "attributes": {"HT_STRING": "HT 14.0", "HT_HEIGHT": 14.0,
                                "OBJECTID": 1}},
                {"layer_name": "Secondary Plan", "present": False,
                 "absence_established": True, "polygons_in_envelope": 0}]}),
            investigation_id="INV-1")
        overlays = evidence.for_model()["overlays"]
        height = [o for o in overlays if o["layer"] == "Zoning Height Overlay"][0]
        self.assertEqual(height["attributes"], {"HT_STRING": "HT 14.0",
                                                "HT_HEIGHT": 14.0})
        absent = [o for o in overlays if o["layer"] == "Secondary Plan"][0]
        self.assertFalse(absent["applies"])
        self.assertTrue(absent["absence_proved"])

    def test_a_machine_readable_official_plan_is_distinguished_from_a_document(self):
        """Mississauga publishes Schedule 10 as polygons; Toronto does not."""
        machine = compiler.evidence_from_gate01(
            _outcome(retrieval={"land_use": {"designations": [
                {"attributes": {"MOP_CODE": "LDI",
                                "MOP_DESCRIPTION": "Residential Low Density I"}}]}}),
            investigation_id="INV-1").for_model()["official_plan"]
        self.assertTrue(machine["machine_readable"])
        self.assertEqual(machine["designations"][0]["MOP_CODE"], "LDI")

        document = compiler.evidence_from_gate01(
            _outcome(authorities=[{"authority_id": "TOR-OFFICIAL-PLAN",
                                   "source_type": "OFFICIAL_MAP_SCHEDULE"}]),
            investigation_id="INV-1").for_model()["official_plan"]
        self.assertFalse(document["machine_readable"])
        self.assertFalse(document["designation_available"])

    def test_geometry_coordinates_are_still_dropped(self):
        """A token said INSIDE; the ring it was computed from is not evidence."""
        evidence = compiler.evidence_from_gate01(
            _outcome(tokens={"zoning_area": {
                "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
                "engine": "archiosk-exact-ring@3",
                "provenance": {"layer_geometry_source": "City zoning"}}}),
            investigation_id="INV-1")
        blob = compiler.canonical_evidence(evidence.for_model())
        self.assertNotIn("coordinates", blob)
        self.assertIn("INSIDE", blob)

    def test_the_spatial_token_is_still_carried_verbatim(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(tokens={"zoning_area": {
                "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS"}}),
            investigation_id="INV-1")
        token = evidence.for_model()["spatial_results"]["zoning_area"]
        self.assertEqual(token["spatial_relation"], "INSIDE")
        self.assertEqual(token["spatial_basis"], "DETERMINISTIC_GIS")

    def test_unresolved_issues_are_forwarded_unchanged(self):
        issues = [{"issue_id": "U-OP", "question": "Which designation?",
                   "materiality": "MATERIAL"}]
        evidence = compiler.evidence_from_gate01(
            _outcome(unresolved=issues), investigation_id="INV-1")
        self.assertEqual(evidence.for_model()["unresolved"], issues)

    def test_the_package_still_passes_its_own_forbidden_key_check(self):
        evidence = compiler.evidence_from_gate01(
            _outcome(retrieval={"zoning_attributes": {"ZN_ZONE": "CR"}}),
            investigation_id="INV-1")
        self.assertEqual(compiler.validate_evidence(evidence), [])


class TheRunnerRetainsWhatTheBuilderNeeds(unittest.TestCase):

    def test_toronto_retains_raw_zoning_attributes(self):
        import inspect
        from services import toronto_gate01
        source = inspect.getsource(toronto_gate01.run)
        self.assertIn('"zoning_attributes"', source,
                      "the builder cannot forward facts the runner discarded")

    def test_mississauga_retains_its_zone_list(self):
        import inspect
        from services import mississauga_gate01
        source = inspect.getsource(mississauga_gate01.run)
        self.assertIn('"zoning"', source)


class TheInstructionsMakeBothOutcomesAvailable(unittest.TestCase):
    """Section 7: restraint must stay a legitimate answer, not a forced one."""

    def test_derivation_is_invited(self):
        self.assertIn("derived_from", compiler.INSTRUCTIONS)
        self.assertIn("GO_INTERPRETS", compiler.INSTRUCTIONS)

    def test_silence_is_explicitly_legitimate(self):
        instructions = compiler.INSTRUCTIONS.lower()
        self.assertIn("write none", instructions)
        self.assertIn("padding", instructions)

    def test_the_prohibitions_all_survived_the_invitation(self):
        instructions = compiler.INSTRUCTIONS
        for prohibition in ("Do not invent an authority",
                            "Do not predict whether an application would be approved",
                            "never mint one",
                            "Preserve material ambiguity",
                            "Stop at the legal envelope"):
            self.assertIn(prohibition, instructions, prohibition)

    def test_the_instruction_stayed_short(self):
        """Section 8: governance is not buried in a massive prompt."""
        self.assertLess(len(compiler.INSTRUCTIONS), 2600)


if __name__ == "__main__":
    unittest.main()
