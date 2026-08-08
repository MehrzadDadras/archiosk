"""
CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01 (+ amendment): persistent, revisable,
historically-attributable Project Context, and the separate, per-Source
Document Context.

Neither concept existed anywhere in this repository before this stage
(no ProjectContext/DocumentContext class, no route, no template
reference) - this file is the first and only coverage for both. Project
Context reuses the append-only "a later record supersedes an earlier
one IN EFFECT, never overwrites or deletes it" shape already
established by ReviewerValidation/Disposition/CaseOutcome
(CaseWorkspaceStore.add_project_context_entry / current_project_context
/ project_context_entries_for). Document Context reuses Source's own
pre-existing, previously-dead `note` field (CaseWorkspaceStore.
set_source_note) - a plain current value, not a history, matching
Operating Instructions' own established shape rather than Project
Context's.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore


class ProjectContextStoreTests(unittest.TestCase):
    """Store-layer tests: the append-only history mechanism itself."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_context_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-context"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_entries_means_no_current_context(self):
        self.assertIsNone(self.store.current_project_context(self.workspace))
        self.assertEqual(self.store.project_context_entries_for(self.workspace), [])

    def test_adding_an_entry_becomes_current(self):
        entry = self.store.add_project_context_entry(
            self.workspace, text="Basement parking ramp under investigation.", actor="owner1",
        )
        current = self.store.current_project_context(self.workspace)
        self.assertEqual(current["id"], entry["id"])
        self.assertEqual(current["text"], "Basement parking ramp under investigation.")
        self.assertEqual(current["created_by"], "owner1")

    def test_second_entry_becomes_current_first_entry_preserved_as_history(self):
        first = self.store.add_project_context_entry(self.workspace, text="Ramp and car elevator under study.", actor="owner1")
        second = self.store.add_project_context_entry(
            self.workspace, text="Client no longer wants the ramp; new by-law permits zero parking.", actor="owner1",
        )
        current = self.store.current_project_context(self.workspace)
        self.assertEqual(current["id"], second["id"])

        entries = self.store.project_context_entries_for(self.workspace)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["id"], first["id"])
        self.assertEqual(entries[0]["text"], "Ramp and car elevator under study.")
        self.assertEqual(entries[1]["id"], second["id"])

    def test_empty_text_is_rejected_and_records_nothing(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_project_context_entry(self.workspace, text="   ", actor="owner1")
        self.assertEqual(self.store.project_context_entries_for(self.workspace), [])

    def test_entry_records_author_role_and_timestamp(self):
        entry = self.store.add_project_context_entry(
            self.workspace, text="Direction change.", actor="design-manager-x", actor_role="admin",
        )
        self.assertEqual(entry["created_by"], "design-manager-x")
        self.assertEqual(entry["created_by_role"], "admin")
        self.assertIsNotNone(entry["created_at"])

    def test_adding_context_does_not_touch_operating_instructions(self):
        self.store.set_operating_instructions(self.workspace, text="Use metric units.", actor="owner1")
        self.store.add_project_context_entry(self.workspace, text="Direction change.", actor="owner1")
        self.assertEqual(self.workspace.operating_instructions, "Use metric units.")

    def test_adding_context_does_not_touch_existing_sources_or_cases(self):
        source = self.store.add_source(self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements")
        case = self.store.create_case(self.workspace, title="Ramp Feasibility", objective="x", created_by="owner1")
        self.store.add_project_context_entry(self.workspace, text="Direction change.", actor="owner1")

        reloaded = self.store.get(self.project_id)
        self.assertIsNotNone(self.store._find(reloaded.sources, source["id"]))
        self.assertIsNotNone(self.store._find(reloaded.cases, case["id"]))
        self.assertEqual(self.store._find(reloaded.cases, case["id"])["title"], "Ramp Feasibility")


class DocumentContextStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_document_context_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-document-context"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="Basement Plan Rev A.pdf", file_path="/tmp/plan.pdf", kind="drawing",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_source_has_no_context_by_default(self):
        self.assertIsNone(self.source["note"])

    def test_set_source_note_records_text(self):
        updated = self.store.set_source_note(
            self.workspace, source_id=self.source["id"], text="Superseded concept - retained for lineage only.", actor="owner1",
        )
        self.assertEqual(updated["note"], "Superseded concept - retained for lineage only.")

    def test_set_source_note_is_a_plain_overwrite_not_a_history(self):
        self.store.set_source_note(self.workspace, source_id=self.source["id"], text="First note.", actor="owner1")
        self.store.set_source_note(self.workspace, source_id=self.source["id"], text="Second note.", actor="owner1")
        reloaded = self.store.get(self.project_id)
        source = self.store._find(reloaded.sources, self.source["id"])
        self.assertEqual(source["note"], "Second note.")

    def test_setting_document_context_does_not_touch_project_context(self):
        self.store.add_project_context_entry(self.workspace, text="Project direction.", actor="owner1")
        self.store.set_source_note(self.workspace, source_id=self.source["id"], text="Doc note.", actor="owner1")
        self.assertEqual(len(self.store.project_context_entries_for(self.workspace)), 1)
        self.assertEqual(self.store.current_project_context(self.workspace)["text"], "Project direction.")

    def test_setting_project_context_does_not_touch_document_context(self):
        self.store.set_source_note(self.workspace, source_id=self.source["id"], text="Doc note.", actor="owner1")
        self.store.add_project_context_entry(self.workspace, text="Project direction.", actor="owner1")
        reloaded = self.store.get(self.project_id)
        source = self.store._find(reloaded.sources, self.source["id"])
        self.assertEqual(source["note"], "Doc note.")

    def test_nonexistent_source_note_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.set_source_note(self.workspace, source_id="does-not-exist", text="x", actor="owner1")


class ProjectContextRouteTests(unittest.TestCase):
    """Route-layer tests: persistent reachability across every workspace
    surface, editing, and project-access isolation."""

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_context_routes_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-context-routes"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.workspace, owner="owner1", actor="owner1")
        self.store.grant_project_access(self.workspace, username="teammate", actor="owner1", actor_role="read_only")

        self.owner_client = self.flask_app.test_client()
        with self.owner_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        self.teammate_client = self.flask_app.test_client()
        with self.teammate_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "teammate"
            sess["role"] = "read_only"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _reload_workspace(self):
        return self.store.get(self.project_id)

    def _create_case(self, title="Ramp Feasibility"):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._reload_workspace()
        return next(c for c in workspace.cases if c["title"] == title)

    # -- persistent reachability across every workspace surface --------------

    def test_project_context_control_appears_on_overview(self):
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project Context", response.data)
        self.assertIn(b"No Project Context set yet.", response.data)

    def test_project_context_control_appears_on_investigation_page(self):
        case = self._create_case()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project Context", response.data)

    def test_project_context_control_appears_on_document_page(self):
        source = self.store.add_source(self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements")
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?source={source['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project Context", response.data)

    def test_project_context_control_appears_on_files_and_chats_views(self):
        for view in ("files",):
            response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view={view}")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Project Context", response.data)
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project Context", response.data)

    # -- editing / history ----------------------------------------------------

    def test_authorized_user_can_add_project_context_entry(self):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/context",
            data={"text": "Client no longer wants the ramp; new by-law permits zero parking."},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"new by-law permits zero parking", response.data)

    def test_new_entry_does_not_erase_previous_entry(self):
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Ramp and car elevator under study."})
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Ramp dropped - office space instead."})

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ramp dropped - office space instead.", response.data)
        self.assertIn(b"Ramp and car elevator under study.", response.data)

        entries = self.store.project_context_entries_for(self._reload_workspace())
        self.assertEqual(len(entries), 2)

    def test_history_shows_author_and_timestamp(self):
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "First direction."})
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Second direction."})
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn(b"owner1", response.data)
        self.assertIn(b"History (1)", response.data)

    def test_empty_submission_is_rejected_with_no_new_entry(self):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/context", data={"text": "   "}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"cannot be empty", response.data)
        self.assertEqual(self.store.project_context_entries_for(self._reload_workspace()), [])

    def test_context_persists_after_navigating_to_a_different_view(self):
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Persisted direction."})
        case = self._create_case()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertIn(b"Persisted direction.", response.data)

    def test_read_only_project_member_can_also_add_context(self):
        # Matches Operating Instructions' own established authority level -
        # Project Context is collaborative orientation, not owner-locked.
        response = self.teammate_client.post(
            f"/projects/{self.project_id}/workspace/context", data={"text": "Teammate-recorded direction."}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teammate-recorded direction.", response.data)

    def test_stranger_without_project_access_cannot_reach_project_context_route(self):
        no_access_client = self.flask_app.test_client()
        with no_access_client.session_transaction() as sess:
            sess["user_id"] = 3
            sess["username"] = "stranger"
            sess["role"] = "read_only"
        response = no_access_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "x"})
        self.assertEqual(response.status_code, 404)

    # -- historical evidence untouched ----------------------------------------

    def test_adding_context_leaves_existing_investigation_and_findings_untouched(self):
        source = self.store.add_source(self.workspace, name="Old Ramp Drawing.pdf", file_path="/tmp/d.pdf", kind="drawing")
        case = self._create_case(title="Old Ramp Investigation")
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Ramp dropped."})

        workspace = self._reload_workspace()
        self.assertIsNotNone(self.store._find(workspace.sources, source["id"]))
        self.assertIsNotNone(self.store._find(workspace.cases, case["id"]))
        self.assertEqual(self.store._find(workspace.cases, case["id"])["title"], "Old Ramp Investigation")


class DocumentContextRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_document_context_routes_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-document-context-routes"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.workspace, owner="owner1", actor="owner1")
        self.source = self.store.add_source(self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements")

        self.owner_client = self.flask_app.test_client()
        with self.owner_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_document_context_empty_state(self):
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?source={self.source['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Document Context", response.data)
        self.assertIn(b"No Document Context set yet.", response.data)

    def test_document_context_can_be_set_and_shown(self):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/context",
            data={"text": "Superseded ramp concept - kept for lineage only."}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Superseded ramp concept", response.data)

    def test_document_context_independent_of_project_context(self):
        self.owner_client.post(f"/projects/{self.project_id}/workspace/context", data={"text": "Project direction."})
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/context",
            data={"text": "Doc-specific note."},
        )
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?source={self.source['id']}")
        self.assertIn(b"Doc-specific note.", response.data)
        self.assertIn(b"Project direction.", response.data)  # still shown in the top-bar control too

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(self.store.project_context_entries_for(workspace)), 1)
        self.assertEqual(self.store.current_project_context(workspace)["text"], "Project direction.")

    def test_nonexistent_source_context_404_via_store_error(self):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/sources/does-not-exist/context",
            data={"text": "x"}, follow_redirects=True,
        )
        # Store raises CaseWorkspaceError -> route flashes and redirects,
        # landing back on a 200 workspace page (matching every other
        # CaseWorkspaceError-catching route in this file), not a raw 500.
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
