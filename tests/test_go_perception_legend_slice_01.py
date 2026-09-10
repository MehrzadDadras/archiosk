"""CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01: what are the ENTRIES in that block?

Detection says WHERE a legend appears to be. Slicing says what rows appear to
be in it - and stops there. What these tests defend, in the order the mistakes
would be made:

1. **A SLICE IS NOT A REGISTRATION.** The whole tranche is worthless if a
   proposed exemplar can become accepted meaning, widen a scope, confirm a
   family or slip past the registration-authority containment that landed in
   `88059bb`. `ProposalOnly` and `AuthorityCarryThrough` pin that, by reading
   the module's own AST for the calls it must not make rather than by
   forbidding a word its docstring legitimately uses.

2. **A ROW IS NOT AN ENTRY.** "AD    AREA DRAIN" is one entry read as two
   boxes; a wrapped label is one entry read as two rows. Getting either wrong
   silently produces a plausible, wrong subdivision - the worst outcome
   available here, because it looks like success.

3. **UNCERTAINTY SURVIVES.** A block that does not resolve must say so. The
   measured case is real: on M2_OF_3, a genuine 2000-era scan, the block
   produced an entry 0.0012 tall whose entire text was a backslash. Anything
   that reports that as a clean entry is lying with geometry.

Geometry is 0-1 fractions of the orientation-normalized frame, as the
perception layer stores it. Nothing here needs Tesseract, an image or a network.
"""
from __future__ import annotations

import ast
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services import legend_detection as ld
from services import legend_slicing as ls
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _png():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), (255, 255, 255)).save(buffer, "PNG")
    return buffer.getvalue()


def _line(text, x, y, width=0.10, height=0.010):
    return {"x": x, "y": y, "width": width, "height": height, "text": text}


def _referenced_names(module_filename):
    """Every name and attribute the module actually references.

    Reading the source as TEXT would fail on this module's own docstring, which
    names `resolve_meaning` precisely to say it is never entered. A test that
    forbids a WORD rather than a MECHANISM catches the explanation instead of
    the behaviour - a mistake this repository has made before, and the reason
    `legend_detection.py`'s own guard is written exactly this way.
    """
    tree = ast.parse((_REPO_ROOT / "services" / module_filename).read_text(
        encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
                if alias.asname:
                    names.add(alias.asname)
    return names


# -- fixture blocks, shaped like the real sheets this was measured on ---------
#
# Pitch and height come from RD-A-L03-001 Rev02, whose CIRCULATION LEGEND runs
# at an 18pt pitch on a 705pt sheet: 0.0255 normalized, with 0.0144 text. Using
# the real proportions means these fixtures exercise the same rhythm rules the
# real sheet does rather than a spacing chosen to make them pass.

PITCH = 0.0255
TEXT_H = 0.0144


def _block(rows, *, heading="LEGEND", x=0.80, y=0.20):
    """A heading plus rows, each row a list of (text, x, width) parts."""
    lines = [_line(heading, x, y, 0.09, TEXT_H)]
    for index, parts in enumerate(rows):
        top = y + TEXT_H + PITCH * (index + 1)
        for text, px, pw in parts:
            lines.append(_line(text, px, top, pw, TEXT_H))
    return lines


def _one_column(count=5):
    return _block([[("Public area %d" % (i + 1), 0.82, 0.09)] for i in range(count)])


def _icon_left(count=5):
    """A code column and a description column on one baseline, gap between."""
    return _block([[("AD%d" % (i + 1), 0.80, 0.015),
                    ("AREA DRAIN %d" % (i + 1), 0.85, 0.07)] for i in range(count)])


def _candidate_for(lines):
    detection = ld.detect_candidates(lines, source_id="s1")
    assert detection["candidates"], detection["outcome"]
    return detection["candidates"][0]


class OneColumnLegend(unittest.TestCase):
    """The measured base case: RD-A-L03-001's own shape."""

    def setUp(self):
        self.lines = _one_column()
        self.result = ls.slice_candidate(_candidate_for(self.lines), self.lines)

    def test_every_row_becomes_its_own_entry(self):
        self.assertEqual(self.result["outcome"], ls.OUTCOME_SLICED)
        self.assertEqual(self.result["entry_count"], 5)

    def test_each_entry_carries_the_text_that_was_read_in_it(self):
        for index, entry in enumerate(self.result["entries"]):
            with self.subTest(entry=index):
                self.assertEqual(entry["observed_text"], "Public area %d" % (index + 1))

    def test_order_is_persisted_and_follows_the_sheet(self):
        """Never re-derivable later from a uuid, a timestamp or a filename."""
        indexes = [e["entry_index"] for e in self.result["entries"]]
        self.assertEqual(indexes, [0, 1, 2, 3, 4])
        tops = [e["region"]["y"] for e in self.result["entries"]]
        self.assertEqual(tops, sorted(tops))

    def test_the_band_spans_the_block_so_a_crop_shows_the_symbol(self):
        """The symbol produces no text and so is in no text box. The band is
        what makes it recoverable - proven on the real sheet, where every
        swatch falls inside its entry's band."""
        parent = _candidate_for(self.lines)["region"]
        for entry in self.result["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertEqual(entry["region"]["x"], parent["x"])
                self.assertEqual(entry["region"]["width"], parent["width"])
                self.assertGreater(entry["region"]["width"],
                                   entry["text_bbox"]["width"] * 0.99)

    def test_text_bbox_and_band_are_never_conflated(self):
        for entry in self.result["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertIn("text_bbox", entry)
                self.assertIsNot(entry["region"], entry["text_bbox"])


class MultiLineAndTextOnlyRows(unittest.TestCase):

    def test_a_tight_wrapped_second_line_joins_the_entry_above(self):
        lines = _one_column(5)
        # A continuation sits far tighter than the block's own pitch - the
        # shape the real note on RD-A-L03-001 has.
        first_top = 0.20 + TEXT_H + PITCH
        lines.append(_line("continued onto a second line", 0.82,
                           first_top + TEXT_H + 0.002, 0.09, TEXT_H))
        result = ls.slice_candidate(_candidate_for(lines), lines)
        merged = [e for e in result["entries"] if e["row_count"] > 1]
        self.assertEqual(len(merged), 1, "the wrap must not become its own entry")
        self.assertIn("continued onto a second line", merged[0]["observed_text"])

    def test_a_text_only_row_has_no_invented_icon_zone(self):
        result = ls.slice_candidate(_candidate_for(_one_column()), _one_column())
        for entry in result["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertIsNone(entry["icon_zone"])
                self.assertTrue(entry["icon_zone_reason"])

    def test_a_row_with_two_parts_is_one_entry_not_two(self):
        """'AD  AREA DRAIN' is one entry read as two boxes. Reading it as two
        entries is the single most likely wrong subdivision here."""
        lines = _icon_left()
        result = ls.slice_candidate(_candidate_for(lines), lines)
        self.assertEqual(result["entry_count"], 5)
        for entry in result["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertEqual(entry["text_part_count"], 2)
                self.assertIn("AREA DRAIN", entry["observed_text"])

    def test_a_wide_intra_row_gap_is_reported_as_a_candidate_visual_zone(self):
        lines = _block([[("AD", 0.80, 0.012), ("AREA DRAIN", 0.86, 0.06)]
                        for _ in range(5)])
        result = ls.slice_candidate(_candidate_for(lines), lines)
        zoned = [e for e in result["entries"] if e["icon_zone"]]
        self.assertTrue(zoned, "a gap far wider than word spacing must be reported")
        zone = zoned[0]["icon_zone"]
        self.assertGreater(zone["width"], 0)
        for key in ("x", "y", "width", "height"):
            self.assertIsInstance(zone[key], float)

    def test_a_visual_zone_is_a_spatial_fact_and_never_a_meaning(self):
        lines = _block([[("AD", 0.80, 0.012), ("AREA DRAIN", 0.86, 0.06)]
                        for _ in range(5)])
        result = ls.slice_candidate(_candidate_for(lines), lines)
        for entry in result["entries"]:
            for forbidden in ("meaning", "symbol_meaning", "signifies",
                              "proposed_meaning", "interpretation"):
                with self.subTest(entry=entry["entry_index"], key=forbidden):
                    self.assertNotIn(forbidden, entry)


class UncertaintySurvives(unittest.TestCase):

    def test_a_degenerate_row_is_ambiguous_not_proposed(self):
        """MEASURED, not anticipated: M2_OF_3 produced an entry 0.0012 tall
        whose whole text was a backslash, beside real rows."""
        lines = _one_column(5)
        lines.append(_line("\\", 0.82, 0.20 + TEXT_H + PITCH * 6, 0.004, 0.0012))
        result = ls.slice_candidate(_candidate_for(lines), lines)
        tiny = [e for e in result["entries"] if e["observed_text"] == "\\"]
        self.assertTrue(tiny)
        self.assertEqual(tiny[0]["slice_resolution"], ls.SLICE_AMBIGUOUS)

    def test_an_entry_with_no_letter_or_digit_is_ambiguous(self):
        lines = _one_column(5)
        lines.append(_line("*** ---", 0.82, 0.20 + TEXT_H + PITCH * 6, 0.05, TEXT_H))
        result = ls.slice_candidate(_candidate_for(lines), lines)
        junk = [e for e in result["entries"] if e["observed_text"] == "*** ---"]
        self.assertTrue(junk)
        self.assertEqual(junk[0]["slice_resolution"], ls.SLICE_AMBIGUOUS)

    def test_a_thin_block_establishes_no_rhythm_and_merges_nothing(self):
        """Below the floor there is no median worth the name, and guessing
        from two samples would be inventing structure."""
        lines = _block([[("Public area 1", 0.82, 0.09)],
                        [("Public area 2", 0.82, 0.09)]])
        result = ls.slice_candidate(_candidate_for(lines), lines)
        self.assertFalse(result["rhythm_established"])
        for entry in result["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertEqual(entry["row_count"], 1)

    def test_a_block_where_nothing_resolves_says_unresolved(self):
        result = ls.slice_candidate(
            {"region": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
             "heading": {"text": "LEGEND", "x": 0.1, "y": 0.1,
                         "width": 0.05, "height": 0.01}},
            [_line("LEGEND", 0.1, 0.1, 0.05, 0.01),
             _line("***", 0.11, 0.13, 0.02, 0.01),
             _line("---", 0.11, 0.16, 0.02, 0.01)])
        self.assertEqual(result["outcome"], ls.OUTCOME_UNRESOLVED)
        for entry in result["entries"]:
            self.assertEqual(entry["slice_resolution"], ls.SLICE_UNRESOLVED)

    def test_a_candidate_with_no_rows_produces_nothing(self):
        result = ls.slice_candidate(
            {"region": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.05},
             "heading": {"text": "LEGEND", "x": 0.1, "y": 0.1,
                         "width": 0.05, "height": 0.01}},
            [_line("LEGEND", 0.1, 0.1, 0.05, 0.01)])
        self.assertEqual(result["outcome"], ls.OUTCOME_NO_ROWS)
        self.assertEqual(result["entries"], [])


class Geometry(unittest.TestCase):

    def _all_entries(self):
        for maker in (_one_column, _icon_left):
            lines = maker()
            candidate = _candidate_for(lines)
            for entry in ls.slice_candidate(candidate, lines)["entries"]:
                yield candidate, entry

    def test_every_box_stays_inside_the_normalized_frame(self):
        for candidate, entry in self._all_entries():
            for name in ("region", "text_bbox"):
                box = entry[name]
                with self.subTest(entry=entry["entry_index"], box=name):
                    self.assertGreaterEqual(box["x"], 0.0)
                    self.assertGreaterEqual(box["y"], 0.0)
                    self.assertGreater(box["width"], 0.0)
                    self.assertGreater(box["height"], 0.0)
                    self.assertLessEqual(box["x"] + box["width"], 1.0 + 1e-9)
                    self.assertLessEqual(box["y"] + box["height"], 1.0 + 1e-9)

    def test_every_entry_sits_inside_its_parent_candidate(self):
        """A slice detached from its block is a rectangle with no provenance."""
        for candidate, entry in self._all_entries():
            parent, box = candidate["region"], entry["region"]
            with self.subTest(entry=entry["entry_index"]):
                self.assertGreaterEqual(box["x"], parent["x"] - 1e-9)
                self.assertGreaterEqual(box["y"], parent["y"] - 1e-9)
                self.assertLessEqual(box["x"] + box["width"],
                                     parent["x"] + parent["width"] + 1e-9)
                self.assertLessEqual(box["y"] + box["height"],
                                     parent["y"] + parent["height"] + 1e-9)

    def test_entries_do_not_overlap_vertically(self):
        for maker in (_one_column, _icon_left):
            lines = maker()
            entries = ls.slice_candidate(_candidate_for(lines), lines)["entries"]
            for previous, current in zip(entries, entries[1:]):
                with self.subTest(pair=(previous["entry_index"],
                                        current["entry_index"])):
                    self.assertLessEqual(
                        previous["region"]["y"] + previous["region"]["height"],
                        current["region"]["y"] + 1e-9)


class ProposalOnly(unittest.TestCase):
    """A candidate exemplar is not a registration, and must not become one."""

    def test_every_entry_says_so_in_the_record(self):
        lines = _one_column()
        for entry in ls.slice_candidate(_candidate_for(lines), lines)["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                self.assertEqual(entry["status"], "candidate_only")

    def test_no_registration_call_exists_in_the_module(self):
        """Checked as a MECHANISM, not as a forbidden word."""
        names = _referenced_names("legend_slicing.py")
        for forbidden in ("propose_legend_item", "decide_legend_item",
                          "decide_proposition", "confirm_family",
                          "apply_family_decision", "register_family",
                          "inherit_proposition", "inherit_group_understanding",
                          "break_inheritance", "propose_target", "LegendItem",
                          "resolve_meaning", "effective_meaning",
                          "effective_evidence_tier", "LEGEND_PRECEDENCE_ORDER"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_no_scope_is_carried_or_mutated(self):
        lines = _one_column()
        for entry in ls.slice_candidate(_candidate_for(lines), lines)["entries"]:
            for forbidden in ("scope_kind", "scope_id", "discipline", "project_scope"):
                with self.subTest(entry=entry["entry_index"], key=forbidden):
                    self.assertNotIn(forbidden, entry)

    def test_the_module_reads_no_image_and_reaches_no_network(self):
        names = _referenced_names("legend_slicing.py")
        for forbidden in ("open", "Image", "fitz", "pymupdf", "requests",
                          "urlopen", "httpx", "socket", "post", "get_pixmap",
                          "snapshot_region", "create_derived_view"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_slicing_is_pure_and_writes_nothing(self):
        lines = _one_column()
        before = [dict(line) for line in lines]
        ls.slice_candidate(_candidate_for(lines), lines)
        self.assertEqual(lines, before, "the input lines must not be mutated")


class TheWorker(unittest.TestCase):
    """Slicing runs in the existing worker, and never fails an examination."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_legend_slice_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _reading(self, lines):
        return {
            "ran": True, "status": "readable", "engine": "tesseract",
            "engine_version": "5.0.0", "reason": None,
            "orientation": {"authority": "stored_pixels", "changed": False},
            "text": "LEGEND", "lines": lines, "line_count": len(lines),
            "word_count": len(lines) * 2, "dropped_line_count": 0,
            "truncated": False, "confidence_available": False,
            "frame": {"normalised_size": [400, 300],
                      "ocr_frame_size": [300.0, 225.0],
                      "px_per_ocr_unit": [4 / 3, 4 / 3], "render_dpi": 200,
                      "coordinate_space": "fraction_of_normalised_frame"},
        }

    def _run(self, lines, project_name="Legend Slice Job"):
        from services import perception_jobs, perception_worker

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="sheet.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name=project_name)
        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        with patch("services.image_intake.extract_image_positioned_text",
                   lambda *a, **kw: self._reading(lines)):
            record = perception_worker.run_one(self.app, jobs, "test-worker")
        return document, record

    def _entries(self, document):
        workspace = self.store.get(document.project_id)
        regions = {r["id"]: r for r in workspace.addressable_regions}
        found = [(e, regions.get(e.get("region_id")))
                 for e in workspace.evidence_items
                 if e.get("content_type") == ls.ENTRY_CONTENT_TYPE]
        found.sort(key=lambda pair: pair[1]["address"]["entry_index"])
        return found

    def _source_snapshot(self, document):
        source = self.store.get(document.project_id).sources[0]
        return (source.get("file_path"), source.get("sha256"),
                source.get("name"), source.get("removed_at"))

    def test_a_sliced_legend_stores_one_child_region_per_entry(self):
        document, record = self._run(_one_column())
        self.assertEqual(record["state"], "completed")
        found = self._entries(document)
        self.assertEqual(len(found), 5)

    def test_each_entry_hangs_off_its_parent_candidate_region(self):
        document, _record = self._run(_one_column())
        workspace = self.store.get(document.project_id)
        parents = {r["id"] for r in workspace.addressable_regions
                   if (r.get("address") or {}).get("detection")
                   == ld.CANDIDATE_CONTENT_TYPE}
        self.assertEqual(len(parents), 1)
        for _evidence, region in self._entries(document):
            with self.subTest(region=region["id"]):
                self.assertIn(region["parent_region_id"], parents)

    def test_order_is_stored_not_left_to_be_derived_later(self):
        document, _record = self._run(_one_column())
        stored = [region["address"]["entry_index"]
                  for _evidence, region in self._entries(document)]
        self.assertEqual(stored, [0, 1, 2, 3, 4])

    def test_the_stored_entry_carries_observed_text_never_a_meaning(self):
        document, _record = self._run(_one_column())
        for evidence, region in self._entries(document):
            with self.subTest(region=region["id"]):
                self.assertTrue(evidence["content"])
                self.assertEqual(region["address"]["status"], "candidate_only")
                self.assertNotIn("meaning", region["address"])
                self.assertNotIn("proposed_meaning", region["address"])

    def test_no_legend_item_is_created_by_a_run_that_slices(self):
        document, _record = self._run(_one_column())
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.legend_items, [],
                         "slicing must create no governed LegendItem")

    def test_the_source_is_untouched_by_slicing(self):
        document, _record = self._run(_one_column())
        before = self._source_snapshot(document)
        document2, _record2 = self._run(_one_column(), project_name="Second")
        self.assertEqual(self._source_snapshot(document), before)
        self.assertTrue(self._entries(document2))

    def test_a_sheet_with_no_candidate_stores_no_entries(self):
        document, record = self._run(
            [_line("FLOOR PLAN", 0.1, 0.1), _line("SCALE 1:100", 0.1, 0.9)])
        self.assertEqual(record["state"], "completed")
        self.assertEqual(self._entries(document), [])

    def test_slicing_raising_does_not_fail_the_examination(self):
        def boom(*_a, **_kw):
            raise RuntimeError("slicer exploded")

        with patch.object(ls, "slice_candidate", boom):
            document, record = self._run(_one_column())
        self.assertEqual(record["state"], "completed")
        self.assertEqual(self._entries(document), [])

    def test_a_replayed_job_does_not_attach_entries_twice(self):
        from services import perception_jobs, perception_worker

        document, _record = self._run(_one_column())
        first = len(self._entries(document))
        workspace = self.store.get(document.project_id)
        job = {"workspace_id": document.project_id,
               "source_id": workspace.sources[0]["id"]}
        detection = {"candidates": [dict(_candidate_for(_one_column()),
                                         stored_region_id="whatever")]}
        with self.app.app_context():
            perception_worker._slice_legend_candidates(
                self.store, job, detection,
                {"lines": _one_column()}, None)
        self.assertEqual(len(self._entries(document)), first)

    def test_the_run_records_what_it_proposed_in_the_governance_log(self):
        document, _record = self._run(_one_column())
        log = Path(self.tmp) / ("%s.governance.jsonl" % document.project_id)
        body = log.read_text(encoding="utf-8")
        self.assertIn("legend_entries_proposed", body)


class AuthorityCarryThrough(unittest.TestCase):
    """The containment that landed in `88059bb` must be exactly as it was."""

    def test_slicing_reaches_no_decision_route_or_authority_helper(self):
        names = _referenced_names("legend_slicing.py")
        for forbidden in ("decide_legend_item_route", "decide_legend_family_route",
                          "_require_legend_decision_authority",
                          "user_can_record_registered_understanding"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_the_worker_slicer_creates_no_legend_item_either(self):
        """The worker is where a shortcut would actually be taken, so its own
        slicing function is read rather than assumed innocent by association."""
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8"))
        target = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_slice_legend_candidates")
        called = set()
        for child in ast.walk(target):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        for forbidden in ("propose_legend_item", "decide_legend_item",
                          "decide_proposition", "confirm_family",
                          "apply_family_decision", "register_family",
                          "inherit_proposition", "inherit_group_understanding",
                          "resolve_meaning"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)
        self.assertIn("create_addressable_region", called)
        self.assertIn("register_evidence_item", called)

    def test_the_registration_gate_still_stands_untouched(self):
        routes = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertEqual(routes.count("\ndef _require_legend_decision_authority("), 1)
        self.assertEqual(routes.count("_require_legend_decision_authority(scope_kind)"), 2)

    def test_slicing_added_no_route_of_its_own(self):
        """A customer-visible proposal is not authorization, and a new surface
        offering these slices would be a new decision path nobody gated."""
        for path in sorted((_REPO_ROOT / "routes").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(module=path.name):
                self.assertNotIn(ls.ENTRY_CONTENT_TYPE, source)
                self.assertNotIn("legend_slicing", source)


class ZeroImageEgress(unittest.TestCase):
    """Slicing added no path off this machine, and no new image file."""

    def test_the_worker_slicer_writes_no_standalone_image(self):
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        window = source[source.index("def _slice_legend_candidates"):]
        window = window[:window.index("\ndef ", 10)]
        for forbidden in ("snapshot_region", "create_derived_view", ".save(",
                          "open(", "write_bytes", "Image."):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, window)

    def test_a_slice_stays_reconstructable_from_source_page_and_bbox(self):
        """No crop file is written BECAUSE none is needed: the parent region
        names the page, the entry names the box, and the source is untouched."""
        lines = _one_column()
        candidate = _candidate_for(lines)
        for entry in ls.slice_candidate(candidate, lines)["entries"]:
            with self.subTest(entry=entry["entry_index"]):
                box = entry["region"]
                self.assertEqual(
                    sorted(box.keys()), ["height", "width", "x", "y"])
                for value in box.values():
                    self.assertIsInstance(value, float)


if __name__ == "__main__":
    unittest.main()
