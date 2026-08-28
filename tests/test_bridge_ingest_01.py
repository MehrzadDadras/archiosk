"""
CLAUDE-BRIDGE-INGEST-01 - manifest to governed Source, without ARCHIOSK ever
holding the file.

THE CHAIN THIS CLOSES

    agent walks private storage  ->  manifest (metadata only)
    Reconcile classifies from hashes alone (no bytes cross)
    NEW files -> one byte request each
    agent delivers -> derivatives registered -> payload destroyed

The interesting property is what does NOT happen. On a real drawing set most
files are UNCHANGED, and the classification proves that from the manifest, so
their bytes never cross the network at all. Retrieval is the exception, not the
sync.

WHY MODIFIED IS NOT ENQUEUED

ingestion.preview_data_room_reconcile's contract says a modified file is "never
auto-registered as a second Source and never overwrites the first - a human
decision this pass does not yet offer an action for". Pulling its bytes would
carry content across the boundary that nothing is permitted to act on, so this
path leaves it alone and reports the count. That is a real constraint inherited
from the Data Room's own semantics, not an omission here, and it is asserted
below so a later change has to face it deliberately.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bridge_queue import BridgeQueueStore, PURPOSE_REGISTER_SOURCE
from services.external_source import ExternalSourceError
from services.storage_agent_access import (
    ingest_delivered_bytes, reconcile_external_manifest, reset_bridges_for_testing,
)

_PROJECT = "bridge-ingest"

_CORPUS = {
    "drawings/A-101.pdf": b"%PDF-1.4 first floor plan",
    "schedules/Door_Schedule.csv": b"Mark,Rating\nD-101,45 MIN\n",
    "specs/Section_08.md": b"# Doors\n\nRated assemblies.\n",
}


def _entry(path, payload):
    return {"relative_path": path, "size_bytes": len(payload),
            "mtime_iso": "2026-08-28T09:00:00+00:00",
            "sha256": hashlib.sha256(payload).hexdigest()}


class _Bridged(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.case_workspace import CaseWorkspaceStore

        self.dir = tempfile.mkdtemp(prefix="bridge-ingest-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        self.addCleanup(reset_bridges_for_testing, self.app)

        self.store = CaseWorkspaceStore(self.dir)
        self.workspace = self.store.get_or_create(_PROJECT)
        self.publish(_CORPUS)
        self.queue = BridgeQueueStore(self.dir)

    def publish(self, files):
        entries = [_entry(path, payload) for path, payload in sorted(files.items())]
        self.store.record_external_manifest(
            self.store.get(_PROJECT), entries, "d" * 64)

    def sources(self):
        return self.store.get(_PROJECT).sources

    def deliver_and_ingest(self, record, payload):
        self.queue.claim_pending(_PROJECT)
        self.queue.deliver(record["id"], payload)
        return ingest_delivered_bytes(_PROJECT, record["id"], app=self.app)


class NewFilesEnqueueExactlyOneRequestEach(_Bridged):
    def test_three_new_files_produce_three_requests(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual(len(result["enqueued"]), 3)
        self.assertEqual(
            sorted(r["relative_path"] for r in result["enqueued"]), sorted(_CORPUS))

    def test_every_request_carries_the_register_source_purpose(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual({r["purpose"] for r in result["enqueued"]},
                         {PURPOSE_REGISTER_SOURCE})

    def test_a_second_confirm_does_not_double_queue(self):
        # A reviewer clicking twice, or two workers confirming, must not make
        # the agent fetch the same file twice.
        first = reconcile_external_manifest(_PROJECT, app=self.app)
        second = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual(len(first["enqueued"]), 3)
        self.assertEqual(second["enqueued"], [])
        self.assertEqual(len(self.queue.pending_for(_PROJECT)), 3)

    def test_nothing_is_registered_before_bytes_arrive(self):
        reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual(self.sources(), [])


class UnchangedFilesNeverCrossTheNetwork(_Bridged):
    def test_a_registered_file_is_not_requested_again(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])
        self.assertEqual(len(self.sources()), 3)

        # Same manifest, second pass: everything is UNCHANGED now.
        again = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual(again["enqueued"], [])
        self.assertEqual(again["report"]["summary"]["unchanged"], 3)
        self.assertEqual(again["report"]["summary"]["new"], 0)

    def test_only_the_genuinely_new_file_is_requested(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])

        extra = dict(_CORPUS)
        extra["specs/Section_09.md"] = b"# Glazing\n"
        self.publish(extra)
        second = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual([r["relative_path"] for r in second["enqueued"]],
                         ["specs/Section_09.md"])

    def test_a_renamed_file_is_not_re_fetched(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])

        moved = {k: v for k, v in _CORPUS.items() if k != "drawings/A-101.pdf"}
        moved["archive/A-101_Rev1.pdf"] = _CORPUS["drawings/A-101.pdf"]
        self.publish(moved)
        second = reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual(second["enqueued"], [])
        self.assertEqual(second["report"]["summary"]["renamed"], 1)


class ModifiedFilesAreReportedNotFetched(_Bridged):
    def test_a_changed_file_enqueues_nothing_and_is_counted(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])

        changed = dict(_CORPUS)
        changed["specs/Section_08.md"] = b"# Doors\n\nRevised assemblies.\n"
        self.publish(changed)
        second = reconcile_external_manifest(_PROJECT, app=self.app)

        self.assertEqual(second["enqueued"], [])
        self.assertEqual(second["modified_not_enqueued"], 1)
        self.assertEqual(second["report"]["summary"]["modified"], 1)

    def test_the_original_source_is_neither_replaced_nor_duplicated(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])
        before = {s["id"]: s["file_hash"] for s in self.sources()}

        changed = dict(_CORPUS)
        changed["specs/Section_08.md"] = b"# Doors\n\nRevised.\n"
        self.publish(changed)
        reconcile_external_manifest(_PROJECT, app=self.app)
        self.assertEqual({s["id"]: s["file_hash"] for s in self.sources()}, before)


class DeliveryProducesGovernedDerivatives(_Bridged):
    def test_a_source_is_registered_under_external_custody(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        result = self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])
        source = result["source"]
        self.assertIsNone(source["file_path"])          # the custody claim itself
        self.assertEqual(source["origin_type"], "external_connector")
        self.assertEqual(source["origin_reference"], record["relative_path"])

    def test_the_hash_matches_what_the_manifest_advertised(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        payload = _CORPUS[record["relative_path"]]
        result = self.deliver_and_ingest(record, payload)
        self.assertEqual(result["source"]["file_hash"],
                         hashlib.sha256(payload).hexdigest())

    def test_the_source_survives_a_reload_from_disk(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        result = self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])
        reloaded = [s for s in self.store.get(_PROJECT).sources
                    if s["id"] == result["source"]["id"]]
        self.assertEqual(len(reloaded), 1)

    def test_the_request_reaches_served_and_cannot_be_ingested_twice(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])
        from services.bridge_queue import BridgeQueueError

        with self.assertRaises(BridgeQueueError):
            ingest_delivered_bytes(_PROJECT, record["id"], app=self.app)

    def test_another_project_cannot_ingest_this_request(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        self.queue.claim_pending(_PROJECT)
        self.queue.deliver(record["id"], _CORPUS[record["relative_path"]])
        with self.assertRaises(ExternalSourceError):
            ingest_delivered_bytes("some-other-project", record["id"], app=self.app)


class NoRawBytesSurviveOnDisk(_Bridged):
    def test_the_whole_corpus_ingests_leaving_no_payload_anywhere(self):
        result = reconcile_external_manifest(_PROJECT, app=self.app)
        for record in result["enqueued"]:
            self.deliver_and_ingest(record, _CORPUS[record["relative_path"]])

        self.assertEqual(len(self.sources()), 3)
        self.assertEqual(list(Path(self.dir).rglob("*.bytes")), [])
        for path in Path(self.dir).rglob("*"):
            if path.is_file():
                blob = path.read_bytes()
                for payload in _CORPUS.values():
                    self.assertNotIn(payload, blob)

    def test_a_payload_is_gone_even_if_ingestion_is_the_only_reader(self):
        record = reconcile_external_manifest(_PROJECT, app=self.app)["enqueued"][0]
        self.queue.claim_pending(_PROJECT)
        self.queue.deliver(record["id"], _CORPUS[record["relative_path"]])
        self.assertTrue(self.queue.holds_payload(record["id"]))
        ingest_delivered_bytes(_PROJECT, record["id"], app=self.app)
        self.assertFalse(self.queue.holds_payload(record["id"]))

    def test_an_unknown_purpose_is_refused_rather_than_guessed(self):
        from services.bridge_queue import PURPOSE_PDF_GEOMETRY

        record = self.queue.enqueue(_PROJECT, "drawings/A-101.pdf",
                                    PURPOSE_PDF_GEOMETRY)
        self.queue.claim_pending(_PROJECT)
        self.queue.deliver(record["id"], _CORPUS["drawings/A-101.pdf"])
        with self.assertRaises(ExternalSourceError):
            ingest_delivered_bytes(_PROJECT, record["id"], app=self.app)


if __name__ == "__main__":
    unittest.main()
