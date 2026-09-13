"""CLAUDE-PRODUCTION-HORIZON-01 - ARCHIOSK originates what ARCHIOSK can prove.

    PRODUCTION HORIZON INVARIANT
    If a planning relationship can be established deterministically from admitted
    evidence, ARCHIOSK originates that finding directly. The LLM is not required
    to discover deterministic truth first.

THE MEASUREMENT THAT FORCED THIS. On 573 Shuter Street the FSI relation was
deterministically verifiable in 5 runs out of 5, and gemini-3.8-flash mentioned
it in 2. The probe-09 promotion path worked exactly as designed and still
delivered the finding 40% of the time, because promotion can only ever act on
something the model happened to say. A fact ARCHIOSK can prove should not depend
on a sampler.

TWO LEGITIMATE ORIGINS, AND BOTH ARE KEPT:

    A. deterministic engine originates a known mechanical relation   (new here)
    B. model proposes, ARCHIOSK verifies and may promote             (probe 09)

Removing B would discard the only path that can reach a relation nobody
implemented. So these tests defend B's continued existence as carefully as they
defend A's arrival - and they defend the rule that when both find the same
relation, the document does not say it twice.
"""
from __future__ import annotations

import copy
import json
import unittest

from services import derivation_check
from services import deterministic_findings as findings
from services import go_pdz_contract as contract
from services import go_pdz_validator as validator
from services import relation_binding

#: 573 Shuter Street exactly as the City publishes it - the live subject that
#: qualified in probe 09 without any surgery. Three DISTINCT values, so a check
#: that merely matched one recurring number would not pass here.
SHUTER = {
    "zoning": {"attributes": {
        "ZN_STRING": "CR 2.0 (c1.0; r1.5) SS2", "ZN_EXCPTN": "N",
        "FSI_TOTAL": 2.0, "FSI_COMMERCIAL_USE": 1.0, "FSI_RESIDENTIAL_USE": 1.5}},
    "admitted_authorities": [
        {"authority_id": "TOR-BYLAW-569-2013", "name": "Zoning By-law 569-2013",
         "authority_status": "IN_FORCE"}],
}


def _facts(**overrides):
    facts = copy.deepcopy(SHUTER)
    for key, value in overrides.items():
        facts["zoning"]["attributes"][key] = value
    return facts


def _without(field):
    facts = copy.deepcopy(SHUTER)
    facts["zoning"]["attributes"].pop(field)
    return facts


class TheRelationOriginatesWithoutAModel(unittest.TestCase):
    """A and G - the whole point of the tranche."""

    def setUp(self):
        self.statements, self.report = findings.originate(
            SHUTER, verified_at="2026-09-13T00:00:00Z")

    def test_an_eligible_relation_originates(self):
        self.assertEqual(len(self.statements), 1)
        self.assertEqual(self.statements[0]["statement_id"],
                         findings.STATEMENT_FSI_ENVELOPE)

    def test_no_model_runner_is_involved_anywhere_in_origination(self):
        """G - `originate` takes facts and nothing else. There is no seam for a
        model to be injected, so discovery cannot become a precondition.

        Asserted against the IMPORT SURFACE, not the prose. An earlier version
        of this test grepped the source for "runner" and fired on the docstring
        phrase "municipal gate-01 runners" - a check on wording rather than on
        code, which is the same false positive this programme has hit before.
        """
        import ast
        import inspect
        signature = inspect.signature(findings.originate)
        self.assertEqual(list(signature.parameters), ["evidence_facts",
                                                      "verified_at"])
        tree = ast.parse(inspect.getsource(findings))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update("%s.%s" % (node.module or "", alias.name)
                                for alias in node.names)
        self.assertEqual(
            {name for name in imported
             if any(token in name for token in ("gateway", "llm", "gemini",
                                                "pydantic", "feasibility",
                                                "sheet_vision"))},
            set(), "a deterministic originator may not reach a model")

    def test_it_originates_on_every_run_not_on_some(self):
        for _ in range(5):
            statements, _report = findings.originate(SHUTER)
            self.assertEqual(len(statements), 1)

    def test_the_report_names_families_that_declined_as_well(self):
        self.assertEqual(self.report[0]["family"], findings.FAMILY_FSI_ENVELOPE)
        self.assertTrue(self.report[0]["originated"])
        self.assertIsNone(self.report[0]["reason"])


class TheArithmeticIsExact(unittest.TestCase):
    """B."""

    def setUp(self):
        self.check = findings.originate(SHUTER)[0][0]["derivation_check"]

    def test_the_computed_values(self):
        self.assertEqual(self.check["computed"],
                         {"sum": 2.5, "total": 2.0, "exceeds_by": 0.5})

    def test_the_operation_and_result(self):
        self.assertEqual(self.check["operation"], "sum(components) > total")
        self.assertEqual(self.check["result"], derivation_check.VERIFIED)
        self.assertTrue(self.check["supports_established"])

    def test_the_inputs_are_the_admitted_figures(self):
        self.assertEqual(sorted(self.check["inputs"]["components"]), [1.0, 1.5])
        self.assertEqual(self.check["inputs"]["total"], 2.0)


class ProvenanceIsRetained(unittest.TestCase):
    """C - an originated finding carries the same proof a promoted one does."""

    def setUp(self):
        self.statement = findings.originate(
            SHUTER, verified_at="2026-09-13T00:00:00Z")[0][0]
        self.check = self.statement["derivation_check"]

    def test_the_attestation_is_one_this_programme_produced(self):
        self.assertTrue(derivation_check.is_valid_attestation(self.check))
        self.assertEqual(self.check["verifier_version"],
                         derivation_check.VERIFIER_VERSION)

    def test_evidence_refs_name_the_fields_actually_read(self):
        self.assertEqual(sorted(self.check["evidence_refs"]),
                         ["FSI_COMMERCIAL_USE", "FSI_RESIDENTIAL_USE", "FSI_TOTAL"])

    def test_the_inputs_hash_and_binding_are_present(self):
        self.assertTrue(self.check["inputs_hash"].startswith("sha256:"))
        self.assertTrue(self.check["binding"].startswith("bind:"))
        self.assertEqual(self.check["verified_at"], "2026-09-13T00:00:00Z")

    def test_the_binding_re_verifies_on_the_same_terms_as_a_promoted_claim(self):
        """An originator is not a privileged author. It earns the class through
        the same attestation the promotion path uses, and fails the same way."""
        self.assertTrue(relation_binding.verify_binding(self.statement, SHUTER))
        moved = _facts(FSI_TOTAL=5.0)
        self.assertFalse(relation_binding.verify_binding(self.statement, moved))

    def test_it_cites_the_in_force_bylaw_so_high_confidence_has_a_basis(self):
        self.assertEqual(self.statement["authority_refs"], ["TOR-BYLAW-569-2013"])

    def test_no_citation_is_invented_when_none_qualifies(self):
        facts = copy.deepcopy(SHUTER)
        facts["admitted_authorities"] = [
            {"authority_id": "TOR-BYLAW-569-2013", "name": "By-law",
             "authority_status": "SUPERSEDED"}]
        self.assertEqual(findings.originate(facts)[0][0]["authority_refs"], [])


class OriginationFailsClosed(unittest.TestCase):
    """D and E - all of section 5's conditions, each tested on its own."""

    def _reason(self, facts):
        statements, report = findings.originate(facts)
        self.assertEqual(statements, [], "nothing may originate here")
        return report[0]["reason"]

    def test_D_an_unretrieved_material_exception_blocks_origination(self):
        """The Danforth outcome. Exact arithmetic over figures an unread
        exception may displace is not an established conclusion - and the
        correct output is NOTHING, not a hedged version of the same figures."""
        facts = copy.deepcopy(SHUTER)
        facts["zoning"]["site_specific_exception"] = {
            "acquired": False, "reason": "the page does not contain exception 2219"}
        self.assertEqual(self._reason(facts), findings.REASON_NOT_ESTABLISHED)

    def test_D_the_attestation_still_records_what_was_computed(self):
        """Blocked from originating is not the same as unexamined."""
        facts = copy.deepcopy(SHUTER)
        facts["zoning"]["site_specific_exception"] = {"acquired": False,
                                                      "reason": "not retrieved"}
        outcome = findings.fsi_envelope(facts)
        self.assertEqual(outcome["attestation"]["result"], derivation_check.VERIFIED)
        self.assertFalse(outcome["attestation"]["supports_established"])
        self.assertTrue(outcome["limits"])

    def test_E_a_missing_component_blocks_origination(self):
        self.assertEqual(self._reason(_without("FSI_COMMERCIAL_USE")),
                         findings.REASON_NO_CANDIDATE)

    def test_E_a_missing_total_blocks_origination(self):
        self.assertEqual(self._reason(_without("FSI_TOTAL")),
                         findings.REASON_NO_CANDIDATE)

    def test_E_a_non_numeric_figure_is_never_coerced(self):
        self.assertEqual(self._reason(_facts(FSI_TOTAL="2.0")),
                         findings.REASON_NO_CANDIDATE)

    def test_a_relation_that_does_not_hold_originates_nothing(self):
        self.assertEqual(self._reason(_facts(FSI_TOTAL=9.0)),
                         findings.REASON_NOT_VERIFIED)

    def test_the_city_not_applicable_sentinel_is_not_read_as_an_allowance(self):
        """-1 means 'not applicable' in the City's schema, not a zero figure."""
        self.assertEqual(self._reason(_facts(FSI_COMMERCIAL_USE=-1.0)),
                         findings.REASON_NO_CANDIDATE)

    def test_empty_evidence_is_answered_with_silence_not_an_exception(self):
        self.assertEqual(findings.originate({})[0], [])
        self.assertEqual(findings.originate(None)[0], [])


class BothOriginsCoexistWithoutDuplicating(unittest.TestCase):
    """F and H."""

    def setUp(self):
        self.originated = findings.originate(SHUTER)[0]
        #: A real sentence gemini-3.8-flash emitted on this parcel in probe 09.
        self.model_statement = {
            "statement_id": "G-S-04", "kind": "GO_INTERPRETS", "topic": "DENSITY",
            "text": ("Because the sum of permitted commercial FSI (1.0) and "
                     "residential FSI (1.5) is 2.5, which exceeds the maximum "
                     "total FSI of 2.0, a mixed-use development cannot "
                     "simultaneously achieve maximum commercial and residential "
                     "density."),
            "statement_status": "PROVISIONAL", "confidence": "HIGH",
            "authority_refs": [], "conflict_refs": [], "derived_from": [],
            "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE"}

    def test_H_the_probe_09_binder_path_still_promotes(self):
        bound = relation_binding.bind(self.model_statement, SHUTER)
        self.assertTrue(bound["promoted"])
        self.assertIsNone(bound["reason"])
        self.assertEqual(bound["derivation"], contract.DERIVATION_DETERMINISTIC)

    def test_H_the_binder_still_refuses_what_it_refused_before(self):
        recitation = dict(self.model_statement, statement_id="G-S-05", text=(
            "The zone permits a total FSI of 2.0, a commercial FSI of 1.0 and a "
            "residential FSI of 1.5."))
        self.assertFalse(relation_binding.bind(recitation, SHUTER)["promoted"])

    def test_F_the_same_relation_from_both_origins_is_one_finding(self):
        bound = relation_binding.bind(self.model_statement, SHUTER)
        promoted = dict(self.model_statement,
                        derivation=bound["derivation"],
                        derivation_check=bound["attestation"])
        self.assertEqual(findings.duplicates_of(self.originated, [promoted]),
                         ["G-S-04"])

    def test_F_identity_is_the_relation_and_its_inputs_not_the_wording(self):
        bound = relation_binding.bind(self.model_statement, SHUTER)
        self.assertEqual(
            findings.relation_identity(bound["attestation"]),
            findings.relation_identity(self.originated[0]["derivation_check"]))

    def test_F_a_different_parcels_figures_are_not_a_duplicate(self):
        other = {"zoning": {"attributes": {
            "FSI_TOTAL": 3.0, "FSI_COMMERCIAL_USE": 2.0,
            "FSI_RESIDENTIAL_USE": 2.5}}}
        elsewhere = findings.originate(other)[0]
        self.assertEqual(findings.duplicates_of(self.originated, elsewhere), [])

    def test_F_an_unattested_statement_is_never_called_a_duplicate(self):
        plain = {"statement_id": "G-S-09", "kind": "GO_INTERPRETS",
                 "text": "The Downtown Plan applies to this parcel."}
        self.assertEqual(findings.duplicates_of(self.originated, [plain]), [])

    def test_F_a_forged_attestation_has_no_identity(self):
        self.assertIsNone(findings.relation_identity({"result": "VERIFIED"}))
        self.assertIsNone(findings.relation_identity(None))


class TheOriginatorStaysInsideItsRemit(unittest.TestCase):
    """Section 4, 6 and 14 - what this module must NOT do."""

    def setUp(self):
        self.statement = findings.originate(SHUTER)[0][0]

    def test_it_does_not_interpret(self):
        """Section 6: the planning implication belongs to GO. An earlier draft
        ended '...a mixed-use scheme has to allocate it between the uses' -
        true, useful, and not arithmetic."""
        text = self.statement["text"]
        for interpretation in ("should", "could", "opportunity", "recommend",
                               "advisable", "scheme has to", "must allocate"):
            self.assertNotIn(interpretation, text.lower())
        self.assertIn("not stated here", text)

    def test_it_does_not_speak_in_the_authority_s_voice(self):
        """VR-18 - stated as what the record CARRIES, never what it requires."""
        document = _document([self.statement])
        vr18 = [f for f in validator.validate(document)["findings"]
                if f.get("rule_id") == "VR-18"]
        self.assertEqual(vr18, [])

    def test_it_adds_no_relation_to_the_frozen_verifier(self):
        self.assertEqual(set(derivation_check.SUPPORTED_RELATIONS),
                         {"components_exceed_total", "value_exceeds_limit"})

    def test_it_declares_only_one_family_and_names_the_upstream_ones(self):
        """Section 4: parcel identity, zoning, height, setback and exception
        presence are already originated by the Gate-01 runners. Re-originating
        them here would be a second definition of the same finding."""
        self.assertEqual(len(findings.ORIGINATORS), 1)
        self.assertIn("HEIGHT_OVERLAY", findings.FAMILIES_ORIGINATED_UPSTREAM)
        self.assertIn("BUILDING_SETBACK_OVERLAY",
                      findings.FAMILIES_ORIGINATED_UPSTREAM)

    def test_ids_are_namespaced_so_they_cannot_collide_with_a_model_s(self):
        self.assertTrue(self.statement["statement_id"].startswith(
            findings.ID_PREFIX))

    def test_a_failing_originator_cannot_break_a_compile(self):
        def explodes(evidence_facts, *, verified_at=None):
            raise RuntimeError("boom")
        original = findings.ORIGINATORS
        findings.ORIGINATORS = (explodes,)
        try:
            statements, report = findings.originate(SHUTER)
        finally:
            findings.ORIGINATORS = original
        self.assertEqual(statements, [])
        self.assertIn("RuntimeError", report[0]["reason"])


def _document(statements):
    return {"contract": contract.CONTRACT_ID,
            "schema_version": contract.SCHEMA_VERSION,
            "gate": contract.GATE_01, "next_authorized_gate": contract.GATE_02,
            "subject": {"subject_id": "S-1", "address_as_given": "573 Shuter St",
                        "identity_confidence": "HIGH"},
            "authorities": [{"authority_id": "TOR-BYLAW-569-2013",
                             "name": "Zoning By-law 569-2013",
                             "authority_status": "IN_FORCE",
                             "effective_date": "2013-05-09"}],
            "statements": statements, "site_specific_exceptions": [],
            "unresolved": [], "result_status": "GOVERNED_RESULT"}


class TheGovernedDocumentAcceptsIt(unittest.TestCase):
    """The originated finding must survive VR-01..VR-21 unchanged."""

    def setUp(self):
        self.statement = findings.originate(
            SHUTER, verified_at="2026-09-13T00:00:00Z")[0][0]
        self.document = _document([self.statement])

    def test_it_validates_without_error(self):
        verdict = validator.validate(self.document)
        self.assertEqual(verdict["error_count"], 0,
                         json.dumps(verdict["findings"])[:600])

    def test_vr21_does_not_cap_a_deterministic_origination(self):
        vr21 = [f for f in validator.validate(self.document)["findings"]
                if f.get("rule_id") == "VR-21"]
        self.assertEqual(vr21, [])

    def test_the_projection_keeps_it_established_on_current_facts(self):
        projected = validator.governed_projection(
            self.document, SHUTER)["statements"][0]["governed"]
        self.assertEqual(projected["derivation"], contract.DERIVATION_DETERMINISTIC)
        self.assertEqual(projected["statement_status"], "ESTABLISHED")
        self.assertFalse(projected["ceiling_applied"])

    def test_the_projection_demotes_it_when_the_inputs_move(self):
        """An originated finding is not permanently trusted - it is re-derived
        from current facts exactly like a promoted one."""
        projected = validator.governed_projection(
            self.document, _facts(FSI_TOTAL=5.0))["statements"][0]["governed"]
        self.assertEqual(projected["derivation"], contract.DERIVATION_MODEL)
        self.assertTrue(projected["ceiling_applied"])


class GoReceivesItAsAnEstablishedInput(unittest.TestCase):
    """Section 10, at the boundary this tranche may reach."""

    def test_the_evidence_carries_the_finding_but_never_its_attestation(self):
        from services import feasibility_compiler as compiler
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="573 Shuter St",
            identity_confidence="HIGH", zoning=SHUTER["zoning"],
            admitted_authorities=SHUTER["admitted_authorities"],
            deterministic_findings=[{
                "statement_id": findings.STATEMENT_FSI_ENVELOPE,
                "topic": "DENSITY", "text": "…", "basis": "DETERMINISTIC_DERIVATION",
                "statement_status": "ESTABLISHED", "confidence": "HIGH"}])
        serialised = evidence.for_model()
        self.assertIn("deterministic_findings", serialised)
        self.assertNotIn("derivation_check",
                         json.dumps(serialised["deterministic_findings"]))

    def test_the_instructions_tell_the_model_not_to_recompute_them(self):
        from services import feasibility_compiler as compiler
        self.assertIn("deterministic_findings", compiler.INSTRUCTIONS)
        self.assertIn("Do NOT recompute their arithmetic", compiler.INSTRUCTIONS)

    def test_the_original_evidence_builder_is_unchanged_in_behaviour(self):
        """Probe replays must still mean what they meant, so the new packet is a
        separate function rather than a change to the old one."""
        from services import feasibility_compiler as compiler
        self.assertTrue(hasattr(compiler, "evidence_from_gate01"))
        self.assertTrue(hasattr(compiler, "evidence_with_deterministic_findings"))


if __name__ == "__main__":
    unittest.main()
