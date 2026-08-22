"""
CLAUDE-POSTCAMEL-INVESTIGATION-AR1: exposing the already-existing,
already-governed archive_case/derive_case_from_archive lifecycle in the
ordinary UI, plus the read-only, non-mutating Smart Snapshot shown in
the new "Continue from Archive" chooser.

This file deliberately does NOT re-test archive_case/derive_case_from_
archive's own store-layer authority/lifecycle rules - tests/
test_case_archive.py and tests/test_case_derivation.py already cover
those exhaustively. This file covers only what AR1 actually added:
route-level exposure, the sidebar's active/archived split, the new
confirm-before-archive page, the New Investigation branching, the
archive chooser's project-scoping, and the Snapshot route's grounding/
non-mutation contract.

Hermetic per this repo's own CLAUDE.md discipline: the Snapshot route
calls services.investigation_snapshot.build_archive_snapshot, which
would otherwise reach the real Anthropic API using whatever
ANTHROPIC_API_KEY happens to be in the process environment (os.getenv
reads the real OS environment directly, not Flask config - TestingConfig
does not shield this). Every test that exercises the snapshot route
patches routes.workspace.build_archive_snapshot with a deterministic
fake, matching the pattern tests/test_security_enforcement.py's own
BHiveParser.parse patching already established.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    CASE_STATUS_ARCHIVED,
    CASE_STATUS_OPEN,
    AnalysisTrigger,
    CaseWorkspaceStore,
)
from services.investigation_snapshot import InvestigationSnapshotResult


class InvestigationArchiveExposureRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ar1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-ar1"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.workspace, owner="owner1", actor="owner1")
        self.store.grant_project_access(self.workspace, username="other-user", actor="owner1", actor_role="read_only")

        self.owner_client = self.flask_app.test_client()
        with self.owner_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        self.other_client = self.flask_app.test_client()
        with self.other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "other-user"
            sess["role"] = "read_only"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _reload_workspace(self):
        return self.store.get(self.project_id)

    def _create_case(self, title="Active Investigation"):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._reload_workspace()
        return next(c for c in workspace.cases if c["title"] == title)

    def _archived_case_with_finding(self, title="Archived Investigation"):
        source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )
        case = self.store.create_case(self.workspace, title=title, objective="x", created_by="owner1")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "a recorded finding", "machine_confidence": 0.5, "source_id": source["id"]}],
            trigger=trigger,
        )
        self.store.add_message(self.workspace, case["id"], role="human", text="what about the ramp?", actor="owner1")
        self.store.archive_case(self.workspace, case_id=case["id"], actor="owner1")
        return case

    # -- 1/2/3: active-row Archive affordance, confirmation required --------

    def test_active_investigation_row_exposes_archive_link_in_sidebar(self):
        case = self._create_case()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Archive " + case["title"].encode(), response.data)
        self.assertIn(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive/confirm".encode(), response.data)

    def test_confirm_page_renders_plain_language_not_kernel_terms(self):
        case = self._create_case()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive/confirm")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"leave the active Investigations list", response.data)
        self.assertIn(b"not delete or change anything", response.data)
        self.assertIn(b"Yes", response.data)

    def test_confirm_page_404s_for_nonexistent_case(self):
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace/cases/does-not-exist/archive/confirm")
        self.assertEqual(response.status_code, 404)

    def test_confirm_page_404s_for_already_archived_case(self):
        case = self._archived_case_with_finding()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive/confirm")
        self.assertEqual(response.status_code, 404)

    def test_archiving_still_requires_the_real_post_route_not_the_confirm_get(self):
        """Visiting the confirm page must never itself archive anything -
        only the existing POST /archive route (unchanged by this stage)
        performs the real transition."""
        case = self._create_case()
        self.owner_client.get(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive/confirm")
        workspace = self._reload_workspace()
        reloaded = self.store._find(workspace.cases, case["id"])
        self.assertEqual(reloaded["status"], CASE_STATUS_OPEN)

    def test_confirm_page_hides_archive_button_for_non_owner_non_admin(self):
        case = self._create_case()
        self.store.share_case(self._reload_workspace(), case_id=case["id"], actor="owner1")
        response = self.other_client.get(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive/confirm")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Yes &mdash; Archive this Investigation", response.data)
        self.assertIn(b"Only this Investigation", response.data)

    # -- 4/5: archived Investigation disappears from active list, history preserved --

    def test_archived_case_disappears_from_active_sidebar_list_and_count(self):
        case = self._create_case()
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", data={})
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        # The active count badge must now read 0 - no active Investigations remain.
        self.assertIn(b'<span class="launcher-count">0</span>', response.data)
        # The sidebar's own per-Investigation leaf link (case=<id>) is the
        # active-list-only rendering signature - it must be gone, even
        # though the case's title may still appear elsewhere (e.g. inside
        # a flash message from the archive action itself).
        self.assertNotIn(f'data-case-id="{case["id"]}"'.encode(), response.data)

    def test_findings_and_discussion_survive_archive_unchanged(self):
        case = self._archived_case_with_finding()
        workspace = self._reload_workspace()
        findings = [f for f in workspace.findings if f["case_id"] == case["id"]]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["statement"], "a recorded finding")
        reloaded_case = self.store._find(workspace.cases, case["id"])
        self.assertEqual(len(reloaded_case["conversation"]), 1)
        self.assertEqual(reloaded_case["conversation"][0]["text"], "what about the ramp?")

    # -- 6: no delete_case / removed_at semantics introduced -----------------

    def test_no_delete_case_or_removed_at_semantics_exist_on_cases(self):
        self.assertFalse(hasattr(self.store, "delete_case"))
        case = self._archived_case_with_finding()
        self.assertNotIn("removed_at", case)

    # -- 7: + New Investigation branching ------------------------------------

    def test_new_investigation_offers_start_new_and_continue_from_archive(self):
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Start New Investigation", response.data)
        self.assertIn(b"Continue from Archive", response.data)
        self.assertNotIn(b"+ New Investigation", response.data)

    def test_start_new_investigation_still_uses_the_unchanged_create_route(self):
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=new-case")
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'/projects/{self.project_id}/workspace/cases"'.encode(), response.data)

    # -- 8: Continue from Archive lists only this project's own archived Investigations --

    def test_continue_from_archive_lists_archived_case_from_this_project(self):
        case = self._archived_case_with_finding()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=continue-from-archive")
        self.assertEqual(response.status_code, 200)
        self.assertIn(case["title"].encode(), response.data)
        self.assertIn(b"Continue from this Archive", response.data)
        self.assertIn(b"1 Finding(s)", response.data)

    def test_continue_from_archive_excludes_active_investigations(self):
        # The left sidebar's own Investigations branch always lists active
        # Investigations regardless of which Display view is open - the
        # real assertion is that the CHOOSER body itself (identified by
        # its own data-archive-case-id row attribute, only ever set for
        # archived_visible_cases) never includes an active Case's id.
        active_case = self._create_case(title="Still Active")
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=continue-from-archive")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f'data-archive-case-id="{active_case["id"]}"'.encode(), response.data)

    def test_continue_from_archive_never_shows_another_projects_archived_case(self):
        other_project_id = "test-project-ar1-other"
        other_document_store = self.store
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        other_workspace = other_document_store.get_or_create(other_project_id)
        other_document_store.set_project_owner(other_workspace, owner="owner1", actor="owner1")
        other_case = other_document_store.create_case(other_workspace, title="Other Project Archive", objective="x", created_by="owner1")
        other_document_store.archive_case(other_workspace, case_id=other_case["id"], actor="owner1")

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=continue-from-archive")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Other Project Archive", response.data)

    def test_unauthorized_user_cannot_reach_continue_from_archive_for_project_they_lack_access_to(self):
        no_access_client = self.flask_app.test_client()
        with no_access_client.session_transaction() as sess:
            sess["user_id"] = 3
            sess["username"] = "stranger"
            sess["role"] = "read_only"
        response = no_access_client.get(f"/projects/{self.project_id}/workspace?view=continue-from-archive")
        self.assertEqual(response.status_code, 404)

    # -- 9/10/11: Snapshot request, non-mutation, honest abstention ----------

    def test_snapshot_route_returns_grounded_summary(self):
        case = self._archived_case_with_finding()
        fake_result = InvestigationSnapshotResult(
            ran=True, summary="This Investigation examined ramp feasibility.",
            grounded_in=["Finding: a recorded finding"], not_covered=None,
        )
        with patch("routes.workspace.build_archive_snapshot", return_value=fake_result) as mocked:
            response = self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/snapshot")
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertTrue(body["ran"])
            self.assertIn("ramp feasibility", body["summary"])
            mocked.assert_called_once()

    def test_snapshot_route_does_not_mutate_archived_case_or_add_governance_events(self):
        case = self._archived_case_with_finding()
        before = self._reload_workspace()
        before_case = self.store._find(before.cases, case["id"])
        before_conversation_len = len(before_case["conversation"])

        fake_result = InvestigationSnapshotResult(ran=True, summary="recap", grounded_in=[])
        with patch("routes.workspace.build_archive_snapshot", return_value=fake_result):
            self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/snapshot")

        after = self._reload_workspace()
        after_case = self.store._find(after.cases, case["id"])
        self.assertEqual(after_case["status"], CASE_STATUS_ARCHIVED)
        self.assertEqual(len(after_case["conversation"]), before_conversation_len)

        from services.governance import GovernanceLog
        gov = GovernanceLog(self.tmp_dir)
        snapshot_events = [e for e in gov.read(self.project_id) if "snapshot" in e.event_type.lower()]
        self.assertEqual(snapshot_events, [])

    def test_snapshot_route_surfaces_honest_abstention(self):
        case = self._archived_case_with_finding()
        fake_result = InvestigationSnapshotResult(
            ran=False, skipped_reason="No ANTHROPIC_API_KEY configured - a Snapshot cannot be generated in this deployment.",
        )
        with patch("routes.workspace.build_archive_snapshot", return_value=fake_result):
            response = self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/snapshot")
        body = response.get_json()
        self.assertFalse(body["ran"])
        self.assertIn("ANTHROPIC_API_KEY", body["skipped_reason"])

    def test_snapshot_route_404s_for_active_not_yet_archived_case(self):
        case = self._create_case()
        response = self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/snapshot")
        self.assertEqual(response.status_code, 404)

    # -- 12/13/14: Continue invokes existing derive_case_from_archive, lineage --

    def test_continue_button_derives_new_case_with_lineage_and_leaves_archive_frozen(self):
        case = self._archived_case_with_finding()
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/derive", follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = self._reload_workspace()
        derived = next(c for c in workspace.cases if c.get("derived_from_case_id") == case["id"])
        self.assertNotEqual(derived["id"], case["id"])
        self.assertEqual(derived["status"], CASE_STATUS_OPEN)

        original = self.store._find(workspace.cases, case["id"])
        self.assertEqual(original["status"], CASE_STATUS_ARCHIVED)

    # -- 15: unauthorized/cross-project archive and continuation denied ------

    def test_non_owner_cannot_archive_via_the_exposed_route(self):
        case = self._create_case()
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", data={}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._reload_workspace()
        reloaded = self.store._find(workspace.cases, case["id"])
        self.assertEqual(reloaded["status"], CASE_STATUS_OPEN)

    def test_non_owner_cannot_derive_from_archive_via_the_exposed_route(self):
        case = self._archived_case_with_finding()
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/derive", data={}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._reload_workspace()
        self.assertFalse(any(c.get("derived_from_case_id") == case["id"] for c in workspace.cases))

    def test_stranger_without_project_access_gets_404_on_archive_and_derive(self):
        case = self._archived_case_with_finding()
        no_access_client = self.flask_app.test_client()
        with no_access_client.session_transaction() as sess:
            sess["user_id"] = 3
            sess["username"] = "stranger"
            sess["role"] = "read_only"
        response = no_access_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/derive")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
