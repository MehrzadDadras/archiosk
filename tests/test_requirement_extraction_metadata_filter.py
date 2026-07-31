"""
CLAUDE-P38 (OBS-09) -- document cover-page/header metadata (RFP
number, version, issue date, issuing organization, document status)
was being classified as a requirement candidate exactly like real
requirement text, because REQUIREMENT_CATEGORIES has no "not a
requirement at all" option in either classifier's schema. Proves the
new pre-filter (services/bhive_parser.py's _is_document_metadata_line,
applied before classification) removes exactly the metadata-shaped
lines the browser walkthrough actually reported, while leaving real
requirement text (including lines that merely mention a date or a
version in passing) untouched.

Uses BHiveParser(anthropic_api_key=None) throughout -- the deterministic
rule-based classifier, no network call, same pattern as
tests/test_foundation_batch_h.py.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from services.bhive_parser import BHiveParser, _is_document_metadata_line

_SAMPLE_DOCUMENT = b"""RFP No: 2026-PROD-099
Version: 1.0
Issue Date: January 15, 2026
Issuing Organization: Riverside Municipal Authority
Document Status: Final

Section 1 - Scope of Work
The Design-Builder shall provide all labor, materials, and equipment
required to complete the renovation.

Section 2 - Technical Specification
All structural steel shall conform to CSA G40.21 350W.
"""


class DocumentMetadataLineDetectionTests(unittest.TestCase):
    def test_rfp_number_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("RFP No: 2026-PROD-099"))

    def test_version_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("Version: 1.0"))

    def test_issue_date_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("Issue Date: January 15, 2026"))

    def test_issuing_organization_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("Issuing Organization: Riverside Municipal Authority"))

    def test_document_status_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("Document Status: Final"))

    def test_page_footer_is_detected_as_metadata(self):
        self.assertTrue(_is_document_metadata_line("Page 3 of 42"))

    def test_a_real_requirement_mentioning_a_date_is_not_excluded(self):
        # Only lines that actually START with a metadata label are
        # excluded -- a requirement that happens to mention a date or
        # version mid-sentence must survive.
        self.assertFalse(_is_document_metadata_line(
            "Substantial performance shall be achieved no later than the Issue Date plus 18 months."
        ))
        self.assertFalse(_is_document_metadata_line(
            "The software version shall be no older than 2.0 at time of demonstration."
        ))

    def test_ordinary_requirement_text_is_not_excluded(self):
        self.assertFalse(_is_document_metadata_line(
            "All structural steel shall conform to CSA G40.21 350W."
        ))


class ExtractionExcludesMetadataEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.parser = BHiveParser(anthropic_api_key=None)

    def test_cover_page_metadata_does_not_appear_as_a_requirement_candidate(self):
        document = self.parser.parse(_SAMPLE_DOCUMENT, "sample_rfp.txt")
        texts = [r.text for r in document.requirements]

        for metadata_fragment in ("RFP No:", "Version:", "Issue Date:", "Issuing Organization:", "Document Status:"):
            self.assertFalse(
                any(t.startswith(metadata_fragment) for t in texts),
                f"{metadata_fragment!r} leaked into requirement candidates: {texts}",
            )

    def test_real_requirement_text_still_survives_the_filter(self):
        document = self.parser.parse(_SAMPLE_DOCUMENT, "sample_rfp.txt")
        texts = [r.text for r in document.requirements]
        self.assertTrue(any("structural steel" in t for t in texts))
        self.assertTrue(any("labor, materials" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
