"""
CLAUDE-CHUNKED-UPLOAD-01 - a Source that arrives in pieces is the same Source.

WHAT THIS HAS TO PROVE

Two things, and the second matters more than the first.

That it WORKS: chunks land, assemble in order, and the digest of the assembled
file equals the digest of the original bytes.

That it produces NOTHING DIFFERENT. The chunked path is a transport for the
existing add_document_source, not a second way to create a Source. If a chunked
document were registered with a different kind, origin_type, or governance event
than a single-request one, provenance would depend on how a file happened to be
delivered - which is exactly the kind of silent divergence a second ingestion
path invites. TheChunkedSourceIsIndistinguishableTests asserts that directly,
against a Source created the ordinary way in the same test.

Hermetic: BHiveParser._extract and .parse are stubbed throughout (CLAUDE.md -
an un-mocked ingest once cost a single background run 8.5 hours).
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.chunked_upload import (
    ChunkedUploadError, ChunkedUploadStore, STAGING_SUBDIR, STAGING_TTL_SECONDS,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _Base(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_chunked_upload_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    _file(b"owner baseline", "owner-program.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Chunked Upload Fixture",
                )
        self.project_id = document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.staging = ChunkedUploadStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="owner", role="read_only", authenticated=True):
        client = self.app.test_client()
        if authenticated:
            with client.session_transaction() as session:
                session["user_id"] = 1
                session["username"] = username
                session["role"] = role
        return client

    def _upload_chunks(self, payload, name="drawings.pdf", chunk_size=8,
                       project_id=None, client=None, upload_id=None):
        """Slice `payload` and POST every chunk. Returns (upload_id, responses)."""
        project_id = project_id or self.project_id
        client = client or self._client()
        upload_id = upload_id or uuid.uuid4().hex
        chunks = [payload[i:i + chunk_size] for i in range(0, len(payload), chunk_size)] or [b""]
        responses = []
        for index, chunk in enumerate(chunks):
            responses.append(client.post(
                f"/projects/{project_id}/workspace/sources/upload-chunk",
                data={
                    "chunk": _file(chunk, name),
                    "upload_id": upload_id,
                    "chunk_index": str(index),
                    "total_chunks": str(len(chunks)),
                    "filename": name,
                },
                content_type="multipart/form-data",
            ))
        return upload_id, responses, len(chunks)

    def _complete(self, upload_id, total, name="drawings.pdf", project_id=None,
                  client=None, sha256=None):
        project_id = project_id or self.project_id
        client = client or self._client()
        data = {"upload_id": upload_id, "filename": name, "total_chunks": str(total)}
        if sha256 is not None:
            data["sha256"] = sha256
        with patch.object(BHiveParser, "_extract", return_value="Drawing set text"):
            return client.post(
                f"/projects/{project_id}/workspace/sources/upload-complete",
                data=data, content_type="multipart/form-data",
            )


class EndToEndTests(_Base):
    def test_multi_chunk_upload_assembles_and_verifies(self):
        payload = b"%PDF-1.4 " + bytes(range(256)) * 40      # 10k+, many chunks
        upload_id, responses, total = self._upload_chunks(payload, chunk_size=1024)

        self.assertGreater(total, 1, "the fixture must actually be multi-chunk")
        for response in responses:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(responses[-1].get_json()["received"], total)

        completed = self._complete(upload_id, total)
        self.assertEqual(completed.status_code, 200)
        body = completed.get_json()

        self.assertTrue(body["ok"])
        self.assertEqual(body["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(body["size_bytes"], len(payload))

    def test_the_assembled_bytes_are_byte_identical_to_the_original(self):
        payload = bytes(range(256)) * 97          # deliberately not chunk-aligned
        upload_id, _, total = self._upload_chunks(payload, chunk_size=1000)
        self._complete(upload_id, total)

        workspace = self.store.get(self.project_id)
        source = [s for s in workspace.sources if s["name"] == "drawings.pdf"][0]
        self.assertEqual(Path(source["file_path"]).read_bytes(), payload)

    def test_progress_counts_climb_with_each_chunk(self):
        payload = b"x" * 50
        _, responses, total = self._upload_chunks(payload, chunk_size=10)
        received = [r.get_json()["received"] for r in responses]
        self.assertEqual(received, list(range(1, total + 1)))

    def test_staging_directory_is_cleaned_after_success(self):
        payload = b"y" * 40
        upload_id, _, total = self._upload_chunks(payload, chunk_size=10)
        staged = self.tmp / STAGING_SUBDIR / upload_id
        self.assertTrue(staged.exists())
        self._complete(upload_id, total)
        self.assertFalse(staged.exists(), "staged chunks must not outlive the Source")


class TheChunkedSourceIsIndistinguishableTests(_Base):
    """The property that makes this a transport rather than a second ingestion."""

    def _single_request_source(self, name="single.pdf", content=b"single bytes"):
        with patch.object(BHiveParser, "_extract", return_value="text"):
            self._client().post(
                f"/projects/{self.project_id}/workspace/sources/document",
                data={"document": _file(content, name)},
                content_type="multipart/form-data", follow_redirects=True,
            )
        workspace = self.store.get(self.project_id)
        return [s for s in workspace.sources if s["name"] == name][0]

    def test_kind_and_origin_match_a_single_request_upload(self):
        ordinary = self._single_request_source()
        upload_id, _, total = self._upload_chunks(b"chunked bytes here", chunk_size=5)
        self._complete(upload_id, total)

        workspace = self.store.get(self.project_id)
        chunked = [s for s in workspace.sources if s["name"] == "drawings.pdf"][0]

        self.assertEqual(chunked["kind"], ordinary["kind"])
        self.assertEqual(chunked["origin_type"], ordinary["origin_type"])
        self.assertIsNone(chunked.get("removed_at"))

    def test_it_emits_the_same_source_registered_governance_event(self):
        upload_id, _, total = self._upload_chunks(b"governed bytes", chunk_size=6)
        self._complete(upload_id, total)

        log_path = self.tmp / f"{self.project_id}.governance.jsonl"
        events = [json.loads(line) for line in
                  log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        registered = [e for e in events if e["event_type"] == "source_registered"]
        self.assertTrue(registered, "a chunked upload must be governed like any other")

    def test_the_recorded_hash_is_the_hash_of_the_stored_file(self):
        payload = b"integrity matters" * 11
        upload_id, _, total = self._upload_chunks(payload, chunk_size=7)
        self._complete(upload_id, total)

        workspace = self.store.get(self.project_id)
        source = [s for s in workspace.sources if s["name"] == "drawings.pdf"][0]
        on_disk = hashlib.sha256(Path(source["file_path"]).read_bytes()).hexdigest()
        self.assertEqual(source["file_hash"], on_disk)
        self.assertEqual(source["file_hash"], hashlib.sha256(payload).hexdigest())


class AuthorizationTests(_Base):
    def test_unauthenticated_chunk_is_refused(self):
        client = self._client(authenticated=False)
        response = client.post(
            f"/projects/{self.project_id}/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.pdf"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "0", "total_chunks": "1", "filename": "a.pdf"},
            content_type="multipart/form-data")
        self.assertIn(response.status_code, (302, 401, 403))

    def test_unauthenticated_complete_is_refused(self):
        client = self._client(authenticated=False)
        response = client.post(
            f"/projects/{self.project_id}/workspace/sources/upload-complete",
            data={"upload_id": uuid.uuid4().hex, "filename": "a.pdf", "total_chunks": "1"},
            content_type="multipart/form-data")
        self.assertIn(response.status_code, (302, 401, 403))

    def test_upload_to_an_unknown_project_is_404(self):
        response = self._client().post(
            "/projects/not-a-real-project/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.pdf"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "0", "total_chunks": "1", "filename": "a.pdf"},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 404)

    def test_a_second_project_cannot_complete_another_projects_upload(self):
        """Cross-project reach is inexpressible, not merely refused."""
        upload_id, _, total = self._upload_chunks(b"project A bytes", chunk_size=5)

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                other = ingest_upload(
                    _file(b"other", "other.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Chunked Upload Other",
                )
        response = self._complete(upload_id, total, project_id=other.project_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "assembly_failed")

        # And nothing was written into the other project. Asserted by NAME,
        # not by count: the fixture project legitimately already holds the
        # baseline document ingest_upload created it with.
        other_names = [s["name"] for s in self.store.get(other.project_id).sources]
        self.assertNotIn("drawings.pdf", other_names)


class InvalidInputTests(_Base):
    def test_chunk_index_beyond_total_is_rejected(self):
        response = self._client().post(
            f"/projects/{self.project_id}/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.pdf"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "5", "total_chunks": "3", "filename": "a.pdf"},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_chunk")

    def test_negative_chunk_index_is_rejected(self):
        response = self._client().post(
            f"/projects/{self.project_id}/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.pdf"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "-1", "total_chunks": "3", "filename": "a.pdf"},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_chunk_index_is_rejected(self):
        response = self._client().post(
            f"/projects/{self.project_id}/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.pdf"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "../../etc", "total_chunks": "3", "filename": "a.pdf"},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_unsupported_extension_is_rejected_at_the_first_chunk(self):
        response = self._client().post(
            f"/projects/{self.project_id}/workspace/sources/upload-chunk",
            data={"chunk": _file(b"x", "a.exe"), "upload_id": uuid.uuid4().hex,
                  "chunk_index": "0", "total_chunks": "1", "filename": "a.exe"},
            content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "unsupported_format")

    def test_completing_with_a_missing_chunk_is_refused(self):
        payload = b"z" * 40
        client = self._client()
        upload_id = uuid.uuid4().hex
        # Deliberately skip index 2.
        for index in (0, 1, 3):
            client.post(
                f"/projects/{self.project_id}/workspace/sources/upload-chunk",
                data={"chunk": _file(b"zzzzzzzzzz", "drawings.pdf"),
                      "upload_id": upload_id, "chunk_index": str(index),
                      "total_chunks": "4", "filename": "drawings.pdf"},
                content_type="multipart/form-data")

        response = self._complete(upload_id, 4)
        self.assertEqual(response.status_code, 400)
        self.assertIn("missing chunk", response.get_json()["message"])
        names = [s["name"] for s in self.store.get(self.project_id).sources]
        self.assertNotIn("drawings.pdf", names,
                         "an incomplete upload must not become a Source")

    def test_a_client_digest_mismatch_discards_the_file(self):
        payload = b"tampered" * 20
        upload_id, _, total = self._upload_chunks(payload, chunk_size=9)
        response = self._complete(upload_id, total, sha256="0" * 64)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "integrity_failed")
        names = [s["name"] for s in self.store.get(self.project_id).sources]
        self.assertNotIn("drawings.pdf", names,
                         "a file failing its digest must not become a Source")

    def test_a_matching_client_digest_is_accepted(self):
        payload = b"honest" * 30
        upload_id, _, total = self._upload_chunks(payload, chunk_size=11)
        response = self._complete(upload_id, total,
                                  sha256=hashlib.sha256(payload).hexdigest())
        self.assertEqual(response.status_code, 200)


class StoreLevelGuardTests(unittest.TestCase):
    """The path and identity guards, asserted directly against the store."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_chunk_store_"))
        self.store = ChunkedUploadStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_traversal_in_upload_id_is_refused(self):
        for bad in ("../escape", "..", "a/b", "\\", "x" * 31, "X" * 32, "", "g" * 32):
            with self.subTest(upload_id=bad):
                with self.assertRaises(ChunkedUploadError):
                    self.store.save_chunk("p", bad, 0, 1, "a.pdf", b"data")

    def test_a_valid_id_never_escapes_the_staging_directory(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 1, "a.pdf", b"data")
        staged = (self.tmp / STAGING_SUBDIR / upload_id).resolve()
        self.assertEqual(staged.parent, (self.tmp / STAGING_SUBDIR).resolve())

    def test_filename_is_sanitised(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 1, "../../evil.pdf", b"data")
        manifest = json.loads(
            (self.tmp / STAGING_SUBDIR / upload_id / "manifest.json").read_text())
        self.assertNotIn("..", manifest["filename"])
        self.assertNotIn("/", manifest["filename"])

    def test_a_mismatched_total_is_refused(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 3, "a.pdf", b"data")
        with self.assertRaises(ChunkedUploadError):
            self.store.save_chunk("p", upload_id, 1, 9, "a.pdf", b"data")

    def test_a_mismatched_filename_is_refused(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 2, "a.pdf", b"data")
        with self.assertRaises(ChunkedUploadError):
            self.store.save_chunk("p", upload_id, 1, 2, "b.pdf", b"data")

    def test_another_project_cannot_append_to_an_upload(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("project-a", upload_id, 0, 2, "a.pdf", b"data")
        with self.assertRaises(ChunkedUploadError):
            self.store.save_chunk("project-b", upload_id, 1, 2, "a.pdf", b"data")

    def test_an_empty_chunk_is_refused(self):
        with self.assertRaises(ChunkedUploadError):
            self.store.save_chunk("p", uuid.uuid4().hex, 0, 1, "a.pdf", b"")

    def test_assembly_refuses_to_exceed_the_ceiling(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 1, "a.pdf", b"x" * 1000)
        with self.assertRaises(ChunkedUploadError):
            self.store.assemble("p", upload_id, "a.pdf", 1,
                                self.tmp / "out.pdf", max_total_bytes=10)

    def test_a_failed_assembly_leaves_no_partial_destination(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 1, "a.pdf", b"x" * 1000)
        destination = self.tmp / "out.pdf"
        with self.assertRaises(ChunkedUploadError):
            self.store.assemble("p", upload_id, "a.pdf", 1, destination,
                                max_total_bytes=10)
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_name(destination.name + ".assembling").exists())

    def test_a_retried_chunk_overwrites_atomically(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 1, "a.pdf", b"first attempt")
        self.store.save_chunk("p", upload_id, 0, 1, "a.pdf", b"second")
        destination = self.tmp / "out.pdf"
        self.store.assemble("p", upload_id, "a.pdf", 1, destination,
                            max_total_bytes=1024)
        self.assertEqual(destination.read_bytes(), b"second")
        self.assertEqual(
            list((self.tmp / STAGING_SUBDIR / upload_id).glob("*.tmp")), [],
            "no temp file may survive a completed write")


class ExpiryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_chunk_expiry_"))
        self.store = ChunkedUploadStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_fresh_upload_is_not_swept(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 2, "a.pdf", b"data")
        self.assertEqual(self.store.sweep_expired(), [])
        self.assertTrue((self.tmp / STAGING_SUBDIR / upload_id).exists())

    def test_an_abandoned_upload_older_than_24h_is_swept(self):
        upload_id = uuid.uuid4().hex
        self.store.save_chunk("p", upload_id, 0, 2, "a.pdf", b"data")
        later = time.time() + STAGING_TTL_SECONDS + 60
        removed = self.store.sweep_expired(now=later)
        self.assertIn(upload_id, removed)
        self.assertFalse((self.tmp / STAGING_SUBDIR / upload_id).exists())

    def test_an_orphan_directory_without_a_manifest_is_still_swept(self):
        # An interrupted first chunk can leave a directory with no manifest.
        # Falling back to mtime is what stops it living forever.
        orphan = self.tmp / STAGING_SUBDIR / uuid.uuid4().hex
        orphan.mkdir(parents=True)
        removed = self.store.sweep_expired(now=time.time() + STAGING_TTL_SECONDS + 60)
        self.assertIn(orphan.name, removed)
        self.assertFalse(orphan.exists())

    def test_starting_a_new_upload_sweeps_expired_ones(self):
        stale = uuid.uuid4().hex
        self.store.save_chunk("p", stale, 0, 2, "a.pdf", b"data")
        manifest_path = self.tmp / STAGING_SUBDIR / stale / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = time.time() - STAGING_TTL_SECONDS - 60
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.store.save_chunk("p", uuid.uuid4().hex, 0, 1, "b.pdf", b"new")
        self.assertFalse((self.tmp / STAGING_SUBDIR / stale).exists(),
                         "a new upload must collect abandoned ones")


if __name__ == "__main__":
    unittest.main()
