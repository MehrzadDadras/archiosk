import unittest
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from services.question_scope import (
    APPLICATION_EVIDENCE_AFFIRMATIVE,
    APPLICATION_EVIDENCE_AMBIGUOUS,
    APPLICATION_EVIDENCE_NONE,
    QUESTION_SCOPE_APPLICATION,
    QUESTION_SCOPE_MIXED,
    QUESTION_SCOPE_PROJECT,
    QUESTION_SCOPE_UNKNOWN,
    classify_question_scope,
    scope_diagnostic,
    SCOPE_DIAGNOSTIC_STATUS,
)


class QuestionScopeClassifierTests(unittest.TestCase):
    def test_built_work_veto_precedes_user_interface_evidence(self):
        cases = (
            "What is the user interface for the fire alarm control panel?",
            "Does the operator user interface show the door status?",
            "What is the operator user interface for the security management system?",
            "Does the head end require a graphical user interface at the officer desk?",
            "Is a user interface required at the control desk?",
        )
        for message in cases:
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertNotEqual(result.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)
                self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)

    def test_sidebar_is_not_an_unconditional_application_term(self):
        result = classify_question_scope("What sidebar content is required in the operations manual?")
        self.assertNotEqual(result.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)
        self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)

    def test_ui_action_requires_application_surface_corroboration(self):
        physical_cases = (
            "Delete the duress button from the day room",
            "Add a call button at the nurse station",
            "Move the annunciator panel to the vestibule",
            "Can we remove the panic button from the interview room?",
            "Create a menu for the kitchen rotation",
            "Add a panel at the sallyport",
            "Move the intercom button to the officer desk",
            "Can we add an icon to the wayfinding signage?",
            "Remove the button from the intercom faceplate",
            "Delete the menu board from the servery scope",
        )
        for message in physical_cases:
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertNotEqual(result.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)
                self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)

    def test_ui_action_with_application_surface_is_affirmative(self):
        for message in (
            "How do I create an empty panel on the left side of this page?",
            "How do I hide the left panel on this page?",
        ):
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertEqual(result.scope, QUESTION_SCOPE_APPLICATION)
                self.assertEqual(result.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)

    def test_adversarial_built_work_language_never_affirms_application(self):
        cases = (
            "What is the design load on the right column at grid line 3?",
            "What is the top rail height for the guardrail?",
            "What is on the left side of the building?",
            "What is shown on the bottom panel of the door elevation?",
            "What is the left side panel of the switchgear rated for?",
            "Is the right column shown on the framing plan?",
            "Remove the smoke damper note from the panel schedule",
            "Show me the electrical panel locations",
            "Where should we place the electrical panel on level 1?",
            "Add a note to the panel schedule about the generator",
            "Can you show me the panel schedule?",
            "Can you open the fire alarm panel detail?",
            "Are you able to show me the electrical panel layout?",
            "What is the application of Division B to this building?",
            "Does the permit application need the Alternative Solution attached?",
            "What is the Code application for a detention occupancy?",
            "Does the application of OBC 3.2.6 require a smoke shaft?",
            "Is there a push button station required at the officer station?",
            "What template does the owner require for the commissioning report?",
            "What is the contractor workspace on this page?",
            "What is the interface panel on the left side of the control room?",
        )
        for message in cases:
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)
                self.assertNotEqual(
                    result.application_evidence,
                    APPLICATION_EVIDENCE_AFFIRMATIVE,
                )

    def test_app_is_not_a_standalone_application_signal(self):
        for message in (
            "See App. B for the damper schedule",
            "Is the exhaust rate in App. C?",
            "Which app. covers the detention hardware?",
        ):
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)
                self.assertNotIn("app", result.application_signals)

    def test_corroboration_terms_are_not_independent_application_evidence(self):
        for message in (
            "What is the application of Division B to this building?",
            "What template does the owner require for the commissioning report?",
            "What is the contractor workspace on this page?",
            "What is the interface panel on the left side of the control room?",
        ):
            with self.subTest(message=message):
                result = classify_question_scope(message)
                self.assertNotEqual(result.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)

    def test_built_work_veto_is_negative_only(self):
        result = classify_question_scope("What is the design load on the right column?")
        self.assertNotEqual(result.scope, QUESTION_SCOPE_APPLICATION)
        self.assertEqual(result.scope, QUESTION_SCOPE_UNKNOWN)
        self.assertTrue(result.built_work_signals)

    def test_application_evidence_strength_is_descriptive_only(self):
        affirmative = classify_question_scope("How do I create an empty panel on the left side of this page?")
        ambiguous = classify_question_scope("Show me the panel on this page")
        unknown = classify_question_scope("Can you help with this?")
        self.assertEqual(affirmative.application_evidence, APPLICATION_EVIDENCE_AFFIRMATIVE)
        self.assertEqual(ambiguous.application_evidence, APPLICATION_EVIDENCE_AMBIGUOUS)
        self.assertEqual(unknown.application_evidence, APPLICATION_EVIDENCE_NONE)
        for result in (affirmative, ambiguous, unknown):
            self.assertFalse(hasattr(result, "route"))
            self.assertFalse(hasattr(result, "authorize"))
            self.assertFalse(hasattr(result, "action"))

    def test_construction_language_regression_matrix(self):
        cases = (
            ("What does the RFP require for smoke control?", QUESTION_SCOPE_PROJECT),
            ("What are the panel schedule requirements in the electrical drawings?", QUESTION_SCOPE_PROJECT),
            ("Does the specification allow a smoke screen at the atrium?", QUESTION_SCOPE_PROJECT),
            ("What page of the RFP covers the HVAC shutdown sequence?", QUESTION_SCOPE_PROJECT),
            ("Show me the drawing layout for level 2", QUESTION_SCOPE_PROJECT),
            ("What does the RFP cover in the source documents?", QUESTION_SCOPE_PROJECT),
            ("How do I create an empty panel on the left side of this page?", QUESTION_SCOPE_APPLICATION),
            ("Delete the left panel", QUESTION_SCOPE_APPLICATION),
            ("Can I put the smoke findings into a panel beside this document?", QUESTION_SCOPE_MIXED),
            ("Can you help with this?", QUESTION_SCOPE_UNKNOWN),
            ("What is on this page?", QUESTION_SCOPE_UNKNOWN),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(classify_question_scope(message).scope, expected)

    def test_common_project_singular_and_plural_forms_are_equivalent(self):
        pairs = (
            ("show the drawing", "show the drawings"),
            ("what requirement applies", "what requirements apply"),
            ("which document controls", "which documents control"),
            ("review the finding", "review the findings"),
            ("identify the source", "identify the sources"),
            ("read the specification", "read the specifications"),
        )
        for singular, plural in pairs:
            with self.subTest(singular=singular, plural=plural):
                self.assertEqual(
                    classify_question_scope(singular).scope,
                    QUESTION_SCOPE_PROJECT,
                )
                self.assertEqual(
                    classify_question_scope(plural).scope,
                    QUESTION_SCOPE_PROJECT,
                )

    def test_project_evidence_question(self):
        result = classify_question_scope("What does the RFP require for smoke control?")
        self.assertEqual(result.scope, QUESTION_SCOPE_PROJECT)

    def test_screenshot_application_question(self):
        result = classify_question_scope("How do I create an empty panel on the left side of this page?")
        self.assertEqual(result.scope, QUESTION_SCOPE_APPLICATION)

    def test_cross_scope_question(self):
        result = classify_question_scope("Can I put the smoke findings into a panel beside this document?")
        self.assertEqual(result.scope, QUESTION_SCOPE_MIXED)

    def test_ambiguous_question_is_safe_unknown(self):
        result = classify_question_scope("Can you help with this?")
        self.assertEqual(result.scope, QUESTION_SCOPE_UNKNOWN)

    def test_tpl_is_observable_but_does_not_create_application_intent(self):
        context = {"template_identity": {"template_id": "TPL-005", "name": "Project Workspace"}}
        result = classify_question_scope("Can you help with this?", context)
        self.assertEqual(result.scope, QUESTION_SCOPE_UNKNOWN)
        self.assertEqual(result.template_id, "TPL-005")

    def test_classifier_is_read_only_and_has_no_authority_fields(self):
        context = {"template_identity": {"template_id": "TPL-005"}, "selected_elements": []}
        result = classify_question_scope("How do I create an empty panel on the left side of this page?", context)
        self.assertEqual(result.scope, QUESTION_SCOPE_APPLICATION)
        self.assertEqual(context["selected_elements"], [])
        self.assertFalse(hasattr(result, "action"))
        self.assertFalse(hasattr(result, "authorize"))
        self.assertFalse(hasattr(result, "mutation"))

    def test_diagnostic_is_explicitly_advisory_and_carries_active_tpl(self):
        diagnostic = scope_diagnostic(
            "How do I create an empty panel on the left side of this page?",
            {"template_identity": {"template_id": "TPL-005"}},
        )
        self.assertEqual(diagnostic["classification"], QUESTION_SCOPE_APPLICATION)
        self.assertEqual(diagnostic["template_id"], "TPL-005")
        self.assertEqual(diagnostic["status"], SCOPE_DIAGNOSTIC_STATUS)
        self.assertEqual(diagnostic["application_evidence"], APPLICATION_EVIDENCE_AFFIRMATIVE)
        self.assertIn("built_work_signals", diagnostic)
        self.assertNotIn("authorize", diagnostic)
        self.assertNotIn("mutation", diagnostic)

    def test_project_evidence_collections_and_routing_files_are_untouched(self):
        from pathlib import Path

        result = classify_question_scope("What does the RFP require for smoke control?")
        self.assertEqual(result.scope, QUESTION_SCOPE_PROJECT)
        self.assertNotIn("evidence", result.__dict__)
        classifier_source = Path("services/question_scope.py").read_text(encoding="utf-8")
        self.assertNotIn("routes.", classifier_source)
        self.assertNotIn("answer_project_question", classifier_source)

    def test_developer_home_turn_records_ephemeral_diagnostic_without_changing_model_path(self):
        import app as app_module
        from services.project_qa import ProjectQAResult

        temp_root = Path(tempfile.mkdtemp(prefix="archiosk_scope_diag_"))
        try:
            application = app_module.create_app("testing")
            application.config.update(REGISTRY_STORE_PATH=str(temp_root), TESTING=True)
            client = application.test_client()
            with client.session_transaction() as session:
                session.update({"user_id": 1, "username": "admin", "role": "admin", "developer_mode": True})
            fake = ProjectQAResult(ran=True, answer="unchanged model path", provider="fake", model="test")
            with patch("routes.portal.answer_application_question", return_value=fake) as model_call:
                response = client.post("/developer-composer", data={"message": "How do I create an empty panel on the left side of this page?"})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(model_call.call_count, 1)
            with client.session_transaction() as session:
                human = session["developer_home_chats"][-1]["messages"][0]
                diagnostic = human["scope_diagnostic"]
            self.assertEqual(diagnostic["classification"], QUESTION_SCOPE_APPLICATION)
            self.assertEqual(diagnostic["template_id"], "TPL-001")
            self.assertEqual(diagnostic["status"], SCOPE_DIAGNOSTIC_STATUS)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
