"""CLAUDE-PROMOTION-08 - discovery is not proof; proof is not discovery.

Probe 07 measured the gap: on 2820 Danforth the model discovered the FSI relation
in 2 runs of 5 while ARCHIOSK verified it deterministically in 5 of 5, and the two
facts never met. The claim stayed MODEL_DERIVATION at PROVISIONAL / MEDIUM with a
proof of it sitting unused beside it. The architecture could only LOWER a claim.

These fixtures defend the narrow path that now connects them, and - more
importantly - the many ways it must REFUSE to connect them:

    the same numbers in an unrelated sentence      -> no binding
    the relation asserted about different values   -> no binding
    an attestation copied onto another statement   -> no binding
    inputs changed after attestation               -> no binding
    a material dependency limiting the inputs      -> verified, NOT promoted

That last one is the real Danforth outcome, and it is the reason this module is
not a rubber stamp: the only live case arithmetically eligible for promotion is
also one where an unretrieved exception displaces the figures being summed.
"""
from __future__ import annotations

import json
import unittest

from services import derivation_check
from services import go_pdz_contract as contract
from services import go_pdz_validator as validator
from services import relation_binding


#: The real Danforth zoning attributes, minus the exception condition, so the
#: positive path can be exercised on a case whose inputs are clean.
CLEAN_FACTS = {"zoning": {"attributes": {
    "ZN_STRING": "CR 3.0 (c2.0; r2.5)", "FSI_TOTAL": 3.0,
    "FSI_COMMERCIAL_USE": 2.0, "FSI_RESIDENTIAL_USE": 2.5}}}

#: The real Danforth evidence: identical figures, plus the unretrieved exception.
DANFORTH_FACTS = {"zoning": {
    "attributes": dict(CLEAN_FACTS["zoning"]["attributes"],
                       ZN_EXCPTN="Y", ZN_EXCPTN_NO=2219),
    "site_specific_exception": {
        "acquired": False,
        "reason": "the page does not contain exception 2219"}}}

CAP_TEXT = ("Commercial FSI of 2.0 and residential FSI of 2.5 sum to 4.5, which "
            "exceeds the total permitted FSI of 3.0, so both cannot be taken in "
            "full.")


def _statement(**overrides):
    base = {"statement_id": "S-FSI", "kind": "GO_INTERPRETS", "topic": "DENSITY",
            "text": CAP_TEXT, "authority_refs": [],
            "statement_status": "PROVISIONAL", "confidence": "HIGH",
            "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
            "conflict_refs": [], "derived_from": ["S-ZONE"]}
    base.update(overrides)
    return base


def _document(statements, unresolved=None, result_status="GOVERNED_RESULT"):
    return {"contract": contract.CONTRACT_ID,
            "schema_version": contract.SCHEMA_VERSION,
            "gate": contract.GATE_01, "next_authorized_gate": contract.GATE_02,
            "subject": {"subject_id": "S-1", "address_as_given": "1 Test St",
                        "identity_confidence": "HIGH"},
            "authorities": [{"authority_id": "EX-1", "name": "By-law",
                             "authority_status": "IN_FORCE",
                             "effective_date": "2020-01-01"}],
            "statements": statements, "site_specific_exceptions": [],
            "unresolved": unresolved or [], "result_status": result_status}


class NegativeFixtures(unittest.TestCase):
    """Section 11 A-H. Every one must end in NO GOVERNED PROMOTION."""

    def test_A_a_model_declaring_deterministic_is_discarded(self):
        """The model's own claim to the class is dropped before ARCHIOSK decides."""
        document = _document([_statement(
            derivation=contract.DERIVATION_DETERMINISTIC,
            derivation_check={"result": "VERIFIED"},
            statement_status="ESTABLISHED", confidence="HIGH")])
        annotated, report = relation_binding.annotate(document, DANFORTH_FACTS)
        statement = annotated["statements"][0]
        self.assertNotEqual(statement.get("derivation_check"),
                            {"result": "VERIFIED"})
        self.assertFalse(report[0]["promoted"])
        self.assertTrue([f for f in validator.validate(annotated)["findings"]
                         if f.get("rule_id") == "VR-21"])

    def test_B_correct_numbers_but_wrong_semantics_do_not_bind(self):
        """Section 3: not any statement containing those values."""
        recital = _statement(
            statement_id="S-RECITE",
            text="The zone permits a total FSI of 3.0, with commercial 2.0 and "
                 "residential 2.5 recorded in the City's zoning attributes.")
        outcome = relation_binding.bind(recital, CLEAN_FACTS)
        self.assertFalse(outcome["promoted"])
        self.assertEqual(outcome["reason"],
                         relation_binding.REASON_NO_RELATION_LANGUAGE)

    def test_C_a_material_dependency_blocks_promotion(self):
        """THE REAL DANFORTH OUTCOME. Exact arithmetic, provisional applicability."""
        outcome = relation_binding.bind(_statement(), DANFORTH_FACTS)
        self.assertEqual(outcome["attestation"]["result"],
                         derivation_check.VERIFIED)
        self.assertFalse(outcome["attestation"]["supports_established"])
        self.assertFalse(outcome["promoted"])
        self.assertEqual(outcome["reason"],
                         relation_binding.REASON_INPUTS_NOT_ESTABLISHED)
        self.assertTrue(outcome["limits"])

    def test_D_an_attestation_for_another_statement_does_not_transfer(self):
        bound = relation_binding.bind(_statement(), CLEAN_FACTS)
        self.assertTrue(bound["promoted"])
        stolen = _statement(statement_id="S-OTHER",
                            derivation=contract.DERIVATION_DETERMINISTIC,
                            derivation_check=bound["attestation"])
        self.assertFalse(relation_binding.verify_binding(stolen, CLEAN_FACTS),
                         "an attestation is a proof about one claim, not a token")

    def test_E_inputs_altered_after_attestation_break_the_binding(self):
        bound = relation_binding.bind(_statement(), CLEAN_FACTS)
        statement = _statement(derivation=contract.DERIVATION_DETERMINISTIC,
                               derivation_check=bound["attestation"])
        self.assertTrue(relation_binding.verify_binding(statement, CLEAN_FACTS))
        moved = {"zoning": {"attributes": dict(
            CLEAN_FACTS["zoning"]["attributes"], FSI_TOTAL=5.0)}}
        self.assertFalse(relation_binding.verify_binding(statement, moved))

    def test_F_ambiguity_refuses_rather_than_choosing(self):
        """Section 8. A second eligible relation means neither is bound."""
        original = relation_binding.candidates_for
        relation_binding.candidates_for = lambda s, e: [
            {"relation": derivation_check.RELATION_COMPONENTS_EXCEED_TOTAL,
             "components": [2.0, 2.5], "labels": ["a", "b"], "total": 3.0},
            {"relation": derivation_check.RELATION_COMPONENTS_EXCEED_TOTAL,
             "components": [1.0, 1.5], "labels": ["c", "d"], "total": 2.0}]
        try:
            outcome = relation_binding.bind(_statement(), CLEAN_FACTS)
        finally:
            relation_binding.candidates_for = original
        self.assertFalse(outcome["promoted"])
        self.assertEqual(outcome["reason"], relation_binding.REASON_AMBIGUOUS)

    def test_G_an_unsupported_relation_type_yields_no_candidate(self):
        """A zone publishing no component allowances has nothing to verify."""
        facts = {"zoning": {"attributes": {"FSI_TOTAL": 1.0,
                                           "FSI_COMMERCIAL_USE": -1.0}}}
        outcome = relation_binding.bind(
            _statement(text="The height limit of 14.0 m binds before the FSI "
                            "of 1.0 does."), facts)
        self.assertFalse(outcome["promoted"])
        self.assertEqual(outcome["reason"], relation_binding.REASON_NO_CANDIDATE)

    def test_H_a_statement_with_no_derivation_is_left_alone(self):
        for statement in (_statement(kind="AUTHORITY_SAYS"),
                          _statement(kind="PROPERTY_FACT"),
                          _statement(text="The parcel is in ward 19.")):
            outcome = relation_binding.bind(statement, CLEAN_FACTS)
            self.assertFalse(outcome["promoted"])
            self.assertEqual(outcome["derivation"], contract.DERIVATION_MODEL)

    def test_a_refuted_relation_is_not_promoted(self):
        facts = {"zoning": {"attributes": {"FSI_TOTAL": 9.0,
                                           "FSI_COMMERCIAL_USE": 2.0,
                                           "FSI_RESIDENTIAL_USE": 2.5}}}
        statement = _statement(
            text="Commercial 2.0 and residential 2.5 together exceed the total "
                 "of 9.0.")
        outcome = relation_binding.bind(statement, facts)
        self.assertEqual(outcome["attestation"]["result"],
                         derivation_check.REFUTED)
        self.assertFalse(outcome["promoted"])
        self.assertEqual(outcome["reason"], relation_binding.REASON_REFUTED)


class PositiveFixtures(unittest.TestCase):
    """Section 12 A-F."""

    def setUp(self):
        self.document = _document([_statement()])
        self.annotated, self.report = relation_binding.annotate(
            self.document, CLEAN_FACTS, verified_at="2026-09-12T00:00:00Z")
        self.statement = self.annotated["statements"][0]

    def test_A_the_exact_arithmetic_relation_is_recomputed(self):
        check = self.statement["derivation_check"]
        self.assertEqual(check["computed"]["sum"], 4.5)
        self.assertEqual(check["computed"]["total"], 3.0)
        self.assertEqual(check["result"], derivation_check.VERIFIED)

    def test_B_inputs_are_established_so_the_conclusion_may_be(self):
        self.assertTrue(self.statement["derivation_check"]["supports_established"])

    def test_C_the_attestation_binds_to_this_statement(self):
        self.assertTrue(relation_binding.verify_binding(self.statement,
                                                        CLEAN_FACTS))
        self.assertTrue(self.statement["derivation_check"]["binding"]
                        .startswith("bind:"))

    def test_D_the_governed_derivation_becomes_deterministic(self):
        self.assertEqual(self.statement["derivation"],
                         contract.DERIVATION_DETERMINISTIC)
        self.assertTrue(self.report[0]["promoted"])

    def test_E_the_claim_may_now_reach_the_stronger_ceiling(self):
        promoted = json.loads(json.dumps(self.annotated))
        promoted["statements"][0]["statement_status"] = "ESTABLISHED"
        promoted["statements"][0]["confidence"] = "HIGH"
        vr21 = [f for f in validator.validate(promoted)["findings"]
                if f.get("rule_id") == "VR-21"]
        self.assertEqual(vr21, [], "deterministic proof permits the ceiling")

    def test_E2_the_ceiling_is_permitted_not_forced(self):
        """Section 7: the evidence permits the ceiling, it does not require it."""
        self.assertEqual(self.statement["statement_status"], "PROVISIONAL",
                         "promotion does not rewrite what the model said")
        self.assertEqual(validator.validate(self.annotated)["error_count"], 0)

    def test_F_the_original_model_payload_is_unchanged(self):
        original = self.document["statements"][0]
        self.assertNotIn("derivation", original)
        self.assertNotIn("derivation_check", original)
        self.assertEqual(original["statement_status"], "PROVISIONAL")

    def test_the_attestation_carries_the_provenance_section_9_requires(self):
        check = self.statement["derivation_check"]
        for field in ("verifier_version", "binder_version", "operation", "inputs",
                      "computed", "inputs_hash", "result", "supports_established",
                      "verified_at", "binding", "evidence_refs"):
            self.assertIn(field, check, field)
        self.assertEqual(check["verified_at"], "2026-09-12T00:00:00Z")


class ThePromotionIsNotAFindingGenerator(unittest.TestCase):
    """Section 14: keep discovery and deterministic generation separate."""

    def test_a_provable_relation_the_model_never_mentioned_creates_nothing(self):
        document = _document([_statement(
            statement_id="S-OTHER", topic="HEIGHT",
            text="The height overlay caps the building at 14.0 m.")])
        annotated, report = relation_binding.annotate(document, CLEAN_FACTS)
        self.assertEqual(len(annotated["statements"]), 1,
                         "no statement is invented from a verifiable relation")
        self.assertFalse(report[0]["promoted"])

    def test_the_binder_never_writes_statement_text(self):
        import inspect
        source = inspect.getsource(relation_binding)
        for banned in ('statement["text"] =', "statement['text'] =",
                       'append({"kind"', "statements.append"):
            self.assertNotIn(banned, source, banned)


class TheCompilerWiresTheWholePath(unittest.TestCase):

    def test_the_envelope_separates_model_payload_from_governed(self):
        from services import feasibility_compiler as compiler
        import inspect
        fields = compiler.CompilerOutcome.__dataclass_fields__
        for field in ("go_pdz_payload", "governed_payload", "bindings",
                      "promoted_statements"):
            self.assertIn(field, fields)
        source = inspect.getsource(compiler.compile_feasibility)
        self.assertIn("validator.validate(governed)", source,
                      "validation runs on the copy ARCHIOSK classified")

    def test_the_projection_rechecks_the_binding_when_evidence_is_supplied(self):
        bound = relation_binding.bind(_statement(), CLEAN_FACTS)
        document = _document([_statement(
            derivation=contract.DERIVATION_DETERMINISTIC,
            derivation_check=bound["attestation"],
            statement_status="ESTABLISHED", confidence="HIGH")])
        kept = validator.governed_projection(document, CLEAN_FACTS)
        self.assertEqual(kept["statements"][0]["governed"]["derivation"],
                         contract.DERIVATION_DETERMINISTIC)
        moved = {"zoning": {"attributes": dict(
            CLEAN_FACTS["zoning"]["attributes"], FSI_TOTAL=5.0)}}
        demoted = validator.governed_projection(document, moved)
        self.assertEqual(demoted["statements"][0]["governed"]["derivation"],
                         contract.DERIVATION_MODEL)
        self.assertTrue(demoted["statements"][0]["governed"]["ceiling_applied"])


if __name__ == "__main__":
    unittest.main()
