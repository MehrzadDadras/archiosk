"""CLAUDE-GO-PDZ-CONTRACT-01: address in, legal envelope out, stop before program.

GO-PDZ is the contract for what ARCHIOSK may return when given nothing but a
municipal address. The blind 35 Taber reconnaissance showed the hard part is not
producing planning prose - it is refusing to produce the parts that are not yet
knowable, and being CHECKABLE about the difference.

What these tests defend, in the order the mistakes would be made:

1. **THREE LAYERS, NEVER COLLAPSED.** `STRUCTURE VALID != SEMANTICALLY VALID !=
   GOVERNED AUTHORITY`. A document can satisfy the schema and still launder an
   inference into an authority; both can pass and the municipality is still the
   only authority. `NoAuthorityPromotion` pins the third, because a green
   validator is exactly the moment someone starts treating output as law.

2. **FAIL-CLOSED.** Any ERROR and the result is not promotable. A WARNING leaves
   it valid and VISIBLE - `WarningStatesSurvive` exists because the cheapest way
   to make a validator look good is to quietly demote warnings, and the golden
   fixture having zero of them must not harden into "warnings cannot happen".

3. **THE TWO RULES THIS WAS BUILT FOR**, both observed for real rather than
   imagined:
     - an exception that cannot be read must NOT fall back to the parent zone,
       because an exception exists precisely to displace it (VR-08 / VR-20);
     - a spatial predicate must come from geometry, not from looking. "Appears
       to be inside the regulated area" is a real observation and a useless
       authority (VR-09 / VR-10).

4. **ONE FIXTURE, ONE RULE.** Every negative is the golden document with exactly
   ONE thing changed, so no failure can mask another.

DERIVATION, RECORDED NOT IMPLIED: the authorizing prompt referred to a supplied
schema and a `100 Example Avenue` fixture; neither was attached. Both are derived
from that prompt's own stated requirements, and rule ids live in one table so
re-keying to a canonical spec is an edit, not a rewrite.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from services import go_pdz_contract as contract
from services import go_pdz_validator as validator

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "go_pdz"
_GOLDEN = _FIXTURES / "golden_100_example_avenue.json"

#: fixture file -> the single rule it exists to trip.
_NEGATIVES = {
    "neg_a_vr06_established_low_confidence.json": "VR-06",
    "neg_b_vr05_authority_from_inference.json": "VR-05",
    "neg_c_vr07_high_confidence_superseded.json": "VR-07",
    "neg_d_vr08_unresolved_exception.json": "VR-08",
    "neg_e_vr09_spatial_without_gis.json": "VR-09",
    "neg_f_vr11_silent_conflict.json": "VR-11",
    "neg_g_vr12_owner_program.json": "VR-12",
    "neg_h_vr13_predicted_approval.json": "VR-13",
    "neg_i_vr14_relief_definite.json": "VR-14",
    "neg_j_vr15_material_unresolved_hidden.json": "VR-15",
}


def _load(name):
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _golden():
    return json.loads(_GOLDEN.read_text(encoding="utf-8"))


class TheGoldenFixture(unittest.TestCase):
    """The positive case, and the only invariant it is allowed to carry."""

    def test_it_satisfies_the_structural_contract(self):
        self.assertEqual(contract.validate_structure(_golden()), [])

    def test_it_produces_zero_errors(self):
        result = validator.validate(_golden())
        self.assertEqual(result["error_count"], 0,
                         [f["rule_id"] + ": " + f["message"]
                          for f in result["findings"]])
        self.assertTrue(result["valid"])
        self.assertTrue(result["promotable"])

    def test_zero_warnings_is_a_property_of_this_fixture_not_an_invariant(self):
        """Section 7 is explicit: do not require zero warnings in general.

        This fixture happens to carry none because every authority in it declares
        an effective date. The validator must still be ABLE to warn - see
        `WarningStatesSurvive`.
        """
        self.assertEqual(validator.validate(_golden())["warning_count"], 0)


class TheNegativeFixtures(unittest.TestCase):
    """One fixture, one rule - so no failure can hide behind another."""

    def test_each_fixture_trips_its_own_rule(self):
        for name, rule_id in _NEGATIVES.items():
            with self.subTest(fixture=name):
                result = validator.validate(_load(name))
                fired = {f["rule_id"] for f in result["findings"]
                         if f["severity"] == contract.SEVERITY_ERROR}
                self.assertIn(rule_id, fired)

    def test_each_fixture_trips_only_its_own_rule(self):
        for name, rule_id in _NEGATIVES.items():
            with self.subTest(fixture=name):
                result = validator.validate(_load(name))
                fired = {f["rule_id"] for f in result["findings"]
                         if f["severity"] == contract.SEVERITY_ERROR}
                self.assertEqual(fired, {rule_id},
                                 "a second rule would mask the one under test")

    def test_every_negative_is_structurally_valid(self):
        """The point of each is a SEMANTIC failure, not a malformed document."""
        for name in _NEGATIVES:
            with self.subTest(fixture=name):
                self.assertEqual(contract.validate_structure(_load(name)), [])

    def test_no_negative_fixture_is_promotable(self):
        for name in _NEGATIVES:
            with self.subTest(fixture=name):
                result = validator.validate(_load(name))
                self.assertFalse(result["valid"])
                self.assertFalse(result["promotable"])


class FailClosed(unittest.TestCase):
    """Severity governs promotability, and nothing else does."""

    def test_any_error_blocks_promotion(self):
        document = _golden()
        document["statements"][0]["confidence"] = "LOW"
        result = validator.validate(document)
        self.assertGreater(result["error_count"], 0)
        self.assertFalse(result["promotable"])

    def test_a_warning_alone_does_not_block_promotion(self):
        document = _golden()
        document["authorities"][0]["effective_date"] = None
        result = validator.validate(document)
        self.assertEqual(result["error_count"], 0)
        self.assertGreater(result["warning_count"], 0)
        self.assertTrue(result["valid"], "a warning must not fail the result")
        self.assertTrue(result["promotable"])


class WarningStatesSurvive(unittest.TestCase):
    """The cheapest way to make a validator look good is to demote warnings."""

    def test_a_missing_effective_date_warns_rather_than_errors(self):
        document = _golden()
        document["authorities"][1]["effective_date"] = None
        findings = [f for f in validator.validate(document)["findings"]
                    if f["rule_id"] == "VR-16"]
        self.assertTrue(findings)
        self.assertEqual(findings[0]["severity"], contract.SEVERITY_WARNING)

    def test_authority_voice_in_a_go_interpretation_warns(self):
        document = _golden()
        interpretation = next(s for s in document["statements"]
                              if s["kind"] == "GO_INTERPRETS")
        interpretation["text"] = "The by-law requires a 14 metre height limit."
        findings = [f for f in validator.validate(document)["findings"]
                    if f["rule_id"] == "VR-18"]
        self.assertTrue(findings)
        self.assertEqual(findings[0]["severity"], contract.SEVERITY_WARNING)
        self.assertTrue(validator.validate(document)["valid"])


class TheDeterministicSpatialRule(unittest.TestCase):
    """GO consumes a spatial token. GO never mints one."""

    def _with_spatial(self, relation, basis, status="PROVISIONAL"):
        document = _golden()
        statement = next(s for s in document["statements"]
                         if s["statement_id"] == "ST-REG")
        statement["spatial_relation"] = relation
        statement["spatial_basis"] = basis
        statement["statement_status"] = status
        return document

    def test_an_assertive_predicate_needs_deterministic_geometry(self):
        for relation in ("INSIDE", "OUTSIDE", "INTERSECTS"):
            for basis in ("VISUAL_IMPRESSION", "NONE"):
                with self.subTest(relation=relation, basis=basis):
                    fired = {f["rule_id"] for f in validator.validate(
                        self._with_spatial(relation, basis))["findings"]}
                    self.assertIn("VR-09", fired)

    def test_deterministic_geometry_permits_an_assertive_predicate(self):
        for relation in ("INSIDE", "OUTSIDE", "INTERSECTS"):
            with self.subTest(relation=relation):
                fired = {f["rule_id"] for f in validator.validate(
                    self._with_spatial(relation, "DETERMINISTIC_GIS"))["findings"]}
                self.assertNotIn("VR-09", fired)

    def test_an_impression_may_still_be_recorded_but_not_as_fact(self):
        """The degradation path: no geometry means AMBIGUOUS, not silence."""
        for relation in ("APPEARS_INSIDE", "AMBIGUOUS"):
            with self.subTest(relation=relation):
                ok = validator.validate(
                    self._with_spatial(relation, "VISUAL_IMPRESSION"))
                self.assertNotIn("VR-09", {f["rule_id"] for f in ok["findings"]})
                escalated = validator.validate(self._with_spatial(
                    relation, "VISUAL_IMPRESSION", status="ESTABLISHED"))
                self.assertIn("VR-10", {f["rule_id"] for f in escalated["findings"]})


class TheExceptionFailClosedRule(unittest.TestCase):
    """An exception exists to displace the parent standard."""

    def _with_unreadable_exception(self):
        document = _golden()
        document["site_specific_exceptions"] = [{
            "exception_id": "(x412)", "indicated_by": "Zoning map annotation",
            "text_retrieved": False, "authority_ref": None,
            "missing_authority": "Text of exception (x412)",
            "development_effect": "May displace CC height and setback standards",
            "required_next_evidence": "Exception text from the by-law office"}]
        return document

    def test_an_unreadable_exception_forces_the_result_to_unresolved(self):
        fired = {f["rule_id"] for f in validator.validate(
            self._with_unreadable_exception())["findings"]}
        self.assertIn("VR-08", fired)

    def test_declaring_unresolved_satisfies_the_rule(self):
        document = self._with_unreadable_exception()
        document["result_status"] = "UNRESOLVED"
        for statement in document["statements"]:
            if statement["topic"] in ("HEIGHT", "ZONING"):
                statement["statement_status"] = "PROVISIONAL"
        fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
        self.assertNotIn("VR-08", fired)
        self.assertNotIn("VR-20", fired)

    def test_parent_zone_standards_cannot_survive_an_unreadable_exception(self):
        """VR-20, the substantive half of the rule.

        Declaring UNRESOLVED is not enough if the document then goes on stating
        the parent zone's height as established fact.
        """
        document = self._with_unreadable_exception()
        document["result_status"] = "UNRESOLVED"   # VR-08 satisfied
        height = next(s for s in document["statements"]
                      if s["topic"] == "HEIGHT")
        height["statement_status"] = "ESTABLISHED"
        fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
        self.assertNotIn("VR-08", fired)
        self.assertIn("VR-20", fired,
                      "the parent standard must not stand while the exception "
                      "that displaces it is unverified")

    def test_a_retrieved_exception_does_not_fail_closed(self):
        document = self._with_unreadable_exception()
        document["site_specific_exceptions"][0]["text_retrieved"] = True
        document["site_specific_exceptions"][0]["authority_ref"] = "AUTH-ZBL"
        fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
        self.assertNotIn("VR-08", fired)
        self.assertNotIn("VR-20", fired)


class TheGateBoundary(unittest.TestCase):
    """Gate 01 ends where the owner's program begins."""

    def test_owner_program_topics_are_refused(self):
        for topic in contract.GATE_01_FORBIDDEN_TOPICS:
            with self.subTest(topic=topic):
                document = _golden()
                document["statements"].append({
                    "statement_id": "ST-X", "kind": "GO_INTERPRETS",
                    "topic": topic, "text": "A program statement.",
                    "authority_refs": [], "statement_status": "PROVISIONAL",
                    "confidence": "LOW", "spatial_relation": "NOT_APPLICABLE",
                    "spatial_basis": "NONE", "conflict_refs": [],
                    "derived_from": []})
                fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
                self.assertIn("VR-12", fired)

    def test_the_next_authorized_gate_is_declared(self):
        self.assertEqual(_golden()["next_authorized_gate"], contract.GATE_02)

    def test_a_result_claiming_the_wrong_gate_is_refused(self):
        document = _golden()
        document["gate"] = contract.GATE_02
        problems = contract.validate_structure(document)
        self.assertTrue(problems, "the schema pins the gate constant")


class StructuralLayer(unittest.TestCase):
    """Schema checking, kept separate from semantics on purpose."""

    def test_a_missing_required_field_is_caught(self):
        document = _golden()
        del document["result_status"]
        problems = contract.validate_structure(document)
        self.assertTrue(any("result_status" in path for path, _m in problems))

    def test_an_unknown_field_is_refused(self):
        document = _golden()
        document["surprise"] = 1
        problems = contract.validate_structure(document)
        self.assertTrue(any("surprise" in path for path, _m in problems))

    def test_a_bad_enum_value_is_caught(self):
        document = _golden()
        document["statements"][0]["kind"] = "AUTHORITY_IMPLIES"
        problems = contract.validate_structure(document)
        self.assertTrue(problems)

    def test_a_boolean_field_does_not_accept_a_string(self):
        document = _golden()
        document["site_specific_exceptions"] = [{
            "exception_id": "x", "indicated_by": "map", "text_retrieved": "yes"}]
        problems = contract.validate_structure(document)
        self.assertTrue(problems)

    def test_structural_failure_still_reports_semantics(self):
        """Reporting only the first layer would send a reader round twice."""
        document = _golden()
        document["surprise"] = 1
        document["statements"][0]["confidence"] = "LOW"
        fired = {f["rule_id"] for f in validator.validate(document)["findings"]}
        self.assertIn("SCHEMA", fired)
        self.assertIn("VR-06", fired)


class GovernedOutput(unittest.TestCase):
    """Section 9's required envelope."""

    def test_every_required_output_field_is_present(self):
        result = validator.validate(_golden())
        for field in ("validator_version", "schema_version", "valid",
                      "error_count", "warning_count", "findings"):
            self.assertIn(field, result)

    def test_every_finding_carries_its_full_identity(self):
        result = validator.validate(_load(
            "neg_a_vr06_established_low_confidence.json"))
        for finding in result["findings"]:
            for field in ("rule_id", "status", "severity", "path",
                          "subject_id", "message"):
                self.assertIn(field, finding)
            self.assertTrue(finding["path"].startswith("$"))

    def test_expected_state_is_given_where_applicable(self):
        result = validator.validate(_load(
            "neg_a_vr06_established_low_confidence.json"))
        finding = next(f for f in result["findings"] if f["rule_id"] == "VR-06")
        self.assertIsNotNone(finding["observed"])
        self.assertIsNotNone(finding["expected"])

    def test_every_rule_id_has_a_declared_severity(self):
        for rule_id, (severity, description) in validator.RULES.items():
            self.assertIn(severity, (contract.SEVERITY_ERROR,
                                     contract.SEVERITY_WARNING,
                                     contract.SEVERITY_INFO))
            self.assertTrue(description)

    def test_all_twenty_rules_are_declared(self):
        self.assertEqual(sorted(validator.RULES),
                         ["VR-%02d" % n for n in range(1, 21)])


class NoAuthorityPromotion(unittest.TestCase):
    """Passing validation does not make the result the law."""

    def test_the_result_says_so_every_time(self):
        note = validator.validate(_golden())["authority_note"]
        self.assertIn("STRUCTURE VALID", note)
        self.assertIn("GOVERNED AUTHORITY", note)
        self.assertIn("remain the authority", note)

    def test_nothing_here_writes_a_governed_record(self):
        import ast
        source = (Path(__file__).resolve().parent.parent / "services"
                  / "go_pdz_validator.py").read_text(encoding="utf-8")
        called = {n.func.attr for n in ast.walk(ast.parse(source))
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for forbidden in ("record_relationship", "register_claim", "create_claim",
                          "record_finding", "save"):
            self.assertNotIn(forbidden, called)

    def test_no_external_egress(self):
        for module in ("go_pdz_contract.py", "go_pdz_validator.py"):
            source = (Path(__file__).resolve().parent.parent / "services"
                      / module).read_text(encoding="utf-8")
            for banned in ("requests.", "urllib.request", "anthropic", "httpx"):
                self.assertNotIn(banned, source)

    def test_no_new_production_dependency_was_added(self):
        for module in ("go_pdz_contract.py", "go_pdz_validator.py"):
            source = (Path(__file__).resolve().parent.parent / "services"
                      / module).read_text(encoding="utf-8")
            self.assertNotIn("import jsonschema", source)


if __name__ == "__main__":
    unittest.main()
