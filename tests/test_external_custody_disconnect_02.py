"""
CLAUDE-EXTERNAL-CUSTODY-02 - the storage goes away; the record does not.

WHAT CLAUDE-EXTERNAL-CUSTODY-01 PROVED, AND WHAT IT DID NOT

That commit proved ARCHIOSK can govern and analyse a Source without retaining
the authoritative bytes: `origin_type == "external_connector"` and
`file_path is None`, which together ARE the custody claim rather than describing
it. What it never exercised is the event the whole design exists for - the
storage becoming unreachable while the governed record lives on.

WHY A RENAME IS THE HONEST EXPERIMENT

The WD/NAS question looks like a networking question and is not. From ARCHIOSK's
side, a NAS powered off, a NAS moved to a new address, an unplugged cable and a
renamed directory are the SAME event: the configured root no longer resolves. So
the property worth proving needs no network, no ports, no credentials, and no
vendor hardware - rename the root and see whether the record starts lying.

If the record survives a rename it survives an outage, and transport becomes
separable engineering rather than a correctness risk. Proving it this way is
also the only version that is reversible and touches nothing outside a temp
directory.

THE DEFECT THIS FOUND

`ExternalSourceUnavailable` was raised in three places and caught in none. Its
MRO is ExternalSourceUnavailable -> ExternalSourceError -> Exception, so it is
NOT a CaseWorkspaceError, and none of the ~61 route handlers catching that
parent would ever have seen it. A NAS going offline would have surfaced as
HTTP 500 "Something went wrong" - blaming ARCHIOSK for a cable somewhere else.
Fixed with one app-level handler returning 503 + Retry-After.

503 and deliberately not 404: 404 says the thing does not exist, and the entire
point of external custody is that the governed record still does.

THE ORACLE

tests/fixtures/wd_nas_bridge/oracle/ was not read, in this stage or any earlier
one, and is not tracked. Nothing here depends on it.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceStore
from services.external_source import (
    ExternalSourceError,
    ExternalSourceForbidden,
    ExternalSourceUnavailable,
    external_source_for_reference,
    iter_external_files,
    read_external_bytes,
    register_external_source,
    resolve_within_root,
    source_bytes_are_externally_held,
)

_FILES = {
    "Project_Requirements.md": b"# Requirements\n\nSmoke dampers at every rated penetration.\n",
    "schedules/Equipment_Schedule.csv": b"Tag,Service,Rating\nAHU-1,Supply,45 MIN\nEF-2,Exhaust,NON-RATED\n",
    "details/Roof_Penetration_Detail.md": b"# Roof Penetration\n\nSee 3/A-501 for the curb detail.\n",
}


class _ExternalProject(unittest.TestCase):
    """A project whose authoritative bytes live outside ARCHIOSK entirely."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="wd-nas-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)

        # The "NAS": a directory ARCHIOSK does not own and can lose.
        self.root = self.base / "company_storage"
        for reference, payload in _FILES.items():
            path = self.root / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        self.store = CaseWorkspaceStore(str(self.base / "registry"))
        self.workspace = self.store.get_or_create("wd-nas-proof")
        self.workspace.external_storage_root = str(self.root)

        # register_external_source returns {"source": ..., "extracted_text": ...}
        # - it derives, and hands persistence of derivatives back to the caller
        # rather than owning a second ingestion path.
        self.registered = [
            register_external_source(self.store, self.workspace, reference,
                                     root=str(self.root), extract_text=False)["source"]
            for reference in sorted(_FILES)
        ]
        self.store.save(self.workspace)

    # -- the disconnection itself -----------------------------------------
    def disconnect(self):
        """Indistinguishable, from ARCHIOSK's side, from the NAS powering off."""
        self.root.rename(self.base / "company_storage_OFFLINE")

    def reconnect(self):
        (self.base / "company_storage_OFFLINE").rename(self.root)

    def reload(self):
        return self.store.get("wd-nas-proof")


class CustodyIsStructuralNotAFlag(_ExternalProject):
    def test_archiosk_holds_no_copy_of_the_bytes(self):
        for source in self.registered:
            self.assertIsNone(source["file_path"])
            self.assertEqual(source["origin_type"], "external_connector")
            self.assertTrue(source_bytes_are_externally_held(source))

    def test_nothing_was_written_into_the_registry_store(self):
        # The claim is custody, so an ARCHIOSK-held copy anywhere would void it.
        copies = [p for p in (self.base / "registry").rglob("*")
                  if p.is_file() and p.suffix in {".md", ".csv"}]
        self.assertEqual(copies, [])

    def test_the_hash_proves_the_bytes_were_really_read(self):
        import hashlib

        by_reference = {s["origin_reference"]: s for s in self.registered}
        for reference, payload in _FILES.items():
            self.assertEqual(by_reference[reference]["file_hash"],
                             hashlib.sha256(payload).hexdigest())


class EpistemicRetentionSurvivesDisconnection(_ExternalProject):
    """Mandate 1. Everything ARCHIOSK knows must outlive the storage."""

    def test_every_source_is_still_listed_when_the_storage_is_gone(self):
        before = [s["id"] for s in self.reload().sources]
        self.disconnect()
        self.assertEqual([s["id"] for s in self.reload().sources], before)

    def test_hashes_are_unchanged_by_the_disconnection(self):
        before = {s["id"]: s["file_hash"] for s in self.reload().sources}
        self.disconnect()
        self.assertEqual({s["id"]: s["file_hash"] for s in self.reload().sources}, before)

    def test_provenance_and_identity_survive_intact(self):
        before = {s["id"]: (s["name"], s["origin_type"], s["origin_reference"],
                            s["added_at"], s["kind"]) for s in self.reload().sources}
        self.disconnect()
        after = {s["id"]: (s["name"], s["origin_type"], s["origin_reference"],
                           s["added_at"], s["kind"]) for s in self.reload().sources}
        self.assertEqual(after, before)

    def test_nothing_is_marked_removed_by_going_offline(self):
        # "never silently deleting governed relationships because a Source can't
        # currently be found" - unavailable and removed are different facts.
        self.disconnect()
        self.assertEqual([s for s in self.reload().sources if s.get("removed_at")], [])

    def test_the_whole_workspace_record_is_byte_identical_after_disconnection(self):
        # The strongest form of the claim: losing the storage must not mutate
        # the governed record in ANY way, not merely leave it usable.
        registry = self.base / "registry"
        before = {p.name: p.read_bytes() for p in registry.rglob("*.json") if p.is_file()}
        self.disconnect()
        self.reload()
        after = {p.name: p.read_bytes() for p in registry.rglob("*.json") if p.is_file()}
        self.assertEqual(after, before)


class DisconnectionFailsHonestly(_ExternalProject):
    def test_reading_bytes_raises_unavailable_not_a_bare_os_error(self):
        self.disconnect()
        with self.assertRaises(ExternalSourceUnavailable):
            read_external_bytes(str(self.root), "Project_Requirements.md")

    def test_listing_the_root_raises_unavailable_too(self):
        self.disconnect()
        with self.assertRaises(ExternalSourceUnavailable):
            list(iter_external_files(str(self.root)))

    def test_it_never_returns_empty_bytes_in_place_of_the_file(self):
        # The failure that would matter most: analysis fabricated from nothing
        # while the source is still presented as current.
        self.disconnect()
        try:
            payload = read_external_bytes(str(self.root), "Project_Requirements.md")
        except ExternalSourceUnavailable:
            payload = None
        self.assertIsNone(payload)

    def test_unavailable_is_distinguishable_from_a_configuration_fault(self):
        # A missing root and a misconfigured one are different problems.
        self.assertTrue(issubclass(ExternalSourceUnavailable, ExternalSourceError))
        with self.assertRaises(ExternalSourceError) as caught:
            resolve_within_root("", "anything.md")
        self.assertNotIsInstance(caught.exception, ExternalSourceUnavailable)

    def test_it_is_not_a_case_workspace_error(self):
        # Deliberate. Promoting it into that hierarchy to get it caught would
        # collapse "temporarily unreachable" into "invalid operation" at every
        # existing catch site.
        from services.case_workspace import CaseWorkspaceError

        self.assertFalse(issubclass(ExternalSourceUnavailable, CaseWorkspaceError))


class ReconnectionNeedsNoReRegistration(_ExternalProject):
    def test_the_same_record_resolves_again_once_storage_returns(self):
        self.disconnect()
        self.reconnect()
        for reference, payload in _FILES.items():
            self.assertEqual(read_external_bytes(str(self.root), reference), payload)

    def test_source_identity_is_stable_across_the_whole_cycle(self):
        before = [s["id"] for s in self.reload().sources]
        self.disconnect()
        self.reconnect()
        self.assertEqual([s["id"] for s in self.reload().sources], before)

    def test_a_reference_still_finds_its_governed_source(self):
        self.disconnect()
        self.reconnect()
        source = external_source_for_reference(self.reload(), "schedules/Equipment_Schedule.csv")
        self.assertIsNotNone(source)
        self.assertTrue(source_bytes_are_externally_held(source))

    def test_moving_the_storage_elsewhere_is_a_reconfiguration_not_a_loss(self):
        # A NAS that comes back at a different address. The record is untouched;
        # only the root moves.
        self.disconnect()
        moved = self.base / "relocated_storage"
        (self.base / "company_storage_OFFLINE").rename(moved)
        self.assertEqual(read_external_bytes(str(moved), "Project_Requirements.md"),
                         _FILES["Project_Requirements.md"])
        self.assertEqual(len(self.reload().sources), len(_FILES))


class RefusalIsNotAbsence(_ExternalProject):
    """CLAUDE-EXTERNAL-CUSTODY-03, converged from a parallel simulator.

    A storage that answers and refuses is a third fact, distinct from one that
    cannot be reached. Permissions are simulated by making the read itself raise
    PermissionError rather than by chmod, because POSIX mode bits do not govern
    readability the same way on Windows - a chmod-based test would pass here by
    doing nothing. What is under test is OUR translation of the OS's answer,
    which is exactly what this exercises.
    """

    def _denied(self, target):
        from unittest import mock

        return mock.patch.object(Path, target, side_effect=PermissionError(13, "denied"))

    def test_a_refused_read_is_forbidden_not_unavailable(self):
        with self._denied("read_bytes"):
            with self.assertRaises(ExternalSourceForbidden):
                read_external_bytes(str(self.root), "Project_Requirements.md")

    def test_a_refused_stat_is_forbidden_not_missing(self):
        # A revoked DIRECTORY denies the stat, so the file's own existence
        # cannot even be asked. Reporting that as "not reachable" would send
        # someone to check a cable that is fine.
        with self._denied("is_file"):
            with self.assertRaises(ExternalSourceForbidden):
                read_external_bytes(str(self.root), "Project_Requirements.md")

    def test_a_refused_root_listing_is_forbidden(self):
        with self._denied("is_dir"):
            with self.assertRaises(ExternalSourceForbidden):
                list(iter_external_files(str(self.root)))

    def test_forbidden_and_unavailable_are_siblings_not_the_same_type(self):
        self.assertTrue(issubclass(ExternalSourceForbidden, ExternalSourceError))
        self.assertFalse(issubclass(ExternalSourceForbidden, ExternalSourceUnavailable))
        self.assertFalse(issubclass(ExternalSourceUnavailable, ExternalSourceForbidden))

    def test_refusal_wipes_no_history(self):
        before = {s["id"]: (s["file_hash"], s["origin_reference"]) for s in self.reload().sources}
        with self._denied("read_bytes"):
            with self.assertRaises(ExternalSourceForbidden):
                read_external_bytes(str(self.root), "Project_Requirements.md")
        after = {s["id"]: (s["file_hash"], s["origin_reference"]) for s in self.reload().sources}
        self.assertEqual(after, before)
        self.assertEqual([s for s in self.reload().sources if s.get("removed_at")], [])


class RelocationIsAlreadyOwnedByReconcile(_ExternalProject):
    """The simulator called this RELOCATED. The codebase already calls it
    `renamed`, and has since the Data Room shipped.

    reconcile_external_root deliberately delegates to preview_data_room_reconcile
    so that unchanged/modified/renamed/missing/ambiguous/ineligible stay decided
    by the code that owns those semantics. Adding a fifth word for a move would
    have been a second vocabulary for one subject.
    """

    def test_the_reconcile_vocabulary_already_covers_a_move(self):
        from services.ingestion import (
            RECONCILE_STATUS_MISSING, RECONCILE_STATUS_RENAMED,
            RECONCILE_STATUS_UNCHANGED,
        )

        self.assertEqual(RECONCILE_STATUS_RENAMED, "renamed")
        self.assertEqual(RECONCILE_STATUS_UNCHANGED, "unchanged")
        self.assertEqual(RECONCILE_STATUS_MISSING, "missing")

    def test_a_moved_file_keeps_its_identity_by_hash(self):
        # The property a move must preserve: same bytes, same hash, therefore
        # the same governed Source - found at a new path rather than replaced.
        import hashlib

        payload = _FILES["details/Roof_Penetration_Detail.md"]
        original = hashlib.sha256(payload).hexdigest()
        (self.root / "details" / "Roof_Penetration_Detail.md").rename(
            self.root / "Roof_Penetration_Detail_Rev1.md")
        self.assertEqual(
            hashlib.sha256(read_external_bytes(
                str(self.root), "Roof_Penetration_Detail_Rev1.md")).hexdigest(),
            original)
        registered = {s["file_hash"] for s in self.reload().sources}
        self.assertIn(original, registered)

    def test_a_move_creates_no_second_source(self):
        before = len(self.reload().sources)
        (self.root / "details" / "Roof_Penetration_Detail.md").rename(
            self.root / "Roof_Penetration_Detail_Rev1.md")
        self.assertEqual(len(self.reload().sources), before)


class TheRootBoundaryHolds(_ExternalProject):
    """No network here, so path containment is the whole security surface."""

    def test_a_traversal_reference_is_refused(self):
        with self.assertRaises(ExternalSourceError):
            resolve_within_root(str(self.root), "../company_storage/../../etc/passwd")

    def test_a_symlink_pointing_outside_the_root_is_refused(self):
        outside = self.base / "outside_secret.md"
        outside.write_bytes(b"not project data")
        link = self.root / "escape.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted in this environment")
        # Checked AFTER resolution, so a symlink anywhere in the chain is caught
        # where a prefix test on the raw string would have passed.
        with self.assertRaises(ExternalSourceError):
            resolve_within_root(str(self.root), "escape.md")


class TheUnavailableStateHasAnHonestHttpAnswer(unittest.TestCase):
    """The defect: raised in three places, caught in none, not a 500."""

    def test_the_handler_is_registered_and_deliberately_narrow(self):
        source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("@app.errorhandler(ExternalSourceUnavailable)", source)
        # Never the parent - a configuration fault must stay a visible bug.
        self.assertNotIn("@app.errorhandler(ExternalSourceError)", source)

    def test_it_answers_503_with_retry_after(self):
        import app as app_module

        application = app_module.create_app("testing")

        @application.route("/__unavailable_probe")
        def _probe():
            raise ExternalSourceUnavailable("the storage root is not reachable")

        client = application.test_client()
        response = client.get("/__unavailable_probe")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers.get("Retry-After"), "60")

    def test_a_json_client_gets_a_structured_body(self):
        # This app decides JSON by PATH, not by content negotiation -
        # app.py's _wants_json() is `request.path.startswith("/api/")`. Asserting
        # via an Accept header would have tested nothing and passed for the
        # wrong reason.
        import app as app_module

        application = app_module.create_app("testing")

        @application.route("/api/__unavailable_probe_json")
        def _probe():
            raise ExternalSourceUnavailable("offline")

        response = application.test_client().get("/api/__unavailable_probe_json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "external_source_unavailable")
        self.assertEqual(response.headers.get("Retry-After"), "60")

    def test_it_does_not_claim_the_document_is_gone(self):
        import app as app_module

        application = app_module.create_app("testing")

        @application.route("/__unavailable_probe_html")
        def _probe():
            raise ExternalSourceUnavailable("offline")

        body = application.test_client().get("/__unavailable_probe_html").get_data(as_text=True)
        # 404's vocabulary would be a lie of a specific kind: it says the thing
        # does not exist, and the record demonstrably does.
        self.assertNotIn("doesn't exist", body)
        self.assertNotIn("Something went wrong", body)
        self.assertIn("unaffected", body)


class RefusalHasItsOwnHonestHttpAnswer(unittest.TestCase):
    """503 for both, but never the same 503."""

    @staticmethod
    def _app_raising(exc, path="/__probe"):
        import app as app_module

        application = app_module.create_app("testing")

        @application.route(path)
        def _probe():
            raise exc

        return application.test_client().get(path)

    def test_forbidden_answers_503(self):
        response = self._app_raising(ExternalSourceForbidden("refused"), "/__forbidden")
        self.assertEqual(response.status_code, 503)

    def test_forbidden_sends_no_retry_after(self):
        # The header is a promise that waiting is the fix. A withdrawn
        # permission does not heal on its own, and a machine client honouring a
        # Retry-After here would poll forever against a door a human must open.
        response = self._app_raising(ExternalSourceForbidden("refused"), "/__forbidden_ra")
        self.assertIsNone(response.headers.get("Retry-After"))

    def test_unavailable_still_does_send_one(self):
        response = self._app_raising(ExternalSourceUnavailable("offline"), "/__unavail_ra")
        self.assertEqual(response.headers.get("Retry-After"), "60")

    def test_it_is_never_403(self):
        # 403 means THIS user is not authorised, which is false - the person
        # asking may be the project owner. What lacks access is ARCHIOSK's own
        # service account against someone else's storage, and answering 403
        # would send an entire investigation into the wrong system.
        response = self._app_raising(ExternalSourceForbidden("refused"), "/__not403")
        self.assertNotEqual(response.status_code, 403)

    def test_the_two_bodies_give_different_advice(self):
        refused = self._app_raising(
            ExternalSourceForbidden("x"), "/__body_forbidden").get_data(as_text=True)
        offline = self._app_raising(
            ExternalSourceUnavailable("x"), "/__body_unavail").get_data(as_text=True)
        self.assertIn("restore access", refused)
        self.assertIn("will not resolve it on its own", refused)
        self.assertIn("Reconnect the storage", offline)
        self.assertNotIn("Reconnect the storage", refused)

    def test_a_json_client_gets_the_distinct_code(self):
        import app as app_module

        application = app_module.create_app("testing")

        @application.route("/api/__forbidden_json")
        def _probe():
            raise ExternalSourceForbidden("refused")

        payload = application.test_client().get("/api/__forbidden_json").get_json()
        self.assertEqual(payload["error"], "external_source_forbidden")

    def test_both_handlers_are_registered_and_neither_catches_the_parent(self):
        source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("@app.errorhandler(ExternalSourceForbidden)", source)
        self.assertIn("@app.errorhandler(ExternalSourceUnavailable)", source)
        self.assertNotIn("@app.errorhandler(ExternalSourceError)", source)


if __name__ == "__main__":
    unittest.main()
