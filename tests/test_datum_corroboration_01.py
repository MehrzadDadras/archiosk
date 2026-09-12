"""CLAUDE-DATUM-CORROBORATION-01: an exact match may corroborate; a mismatch may not accuse.

Product Owner decision, 2026-09-11: ARCHIOSK may assert CROSS-DISCIPLINE
CORROBORATION. It may NOT assert a cross-discipline DISCREPANCY from an
OCR-derived mismatch. Mismatches abstain.

The asymmetry is measured, not cautious. Against the exact structural register,
architectural OCR readings produced 7 exact matches and 3 near misses, and every
near miss is indistinguishable from a real coordination error by its value:

  - `192320` against `192610`, delta -290 mm, which reads like a textbook
    discrepancy and is `C.L. OF RD.` - the ROAD CENTRELINE, an
    architecture-only datum with no structural counterpart, forced onto the
    nearest structural number by a nearest-value pairing;
  - `186620` against `186670` (-50) and `191700` against `191500` (+200), where
    one mis-read digit produces exactly the magnitude a real error has.

An exact match is SELF-CORROBORATING: a mis-read digit destroys a match, it can
never create one. That is why one direction is assertable and the other is not,
and `MismatchNeverAccuses` is the largest class here because it is the whole
governed boundary.

What these tests defend:

1. **NOTHING IS ASSERTED ON A MISMATCH.** No relationship, no claim, no
   finding - and the pair is still REPORTED, because an abstention a reader
   cannot see is indistinguishable from not having looked.
2. **NO NEW VOCABULARY.** A corroboration is `RELATIONSHIP_TYPE_CORRESPONDS_TO`
   through the existing writer, and it is PROVISIONAL because a machine derived
   it - `provisional=False` stays reserved for human confirmation.
3. **COUNTERPART FIDELITY IS REQUIRED, NOT ASSUMED.** `PARK FTG` and
   `PARK SLAB` share a token and are not the same thing.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from services import datum_corroboration as dc

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _line(text, x, y, width=0.004, height=0.02, region=None, passname="native_text"):
    return {"text": text, "x": x, "y": y, "width": width, "height": height,
            "region_id": region or ("r-" + text.replace(" ", "-")),
            "extraction_pass": passname}


def _datum(value, name, *, x=0.50, y=0.50, qualifier="U/S", passname="native_text",
           region=None):
    """One datum marker in the real measured layout: name | value | qualifier."""
    value_line = _line(value, x, y, region=region, passname=passname)
    name_line = _line(name, x - 0.0135, y, width=0.012, passname=passname)
    qual_line = _line(qualifier, x + 0.0041, y, width=0.004, passname=passname)
    return [name_line, value_line, qual_line]


class Units(unittest.TestCase):
    """Structure states millimetres; architecture states metres."""

    def test_both_written_forms_normalise_to_one_number(self):
        self.assertEqual(dc.to_millimetres("192610"), 192610)
        self.assertEqual(dc.to_millimetres("192.61"), 192610)
        self.assertEqual(dc.to_millimetres("186.67"), 186670)

    def test_a_member_size_is_not_a_level(self):
        for not_a_level in ("300", "W250X33", "12", "1850", "", None):
            self.assertIsNone(dc.to_millimetres(not_a_level))

    def test_normalisation_is_stated_value_not_measurement(self):
        source = (_REPO_ROOT / "services" / "datum_corroboration.py").read_text(
            encoding="utf-8")
        for banned in ("scale_factor", "points_per_foot", "px_per_mm", "world_",
                       "dpi"):
            self.assertNotIn(banned, source.lower())


class Names(unittest.TestCase):
    """A datum name is a token set, because the two sides disagree on order."""

    def test_order_does_not_change_identity(self):
        self.assertEqual(dc.name_tokens("ELEV. FTG"), dc.name_tokens("FTG ELEV"))

    def test_punctuation_and_stop_words_do_not_change_identity(self):
        self.assertEqual(dc.name_tokens("TOP OF SKYLIGHT"),
                         dc.name_tokens("TOP SKYLIGHT"))

    def test_two_different_datums_sharing_one_word_are_not_the_same(self):
        park_ftg = dc.name_tokens("PARK. FTG")
        park_slab = dc.name_tokens("PARK. SLAB")
        self.assertNotEqual(park_ftg, park_slab)
        matched, _basis = dc._match_names([park_ftg], [park_slab])
        self.assertFalse(matched, "sharing only PARK must not pair a footing "
                                  "with a slab")

    def test_a_contained_name_is_the_same_datum(self):
        matched, basis = dc._match_names([dc.name_tokens("EXT. ST.")],
                                         [dc.name_tokens("EXT. ST. FTG")])
        self.assertTrue(matched)
        self.assertIn("EXT", basis)


class Association(unittest.TestCase):
    """Positional, because text proximity was measured and was wrong."""

    def test_a_value_takes_the_label_beside_it(self):
        lines = _datum("191500", "PERIMETER BEAM")
        value = next(l for l in lines if l["text"] == "191500")
        names = dc.names_beside(value, lines)
        self.assertEqual([n["text"] for n in names], ["PERIMETER BEAM"])

    def test_a_qualifier_is_never_read_as_a_name(self):
        lines = _datum("191500", "PERIMETER BEAM", qualifier="U/S")
        value = next(l for l in lines if l["text"] == "191500")
        self.assertNotIn("U/S", [n["text"] for n in dc.names_beside(value, lines)])

    def test_a_datum_may_carry_a_label_on_each_side(self):
        """`192610` is written between `F.F.` and `GR. FL. SLAB`; both are real."""
        value = _line("192610", 0.50, 0.50)
        lines = [value,
                 _line("F.F.", 0.4859, 0.50, width=0.012),
                 _line("GR. FL. SLAB", 0.5051, 0.50, width=0.012)]
        names = {n["text"] for n in dc.names_beside(value, lines)}
        self.assertEqual(names, {"F.F.", "GR. FL. SLAB"})

    def test_a_distant_label_is_not_taken(self):
        value = _line("191500", 0.50, 0.50)
        lines = [value, _line("ROOF DECK", 0.80, 0.50, width=0.012)]
        self.assertEqual(dc.names_beside(value, lines), [])

    def test_a_label_on_another_line_is_not_taken(self):
        value = _line("191500", 0.50, 0.50)
        lines = [value, _line("ROOF DECK", 0.4865, 0.90, width=0.012)]
        self.assertEqual(dc.names_beside(value, lines), [])

    def test_another_number_is_never_a_name(self):
        value = _line("191500", 0.50, 0.50)
        lines = [value, _line("192610", 0.4859, 0.50)]
        self.assertEqual(dc.names_beside(value, lines), [])


class _Workspace:
    """The smallest thing `datum_register` needs: regions, units, evidence."""

    def __init__(self, per_source):
        self.project_id = "p1"
        self.sources = [{"id": sid} for sid in per_source]
        self.structural_units, self.addressable_regions = [], []
        self.evidence_items, self.relationships = [], []
        for sid, lines in per_source.items():
            unit_id = "u-" + sid
            self.structural_units.append(
                {"id": unit_id, "source_id": sid, "unit_type": "page",
                 "order_index": 0, "label": "Page 1"})
            for i, line in enumerate(lines):
                rid = "%s-r%d" % (sid, i)
                self.addressable_regions.append({
                    "id": rid, "structural_unit_id": unit_id,
                    "address": {"x": line["x"], "y": line["y"],
                                "width": line["width"], "height": line["height"],
                                "extraction_pass": line["extraction_pass"]}})
                self.evidence_items.append({
                    "source_id": sid, "region_id": rid,
                    "content_type": "positioned_text", "content": line["text"]})


class Corroboration(unittest.TestCase):
    """The one thing ARCHIOSK is authorized to assert."""

    def _workspace(self, arch_value, struct_value, name="PARK. SLAB"):
        return _Workspace({
            "arch": _datum(arch_value, name, passname="positioned_ocr"),
            "struct": _datum(struct_value, name, passname="native_text"),
        })

    def test_an_exact_match_across_disciplines_corroborates(self):
        report = dc.corroborate(self._workspace("188.62", "188620"),
                                "arch", "struct")
        self.assertEqual(len(report["corroborated"]), 1)
        self.assertEqual(report["unresolved"], [])
        item = report["corroborated"][0]
        self.assertEqual(item["value_mm"], 188620)
        self.assertEqual(item["status"], dc.STATUS_CORROBORATED)
        self.assertIn("188.62", item["normalisation"])
        self.assertIn("188620", item["normalisation"])

    def test_both_sides_keep_their_own_verbatim_and_unit(self):
        report = dc.corroborate(self._workspace("188.62", "188620"),
                                "arch", "struct")
        item = report["corroborated"][0]
        self.assertEqual(item["left_verbatim"], "188.62")
        self.assertEqual(item["right_verbatim"], "188620")
        self.assertEqual(item["left"]["unit_as_written"], "m")
        self.assertEqual(item["right"]["unit_as_written"], "mm")

    def test_provenance_reaches_both_regions_and_pages(self):
        report = dc.corroborate(self._workspace("188.62", "188620"),
                                "arch", "struct")
        item = report["corroborated"][0]
        for side in ("left", "right"):
            self.assertTrue(item[side]["region_id"])
            self.assertTrue(item[side]["structural_unit_id"])
            self.assertIn(item[side]["extraction_pass"],
                          ("native_text", "positioned_ocr"))


class MismatchNeverAccuses(unittest.TestCase):
    """The governed boundary. Nothing is asserted from a disagreement."""

    def _workspace(self, arch_value, struct_value, name="PARK. SLAB"):
        return _Workspace({
            "arch": _datum(arch_value, name, passname="positioned_ocr"),
            "struct": _datum(struct_value, name, passname="native_text"),
        })

    def test_a_differing_value_is_unresolved_not_a_discrepancy(self):
        report = dc.corroborate(self._workspace("188.72", "188620"),
                                "arch", "struct")
        self.assertEqual(report["corroborated"], [])
        self.assertEqual(len(report["unresolved"]), 1)
        self.assertEqual(report["unresolved"][0]["status"], dc.STATUS_UNRESOLVED)

    def test_the_real_near_miss_that_is_not_an_error_at_all(self):
        """`192.32` is C.L. OF RD. - a datum only architecture has.

        Under a nearest-value rule it becomes a -290mm discrepancy against
        192610. Here it pairs with nothing, because its NAME pairs with nothing.
        """
        workspace = _Workspace({
            "arch": _datum("192.32", "C.L. OF RD", passname="positioned_ocr"),
            "struct": _datum("192610", "GR. FL. SLAB", passname="native_text"),
        })
        report = dc.corroborate(workspace, "arch", "struct")
        self.assertEqual(report["corroborated"], [])
        self.assertEqual(report["unresolved"], [],
                         "an architecture-only datum must not be forced onto "
                         "the nearest structural number")

    def test_no_discrepancy_vocabulary_exists_in_the_module(self):
        source = (_REPO_ROOT / "services" / "datum_corroboration.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for forbidden in ("register_claim", "create_claim", "record_finding",
                          "record_discrepancy", "create_finding"):
            self.assertNotIn(forbidden, called)

    def test_the_only_relationship_type_used_is_corresponds_to(self):
        source = (_REPO_ROOT / "services" / "datum_corroboration.py").read_text(
            encoding="utf-8")
        for forbidden in ("RELATIONSHIP_TYPE_CONTRADICTS",
                          "RELATIONSHIP_TYPE_INVALIDATES"):
            self.assertNotIn(forbidden, source)
        self.assertIn("RELATIONSHIP_TYPE_CORRESPONDS_TO", source)


class Writing(unittest.TestCase):
    """What reaches the store, and what deliberately does not."""

    class _Store:
        def __init__(self):
            self.calls = []

        def record_relationship(self, workspace, **kwargs):
            self.calls.append(kwargs)
            edge = dict(kwargs, id="edge-%d" % len(self.calls))
            workspace.relationships.append(edge)
            return edge

    def _workspace(self, arch_value, struct_value):
        return _Workspace({
            "arch": _datum(arch_value, "PARK. SLAB", passname="positioned_ocr"),
            "struct": _datum(struct_value, "PARK. SLAB", passname="native_text"),
        })

    def test_a_corroboration_writes_one_corresponds_to_edge(self):
        store = self._Store()
        workspace = self._workspace("188.62", "188620")
        report = dc.record_corroborations(store, workspace, "arch", "struct")
        self.assertEqual(report["relationships_created"], 1)
        self.assertEqual(store.calls[0]["relationship_type"], "corresponds_to")
        self.assertEqual(store.calls[0]["from_type"], "addressable_region")

    def test_the_edge_is_provisional_because_a_machine_derived_it(self):
        store = self._Store()
        dc.record_corroborations(store, self._workspace("188.62", "188620"),
                                 "arch", "struct")
        self.assertTrue(store.calls[0]["provisional"],
                        "provisional=False is reserved for human confirmation")

    def test_the_reason_states_both_values_and_the_name_basis(self):
        store = self._Store()
        dc.record_corroborations(store, self._workspace("188.62", "188620"),
                                 "arch", "struct")
        reason = store.calls[0]["reason"]
        for fragment in ("188.62", "188620", "PARK. SLAB", dc.CORROBORATION_VERSION):
            self.assertIn(fragment, reason)

    def test_a_mismatch_writes_nothing_at_all(self):
        store = self._Store()
        report = dc.record_corroborations(store, self._workspace("188.72", "188620"),
                                          "arch", "struct")
        self.assertEqual(store.calls, [])
        self.assertEqual(report["relationships_created"], 0)
        self.assertEqual(len(report["unresolved"]), 1,
                         "an abstention a reader cannot see is "
                         "indistinguishable from not having looked")

    def test_running_twice_adds_nothing(self):
        store = self._Store()
        workspace = self._workspace("188.62", "188620")
        dc.record_corroborations(store, workspace, "arch", "struct")
        again = dc.record_corroborations(store, workspace, "arch", "struct")
        self.assertEqual(again["relationships_created"], 0)
        self.assertEqual(len(store.calls), 1)

    def test_a_dry_run_writes_nothing(self):
        store = self._Store()
        report = dc.record_corroborations(store, self._workspace("188.62", "188620"),
                                          "arch", "struct", dry_run=True)
        self.assertEqual(store.calls, [])
        self.assertEqual(len(report["corroborated"]), 1)


class NoEgress(unittest.TestCase):
    def test_the_module_reaches_no_provider_and_no_network(self):
        source = (_REPO_ROOT / "services" / "datum_corroboration.py").read_text(
            encoding="utf-8")
        for banned in ("requests.", "urllib.request", "anthropic", "genai", "httpx"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
