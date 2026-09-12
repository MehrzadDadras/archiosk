"""CLAUDE-DATUM-CORROBORATION-WIRING-01: the earned capability nobody could reach.

`record_corroborations` shipped implemented, deployed, and proven on the real
corpus with NO application caller. Every corroboration that existed had been
produced by a scratchpad script rather than by ARCHIOSK - the exact pattern the
master plan section 2 exists to catch, and the second time this programme has
produced it.

What these tests defend:

1. **A CORROBORATION NEEDS TWO SOURCES, AND THE WORKER SEES ONE JOB.** The stage
   runs when a sheet's datum evidence lands and compares it against the sheets
   already read. Each new sheet covers its pairs with every prior one, so
   coverage completes without any sheet being compared to itself or to a sheet
   that does not yet exist.

2. **THE CHEAPEST TEST FIRST.** Most sheets declare no datum, and such a sheet
   must cost effectively nothing - it asks its own register and stops.

3. **THE CLAIM BOUNDARY IS UNCHANGED.** An exact match may corroborate; a
   mismatch stays unresolved and writes nothing. No claim, finding or
   discrepancy writer is reachable from this path.

4. **PERCEPTION SURVIVES.** The stage runs after the job record is terminal, so
   a failure here cannot take a completed examination with it.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from services import datum_corroboration as dc
from services import perception_worker

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _line(text, x, y, width=0.004, height=0.02, passname="native_text"):
    return {"text": text, "x": x, "y": y, "width": width, "height": height,
            "extraction_pass": passname}


def _datum_lines(value, name):
    """One datum marker at the real measured spacing: value, then name beside it."""
    return [_line(value, 0.0803, 0.50, width=0.0096, height=0.0216),
            _line(name, 0.0864, 0.50, width=0.0061, height=0.0216)]


class _Workspace:
    def __init__(self, per_source):
        self.project_id = "p1"
        self.sources = [{"id": sid} for sid in per_source]
        self.structural_units, self.addressable_regions = [], []
        self.evidence_items, self.relationships = [], []
        self.claims, self.findings = [], []
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


class _Store:
    def __init__(self, workspace):
        self.workspace = workspace
        self.calls = []

    def get(self, _project_id):
        return self.workspace

    def record_relationship(self, workspace, **kwargs):
        self.calls.append(kwargs)
        edge = dict(kwargs, id="edge-%d" % len(self.calls))
        workspace.relationships.append(edge)
        return edge


def _job(source_id="arch"):
    return {"workspace_id": "p1", "source_id": source_id, "source_name": "s.pdf"}


def _done():
    return {"state": "completed"}


class Counterparts(unittest.TestCase):
    """Which sheets a newly-read one is compared against."""

    def test_only_sheets_that_declare_a_datum_are_counterparts(self):
        workspace = _Workspace({
            "arch": _datum_lines("188.62", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
            "blank": [_line("GENERAL NOTES", 0.1, 0.1, width=0.02)],
        })
        self.assertEqual(dc.sources_with_datums(workspace, exclude_source_id="arch"),
                         ["struct"])

    def test_a_sheet_is_never_its_own_counterpart(self):
        workspace = _Workspace({"arch": _datum_lines("188.62", "PARK. SLAB")})
        self.assertEqual(dc.sources_with_datums(workspace, exclude_source_id="arch"),
                         [])

    def test_a_removed_source_is_not_a_counterpart(self):
        workspace = _Workspace({
            "arch": _datum_lines("188.62", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        next(s for s in workspace.sources if s["id"] == "struct")["removed_at"] = "now"
        self.assertEqual(dc.sources_with_datums(workspace, exclude_source_id="arch"),
                         [])


class TheStage(unittest.TestCase):
    """The lifecycle hook itself."""

    def _run(self, per_source, source_id="arch", record=None):
        workspace = _Workspace(per_source)
        store = _Store(workspace)
        out = perception_worker._corroborate_datums(
            store, _job(source_id), None, record or _done())
        return out, store, workspace

    def test_an_exact_cross_source_match_is_corroborated(self):
        out, store, _w = self._run({
            "arch": _datum_lines("188.62", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        self.assertEqual(out["corroborated"], 1)
        self.assertEqual(out["relationships_created"], 1)
        self.assertEqual(store.calls[0]["relationship_type"], "corresponds_to")
        self.assertTrue(store.calls[0]["provisional"],
                        "machine-derived correspondence stays provisional")

    def test_a_mismatch_writes_nothing_and_is_still_reported(self):
        out, store, _w = self._run({
            "arch": _datum_lines("188.72", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        self.assertEqual(out["corroborated"], 0)
        self.assertEqual(out["relationships_created"], 0)
        self.assertEqual(out["unresolved"], 1)
        self.assertEqual(store.calls, [])

    def test_a_sheet_with_no_datum_does_nothing_at_all(self):
        out, store, _w = self._run({
            "arch": [_line("GENERAL NOTES", 0.1, 0.1, width=0.02)],
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        self.assertIsNone(out, "the commonest case must cost nothing")
        self.assertEqual(store.calls, [])

    def test_it_does_not_run_on_a_job_that_did_not_complete(self):
        for state in ("needs_attention", "failed", "leased"):
            out, store, _w = self._run(
                {"arch": _datum_lines("188.62", "PARK. SLAB"),
                 "struct": _datum_lines("188620", "PARK. SLAB")},
                record={"state": state})
            self.assertIsNone(out, state)
            self.assertEqual(store.calls, [])

    def test_running_twice_creates_no_duplicate(self):
        workspace = _Workspace({
            "arch": _datum_lines("188.62", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        store = _Store(workspace)
        perception_worker._corroborate_datums(store, _job(), None, _done())
        perception_worker._corroborate_datums(store, _job(), None, _done())
        self.assertEqual(len(store.calls), 1)


class FailureIsolation(unittest.TestCase):
    """A completed examination stays completed."""

    def _workspace(self):
        return _Workspace({
            "arch": _datum_lines("188.62", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })

    def test_a_raising_corroborator_does_not_propagate(self):
        store = _Store(self._workspace())

        def boom(*_a, **_k):
            raise RuntimeError("corroborator fell over")

        with patch.object(dc, "record_corroborations", boom):
            out = perception_worker._corroborate_datums(store, _job(), None, _done())
        self.assertIsNone(out)
        self.assertEqual(store.calls, [])

    def test_the_failure_is_surfaced_in_the_governance_log(self):
        store = _Store(self._workspace())
        events = []

        class _Log:
            def append(self, **kwargs):
                events.append(kwargs)

        def boom(*_a, **_k):
            raise RuntimeError("corroborator fell over")

        with patch.object(dc, "record_corroborations", boom):
            perception_worker._corroborate_datums(store, _job(), _Log(), _done())
        failures = [e for e in events
                    if e.get("event_type") == "datum_corroboration_failed"]
        self.assertTrue(failures)
        self.assertEqual(failures[0]["payload"]["perception_state"], "completed")

    def test_the_outcome_is_logged_even_when_nothing_corroborated(self):
        workspace = _Workspace({
            "arch": _datum_lines("188.72", "PARK. SLAB"),
            "struct": _datum_lines("188620", "PARK. SLAB"),
        })
        store = _Store(workspace)
        events = []

        class _Log:
            def append(self, **kwargs):
                events.append(kwargs)

        perception_worker._corroborate_datums(store, _job(), _Log(), _done())
        done = [e for e in events
                if e.get("event_type") == "datum_corroboration_completed"]
        self.assertTrue(done, "an abstention a reader cannot see is "
                              "indistinguishable from not having looked")
        self.assertEqual(done[0]["payload"]["corroborated"], 0)
        self.assertEqual(done[0]["payload"]["unresolved"], 1)


class Reachability(unittest.TestCase):
    """The integration gap this tranche exists to close."""

    def test_the_worker_calls_the_corroborator_itself(self):
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py")
                         .read_text(encoding="utf-8"))
        calls = {n.func.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("record_corroborations", calls)

    def test_no_second_corroboration_implementation_was_created(self):
        """Section 2: reuse the existing writer, never fork it."""
        worker = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        self.assertNotIn("def corroborate", worker)
        self.assertNotIn("CORRESPONDS_TO", worker)

    def test_no_claim_finding_or_discrepancy_writer_is_reachable(self):
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py")
                         .read_text(encoding="utf-8"))
        target = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "_corroborate_datums")
        called = {n.func.attr for n in ast.walk(target)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for forbidden in ("register_claim", "create_claim", "record_finding",
                          "record_discrepancy", "record_relationship"):
            self.assertNotIn(forbidden, called)


if __name__ == "__main__":
    unittest.main()
