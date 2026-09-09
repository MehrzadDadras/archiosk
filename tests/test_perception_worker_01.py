"""CLAUDE-GO-PERCEPTION-WORKER-01 / MULTISOURCE-01.

Perception moved off the Gunicorn request, and an examination stopped being
one document. The properties below are ordered by what would hurt most:

  1. A source that has not been looked at NEVER renders as a finished reading.
  2. Evidence attaches exactly once, however many times a job replays.
  3. One bad photo does not discard its siblings, and one failed source does
     not erase completed ones.
  4. Ordinary customer activity during a job never becomes a visible 409.
  5. No image bytes leave the host.
"""
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from models import ROLE_CUSTOMER, User, db
from services import document_examination as dx
from services import perception_jobs as pj
from services import perception_worker as pw
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import EVIDENCE_CLASS_EXTRACTED, CaseWorkspaceStore

PW_PASSWORD = "TestCustomer!2026"


def _jpeg(size=(320, 240), colour=(240, 240, 235)):
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, "JPEG")
    return buffer.getvalue()


def _fake_parse(_p, raw, filename):
    text = raw.decode("utf-8", errors="ignore")
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="extracted" if text.strip() else "no_native_text")


class JobIdentityTests(unittest.TestCase):
    """Identity IS the idempotency - the file name is the deduplication."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_jobs_"))
        self.store = pj.PerceptionJobStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_same_work_is_the_same_job(self):
        a = self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h")
        b = self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h")
        self.assertEqual(a["job_id"], b["job_id"])
        self.assertEqual(len(self.store.list_all()), 1)

    def test_a_new_processing_version_is_an_explicit_new_run(self):
        a = self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h")
        b = self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h",
                               processing_version="regions@1")
        self.assertNotEqual(a["job_id"], b["job_id"])
        self.assertEqual(len(self.store.list_all()), 2,
                         "historical run was overwritten instead of preserved")

    def test_different_sources_are_different_jobs(self):
        a = self.store.enqueue(workspace_id="w", source_id="s1", source_sha256="h")
        b = self.store.enqueue(workspace_id="w", source_id="s2", source_sha256="h")
        self.assertNotEqual(a["job_id"], b["job_id"])

    def test_a_repeated_post_cannot_duplicate_work(self):
        for _ in range(6):
            self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h")
        self.assertEqual(len(self.store.list_all()), 1)

    def test_every_job_records_zero_egress(self):
        job = self.store.enqueue(workspace_id="w", source_id="s", source_sha256="h")
        self.assertEqual(job["egress"], pj.EGRESS_NONE)
        self.assertTrue(job["processing_location"])


class ClaimAndRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_claim_"))
        self.store = pj.PerceptionJobStore(self.tmp)
        self.job = self.store.enqueue(workspace_id="w", source_id="s",
                                      source_sha256="h")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_queued_to_running_to_completed(self):
        claimed = self.store.claim_next(worker_id="w1")
        self.assertEqual(claimed["state"], pj.STATE_RUNNING)
        self.assertEqual(claimed["attempt_count"], 1)
        done = self.store.complete(claimed, state=pj.STATE_COMPLETED)
        self.assertEqual(done["state"], pj.STATE_COMPLETED)
        self.assertIsNotNone(done["completed_at"])

    def test_a_running_job_is_not_handed_to_a_second_worker(self):
        self.store.claim_next(worker_id="w1")
        self.assertIsNone(self.store.claim_next(worker_id="w2"))

    def test_a_crashed_worker_does_not_wedge_the_source(self):
        claimed = self.store.claim_next(worker_id="w1")
        stale = datetime.now(timezone.utc) - timedelta(seconds=pj.LEASE_SECONDS + 60)
        claimed["claimed_at"] = stale.isoformat()
        self.store._write(claimed)
        reclaimed = self.store.claim_next(worker_id="w2")
        self.assertIsNotNone(reclaimed, "an expired lease was not reclaimed")
        self.assertEqual(reclaimed["attempt_count"], 2)
        self.assertEqual(reclaimed["claimed_by"], "w2")

    def test_the_retry_ceiling_is_honoured(self):
        for _ in range(pj.MAX_ATTEMPTS):
            claimed = self.store.claim_next(worker_id="w1")
            self.assertIsNotNone(claimed)
            self.store.release_for_retry(claimed, reason="transient")
        self.assertIsNone(self.store.claim_next(worker_id="w1"),
                          "a job kept being handed out past its ceiling")
        self.assertEqual(self.store.get(self.job["job_id"])["state"],
                         pj.STATE_FAILED)

    def test_queue_depth_reports_real_counts(self):
        depth = self.store.queue_depth()
        self.assertEqual(depth["queued"], 1)
        self.assertEqual(depth["running"], 0)
        self.assertIsNotNone(depth["oldest_queued_at"])


class WorkerIntegrationTests(unittest.TestCase):
    """The whole path, with the real store and the real OCR adapter stubbed
    only at the extractor boundary."""

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_pw_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        from werkzeug.security import generate_password_hash
        for name in ("cust", "cust2"):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=ROLE_CUSTOMER)
                user.password_hash = generate_password_hash(PW_PASSWORD)
                db.session.add(user)
        db.session.commit()
        self.client = self.app.test_client()
        self.client.post("/login", data={"username": "cust", "password": PW_PASSWORD})
        self.jobs = pj.PerceptionJobStore(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upload(self, files, name=None):
        data = {"name": name or ("Job %s" % uuid.uuid4().hex[:8])}
        data["file"] = files
        with patch.object(BHiveParser, "parse", _fake_parse):
            return self.client.post("/document-shop", data=data,
                                    content_type="multipart/form-data")

    def _pid(self, response):
        return response.headers["Location"].rstrip("/").split("/")[-1]

    # -- multi-source ------------------------------------------------------

    def test_one_examination_accepts_several_sources(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg"),
                          (io.BytesIO(_jpeg((300, 200))), "image.jpg"),
                          (io.BytesIO(_jpeg((280, 210))), "image.jpg")])
        self.assertEqual(r.status_code, 302)
        workspace = self.store.get(self._pid(r))
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 3, "a batch collapsed into fewer sources")

    def test_repeated_filenames_are_safe(self):
        r = self._upload([(io.BytesIO(_jpeg((10 + i, 10 + i))), "image.jpg")
                          for i in range(4)])
        workspace = self.store.get(self._pid(r))
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 4)
        self.assertEqual(len({s["id"] for s in live}), 4,
                         "filename was used as identity")

    def test_customer_selected_order_is_persisted_not_derived(self):
        r = self._upload([(io.BytesIO(_jpeg((100 + i, 100))), "image.jpg")
                          for i in range(3)])
        workspace = self.store.get(self._pid(r))
        live = [s for s in workspace.sources if not s.get("removed_at")]
        orders = [s.get("intake_order") for s in live[1:]]
        self.assertEqual(orders, [1, 2], "explicit order was not recorded")

    def test_each_source_gets_exactly_one_job(self):
        r = self._upload([(io.BytesIO(_jpeg((120 + i, 90))), "image.jpg")
                          for i in range(3)])
        pid = self._pid(r)
        workspace = self.store.get(pid)
        live = [s for s in workspace.sources if not s.get("removed_at")]
        for source in live:
            with self.subTest(source=source["name"]):
                self.assertEqual(len(self.jobs.for_source(pid, source["id"])), 1)

    def test_independent_source_hashes(self):
        r = self._upload([(io.BytesIO(_jpeg((150, 100))), "image.jpg"),
                          (io.BytesIO(_jpeg((160, 100))), "image.jpg")])
        pid = self._pid(r)
        hashes = {j["source_sha256"] for j in self.jobs.for_workspace(pid)}
        self.assertEqual(len(hashes), 2)

    def test_a_single_source_examination_still_works(self):
        r = self._upload([(io.BytesIO(b"The contractor shall comply.\n"), "spec.txt")])
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(
            "/document-shop/jobs/%s" % self._pid(r)).status_code, 200)

    # -- partial batches ---------------------------------------------------

    def test_one_bad_file_does_not_discard_its_siblings(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg"),
                          (io.BytesIO(b"not an image"), "broken.jpg"),
                          (io.BytesIO(_jpeg((200, 150))), "image.jpg")])
        self.assertEqual(r.status_code, 302)
        workspace = self.store.get(self._pid(r))
        live = [s for s in workspace.sources if not s.get("removed_at")]
        self.assertEqual(len(live), 2, "a rejection took a good sibling with it")

    def test_an_unsupported_type_among_siblings_is_reported_not_silent(self):
        from services.ingestion import attach_document_shop_sources
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        workspace = self.store.get(self._pid(r))

        class _F:
            def __init__(self, name, data):
                self.filename = name
                self._data = data

            def read(self):
                return self._data

        results = attach_document_shop_sources(
            self.app, workspace, [_F("notes.exe", b"MZ"), _F("b.jpg", _jpeg())],
            owner="cust", actor="cust")
        self.assertEqual(results[0]["status"], "rejected")
        self.assertIn("Unsupported", results[0]["reason"])
        self.assertEqual(results[1]["status"], "accepted")

    # -- worker ------------------------------------------------------------

    def test_the_worker_completes_a_job_and_attaches_evidence_once(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        pid = self._pid(r)

        def fake_extract(raw, name, **kwargs):
            return {"ran": True, "status": "readable", "engine": "tesseract",
                    "engine_version": "4.1.1", "reason": None,
                    "text": "FIRE DAMPER SCHEDULE",
                    "orientation": {"authority": "exif", "changed": False}}

        with patch("services.image_intake.extract_image_text", fake_extract):
            done = pw.run_one(self.app, self.jobs, "w1")
        self.assertEqual(done["state"], pj.STATE_COMPLETED)

        workspace = self.store.get(pid)
        evidence = [e for e in workspace.evidence_items
                    if e.get("content_type") == "text"]
        self.assertEqual(len(evidence), 1)

        # replay: the same work must not attach a second copy
        replayed = self.jobs.get(done["job_id"])
        replayed["state"] = pj.STATE_QUEUED
        self.jobs._write(replayed)
        with patch("services.image_intake.extract_image_text", fake_extract):
            pw.run_one(self.app, self.jobs, "w1")
        workspace = self.store.get(pid)
        evidence = [e for e in workspace.evidence_items
                    if e.get("content_type") == "text"]
        self.assertEqual(len(evidence), 1, "replay duplicated evidence")

    def test_a_source_that_reads_as_nothing_is_needs_attention_not_failed(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])

        def empty(raw, name, **kwargs):
            return {"ran": True, "status": "readable", "engine": "tesseract",
                    "engine_version": "4.1.1", "reason": None, "text": "",
                    "orientation": {}}

        with patch("services.image_intake.extract_image_text", empty):
            done = pw.run_one(self.app, self.jobs, "w1")
        self.assertEqual(done["state"], pj.STATE_NEEDS_ATTENTION,
                         "an established-nothing outcome was called a fault")

    def test_a_raising_extractor_is_retried_not_lost(self):
        self._upload([(io.BytesIO(_jpeg()), "image.jpg")])

        def boom(raw, name, **kwargs):
            raise RuntimeError("engine died")

        with patch("services.image_intake.extract_image_text", boom):
            done = pw.run_one(self.app, self.jobs, "w1")
        self.assertEqual(done["state"], pj.STATE_QUEUED)
        self.assertEqual(done["attempt_count"], 1)

    def test_the_worker_never_takes_a_path_from_the_job_record(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        pid = self._pid(r)
        job = self.jobs.for_workspace(pid)[0]
        self.assertNotIn("file_path", job)
        self.assertNotIn("path", job)

    def test_a_source_from_another_workspace_is_not_readable(self):
        r1 = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        r2 = self._upload([(io.BytesIO(_jpeg((200, 150))), "image.jpg")])
        pid1, pid2 = self._pid(r1), self._pid(r2)
        other_source = [s for s in self.store.get(pid2).sources
                        if not s.get("removed_at")][0]["id"]
        self.assertIsNone(
            pw.read_source_bytes(self.store, pid1, other_source),
            "a source id crossed a workspace boundary")

    # -- honest async state ------------------------------------------------

    def test_a_queued_source_is_not_rendered_as_a_finished_reading(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        pid = self._pid(r)
        document = __import__("services.ingestion", fromlist=["get_registry"]) \
            .get_registry(self.app).get(pid)
        result = dx.build_result(document, self.store.get(pid),
                                 display_name="x", jobs=self.jobs)
        self.assertEqual(result["state"], dx.STATE_QUEUED)
        self.assertTrue(result["pending"])
        self.assertNotEqual(result["state_label"], "Read, not interpreted")

    def test_a_running_source_reads_as_being_examined(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        pid = self._pid(r)
        self.jobs.claim_next(worker_id="w1")
        document = __import__("services.ingestion", fromlist=["get_registry"]) \
            .get_registry(self.app).get(pid)
        result = dx.build_result(document, self.store.get(pid),
                                 display_name="x", jobs=self.jobs)
        self.assertEqual(result["state"], dx.STATE_PROCESSING)

    def test_aggregate_takes_the_least_settled_source(self):
        r = self._upload([(io.BytesIO(_jpeg((100, 90))), "image.jpg"),
                          (io.BytesIO(_jpeg((110, 90))), "image.jpg")])
        pid = self._pid(r)
        all_jobs = self.jobs.for_workspace(pid)
        self.jobs.complete(all_jobs[0], state=pj.STATE_COMPLETED)
        document = __import__("services.ingestion", fromlist=["get_registry"]) \
            .get_registry(self.app).get(pid)
        summary = dx.summarise_job(document, self.store.get(pid),
                                   display_name="x", project_id=pid,
                                   jobs=self.jobs)
        self.assertEqual(summary["state"], dx.STATE_QUEUED,
                         "an examination looked finished while part was waiting")
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["settled_count"], 1)

    def test_one_failed_source_does_not_erase_completed_siblings(self):
        r = self._upload([(io.BytesIO(_jpeg((130, 90))), "image.jpg"),
                          (io.BytesIO(_jpeg((140, 90))), "image.jpg")])
        pid = self._pid(r)
        all_jobs = sorted(self.jobs.for_workspace(pid),
                          key=lambda j: j.get("intake_order") or 0)
        self.jobs.complete(all_jobs[0], state=pj.STATE_COMPLETED)
        self.jobs.complete(all_jobs[1], state=pj.STATE_FAILED,
                           failure_reason="engine unavailable")
        document = __import__("services.ingestion", fromlist=["get_registry"]) \
            .get_registry(self.app).get(pid)
        result = dx.build_result(document, self.store.get(pid),
                                 display_name="x", jobs=self.jobs)
        states = [row["state"] for row in result["sources"]]
        self.assertIn(dx.STATE_NEEDS_ATTENTION, states)
        self.assertEqual(len(result["sources"]), 2,
                         "a failed source removed its sibling from the result")

    def test_a_historical_container_without_jobs_still_opens(self):
        """Backward compatibility: one source, no job store entry."""
        r = self._upload([(io.BytesIO(b"Shall comply.\n"), "old.txt")])
        pid = self._pid(r)
        for job in self.jobs.for_workspace(pid):
            Path(self.jobs._path(job["job_id"])).unlink()
        self.assertEqual(self.client.get(
            "/document-shop/jobs/%s" % pid).status_code, 200)

    # -- the web stays healthy --------------------------------------------

    def test_the_application_is_healthy_with_no_worker_running(self):
        r = self._upload([(io.BytesIO(_jpeg()), "image.jpg")])
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/document-shop/jobs").status_code, 200)
        self.assertEqual(self.client.get(
            "/document-shop/jobs/%s" % self._pid(r)).status_code, 200)

    def test_no_image_bytes_reach_a_provider_on_the_worker_path(self):
        from services import llm_gateway
        self._upload([(io.BytesIO(_jpeg()), "image.jpg")])

        def detonate(*a, **k):
            raise AssertionError("the worker attempted a provider call")

        with patch.object(llm_gateway, "call_llm_json", detonate), \
             patch.object(llm_gateway, "call_gemini_json", detonate):
            pw.run_one(self.app, self.jobs, "w1")


if __name__ == "__main__":
    unittest.main()
