"""CLAUDE-SHEET-IDENTITY-WIRING-01: a capability nobody can reach.

`register_sheet_index` shipped built, tested and deployed — and with **no
application caller at all**. It was reachable only by importing the service and
invoking it by hand, which is not a workflow; the register's own measurement
(48 real sheet identities resolved from one real drawing index) was produced by
a scratchpad script rather than by ARCHIOSK. That is an integration gap before
it is an architecture gap, and this tranche closes exactly that and nothing
else.

What these tests defend, in the order the mistakes would be made:

1. **REGISTRATION MUST NEVER COST AN EXAMINATION.** The stage runs strictly
   after the job record is terminal, so failure isolation is structural rather
   than promised — but structure is only worth having if it is pinned, so
   `FailureIsolation` proves that a stage which raises leaves a completed job
   completed and its perception evidence whole.

2. **CALLED ONLY WHEN JUSTIFIED.** An ordinary drawing sheet is not an index,
   and a stage that ran blindly on every document would turn honest abstention
   into governed noise. `Justification` pins the no-op.

3. **THE APPLICATION REVISITS SOURCES.** A second pass over the same Source
   must add nothing. Idempotency here is the store's own existing rule — the
   (source_id, reference_text, reference_type, origin_context) key — not a new
   one invented for this caller, and the test proves the caller stays inside it.

4. **NO NEW MEANING.** Identity is not correspondence. Nothing here may emit a
   Relationship, a Claim or a discrepancy, and `NoNewMeaning` asserts on the
   collections rather than trusting the docstring that says so.

The OCR engine is injected at the same seam every other perception test uses, so
none of this needs Tesseract, a real PDF render, or a network.
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

from PIL import Image
from werkzeug.datastructures import FileStorage

from services import perception_worker, positioned_text, sheet_identity
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_TARGET_NOT_FOUND, CaseWorkspaceStore,
)
from services.ingestion import attach_document_shop_sources, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: The index page's own words. `A999` names no Source in this project and is
#: the unresolved-but-legitimate declaration every assertion about abstention
#: depends on — it must be PRESERVED, never discarded for failing to resolve.
_INDEX_WORDS = ["DRAWING", "INDEX", "A101", "A102", "A999"]

#: An ordinary sheet. Sheet-shaped tokens are present on purpose: the no-op must
#: come from the absence of an INDEX HEADING, not from an absence of tokens.
_SHEET_WORDS = ["GROUND", "FLOOR", "PLAN", "A102", "NORTH"]


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _words(tokens):
    """PyMuPDF-shaped word tuples, one per line, top to bottom."""
    out = []
    for i, token in enumerate(tokens):
        y = 100.0 + i * 40.0
        out.append((100.0, y, 300.0, y + 20.0, token, i, 0, 0))
    return out


class _WiringCase(unittest.TestCase):
    """A real-shaped Document Shop examination: one index, two sheets."""

    INDEX = "index.pdf"
    SHEETS = ("212109 A101 SITE PLAN.pdf", "212109 A102 GROUND FLOOR PLAN.pdf")

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_si_wiring_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- the examination -----------------------------------------------------

    def _ocr(self):
        """Text keyed to the FILE'S OWN BYTES, so each Source reads differently.

        `read_pdf_positioned_pages` hands the reader the source bytes verbatim
        (filetype="pdf"), which is what makes one injected reader able to serve
        an index and an ordinary sheet in the same run without either one
        having to know which Source it is.
        """
        def reader(frame_bytes, dpi, filetype="png", page_index=0):
            tokens = _INDEX_WORDS if b"INDEX" in frame_bytes else _SHEET_WORDS
            words = _words(tokens)
            return words, (612.0, 792.0), "tesseract", "5.0.0", \
                "\n".join(w[4] for w in words)
        return reader

    def _ingest(self, extra=()):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"founding"), filename="job.txt"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Sheet Identity Wiring")
                workspace = self.store.get(document.project_id)
                uploads = [FileStorage(stream=io.BytesIO(b"%PDF-1.4 INDEX"),
                                       filename=self.INDEX)]
                uploads += [FileStorage(stream=io.BytesIO(b"%PDF-1.4 SHEET"),
                                        filename=name)
                            for name in tuple(self.SHEETS) + tuple(extra)]
                attach_document_shop_sources(self.app, workspace, uploads,
                                             owner="cust")
        self.document = document
        return document

    def _drain(self, limit=20):
        """Run the NORMAL worker until the queue is empty. Returns the records.

        Nothing in this helper calls `register_sheet_index`. Reachability is the
        whole question, so the tests must not reach past the application to
        answer it.
        """
        from services import perception_jobs

        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        records = []
        with patch.object(positioned_text, "pdf_page_count", lambda _b: 1):
            with patch.object(positioned_text, "_native_positioned_lines",
                              lambda _b, _i: None):
                with patch.object(positioned_text, "_default_ocr", self._ocr()):
                    for _ in range(limit):
                        record = perception_worker.run_one(
                            self.app, jobs, "test-worker")
                        if record is None:
                            break
                        records.append(record)
        return records

    # -- readers -------------------------------------------------------------

    def _workspace(self):
        return self.store.get(self.document.project_id)

    def _source_id(self, name):
        return next(s["id"] for s in self._workspace().sources
                    if s.get("name") == name)

    def _index_refs(self, source_name=None):
        """Sheet-index references, read through the STORE'S EXISTING reader."""
        workspace = self._workspace()
        source_id = self._source_id(source_name or self.INDEX)
        return [r for r in self.store.source_references_for_source(
            workspace, source_id)
            if (r.get("origin_context") or {}).get("origin")
            == sheet_identity.REGISTER_METHOD]


class Reachability(_WiringCase):
    """The gap this tranche exists to close."""

    def test_the_normal_workflow_registers_sheet_identities(self):
        self._ingest()
        records = self._drain()
        self.assertTrue(records, "the worker processed nothing")
        self.assertTrue(all(r["state"] == "completed" for r in records),
                        [r["state"] for r in records])
        refs = self._index_refs()
        self.assertEqual(len(refs), 3,
                         "every index candidate must become a governed record")

    def test_declared_sheets_resolve_to_their_actual_sources(self):
        self._ingest()
        self._drain()
        by_text = {r["reference_text"]: r for r in self._index_refs()}
        workspace = self._workspace()
        for text, name in (("A101", self.SHEETS[0]), ("A102", self.SHEETS[1])):
            reference = by_text[text]
            self.assertEqual(reference["resolution_status"],
                             RESOLUTION_STATUS_RESOLVED_EXACT, text)
            self.assertEqual(reference["resolved_target_ids"],
                             [self._source_id(name)], text)
            # And the graph reads BACK, which is what "available through
            # existing readers" has to mean to be worth anything.
            back = self.store.source_references_to_target(
                workspace, self._source_id(name))
            self.assertEqual([r["id"] for r in back], [reference["id"]], text)

    def test_the_register_is_no_longer_called_only_from_outside(self):
        """The literal integration gap, pinned by AST rather than by grep.

        The previous tranche's own closing finding was that `register_sheet_
        index` had no caller in the application at all. A test that only checked
        outcomes would go green again the day someone deleted the call and
        re-registered from a script.
        """
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py")
                         .read_text(encoding="utf-8"))
        calls = {node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)}
        self.assertIn("register_sheet_index", calls,
                      "the perception lifecycle must call the register itself")


class Justification(_WiringCase):
    """Run when justified, abstain otherwise — and abstain for the right reason."""

    def test_an_ordinary_sheet_registers_nothing(self):
        self._ingest()
        self._drain()
        for name in self.SHEETS:
            self.assertEqual(self._index_refs(name), [],
                             "%s is not an index and must no-op" % name)

    def test_the_no_op_is_caused_by_the_missing_heading_not_missing_tokens(self):
        """`A102` is present in the ordinary sheet's own text on purpose."""
        self.assertIn("A102", _SHEET_WORDS)
        self.assertFalse(sheet_identity.looks_like_index("\n".join(_SHEET_WORDS)))
        self.assertTrue(sheet_identity.looks_like_index("\n".join(_INDEX_WORDS)))

    def test_registration_does_not_run_on_a_job_that_did_not_complete(self):
        """A needs-attention or failed job is not a reading of an index."""
        calls = []
        with patch.object(sheet_identity, "register_sheet_index",
                          lambda *a, **k: calls.append(a)):
            for state in ("needs_attention", "failed", "leased"):
                perception_worker._register_sheet_index(
                    self.store, {"workspace_id": "w", "source_id": "s"},
                    None, {"state": state})
            perception_worker._register_sheet_index(
                self.store, {"workspace_id": "w", "source_id": "s"}, None, None)
        self.assertEqual(calls, [])


class Idempotency(_WiringCase):
    """The application revisits Sources. Revisiting must not accumulate."""

    def test_a_second_pass_creates_no_duplicate_records(self):
        self._ingest()
        self._drain()
        first = self._index_refs()
        self.assertTrue(first)

        from services import perception_jobs

        workspace = self._workspace()
        source = next(s for s in workspace.sources if s["name"] == self.INDEX)
        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        jobs.enqueue(workspace_id=workspace.project_id, source_id=source["id"],
                     source_sha256=source.get("file_hash") or "",
                     source_name=self.INDEX, intake_order=99)
        self._drain()

        second = self._index_refs()
        self.assertEqual(len(second), len(first))
        self.assertEqual({r["id"] for r in second}, {r["id"] for r in first},
                         "a revisit must reuse the existing governed records")

    def test_calling_the_stage_again_directly_also_adds_nothing(self):
        """Idempotency belongs to the WRITE, not to the queue's exactly-once.

        Pinned separately because the two are different guarantees: a job that
        is never claimed twice would hide a caller that duplicates when it is.
        """
        self._ingest()
        self._drain()
        before = self._index_refs()
        job = {"workspace_id": self.document.project_id,
               "source_id": self._source_id(self.INDEX)}
        report = perception_worker._register_sheet_index(
            self.store, job, None, {"state": "completed"})
        self.assertTrue(report["is_index"])
        self.assertEqual(report["references_created"], 0)
        self.assertEqual({r["id"] for r in self._index_refs()},
                         {r["id"] for r in before})


class UnresolvedDeclarations(_WiringCase):
    """A declaration that resolves to nothing is still a declaration."""

    def test_an_undelivered_sheet_is_preserved_not_discarded(self):
        self._ingest()
        self._drain()
        reference = next(r for r in self._index_refs()
                         if r["reference_text"] == "A999")
        self.assertEqual(reference["resolution_status"],
                         RESOLUTION_STATUS_TARGET_NOT_FOUND)
        self.assertEqual(reference["resolved_target_ids"], [])
        self.assertEqual(reference["reference_text"], "A999",
                         "the verbatim citation must survive non-resolution")


class ArrivalOrder(_WiringCase):
    """A LIMIT THIS TRANCHE MAKES LIVE, pinned rather than left to be discovered.

    `services/sheet_identity.py`'s own docstring says the decisive practical
    consequence of choosing SourceReference is RESOLUTION AT READ TIME - "an
    index that lists a sheet nobody has uploaded resolves to nothing today and
    resolves the moment that sheet arrives, with no mutation, no reprocessing,
    and no stored answer to go stale."

    **THAT IS NOT TRUE OF THIS FAMILY, and these tests are what establishes it.**
    `extract_and_register_source_references` stores `resolution_status` and
    `resolved_target_ids` at write time, and the store's one read-time
    re-resolver (`resolve_source_reference_status`) re-resolves SECTION
    citations against Requirements - not SHEET citations against Sources. A
    sheet that arrives after its index therefore stays `target_not_found`, and
    the idempotency key that correctly prevents duplicates is also what
    prevents the record from ever being upgraded.

    Nothing here is a defect in the WIRING, and nothing is repaired in this
    tranche: this is a property the register already had, which was harmless
    while it was unreachable and becomes a live production property the moment
    the lifecycle calls it. It is pinned so that the next tranche starts from a
    measured fact rather than from a docstring, and so that a future read-time
    resolver has a failing assertion to flip rather than a paragraph to trust.
    """

    SHEETS = ("212109 A101 SITE PLAN.pdf",)

    def test_a_sheet_arriving_after_its_index_does_not_retroactively_resolve(self):
        self._ingest()
        self._drain()
        before = {r["reference_text"]: r["resolution_status"]
                  for r in self._index_refs()}
        self.assertEqual(before.get("A102"), RESOLUTION_STATUS_TARGET_NOT_FOUND,
                         "A102 has not been uploaded yet")

        # The missing sheet arrives, exactly as it would in practice.
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                attach_document_shop_sources(
                    self.app, self._workspace(),
                    [FileStorage(stream=io.BytesIO(b"%PDF-1.4 SHEET"),
                                 filename="212109 A102 GROUND FLOOR PLAN.pdf")],
                    owner="cust")
        self._drain()

        after = {r["reference_text"]: r["resolution_status"]
                 for r in self._index_refs()}
        self.assertEqual(after.get("A102"), RESOLUTION_STATUS_TARGET_NOT_FOUND,
                         "MEASURED, NOT DESIRED: the stored status does not "
                         "upgrade when the sheet arrives. Flip this assertion "
                         "when a read-time sheet resolver exists, not before.")
        # The declaration itself is intact, which is why the repair is cheap
        # later: nothing was lost, only left un-re-resolved.
        self.assertEqual(len(self._index_refs()), len(before))

    def test_the_ordinary_document_shop_order_resolves_completely(self):
        """And the reason the limit above is not urgent.

        The real workflow attaches every file of an examination before any
        perception job runs, so an index is perceived with its siblings already
        present. The limit bites on incremental delivery, not on the path the
        reachability proof actually exercises.
        """
        self.SHEETS = ("212109 A101 SITE PLAN.pdf",
                       "212109 A102 GROUND FLOOR PLAN.pdf")
        self._ingest()
        self._drain()
        statuses = {r["reference_text"]: r["resolution_status"]
                    for r in self._index_refs()}
        self.assertEqual(statuses["A101"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(statuses["A102"], RESOLUTION_STATUS_RESOLVED_EXACT)


class Provenance(_WiringCase):
    """Page-bounded, and able to say so on the record."""

    def test_every_record_names_the_page_it_was_read_from(self):
        self._ingest()
        self._drain()
        workspace = self._workspace()
        units = {u["id"] for u in workspace.structural_units
                 if u.get("source_id") == self._source_id(self.INDEX)}
        for reference in self._index_refs():
            origin = reference.get("origin_context") or {}
            self.assertEqual(origin.get("origin"), sheet_identity.REGISTER_METHOD)
            self.assertEqual(origin.get("location_type"), "drawing_index")
            self.assertEqual(origin.get("boundary"), "page")
            pages = origin.get("index_pages") or []
            self.assertTrue(pages, "the index page must be named on the record")
            for page in pages:
                self.assertIn(page["structural_unit_id"], units,
                              "provenance must name THIS source's own page")

    def test_the_method_and_version_survive_the_wiring(self):
        self._ingest()
        self._drain()
        for reference in self._index_refs():
            self.assertEqual(reference["resolution_method"],
                             sheet_identity.REGISTER_METHOD)
            self.assertEqual(reference["extractor_version"],
                             sheet_identity.REGISTER_VERSION)

    def test_the_actor_is_the_worker_not_a_person(self):
        self._ingest()
        self._drain()
        for reference in self._index_refs():
            self.assertEqual(reference["created_by"], "perception-worker")


class FailureIsolation(_WiringCase):
    """Drawing evidence was produced. Nothing downstream may take that away."""

    def _positioned_count(self, source_name):
        workspace = self._workspace()
        source_id = self._source_id(source_name)
        return len([e for e in workspace.evidence_items
                    if e.get("source_id") == source_id
                    and e.get("content_type")
                    == positioned_text.POSITIONED_CONTENT_TYPE])

    def test_a_raising_register_leaves_the_examination_completed(self):
        self._ingest()

        def boom(*_a, **_k):
            raise RuntimeError("the index parser fell over")

        with patch.object(sheet_identity, "register_sheet_index", boom):
            records = self._drain()

        self.assertTrue(records)
        self.assertTrue(all(r["state"] == "completed" for r in records),
                        "perception must survive a downstream failure")
        self.assertGreater(self._positioned_count(self.INDEX), 0,
                           "the drawing evidence itself must be intact")
        self.assertEqual(self._index_refs(), [],
                         "and no half-written registration is left behind")

    def test_the_failure_is_surfaced_rather_than_swallowed(self):
        self._ingest()
        events = []

        class _Log:
            def append(self, **kwargs):
                events.append(kwargs)

        def boom(*_a, **_k):
            raise RuntimeError("the index parser fell over")

        with patch.object(sheet_identity, "register_sheet_index", boom):
            with patch("services.ingestion.get_governance_log",
                       lambda _app: _Log()):
                self._drain()

        failures = [e for e in events
                    if e.get("event_type") == "sheet_index_registration_failed"]
        self.assertTrue(failures, "a silent downstream failure is the one "
                                  "outcome section 4 forbids")
        self.assertEqual(failures[0]["payload"]["error_type"], "RuntimeError")
        self.assertEqual(failures[0]["payload"]["perception_state"], "completed")

    def test_the_outcome_is_logged_even_when_the_source_is_not_an_index(self):
        """A log that records only index pages cannot say how rare one is."""
        self._ingest()
        events = []

        class _Log:
            def append(self, **kwargs):
                events.append(kwargs)

        with patch("services.ingestion.get_governance_log", lambda _app: _Log()):
            self._drain()

        registered = [e for e in events
                      if e.get("event_type") == "sheet_index_registered"]
        self.assertEqual(len(registered), 3, "one per perceived source")
        self.assertEqual(sorted(e["payload"]["is_index"] for e in registered),
                         [False, False, True])


class NoNewMeaning(_WiringCase):
    """Identity is not correspondence, and this tranche adds no family."""

    def test_no_relationship_or_claim_is_emitted(self):
        self._ingest()
        self._drain()
        workspace = self._workspace()
        self.assertEqual(getattr(workspace, "relationships", []) or [], [])
        self.assertEqual(getattr(workspace, "claims", []) or [], [])

    def test_the_wiring_imports_no_relationship_or_discrepancy_writer(self):
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        called = {node.func.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)}
        for forbidden in ("record_relationship", "register_claim",
                          "record_discrepancy", "create_claim"):
            self.assertNotIn(forbidden, called)


class NoEgress(_WiringCase):
    """Zero image egress is unchanged, and the stage re-reads no document."""

    def test_the_stage_opens_no_network_and_no_provider(self):
        source = (_REPO_ROOT / "services" / "sheet_identity.py").read_text(
            encoding="utf-8")
        worker = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        for module in (source, worker):
            for forbidden in ("requests.", "urllib.request", "anthropic",
                              "genai", "httpx"):
                self.assertNotIn(forbidden, module)

    def test_registration_does_not_re_read_the_source_bytes(self):
        """The cost question from section 7, pinned rather than asserted.

        Candidates come from evidence the job already wrote. If this stage ever
        starts re-opening the document, a 49-page index would pay for its
        perception twice and the regression would be invisible in every
        outcome-shaped test above.
        """
        self._ingest()
        self._drain()
        reads = []
        real = perception_worker.read_source_bytes
        job = {"workspace_id": self.document.project_id,
               "source_id": self._source_id(self.INDEX)}
        with patch.object(perception_worker, "read_source_bytes",
                          lambda *a, **k: reads.append(a) or real(*a, **k)):
            perception_worker._register_sheet_index(
                self.store, job, None, {"state": "completed"})
        self.assertEqual(reads, [])


class PerceptionUnaffected(_WiringCase):
    """The existing image and PDF paths must be exactly what they were."""

    def test_pdf_page_evidence_is_unchanged(self):
        self._ingest()
        self._drain()
        workspace = self._workspace()
        for name in (self.INDEX,) + self.SHEETS:
            source_id = self._source_id(name)
            units = perception_worker._page_units_for(workspace, source_id)
            self.assertEqual(len(units), 1, name)
            positioned = [e for e in workspace.evidence_items
                          if e.get("source_id") == source_id
                          and e.get("content_type")
                          == positioned_text.POSITIONED_CONTENT_TYPE]
            self.assertEqual(len(positioned), 5,
                             "%s: one positioned line per injected word" % name)

    def test_an_image_source_still_completes(self):
        """The image path gained the same stage; it must not have gained a gate."""
        from services import image_intake, perception_jobs

        # A REAL PNG, and the founding path rather than the attach path: intake
        # runs `verify_image_bytes` and rejects fabricated image bytes outright,
        # which would leave the queue empty and the assertion below reading a
        # None record instead of a result.
        buffer = io.BytesIO()
        Image.new("RGB", (400, 300), (255, 255, 255)).save(buffer, "PNG")
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(buffer.getvalue()),
                                filename="sheet.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Image Path Unchanged")
        self.document = document

        lines = [{"text": token, "bbox": {"x": 0.1, "y": 0.1 + i * 0.05,
                                          "width": 0.2, "height": 0.03}}
                 for i, token in enumerate(_SHEET_WORDS)]

        def positioned(*_a, **_k):
            return {
                "ran": True, "status": "readable", "engine": "tesseract",
                "engine_version": "5.0.0", "reason": None,
                "orientation": {"authority": "stored_pixels", "changed": False},
                "text": "\n".join(_SHEET_WORDS), "lines": lines,
                "line_count": len(lines), "word_count": len(lines),
                "dropped_line_count": 0, "truncated": False,
                "confidence_available": False,
                "frame": {"normalised_size": [400, 300],
                          "ocr_frame_size": [300.0, 225.0],
                          "px_per_ocr_unit": [4 / 3, 4 / 3], "render_dpi": 200,
                          "coordinate_space": "fraction_of_normalised_frame"},
            }

        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        with patch.object(image_intake, "extract_image_positioned_text", positioned):
            record = perception_worker.run_one(self.app, jobs, "test-worker")
        self.assertEqual(record["state"], "completed")
        self.assertEqual(self._index_refs("sheet.png"), [],
                         "an ordinary image sheet is not an index")


if __name__ == "__main__":
    unittest.main()
