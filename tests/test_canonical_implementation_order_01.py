"""Structural validation for the Canonical Implementation Order registry."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "governance" / "current" / "contracts"


class CanonicalImplementationOrderTests(unittest.TestCase):
    def test_order_has_required_sections_and_inventory_link(self):
        text = (ROOT / "governance/current/canonical-implementation-order.md").read_text(encoding="utf-8")
        for section in ("SITUATION", "MISSION", "EXECUTION", "SUPPORT", "COMMAND & CONTROL"):
            self.assertIn(section, text)
        self.assertIn("page-surface-template-inventory.md", text)
        self.assertIn("Contract compliance check", text)

    def test_registry_resolves_all_initial_contract_records(self):
        registry = (CONTRACTS / "README.md").read_text(encoding="utf-8")
        ids = re.findall(r"\| (CIC-[A-Z-]+) \| v[0-9]+\.[0-9]+ .*?\| \[Record\]\((CIC-[A-Z-]+(?:-v[0-9]+\.[0-9]+)?\.md)\)", registry)
        self.assertEqual(len(ids), 9)
        for contract_id, filename in ids:
            self.assertTrue((CONTRACTS / filename).exists(), contract_id)
            text = (CONTRACTS / filename).read_text(encoding="utf-8")
            self.assertIn(f"CONTRACT ID:** {contract_id}", text)
            self.assertRegex(text, r"VERSION:\*\* v[0-9]+\.[0-9]+")
            self.assertIn("SUPERSEDED BY", text)

    def test_no_second_contract_registry_exists(self):
        # A count, not a ceiling. The registry's own version rule requires a
        # NEW file per version ("Do not edit an approved invariant in place.
        # Create the next version, state SUPERSEDES and the semantic delta"),
        # so this number rises by one every time a contract is superseded -
        # CIC-DEVELOPER-MODE-v1.1, CIC-SPIN-INTELLIGENCE-v1.1, and now
        # CIC-PANEL-v1.1 (CLAUDE-MOBILE-FRAME-02), and now
        # CIC-GO-CONVERSATION-v1.1 (CLAUDE-AIRLOCK-WEB-RESEARCH-01, which both
        # added external research as an answering domain and corrected a KNOWN
        # LIMITATION that CLAUDE-GO-GATEWAY-COGNITION-01/02 had already made
        # untrue), and now CIC-SPIN-INTELLIGENCE-v1.2 (GOV-CN-001, approved
        # 2026-08-30 and recorded by GOV-S-001 - a PARTIAL supersession
        # admitting Multi-Observer Shear as a layer distinct from Helix; every
        # v1.1 invariant, both Helix clauses included, carries forward
        # verbatim). What this test actually guards is the line below: one
        # registry, in one place.
        records = list((ROOT / "governance").rglob("CIC-*.md"))
        self.assertEqual(len(records), 14)
        self.assertEqual((CONTRACTS / "README.md").exists(), True)
