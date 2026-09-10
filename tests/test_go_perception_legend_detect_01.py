"""CLAUDE-GO-PERCEPTION-LEGEND-DETECT-01: WHERE is the legend block?

`find_legend_evidence` answers "does this project explain its own drawing
language" from text markers alone - a source name, a page label, an observed
string. It cannot say where the legend sits, and it cannot tell a legend from a
note that mentions one. Positioned OCR now makes both answerable.

What these tests defend, in the order the mistakes would be made:

1. **A word is not a legend.** The single most likely failure is accepting
   "REFER TO THE LEGEND ON SHEET A-01" because it contains the marker.
   `FalsePositives` is the largest class here on purpose.

2. **A candidate is not a finding.** Detection evidence must never become a
   LegendItem, a meaning, or an input to `resolve_meaning`'s precedence.
   `ProposalOnly` pins that, including by reading the source for the calls it
   must not contain.

3. **Nothing is invented when the evidence is thin.** Poor OCR, one row, or an
   unreadable heading must produce no candidate or an ambiguous one - never a
   confident region over nothing.

Geometry is expressed the way the perception layer stores it: 0-1 fractions of
the orientation-normalized frame. Nothing here needs Tesseract or a network.
"""
from __future__ import annotations

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
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, EVIDENCE_CLASS_EXTRACTED,
)
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


def _line(text, x, y, width=0.10, height=0.01):
    return {"x": x, "y": y, "width": width, "height": height, "text": text}


def _legend_block(heading="LEGEND", *, x=0.10, y=0.20, rows=8, gap=0.015,
                  height=0.01, label="FD-%d FIRE DAMPER"):
    """A heading with a list beneath it, on a believable rhythm."""
    lines = [_line(heading, x, y, 0.06, height * 1.5)]
    for i in range(rows):
        lines.append(_line(label % (i + 1), x + 0.005,
                           y + height * 1.5 + gap * (i + 1), 0.12, height))
    return lines


def _referenced_names(module_filename):
    """Every name and attribute the module actually references.

    Reading the source as TEXT would fail on this module's own docstring, which
    names `resolve_meaning` precisely to say it is not entered. A test that
    forbids a WORD rather than a MECHANISM catches the explanation instead of
    the behaviour - a mistake this repository has made before.
    """
    import ast

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


class HeadingShape(unittest.TestCase):
    """A marker match is the FIRST signal, never the whole answer."""

    def test_a_bare_marker_is_heading_shaped(self):
        found = ld.heading_candidates([_line("LEGEND", 0.1, 0.2)])
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["is_heading_shaped"])
        self.assertEqual(found[0]["marker_kind"], "legend")

    def test_a_real_two_word_heading_is_heading_shaped(self):
        """Measured on a real sheet: 'CIRCULATION LEGEND'."""
        found = ld.heading_candidates([_line("CIRCULATION LEGEND", 0.8, 0.2)])
        self.assertTrue(found[0]["is_heading_shaped"])

    def test_a_sentence_mentioning_a_legend_is_not_heading_shaped(self):
        found = ld.heading_candidates(
            [_line("REFER TO THE LEGEND ON SHEET A-01 FOR SYMBOL MEANINGS", 0.1, 0.5)])
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["is_heading_shaped"])
        self.assertIn("prose", found[0]["reason"])

    def test_a_line_with_no_marker_is_not_a_heading(self):
        self.assertEqual(ld.heading_candidates([_line("ROOM SCHEDULE", 0.1, 0.2)]), [])

    def test_the_marker_vocabulary_is_the_existing_one_not_a_copy(self):
        """Two vocabularies would drift into disagreeing about what a legend is."""
        source = (_REPO_ROOT / "services" / "legend_detection.py").read_text(
            encoding="utf-8")
        self.assertIn("_matches_legend_marker", source)
        self.assertNotIn("LEGEND_EVIDENCE_MARKERS = (", source,
                         "the marker list must be imported, never re-declared")

    def test_the_existing_governed_markers_are_all_reachable(self):
        from services import legend_of_understanding as lou

        for phrase, _kind in lou.LEGEND_EVIDENCE_MARKERS:
            with self.subTest(phrase=phrase):
                found = ld.heading_candidates([_line(phrase.upper(), 0.1, 0.2)])
                self.assertTrue(found, "%r announced nothing" % phrase)


class ClearLegend(unittest.TestCase):
    """The case this exists to find."""

    def setUp(self):
        self.result = ld.detect_candidates(_legend_block(), source_id="s1",
                                           structural_unit_id="u1")

    def test_a_heading_over_a_list_is_a_candidate(self):
        self.assertEqual(self.result["outcome"], ld.OUTCOME_CANDIDATES)
        self.assertEqual(len(self.result["candidates"]), 1)

    def test_the_candidate_is_supported_not_merely_present(self):
        self.assertEqual(self.result["candidates"][0]["strength"],
                         ld.STRENGTH_SUPPORTED)

    def test_the_region_encloses_the_heading_and_its_rows(self):
        candidate = self.result["candidates"][0]
        region = candidate["region"]
        self.assertLessEqual(region["y"], candidate["heading"]["y"] + 1e-9)
        self.assertGreater(region["height"], candidate["heading"]["height"])

    def test_the_region_is_a_normalized_fraction_inside_the_frame(self):
        region = self.result["candidates"][0]["region"]
        self.assertGreaterEqual(region["x"], 0.0)
        self.assertGreaterEqual(region["y"], 0.0)
        self.assertLessEqual(region["x"] + region["width"], 1.0 + 1e-9)
        self.assertLessEqual(region["y"] + region["height"], 1.0 + 1e-9)
        self.assertGreater(region["width"], 0)
        self.assertGreater(region["height"], 0)

    def test_it_carries_the_identity_the_brief_requires(self):
        candidate = self.result["candidates"][0]
        for key in ("source_id", "structural_unit_id", "region", "heading",
                    "spatial_support", "detection_method", "detection_version",
                    "strength", "reason", "status"):
            with self.subTest(key=key):
                self.assertIn(key, candidate)
        self.assertEqual(candidate["source_id"], "s1")
        self.assertEqual(candidate["structural_unit_id"], "u1")

    def test_the_supporting_evidence_is_reported_not_just_the_verdict(self):
        support = self.result["candidates"][0]["spatial_support"]
        self.assertGreaterEqual(support["row_count"], ld.MIN_SUPPORTED_ROWS)
        self.assertIn("stop_reason", support)
        self.assertIn("short_label_count", support)

    def test_no_probability_is_invented(self):
        candidate = self.result["candidates"][0]
        self.assertNotIn("confidence", candidate)
        self.assertNotIn("probability", candidate)
        self.assertIn(candidate["strength"],
                      (ld.STRENGTH_SUPPORTED, ld.STRENGTH_AMBIGUOUS,
                       ld.STRENGTH_UNSUPPORTED))


class LayoutVariants(unittest.TestCase):
    """A legend sits below its title, or beside it."""

    def test_a_legend_below_its_heading_is_found(self):
        result = ld.detect_candidates(_legend_block())
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["layout"], "below")

    def test_a_legend_beside_its_heading_is_found(self):
        """BESIDE is a FALLBACK, consulted only when nothing sits below.

        Not a preference - a measurement. Every real legend available sits
        below its heading, and on dense CAD sheets the horizontal band beside a
        heading is crowded with small OCR fragments: taking whichever side had
        more rows gave a real A-01 a 159-row "legend" across half the sheet.
        The larger side is the denser one, not the better one.
        """
        lines = [_line("LEGEND", 0.10, 0.30, 0.06, 0.015)]
        for i in range(6):
            lines.append(_line("SD-%d SMOKE DETECTOR" % i, 0.20 + 0.001 * i,
                               0.30 + 0.002 * i, 0.15, 0.01))
        result = ld.detect_candidates(lines)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["layout"], "beside")

    def test_a_crowded_row_beside_a_heading_cannot_outvote_a_real_column(self):
        """The A-01 failure, pinned so it cannot come back."""
        lines = _legend_block("LEGEND", x=0.10, y=0.30, rows=6)
        heading = lines[0]
        # a dense band of fragments on the heading's own line
        for i in range(40):
            lines.append(_line("F%d" % i, 0.20 + 0.015 * i, heading["y"],
                               0.012, 0.008))
        result = ld.detect_candidates(lines)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["layout"], "below",
                         "a crowded horizontal band beat the real column")
        self.assertLessEqual(result["candidates"][0]["region"]["width"], 0.30)

    def test_a_list_exactly_on_the_rhythm_boundary_is_not_cut_short(self):
        """Rows one line-height apart are ORDINARY drafting, not an edge case.

        Without slack in the comparison, 0.35 - 0.33 evaluates to
        0.020000000000000018 and loses to 0.01 * 2.0, so a perfectly regular
        six-row list ended after one row and a crowded band beside the heading
        won the layout instead. The existing fixture happened to sit just
        inside the boundary and passed while the rule was fragile - this sits
        exactly ON it.
        """
        lines = [_line("LEGEND", 0.10, 0.30, 0.06, 0.015)]
        for i in range(6):
            lines.append(_line("FD-%d DAMPER" % i, 0.105, 0.33 + 0.02 * i,
                               0.12, 0.01))
        result = ld.detect_candidates(lines)
        self.assertEqual(len(result["candidates"]), 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["spatial_support"]["row_count"], 6)
        self.assertEqual(candidate["strength"], ld.STRENGTH_SUPPORTED)

    def test_the_layout_that_supported_the_candidate_is_recorded(self):
        result = ld.detect_candidates(_legend_block())
        support = result["candidates"][0]["spatial_support"]
        self.assertIn("rows_below", support)
        self.assertIn("rows_beside", support)


class MultipleAndNone(unittest.TestCase):
    """Zero, one, or several - and zero is a real answer."""

    def test_two_legend_blocks_on_one_sheet_are_both_found(self):
        lines = (_legend_block("LEGEND", x=0.05, y=0.10)
                 + _legend_block("ABBREVIATIONS", x=0.55, y=0.10,
                                 label="AFF-%d ABOVE FLOOR"))
        result = ld.detect_candidates(lines)
        self.assertEqual(len(result["candidates"]), 2)
        kinds = {c["heading"]["marker_kind"] for c in result["candidates"]}
        self.assertEqual(kinds, {"legend", "abbreviations"})

    def test_a_sheet_with_no_legend_yields_no_candidate(self):
        lines = [_line("FLOOR PLAN", 0.1, 0.1), _line("SCALE 1:100", 0.1, 0.9)]
        result = ld.detect_candidates(lines)
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["outcome"], ld.OUTCOME_NO_HEADING)

    def test_no_positioned_text_is_its_own_outcome(self):
        result = ld.detect_candidates([])
        self.assertEqual(result["outcome"], ld.OUTCOME_NO_LINES)
        self.assertEqual(result["candidates"], [])

    def test_a_legend_is_never_manufactured_because_sheets_usually_have_one(self):
        """The refusal find_legend_evidence already states, held here too."""
        result = ld.detect_candidates([_line("DRAWING TITLE", 0.1, 0.1)])
        self.assertEqual(result["candidates"], [])


class FalsePositives(unittest.TestCase):
    """Heading plus structure - marker text alone must never be enough."""

    def test_a_general_note_mentioning_a_legend_is_rejected(self):
        lines = [_line("3. REFER TO THE LEGEND ON SHEET A-01 FOR ALL SYMBOLS",
                       0.1, 0.4, 0.5, 0.01)]
        for i in range(8):
            lines.append(_line("%d. GENERAL NOTE TEXT CONTINUES HERE AT LENGTH"
                               % (i + 4), 0.1, 0.42 + 0.015 * i, 0.5, 0.01))
        result = ld.detect_candidates(lines)
        self.assertEqual(result["candidates"], [],
                         "a sentence in the general notes became a legend")
        self.assertTrue(result["rejected"])

    def test_a_lone_heading_with_nothing_under_it_is_rejected(self):
        result = ld.detect_candidates([_line("LEGEND", 0.1, 0.2, 0.06, 0.015),
                                       _line("SOMETHING FAR AWAY", 0.1, 0.95)])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["outcome"], ld.OUTCOME_NO_SUPPORT)
        self.assertIn("row", result["rejected"][0]["reason"])

    def test_a_title_block_line_is_not_a_legend(self):
        lines = [_line("DRAWING LEGEND AND GENERAL ARRANGEMENT NOTES SHEET",
                       0.7, 0.9, 0.28, 0.01)]
        result = ld.detect_candidates(lines)
        self.assertEqual(result["candidates"], [])

    def test_a_rejection_records_why(self):
        result = ld.detect_candidates([_line("LEGEND", 0.1, 0.2, 0.06, 0.015)])
        self.assertTrue(result["rejected"])
        self.assertTrue(result["rejected"][0]["reason"])

    def test_prose_under_a_heading_is_ambiguous_not_supported(self):
        """Structure without short labels is a place to look, not a finding."""
        lines = [_line("LEGEND", 0.1, 0.2, 0.06, 0.015)]
        for i in range(6):
            lines.append(_line(
                "THIS ROW IS A LONG SENTENCE OF PROSE NOT A SHORT LABEL AT ALL %d" % i,
                0.1, 0.23 + 0.012 * i, 0.6, 0.01))
        result = ld.detect_candidates(lines)
        if result["candidates"]:
            self.assertEqual(result["candidates"][0]["strength"],
                             ld.STRENGTH_AMBIGUOUS)


class Degradation(unittest.TestCase):
    """Uncertainty must not become a false region."""

    def test_poor_ocr_that_recovers_nothing_yields_no_candidate(self):
        result = ld.detect_candidates([])
        self.assertEqual(result["candidates"], [])

    def test_an_unreadable_heading_means_no_detection(self):
        """If OCR could not read the word, no legend is inferred from layout."""
        lines = [_line("|_G3ND", 0.1, 0.2, 0.06, 0.015)]
        for i in range(8):
            lines.append(_line("FD-%d" % i, 0.1, 0.23 + 0.012 * i, 0.05, 0.01))
        result = ld.detect_candidates(lines)
        self.assertEqual(result["candidates"], [],
                         "a legend was inferred from appearance alone")

    def test_garbled_rows_do_not_crash_detection(self):
        lines = [_line("LEGEND", 0.1, 0.2, 0.06, 0.015)]
        lines += [_line("", 0.1, 0.23), {"x": 0.1, "y": 0.25}]
        result = ld.detect_candidates(lines)
        self.assertIsInstance(result["candidates"], list)

    def test_a_zero_height_heading_does_not_divide_by_zero(self):
        lines = [{"x": 0.1, "y": 0.2, "width": 0.06, "height": 0.0, "text": "LEGEND"}]
        lines += [_line("FD-%d" % i, 0.1, 0.22 + 0.01 * i) for i in range(6)]
        result = ld.detect_candidates(lines)
        self.assertIsInstance(result["candidates"], list)


class BoundsAreAlwaysValid(unittest.TestCase):
    """A region that leaves the frame is not an address."""

    def test_rows_near_the_frame_edge_stay_inside_it(self):
        lines = [_line("LEGEND", 0.90, 0.90, 0.09, 0.01)]
        for i in range(5):
            lines.append(_line("X-%d" % i, 0.92, 0.92 + 0.012 * i, 0.07, 0.01))
        result = ld.detect_candidates(lines)
        for candidate in result["candidates"]:
            region = candidate["region"]
            with self.subTest(region=region):
                self.assertLessEqual(region["x"] + region["width"], 1.0 + 1e-9)
                self.assertLessEqual(region["y"] + region["height"], 1.0 + 1e-9)


class ProposalOnly(unittest.TestCase):
    """Detection evidence is not a finding, and must not become one here."""

    def test_the_candidate_says_so_in_the_record(self):
        result = ld.detect_candidates(_legend_block())
        self.assertEqual(result["candidates"][0]["status"], "candidate_only")

    def test_no_legend_item_is_created_anywhere_in_this_module(self):
        names = _referenced_names("legend_detection.py")
        for forbidden in ("propose_legend_item", "decide_legend_item",
                          "LegendItem", "register_family", "confirm_family",
                          "apply_family_decision", "inherit_proposition"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_no_meaning_is_assigned(self):
        result = ld.detect_candidates(_legend_block())
        candidate = result["candidates"][0]
        for forbidden in ("meaning", "proposed_meaning", "proposed_kind",
                          "symbol", "signifies"):
            with self.subTest(key=forbidden):
                self.assertNotIn(forbidden, candidate)

    def test_it_never_enters_the_meaning_precedence(self):
        """Checked as a MECHANISM, not as a forbidden word."""
        names = _referenced_names("legend_detection.py")
        for forbidden in ("resolve_meaning", "effective_meaning",
                          "LEGEND_PRECEDENCE_ORDER", "effective_evidence_tier",
                          "propose_legend_item", "decide_legend_item"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)

    def test_legend_of_understanding_is_unchanged_by_this_tranche(self):
        """The existing system is fed, never redesigned."""
        source = (_REPO_ROOT / "services" / "legend_of_understanding.py").read_text(
            encoding="utf-8")
        self.assertNotIn("legend_detection", source,
                         "the existing module must not depend on the new one")


class ZeroImageEgress(unittest.TestCase):
    """Detection reads geometry and text. It never touches an image."""

    def test_the_module_opens_no_image_and_reaches_no_provider(self):
        names = _referenced_names("legend_detection.py")
        for forbidden in ("llm_gateway", "anthropic", "Anthropic", "gemini",
                          "requests", "urllib", "httpx", "image_base64",
                          "PIL", "Image", "pymupdf", "fitz", "open",
                          "subprocess", "socket"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, names)


class ReadingBackFromTheStore(unittest.TestCase):
    """Detection can run over a Source perceived earlier, without re-reading it."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_legend_detect_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="sheet.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Legend Sheet")
        workspace = self.store.get(self.document.project_id)
        self.first = workspace.sources[0]["id"]
        self.unit_one = self.store.register_pdf_page_structure(
            workspace, source_id=self.first, pages=["x"], actor="test",
        )["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _store_lines(self, source_id, unit_id, lines):
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=source_id, structural_unit_id=unit_id,
            lines=lines, actor="perception-worker")

    def test_stored_positioned_lines_are_read_back_in_fraction_space(self):
        self._store_lines(self.first, self.unit_one, _legend_block())
        workspace = self.store.get(self.document.project_id)
        lines = ld.lines_from_workspace(workspace, self.first)
        self.assertTrue(lines)
        for line in lines:
            for key in ("x", "y", "width", "height", "text"):
                self.assertIn(key, line)
        result = ld.detect_candidates(lines, source_id=self.first)
        self.assertEqual(len(result["candidates"]), 1)

    def test_a_second_source_keeps_its_own_lines(self):
        second = self.store.add_source(
            self.store.get(self.document.project_id), name="two.png",
            file_path="", kind="image", actor="test")["id"]
        workspace = self.store.get(self.document.project_id)
        unit_two = self.store.register_pdf_page_structure(
            workspace, source_id=second, pages=["y"], actor="test",
        )["structural_unit_ids"][0]

        self._store_lines(self.first, self.unit_one, _legend_block("LEGEND"))
        self._store_lines(second, unit_two, _legend_block("ABBREVIATIONS"))

        workspace = self.store.get(self.document.project_id)
        first_lines = ld.lines_from_workspace(workspace, self.first)
        second_lines = ld.lines_from_workspace(workspace, second)
        self.assertTrue(any("LEGEND" in l["text"] for l in first_lines))
        self.assertFalse(any("ABBREVIATIONS" in l["text"] for l in first_lines),
                         "a line crossed a Source boundary")
        self.assertTrue(any("ABBREVIATIONS" in l["text"] for l in second_lines))

    def test_plain_text_evidence_is_not_mistaken_for_positioned_lines(self):
        workspace = self.store.get(self.document.project_id)
        self.store.register_pdf_page_structure(
            workspace, source_id=self.first,
            pages=["LEGEND\n\nsome ordinary paragraph text"], actor="test",
            evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED})
        workspace = self.store.get(self.document.project_id)
        self.assertEqual(ld.lines_from_workspace(workspace, self.first), [])


class TheWorker(unittest.TestCase):
    """Detection runs in the perception worker, and never fails an examination."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_legend_worker_"))
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

    def _run(self, lines, project_name="Legend Worker Job"):
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
        return document, jobs, record

    def _candidates(self, document):
        workspace = self.store.get(document.project_id)
        regions = {r["id"]: r for r in workspace.addressable_regions}
        return [(e, regions.get(e.get("region_id")))
                for e in workspace.evidence_items
                if e.get("content_type") == ld.CANDIDATE_CONTENT_TYPE]

    def test_a_sheet_with_a_legend_stores_a_candidate_region(self):
        document, jobs, record = self._run(_legend_block())
        self.assertEqual(record["state"], "completed")
        found = self._candidates(document)
        self.assertEqual(len(found), 1)
        evidence, region = found[0]
        self.assertEqual(evidence["content"], "LEGEND")
        self.assertEqual(region["address"]["detection"], ld.CANDIDATE_CONTENT_TYPE)
        self.assertEqual(region["address"]["status"], "candidate_only")

    def test_the_stored_region_is_a_fraction_inside_the_frame(self):
        document, jobs, record = self._run(_legend_block())
        _evidence, region = self._candidates(document)[0]
        address = region["address"]
        self.assertGreaterEqual(address["x"], 0.0)
        self.assertLessEqual(address["x"] + address["width"], 1.0 + 1e-9)
        self.assertLessEqual(address["y"] + address["height"], 1.0 + 1e-9)

    def test_a_sheet_with_no_legend_stores_nothing(self):
        document, jobs, record = self._run(
            [_line("FLOOR PLAN", 0.1, 0.1), _line("SCALE 1:100", 0.1, 0.9)])
        self.assertEqual(record["state"], "completed")
        self.assertEqual(self._candidates(document), [])

    def test_the_examination_still_completes_when_detection_finds_nothing(self):
        document, jobs, record = self._run([_line("PLAN", 0.1, 0.1)])
        self.assertEqual(record["state"], "completed")
        workspace = self.store.get(document.project_id)
        self.assertTrue([e for e in workspace.evidence_items
                         if e["content_type"] == "text"])

    def test_detection_raising_does_not_fail_the_examination(self):
        from services import legend_detection

        def boom(*_a, **_kw):
            raise RuntimeError("detector exploded")

        with patch.object(legend_detection, "detect_candidates", boom):
            document, jobs, record = self._run(_legend_block())
        self.assertEqual(record["state"], "completed")
        self.assertEqual(self._candidates(document), [])

    def test_positioned_text_is_unaffected_by_detection(self):
        document, jobs, record = self._run(_legend_block())
        workspace = self.store.get(document.project_id)
        positioned = [e for e in workspace.evidence_items
                      if e["content_type"] == "positioned_text"]
        self.assertTrue(positioned)

    def test_no_legend_item_is_ever_created_by_the_worker_path(self):
        document, jobs, record = self._run(_legend_block())
        workspace = self.store.get(document.project_id)
        self.assertEqual(getattr(workspace, "legend_items", []), [],
                         "detection registered meaning")

    def test_the_customer_result_does_not_show_candidates(self):
        """A candidate is engineering evidence, not a customer-facing finding.

        Asserted by COUNT rather than by looking for the word: the sheet's own
        recovered text may legitimately contain "LEGEND", and a test that
        searched for it would be catching the drawing rather than the leak.
        """
        from services import document_examination

        document, jobs, record = self._run(_legend_block())
        workspace = self.store.get(document.project_id)
        source_id = workspace.sources[0]["id"]
        recovered = document_examination._recovered(workspace, source_id)
        plain = [e for e in workspace.evidence_items
                 if e["content_type"] == "text" and e["source_id"] == source_id]
        self.assertTrue(self._candidates(document), "nothing was detected to leak")
        self.assertEqual(recovered["passage_count"], len(plain),
                         "a legend candidate reached the customer's result")

    def test_detection_is_recorded_even_when_nothing_is_found(self):
        """How often sheets fail to explain themselves is a real question."""
        document, jobs, record = self._run([_line("PLAN", 0.1, 0.1)])
        log = Path(self.tmp) / ("%s.governance.jsonl" % document.project_id)
        self.assertTrue(log.exists())
        self.assertIn("legend_candidates_detected", log.read_text(encoding="utf-8"))

    def test_a_replay_does_not_duplicate_candidates(self):
        from services import perception_jobs, perception_worker

        document, jobs, record = self._run(_legend_block())
        source_id = self.store.get(document.project_id).sources[0]["id"]
        jobs.enqueue(workspace_id=document.project_id, source_id=source_id,
                     source_name="sheet.png", source_sha256="x" * 64)
        with patch("services.image_intake.extract_image_positioned_text",
                   lambda *a, **kw: self._reading(_legend_block())):
            perception_worker.run_one(self.app, jobs, "test-worker")
        self.assertEqual(len(self._candidates(document)), 1)

    def test_detection_runs_in_the_worker_not_the_request(self):
        for path in ("ingestion.py",):
            source = (_REPO_ROOT / "services" / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("legend_detection", source)
        routes = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        self.assertNotIn("legend_detection", routes)


if __name__ == "__main__":
    unittest.main()
