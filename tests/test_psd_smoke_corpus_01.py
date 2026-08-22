"""Integrity and blindness checks for the published PSD smoke corpus."""

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parent / "fixtures" / "psd"
BUILDER = ROOT / "builder_corpus"
ORACLE = ROOT / "oracle" / "psd-rfp-adversarial-001.md"


class PsdSmokeCorpusIntegrityTests(unittest.TestCase):
    def test_manifest_points_to_bounded_builder_package_and_private_oracle(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["builder_root"], "builder_corpus")
        self.assertEqual(manifest["oracle_path"], "oracle/psd-rfp-adversarial-001.md")
        self.assertTrue(ORACLE.exists())
        self.assertFalse(ORACLE.is_relative_to(BUILDER))

    def test_every_manifest_document_exists_and_is_builder_visible(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        listed = {entry["file"] for entry in manifest["documents"]}
        actual = {path.name for path in BUILDER.glob("PSD-*.md")}
        self.assertEqual(actual, listed)

    def test_builder_files_do_not_contain_oracle_markers(self):
        forbidden = ("answer key", "oracle", "expected evaluation", "PSD-A01", "do not ingest")
        for path in BUILDER.glob("*.md"):
            text = path.read_text(encoding="utf-8").lower()
            for marker in forbidden:
                self.assertNotIn(marker.lower(), text, path.name)

    def test_package_contains_mixed_realistic_conditions(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in BUILDER.glob("PSD-*.md")).lower()
        for phrase in ("addendum", "shop drawings", "verification", "access clearance", "proposal", "superseded"):
            self.assertIn(phrase, text)
        self.assertGreaterEqual(len(list(BUILDER.glob("PSD-*.md"))), 8)

    def test_oracle_covers_required_evaluation_classes(self):
        oracle = ORACLE.read_text(encoding="utf-8").lower()
        for phrase in ("non-closed upstream", "peer-condition divergence", "propagation delta", "pricing exposure", "clean control", "insufficient evidence", "legitimate variation", "resolved history", "contradictory live evidence"):
            self.assertIn(phrase, oracle)


if __name__ == "__main__":
    unittest.main()
