import unittest
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from services.question_scope import (
    QUESTION_SCOPE_APPLICATION,
    QUESTION_SCOPE_MIXED,
    QUESTION_SCOPE_PROJECT,
    QUESTION_SCOPE_UNKNOWN,
    classify_question_scope,
    scope_diagnostic,
    SCOPE_DIAGNOSTIC_STATUS,
)


class QuestionScopeClassifierTests(unittest.TestCase):
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
