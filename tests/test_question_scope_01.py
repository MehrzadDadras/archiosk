import unittest

from services.question_scope import (
    QUESTION_SCOPE_APPLICATION,
    QUESTION_SCOPE_MIXED,
    QUESTION_SCOPE_PROJECT,
    QUESTION_SCOPE_UNKNOWN,
    classify_question_scope,
)


class QuestionScopeClassifierTests(unittest.TestCase):
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

    def test_project_evidence_collections_and_routing_files_are_untouched(self):
        from pathlib import Path

        result = classify_question_scope("What does the RFP require for smoke control?")
        self.assertEqual(result.scope, QUESTION_SCOPE_PROJECT)
        self.assertNotIn("evidence", result.__dict__)
        self.assertNotIn("question_scope", Path("routes/workspace.py").read_text(encoding="utf-8"))
        self.assertNotIn("question_scope", Path("routes/portal.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
