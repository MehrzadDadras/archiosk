"""
CLAUDE-STORAGE-BRIDGE-07 - the same invariants, now across fifteen workers.

WHAT CHANGED AND WHY THESE TESTS EXIST

Phase 2 put the bridge into production and immediately exposed the flaw: the
manifest lived in a process-local dict, production runs fifteen gunicorn workers,
and the manifest landed in one of them. About one request in fifteen could see
it - which presents as intermittent rather than broken, the worst way for
something to be wrong. Byte retrieval could not work at all.

So StorageBridge/BridgeRegistry were DELETED, not deprecated. The manifest moved
to ProjectWorkspace.external_manifest (project data, dies with the project) and
the byte queue to services/bridge_queue.py (transient coordination on the shared
filesystem). Every property the in-memory version claimed has to be re-proven
against the durable one, which is what this file is for - a relocated test that
was never re-argued is just an old assertion in a new place.

WHY NO MOCKING OF THE WORKER BOUNDARY

The bug WAS shared memory, so a test that shares memory cannot detect it. These
use separately constructed store objects and, for the claim race, real
multiprocessing - because os.rename's atomicity is a guarantee of the operating
system, not of Python, and only real processes exercise it.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import multiprocessing
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from services.bridge_queue import (
    KNOWN_PURPOSES,
    PURPOSE_EXTRACT_TEXT,
    PURPOSE_PDF_GEOMETRY,
    PURPOSE_REGISTER_SOURCE,
    BridgeQueueError,
    BridgeQueueStore,
)

_ROOT = Path(__file__).resolve().parent.parent
_PROJECT = "wd-durable"


def _claim_in_subprocess(store_path, project_id, result_queue):
    """Runs in a REAL separate process - the only honest test of rename()."""
    store = BridgeQueueStore(store_path)
    claimed = store.claim_pending(project_id)
    result_queue.put([record["id"] for record in claimed])


class _Queue(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bridge-queue-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.queue = BridgeQueueStore(self.dir)


class AnyWorkerSeesWhatAnotherWrote(_Queue):
    """The defect Phase 2 exposed, asserted directly."""

    def test_a_request_enqueued_by_one_store_is_visible_to_another(self):
        record = self.queue.enqueue(_PROJECT, "drawings/A-101.pdf", PURPOSE_EXTRACT_TEXT)
        # A SEPARATE object over the same directory - the stand-in for another
        # gunicorn worker, sharing nothing but the filesystem.
        other_worker = BridgeQueueStore(self.dir)
        self.assertEqual([r["id"] for r in other_worker.pending_for(_PROJECT)],
                         [record["id"]])

    def test_a_delivery_by_one_worker_is_consumable_by_a_third(self):
        payload = b"%PDF-1.4 drawing"
        record = self.queue.enqueue(_PROJECT, "drawings/A-101.pdf", PURPOSE_PDF_GEOMETRY)
        BridgeQueueStore(self.dir).claim_pending(_PROJECT)
        BridgeQueueStore(self.dir).deliver(record["id"], payload)
        served, bytes_back = BridgeQueueStore(self.dir).consume(record["id"])
        self.assertEqual(bytes_back, payload)
        self.assertEqual(served["relative_path"], "drawings/A-101.pdf")

    def test_no_module_level_state_backs_any_of_it(self):
        for module_name in ("services.bridge_queue", "services.storage_agent_access"):
            module = __import__(module_name, fromlist=["x"])
            tree = ast.parse(inspect.getsource(module))
            mutable = []
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    if isinstance(value, (ast.Dict, ast.List, ast.Set)):
                        mutable.append(module_name)
            self.assertEqual(mutable, [], "%s holds module-level mutable state" % module_name)

    def test_the_deleted_in_memory_classes_are_really_gone(self):
        # Deprecating them would leave two implementations of one protocol -
        # the duplication this work already had to converge away from once.
        import services.storage_bridge as module

        for dead in ("StorageBridge", "BridgeRegistry", "ByteRequest"):
            self.assertFalse(hasattr(module, dead), "%s survived" % dead)


class ClaimingIsAtomicAcrossRealProcesses(_Queue):
    def test_exactly_one_of_four_processes_wins_a_single_request(self):
        record = self.queue.enqueue(_PROJECT, "drawings/A-101.pdf", PURPOSE_REGISTER_SOURCE)
        results = multiprocessing.Queue()
        workers = [
            multiprocessing.Process(target=_claim_in_subprocess,
                                    args=(self.dir, _PROJECT, results))
            for _ in range(4)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=30)
        claimed = []
        while not results.empty():
            claimed.extend(results.get())
        self.assertEqual(claimed, [record["id"]],
                         "os.rename must produce exactly one winner")

    def test_a_second_claim_in_the_same_process_finds_nothing(self):
        self.queue.enqueue(_PROJECT, "drawings/A-101.pdf", PURPOSE_EXTRACT_TEXT)
        self.assertEqual(len(self.queue.claim_pending(_PROJECT)), 1)
        self.assertEqual(self.queue.claim_pending(_PROJECT), [])


class ProjectScopingSurvivesASharedDirectory(_Queue):
    def test_one_project_never_claims_another_s_work(self):
        mine = self.queue.enqueue("project-a", "a.pdf", PURPOSE_EXTRACT_TEXT)
        self.queue.enqueue("project-b", "b.pdf", PURPOSE_EXTRACT_TEXT)
        claimed = self.queue.claim_pending("project-a")
        self.assertEqual([r["id"] for r in claimed], [mine["id"]])
        self.assertEqual(len(self.queue.pending_for("project-b")), 1)

    def test_purging_one_project_leaves_the_other_intact(self):
        self.queue.enqueue("project-a", "a.pdf", PURPOSE_EXTRACT_TEXT)
        self.queue.enqueue("project-b", "b.pdf", PURPOSE_EXTRACT_TEXT)
        self.assertEqual(self.queue.purge_project("project-a"), 1)
        self.assertEqual(self.queue.pending_for("project-a"), [])
        self.assertEqual(len(self.queue.pending_for("project-b")), 1)


class ThePurposeVocabularyIsClosed(_Queue):
    def test_only_the_three_declared_purposes_are_accepted(self):
        self.assertEqual(sorted(KNOWN_PURPOSES),
                         ["extract_text", "pdf_geometry", "register_source"])
        for purpose in KNOWN_PURPOSES:
            with self.subTest(purpose=purpose):
                self.assertTrue(self.queue.enqueue(_PROJECT, "a.pdf", purpose)["id"])

    def test_an_unknown_purpose_is_refused_at_enqueue_not_later(self):
        # An open-world purpose would let any future caller push arbitrary work
        # through the byte queue by naming it - a capability boundary, not a
        # naming convention. Checked where it is declared.
        for bad in ("exfiltrate", "", "REGISTER_SOURCE", None):
            with self.subTest(purpose=bad):
                with self.assertRaises(BridgeQueueError):
                    self.queue.enqueue(_PROJECT, "a.pdf", bad)

    def test_the_purpose_travels_with_the_request(self):
        self.queue.enqueue(_PROJECT, "a.pdf", PURPOSE_PDF_GEOMETRY)
        self.assertEqual(self.queue.claim_pending(_PROJECT)[0]["purpose"],
                         PURPOSE_PDF_GEOMETRY)


class BytesAreStagedAndDestroyed(_Queue):
    PAYLOAD = b"%PDF-1.4 authoritative bytes"

    def _delivered(self):
        record = self.queue.enqueue(_PROJECT, "drawings/A-101.pdf", PURPOSE_EXTRACT_TEXT)
        self.queue.claim_pending(_PROJECT)
        self.queue.deliver(record["id"], self.PAYLOAD)
        return record

    def test_a_payload_is_readable_exactly_once(self):
        record = self._delivered()
        self.assertTrue(self.queue.holds_payload(record["id"]))
        _served, payload = self.queue.consume(record["id"])
        self.assertEqual(payload, self.PAYLOAD)
        with self.assertRaises(BridgeQueueError):
            self.queue.consume(record["id"])

    def test_the_staged_file_is_gone_from_disk_after_consumption(self):
        record = self._delivered()
        self.queue.consume(record["id"])
        self.assertFalse(self.queue.holds_payload(record["id"]))
        leftovers = [p for p in Path(self.dir).rglob("*.bytes")]
        self.assertEqual(leftovers, [])

    def test_no_copy_of_the_payload_survives_anywhere_under_the_store(self):
        record = self._delivered()
        self.queue.consume(record["id"])
        for path in Path(self.dir).rglob("*"):
            if path.is_file():
                self.assertNotIn(self.PAYLOAD, path.read_bytes())

    def test_delivering_against_an_unclaimed_request_is_refused(self):
        record = self.queue.enqueue(_PROJECT, "a.pdf", PURPOSE_EXTRACT_TEXT)
        with self.assertRaises(BridgeQueueError):
            self.queue.deliver(record["id"], self.PAYLOAD)

    def test_an_unknown_request_id_is_refused(self):
        with self.assertRaises(BridgeQueueError):
            self.queue.deliver("req-nope", self.PAYLOAD)


class AbandonedWorkExpires(_Queue):
    def test_a_claim_a_dead_worker_never_answered_is_swept(self):
        queue = BridgeQueueStore(self.dir, claim_ttl_seconds=60)
        record = queue.enqueue(_PROJECT, "a.pdf", PURPOSE_EXTRACT_TEXT, now=1000.0)
        queue.claim_pending(_PROJECT, now=1000.0)
        self.assertEqual(len(queue.claimed_for(_PROJECT)), 1)
        queue.sweep_expired(now=1000.0 + 61)
        self.assertEqual(queue.claimed_for(_PROJECT), [])

    def test_a_swept_claim_takes_its_staged_payload_with_it(self):
        queue = BridgeQueueStore(self.dir, claim_ttl_seconds=60)
        record = queue.enqueue(_PROJECT, "a.pdf", PURPOSE_EXTRACT_TEXT, now=1000.0)
        queue.claim_pending(_PROJECT, now=1000.0)
        queue.deliver(record["id"], b"payload", now=1000.0)
        queue.sweep_expired(now=1000.0 + 61)
        self.assertFalse(queue.holds_payload(record["id"]))

    def test_a_request_nobody_ever_claimed_expires_too(self):
        queue = BridgeQueueStore(self.dir, request_ttl_seconds=30)
        queue.enqueue(_PROJECT, "a.pdf", PURPOSE_EXTRACT_TEXT, now=1000.0)
        queue.sweep_expired(now=1000.0 + 31)
        self.assertEqual(queue.pending_for(_PROJECT), [])

    def test_a_corrupt_record_is_swept_rather_than_raised(self):
        # A partially written file must not break an agent's poll.
        (Path(self.dir) / "_bridge_queue" / "pending" / "broken.json").write_text("{oh no")
        self.assertGreaterEqual(self.queue.sweep_expired(), 1)
        self.assertEqual(self.queue.pending_for(_PROJECT), [])


class TheManifestLivesOnTheProjectRecord(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.case_workspace import CaseWorkspaceStore

        self.dir = tempfile.mkdtemp(prefix="bridge-manifest-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.store = CaseWorkspaceStore(self.dir)
        self.workspace = self.store.get_or_create(_PROJECT)

    def _entries(self):
        from services.storage_bridge import ManifestEntry

        payload = b"# requirements\n"
        return [ManifestEntry("specs/Requirements.md", len(payload),
                              "2026-08-27T12:00:00+00:00",
                              hashlib.sha256(payload).hexdigest())]

    def test_it_is_readable_through_a_separately_constructed_store(self):
        from services.case_workspace import CaseWorkspaceStore
        from services.storage_bridge import manifest_digest

        entries = self._entries()
        self.store.record_external_manifest(
            self.workspace, [e.as_dict() for e in entries], manifest_digest(entries))
        other_worker = CaseWorkspaceStore(self.dir).get(_PROJECT)
        self.assertEqual(len(other_worker.external_manifest), 1)
        self.assertEqual(other_worker.external_manifest_digest, manifest_digest(entries))
        self.assertIsNotNone(other_worker.external_manifest_recorded_at)

    def test_it_holds_no_file_contents(self):
        entries = self._entries()
        self.store.record_external_manifest(self.workspace,
                                            [e.as_dict() for e in entries], "d" * 64)
        blob = str(self.store.get(_PROJECT).external_manifest)
        self.assertNotIn("requirements", blob.lower().replace("requirements.md", ""))
        for row in self.store.get(_PROJECT).external_manifest:
            self.assertEqual(sorted(row), ["mtime_iso", "relative_path", "sha256", "size_bytes"])

    def test_a_project_with_no_agent_has_an_empty_manifest(self):
        self.assertEqual(self.store.get(_PROJECT).external_manifest, [])
        self.assertIsNone(self.store.get(_PROJECT).external_manifest_digest)


class TheManifestBecomesReconcileDescriptors(unittest.TestCase):
    """Slice A's whole purpose, joined up."""

    def setUp(self):
        import app as app_module
        from services.case_workspace import CaseWorkspaceStore

        self.dir = tempfile.mkdtemp(prefix="bridge-adapter-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.store = CaseWorkspaceStore(self.dir)
        self.workspace = self.store.get_or_create(_PROJECT)
        self.payload = b"# Doors\n\nRated assemblies.\n"
        self.store.record_external_manifest(self.workspace, [{
            "relative_path": "specs/Section_08.md",
            "size_bytes": len(self.payload),
            "mtime_iso": "2026-08-27T12:00:00+00:00",
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }], "d" * 64)

    def test_the_adapter_produces_usable_descriptors(self):
        from services.storage_agent_access import descriptors_for_manifest

        descriptors = descriptors_for_manifest(_PROJECT, app=self.app)
        self.assertEqual(len(descriptors), 1)
        self.assertEqual(descriptors[0].relative_path, "specs/Section_08.md")
        self.assertEqual(descriptors[0].filename, "Section_08.md")
        self.assertEqual(descriptors[0].sha256,
                         hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(descriptors[0].size_bytes, len(self.payload))

    def test_reconcile_classifies_a_manifest_with_no_bytes_at_all(self):
        from services.ingestion import classify_reconcile_descriptors
        from services.storage_agent_access import descriptors_for_manifest

        with self.app.app_context():
            report, new = classify_reconcile_descriptors(
                descriptors_for_manifest(_PROJECT, app=self.app), _PROJECT, self.app)
        self.assertEqual(report["summary"]["new"], 1)
        self.assertEqual(len(new), 1)

    def test_the_adapter_lives_where_the_coupling_was_confined(self):
        # Neither ingestion nor storage_bridge may learn about the other.
        import services.ingestion as ingestion
        import services.storage_bridge as bridge

        self.assertNotIn("storage_bridge", inspect.getsource(ingestion))
        self.assertNotIn("ingestion", inspect.getsource(bridge))


if __name__ == "__main__":
    unittest.main()
