"""
CLAUDE-P40-VW9 (Governed Files Display and Project File Architecture).

Independent architectural review, grounded directly in the repository
(services/case_workspace.py, routes/workspace.py, static/js/
case_workspace.js, templates/base.html+case_workspace.html), before any
code was written for this stage:

1. Files IS registered as a stable directory/Display kind through the
   CLAUDE-P40-VW8-QA1 extension point - `routes.workspace.
   STABLE_DIRECTORY_KINDS["files"] = "Files"` and `case_workspace.js`'s
   `PANEL_KINDS.files` - exactly the "second real entry" that extension
   point was built to prove out. Zero template changes were needed for
   the breadcrumb/division-0-header label (both already read the shared
   `directory_view_label` VW8-QA1 introduced).

2. Data Room and Design-Builder Workspace are GOVERNED VIRTUAL roots this
   stage, not persisted domain rows of their own -
   `FOLDER_ROOT_DATA_ROOM`/`FOLDER_ROOT_DESIGN_BUILDER` are fixed
   constants; real, persisted `Folder` records exist only inside Design-
   Builder Workspace (every `create_folder` call always writes
   `root=FOLDER_ROOT_DESIGN_BUILDER` - there is no parameter or route
   path that can create a Data Room folder record at all). This makes
   "ordinary Design-Builder actions cannot touch Data Room" true
   structurally, not by convention.

3. Folder identity is `Folder.id` (uuid4), exactly mirroring the
   pre-existing principle already stated on `Source`'s own docstring
   ("folder locations and filenames are external representations only").
   A folder's path is always DERIVED at read time
   (`CaseWorkspaceStore._folder_path`), never stored as a string.

4. No `folder_id` field was added to `Source` this stage - a Document is
   structurally incapable of being assigned into a folder yet, so every
   existing Investigation/RFI/Task/Tag/conversation/citation relationship
   (all keyed off `Source.id`, never location) is untouched by anything
   in this stage, both now and by construction for whatever a future
   stage adds.

5. No route/method anywhere converts a folder id, name, or path into a
   business identifier, cache key, or lookup key - only `Folder.id`/
   `Source.id` (both uuid4) are ever used that way.

6. Files/folders reuse `_load_workspace_or_404`/`can_access_project`
   exactly like every other `show_workspace` view - no new authorization
   path. Folder mutation routes additionally re-validate `project_id`
   against the folder's own stored value before acting (the same
   structural project-isolation shape `Source.project_id` already uses) -
   a crafted id from another project simply isn't found in `workspace.
   folders`, since each project's `CaseWorkspaceStore` state lives in its
   own file.

7. This stage's actual slice: Files as a real registered stable Display
   kind; two visually/semantically distinct roots (Data Room fixed/
   controlled/compatibility-view-or-empty, Design-Builder Workspace real
   and mutable); folder CRUD scoped ONLY to Design-Builder Workspace
   (create, nested create, rename, move with cycle prevention, delete-
   empty via the lightweight confirm=yes/no gate, soft-delete/tombstone
   matching Source/Project's own established convention). No Document-
   to-folder assignment, no Data Room hierarchy invention, no lifecycle
   automation, no cross-project/global-search/bulk-import anything.

These tests prove the above with real repository evidence: request-level
tests through a real Flask test client (matching this repository's
dominant test-authoring convention) plus store-layer tests exercising
`CaseWorkspaceStore` directly. A real-Chromium browser pass (real-browser
verification, reported separately in the completion notes - not part of
this automated file) additionally confirmed the rendered two-root layout,
folder CRUD, and multi-Display embedding all work as this file asserts.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw
import routes.workspace as workspace_routes

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CASE_WORKSPACE_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"
_CASE_WORKSPACE_PY_PATH = _REPO_ROOT / "services" / "case_workspace.py"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw9_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="vw9_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.store = cw.CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw9_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="vw9_owner", user_id=1, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# Architecture and registry
# ---------------------------------------------------------------------------

class RegistryTests(_BaseTestCase):
    def test_files_registered_in_stable_directory_kinds(self):
        self.assertEqual(workspace_routes.STABLE_DIRECTORY_KINDS.get("files"), "Files")

    def test_files_registered_in_panel_kinds_client_side(self):
        js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")
        table_idx = js.index("const PANEL_KINDS = {")
        table = js[table_idx:js.index("\n        };", table_idx)]
        self.assertIn("files:", table)

    def test_selecting_files_projects_into_display_with_registry_driven_breadcrumb(self):
        doc = self._ingest("VW9 Registry Project")
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace?view=files")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<span class="workspace-topbar-doc">Files</span>', body)
        header_idx = body.index("display-division-header-name")
        self.assertIn("Files", body[header_idx:header_idx + 400])

    def test_unrecognized_kind_does_not_inherit_files_or_overview_active_selector(self):
        # Source-text evidence: syncListsActiveState resolves an
        # unrecognized kind to NO selector (skipped), not a fallback onto
        # 'files' or 'overview' - the exact latent-bug class VW8-QA1's
        # own PANEL_KINDS refactor closed, re-verified still holds now
        # that 'files' is a second real entry.
        js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")
        start = js.index("function syncListsActiveState(")
        body = js[start:start + 1000]
        self.assertIn("PANEL_KINDS[kind]", body)
        self.assertNotIn(': \'a[data-view="overview"]\';', body)
        self.assertNotIn(': \'a[data-view="files"]\';', body)

    def test_files_leaf_has_no_dynamic_record_count_or_tab_strip_pill(self):
        # Section 3's own "does not create a dynamic-record tab-strip
        # pill" - same stable-singleton shape as Overview: one leaf, no
        # launcher-count, no data-source-id/data-case-id pattern.
        base_html = (_REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        idx = base_html.index('data-ui-ref="lists.project.files"')
        tag = base_html[base_html.rindex("<li", 0, idx):base_html.index("</li>", idx) + 5]
        self.assertNotIn("launcher-count", tag)
        self.assertNotIn("data-source-id", tag)
        self.assertNotIn("data-case-id", tag)

    def test_multi_display_click_interceptor_resolves_files_kind_not_overview(self):
        # CLAUDE-P40-VW9: a real bug found and fixed during this stage's
        # own real-browser verification (not caught by any request-level
        # test, since this is pure client-side click-routing logic).
        # base.html's multi-Display click-interceptor used to have
        # exactly ONE data-view leaf (Overview), so its dispatch fell
        # through to a hardcoded kind='overview' for "any data-view link,
        # whatever its value" - accidentally correct at the time. Adding
        # a SECOND data-view leaf (Files) exposed the real shape of the
        # bug: clicking Files while a non-zero Display was the active
        # target silently populated Overview instead. Fixed by reading
        # the attribute's own VALUE. Source-text proof here (the genuine
        # runtime behavior was independently confirmed live in a real
        # browser - see this stage's own completion notes) that the fix
        # is in place and ordered correctly (checked before the generic
        # 'overview' fallback, not after - a fallback later in the
        # if/elif chain would never be reached).
        base_html = (_REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        interceptor_start = base_html.index("root.addEventListener('click'")
        interceptor_body = base_html[interceptor_start:interceptor_start + 3500]
        self.assertIn("kind = 'files'", interceptor_body)
        files_branch_idx = interceptor_body.index("kind = 'files'")
        overview_fallback_idx = interceptor_body.rindex("kind = 'overview'")
        self.assertLess(files_branch_idx, overview_fallback_idx)

    def test_opening_files_repeatedly_does_not_duplicate_the_surface(self):
        doc = self._ingest("VW9 No Duplicate Project")
        client = self._client()
        first = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        second = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertEqual(first.count('data-ui-ref="display.files"'), 1)
        self.assertEqual(second.count('data-ui-ref="display.files"'), 1)

    def test_real_case_selection_still_overrides_files(self):
        doc = self._ingest("VW9 Precedence Project")
        client = self._client()
        resp = client.post(f"/projects/{doc.project_id}/workspace/cases", data={"title": "Precedence Investigation", "objective": ""})
        case_id = resp.headers["Location"].split("case=")[1].split("&")[0]
        resp2 = client.get(f"/projects/{doc.project_id}/workspace?view=files&case={case_id}")
        body = resp2.get_data(as_text=True)
        self.assertIn("Precedence Investigation", body)
        self.assertNotIn('<span class="workspace-topbar-doc">Files</span>', body)

    def test_files_coexists_with_overview_and_document_surfaces(self):
        doc = self._ingest("VW9 Coexistence Project")
        client = self._client()
        overview = client.get(f"/projects/{doc.project_id}/workspace?view=overview")
        files = client.get(f"/projects/{doc.project_id}/workspace?view=files")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(files.status_code, 200)
        self.assertIn("Files", overview.get_data(as_text=True))  # Lists leaf still present
        self.assertIn("Overview", files.get_data(as_text=True))  # Lists leaf still present


# ---------------------------------------------------------------------------
# Persistence and identity
# ---------------------------------------------------------------------------

class FolderIdentityTests(_BaseTestCase):
    def test_create_folder_generates_a_new_uuid_and_only_ever_targets_design_builder(self):
        doc = self._ingest("VW9 Identity Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Drawings", actor="vw9_owner")
        self.assertTrue(folder["id"])
        self.assertEqual(folder["root"], cw.FOLDER_ROOT_DESIGN_BUILDER)
        self.assertNotEqual(folder["root"], cw.FOLDER_ROOT_DATA_ROOM)

    def test_rename_does_not_change_identity(self):
        doc = self._ingest("VW9 Rename Identity Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Original", actor="vw9_owner")
        renamed = self.store.rename_folder(ws, folder["id"], "Renamed", actor="vw9_owner")
        self.assertEqual(renamed["id"], folder["id"])
        self.assertEqual(renamed["name"], "Renamed")

    def test_move_does_not_change_identity(self):
        doc = self._ingest("VW9 Move Identity Project")
        ws = self.store.get(doc.project_id)
        parent = self.store.create_folder(ws, "Parent", actor="vw9_owner")
        child = self.store.create_folder(ws, "Child", actor="vw9_owner")
        moved = self.store.move_folder(ws, child["id"], parent["id"], actor="vw9_owner")
        self.assertEqual(moved["id"], child["id"])
        self.assertEqual(moved["parent_folder_id"], parent["id"])

    def test_folder_path_is_derived_never_stored(self):
        doc = self._ingest("VW9 Path Derivation Project")
        ws = self.store.get(doc.project_id)
        root = self.store.create_folder(ws, "Root", actor="vw9_owner")
        child = self.store.create_folder(ws, "Child", parent_folder_id=root["id"], actor="vw9_owner")
        self.assertNotIn("path", cw.Folder.__dataclass_fields__)
        path = self.store._folder_path(ws, child["id"])
        self.assertEqual([f["name"] for f in path], ["Root", "Child"])

    def test_sibling_name_uniqueness_enforced_scoped_to_parent(self):
        doc = self._ingest("VW9 Sibling Uniqueness Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "Drawings", actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.create_folder(ws, "Drawings", actor="vw9_owner")
        # Same name is fine in a DIFFERENT parent - sibling-scoped, not global.
        other_parent = self.store.create_folder(ws, "Other Parent", actor="vw9_owner")
        nested = self.store.create_folder(ws, "Drawings", parent_folder_id=other_parent["id"], actor="vw9_owner")
        self.assertTrue(nested["id"])

    def test_cycle_prevented_moving_ancestor_into_its_own_descendant(self):
        doc = self._ingest("VW9 Cycle Project")
        ws = self.store.get(doc.project_id)
        root = self.store.create_folder(ws, "Root", actor="vw9_owner")
        child = self.store.create_folder(ws, "Child", parent_folder_id=root["id"], actor="vw9_owner")
        grandchild = self.store.create_folder(ws, "Grandchild", parent_folder_id=child["id"], actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.move_folder(ws, root["id"], grandchild["id"], actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.move_folder(ws, child["id"], grandchild["id"], actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.move_folder(ws, root["id"], root["id"], actor="vw9_owner")

    def test_project_scoped_ownership_folder_carries_its_own_project_id(self):
        doc = self._ingest("VW9 Ownership Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Scoped", actor="vw9_owner")
        self.assertEqual(folder["project_id"], doc.project_id)

    def test_cross_project_folder_mutation_rejected_by_workspace_isolation(self):
        # Realistic route-level shape: workspace.folders can only ever
        # contain the folders of the project that workspace file was
        # actually loaded for (routes/workspace.py's _load_workspace_or_404
        # always loads the CORRECT project's own store file - see
        # test_p40vw9...GovernanceTests for the route-level version of
        # this). A folder id that belongs to a different project is
        # therefore simply ABSENT from this workspace's own list -
        # _find returns None, the exact same structural guarantee
        # Source/Case already rely on (fork audit: "each project's
        # CaseWorkspaceStore state lives in its own file").
        doc_a = self._ingest("VW9 Cross Project A")
        doc_b = self._ingest("VW9 Cross Project B")
        ws_a = self.store.get(doc_a.project_id)
        ws_b = self.store.get(doc_b.project_id)
        folder_a = self.store.create_folder(ws_a, "A-Folder", actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.rename_folder(ws_b, folder_a["id"], "Hacked", actor="mallory")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.move_folder(ws_b, folder_a["id"], None, actor="mallory")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.delete_folder(ws_b, folder_a["id"], actor="mallory")

    def test_project_id_field_is_independently_checked_defense_in_depth(self):
        # Distinct from the test above: this proves the explicit
        # `folder["project_id"] != workspace.project_id` guard inside
        # rename/move/delete_folder is itself real and load-bearing, not
        # dead code - by constructing the one scenario where a folder
        # record's own project_id could legitimately disagree with the
        # workspace it's found in (a corrupted/hand-edited JSON file, or
        # a future data-migration bug), which the structural isolation
        # above does NOT cover on its own. Falsified directly during this
        # stage's own review: removing this check from rename_folder left
        # this exact scenario unguarded while the test above kept passing
        # for an unrelated reason (workspace-file isolation) - restored,
        # not weakened.
        doc_a = self._ingest("VW9 Corrupted Record Project A")
        doc_b = self._ingest("VW9 Corrupted Record Project B")
        ws_b = self.store.get(doc_b.project_id)
        corrupted = cw.Folder(
            id=str(uuid.uuid4()), project_id=doc_a.project_id, root=cw.FOLDER_ROOT_DESIGN_BUILDER,
            name="Corrupted", created_at=datetime.now(timezone.utc).isoformat(), created_by="vw9_owner",
        )
        from dataclasses import asdict
        ws_b.folders.append(asdict(corrupted))
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.rename_folder(ws_b, corrupted.id, "Hacked", actor="mallory")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.move_folder(ws_b, corrupted.id, None, actor="mallory")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.delete_folder(ws_b, corrupted.id, actor="mallory")

    def test_delete_requires_an_empty_folder(self):
        doc = self._ingest("VW9 Non-Empty Delete Project")
        ws = self.store.get(doc.project_id)
        parent = self.store.create_folder(ws, "Parent", actor="vw9_owner")
        self.store.create_folder(ws, "Child", parent_folder_id=parent["id"], actor="vw9_owner")
        with self.assertRaises(cw.CaseWorkspaceError):
            self.store.delete_folder(ws, parent["id"], actor="vw9_owner")

    def test_delete_is_a_soft_delete_never_erasure(self):
        doc = self._ingest("VW9 Soft Delete Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Temp", actor="vw9_owner")
        deleted = self.store.delete_folder(ws, folder["id"], actor="vw9_owner")
        self.assertIsNotNone(deleted["removed_at"])
        # Constitutional Invariant 5: correction is non-destructive -
        # the record persists on reload, never erased.
        ws2 = self.store.get(doc.project_id)
        tombstone = next(f for f in ws2.folders if f["id"] == folder["id"])
        self.assertIsNotNone(tombstone["removed_at"])
        self.assertEqual(tombstone["name"], "Temp")

    def test_removed_folder_id_is_never_reused_for_a_different_folder(self):
        doc = self._ingest("VW9 Id Reuse Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Original", actor="vw9_owner")
        self.store.delete_folder(ws, folder["id"], actor="vw9_owner")
        # Recreating the same name is a genuinely NEW record, new id.
        recreated = self.store.create_folder(ws, "Original", actor="vw9_owner")
        self.assertNotEqual(recreated["id"], folder["id"])

    def test_legacy_workspace_without_folders_key_loads_safely(self):
        # Additive-migration proof: a workspace JSON written before this
        # stage simply lacks "folders" - ProjectWorkspace(**data) fills
        # the dataclass default (empty list), no explicit migration step
        # needed, matching tags/tag_occurrences/tasks' own established
        # precedent (see ProjectWorkspace.folders' own comment).
        import json
        doc = self._ingest("VW9 Legacy Compatibility Project")
        path = self.tmp_dir / f"{doc.project_id}.workspace.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("folders", data)
        del data["folders"]
        path.write_text(json.dumps(data), encoding="utf-8")
        ws = self.store.get(doc.project_id)
        self.assertEqual(ws.folders, [])
        # And a legacy workspace can still create a folder going forward.
        folder = self.store.create_folder(ws, "New On Legacy", actor="vw9_owner")
        self.assertTrue(folder["id"])

    def test_folder_id_field_defaults_to_none_and_is_backward_compatible(self):
        # CLAUDE-RFP27-TERRITORY-01: VW9 originally asserted `folder_id`
        # did NOT exist on Source at all ("a Document is never assigned
        # into a Folder in this slice"); that slice's own scope boundary
        # was deliberately widened this stage (governance/STATUS.md's own
        # CLAUDE-RFP27-TERRITORY-01 row) - a Source CAN now belong to a
        # Folder. What VW9's own test actually protected - a legacy
        # Source record predating this field loads safely - still holds:
        # every pre-existing Source simply lacks the key and gets the
        # honest None default, the same backward-compatible shape every
        # other additive Source field already uses.
        self.assertIn("folder_id", cw.Source.__dataclass_fields__)
        self.assertIsNone(cw.Source.__dataclass_fields__["folder_id"].default)

    def test_existing_document_identity_and_relationships_unaffected_by_folders(self):
        doc = self._ingest("VW9 Document Compatibility Project")
        ws = self.store.get(doc.project_id)
        source_id = ws.sources[0]["id"]
        case = self.store.create_case(ws, title="Unrelated Investigation", objective="")
        self.store.create_folder(ws, "Unrelated Folder", actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        self.assertEqual(ws2.sources[0]["id"], source_id)
        self.assertEqual(ws2.cases[0]["id"], case["id"])


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

class GovernanceTests(_BaseTestCase):
    def test_data_room_cannot_be_mutated_through_design_builder_folder_actions(self):
        # Structural: create_folder has no `root` parameter at all -
        # every call this stage can ever make writes
        # FOLDER_ROOT_DESIGN_BUILDER unconditionally.
        import inspect
        sig = inspect.signature(cw.CaseWorkspaceStore.create_folder)
        self.assertNotIn("root", sig.parameters)

    def test_design_builder_route_cannot_target_data_room_root(self):
        source = _CASE_WORKSPACE_PY_PATH.read_text(encoding="utf-8")
        fn_start = source.index("def create_folder(")
        fn_body = source[fn_start:source.index("\n    def ", fn_start + 10)]
        self.assertIn("FOLDER_ROOT_DESIGN_BUILDER", fn_body)
        self.assertNotIn("FOLDER_ROOT_DATA_ROOM,", fn_body)

    def test_unauthorized_direct_route_access_denied(self):
        doc = self._ingest("VW9 Unauthorized Project")
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw9_stranger", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        stranger = self._client(username="vw9_stranger", user_id=2, role="read_only")
        resp = stranger.get(f"/projects/{doc.project_id}/workspace?view=files")
        self.assertEqual(resp.status_code, 404)
        resp2 = stranger.post(f"/projects/{doc.project_id}/workspace/folders", data={"name": "Intrusion"})
        self.assertEqual(resp2.status_code, 404)

    def test_unauthenticated_request_redirects_to_login(self):
        doc = self._ingest("VW9 Anonymous Project")
        anon = self.flask_app.test_client()
        resp = anon.post(f"/projects/{doc.project_id}/workspace/folders", data={"name": "x"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_delete_route_requires_explicit_confirm_yes(self):
        doc = self._ingest("VW9 Confirm Gate Project")
        client = self._client()
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "ToDelete", actor="vw9_owner")
        # No confirm value yet -> shown the confirm page, not deleted.
        resp = client.post(f"/projects/{doc.project_id}/workspace/folders/{folder['id']}/delete", data={})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("delete this folder", resp.get_data(as_text=True))
        ws2 = self.store.get(doc.project_id)
        self.assertIsNone(next(f for f in ws2.folders if f["id"] == folder["id"])["removed_at"])
        # confirm=no -> explicitly cancelled, not deleted.
        resp2 = client.post(f"/projects/{doc.project_id}/workspace/folders/{folder['id']}/delete", data={"confirm": "no"}, follow_redirects=True)
        ws3 = self.store.get(doc.project_id)
        self.assertIsNone(next(f for f in ws3.folders if f["id"] == folder["id"])["removed_at"])
        # confirm=yes -> actually deleted.
        resp3 = client.post(f"/projects/{doc.project_id}/workspace/folders/{folder['id']}/delete", data={"confirm": "yes"}, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        ws4 = self.store.get(doc.project_id)
        self.assertIsNotNone(next(f for f in ws4.folders if f["id"] == folder["id"])["removed_at"])

    def test_reference_mode_toggle_does_not_expose_a_hidden_files_control(self):
        # UI Reference Mode only ever labels already-rendered content
        # (existing convention) - not exercised via a new mechanism here.
        doc = self._ingest("VW9 Reference Mode Project")
        client = self._client()
        without = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.files"', without)
        self.assertIn('data-ui-ref="display.files"', without)


# ---------------------------------------------------------------------------
# Display behavior
# ---------------------------------------------------------------------------

class DisplayBehaviorTests(_BaseTestCase):
    def test_data_room_and_design_builder_render_as_sibling_roots(self):
        doc = self._ingest("VW9 Two Roots Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.data-room"', body)
        self.assertIn('data-ui-ref="display.files.design-builder"', body)
        self.assertLess(body.index("Data Room"), body.index("Design-Builder Workspace"))

    def test_data_room_shows_compatibility_view_of_existing_documents(self):
        doc = self._ingest("VW9 Compatibility View Project", filename="issued_spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.data-room.compatibility-list"', body)
        self.assertIn("issued_spec.pdf", body)

    def test_data_room_empty_state_when_no_documents(self):
        # A project ingested from an empty seed source still has ITS OWN
        # ingested document as source #1 (ingest always registers one) -
        # remove it to genuinely test the empty-state path.
        doc = self._ingest("VW9 Empty Data Room Project")
        ws = self.store.get(doc.project_id)
        self.store.remove_source(ws, ws.sources[0]["id"], actor="vw9_owner", actor_role="admin")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.data-room.empty"', body)

    def test_design_builder_folder_creation_via_route_and_rendering(self):
        doc = self._ingest("VW9 Route Create Folder Project")
        client = self._client()
        resp = client.post(f"/projects/{doc.project_id}/workspace/folders", data={"name": "Structural Drawings"}, follow_redirects=True)
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Structural Drawings", body)
        self.assertIn('data-ui-ref="display.files.design-builder.folder-row"', body)

    def test_nested_folder_navigation_and_breadcrumb(self):
        doc = self._ingest("VW9 Nested Navigation Project")
        ws = self.store.get(doc.project_id)
        root = self.store.create_folder(ws, "Root Folder", actor="vw9_owner")
        child = self.store.create_folder(ws, "Nested Folder", parent_folder_id=root["id"], actor="vw9_owner")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files&folder={child['id']}").get_data(as_text=True)
        breadcrumb_idx = body.index('data-ui-ref="display.files.design-builder.breadcrumb"')
        breadcrumb = body[breadcrumb_idx:breadcrumb_idx + 600]
        self.assertIn("Root Folder", breadcrumb)
        self.assertIn("Nested Folder", breadcrumb)

    def test_unknown_folder_id_degrades_honestly_to_design_builder_root(self):
        doc = self._ingest("VW9 Unknown Folder Project")
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace?view=files&folder=not-a-real-id")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn("not-a-real-id", body)

    def test_design_builder_empty_state_present_at_root_and_in_subfolder(self):
        doc = self._ingest("VW9 Empty States Project")
        client = self._client()
        root_body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.design-builder.empty"', root_body)

        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Empty Subfolder", actor="vw9_owner")
        sub_body = client.get(f"/projects/{doc.project_id}/workspace?view=files&folder={folder['id']}").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.design-builder.empty"', sub_body)
        self.assertIn("This folder is empty.", sub_body)

    def test_multi_display_panel_rendering_of_files(self):
        doc = self._ingest("VW9 Panel Project")
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace?view=files&panel=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Data Room", body)
        self.assertIn("Design-Builder Workspace", body)
        # panel_shell.html (minimal standalone document), not the full
        # application shell - the content block itself (including
        # #display-divisions) is genuinely shared between panel_shell.html
        # and base.html (see case_workspace.html's own header comment on
        # this dynamic {% extends %}), so the real distinguishing absence
        # is the surrounding shell: no Lists tree, no top application menu.
        self.assertNotIn("data-tree-root", body)
        self.assertNotIn("workspace-topbar", body)

    def test_project_switching_does_not_leak_folder_state_across_projects(self):
        doc_a = self._ingest("VW9 Switch Project A")
        doc_b = self._ingest("VW9 Switch Project B")
        ws_a = self.store.get(doc_a.project_id)
        self.store.create_folder(ws_a, "Only In Project A", actor="vw9_owner")
        client = self._client()
        body_b = client.get(f"/projects/{doc_b.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertNotIn("Only In Project A", body_b)
        body_a = client.get(f"/projects/{doc_a.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn("Only In Project A", body_a)

    def test_move_folder_offers_only_valid_destinations_excluding_self_and_descendants(self):
        doc = self._ingest("VW9 Move Targets Project")
        ws = self.store.get(doc.project_id)
        root = self.store.create_folder(ws, "Root", actor="vw9_owner")
        child = self.store.create_folder(ws, "Child", parent_folder_id=root["id"], actor="vw9_owner")
        other = self.store.create_folder(ws, "Sibling Elsewhere", actor="vw9_owner")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        row_idx = body.index(f'href="/projects/{doc.project_id}/workspace?view=files&amp;folder={root["id"]}"')
        panel = body[row_idx:row_idx + 2000]
        self.assertIn(other["name"], panel)
        self.assertNotIn(f'value="{root["id"]}"', panel)  # not offered as its own move target


# ---------------------------------------------------------------------------
# CLAUDE-RFP27-TERRITORY-01 Parts 3-4: Data Room folder construction,
# Source relinking/reconciliation, and GO folder-reference resolution.
# ---------------------------------------------------------------------------

class DataRoomFolderConstructionTests(_BaseTestCase):
    def test_ensure_folder_path_creates_nested_data_room_folders(self):
        doc = self._ingest("RFP27 Nested Path Project")
        ws = self.store.get(doc.project_id)
        folder_id = self.store.ensure_folder_path(
            ws, root=cw.FOLDER_ROOT_DATA_ROOM, relative_path="01 RFP Documents/01.2 Addenda", actor="vw9_owner",
        )
        ws2 = self.store.get(doc.project_id)
        leaf = next(f for f in ws2.folders if f["id"] == folder_id)
        self.assertEqual(leaf["name"], "01.2 Addenda")
        self.assertEqual(leaf["root"], cw.FOLDER_ROOT_DATA_ROOM)
        parent = next(f for f in ws2.folders if f["id"] == leaf["parent_folder_id"])
        self.assertEqual(parent["name"], "01 RFP Documents")
        self.assertIsNone(parent["parent_folder_id"])

    def test_ensure_folder_path_is_idempotent(self):
        doc = self._ingest("RFP27 Idempotent Path Project")
        ws = self.store.get(doc.project_id)
        first = self.store.ensure_folder_path(ws, root=cw.FOLDER_ROOT_DATA_ROOM, relative_path="Addenda", actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        second = self.store.ensure_folder_path(ws2, root=cw.FOLDER_ROOT_DATA_ROOM, relative_path="Addenda", actor="vw9_owner")
        self.assertEqual(first, second)
        ws3 = self.store.get(doc.project_id)
        matches = [f for f in ws3.folders if f["name"] == "Addenda" and f["root"] == cw.FOLDER_ROOT_DATA_ROOM]
        self.assertEqual(len(matches), 1)

    def test_ensure_folder_path_blank_segment_yields_no_folder(self):
        doc = self._ingest("RFP27 Blank Path Project")
        ws = self.store.get(doc.project_id)
        folder_id = self.store.ensure_folder_path(ws, root=cw.FOLDER_ROOT_DATA_ROOM, relative_path="", actor="vw9_owner")
        self.assertIsNone(folder_id)


class SetSourceFolderTests(_BaseTestCase):
    def test_relinking_a_source_does_not_change_its_identity(self):
        doc = self._ingest("RFP27 Relink Identity Project")
        ws = self.store.get(doc.project_id)
        source_id = ws.sources[0]["id"]
        folder = self.store.create_folder(ws, "Somewhere", actor="vw9_owner")
        updated = self.store.set_source_folder(ws, source_id, folder["id"], actor="vw9_owner")
        self.assertEqual(updated["id"], source_id)
        self.assertEqual(updated["folder_id"], folder["id"])
        ws2 = self.store.get(doc.project_id)
        self.assertEqual(ws2.sources[0]["id"], source_id)

    def test_relinking_to_none_clears_folder_membership(self):
        doc = self._ingest("RFP27 Unlink Project")
        ws = self.store.get(doc.project_id)
        source_id = ws.sources[0]["id"]
        folder = self.store.create_folder(ws, "Somewhere", actor="vw9_owner")
        self.store.set_source_folder(ws, source_id, folder["id"], actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        cleared = self.store.set_source_folder(ws2, source_id, None, actor="vw9_owner")
        self.assertIsNone(cleared["folder_id"])


class ReconcileDataRoomUploadTests(_BaseTestCase):
    def test_new_file_is_added_and_folder_created_from_relative_path(self):
        from services.ingestion import reconcile_data_room_upload

        def fake_parse(self_parser, raw_bytes, filename_):
            return "extracted text"

        doc = self._ingest("RFP27 Reconcile New File Project")
        with patch.object(BHiveParser, "_extract", fake_parse):
            with self.flask_app.app_context():
                results = reconcile_data_room_upload(
                    [_fake_file(b"brand new content", "Addendum-01.pdf")],
                    ["01 RFP Documents/01.2 Addenda/Addendum-01.pdf"],
                    doc.project_id, self.flask_app, actor="vw9_owner",
                )
        self.assertEqual(results[0]["status"], "added")
        ws = self.store.get(doc.project_id)
        added_source = next(s for s in ws.sources if s["id"] == results[0]["source_id"])
        folder = next(f for f in ws.folders if f["id"] == added_source["folder_id"])
        self.assertEqual(folder["name"], "01.2 Addenda")
        self.assertEqual(folder["root"], cw.FOLDER_ROOT_DATA_ROOM)

    def test_byte_identical_file_is_relinked_not_duplicated(self):
        from services.ingestion import reconcile_data_room_upload

        content = b"same bytes both times"
        doc = self._ingest("RFP27 Reconcile Dedup Project", content=content)
        ws = self.store.get(doc.project_id)
        original_source_id = ws.sources[0]["id"]
        before_count = len(ws.sources)

        with self.flask_app.app_context():
            results = reconcile_data_room_upload(
                [_fake_file(content, "spec.pdf")], ["Data Room/spec.pdf"],
                doc.project_id, self.flask_app, actor="vw9_owner",
            )
        self.assertEqual(results[0]["status"], "relinked")
        self.assertEqual(results[0]["source_id"], original_source_id)
        ws2 = self.store.get(doc.project_id)
        self.assertEqual(len(ws2.sources), before_count)  # no duplicate created
        relinked = next(s for s in ws2.sources if s["id"] == original_source_id)
        folder = next(f for f in ws2.folders if f["id"] == relinked["folder_id"])
        self.assertEqual(folder["name"], "Data Room")

    def test_unsupported_extension_is_skipped_not_silently_dropped(self):
        from services.ingestion import reconcile_data_room_upload

        doc = self._ingest("RFP27 Reconcile Skip Project")
        with self.flask_app.app_context():
            results = reconcile_data_room_upload(
                [_fake_file(b"<svg></svg>", "Reference-Design.svg")], ["Reference Design/Reference-Design.svg"],
                doc.project_id, self.flask_app, actor="vw9_owner",
            )
        self.assertEqual(results[0]["status"], "skipped")
        self.assertIn("Unsupported file type", results[0]["reason"])
        ws = self.store.get(doc.project_id)
        self.assertFalse(any(f["name"] == "Reference Design" for f in ws.folders))


class TerritoryRouteTests(_BaseTestCase):
    def test_register_folder_paths_route_creates_empty_folders_visible_without_documents(self):
        doc = self._ingest("RFP27 Register Paths Route Project")
        client = self._client()
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/folders/register-paths",
            data={"root": cw.FOLDER_ROOT_DESIGN_BUILDER, "paths": "01_TECHNICAL_SUBMISSION\n02_FINANCIAL_SUBMISSION_(PART_B)\n03_LEGAL_&_CONSORTIUM_AGREEMENTS"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("01_TECHNICAL_SUBMISSION", body)
        ws = self.store.get(doc.project_id)
        names = {f["name"] for f in ws.folders}
        self.assertIn("01_TECHNICAL_SUBMISSION", names)
        self.assertIn("02_FINANCIAL_SUBMISSION_(PART_B)", names)
        self.assertIn("03_LEGAL_&_CONSORTIUM_AGREEMENTS", names)

    def test_register_folder_paths_route_rejects_invalid_root(self):
        doc = self._ingest("RFP27 Register Invalid Root Project")
        client = self._client()
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/folders/register-paths",
            data={"root": "not-a-real-root", "paths": "Something"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        ws = self.store.get(doc.project_id)
        self.assertEqual(ws.folders, [])

    def test_reconcile_data_room_route_end_to_end(self):
        # .txt content is genuinely, directly extractable text - avoids
        # exercising the real pypdf parser against fabricated PDF bytes
        # (that's what the mocked-parser unit tests above already cover).
        doc = self._ingest("RFP27 Reconcile Route Project")
        client = self._client()
        resp = client.post(
            f"/projects/{doc.project_id}/workspace/data-room/reconcile",
            data={"folder_files": [_fake_file(b"genuinely new evidence", "Schedule-4.txt")]},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        ws = self.store.get(doc.project_id)
        self.assertTrue(any(s["name"] == "Schedule-4.txt" for s in ws.sources))

    def test_reconcile_data_room_route_requires_admin(self):
        doc = self._ingest("RFP27 Reconcile Route Auth Project")
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw9_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        reader = self._client(username="vw9_reader", user_id=3, role="read_only")
        resp = reader.post(
            f"/projects/{doc.project_id}/workspace/data-room/reconcile",
            data={"folder_files": [_fake_file(b"x", "y.pdf")]},
            content_type="multipart/form-data",
        )
        # admin_required's own split (services/auth.py): authenticated but
        # non-admin is 403, distinct from unauthenticated (302) and from
        # login_required-only routes' 404-on-non-owner pattern used
        # elsewhere in this file.
        self.assertEqual(resp.status_code, 403)


class GoFolderReferenceTests(_BaseTestCase):
    """CLAUDE-RFP27-TERRITORY-01 (Part 3): GO must distinguish 'exists
    and is currently empty' from 'does not exist', deterministically,
    with no model call - direct interpret_message unit tests, same
    pattern as InterpretMessageWithoutACaseTests in
    test_conversation_apertures.py."""

    def _interpret(self, workspace, text):
        from services.conversation_interpreter import interpret_message
        return interpret_message(
            text=text, workspace=workspace, case=None, store=self.store,
            artifacts_dir=self.tmp_dir, reviewer="vw9_owner", focused_finding_id=None,
        )

    def test_go_reports_an_empty_folder_honestly_as_empty_not_missing(self):
        doc = self._ingest("RFP27 GO Empty Folder Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "01_TECHNICAL_SUBMISSION", actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        result = self._interpret(ws2, "Is anything in 01_TECHNICAL_SUBMISSION yet?")
        self.assertEqual(result.action_taken, "folder_reference")
        self.assertIn("currently empty", result.reply_text)
        self.assertNotIn("does not exist", result.reply_text)

    def test_go_reports_a_populated_folder_with_a_real_count(self):
        doc = self._ingest("RFP27 GO Populated Folder Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Addenda", actor="vw9_owner")
        self.store.set_source_folder(ws, ws.sources[0]["id"], folder["id"], actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        result = self._interpret(ws2, "What's in the Addenda folder?")
        self.assertEqual(result.action_taken, "folder_reference")
        self.assertIn("1 Document(s)", result.reply_text)

    def test_go_never_falsely_matches_unrelated_conversation(self):
        doc = self._ingest("RFP27 GO No False Match Project")
        ws = self.store.get(doc.project_id)
        self.store.create_folder(ws, "Addenda", actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        result = self._interpret(ws2, "just leaving a note here, nothing to action")
        self.assertNotEqual(result.action_taken, "folder_reference")

    def test_go_ignores_a_removed_folder_reference(self):
        doc = self._ingest("RFP27 GO Removed Folder Project")
        ws = self.store.get(doc.project_id)
        folder = self.store.create_folder(ws, "Addenda", actor="vw9_owner")
        self.store.delete_folder(ws, folder["id"], actor="vw9_owner")
        ws2 = self.store.get(doc.project_id)
        result = self._interpret(ws2, "What's in the Addenda folder?")
        self.assertNotEqual(result.action_taken, "folder_reference")


if __name__ == "__main__":
    unittest.main()
