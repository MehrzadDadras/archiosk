"""
CLAUDE-RECONCILE-DESCRIPTORS-01 - Reconcile without the bytes.

WHY

Reconcile classifies by extension, size and content hash, and read bytes solely
to derive the last two. A private-storage manifest already carries both, so the
same classification is available for storage ARCHIOSK never touches - but only
if there is ONE classifier. A manifest-shaped sibling function would drift from
the Data Room's the first time either changed, which is the duplication the
storage-bridge work already deleted once.

So the rules moved into classify_reconcile_descriptors and
preview_data_room_reconcile became an adapter over it. Its signature, return
shape and verdicts are unchanged, which is what the bulk of this file asserts -
a refactor of shared ingestion code earns suspicion, not trust.

THE SHORT-CIRCUIT THAT ALMOST DIED

The extension check happens BEFORE any read, so a folder containing a 5GB ISO
never pulls it into memory. Building descriptors up front is exactly the change
that would quietly undo that, and no existing test would have noticed because
none uses a file big enough. ReconcileDescriptor.sha256/size_bytes are therefore
Optional, and TheReadShortCircuitSurvives asserts a rejected extension is never
read at all.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage

from services.ingestion import (
    ReconcileDescriptor,
    classify_reconcile_descriptors,
    describe_upload_for_reconcile,
    preview_data_room_reconcile,
)


def _upload(name, payload):
    return FileStorage(stream=io.BytesIO(payload), filename=Path(name).name)


class _Project(unittest.TestCase):
    """A project with one registered Source, so every verdict is reachable."""

    FILES = {
        "drawings/A-101.pdf": b"%PDF-1.4 registered floor plan",
        "specs/Section_08.md": b"# Doors\n\nRated assemblies.\n",
    }

    def setUp(self):
        import app as app_module
        from services.case_workspace import CaseWorkspaceStore

        self.dir = tempfile.mkdtemp(prefix="reconcile-desc-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

        self.project_id = "reconcile-%s" % uuid.uuid4().hex[:8]
        store = CaseWorkspaceStore(self.dir)
        workspace = store.get_or_create(self.project_id)
        payload = self.FILES["drawings/A-101.pdf"]
        store.add_source(
            workspace, name="A-101.pdf", file_path=None, kind="project_document",
            origin_type="external_connector", origin_reference="drawings/A-101.pdf",
            file_hash=hashlib.sha256(payload).hexdigest())
        store.save(workspace)
        self.store = store

    def both_paths(self, uploads):
        """Run the same folder through the byte path and the descriptor path."""
        paths = [p for p, _ in uploads]
        by_bytes, _ = preview_data_room_reconcile(
            [_upload(p, b) for p, b in uploads], paths, self.project_id, self.app)
        descriptors = [
            ReconcileDescriptor(p, Path(p).name, hashlib.sha256(b).hexdigest(), len(b))
            for p, b in uploads
        ]
        by_descriptor, _ = classify_reconcile_descriptors(
            descriptors, self.project_id, self.app)
        return by_bytes, by_descriptor


class BothPathsReachIdenticalVerdicts(_Project):
    """The central claim. Anything else is detail."""

    def _assert_same(self, uploads):
        by_bytes, by_descriptor = self.both_paths(uploads)
        self.assertEqual(by_bytes["summary"], by_descriptor["summary"])
        self.assertEqual(by_bytes["by_status"], by_descriptor["by_status"])

    def test_unchanged(self):
        self._assert_same([("drawings/A-101.pdf", self.FILES["drawings/A-101.pdf"])])

    def test_renamed(self):
        self._assert_same([("archive/A-101_Rev1.pdf", self.FILES["drawings/A-101.pdf"])])

    def test_modified(self):
        self._assert_same([("drawings/A-101.pdf", b"%PDF-1.4 revised plan")])

    def test_new(self):
        self._assert_same([("specs/Section_08.md", self.FILES["specs/Section_08.md"])])

    def test_missing(self):
        self._assert_same([("specs/Section_08.md", self.FILES["specs/Section_08.md"])])

    def test_ambiguous_duplicate_content_in_one_scan(self):
        payload = b"# identical twins\n"
        self._assert_same([("a/one.md", payload), ("b/two.md", payload)])

    def test_ineligible_extension(self):
        self._assert_same([("setup.exe", b"MZ binary")])

    def test_every_status_at_once(self):
        by_bytes, by_descriptor = self.both_paths([
            ("drawings/A-101.pdf", self.FILES["drawings/A-101.pdf"]),
            ("specs/Section_08.md", self.FILES["specs/Section_08.md"]),
            ("setup.exe", b"MZ binary"),
        ])
        self.assertEqual(by_bytes["by_status"], by_descriptor["by_status"])
        self.assertEqual(by_bytes["summary"]["unchanged"], 1)
        self.assertEqual(by_bytes["summary"]["new"], 1)
        self.assertEqual(by_bytes["summary"]["ineligible"], 1)


class TheByteApiIsUnchanged(_Project):
    """Backward compatibility for every existing Data Room caller."""

    def test_it_still_returns_new_eligible_files_with_real_bytes(self):
        payload = self.FILES["specs/Section_08.md"]
        _report, new_files = preview_data_room_reconcile(
            [_upload("specs/Section_08.md", payload)], ["specs/Section_08.md"],
            self.project_id, self.app)
        self.assertEqual(new_files, [("specs/Section_08.md", "Section_08.md", payload)])

    def test_only_new_files_carry_bytes_forward(self):
        # An UNCHANGED file must not be handed to the staging store: registering
        # it again is the duplicate this whole classification exists to prevent.
        _report, new_files = preview_data_room_reconcile(
            [_upload("drawings/A-101.pdf", self.FILES["drawings/A-101.pdf"])],
            ["drawings/A-101.pdf"], self.project_id, self.app)
        self.assertEqual(new_files, [])

    def test_an_unknown_project_still_raises(self):
        from services.ingestion import UploadError

        with self.assertRaises(UploadError):
            preview_data_room_reconcile([], [], "no-such-project", self.app)

    def test_the_report_still_uses_by_status_not_items(self):
        # A dict has its own .items(), and Jinja resolves the attribute before
        # key access - a real bug this key name exists to avoid.
        report, _ = preview_data_room_reconcile([], [], self.project_id, self.app)
        self.assertIn("by_status", report)
        self.assertNotIn("items", report)


class TheReadShortCircuitSurvives(_Project):
    """The regression that would have been invisible."""

    class _ExplodingUpload:
        """Any read at all is a failure - the extension already ruled it out."""

        def __init__(self, filename):
            self.filename = filename

        def read(self):
            raise AssertionError("a rejected extension must never be read")

    def test_a_disallowed_extension_is_never_read(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        descriptor, raw = describe_upload_for_reconcile(
            self._ExplodingUpload("Win11.iso"), "isos/Win11.iso", allowed)
        self.assertIsNone(raw)
        self.assertIsNone(descriptor.sha256)
        self.assertIsNone(descriptor.size_bytes)

    def test_an_allowed_extension_is_read_and_hashed(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        payload = b"# real content\n"
        descriptor, raw = describe_upload_for_reconcile(
            _upload("notes.md", payload), "notes.md", allowed)
        self.assertEqual(raw, payload)
        self.assertEqual(descriptor.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(descriptor.size_bytes, len(payload))

    def test_a_missing_relative_path_is_not_read_either(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        descriptor, raw = describe_upload_for_reconcile(
            self._ExplodingUpload(""), "", allowed)
        self.assertIsNone(raw)
        self.assertEqual(descriptor.filename, "(unnamed file)")


class ADescriptorWithoutAHashIsReportedNotGuessed(_Project):
    """A manifest that cannot supply a hash must not silently become NEW."""

    def test_it_is_ineligible_with_a_stated_reason(self):
        report, new = classify_reconcile_descriptors(
            [ReconcileDescriptor("specs/Section_08.md", "Section_08.md")],
            self.project_id, self.app)
        self.assertEqual(report["summary"]["new"], 0)
        self.assertEqual(report["summary"]["ineligible"], 1)
        self.assertIn("hash", report["by_status"]["ineligible"][0]["reason"])
        self.assertEqual(new, [])

    def test_a_descriptor_without_a_size_is_not_rejected_for_size(self):
        # Size is only ever a REJECTION rule. Absent size means "unknown", which
        # must not be read as "too big".
        payload = self.FILES["specs/Section_08.md"]
        report, new = classify_reconcile_descriptors(
            [ReconcileDescriptor("specs/Section_08.md", "Section_08.md",
                                 hashlib.sha256(payload).hexdigest(), None)],
            self.project_id, self.app)
        self.assertEqual(report["summary"]["new"], 1)
        self.assertEqual(len(new), 1)


class TheClassifierNeverTouchesBytes(unittest.TestCase):
    """Asserted from source: this is what makes it usable from a manifest."""

    def test_no_byte_handling_survives_in_it(self):
        import inspect

        from services.ingestion import classify_reconcile_descriptors as classifier

        source = inspect.getsource(classifier)
        for byte_handling in ("file_storage", "raw_bytes", ".read()", "hashlib."):
            self.assertNotIn(byte_handling, source)


if __name__ == "__main__":
    unittest.main()
