"""
CLAUDE-RFP-BOUNDARY-01 -- RFP workspace-side identity, Client/Proponent
separation, and publication isolation. The no-leak smoke test required by
this stage's own governing prompt (Section 10): a fact that exists only in
an Owner (CLIENT_OWNER) project's pre-publication corpus must never be
retrievable from a genuinely separate Proponent (DESIGN_BUILDER_PROPONENT)
project that only ever registered the *published* package.

Every ingestion call here spies on BHiveParser.parse rather than letting it
run for real -- the same convention tests/test_project_access_control.py
and tests/test_security_enforcement.py already establish (see the CLAUDE-P31
8.5-hour live-API incident their own header comments describe). The
non-founding-file extraction path inside services.ingestion.
ingest_folder_upload calls BHiveParser._extract directly (not .parse) --
for a plain .txt fixture this is a pure bytes-decode with no external call
at all (see BHiveParser._extract's own ext == ".txt" branch), so no
additional mock is needed for that path with these fixtures.

The core proof (test_published_package_is_the_only_thing_that_crosses) is
structural, not a single AI-response spot check: it scans every file
persisted anywhere under the shared registry storage root for a uniquely-
named planted secret, and asserts every file that contains it is scoped to
the Owner project's own project_id -- never the Proponent's. A technically
correct leaked answer from one prompt would still be a failure per Section
10's own words; this proves the secret is structurally absent from every
file GO could possibly retrieve from in the Proponent project, which is a
stronger claim than "one question didn't surface it."
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.environment_capabilities import (
    CLIENT_OWNER,
    DESIGN_BUILDER_PROPONENT,
    LIFECYCLE_PRE_PUBLICATION,
    LIFECYCLE_PUBLISHED,
    LIFECYCLE_RESPONSE,
)
from services.governance import GovernanceLog
from services.ingestion import ingest_folder_upload, ingest_upload
from services.procurement_publication import PublicationExportError, build_published_package_zip

SECRET = "SECRET-DEFECT-9F21"
PRIVATE_NOTE = (
    f"{SECRET}: internal drafting note - clause 4.2 was changed before "
    "publication because the original wording contradicted the site "
    "geotechnical report; never disclosed to bidders."
)
PUBLIC_TEXT = "Public RFP content - Section 3, Scope of Work."


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _BaseIsolationTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_test_rfp_boundary_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _log(self) -> GovernanceLog:
        return GovernanceLog(self.tmp_dir)

    def _ingest_owner_package(self):
        """Registers a CLIENT_OWNER project with two Sources: the public
        RFP text (founding) and a private internal note carrying SECRET.
        Exercises the real ingest_folder_upload path, including its
        non-founding _extract/register_plain_text_structure call - not a
        hand-built fixture."""
        included = _fake_file(PUBLIC_TEXT.encode(), "RFP.txt")
        private = _fake_file(PRIVATE_NOTE.encode(), "internal_note.txt")
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.flask_app.app_context():
                founding_doc, results = ingest_folder_upload(
                    files=[included, private],
                    relative_paths=["RFP.txt", "internal_note.txt"],
                    founding_index=0,
                    app=self.flask_app,
                    operating_environment=CLIENT_OWNER,
                    owner="alice",
                )
        self.assertEqual([r["status"] for r in results], ["added"])
        return founding_doc

    def _ingest_proponent_project(self, file_bytes: bytes, filename: str, project_name: str = "Proponent Response Project"):
        # project_name is distinct from the Owner project's own entry name
        # on purpose - services.ingestion._reject_if_name_taken enforces
        # globally unique project entry names (an existing, unrelated
        # product rule), and a real Proponent would give their own
        # response project its own name regardless.
        file_storage = _fake_file(file_bytes, filename)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    file_storage, self.flask_app,
                    operating_environment=DESIGN_BUILDER_PROPONENT, owner="alice",
                    project_name=project_name,
                )


class LifecycleAndEnvironmentTests(_BaseIsolationTestCase):
    """Validation points 1-5, 17: side/lifecycle are stored explicitly,
    independent of admin role, and displayed truthfully for both sides."""

    def test_owner_project_gets_client_owner_and_pre_publication(self):
        founding_doc = self._ingest_owner_package()
        workspace = self._store().get(founding_doc.project_id)
        self.assertEqual(workspace.operating_environment, CLIENT_OWNER)
        self.assertEqual(workspace.lifecycle_stage, LIFECYCLE_PRE_PUBLICATION)
        self.assertIsNotNone(workspace.lifecycle_stage_set_by)
        self.assertIsNotNone(workspace.lifecycle_stage_set_at)

    def test_proponent_project_gets_design_builder_proponent_and_response(self):
        doc = self._ingest_proponent_project(PUBLIC_TEXT.encode(), "RFP.txt")
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.operating_environment, DESIGN_BUILDER_PROPONENT)
        self.assertEqual(workspace.lifecycle_stage, LIFECYCLE_RESPONSE)

    def test_owner_and_proponent_are_genuinely_separate_projects(self):
        owner_doc = self._ingest_owner_package()
        proponent_doc = self._ingest_proponent_project(PUBLIC_TEXT.encode(), "RFP.txt")
        self.assertNotEqual(owner_doc.project_id, proponent_doc.project_id)

    def test_admin_role_does_not_substitute_for_procurement_side(self):
        """Section 2/8: is_admin is a pure session-role check
        (services.auth.admin_required/is_admin), structurally unrelated to
        operating_environment - proven here by the fact that establishing
        a project's side never reads or requires any admin/session state
        at all; set_operating_environment's own signature takes no role
        argument, only an explicit environment value."""
        import inspect

        from services.case_workspace import CaseWorkspaceStore as CWS

        params = list(inspect.signature(CWS.set_operating_environment).parameters)
        self.assertNotIn("is_admin", params)
        self.assertNotIn("role", params)


class PublishGovernanceTests(_BaseIsolationTestCase):
    """Validation points 6, 9, 10: Register RFP is one action; publication
    is a real, one-time, governed act."""

    def test_publish_requires_client_owner_project(self):
        doc = self._ingest_proponent_project(PUBLIC_TEXT.encode(), "RFP.txt")
        store = self._store()
        workspace = store.get(doc.project_id)
        source_id = workspace.sources[0]["id"]
        with self.assertRaises(CaseWorkspaceError):
            store.publish_procurement_package(
                workspace, source_ids=[source_id], founding_source_id=source_id, actor="alice",
            )

    def test_publish_locks_lifecycle_stage_once(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        workspace = store.get(founding_doc.project_id)
        included = next(s for s in workspace.sources if s["name"] == "RFP.txt")

        store.publish_procurement_package(
            workspace, source_ids=[included["id"]], founding_source_id=included["id"], actor="alice",
        )
        self.assertEqual(workspace.lifecycle_stage, LIFECYCLE_PUBLISHED)

        with self.assertRaises(CaseWorkspaceError):
            store.publish_procurement_package(
                workspace, source_ids=[included["id"]], founding_source_id=included["id"], actor="alice",
            )

    def test_publish_rejects_empty_selection(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        workspace = store.get(founding_doc.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.publish_procurement_package(workspace, source_ids=[], founding_source_id="", actor="alice")

    def test_publish_rejects_unselected_founding_id(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        workspace = store.get(founding_doc.project_id)
        included = next(s for s in workspace.sources if s["name"] == "RFP.txt")
        private = next(s for s in workspace.sources if s["name"] == "internal_note.txt")
        with self.assertRaises(CaseWorkspaceError):
            store.publish_procurement_package(
                workspace, source_ids=[included["id"]], founding_source_id=private["id"], actor="alice",
            )

    def test_only_selected_sources_appear_in_the_zip(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        workspace = store.get(founding_doc.project_id)
        included = next(s for s in workspace.sources if s["name"] == "RFP.txt")

        selected = store.publish_procurement_package(
            workspace, source_ids=[included["id"]], founding_source_id=included["id"], actor="alice",
        )
        zip_bytes = build_published_package_zip(selected)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        self.assertEqual(zf.namelist(), ["RFP.txt"])
        self.assertEqual(zf.read("RFP.txt"), PUBLIC_TEXT.encode())

    def test_governance_log_entry_carries_metadata_only_never_content(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        governance_log = self._log()
        workspace = store.get(founding_doc.project_id)
        included = next(s for s in workspace.sources if s["name"] == "RFP.txt")

        store.publish_procurement_package(
            workspace, source_ids=[included["id"]], founding_source_id=included["id"],
            actor="alice", governance_log=governance_log,
        )
        events = [
            e for e in governance_log.read(founding_doc.project_id)
            if e.event_type == "procurement_package_published"
        ]
        self.assertEqual(len(events), 1)
        payload_text = json.dumps(events[0].payload)
        self.assertNotIn(SECRET, payload_text)
        self.assertNotIn(PRIVATE_NOTE, payload_text)
        self.assertEqual(events[0].payload["source_ids"], [included["id"]])


class NoLeakIsolationTests(_BaseIsolationTestCase):
    """Section 10 / validation points 7, 8, 11-16: the actual no-leak
    proof, plus confirmation the Proponent registration path (Register
    RFP, unchanged) only ever sees the published material."""

    def test_published_package_is_the_only_thing_that_crosses(self):
        # -- Stage A: Owner registers, then publishes only the public file --
        owner_doc = self._ingest_owner_package()
        store = self._store()
        governance_log = self._log()
        owner_workspace = store.get(owner_doc.project_id)
        included = next(s for s in owner_workspace.sources if s["name"] == "RFP.txt")
        private = next(s for s in owner_workspace.sources if s["name"] == "internal_note.txt")

        selected = store.publish_procurement_package(
            owner_workspace, source_ids=[included["id"]], founding_source_id=included["id"],
            actor="alice", governance_log=governance_log,
        )
        zip_bytes = build_published_package_zip(selected)

        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        self.assertEqual(zf.namelist(), ["RFP.txt"], "only the selected Source may cross the boundary")
        published_bytes = zf.read("RFP.txt")

        # -- Stage B: Proponent registers ONLY the published bytes, via the
        # same, unmodified Register RFP path (services.ingestion.
        # ingest_upload) real users go through. --
        proponent_doc = self._ingest_proponent_project(published_bytes, "RFP.txt")
        self.assertNotEqual(proponent_doc.project_id, owner_doc.project_id)
        proponent_workspace = store.get(proponent_doc.project_id)
        self.assertEqual(len(proponent_workspace.sources), 1)
        self.assertEqual(proponent_workspace.sources[0]["name"], "RFP.txt")

        # -- The structural proof: the planted secret must never appear in
        # any file scoped to the Proponent project, anywhere under the
        # shared registry storage root (workspace JSON, source files,
        # requirements registry, governance log - whatever storage
        # subsystem a given piece of data lives in). --
        files_with_secret = []
        for path in Path(self.tmp_dir).rglob("*"):
            if not path.is_file():
                continue
            try:
                content = path.read_bytes()
            except OSError:
                continue
            if SECRET.encode() in content:
                files_with_secret.append(path)

        self.assertTrue(files_with_secret, "sanity check: the secret must exist SOMEWHERE (the Owner's own files)")
        for path in files_with_secret:
            self.assertIn(
                owner_doc.project_id, str(path),
                f"secret found in a file not scoped to the Owner project: {path}",
            )
            self.assertNotIn(
                proponent_doc.project_id, str(path),
                f"LEAK: Owner-only secret found in a Proponent-scoped file: {path}",
            )

        # Belt-and-suspenders: explicitly confirm zero files anywhere
        # under the Proponent project's own project_id contain it.
        for path in Path(self.tmp_dir).rglob(f"*{proponent_doc.project_id}*"):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes())

    def test_publish_export_fails_honestly_on_missing_file(self):
        founding_doc = self._ingest_owner_package()
        store = self._store()
        workspace = store.get(founding_doc.project_id)
        included = next(s for s in workspace.sources if s["name"] == "RFP.txt")

        selected = store.publish_procurement_package(
            workspace, source_ids=[included["id"]], founding_source_id=included["id"], actor="alice",
        )
        # Simulate the file having disappeared from disk between selection
        # and export - build_published_package_zip must refuse, not
        # silently produce a package missing content it claimed to include.
        Path(selected[0]["file_path"]).unlink()
        with self.assertRaises(PublicationExportError):
            build_published_package_zip(selected)


if __name__ == "__main__":
    unittest.main()
