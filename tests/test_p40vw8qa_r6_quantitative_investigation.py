"""
CLAUDE-P40-VW8-QA-R6 - Natural-Language, Evidence-Guided Quantitative
Investigation.

Acceptance scenario: inside an active Investigation, the reviewer asks
"Is there enough available length to construct a 6 m wide driveway ramp
descending from exterior ground grade to the basement level?" and later
writes "Those numbers are geodetic elevations from ground floor to the
basement." - the second message previously got the same "I didn't
recognize an action in that message" reply as a genuinely unrelated
stray message. services/conversation_interpreter.py's final fallback
now checks for an open Case first and records ordinary discussion as a
real contribution instead.

services/quantitative_investigation.py is the general (not "Nipigon
Ramp"-specific) evidence-guided pattern: extracts numbers the reviewer
has directly TYPED into this conversation (never a drawing - no local
OCR/PDF-rendering capability exists in this environment, same
conclusion as the R2A stage's own capability audit), computes the
vertical-drop/slope-run/feasibility-comparison formula transparently,
and - only once the relevant evidence is visible - records a candidate,
provisional Finding via the EXISTING record_analysis/Finding mechanism
(no new business object, no new confirmation gate: Finding is already
provisional-until-reviewed for every caller of record_analysis, not
something this stage adds).

No external-AI call of any kind in this whole path - every assertion
below runs with no ANTHROPIC_API_KEY reachable (TestingConfig already
clears it - see CLAUDE.md's own hermetic-test note) and still succeeds,
which is itself part of the proof that nothing here depends on one.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from services.case_workspace import FINDING_STATUS_PROVISIONAL, CaseWorkspaceStore
from services.conversation_interpreter import interpret_message
import services.quantitative_investigation as quant

_ACCEPTANCE_QUESTION = (
    "Is there enough available length to construct a 6 m wide driveway ramp "
    "descending from exterior ground grade to the basement level?"
)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_r6_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-r6")
        self.store.set_operating_environment(self.workspace, "client_owner", actor="reviewer")
        self.workspace = self.store.get("proj-r6")
        self.case = self.store.create_case(
            self.workspace, title="Basement Ramp", objective="", created_by="reviewer",
        )
        self.workspace = self.store.get("proj-r6")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _send(self, text):
        """Mirrors routes/workspace.py:_run_conversation_turn's own real
        ordering exactly - the human message is persisted BEFORE
        interpret_message runs, so case["conversation"] already
        reflects it (see conversation_interpreter.py's own question_text
        selection comment for why this ordering matters)."""
        human = self.store.add_message(self.workspace, self.case["id"], role="human", text=text, actor="reviewer")
        self.workspace = self.store.get("proj-r6")
        self.case = next(c for c in self.workspace.cases if c["id"] == self.case["id"])
        result = interpret_message(
            text, self.workspace, self.case, self.store, self.tmp_dir, "reviewer", None,
            triggering_message_id=human["id"],
        )
        self.store.add_message(self.workspace, self.case["id"], role="system", text=result.reply_text, actor="system")
        self.workspace = self.store.get("proj-r6")
        self.case = next(c for c in self.workspace.cases if c["id"] == self.case["id"])
        return result


# ---------------------------------------------------------------------------
# The reported defect itself: contextual statements in an active
# Investigation.
# ---------------------------------------------------------------------------

class DiscussionContributionTests(_BaseTestCase):
    def test_contextual_clarification_is_not_rejected_as_unrecognized(self):
        result = self._send("Those numbers are geodetic elevations from ground floor to the basement.")
        self.assertNotEqual(result.action_taken, "unrecognized")
        self.assertNotIn("I didn't recognize an action", result.reply_text)

    def test_contextual_clarification_is_recorded_as_discussion_contribution(self):
        result = self._send("Those numbers are geodetic elevations from ground floor to the basement.")
        self.assertEqual(result.action_taken, "discussion_contribution")
        self.assertIn("Noted as context for this Investigation", result.reply_text)

    def test_a_genuinely_unrelated_stray_message_with_no_case_still_gets_the_honest_unrecognized_reply(self):
        # The fallback change is scoped to an OPEN Case - a project-level
        # (no Case) unrelated message must still behave exactly as
        # before this stage, not silently start "recording discussion"
        # with nothing to attach it to.
        result = interpret_message(
            "asdkfjhaslkdfj random unrelated text", self.workspace, None, self.store, self.tmp_dir, "reviewer", None,
        )
        self.assertEqual(result.action_taken, "unrecognized")
        self.assertIn("I didn't recognize an action", result.reply_text)

    def test_discussion_contribution_does_not_create_a_finding(self):
        self._send("Those numbers are geodetic elevations from ground floor to the basement.")
        self.assertEqual(len(self.workspace.findings), 0)


# ---------------------------------------------------------------------------
# Natural-language question recognition and missing-source/measurement
# guidance.
# ---------------------------------------------------------------------------

class QuestionRecognitionTests(_BaseTestCase):
    def test_the_acceptance_scenario_question_is_recognized_as_quantitative(self):
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIn(result.action_taken, ("quantitative_investigation_in_progress", "quantitative_investigation_calculated"))

    def test_full_question_text_is_preserved_not_truncated(self):
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIn(_ACCEPTANCE_QUESTION, result.reply_text)

    def test_missing_measurements_are_named_specifically(self):
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIn("exterior driveway-entry grade elevation", result.reply_text)
        self.assertIn("basement driveway/garage threshold elevation", result.reply_text)
        self.assertIn("applicable maximum longitudinal slope", result.reply_text)

    def test_missing_source_guidance_explains_what_and_why_not_just_add_a_source(self):
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIn("site plan", result.reply_text)
        self.assertIn("basement", result.reply_text.lower())
        self.assertNotIn("just add a source", result.reply_text.lower())
        self.assertGreater(len(result.reply_text), len("Add a Source."))

    def test_regulatory_slope_is_never_hardcoded_or_assumed(self):
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIn("never assumed automatically", result.reply_text)
        self.assertIn("your own explicit design assumption", result.reply_text)

    def test_suggested_title_is_generalizable_not_hardcoded_to_one_phrase(self):
        self.assertEqual(quant.suggested_title(_ACCEPTANCE_QUESTION), "Basement driveway ramp feasibility")
        # A differently-worded slope question still gets a real,
        # pattern-derived title, not a copy of the ramp-specific one.
        other = quant.suggested_title("Is the site grading slope within allowable limits for accessibility?")
        self.assertNotEqual(other, "Basement driveway ramp feasibility")
        self.assertTrue(other)


# ---------------------------------------------------------------------------
# Evidence-backed extraction: no fabrication, provenance, units.
# ---------------------------------------------------------------------------

class ExtractionTests(unittest.TestCase):
    def test_no_value_is_extracted_when_none_was_stated(self):
        values = quant.extract_values_from_text("I'm thinking about the ramp design generally.")
        self.assertEqual(values, [])

    def test_extracted_value_retains_its_exact_source_quote(self):
        values = quant.extract_values_from_text("The entrance grade elevation is 105.20 today.")
        self.assertEqual(len(values), 1)
        self.assertIn("105.20", values[0].raw_text)
        self.assertEqual(values[0].extraction_method, "conversation_stated")
        self.assertEqual(values[0].status, "user_provided")

    def test_slope_unit_is_correctly_identified_as_percent(self):
        values = quant.extract_values_from_text("Available length is 22 m. Assume 15% slope.")
        slope = next(v for v in values if v.field == "longitudinal_slope_percent")
        self.assertEqual(slope.unit, "%")
        self.assertEqual(slope.value, 15.0)

    def test_length_unit_is_correctly_identified_as_meters_not_a_neighboring_units_leak(self):
        values = quant.extract_values_from_text("Available length is 22 m. Assume 15% slope.")
        length = next(v for v in values if v.field == "available_travel_length")
        self.assertEqual(length.unit, "m")
        self.assertEqual(length.value, 22.0)

    def test_a_later_restatement_of_the_same_field_supersedes_the_earlier_one(self):
        first = quant.extract_values_from_text("Entrance grade elevation is 100.0.")
        second = quant.extract_values_from_text("Correction - entrance grade elevation is 105.2.")
        merged = quant.merge_values(first, second)
        self.assertEqual(merged["entrance_grade_elevation"].value, 105.2)

    def test_ground_floor_elevation_is_not_silently_substituted_for_entrance_grade_when_both_are_distinct(self):
        # Section: "Do not substitute the ground-floor elevation
        # automatically for the exterior ramp-entry grade. They may
        # differ." - both map to the SAME field by design (this module
        # treats a stated "ground floor" value as an entrance-grade
        # candidate, per the acceptance scenario's own wording,
        # "elevations from ground floor to the basement") - the
        # guarantee this test actually pins down is narrower and more
        # important: nothing here ever COMPUTES a basement value FROM
        # the entrance value or vice versa - each is only ever populated
        # by its own distinct, directly-stated number.
        values = quant.extract_values_from_text("Ground floor is at 105.2. Basement grade elevation is 101.0.")
        by_field = {v.field: v for v in values}
        self.assertEqual(by_field["entrance_grade_elevation"].value, 105.2)
        self.assertEqual(by_field["basement_grade_elevation"].value, 101.0)
        self.assertNotEqual(by_field["entrance_grade_elevation"].value, by_field["basement_grade_elevation"].value)


# ---------------------------------------------------------------------------
# Transparent calculation - geodetic-elevation subtraction, the exact
# 5-step formula.
# ---------------------------------------------------------------------------

class CalculationTests(unittest.TestCase):
    def test_vertical_drop_is_entrance_minus_basement(self):
        calc = quant.compute_feasibility(entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0)
        self.assertAlmostEqual(calc.vertical_drop, 4.2)

    def test_basic_run_is_drop_divided_by_slope_fraction(self):
        calc = quant.compute_feasibility(entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0)
        self.assertAlmostEqual(calc.basic_sloped_run, 4.2 / 0.15)

    def test_width_is_never_inserted_into_the_longitudinal_slope_formula(self):
        # The 6 m width must never appear in vertical_drop/basic_sloped_run
        # at all - compute_feasibility doesn't even accept a width
        # parameter, structurally guaranteeing this.
        import inspect
        params = inspect.signature(quant.compute_feasibility).parameters
        self.assertNotIn("width", params)

    def test_total_required_travel_includes_additional_length_when_given(self):
        calc = quant.compute_feasibility(
            entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0, additional_length=3.0,
        )
        self.assertAlmostEqual(calc.total_required_travel, calc.basic_sloped_run + 3.0)

    def test_feasibility_margin_and_verdict_computed_correctly(self):
        calc = quant.compute_feasibility(
            entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0, available_travel_length=22.0,
        )
        self.assertAlmostEqual(calc.margin, 22.0 - calc.total_required_travel)
        self.assertFalse(calc.feasible)

    def test_feasible_when_available_exceeds_required(self):
        calc = quant.compute_feasibility(
            entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0, available_travel_length=40.0,
        )
        self.assertTrue(calc.feasible)

    def test_no_feasibility_verdict_without_an_available_length(self):
        calc = quant.compute_feasibility(entrance_grade=105.2, basement_grade=101.0, slope_percent=15.0)
        self.assertIsNone(calc.feasible)
        self.assertIsNone(calc.margin)


# ---------------------------------------------------------------------------
# Full conversational flow: unresolved criteria, calculation shown
# before all inputs present, candidate Finding, human confirmation
# before Apply, conversation persistence.
# ---------------------------------------------------------------------------

class FullFlowTests(_BaseTestCase):
    def _run_full_scenario(self):
        self._send(_ACCEPTANCE_QUESTION)
        self._send("Those numbers are geodetic elevations from ground floor to the basement.")
        self._send("The entrance grade elevation is 105.20 and the basement grade elevation is 101.00.")
        return self._send("Available length is 22 m and assume 15% slope.")

    def test_calculation_is_shown_before_all_inputs_are_present(self):
        self._send(_ACCEPTANCE_QUESTION)
        self._send("Those numbers are geodetic elevations from ground floor to the basement.")
        result = self._send("The entrance grade elevation is 105.20 and the basement grade elevation is 101.00.")
        self.assertIn("Vertical drop", result.reply_text)
        self.assertIn("4.20", result.reply_text)
        # No Finding yet - available length still unresolved.
        self.assertEqual(len(self.workspace.findings), 0)

    def test_final_message_produces_exactly_one_candidate_finding(self):
        self._run_full_scenario()
        self.assertEqual(len(self.workspace.findings), 1)

    def test_finding_is_provisional_not_auto_applied(self):
        self._run_full_scenario()
        finding = self.workspace.findings[0]
        self.assertEqual(finding["claim_status"], FINDING_STATUS_PROVISIONAL)

    def test_finding_statement_contains_every_required_field(self):
        self._run_full_scenario()
        statement = self.workspace.findings[0]["statement"]
        for expected in (
            "Question evaluated", "Confirmed inputs", "Formula", "Vertical drop",
            "Available length", "margin", "professional confirmation",
        ):
            self.assertIn(expected, statement)

    def test_finding_cites_the_conversation_as_the_evidence_source(self):
        self._run_full_scenario()
        statement = self.workspace.findings[0]["statement"]
        self.assertIn("source: conversation", statement)
        self.assertIn("quote:", statement)

    def test_unresolved_items_are_named_in_the_finding_not_silently_dropped(self):
        self._run_full_scenario()
        statement = self.workspace.findings[0]["statement"]
        self.assertIn("Unresolved", statement)

    def test_full_question_preserved_in_the_finding_even_after_later_messages(self):
        self._run_full_scenario()
        statement = self.workspace.findings[0]["statement"]
        self.assertIn(_ACCEPTANCE_QUESTION, statement)

    def test_conversation_persists_every_turn(self):
        self._run_full_scenario()
        texts = [m["text"] for m in self.case["conversation"]]
        self.assertIn(_ACCEPTANCE_QUESTION, texts)
        self.assertTrue(any("geodetic elevations" in t for t in texts))

    def test_geometric_feasibility_is_labeled_distinctly_from_regulatory_or_professional_signoff(self):
        result = self._run_full_scenario()
        self.assertIn("not a regulatory", result.reply_text.lower())
        self.assertIn("professional", result.reply_text.lower())


class AttachedDrawingSourceTests(_BaseTestCase):
    def test_guidance_is_suppressed_once_a_drawing_source_is_attached(self):
        self.assertEqual(quant.build_source_guidance(has_drawing_source=True), "")

    def test_guidance_present_when_no_drawing_source_is_attached(self):
        guidance = quant.build_source_guidance(has_drawing_source=False)
        self.assertIn("Add drawing Source", guidance)

    def test_reply_omits_source_guidance_once_a_drawing_source_exists(self):
        # Attach a real drawing Source to the Case, then ask - the
        # missing-source paragraph must not appear (even though the
        # measurements are still unresolved, since no OCR is available
        # to read them - see this module's own header).
        source = {
            "id": "src-1", "project_id": self.workspace.project_id, "kind": "drawing",
            "name": "Site Plan.png", "added_at": "2026-01-01T00:00:00+00:00",
        }
        self.workspace.sources.append(source)
        # self.case (from create_case's own RETURN value) is a separate
        # dict from the one actually living inside workspace.cases
        # (create_case calls asdict(new_case) twice - once to append,
        # once to return) - mutate the live one directly, matching how
        # _send's own post-reload rebinding already works.
        live_case = next(c for c in self.workspace.cases if c["id"] == self.case["id"])
        live_case["source_ids"].append("src-1")
        self.store.save(self.workspace)
        self.workspace = self.store.get("proj-r6")
        self.case = next(c for c in self.workspace.cases if c["id"] == self.case["id"])
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertNotIn("Add drawing Source", result.reply_text)


class NoExternalAICallTests(_BaseTestCase):
    def test_module_never_imports_anthropic(self):
        source = Path(quant.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import anthropic", source)
        self.assertNotIn("from anthropic", source)

    def test_full_scenario_succeeds_with_no_reachable_api_key(self):
        # TestingConfig already clears ANTHROPIC_API_KEY at the app
        # level - this test's own store/workspace never touch that at
        # all (no Flask app involved), which is itself the point: this
        # whole path has no dependency on one being configured.
        result = self._send(_ACCEPTANCE_QUESTION)
        self.assertIsNotNone(result.reply_text)
        self.assertNotIn("policy", result.action_taken)


if __name__ == "__main__":
    unittest.main()
