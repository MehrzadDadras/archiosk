"""
CLAUDE-CGP-02: focused tests for services/formatting.py's source_kind_label -
a presentation-only display gloss over Source.kind (services/case_workspace.py's
open-world string field). Confirms the mapped case, the unmapped fallback
(still the pre-existing underscore-replace humanization), and the empty/None
edge case, so a future change to the mapping can't silently regress either
behavior.
"""
import unittest

from services.formatting import source_kind_label


class SourceKindLabelTests(unittest.TestCase):
    def test_known_kind_uses_mapped_label(self):
        self.assertEqual(source_kind_label("rfq_rfp_document"), "Project Document")

    def test_unmapped_kind_falls_back_to_humanized_replace(self):
        self.assertEqual(source_kind_label("drawing"), "drawing")
        self.assertEqual(source_kind_label("text_record"), "text record")

    def test_empty_or_none_returns_empty_string(self):
        self.assertEqual(source_kind_label(None), "")
        self.assertEqual(source_kind_label(""), "")


if __name__ == "__main__":
    unittest.main()
