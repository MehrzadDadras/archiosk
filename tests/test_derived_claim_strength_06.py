"""CLAUDE-DERIVED-STRENGTH-06 - the model may discover a claim; evidence decides
how strongly ARCHIOSK may state it.

Probe 05 measured the failure this closes. A derived finding that appeared in ONE
run out of five emitted ESTABLISHED / HIGH, while the finding produced in FIVE out
of five stayed PROVISIONAL: the model was most assertive exactly where it was
least reproducible, and nothing downstream could tell a rare-and-right claim from
a rare-and-wrong one.

Two design commitments these fixtures defend:

1. RUN FREQUENCY IS NOT ENCODED IN PRODUCTION VALIDATION. It is a research
   signal. What VR-21 encodes is that an unverified model reading cannot promote
   itself, whatever it says about its own confidence.

2. THE FIX FOR THE FSI CONSTRAINT IS VERIFICATION, NOT DISTRUST. Downgrading a
   correct arithmetic finding because Gemini noticed it inconsistently would
   discard a true, useful conclusion for a reason unrelated to whether it is
   true. `derivation_check` recomputes the relation outside the model, and the
   claim is then governed by arithmetic.
"""
from __future__ import annotations

import unittest

from services import derivation_check
from services import go_pdz_contract as contract
from services import go_pdz_validator as validator


def _document(statements, authorities=None, unresolved=None,
              result_status="GOVERNED_RESULT"):
    return {
        "contract": contract.CONTRACT_ID,
        "schema_version": contract.SCHEMA_VERSION,
        "gate": contract.GATE_01,
        "next_authorized_gate": contract.GATE_02,
        "subject": {"subject_id": "S-1", "address_as_given": "1 Test St",
                    "identity_confidence": "HIGH"},
        "authorities": authorities if authorities is not None else [{
            "authority_id": "EX-1", "name": "Example By-law",
            "authority_status": "IN_FORCE", "effective_date": "2020-01-01"}],
        "statements": statements,
        "site_specific_exceptions": [],
        "unresolved": unresolved or [],
        "result_status": result_status,
    }


def _statement(**overrides):
    base = {"statement_id": "S-1", "kind": "GO_INTERPRETS", "topic": "ENVELOPE",
            "text": "A derived reading.", "authority_refs": [],
            "statement_status": "PROVISIONAL", "confidence": "MEDIUM",
            "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
            "conflict_refs": [], "derived_from": []}
    base.update(overrides)
    return base


def _vr21(document):
    return [f for f in validator.validate(document)["findings"]
            if f.get("rule_id") == "VR-21"]


#: The real Danforth figures, verified deterministically.
FSI_CHECK = derivation_check.verify_fsi_envelope(
    {"FSI_TOTAL": 3.0, "FSI_COMMERCIAL_USE": 2.0, "FSI_RESIDENTIAL_USE": 2.5})


class TheTaxonomyDoesNotDuplicateWhatKindAlreadySays(unittest.TestCase):
    """Section 3."""

    def test_derivation_defaults_from_kind(self):
        self.assertEqual(
            contract.derivation_of({"kind": "AUTHORITY_SAYS"}),
            contract.DERIVATION_DIRECT_AUTHORITY)
        self.assertEqual(
            contract.derivation_of({"kind": "PROPERTY_FACT"}),
            contract.DERIVATION_PROPERTY_FACT)

    def test_go_interprets_defaults_to_the_SAFE_class(self):
        """A statement is an unverified model reading until proven otherwise."""
        self.assertEqual(contract.derivation_of({"kind": "GO_INTERPRETS"}),
                         contract.DERIVATION_MODEL)

    def test_an_existing_document_without_the_field_still_validates(self):
        document = _document([_statement()])
        self.assertTrue(validator.validate(document)["valid"])

    def test_the_confidence_ceiling_uses_the_contracts_own_vocabulary(self):
        """No fourth confidence value was invented for one rule."""
        for _status, confidence in contract.CLAIM_CEILINGS.values():
            self.assertIn(confidence, contract.CONFIDENCES)


class NegativeFixtures(unittest.TestCase):
    """Section 10 A-E."""

    def test_A_model_derivation_claiming_established_high_is_rejected(self):
        document = _document([_statement(statement_status="ESTABLISHED",
                                         confidence="HIGH")])
        findings = _vr21(document)
        self.assertEqual(len(findings), 2, "status AND confidence both exceed")
        self.assertFalse(validator.validate(document)["promotable"])
        paths = {f["path"] for f in findings}
        self.assertIn("$.statements[0].statement_status", paths)
        self.assertIn("$.statements[0].confidence", paths)

    def test_B_model_derivation_high_with_only_input_authority_refs(self):
        """Citing the inputs it reasoned over does not make the reading direct."""
        document = _document([_statement(confidence="HIGH",
                                         authority_refs=["EX-1"],
                                         derived_from=["S-INPUT-1", "S-INPUT-2"])])
        findings = _vr21(document)
        self.assertEqual(len(findings), 1)
        self.assertIn("confidence", findings[0]["path"])

    def test_C_dependency_finding_cannot_claim_substantive_certainty(self):
        document = _document(
            [_statement(derivation=contract.DERIVATION_DEPENDENCY,
                        statement_status="ESTABLISHED", confidence="HIGH")],
            unresolved=[{"issue_id": "U-1", "question": "What does it say?",
                         "materiality": "MATERIAL"}],
            result_status="UNRESOLVED")
        findings = _vr21(document)
        self.assertEqual(len(findings), 1, "a real dependency exists, so only "
                                           "the status ceiling is breached")
        self.assertIn("statement_status", findings[0]["path"])
        self.assertIn("DEPENDENCY_FINDING", findings[0]["message"])

    def test_F_a_dependency_class_with_no_dependency_is_not_trusted(self):
        """FOUND LIVE. Once the schema reached the prompt the model began
        declaring its own derivation class, and DEPENDENCY_FINDING carries a
        higher confidence ceiling than MODEL_DERIVATION - so self-declaring it
        was a route around this very rule. The class is corroborated from the
        DOCUMENT now, not taken from the statement claiming it."""
        document = _document([_statement(
            derivation=contract.DERIVATION_DEPENDENCY, confidence="HIGH")])
        findings = _vr21(document)
        self.assertTrue(findings)
        self.assertTrue(any("no unresolved dependency" in f["message"]
                            for f in findings))
        self.assertTrue(any("confidence" in f["path"] for f in findings),
                        "and it is then held to the MODEL_DERIVATION ceiling")

    def test_D_deterministic_arithmetic_with_an_unresolved_input(self):
        """The sum is exact and the conclusion is still not established: a
        correct sum over a figure an unretrieved exception may displace."""
        check = derivation_check.verify_fsi_envelope(
            {"FSI_TOTAL": 3.0, "FSI_COMMERCIAL_USE": 2.0,
             "FSI_RESIDENTIAL_USE": 2.5},
            unresolved_affecting=["exception 2219 text not retrieved"])
        self.assertEqual(check["result"], derivation_check.VERIFIED)
        self.assertFalse(check["supports_established"],
                         "exact arithmetic, provisional inputs")
        document = _document([_statement(
            derivation=contract.DERIVATION_DETERMINISTIC,
            derivation_check=check,
            statement_status="ESTABLISHED", confidence="HIGH")])
        self.assertTrue(_vr21(document))
        self.assertFalse(validator.validate(document)["promotable"])

    def test_E_same_evidence_cannot_yield_different_governed_strength(self):
        """Section 6: one stochastic run must not promote a conclusion.

        This is the split-zone case. Probe 05 saw the identical finding emitted
        UNRESOLVED four times and PROVISIONAL once on unchanged evidence.
        """
        dependency = [{"issue_id": "U-SPLIT", "materiality": "MATERIAL",
                       "question": "Where does the zone boundary fall?"}]
        weak = _document([_statement(statement_status="UNRESOLVED",
                                     confidence="HIGH",
                                     derivation=contract.DERIVATION_DEPENDENCY)],
                         unresolved=dependency, result_status="UNRESOLVED")
        strong = _document([_statement(statement_status="PROVISIONAL",
                                       confidence="HIGH",
                                       derivation=contract.DERIVATION_DEPENDENCY)],
                           unresolved=dependency, result_status="UNRESOLVED")
        # Neither exceeds the DEPENDENCY ceiling, so both are permitted - and
        # crucially NEITHER can reach ESTABLISHED on the same evidence.
        self.assertEqual(_vr21(weak), [])
        self.assertEqual(_vr21(strong), [])
        promoted = _document([_statement(
            statement_status="ESTABLISHED", confidence="HIGH",
            derivation=contract.DERIVATION_DEPENDENCY)],
            unresolved=dependency, result_status="UNRESOLVED")
        self.assertTrue(_vr21(promoted),
                        "the ceiling is what makes the same evidence imply the "
                        "same maximum claim strength")

    def test_a_model_cannot_declare_itself_deterministic(self):
        """The attestation is the whole guarantee."""
        for forged in (None, {}, {"result": "VERIFIED"},
                       {"verifier_version": "not-ours", "relation": "x"}):
            document = _document([_statement(
                derivation=contract.DERIVATION_DETERMINISTIC,
                derivation_check=forged,
                statement_status="ESTABLISHED", confidence="HIGH")])
            findings = _vr21(document)
            self.assertTrue(findings, repr(forged))
            self.assertTrue(any("attestation" in f["message"] for f in findings),
                            repr(forged))


class PositiveFixtures(unittest.TestCase):
    """Section 11 A-E."""

    def test_A_direct_authority_may_be_established_high(self):
        document = _document([_statement(
            kind="AUTHORITY_SAYS", statement_status="ESTABLISHED",
            confidence="HIGH", authority_refs=["EX-1"],
            spatial_relation="INSIDE", spatial_basis="DETERMINISTIC_GIS")])
        self.assertEqual(_vr21(document), [])
        self.assertTrue(validator.validate(document)["promotable"])

    def test_B_grounded_property_fact_may_be_established_high(self):
        document = _document([_statement(
            kind="PROPERTY_FACT", statement_status="ESTABLISHED",
            confidence="HIGH")])
        self.assertEqual(_vr21(document), [])
        self.assertTrue(validator.validate(document)["promotable"])

    def test_C_verified_arithmetic_derivation_may_be_established(self):
        """THE DANFORTH FSI FINDING, promoted by verification not by frequency."""
        self.assertEqual(FSI_CHECK["result"], derivation_check.VERIFIED)
        self.assertTrue(FSI_CHECK["supports_established"])
        document = _document([_statement(
            statement_id="S-FSI",
            text="Commercial 2.0 and residential 2.5 sum to 4.5, exceeding the "
                 "total cap of 3.0, so both cannot be taken in full.",
            derivation=contract.DERIVATION_DETERMINISTIC,
            derivation_check=FSI_CHECK,
            statement_status="ESTABLISHED", confidence="HIGH",
            derived_from=["S-ZONE"])])
        self.assertEqual(_vr21(document), [])
        self.assertTrue(validator.validate(document)["promotable"])

    def test_D_model_derivation_at_provisional_medium_is_accepted(self):
        document = _document([_statement(statement_status="PROVISIONAL",
                                         confidence="MEDIUM")])
        self.assertEqual(_vr21(document), [])
        self.assertTrue(validator.validate(document)["promotable"])

    def test_E_dependency_finding_preserving_unresolved_is_accepted(self):
        document = _document(
            [_statement(derivation=contract.DERIVATION_DEPENDENCY,
                        statement_status="UNRESOLVED", confidence="HIGH")],
            unresolved=[{"issue_id": "U-1", "question": "What does it say?",
                         "materiality": "MATERIAL"}],
            result_status="UNRESOLVED")
        self.assertEqual(_vr21(document), [])
        self.assertTrue(validator.validate(document)["valid"])


class TheVerifierIsHonestAboutItsCompetence(unittest.TestCase):

    def test_it_recomputes_the_relation_rather_than_believing_it(self):
        refuted = derivation_check.check_components_exceed_total(
            components=[1.0, 1.0], total=3.0)
        self.assertEqual(refuted["result"], derivation_check.REFUTED)
        self.assertFalse(refuted["supports_established"])

    def test_non_numeric_evidence_is_unverified_not_assumed(self):
        outcome = derivation_check.check_components_exceed_total(
            components=["2.0", 2.5], total=3.0)
        self.assertEqual(outcome["result"], derivation_check.UNVERIFIED)

    def test_a_zone_without_component_allowances_yields_nothing(self):
        """35 Taber: FSI 1.0 with no split. Saying nothing is correct."""
        self.assertIsNone(derivation_check.verify_fsi_envelope(
            {"FSI_TOTAL": 1.0, "FSI_COMMERCIAL_USE": -1.0}))

    def test_the_citys_minus_one_is_not_a_zero_allowance(self):
        self.assertIsNone(derivation_check.verify_fsi_envelope(
            {"FSI_TOTAL": 3.0, "FSI_COMMERCIAL_USE": -1.0,
             "FSI_RESIDENTIAL_USE": -1.0}))

    def test_the_attestation_carries_what_it_actually_read(self):
        self.assertEqual(sorted(FSI_CHECK["inputs"]["components"]), [2.0, 2.5])
        self.assertEqual(FSI_CHECK["inputs"]["total"], 3.0)
        self.assertEqual(FSI_CHECK["computed"]["sum"], 4.5)
        self.assertTrue(FSI_CHECK["inputs_hash"].startswith("sha256:"))
        self.assertEqual(FSI_CHECK["verifier_version"],
                         derivation_check.VERIFIER_VERSION)


class NoHiddenNormalisation(unittest.TestCase):
    """Section 8: current state must not launder model behaviour."""

    OVERCLAIMED = _document([_statement(statement_status="ESTABLISHED",
                                        confidence="HIGH")])

    def test_validate_rejects_rather_than_repairs(self):
        outcome = validator.validate(self.OVERCLAIMED)
        self.assertFalse(outcome["promotable"])
        self.assertEqual(
            self.OVERCLAIMED["statements"][0]["statement_status"], "ESTABLISHED",
            "the stored payload must still show what the model emitted")

    def test_the_projection_retains_both_values(self):
        projected = validator.governed_projection(self.OVERCLAIMED)
        statement = projected["statements"][0]
        self.assertEqual(statement["model_emitted"]["statement_status"],
                         "ESTABLISHED")
        self.assertEqual(statement["model_emitted"]["confidence"], "HIGH")
        self.assertEqual(statement["governed"]["statement_status"], "PROVISIONAL")
        self.assertEqual(statement["governed"]["confidence"], "MEDIUM")
        self.assertTrue(statement["governed"]["ceiling_applied"])
        self.assertIn("VR-21", statement["governed"]["governed_by"])

    def test_the_projection_does_not_mutate_the_original(self):
        before = dict(self.OVERCLAIMED["statements"][0])
        validator.governed_projection(self.OVERCLAIMED)
        self.assertEqual(self.OVERCLAIMED["statements"][0], before)

    def test_a_compliant_statement_is_unchanged_by_the_projection(self):
        document = _document([_statement(statement_status="PROVISIONAL",
                                         confidence="MEDIUM")])
        statement = validator.governed_projection(document)["statements"][0]
        self.assertFalse(statement["governed"]["ceiling_applied"])
        self.assertEqual(statement["governed"]["statement_status"], "PROVISIONAL")


class RunFrequencyIsNotProductionGovernance(unittest.TestCase):
    """Section 1, stated as a test so it cannot drift in later.

    Checks the API SURFACE rather than the source text. Both modules
    deliberately DISCUSS run frequency in order to record that it is not encoded,
    so a scan over prose would fail on the very sentence documenting the rule -
    the same false positive the owner-program check produced in probe 04, where
    bare "owner" fired on the contract's own GATE_02_OWNER_PROGRAM_ENTRY. A check
    that fires on correct output trains you to ignore it.

    Names are also the stronger test: prose can say anything, but a ceiling that
    consulted run frequency would need somewhere to read it from.
    """

    BANNED = ("run_count", "frequency", "runs_seen", "appeared_in",
              "reproducibility", "sample_size")

    def test_no_frequency_input_exists_on_the_validator(self):
        for name in dir(validator):
            for banned in self.BANNED:
                self.assertNotIn(banned, name.lower(), name)

    def test_no_frequency_input_exists_on_the_contract(self):
        for name in dir(contract):
            for banned in self.BANNED:
                self.assertNotIn(banned, name.lower(), name)

    def test_no_statement_field_carries_a_frequency(self):
        properties = (contract.SCHEMA["properties"]["statements"]["items"]
                      ["properties"])
        for field in properties:
            for banned in self.BANNED:
                self.assertNotIn(banned, field.lower(), field)

    def test_the_ceiling_depends_only_on_derivation_class(self):
        """Not on how often a finding was seen, which production never knows."""
        import inspect
        signature = inspect.signature(contract.ceiling_for)
        self.assertEqual(list(signature.parameters), ["derivation"])


if __name__ == "__main__":
    unittest.main()
