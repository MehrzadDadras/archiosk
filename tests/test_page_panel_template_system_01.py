"""Structural checks for the page-by-panel governance inventory."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PagePanelTemplateSystemTests(unittest.TestCase):
    def setUp(self):
        self.inventory = (ROOT / "governance/current/page-surface-template-inventory.md").read_text(encoding="utf-8")
        self.panels = (ROOT / "governance/current/panel-template-system.md").read_text(encoding="utf-8")

    def test_all_eighteen_tpl_ids_have_panel_composition_rows(self):
        ids = {f"TPL-{number:03d}" for number in range(1, 19)}
        rows = set(re.findall(r"\| (TPL-\d{3}) \|", self.panels))
        self.assertEqual(ids, rows)
        self.assertIn("panel-template-system.md", self.inventory)

    def test_layout_and_nested_catalogues_are_controlled(self):
        for layout in ("LAY-1", "LAY-2V", "LAY-2H", "LAY-3A", "LAY-4A", "LAY-5A", "LAY-2H-R"):
            self.assertIn(f"| {layout} |", self.panels)
        self.assertGreaterEqual(len(set(re.findall(r"\| (NPT-\d{3}) \|", self.panels))), 10)
        self.assertIn("Closing hides a panel only", self.panels)
        self.assertIn("Menus are the canonical", (ROOT / "governance/current/contracts/CIC-PANEL.md").read_text(encoding="utf-8"))

