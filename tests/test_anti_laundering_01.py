"""CLAUDE-ANTI-LAUNDERING-01 - three boundaries a weaker state must not cross.

    SILENCE                is not   PERMISSION
    A VALUE THAT MATCHES   is not   CORROBORATION
    A DERIVATION           is not   AN AUTHORITY

Each invariant here exists because the failure it prevents is INVISIBLE at the
step that commits it. Nothing lies; a boundary simply was not typed, so nothing
could check it. See `governance/current/anti-laundering-invariants.md`.
"""
from __future__ import annotations

import copy
import unittest

from services import entity_binding as binding
from services import feasibility_compiler as compiler
from services import go_pdz_contract as contract
from services import go_pdz_validator as validator
from services import planning_posture as posture


# --- the real Toronto shape the directive's worked example comes from --------
#: 573 Shuter Street's own family of figures, restated as the directive states
#: them: components that sum PAST the cap, so the sum and the cap are different
#: numbers with different meanings and a checker can be caught confusing them.
ZONING_FACTS = {
    "attributes": {
        "ZN_ZONE": "CR",
        "FSI_TOTAL": 2.0,
        "FSI_COMMERCIAL_USE": 1.0,
        "FSI_RESIDENTIAL_USE": 1.5,
        "ZN_EXCPTN": "N",
    },
}
EVIDENCE_FACTS = {"zoning": ZONING_FACTS}


def _statement(text, **overrides):
    base = {"statement_id": "S-GO-1", "kind": "GO_INTERPRETS",
            "topic": "DENSITY", "text": text,
            "statement_status": "PROVISIONAL", "confidence": "MEDIUM"}
    base.update(overrides)
    return base


def _document(*statements, **overrides):
    base = {
        "contract": contract.CONTRACT_ID,
        "schema_version": contract.SCHEMA_VERSION,
        "gate": contract.GATE_01,
        "next_authorized_gate": contract.GATE_02,
        "subject": {"subject_id": "SUBJ-1",
                    "address_as_given": "573 Shuter Street",
                    "parcel_identifier": "TOR-PARCEL-TEST",
                    "municipality": "City of Toronto",
                    "identity_confidence": "HIGH"},
        "authorities": [{"authority_id": "TOR-BYLAW-569-2013",
                         "name": "City of Toronto Zoning By-law 569-2013",
                         "authority_status": "IN_FORCE",
                         "effective_date": "2013-05-09"}],
        "statements": list(statements),
        "site_specific_exceptions": [],
        "unresolved": [],
        "result_status": "GOVERNED_RESULT",
    }
    base.update(overrides)
    return base


def _rules_fired(document):
    return {finding["rule_id"]
            for finding in validator.validate_semantics(document)}


# ============================================================================
# INVARIANT A - EFFECT TYPING
# ============================================================================

class SilenceIsNotPermission(unittest.TestCase):
    """A, B, C, D."""

    def test_a_explicit_prohibition_is_not_silence(self):
        """The two are distinct primitives, and neither implies the other."""
        self.assertIn(contract.EFFECT_EXPLICIT_PROHIBITION,
                      contract.STATUTORY_EFFECTS)
        self.assertIn(contract.EFFECT_NO_EXPRESS_PROVISION,
                      contract.STATUTORY_EFFECTS)
        self.assertNotEqual(contract.EFFECT_EXPLICIT_PROHIBITION,
                            contract.EFFECT_NO_EXPRESS_PROVISION)
        # A prohibition needs an instrument that prohibits. Silence cannot.
        self.assertTrue(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PROHIBITION, contract.BASIS_EXPRESS_TEXT))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PROHIBITION, contract.BASIS_UNRESOLVED))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PROHIBITION, contract.BASIS_DETERMINISTIC))

    def test_there_is_no_silent_permitted_primitive(self):
        """The directive's central prohibition, asserted against the vocabulary."""
        for value in contract.STATUTORY_EFFECTS:
            self.assertNotIn("SILENT", value)
        source = open("services/go_pdz_contract.py", encoding="utf-8").read()
        # The name may appear only where it is being REFUSED, never as a value.
        for effect in contract.STATUTORY_EFFECTS:
            self.assertNotEqual(effect, "SILENT_PERMITTED")
        self.assertNotIn('"SILENT_PERMITTED"', source)

    def test_b_no_express_provision_is_not_permission(self):
        """Two ways it must fail, because there are two ways to assert it."""
        # By TYPE: permission cannot rest on an absence-shaped basis.
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PERMISSION, contract.BASIS_UNRESOLVED))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PERMISSION, contract.BASIS_DETERMINISTIC))
        document = _document(_statement(
            "No provision addresses this, so a tower is permitted.",
            statutory_effect=contract.EFFECT_EXPLICIT_PERMISSION,
            effect_basis=contract.BASIS_DETERMINISTIC))
        self.assertIn("VR-22", _rules_fired(document))

        # By VOICE: the effect may be typed honestly and still speak a grant.
        document = _document(_statement(
            "The by-law contains no express provision, so the use is permitted.",
            statutory_effect=contract.EFFECT_NO_EXPRESS_PROVISION,
            effect_basis=contract.BASIS_EXPRESS_TEXT))
        self.assertIn("VR-24", _rules_fired(document))

    def test_a_proven_absence_may_still_be_stated_strongly(self):
        """The other half of B, and the one a careless rule would break.

        ARCHIOSK proves absences deterministically and states them ESTABLISHED.
        A rule that forced every absence into doubt would make the real, proven
        ones present as uncertainty - so NO_EXPRESS_PROVISION is deliberately not
        capped, and only its VOICE is constrained.
        """
        document = _document(_statement(
            "The City's Heritage District layer contains no polygon applying to "
            "this parcel; every polygon within 2 km was computed outside it.",
            kind="PROPERTY_FACT",
            statement_status="ESTABLISHED", confidence="HIGH",
            statutory_effect=contract.EFFECT_NO_EXPRESS_PROVISION,
            effect_basis=contract.BASIS_DETERMINISTIC))
        fired = _rules_fired(document)
        self.assertNotIn("VR-22", fired)
        self.assertNotIn("VR-23", fired)
        self.assertNotIn("VR-24", fired)

    def test_c_a_removed_requirement_is_not_a_prohibition(self):
        self.assertNotEqual(contract.EFFECT_REQUIREMENT_REMOVED,
                            contract.EFFECT_EXPLICIT_PROHIBITION)
        # A requirement is removed by an instrument that removes it - never by
        # the parent regime merely existing, and never by computation.
        self.assertTrue(contract.basis_supports_effect(
            contract.EFFECT_REQUIREMENT_REMOVED, contract.BASIS_SITE_SPECIFIC))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_REQUIREMENT_REMOVED, contract.BASIS_PARENT_REGIME))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_REQUIREMENT_REMOVED, contract.BASIS_DETERMINISTIC))
        document = _document(_statement(
            "The setback requirement no longer applies.",
            statutory_effect=contract.EFFECT_REQUIREMENT_REMOVED,
            effect_basis=contract.BASIS_DETERMINISTIC))
        self.assertIn("VR-22", _rules_fired(document))

    def test_the_four_absence_states_are_four_distinct_values(self):
        """NO EVIDENCE != NO REQUIREMENT != REMOVED != PROHIBITED."""
        distinct = {contract.EFFECT_UNRESOLVED,
                    contract.EFFECT_NO_EXPRESS_PROVISION,
                    contract.EFFECT_NOT_APPLICABLE,
                    contract.EFFECT_REQUIREMENT_REMOVED,
                    contract.EFFECT_EXPLICIT_PROHIBITION}
        self.assertEqual(len(distinct), 5)

    def test_d_an_unresolved_effect_fails_closed(self):
        document = _document(_statement(
            "The effect of the provision on this parcel is undetermined.",
            statement_status="ESTABLISHED", confidence="HIGH",
            statutory_effect=contract.EFFECT_UNRESOLVED,
            effect_basis=contract.BASIS_UNRESOLVED))
        self.assertIn("VR-23", _rules_fired(document))
        self.assertEqual(contract.effect_ceiling_for(contract.EFFECT_UNRESOLVED),
                         ("UNRESOLVED", "LOW"))

    def test_an_unrecognised_effect_or_basis_supports_nothing(self):
        for effect, basis in ((None, contract.BASIS_EXPRESS_TEXT),
                              ("INVENTED_EFFECT", contract.BASIS_EXPRESS_TEXT),
                              (contract.EFFECT_EXPLICIT_PERMISSION, None),
                              (contract.EFFECT_EXPLICIT_PERMISSION, "VIBES")):
            self.assertFalse(contract.basis_supports_effect(effect, basis),
                             "%s / %s" % (effect, basis))

    def test_an_untyped_document_is_unaffected(self):
        """The whole reason the fields are optional: no stored result changes."""
        document = _document(_statement("An ordinary interpretation.",
                                        statement_status="PROVISIONAL",
                                        confidence="MEDIUM"))
        fired = _rules_fired(document)
        for rule in ("VR-22", "VR-23", "VR-24"):
            self.assertNotIn(rule, fired)

    def test_the_new_fields_are_declared_in_the_schema(self):
        properties = contract.SCHEMA["properties"]["statements"]["items"][
            "properties"]
        self.assertIn("statutory_effect", properties)
        self.assertIn("effect_basis", properties)
        required = contract.SCHEMA["properties"]["statements"]["items"]["required"]
        self.assertNotIn("statutory_effect", required, "must stay optional")
        self.assertNotIn("effect_basis", required, "must stay optional")


# ============================================================================
# INVARIANT B - ENTITY-ROLE BINDING
# ============================================================================

class AValueMatchIsNotCorroboration(unittest.TestCase):
    """E, F, G, H."""

    def test_the_host_owns_the_role_assignment(self):
        roles = binding.host_roles(EVIDENCE_FACTS)
        self.assertIn("2", roles[binding.ROLE_TOTAL_FSI_CAP])
        self.assertIn("1", roles[binding.ROLE_COMMERCIAL_COMPONENT])
        self.assertIn("1.5", roles[binding.ROLE_RESIDENTIAL_COMPONENT])
        # COMPUTED, not read from any contribution.
        self.assertIn("2.5", roles[binding.ROLE_COMPUTED_COMPONENT_SUM])
        self.assertIn("0.5", roles[binding.ROLE_EXCEEDS_BY])

    def test_e_correct_value_in_the_correct_role_passes(self):
        outcome = binding.bind_statement(_statement(
            "The total FSI of 2.0 is the cap, while the commercial component is "
            "1.0 and the residential component is 1.5."), EVIDENCE_FACTS)
        self.assertEqual(outcome["failures"], [])
        bound = {(b["value"], b["asserted_role"]) for b in outcome["bindings"]
                 if b["bound"]}
        self.assertIn(("2.0", binding.ROLE_TOTAL_FSI_CAP), bound)
        self.assertIn(("1.0", binding.ROLE_COMMERCIAL_COMPONENT), bound)
        self.assertIn(("1.5", binding.ROLE_RESIDENTIAL_COMPONENT), bound)

    def test_f_the_worked_case_correct_value_wrong_role_fails(self):
        """THE test. Every number host-owned, provenance intact, meaning inverted."""
        outcome = binding.bind_statement(
            _statement("The permitted FSI is 2.5."), EVIDENCE_FACTS)
        failures = outcome["failures"]
        self.assertEqual(len(failures), 1, failures)
        self.assertEqual(failures[0]["failure"], binding.FAILURE_ROLE_MISMATCH)
        self.assertEqual(failures[0]["value"], "2.5")
        self.assertEqual(failures[0]["asserted_role"], binding.ROLE_TOTAL_FSI_CAP)
        self.assertEqual(failures[0]["host_role"],
                         binding.ROLE_COMPUTED_COMPONENT_SUM)

    def test_the_same_value_would_have_passed_a_membership_test(self):
        """Why role fidelity had to be added rather than assumed present.

        2.5 IS in the host's own value set, so any checker comparing values
        against admitted evidence - including `relation_binding`'s
        `needed.issubset(present)` - sees nothing wrong with this sentence.
        """
        owned = set()
        for forms in binding.host_roles(EVIDENCE_FACTS).values():
            owned |= forms
        self.assertIn("2.5", owned, "the value is genuinely host-owned")
        outcome = binding.bind_statement(
            _statement("The permitted FSI is 2.5."), EVIDENCE_FACTS)
        self.assertTrue(outcome["failures"], "and it must still be refused")

    def test_g_a_novel_numeric_claim_fails(self):
        outcome = binding.bind_statement(
            _statement("The total FSI is 4.0."), EVIDENCE_FACTS)
        self.assertEqual([f["failure"] for f in outcome["failures"]],
                         [binding.FAILURE_UNBOUNDED_NUMERIC])
        self.assertEqual(outcome["failures"][0]["value"], "4.0")

    def test_a_number_with_no_asserted_role_is_not_a_claim(self):
        """Silence about meaning is not an assertion to contradict."""
        outcome = binding.bind_statement(
            _statement("Chapter 900 was consulted on 12 occasions."),
            EVIDENCE_FACTS)
        self.assertEqual(outcome["failures"], [])
        self.assertTrue(all(b["bound"] is None for b in outcome["bindings"]))

    def test_a_role_the_host_cannot_source_is_unchecked_not_failed(self):
        """Our coverage gap must not become the contribution's failure.

        The Toronto zoning record publishes no site area, so a true statement
        about site area must survive a checker that cannot see one.
        """
        outcome = binding.bind_statement(
            _statement("The site area is 2302.79 square metres."), EVIDENCE_FACTS)
        self.assertEqual(outcome["failures"], [])
        unchecked = [b for b in outcome["bindings"]
                     if b["asserted_role"] == binding.ROLE_SITE_AREA]
        self.assertTrue(unchecked)
        self.assertIsNone(unchecked[0]["bound"])

    def test_a_role_phrase_does_not_reach_across_an_intervening_number(self):
        """The regression that would have quarantined a TRUE statement.

        This is the wording `deterministic_findings` produces. With a bare
        nearest-preceding-phrase rule, `sum to` reaches past 2.5 and asserts that
        2.0 is the component sum - a ROLE_MISMATCH against a correct sentence.
        A role phrase already taken by a nearer number cannot claim a later one.
        """
        outcome = binding.bind_statement(_statement(
            "The components sum to 2.5, exceeding the cap of 2.0."),
            EVIDENCE_FACTS)
        self.assertEqual(outcome["failures"], [], outcome["failures"])
        by_value = {b["value"]: b for b in outcome["bindings"]}
        self.assertEqual(by_value["2.5"]["asserted_role"],
                         binding.ROLE_COMPUTED_COMPONENT_SUM)
        self.assertTrue(by_value["2.5"]["bound"])
        # 2.0 attaches to no modelled phrase here, so it is not a claim - the
        # safe outcome, and better than a confident wrong one.
        self.assertIsNone(by_value["2.0"]["asserted_role"])

    def test_the_full_deterministic_finding_wording_is_admitted(self):
        """End to end on the real sentence, through the admission boundary."""
        document = _document(_statement(
            "The zoning record's commercial component of 1.0 and residential "
            "component of 1.5 sum to 2.5, which exceeds the total FSI of 2.0."))
        admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual(failures, [], failures)
        self.assertEqual(len(admitted["statements"]), 1)

    def test_archiosks_own_proven_finding_is_not_quarantined(self):
        """THE NEAR-MISS, pinned against the REAL originator rather than a
        paraphrase of it.

        `deterministic_findings._fsi_text` emits "1.0 for commercial use, 1.5 for
        residential use" as a GO_INTERPRETS statement, so it passes through this
        admission boundary. An earlier version of `asserted_role` read that as
        commercial=1.5 - because "commercial use" sits closer to 1.5 than
        "residential use" does - and quarantined a finding ARCHIOSK had proven
        deterministically in five runs of five. Generating the statement here
        rather than restating its wording means a future edit to that wording
        cannot silently reintroduce the failure.
        """
        from services import deterministic_findings

        outcome = deterministic_findings.fsi_envelope(EVIDENCE_FACTS)
        self.assertTrue(outcome["originated"], outcome["reason"])
        statement = outcome["statement"]
        self.assertEqual(statement["kind"], "GO_INTERPRETS",
                         "if this changes, admission no longer applies to it")

        document = _document(statement)
        admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual(failures, [], failures)
        self.assertEqual(len(admitted["statements"]), 1,
                         "ARCHIOSK's own proven finding must survive admission")

    def test_every_value_in_the_real_finding_binds_to_its_own_role(self):
        from services import deterministic_findings

        statement = deterministic_findings.fsi_envelope(
            EVIDENCE_FACTS)["statement"]
        outcome = binding.bind_statement(statement, EVIDENCE_FACTS)
        bound = {b["value"]: b["asserted_role"] for b in outcome["bindings"]
                 if b["bound"]}
        self.assertEqual(bound.get("2.0"), binding.ROLE_TOTAL_FSI_CAP)
        self.assertEqual(bound.get("1.0"), binding.ROLE_COMMERCIAL_COMPONENT)
        self.assertEqual(bound.get("1.5"), binding.ROLE_RESIDENTIAL_COMPONENT)
        self.assertEqual(bound.get("2.5"), binding.ROLE_COMPUTED_COMPONENT_SUM)
        self.assertEqual(bound.get("0.5"), binding.ROLE_EXCEEDS_BY)

    def test_h_an_unbound_exception_reference_fails(self):
        document = _document(
            _statement("Exception TOR-EXCEPTION-9999 removes the setback."),
            site_specific_exceptions=[{"exception_id": "TOR-EXCEPTION-2382",
                                       "indicated_by": "ZN_EXCPTN=Y",
                                       "text_retrieved": True}])
        _admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual([f["failure"] for f in failures],
                         [binding.FAILURE_UNBOUND_EXCEPTION])

    def test_h_a_declared_exception_reference_binds(self):
        document = _document(
            _statement("Exception TOR-EXCEPTION-2382 removes the setback."),
            site_specific_exceptions=[{"exception_id": "TOR-EXCEPTION-2382",
                                       "indicated_by": "ZN_EXCPTN=Y",
                                       "text_retrieved": True}])
        _admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual(failures, [])

    def test_h_an_exception_reference_is_unchecked_when_none_is_declared(self):
        """A checker whose only behaviour is a false positive is worse than none.

        `_zoning_facts` carries whether an exception was acquired, never its id,
        so sourcing the declared set from evidence facts would refuse EVERY
        exception reference. The document's own declaration is the authority.
        """
        document = _document(
            _statement("Exception TOR-EXCEPTION-2382 removes the setback."))
        _admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual(failures, [])

    def test_authority_references_are_not_reimplemented_here(self):
        """VR-19 already IS this rule; a second checker would be a second truth."""
        self.assertIn("VR-19", validator.RULES)
        self.assertIn("authority", validator.RULES["VR-19"][1].lower())
        document = _document(_statement(
            "The by-law says so.", kind="AUTHORITY_SAYS",
            authority_refs=["TOR-BYLAW-NOT-DECLARED"]))
        self.assertIn("VR-19", _rules_fired(document))

    def test_a_host_originated_statement_is_not_subject_to_admission(self):
        """Checking ARCHIOSK's own transcription against itself is circular."""
        document = _document(
            _statement("FSI_TOTAL = 2.0 with a permitted FSI of 2.5 recorded.",
                       kind="AUTHORITY_SAYS", statement_id="S-ZONE",
                       authority_refs=["TOR-BYLAW-569-2013"]))
        admitted, bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertEqual(failures, [])
        self.assertEqual(bindings, [])
        self.assertEqual(len(admitted["statements"]), 1)

    def test_confidence_reduction_is_not_available_as_a_rescue(self):
        """Section 7: a failed binding is quarantined, never merely weakened."""
        before = _statement("The permitted FSI is 2.5.",
                            statement_status="PROVISIONAL", confidence="MEDIUM")
        document = _document(copy.deepcopy(before))
        admitted, _bindings, failures = binding.admit(document, EVIDENCE_FACTS)
        self.assertTrue(failures)
        self.assertEqual(admitted["statements"], [],
                         "the statement is excluded, not admitted more weakly")
        # And the input statement was not rewritten on the way out.
        self.assertEqual(document["statements"][0], before)


# ============================================================================
# INVARIANT C - MONOTONIC POSTURE INHERITANCE
# ============================================================================

class DerivationMayNotImprovePosture(unittest.TestCase):
    """I, J, K, L."""

    def test_the_ladder_runs_authoritative_to_conservative(self):
        self.assertEqual(posture.POSTURE_LADDER[0], posture.POSTURE_AS_OF_RIGHT)
        self.assertEqual(posture.POSTURE_LADDER[-1], posture.POSTURE_UNSUPPORTED)
        self.assertLess(posture.strength_index(posture.POSTURE_AS_OF_RIGHT),
                        posture.strength_index(posture.POSTURE_RELIEF_DEPENDENT))

    def test_i_a_relief_dependent_parent_cannot_yield_as_of_right(self):
        outcome = posture.inherit(posture.POSTURE_RELIEF_DEPENDENT,
                                  posture.POSTURE_AS_OF_RIGHT)
        self.assertEqual(outcome["posture"], posture.POSTURE_RELIEF_DEPENDENT)
        self.assertTrue(outcome["refused"])
        self.assertEqual(outcome["reason"], posture.REFUSED_NO_AUTHORITY)

    def test_i_no_derivation_reaches_as_of_right_from_below(self):
        for parent in (posture.POSTURE_RELIEF_DEPENDENT,
                       posture.POSTURE_SPECULATIVE_TEST,
                       posture.POSTURE_UNSUPPORTED):
            for target in (posture.POSTURE_AS_OF_RIGHT,
                           posture.POSTURE_APPROVED_RELIEF):
                with self.subTest(parent=parent, target=target):
                    if not posture.more_authoritative_than(target, parent):
                        continue
                    outcome = posture.inherit(parent, target)
                    self.assertTrue(outcome["refused"])
                    self.assertEqual(outcome["posture"], parent)

    def test_j_a_derivation_may_preserve_its_parent_posture(self):
        for parent in posture.POSTURE_LADDER:
            with self.subTest(parent=parent):
                outcome = posture.inherit(parent, parent)
                self.assertEqual(outcome["posture"], parent)
                self.assertFalse(outcome["refused"])
                self.assertEqual(outcome["posture_basis"],
                                 posture.BASIS_INHERITED)

    def test_j_a_derivation_proposing_nothing_inherits_the_qualification(self):
        """The default must carry the caveat, not drop it."""
        outcome = posture.inherit(posture.POSTURE_RELIEF_DEPENDENT)
        self.assertEqual(outcome["posture"], posture.POSTURE_RELIEF_DEPENDENT)
        self.assertFalse(outcome["refused"])

    def test_k_a_derivation_may_become_more_conservative(self):
        outcome = posture.inherit(posture.POSTURE_AS_OF_RIGHT,
                                  posture.POSTURE_SPECULATIVE_TEST)
        self.assertEqual(outcome["posture"], posture.POSTURE_SPECULATIVE_TEST)
        self.assertFalse(outcome["refused"])
        self.assertEqual(outcome["posture_basis"], posture.BASIS_MORE_CONSERVATIVE)
        self.assertEqual(outcome["inherited_posture"], posture.POSTURE_AS_OF_RIGHT)

    def test_k_a_speculative_parent_stays_at_least_speculative(self):
        for proposed in (None, posture.POSTURE_SPECULATIVE_TEST,
                         posture.POSTURE_UNSUPPORTED,
                         posture.POSTURE_AS_OF_RIGHT,
                         posture.POSTURE_RELIEF_DEPENDENT):
            with self.subTest(proposed=proposed):
                outcome = posture.inherit(posture.POSTURE_SPECULATIVE_TEST,
                                          proposed)
                self.assertGreaterEqual(
                    posture.strength_index(outcome["posture"]),
                    posture.strength_index(posture.POSTURE_SPECULATIVE_TEST))

    def test_l_a_governed_authority_event_may_improve_posture(self):
        event = {"authority_ref": "TOR-COA-DECISION-2026-114",
                 "decided_by": "Toronto Committee of Adjustment",
                 "decision": "MINOR_VARIANCE_GRANTED",
                 "decided_at": "2026-09-01"}
        outcome = posture.authorize_transition(
            posture.POSTURE_RELIEF_DEPENDENT, posture.POSTURE_APPROVED_RELIEF,
            authority_event=event)
        self.assertEqual(outcome["posture"], posture.POSTURE_APPROVED_RELIEF)
        self.assertFalse(outcome["refused"])
        self.assertEqual(outcome["posture_basis"], posture.BASIS_AUTHORITY_EVENT)
        self.assertEqual(outcome["authorized_by"]["authority_ref"],
                         "TOR-COA-DECISION-2026-114")

    def test_l_an_incomplete_event_authorizes_nothing(self):
        complete = {"authority_ref": "A", "decided_by": "B",
                    "decision": "GRANTED", "decided_at": "2026-09-01"}
        for missing in complete:
            partial = {k: v for k, v in complete.items() if k != missing}
            with self.subTest(missing=missing):
                self.assertFalse(posture.is_governed_authority_event(partial))
                outcome = posture.authorize_transition(
                    posture.POSTURE_RELIEF_DEPENDENT,
                    posture.POSTURE_APPROVED_RELIEF, authority_event=partial)
                self.assertTrue(outcome["refused"])
                self.assertEqual(outcome["posture"],
                                 posture.POSTURE_RELIEF_DEPENDENT)

    def test_l_a_derivations_own_confidence_is_not_an_authority_event(self):
        """A cost estimate cannot vouch for its own regulatory standing."""
        for pretender in ({"confidence": "HIGH"},
                          {"model": "gemini-3.8-flash", "certainty": 0.99},
                          {"decision": "GRANTED"},
                          "APPROVED", None, 1):
            with self.subTest(pretender=pretender):
                self.assertFalse(posture.is_governed_authority_event(pretender))

    def test_approved_relief_has_no_derivational_path(self):
        self.assertIn(posture.POSTURE_APPROVED_RELIEF,
                      posture.AUTHORITY_ONLY_POSTURES)
        for parent in posture.POSTURE_LADDER:
            outcome = posture.inherit(parent, posture.POSTURE_APPROVED_RELIEF)
            if parent == posture.POSTURE_APPROVED_RELIEF:
                continue
            with self.subTest(parent=parent):
                if posture.more_authoritative_than(
                        posture.POSTURE_APPROVED_RELIEF, parent):
                    self.assertTrue(outcome["refused"])
                    self.assertNotEqual(outcome["posture"],
                                        posture.POSTURE_APPROVED_RELIEF)

    def test_an_unknown_parent_fails_closed_to_unsupported(self):
        for parent in (None, "", "PROBABLY_FINE", 7):
            with self.subTest(parent=parent):
                outcome = posture.inherit(parent, posture.POSTURE_AS_OF_RIGHT)
                self.assertEqual(outcome["posture"], posture.POSTURE_UNSUPPORTED)
                self.assertTrue(outcome["refused"])

    def test_an_unknown_proposal_is_ignored_rather_than_honoured(self):
        outcome = posture.inherit(posture.POSTURE_RELIEF_DEPENDENT, "AS_OF_RIGHT_ISH")
        self.assertEqual(outcome["posture"], posture.POSTURE_RELIEF_DEPENDENT)
        self.assertTrue(outcome["refused"])


# ============================================================================
# ASSEMBLER ADMISSION
# ============================================================================

def _evidence():
    return compiler.FeasibilityEvidence(
        investigation_id="INV-ANTI-LAUNDER-1",
        input_address="573 Shuter Street",
        normalized_address="573 Shuter St",
        parcel_identifier="TOR-PARCEL-TEST",
        municipality="City of Toronto",
        identity_confidence="HIGH",
        spatial_results={"zoning": {"spatial_relation": "INSIDE",
                                    "spatial_basis": "DETERMINISTIC_GIS"}},
        admitted_authorities=[{"authority_id": "TOR-BYLAW-569-2013",
                               "name": "City of Toronto Zoning By-law 569-2013"}],
        zoning=copy.deepcopy(ZONING_FACTS))


def _payload(*extra_statements):
    document = _document(
        _statement("The parcel lies within the CR zone.",
                   statement_id="S-ZONE", kind="AUTHORITY_SAYS",
                   authority_refs=["TOR-BYLAW-569-2013"],
                   statement_status="ESTABLISHED", confidence="HIGH",
                   spatial_relation="INSIDE", spatial_basis="DETERMINISTIC_GIS"),
        *extra_statements)
    document["authorities"][0].update({
        "instrument": "City of Toronto", "citation": "Chapter 40",
        "version_identifier": "569-2013",
        "source_type": "OFFICIAL_MACHINE_READABLE_GEOMETRY",
        "retrieved_at": "2026-09-13T00:00:00Z"})
    return document


class Runner:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __call__(self, instructions, evidence, attempt):
        self.calls += 1
        return copy.deepcopy(self.payload)


class TheAssemblerQuarantinesRatherThanWeakens(unittest.TestCase):
    """M, N, O."""

    def _compile(self, *extra):
        return compiler.compile_feasibility(_evidence(),
                                           runner=Runner(_payload(*extra)))

    def test_m_a_quarantined_failure_remains_auditable(self):
        outcome = self._compile(_statement("The permitted FSI is 2.5.",
                                           statement_id="S-GO-BAD"))
        self.assertEqual(outcome.quarantined_statements, ["S-GO-BAD"])
        self.assertEqual([f["failure"] for f in outcome.binding_failures],
                         [binding.FAILURE_ROLE_MISMATCH])

        # THE RAW CONTRIBUTION SURVIVES. Quarantine excludes it from the governed
        # document; it does not destroy the evidence that it was offered.
        raw_ids = [s["statement_id"] for s in outcome.go_pdz_payload["statements"]]
        governed_ids = [s["statement_id"]
                        for s in outcome.governed_payload["statements"]]
        self.assertIn("S-GO-BAD", raw_ids)
        self.assertNotIn("S-GO-BAD", governed_ids)

        # And the audit trail names the roles, so a reader can see WHY.
        failure = outcome.binding_failures[0]
        self.assertEqual(failure["asserted_role"], binding.ROLE_TOTAL_FSI_CAP)
        self.assertEqual(failure["host_role"], binding.ROLE_COMPUTED_COMPONENT_SUM)

    def test_m_the_bindings_record_what_was_checked_not_only_what_failed(self):
        outcome = self._compile(_statement(
            "The total FSI of 2.0 is the cap.", statement_id="S-GO-OK"))
        self.assertEqual(outcome.binding_failures, [])
        checked = [b for record in outcome.entity_bindings
                   for b in record["bindings"]]
        self.assertTrue(any(b["bound"] for b in checked))

    def test_n_a_nonmaterial_quarantine_still_yields_a_governed_document(self):
        """Section 7: quarantine must not invalidate the whole document."""
        outcome = self._compile(_statement("The permitted FSI is 2.5.",
                                           statement_id="S-GO-BAD"))
        self.assertTrue(outcome.quarantined_statements)
        self.assertIsNotNone(outcome.governed_payload)
        self.assertTrue(outcome.governed_payload["statements"],
                        "the surviving statements still form a document")
        self.assertTrue(outcome.semantic_validation_valid,
                        "validation errors: %s"
                        % (outcome.validation_result or {}).get("findings"))
        self.assertTrue(outcome.promotable)

    def test_o_host_facts_are_not_mutated_by_admission(self):
        evidence = _evidence()
        before = copy.deepcopy(evidence.for_model())
        compiler.compile_feasibility(
            evidence, runner=Runner(_payload(
                _statement("The permitted FSI is 2.5.", statement_id="S-GO-BAD"))))
        self.assertEqual(evidence.for_model(), before)
        self.assertEqual(evidence.zoning["attributes"]["FSI_TOTAL"], 2.0)

    def test_o_a_clean_contribution_is_admitted_untouched(self):
        statement = _statement("The total FSI of 2.0 is the cap.",
                               statement_id="S-GO-OK")
        outcome = self._compile(copy.deepcopy(statement))
        admitted = [s for s in outcome.governed_payload["statements"]
                    if s["statement_id"] == "S-GO-OK"]
        self.assertEqual(len(admitted), 1)
        self.assertEqual(admitted[0]["text"], statement["text"])
        self.assertEqual(admitted[0]["confidence"], statement["confidence"])


class TheDoctrineIsRecorded(unittest.TestCase):
    """Section 2 and section 12 - the governance side, asserted not assumed."""

    PATH = "governance/current/anti-laundering-invariants.md"

    def setUp(self):
        self.text = open(self.PATH, encoding="utf-8").read()

    def test_the_three_invariant_statements_are_recorded_verbatim(self):
        for wording in (
                "SILENCE IS EVIDENCE ABOUT WHAT WAS FOUND",
                "A VALUE MATCH WITHOUT ROLE FIDELITY IS NOT CORROBORATION",
                "AUTHORITY MAY IMPROVE POSTURE. DERIVATION ALONE MAY NOT"):
            self.assertIn(wording, self.text)

    def test_every_domain_is_registered_and_only_planning_is_implemented(self):
        for domain in ("Planning & Zoning", "RFP / Procurement",
                       "Drawing Intelligence", "Document Review",
                       "Design Review"):
            self.assertIn(domain, self.text)
        self.assertIn("NOT YET IMPLEMENTED", self.text)

    def test_no_production_code_was_created_in_the_other_domains(self):
        """Section 12 forbids placeholder code, so nothing may import these."""
        import os
        for name in os.listdir("services"):
            if not name.endswith(".py"):
                continue
            body = open(os.path.join("services", name), encoding="utf-8").read()
            if "planning_posture" in body or "entity_binding" in body:
                self.assertIn(name, ("feasibility_compiler.py",
                                     "entity_binding.py",
                                     "planning_posture.py"),
                              "%s must not consume the invariants yet" % name)


if __name__ == "__main__":
    unittest.main()
