"""
CLAUDE-EXTERNAL-CUSTODY-01 - a governed Source whose authoritative bytes
ARCHIOSK does not keep.

THE CLAIM UNDER TEST

    ARCHIOSK can govern and analyze a Source without permanently retaining the
    authoritative source bytes.

The Product Owner's own standard for this proof: "The test succeeds only if the
answer is demonstrated by code and tests, not merely by the existence of a path
field." So the central assertions here do not check that a field was set - they
walk the entire ARCHIOSK storage tree and assert the file's bytes are not in it,
while the governed record and its derivatives remain fully intact.

Local folder only. No network, no credentials, no SMB, no NAS.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    CaseWorkspaceStore, SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR, SOURCE_ORIGIN_TYPE_UPLOAD,
)
from services.external_source import (
    ExternalSourceError, ExternalSourceUnavailable, external_source_for_reference,
    iter_external_files, normalize_relative_reference, read_external_bytes,
    register_external_source, resolve_within_root, source_bytes_are_externally_held,
)

_SPEC = (b"SECTION 08 80 00 GLAZING\n"
         b"Provide tempered glazing at all doors. Refer to drawing A101 for extents.\n"
         b"Smoke control damper D-14 shall close on alarm.\n")


class _ExternalRootCase(unittest.TestCase):
    """A project whose authoritative files live in a folder ARCHIOSK does not own."""

    def setUp(self):
        self.store_dir = tempfile.mkdtemp(prefix="archiosk-store-")
        self.external_dir = tempfile.mkdtemp(prefix="project-files-")
        self.addCleanup(shutil.rmtree, self.store_dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.external_dir, ignore_errors=True)

        drawings = Path(self.external_dir) / "Drawings"
        drawings.mkdir()
        self.spec_path = drawings / "A101-spec.txt"
        self.spec_path.write_bytes(_SPEC)

        self.store = CaseWorkspaceStore(self.store_dir)
        self.workspace = self.store.get_or_create("proj-external-01")
        self.workspace.external_storage_root = self.external_dir
        self.store.save(self.workspace)

    def _archiosk_holds_bytes(self, needle: bytes) -> bool:
        """Walk everything ARCHIOSK persists and look for the actual content.

        This is the real test. A `file_path is None` assertion proves only that
        a field is None; this proves the bytes are genuinely not in ARCHIOSK's
        custody anywhere - workspace_sources, the workspace JSON, or otherwise.
        """
        for path in Path(self.store_dir).rglob("*"):
            if path.is_file() and needle in path.read_bytes():
                return True
        return False


class RegisteringWithoutTakingCustody(_ExternalRootCase):
    def test_the_source_is_governed(self):
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        source = result["source"]
        self.assertTrue(source["id"])
        self.assertEqual(source["name"], "A101-spec.txt")
        self.assertEqual(source["file_hash"], hashlib.sha256(_SPEC).hexdigest())

    def test_archiosk_does_not_keep_the_authoritative_bytes(self):
        # The whole proof, in one assertion.
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.assertFalse(
            self._archiosk_holds_bytes(b"SECTION 08 80 00 GLAZING"),
            "the authoritative file content was found inside ARCHIOSK's own storage")

    def test_no_file_was_written_into_workspace_sources(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        sources_dir = Path(self.store_dir) / "workspace_sources"
        written = [p for p in sources_dir.rglob("*") if p.is_file()] if sources_dir.exists() else []
        self.assertEqual(written, [])

    def test_custody_is_derived_from_the_record_not_a_separate_flag(self):
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        source = result["source"]
        self.assertEqual(source["origin_type"], SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR)
        self.assertIsNone(source["file_path"])
        self.assertTrue(source_bytes_are_externally_held(source))

    def test_the_original_file_is_untouched_where_it_lives(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.assertEqual(self.spec_path.read_bytes(), _SPEC)

    def test_the_reference_is_project_relative_not_machine_specific(self):
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        reference = result["source"]["origin_reference"]
        self.assertEqual(reference, "Drawings/A101-spec.txt")
        # Nothing machine-specific survives into durable identity.
        self.assertNotIn(self.external_dir, reference)
        self.assertNotIn(":", reference)
        self.assertNotIn("\\", reference)


class TheFileIsActuallyRead(_ExternalRootCase):
    """Registration is not merely metadata: the bytes are processed."""

    def test_text_is_extracted_from_the_external_file(self):
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.assertIn("GLAZING", result["extracted_text"])
        self.assertIn("damper D-14", result["extracted_text"])

    def test_the_hash_proves_the_real_content_was_read(self):
        # A metadata-only registration could not produce this.
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.assertEqual(result["source"]["file_hash"], hashlib.sha256(_SPEC).hexdigest())

    def test_an_unreadable_format_still_registers_a_governed_source(self):
        odd = Path(self.external_dir) / "Drawings" / "model.dwg"
        odd.write_bytes(b"\x00\x01binary")
        result = register_external_source(self.store, self.workspace, "Drawings/model.dwg")
        self.assertTrue(result["source"]["id"])
        self.assertEqual(result["extracted_text"], "")


class GovernedDerivativesSurviveWithoutCustody(_ExternalRootCase):
    def test_the_record_persists_and_reloads(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        reloaded = self.store.get("proj-external-01")
        source = external_source_for_reference(reloaded, "Drawings/A101-spec.txt")
        self.assertIsNotNone(source)
        self.assertEqual(source["file_hash"], hashlib.sha256(_SPEC).hexdigest())

    def test_the_governed_record_outlives_the_file_itself(self):
        # Losing access to the original must not lose the project's knowledge.
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.spec_path.unlink()
        reloaded = self.store.get("proj-external-01")
        source = external_source_for_reference(reloaded, "Drawings/A101-spec.txt")
        self.assertIsNotNone(source, "the governed Source vanished with its file")
        self.assertIsNone(source.get("removed_at"), "an unreachable file was treated as removed")
        self.assertEqual(source["file_hash"], hashlib.sha256(_SPEC).hexdigest())

    def test_evidence_anchored_to_the_source_stays_referentially_intact(self):
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        source_id = result["source"]["id"]
        self.spec_path.unlink()
        reloaded = self.store.get("proj-external-01")
        # The id an anchor would hold still resolves to the governed record.
        self.assertTrue(any(s["id"] == source_id for s in reloaded.sources))


class FailingHonestlyWhenBytesAreNeeded(_ExternalRootCase):
    def test_reading_a_missing_file_raises_unavailable_not_empty(self):
        # "Do not fabricate analysis from stale bytes while representing the
        # source as current."
        self.spec_path.unlink()
        with self.assertRaises(ExternalSourceUnavailable):
            read_external_bytes(self.external_dir, "Drawings/A101-spec.txt")

    def test_unavailable_is_its_own_type_distinct_from_a_bad_request(self):
        # "Currently unavailable" and "you asked for something invalid" are
        # different facts and must not collapse.
        self.assertTrue(issubclass(ExternalSourceUnavailable, ExternalSourceError))
        with self.assertRaises(ExternalSourceError) as caught:
            resolve_within_root(self.external_dir, "../../etc/passwd")
        self.assertNotIsInstance(caught.exception, ExternalSourceUnavailable)

    def test_registering_a_missing_file_does_not_create_a_source(self):
        before = len(self.store.get("proj-external-01").sources)
        with self.assertRaises(ExternalSourceUnavailable):
            register_external_source(self.store, self.workspace, "Drawings/nope.txt")
        self.assertEqual(len(self.store.get("proj-external-01").sources), before)

    def test_an_unconfigured_root_is_refused_rather_than_guessed(self):
        workspace = self.store.get_or_create("proj-external-02")
        with self.assertRaises(ExternalSourceError):
            register_external_source(self.store, workspace, "anything.txt")


class TheRootIsABoundary(_ExternalRootCase):
    def test_traversal_is_refused(self):
        for attempt in ["../secrets.txt", "Drawings/../../secrets.txt", "..\\secrets.txt"]:
            with self.subTest(attempt=attempt), self.assertRaises(ExternalSourceError):
                resolve_within_root(self.external_dir, attempt)

    def test_an_absolute_path_cannot_escape_by_being_absolute(self):
        # Normalizing strips the leading separator, so it resolves INSIDE the
        # root rather than at the filesystem root.
        resolved = resolve_within_root(self.external_dir, "/Drawings/A101-spec.txt")
        self.assertEqual(resolved, (Path(self.external_dir) / "Drawings" / "A101-spec.txt").resolve())

    def test_an_empty_reference_is_refused(self):
        for attempt in ["", "   ", "/", "./"]:
            with self.subTest(attempt=attempt), self.assertRaises(ExternalSourceError):
                normalize_relative_reference(attempt)

    def test_walking_the_root_yields_relative_references(self):
        (Path(self.external_dir) / "Reports").mkdir()
        (Path(self.external_dir) / "Reports" / "r1.txt").write_bytes(b"r")
        found = set(iter_external_files(self.external_dir))
        self.assertIn("Drawings/A101-spec.txt", found)
        self.assertIn("Reports/r1.txt", found)


class ReconcileSemanticsAreReused(_ExternalRootCase):
    """Not a second synchronization mechanism - the existing one, fed from disk."""

    def setUp(self):
        super().setUp()
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = self.store_dir
        self.store = CaseWorkspaceStore(self.store_dir)
        self.workspace = self.store.get("proj-external-01")

    def _reconcile(self):
        from services.external_source import reconcile_external_root

        with self.flask_app.app_context():
            report, _new = reconcile_external_root(self.flask_app, "proj-external-01")
        return report

    def test_it_delegates_to_the_existing_preview_rather_than_reimplementing(self):
        from unittest.mock import patch

        with patch("services.ingestion.preview_data_room_reconcile",
                   return_value=({"ok": True}, [])) as preview:
            report = self._reconcile()
        preview.assert_called_once()
        self.assertEqual(report, {"ok": True})

    def test_an_untouched_file_reconciles_as_unchanged(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        report = self._reconcile()
        self.assertEqual(report["summary"]["unchanged"], 1, report["summary"])
        self.assertEqual(report["summary"]["new"], 0, report["summary"])

    def test_modified_content_is_detected(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        self.spec_path.write_bytes(_SPEC + b"REVISED: damper D-14 replaced by D-22.\n")
        report = self._reconcile()
        # MODIFIED, not NEW: a known identity whose content changed. Reported as
        # NEW it would be re-registered as a duplicate Source.
        self.assertEqual(report["summary"]["modified"], 1, report["summary"])
        self.assertEqual(report["summary"]["new"], 0, report["summary"])
        self.assertEqual(report["by_status"]["modified"][0]["relative_path"],
                         "Drawings/A101-spec.txt")

    def test_a_vanished_file_is_reported_missing_and_not_deleted(self):
        # The honest-degradation requirement. "Do not silently treat unavailable
        # files as deleted or superseded" - the Source stays governed, keeps its
        # hash, and is merely REPORTED.
        result = register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        source_id = result["source"]["id"]
        self.spec_path.unlink()
        report = self._reconcile()
        self.assertEqual(report["summary"]["missing"], 1, report["summary"])
        surviving = self.store.get("proj-external-01").sources
        still_there = next(s for s in surviving if s["id"] == source_id)
        self.assertIsNone(still_there.get("removed_at"),
                          "a missing file was silently treated as a removal")

    def test_a_brand_new_file_is_detected(self):
        register_external_source(self.store, self.workspace, "Drawings/A101-spec.txt")
        (Path(self.external_dir) / "Drawings" / "A102.txt").write_bytes(b"new drawing content\n")
        report = self._reconcile()
        self.assertEqual(report["summary"]["new"], 1, report["summary"])
        self.assertEqual(report["by_status"]["new"][0]["relative_path"], "Drawings/A102.txt")


class OrdinaryUploadedSourcesAreUnchanged(unittest.TestCase):
    """The custody relaxation is opt-in and must not leak."""

    def setUp(self):
        self.store_dir = tempfile.mkdtemp(prefix="archiosk-store-")
        self.addCleanup(shutil.rmtree, self.store_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.store_dir)
        self.workspace = self.store.get_or_create("proj-ordinary-01")

    def test_a_project_that_never_configures_a_root_is_unaffected(self):
        self.assertIsNone(self.workspace.external_storage_root)

    def test_an_uploaded_source_still_holds_its_path_and_is_not_external(self):
        held = Path(self.store_dir) / "held.txt"
        held.write_bytes(b"archiosk holds this")
        source = self.store.add_source(
            self.workspace, name="held.txt", file_path=str(held),
            kind="project_document", origin_type=SOURCE_ORIGIN_TYPE_UPLOAD)
        self.assertEqual(source["file_path"], str(held))
        self.assertEqual(source["origin_type"], SOURCE_ORIGIN_TYPE_UPLOAD)
        self.assertFalse(source_bytes_are_externally_held(source))

    def test_a_source_with_a_path_is_never_read_as_externally_held(self):
        # Even if something set origin_type wrongly, a real retained path means
        # ARCHIOSK holds the bytes. The derivation refuses to claim otherwise.
        self.assertFalse(source_bytes_are_externally_held(
            {"origin_type": SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR, "file_path": "/somewhere/real"}))

    def test_the_ingestion_write_that_takes_custody_still_exists(self):
        # This proof relaxes custody for ONE opt-in path. If the ordinary
        # ingestion write ever disappears, every existing Source silently
        # changed meaning - which this stage explicitly must not do.
        source = Path("services/ingestion.py").read_text(encoding="utf-8")
        self.assertIn("stored_path.write_bytes(raw_bytes)", source)


if __name__ == "__main__":
    unittest.main()
