"""CLAUDE-DETAIL-CALLOUT-01: the first relationship family the corpus earned.

Two tranches of reconnaissance chose this family and retired the alternative.
Grid identity was measured and rejected - architectural grid labels are not
recoverable (two OCR reads of the SAME sheet share a count on 2 of 11 letters)
and the structural grid vocabulary is not discriminative (six of eight sheets
carry an identical `A`-`M`). Declared detail callouts, measured in the same
pass, resolved completely.

What these tests defend, in the order the mistakes would be made:

1. **POSITION IS THE RULE, NOT TEXT ORDER.** `1` followed by `RS505` in reading
   order is not a callout; `1` and `RS505` sharing one split bubble is. The
   difference is measurable and it matters: the scale note `1 : 50` beside a
   title block reads as `50`+`RS501` in text order and is a plausible false
   reference. `TextAdjacencyIsNotEnough` is the largest class here because it
   is the whole justification for the tranche.

2. **A SHEET DOES NOT CITE ITSELF.** The geometry legitimately admits a sheet's
   own number beside its own identity in the title block. Every one of those is
   a self-reference and all of them are refused.

3. **ABSTENTION OVER A PLAUSIBLE FALSE REFERENCE.** A token naming no Source is
   not proposed at all; an ambiguous target is never chosen between; a removed
   Source is not an active target.

4. **NO NEW MEANING.** A declared reference is not a shared location, a
   discrepancy, or a dimensional conflict. Nothing here emits a Relationship or
   a Claim, and no physical magnitude is derived from page geometry.
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

from services import detail_callout, perception_worker, positioned_text
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, REFERENCE_TYPE_DETAIL_CALLOUT,
    RESOLUTION_STATUS_RESOLVED_EXACT, RESOLUTION_STATUS_RESOLVED_MULTIPLE,
    CaseWorkspaceStore,
)
from services.ingestion import attach_document_shop_sources, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: The measured real bubble: target 0.25-0.27 heights right of its number,
#: -0.04..-0.02 down, standard deviation 0.004 and 0.003 over ten real sheets.
REAL_DX = 0.26
REAL_DY = -0.03
TARGET_H = 0.02


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _line(text, x, y, *, height=TARGET_H, width=0.01):
    return {"text": text, "x": x, "y": y, "width": width, "height": height,
            "extraction_pass": positioned_text.PASS_NATIVE}


def _bubble(number, token, x=0.30, y=0.50):
    """One split bubble at the REAL measured offset: number left, token right."""
    num = _line(number, x, y, height=TARGET_H * 0.3, width=0.004)
    ncx, ncy = num["x"] + num["width"] / 2, num["y"] + num["height"] / 2
    tcx = ncx + REAL_DX * TARGET_H
    tcy = ncy + REAL_DY * TARGET_H
    tgt = _line(token, tcx - 0.005, tcy - TARGET_H / 2, height=TARGET_H, width=0.01)
    return [num, tgt]


class TheRule(unittest.TestCase):
    """The positional envelope, tested directly."""

    def _page(self, lines):
        return {"unit": {"id": "u1", "label": "Page 1", "order_index": 0},
                "lines": lines}

    def test_a_real_split_bubble_is_a_callout(self):
        page = self._page(_bubble("1", "RS505"))
        found = detail_callout.callout_candidates(page, {"RS505"})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["detail_number"], "1")
        self.assertEqual(found[0]["sheet_token"], "RS505")
        self.assertEqual(found[0]["reference_text"], "1 RS505")

    def test_the_envelope_matches_what_was_measured(self):
        """Guards the constants against a silent later widening."""
        self.assertLess(detail_callout.DX_MIN, 0.25)
        self.assertGreater(detail_callout.DX_MAX, 0.27)
        self.assertGreater(detail_callout.DY_MAX, 0.04)
        # And is not so wide it stops discriminating.
        self.assertLess(detail_callout.DX_MAX, 1.0)
        self.assertLess(detail_callout.DY_MAX, 0.3)

    def test_a_four_digit_token_is_not_a_detail_number(self):
        num, tgt = _bubble("1", "RS505")
        num["text"] = "1850"
        self.assertEqual(
            detail_callout.callout_candidates(self._page([num, tgt]), {"RS505"}), [])

    def test_a_zero_height_target_cannot_be_measured_against(self):
        num, tgt = _bubble("1", "RS505")
        tgt["height"] = 0.0
        self.assertIsNone(detail_callout.positional_basis(num, tgt))


class TextAdjacencyIsNotEnough(unittest.TestCase):
    """The finding that justified the whole tranche."""

    def _page(self, lines):
        return {"unit": {"id": "u1", "label": "Page 1", "order_index": 0},
                "lines": lines}

    def test_tokens_adjacent_in_reading_order_but_far_apart_are_refused(self):
        lines = [_line("1", 0.10, 0.10, height=TARGET_H * 0.3),
                 _line("RS505", 0.80, 0.90)]
        self.assertEqual(
            detail_callout.callout_candidates(self._page(lines), {"RS505"}), [])

    def test_the_scale_note_false_positive_is_refused(self):
        """`1 : 50` beside a title block - a real false pair from the corpus.

        It is STACKED rather than side by side, which is exactly the difference
        the envelope encodes.
        """
        num = _line("50", 0.60, 0.50, height=TARGET_H * 0.3, width=0.006)
        ncx = num["x"] + num["width"] / 2
        ncy = num["y"] + num["height"] / 2
        tgt = _line("RS501", ncx - 0.005, ncy + TARGET_H * 1.26, height=TARGET_H)
        self.assertEqual(
            detail_callout.callout_candidates(self._page([num, tgt]), {"RS501"}), [])

    def test_a_token_directly_left_of_the_number_is_refused(self):
        """Direction matters: the sheet token sits RIGHT of its number."""
        num = _line("1", 0.50, 0.50, height=TARGET_H * 0.3, width=0.004)
        ncx = num["x"] + num["width"] / 2
        ncy = num["y"] + num["height"] / 2
        tgt = _line("RS505", ncx - REAL_DX * TARGET_H - 0.005,
                    ncy - TARGET_H / 2, height=TARGET_H)
        self.assertEqual(
            detail_callout.callout_candidates(self._page([num, tgt]), {"RS505"}), [])

    def test_a_number_on_another_page_cannot_pair(self):
        """Page-bounded, the lesson CLAUDE-SHEET-INDEX-BOUNDARY-01 paid for."""
        num, tgt = _bubble("1", "RS505")
        page_a = self._page([num])
        page_b = self._page([tgt])
        self.assertEqual(detail_callout.callout_candidates(page_a, {"RS505"}), [])
        self.assertEqual(detail_callout.callout_candidates(page_b, {"RS505"}), [])


class Abstention(unittest.TestCase):
    """A plausible false reference is worse than no reference."""

    def _page(self, lines):
        return {"unit": {"id": "u1", "label": "Page 1", "order_index": 0},
                "lines": lines}

    def test_a_token_naming_no_source_is_not_proposed(self):
        page = self._page(_bubble("1", "RS999"))
        self.assertEqual(detail_callout.callout_candidates(page, {"RS505"}), [])

    def test_a_sheet_does_not_cite_itself(self):
        page = self._page(_bubble("2", "RS501"))
        self.assertEqual(len(detail_callout.callout_candidates(page, {"RS501"})), 1)
        self.assertEqual(
            detail_callout.callout_candidates(page, {"RS501"}, self_token="RS501"), [])


class _CorpusCase(unittest.TestCase):
    """A project of real-shaped sheets, perceived through the normal worker."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_callout_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _native(self, plan):
        """Inject one page of NATIVE words per Source, keyed to its own bytes.

        The native path on purpose. A detail number is one character, so the OCR
        path's garbage control drops it - correctly, because a lone glyph from a
        recogniser is usually noise. This family is therefore a NATIVE-TEXT
        capability today, and these tests exercise the path it actually runs on
        rather than one where it cannot work. `NativeOnlyToday` states the limit.
        """
        def reader(pdf_bytes, page_index):
            key = next((k for k in plan if k.encode() in pdf_bytes), None)
            words = plan.get(key, [])
            if not words:
                return None
            result = positioned_text._assemble_positioned(
                words, (1000.0, 1000.0), (0, 0),
                "\n".join(w[4] for w in words),
                engine="pymupdf-native", version="native", dpi=0,
                garbage_control=False)
            for line in result["lines"]:
                line["extraction_pass"] = positioned_text.PASS_NATIVE
            return result
        return reader

    def _words_for_bubble(self, number, token):
        """PyMuPDF word tuples placing one real split bubble on a 1000x1000 page."""
        nh = TARGET_H * 0.3 * 1000
        th = TARGET_H * 1000
        nx0, ny0 = 300.0, 500.0
        ncx, ncy = nx0 + 4.0 / 2, ny0 + nh / 2
        tcx = ncx + REAL_DX * th
        tcy = ncy + REAL_DY * th
        return [
            (nx0, ny0, nx0 + 4.0, ny0 + nh, number, 0, 0, 0),
            (tcx - 5.0, tcy - th / 2, tcx + 5.0, tcy + th / 2, token, 1, 0, 0),
        ]

    def _ingest(self, files):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"engagement"), filename="job.txt"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Detail Callout Corpus")
                workspace = self.store.get(document.project_id)
                attach_document_shop_sources(
                    self.app, workspace,
                    [FileStorage(stream=io.BytesIO(b"%PDF-1.4 " + name.encode()),
                                 filename=name) for name in files],
                    owner="cust")
        self.document = document
        return document

    def _drain(self, plan, limit=30):
        from services import perception_jobs

        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        records = []
        def _no_ocr(frame_bytes, dpi, filetype="png", page_index=0):
            # Nothing in this family may depend on a recogniser running.
            return [], (1000.0, 1000.0), "tesseract", "5.0.0", ""

        with patch.object(positioned_text, "pdf_page_count", lambda _b: 1):
            with patch.object(positioned_text, "_native_positioned_lines",
                              self._native(plan)):
                with patch.object(positioned_text, "_default_ocr", _no_ocr):
                    for _ in range(limit):
                        record = perception_worker.run_one(self.app, jobs, "test")
                        if record is None:
                            break
                        records.append(record)
        return records

    def _workspace(self):
        return self.store.get(self.document.project_id)

    def _callouts(self):
        return [r for r in self._workspace().source_references
                if (r.get("origin_context") or {}).get("origin")
                == detail_callout.CALLOUT_METHOD]


class TheWorkflow(_CorpusCase):
    """Reachability: the family arrives through the normal lifecycle."""

    FILES = ("RS501.pdf", "RS505.pdf")

    def test_a_declared_callout_becomes_a_governed_reference(self):
        self._ingest(self.FILES)
        records = self._drain({"RS501": self._words_for_bubble("1", "RS505"),
                               "RS505": []})
        # The target sheet carries no text in this fixture and so ends
        # needs_attention - "ran, established nothing", which is an honest
        # outcome and deliberately NOT a failure. The citing sheet completes.
        citing = [r for r in records
                  if (r.get("source_name") or "").startswith("RS501")]
        self.assertEqual([r["state"] for r in citing], ["completed"])
        refs = self._callouts()
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["reference_text"], "1 RS505")
        self.assertEqual(refs[0]["reference_type"], REFERENCE_TYPE_DETAIL_CALLOUT)
        self.assertEqual(refs[0]["resolution_status"],
                         RESOLUTION_STATUS_RESOLVED_EXACT)

    def test_it_resolves_to_the_actual_target_source(self):
        self._ingest(self.FILES)
        self._drain({"RS501": self._words_for_bubble("1", "RS505"), "RS505": []})
        workspace = self._workspace()
        target = next(s["id"] for s in workspace.sources if s["name"] == "RS505.pdf")
        self.assertEqual(self._callouts()[0]["resolved_target_ids"], [target])
        # And reads back through the store's existing reverse reader.
        back = self.store.source_references_to_target(workspace, target)
        self.assertEqual([r["id"] for r in back], [self._callouts()[0]["id"]])

    def test_a_sheet_with_no_callouts_registers_nothing(self):
        self._ingest(self.FILES)
        self._drain({"RS501": [], "RS505": []})
        self.assertEqual(self._callouts(), [])

    def test_the_worker_calls_the_register_itself(self):
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py")
                         .read_text(encoding="utf-8"))
        calls = {n.func.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        self.assertIn("register_detail_callouts", calls)


class Provenance(_CorpusCase):
    """Why did ARCHIOSK read these two tokens as one reference?"""

    FILES = ("RS501.pdf", "RS505.pdf")

    def test_the_positional_basis_is_on_the_candidate(self):
        page = {"unit": {"id": "u1"}, "lines": _bubble("1", "RS505")}
        basis = detail_callout.callout_candidates(page, {"RS505"})[0]["positional_basis"]
        for key in ("dx_in_target_heights", "dy_in_target_heights", "envelope",
                    "number_bbox", "target_bbox", "arrangement"):
            self.assertIn(key, basis)
        self.assertAlmostEqual(basis["dx_in_target_heights"], REAL_DX, places=2)

    def test_the_reason_is_readable_and_carries_no_score(self):
        page = {"unit": {"id": "u1"}, "lines": _bubble("1", "RS505")}
        reason = detail_callout.callout_candidates(page, {"RS505"})[0]["reason"]
        self.assertIn("split bubble", reason)
        for word in ("confidence", "score", "probability"):
            self.assertNotIn(word, reason.lower())

    def test_the_record_names_its_origin_boundary_and_method(self):
        self._ingest(self.FILES)
        self._drain({"RS501": self._words_for_bubble("1", "RS505"), "RS505": []})
        reference = self._callouts()[0]
        origin = reference["origin_context"]
        self.assertEqual(origin["origin"], detail_callout.CALLOUT_METHOD)
        self.assertEqual(origin["location_type"], "detail_callout")
        self.assertEqual(origin["boundary"], "page")
        self.assertTrue(origin["pages"])
        self.assertEqual(reference["resolution_method"], detail_callout.CALLOUT_METHOD)
        self.assertEqual(reference["extractor_version"], detail_callout.CALLOUT_VERSION)
        self.assertEqual(reference["created_by"], "perception-worker")


class Resolution(_CorpusCase):
    """Existing statuses, existing eligibility rules. Nothing new."""

    def test_an_ambiguous_target_is_never_chosen_between(self):
        self._ingest(("RS501.pdf", "212109 RS505 PLAN.pdf", "RS505.pdf"))
        self._drain({"RS501": self._words_for_bubble("1", "RS505"),
                     "RS505": [], "PLAN": []})
        refs = self._callouts()
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["resolution_status"],
                         RESOLUTION_STATUS_RESOLVED_MULTIPLE)
        self.assertEqual(len(refs[0]["resolved_target_ids"]), 2)

    def test_a_removed_source_is_not_an_active_target(self):
        self._ingest(("RS501.pdf", "RS505.pdf"))
        workspace = self._workspace()
        target = next(s for s in workspace.sources if s["name"] == "RS505.pdf")
        target["removed_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(workspace)
        self._drain({"RS501": self._words_for_bubble("1", "RS505"), "RS505": []})
        self.assertEqual(self._callouts(), [],
                         "a removed Source must not become a live target")


class Idempotency(_CorpusCase):
    FILES = ("RS501.pdf", "RS505.pdf")

    def test_a_revisit_creates_no_duplicate(self):
        from services import perception_jobs

        self._ingest(self.FILES)
        plan = {"RS501": self._words_for_bubble("1", "RS505"), "RS505": []}
        self._drain(plan)
        first = self._callouts()
        self.assertTrue(first)

        workspace = self._workspace()
        source = next(s for s in workspace.sources if s["name"] == "RS501.pdf")
        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        jobs.enqueue(workspace_id=workspace.project_id, source_id=source["id"],
                     source_sha256=source.get("file_hash") or "",
                     source_name="RS501.pdf", intake_order=99)
        self._drain(plan)

        second = self._callouts()
        self.assertEqual(len(second), len(first))
        self.assertEqual({r["id"] for r in second}, {r["id"] for r in first})


class FailureIsolation(_CorpusCase):
    FILES = ("RS501.pdf", "RS505.pdf")

    def test_a_raising_register_leaves_perception_completed(self):
        self._ingest(self.FILES)

        def boom(*_a, **_k):
            raise RuntimeError("the callout reader fell over")

        with patch.object(detail_callout, "register_detail_callouts", boom):
            records = self._drain({"RS501": self._words_for_bubble("1", "RS505"),
                                   "RS505": []})
        # The CITING sheet is the one this test is about. A Source with no words
        # legitimately ends needs_attention - it ran and established nothing -
        # and that is not what a downstream failure must be allowed to cause.
        citing = [r for r in records
                  if (r.get("source_name") or "").startswith("RS501")]
        self.assertTrue(citing)
        self.assertTrue(all(r["state"] == "completed" for r in citing),
                        [r["state"] for r in citing])
        self.assertFalse([r for r in records if r["state"] == "failed"])
        workspace = self._workspace()
        positioned = [e for e in workspace.evidence_items
                      if e.get("content_type")
                      == positioned_text.POSITIONED_CONTENT_TYPE]
        self.assertTrue(positioned, "the drawing evidence must survive")
        self.assertEqual(self._callouts(), [])

    def test_the_failure_is_surfaced_in_the_governance_log(self):
        self._ingest(self.FILES)
        events = []

        class _Log:
            def append(self, **kwargs):
                events.append(kwargs)

        def boom(*_a, **_k):
            raise RuntimeError("the callout reader fell over")

        with patch.object(detail_callout, "register_detail_callouts", boom):
            with patch("services.ingestion.get_governance_log", lambda _a: _Log()):
                self._drain({"RS501": self._words_for_bubble("1", "RS505"),
                             "RS505": []})
        failures = [e for e in events
                    if e.get("event_type") == "detail_callout_registration_failed"]
        self.assertTrue(failures)
        self.assertEqual(failures[0]["payload"]["perception_state"], "completed")


class Mutuality(unittest.TestCase):
    """Recorded as an observation, never as a validity requirement (section 9)."""

    def test_one_way_references_are_kept(self):
        class _WS:
            source_references = [
                {"source_id": "a", "resolved_target_ids": ["b"],
                 "origin_context": {"origin": detail_callout.CALLOUT_METHOD}},
                {"source_id": "b", "resolved_target_ids": ["a"],
                 "origin_context": {"origin": detail_callout.CALLOUT_METHOD}},
                {"source_id": "a", "resolved_target_ids": ["c"],
                 "origin_context": {"origin": detail_callout.CALLOUT_METHOD}},
            ]
        edges = detail_callout.mutual_edges(_WS())
        self.assertEqual(edges["directed_count"], 3)
        self.assertEqual(edges["mutual_count"], 2)
        self.assertEqual(edges["one_way_count"], 1)

    def test_other_reference_families_are_not_counted(self):
        class _WS:
            source_references = [
                {"source_id": "a", "resolved_target_ids": ["b"],
                 "origin_context": {"origin": "declared_sheet_index"}},
            ]
        self.assertEqual(detail_callout.mutual_edges(_WS())["directed_count"], 0)


class NoNewMeaning(_CorpusCase):
    FILES = ("RS501.pdf", "RS505.pdf")

    def test_no_relationship_claim_or_discrepancy_is_emitted(self):
        self._ingest(self.FILES)
        self._drain({"RS501": self._words_for_bubble("1", "RS505"), "RS505": []})
        workspace = self._workspace()
        self.assertEqual(getattr(workspace, "relationships", []) or [], [])
        self.assertEqual(getattr(workspace, "claims", []) or [], [])

    def test_no_physical_magnitude_is_derived(self):
        source = (_REPO_ROOT / "services" / "detail_callout.py").read_text(
            encoding="utf-8")
        for banned in ("millimet", "inch", "feet", "scale_factor", "points_per_foot",
                       "px_per_mm", "world_"):
            self.assertNotIn(banned, source.lower())

    def test_no_new_reference_type_or_store_was_introduced(self):
        source = (_REPO_ROOT / "services" / "detail_callout.py").read_text(
            encoding="utf-8")
        self.assertIn("REFERENCE_TYPE_DETAIL_CALLOUT", source)
        tree = ast.parse(source)
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        for forbidden in ("record_relationship", "register_claim", "create_claim",
                          "record_discrepancy"):
            self.assertNotIn(forbidden, called)

    def test_no_external_egress(self):
        source = (_REPO_ROOT / "services" / "detail_callout.py").read_text(
            encoding="utf-8")
        for banned in ("requests.", "urllib.request", "anthropic", "genai", "httpx"):
            self.assertNotIn(banned, source)


class GarbageControlIsNowAsymmetric(unittest.TestCase):
    """The perception correction this family required, pinned in both directions.

    `is_legible_token` is a refusal to store what OCR obviously misread. It
    cannot apply to text a document positioned itself - and applying it there
    discarded 40-45% of every real native structural page, including EVERY
    detail number, because the rule needs three characters and a detail number
    is one.
    """

    def _words(self, tokens):
        return [(100.0 + i * 20, 100.0, 110.0 + i * 20, 112.0, t, i, 0, 0)
                for i, t in enumerate(tokens)]

    def test_native_text_keeps_short_tokens(self):
        result = positioned_text._assemble_positioned(
            self._words(["1", "A", "U/S"]), (1000.0, 1000.0), (0, 0), "x",
            engine="pymupdf-native", version="native", dpi=0,
            garbage_control=False)
        self.assertEqual(len(result["lines"]), 3)
        self.assertEqual([ln["text"] for ln in result["lines"]], ["1", "A", "U/S"])

    def test_ocr_still_drops_them(self):
        result = positioned_text._assemble_positioned(
            self._words(["1", "A", "U/S"]), (1000.0, 1000.0), (0, 0), "x",
            engine="tesseract", version="5", dpi=200)
        self.assertEqual(result["lines"], [])
        self.assertEqual(result["dropped_line_count"], 3)

    def test_the_native_reader_passes_garbage_control_off(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        native = source[source.index("def _native_positioned_lines"):
                        source.index("def pdf_page_count")]
        self.assertIn("garbage_control=False", native)

    def test_the_zero_extent_refusal_still_governs_native(self):
        """Loosening garbage control must not loosen the store's own rule."""
        words = [(100.0, 100.0, 100.0, 100.0, "1", 0, 0, 0)]
        result = positioned_text._assemble_positioned(
            words, (1000.0, 1000.0), (0, 0), "x", engine="pymupdf-native",
            version="native", dpi=0, garbage_control=False)
        self.assertEqual(result["lines"], [])


class NativeOnlyToday(unittest.TestCase):
    """A LIMIT OF THIS FAMILY, pinned rather than left to be discovered.

    A detail number is one character. OCR garbage control requires three, and
    that rule is CORRECT for a recogniser - a lone glyph out of Tesseract is
    usually noise, as the architectural measurement showed (two reads of one
    sheet agreeing on the count of 2 of 11 single letters).

    So this family reaches native-text sheets and does NOT reach raster ones.
    That is a real boundary on its coverage, not a defect in the rule, and it is
    exactly why no architectural sheet in the Nipigon set produces a callout.
    Flip this test when a measured way to recover single glyphs from raster
    exists - not before, and never by loosening the OCR rule to get links.
    """

    def test_a_lone_detail_number_does_not_survive_the_ocr_path(self):
        words = [(100.0, 100.0, 110.0, 112.0, "1", 0, 0, 0)]
        result = positioned_text._assemble_positioned(
            words, (1000.0, 1000.0), (0, 0), "1", engine="tesseract",
            version="5", dpi=200)
        self.assertEqual(result["lines"], [],
                         "MEASURED, NOT DESIRED: the callout family is "
                         "native-text only until raster single-glyph recovery "
                         "is measured.")

    def test_and_does_survive_the_native_path(self):
        words = [(100.0, 100.0, 110.0, 112.0, "1", 0, 0, 0)]
        result = positioned_text._assemble_positioned(
            words, (1000.0, 1000.0), (0, 0), "1", engine="pymupdf-native",
            version="native", dpi=0, garbage_control=False)
        self.assertEqual([ln["text"] for ln in result["lines"]], ["1"])


class SheetIdentityUnaffected(_CorpusCase):
    """The previous family must be exactly what it was."""

    def test_an_index_still_registers_its_sheet_identities(self):
        from services import sheet_identity

        self._ingest(("index.pdf", "212109 A101 SITE PLAN.pdf"))
        words = [(100.0, 100.0, 200.0, 112.0, "DRAWING", 0, 0, 0),
                 (210.0, 100.0, 300.0, 112.0, "INDEX", 0, 0, 1),
                 (100.0, 140.0, 160.0, 152.0, "A101", 1, 0, 0)]
        self._drain({"index": words, "A101": []})
        workspace = self._workspace()
        index_refs = [r for r in workspace.source_references
                      if (r.get("origin_context") or {}).get("origin")
                      == sheet_identity.REGISTER_METHOD]
        self.assertTrue(index_refs, "the sheet index family must still fire")
        self.assertEqual(index_refs[0]["reference_text"], "A101")


if __name__ == "__main__":
    unittest.main()
