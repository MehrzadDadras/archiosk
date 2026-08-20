"""
Project Home (Prompt 3): the calm, project-first landing state for an
opened Project, reached whenever /projects/<id>/workspace is visited
without ?case=. The deep, existing Case Workspace (Sources/Cases/
Requirements/RFI Export/History in the always-visible left aside;
Conversation/Findings once a Case is selected) is completely unchanged -
these tests only cover the new landing state and its own routes:
Star, Edit Project Details, Project/Case Operating Instructions,
Project Sources (Add Documents / Add Text Record), the central composer
(quick-start into a new Investigation), and Create Snapshot.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class ProjectHomeTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_home_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-home"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    # -- landing state -----------------------------------------------------

    def test_opening_a_project_lands_on_project_home_not_a_case(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 5): the bare workspace URL
        # (no ?view=) no longer lands on Project Home by default - Display
        # is blank unless a leaf is explicitly selected, and "Overview" is
        # now that explicit leaf (?view=overview). The chat composer
        # (shell-level, Section 9) still renders regardless, since Chat is
        # not part of Display's own blank/non-blank state.
        response = self.client.get(f"/projects/{self.project_id}/workspace")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id="project-overview"', body)
        self.assertIn("Ask a question, or describe what you want to work on", body)
        self.assertNotIn("workspace-topbar-sep", body)

        overview_response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        overview_body = overview_response.get_data(as_text=True)
        self.assertEqual(overview_response.status_code, 200)
        # CLAUDE-P40-E1: the separate "Start or continue project work"
        # composer (placeholder "What are we working on?") was removed -
        # the single Project Conversation dock composer now covers both
        # a plain question and a real "start work" request.
        self.assertIn("Ask a question, or describe what you want to work on", overview_body)
        # CLAUDE-P38-C: this explanation moved behind a collapsed
        # "What is Project State?" disclosure - still present in the
        # rendered HTML (a <details> element's content is always in the
        # DOM, just visually collapsed), only reformatted onto several
        # source lines, so checked as separate fragments rather than one
        # exact-whitespace string.
        self.assertIn("What is Project State?", overview_body)
        self.assertIn("You are working inside the current governed project state.", overview_body)
        self.assertIn("New work inherits its sources,", overview_body)
        # CLAUDE-P40-E2B: the page_header <h1> (was renamed from "Case
        # Workspace" to "Workspace" under P40-E) is gone entirely,
        # replaced by the top bar's own breadcrumb. SUPERSEDED here
        # (CLAUDE-P40-E3A): Overview is now itself a real breadcrumb leaf
        # (base.html's own "elif directory_view == 'overview'" branch), so
        # the separator DOES render for it too - it's no longer exclusive
        # to an active Investigation/Document.
        self.assertIn("workspace-topbar-sep", overview_body)
        self.assertIn(">Overview<", overview_body)

    def test_explicit_case_param_still_reaches_deep_case_view(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Structural Drawing Review", "objective": "x"}, follow_redirects=True,
        )
        case = self._store().get(self.project_id).cases[0]

        response = self.client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)

        self.assertIn("workspace-topbar-sep", body)
        self.assertIn("Structural Drawing Review", body)
        self.assertNotIn("Ask a question, or describe what you want to work on", body)

    def test_left_aside_always_visible_regardless_of_case_selection(self):
        # Requirements/RFIs/History are project-scoped, not Case-scoped -
        # they must stay reachable even with zero Cases. ("RFI Export"
        # renamed to "RFIs" - CLAUDE-P38 OBS-08.) SUPERSEDED (CLAUDE-P40-
        # E3A): this content now lives behind the explicit Overview leaf
        # (?view=overview), not the bare workspace URL (Section 5 - blank
        # by default). Sources/Documents moved out of Display entirely -
        # their names now live directly beneath the Project root in Lists
        # (the later project-root correction retired the visible Documents
        # wrapper and its count).
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)

        self.assertIn("Project Instructions", body)
        self.assertIn(">RFI Correspondence<", body)
        self.assertIn("History (", body)

        self.assertEqual(body.count('data-ui-ref="lists.project.documents.leaf"'), 1)
        self.assertNotIn('data-ui-ref="lists.project.documents"', body)
        self.assertIn("rfp.md", body)

    # -- star ----------------------------------------------------------------

    def test_star_toggle_persists_and_has_no_governance_event(self):
        response = self.client.post(f"/projects/{self.project_id}/workspace/star", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._store().get(self.project_id).starred)
        self.assertIn(">&#9733;<", response.get_data(as_text=True))

        from services.governance import GovernanceLog
        events = GovernanceLog(self.tmp_dir).read(self.project_id)
        self.assertFalse(any(e.event_type == "project_starred" for e in events))

    def test_star_toggle_twice_returns_to_unstarred(self):
        self.client.post(f"/projects/{self.project_id}/workspace/star")
        self.client.post(f"/projects/{self.project_id}/workspace/star")
        self.assertFalse(self._store().get(self.project_id).starred)

    # -- project details -------------------------------------------------------

    def test_edit_project_details_updates_home_header(self):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/details",
            data={"display_title": "NREOCRC", "display_description": "North River Emergency Operations Centre"},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)

        self.assertIn("NREOCRC", body)
        self.assertIn("North River Emergency Operations Centre", body)
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.display_title, "NREOCRC")

    # -- operating instructions -------------------------------------------------

    def test_operating_instructions_saved_and_shown_subordinate_to_governance(self):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/instructions",
            data={"instructions": "Owner priority: schedule over cost."},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)

        self.assertIn("Owner priority: schedule over cost.", body)
        self.assertIn("subordinate to Archiosk governance", body)
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.operating_instructions, "Owner priority: schedule over cost.")
        self.assertEqual(workspace.operating_instructions_updated_by, "tester")

    # -- project sources ---------------------------------------------------------

    def test_add_text_record_source_becomes_a_project_source(self):
        # SUPERSEDED (CLAUDE-P40-E3A): the retired "Sources (N)" Display
        # heading is gone - confirmation is now the success flash plus
        # Lists' direct project-file leaves, present on the redirect
        # target (view=overview, Section 5's own required consequence -
        # see routes/workspace.py's own note on this redirect target).
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/sources/text-record",
            data={"title": "Site visit note", "content": "Observed standing water near loading dock."},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)

        self.assertIn("Text Record added as a Project Source.", body)
        self.assertEqual(body.count('data-ui-ref="lists.project.documents.leaf"'), 2)
        self.assertNotIn('data-ui-ref="lists.project.documents"', body)
        self.assertIn("Site visit note", body)
        workspace = self._store().get(self.project_id)
        text_source = next(s for s in workspace.sources if s["kind"] == "text_record")
        self.assertEqual(Path(text_source["file_path"]).read_text(encoding="utf-8"), "Observed standing water near loading dock.")

    def test_add_document_source_rejects_unsupported_extension(self):
        data = {"document": (io.BytesIO(b"not a real doc"), "malware.exe")}
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertIn("Unsupported document format", response.get_data(as_text=True))
        self.assertEqual(len(self._store().get(self.project_id).sources), 1)

    def test_add_document_source_accepts_allowed_extension(self):
        data = {"document": (io.BytesIO(b"hello world"), "note.txt")}
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertIn("Document added as a Project Source.", body)
        self.assertEqual(body.count('data-ui-ref="lists.project.documents.leaf"'), 2)
        self.assertNotIn('data-ui-ref="lists.project.documents"', body)
        self.assertIn("note.txt", body)

    def test_external_source_shown_as_disabled_placeholder(self):
        # CLAUDE-P40-E2B1: Sources/Documents moved out of Project Home
        # entirely into their own launcher-projected Documents directory
        # (?view=documents) - no longer reachable from the bare
        # Project Home URL.
        #
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 (Part B2) supersedes
        # this test's own original assertion: "+ Add External Source"
        # was retired from the rail entirely (the left rail is
        # "principally project switching + project/evidence navigation,
        # not an action drawer or administration panel") and parked at
        # Reserve/Spare Parts Yard status - see
        # governance/spare-parts-yard.md Section 3, which also notes it
        # was already inert before this stage (no real connector was
        # ever configured, only this same static placeholder message).
        # Nothing to assert present on this page anymore; assert its
        # absence instead, per this repo's own established convention
        # for a deliberately-changed invariant.
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=documents")
        body = response.get_data(as_text=True)
        self.assertNotIn("Add External Source", body)

    # -- composer / quick-start ---------------------------------------------------

    def test_quick_start_creates_investigation_and_posts_first_message(self):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Analyze this drawing for datum inconsistencies"},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)

        self.assertIn("workspace-topbar-sep", body)
        self.assertIn("Analyze this drawing for datum inconsistencies", body)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.cases), 1)
        self.assertEqual(workspace.cases[0]["title"], "Analyze this drawing for datum inconsistencies")

    def test_quick_start_requires_text(self):
        response = self.client.post(f"/projects/{self.project_id}/workspace/quick-start", data={"text": "  "}, follow_redirects=True)
        self.assertIn("Ask a question, or describe what you want to work on", response.get_data(as_text=True))
        self.assertEqual(len(self._store().get(self.project_id).cases), 0)

    # -- active work summary -------------------------------------------------------

    def test_active_work_summary_reflects_real_state(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Spec Review", "objective": "x"}, follow_redirects=True,
        )
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)

        self.assertIn("1 Investigation", body)
        self.assertIn("View Investigations (1)", body)
        self.assertIn("Spec Review", body)

    # -- snapshot --------------------------------------------------------------

    def test_create_snapshot_via_project_home(self):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots",
            data={"label": "Pre-Award baseline", "note": "test"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.snapshots), 1)
        self.assertEqual(workspace.snapshots[0]["label"], "Pre-Award baseline")

    def test_create_snapshot_requires_label(self):
        response = self.client.post(f"/projects/{self.project_id}/workspace/snapshots", data={}, follow_redirects=True)
        self.assertIn("needs a label", response.get_data(as_text=True))
        self.assertEqual(len(self._store().get(self.project_id).snapshots), 0)


if __name__ == "__main__":
    unittest.main()
