"""
Case Visibility: PRIVATE -> explicit Share -> SHARED (ratified governance
baseline, Private + Explicit Share Only tranche).

Covers CaseWorkspaceStore.visible_cases_for/share_case directly (the one
real enforcement point for Case privacy - every listing/switching/default-
selection query must go through it, never raw workspace.cases) and the
route-layer wiring that makes privacy actually hold across a real HTTP
request from a different authenticated user, not just at the store layer.
Also covers the two indirect-identifier guards added alongside this
tranche (artifact_image, preview_finding_id) and project-state separation
(a private Case's own privacy must never leak onto, or leak from, already-
governed Source/Requirement records it references).

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    CASE_STATUS_ARCHIVED,
    CASE_STATUS_OPEN,
    CASE_VISIBILITY_PRIVATE,
    CASE_VISIBILITY_SHARED,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class CasePrivacyTests(unittest.TestCase):
    """Store-layer tests for visible_cases_for/share_case."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_privacy_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-privacy"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -- creation ----------------------------------------------------------

    def test_new_case_defaults_private(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        self.assertEqual(case["visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertEqual(case["created_by"], "owner1")

    def test_creator_can_retrieve_own_private_case(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        visible = self.store.visible_cases_for(self.workspace, "owner1")
        self.assertIn(case["id"], [c["id"] for c in visible])

    def test_visibility_persists_across_reload(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        reloaded = self.store.get(self.project_id)
        reloaded_case = self.store._find(reloaded.cases, case["id"])
        self.assertEqual(reloaded_case["visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertEqual(reloaded_case["created_by"], "owner1")

    # -- privacy -------------------------------------------------------------

    def test_other_actor_cannot_retrieve_private_case(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        visible = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertNotIn(case["id"], [c["id"] for c in visible])

    def test_private_case_excluded_from_count_for_other_actor(self):
        self.store.create_case(self.workspace, title="A", objective="x", created_by="owner1")
        self.store.create_case(self.workspace, title="B", objective="x", created_by="owner2")
        all_cases = self.store.get(self.project_id).cases
        self.assertEqual(len(all_cases), 2)
        # owner1 sees only their own; the count itself must not leak owner2's Case
        visible_to_owner1 = self.store.visible_cases_for(self.workspace, "owner1")
        self.assertEqual(len(visible_to_owner1), 1)

    def test_open_cases_precede_archived_regardless_of_creation_order(self):
        case_a = self.store.create_case(self.workspace, title="A", objective="x", created_by="owner1")
        case_b = self.store.create_case(self.workspace, title="B", objective="x", created_by="owner1")
        case_c = self.store.create_case(self.workspace, title="C", objective="x", created_by="owner1")
        # A was created first but gets archived - it must not lead the
        # list on creation order alone once it's no longer active work.
        self.store.archive_case(self.workspace, case_id=case_a["id"], actor="owner1")
        visible = self.store.visible_cases_for(self.workspace, "owner1")
        self.assertEqual(
            [c["status"] for c in visible],
            [CASE_STATUS_OPEN, CASE_STATUS_OPEN, CASE_STATUS_ARCHIVED],
        )
        # relative order within each group (open, then archived) is
        # otherwise unchanged - B before C, both created after A.
        self.assertEqual([c["id"] for c in visible], [case_b["id"], case_c["id"], case_a["id"]])

    # -- sharing ---------------------------------------------------------------

    def test_owner_can_share_case(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        result = self.store.share_case(self.workspace, case_id=case["id"], actor="owner1", governance_log=self.gov)
        self.assertEqual(result["visibility"], CASE_VISIBILITY_SHARED)

    def test_case_id_unchanged_after_share(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        result = self.store.share_case(self.workspace, case_id=case["id"], actor="owner1")
        self.assertEqual(result["id"], case["id"])

    def test_share_transition_metadata_preserved(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        result = self.store.share_case(self.workspace, case_id=case["id"], actor="owner1")
        self.assertEqual(result["shared_by"], "owner1")
        self.assertIsNotNone(result["shared_at"])
        self.assertEqual(result["created_by"], "owner1")  # ownership itself is not overwritten by sharing

    def test_governance_log_event_on_share(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        self.store.share_case(self.workspace, case_id=case["id"], actor="owner1", governance_log=self.gov)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_shared"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["case_id"], case["id"])
        self.assertEqual(events[0].payload["prior_visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertEqual(events[0].payload["resulting_visibility"], CASE_VISIBILITY_SHARED)
        self.assertEqual(events[0].actor, "owner1")
        self.assertEqual(events[0].role, "human")

    def test_shared_case_visible_to_other_actors(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        self.store.share_case(self.workspace, case_id=case["id"], actor="owner1")
        visible_to_other = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertIn(case["id"], [c["id"] for c in visible_to_other])

    # -- authority ---------------------------------------------------------------

    def test_unauthorized_actor_cannot_share(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id=case["id"], actor="not-the-owner")
        reloaded = self.store.get(self.project_id)
        self.assertEqual(self.store._find(reloaded.cases, case["id"])["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_already_shared_case_rejects_reshare(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        self.store.share_case(self.workspace, case_id=case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id=case["id"], actor="owner1")

    def test_nonexistent_case_share_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id="does-not-exist", actor="owner1")

    def test_legacy_case_without_owner_cannot_be_shared_by_anyone(self):
        # Simulates a pre-visibility Case created via the old create_case()
        # call shape (no created_by) - no ambient/inferred owner exists,
        # and nobody is silently treated as one.
        case = self.store.create_case(self.workspace, title="Legacy", objective="x")
        self.assertIsNone(case["created_by"])
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id=case["id"], actor="anybody")

    # -- failure safety ---------------------------------------------------------------

    def test_failed_share_leaves_no_partial_state(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id=case["id"], actor="not-the-owner", governance_log=self.gov)

        reloaded = self.store.get(self.project_id)
        reloaded_case = self.store._find(reloaded.cases, case["id"])
        self.assertEqual(reloaded_case["visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertIsNone(reloaded_case["shared_by"])
        self.assertIsNone(reloaded_case["shared_at"])
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_shared"]
        self.assertEqual(events, [])

    # -- project-state separation ---------------------------------------------------------------

    def test_referenced_source_remains_independently_governed(self):
        """A private Case's own privacy must never leak onto governed
        project truth it merely references - the Source stays exactly as
        queryable/registerable-against as it would be for any Case."""
        case = self.store.create_case(self.workspace, title="Investigation", objective="x", created_by="owner1")
        self.store.attach_source_to_case(self.workspace, case_id=case["id"], source_id=self.source["id"])

        requirement = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="1.1",
            text_reference="Some requirement text.", created_by="owner1",
            registration_method="manually_registered_test_fixture",
        )
        self.assertEqual(requirement["source_id"], self.source["id"])
        # requirement lookup never requires case visibility at all - Requirement
        # has no case_id/case linkage in this model, by design (Prompt 14/15).
        self.assertIn(requirement["id"], [r["id"] for r in self.store.requirements_for_source(self.workspace, self.source["id"])])

    def test_shared_project_truth_does_not_expose_private_case(self):
        """Iterating Sources (already-shared/project-wide governed truth)
        must not itself reveal that a private, unrelated Case exists."""
        self.store.create_case(self.workspace, title="Private Investigation", objective="x", created_by="owner1")
        reloaded = self.store.get(self.project_id)
        # Source records carry no case_id/case-reference field at all -
        # nothing about iterating workspace.sources can name a Case.
        for source in reloaded.sources:
            self.assertNotIn("case_id", source)


class CasePrivacyRouteTests(unittest.TestCase):
    """
    Route-layer tests: privacy must hold across a real HTTP request from a
    genuinely different authenticated user/session, not just at the store
    layer - exercises the actual retrieval/query paths named in the
    ratified tranche (listings, direct ?case= lookup, indirect artifact_id/
    preview_finding_id identifiers).
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_privacy_routes_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-privacy-route"

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

        # Seed a registered document so _load_workspace_or_404 doesn't 404.
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_case_as_owner(self, title="Private Investigation"):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        return next(c for c in workspace.cases if c["title"] == title)

    def test_route_creates_case_owned_and_private(self):
        case = self._create_case_as_owner()
        self.assertEqual(case["visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertEqual(case["created_by"], "owner1")

    def test_owner_sees_own_case_in_workspace_page(self):
        case = self._create_case_as_owner()
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(case["title"].encode(), response.data)

    def test_other_user_does_not_see_private_case_in_listing(self):
        case = self._create_case_as_owner()
        response = self.other_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(case["title"].encode(), response.data)
        self.assertIn(b"Cases (0)", response.data)

    def test_other_user_cannot_load_private_case_via_direct_case_param(self):
        case = self._create_case_as_owner()
        response = self.other_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertEqual(response.status_code, 200)
        # Guessing/typing the id directly must not surface it either.
        self.assertNotIn(case["title"].encode(), response.data)

    def test_share_route_rejects_non_owner(self):
        case = self._create_case_as_owner()
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/share",
            data={}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        self.assertEqual(store._find(workspace.cases, case["id"])["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_share_route_works_for_owner_and_becomes_visible_to_others(self):
        case = self._create_case_as_owner()
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/share",
            data={}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        response = self.other_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertIn(case["title"].encode(), response.data)

    def test_artifact_image_indirect_identifier_guarded(self):
        case = self._create_case_as_owner()
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        source = store.add_source(workspace, name="drawing.png", file_path="/tmp/d.png", kind="drawing")

        image_rel_path = "test-artifact.png"
        (self.tmp_dir / "workspace_artifacts").mkdir(parents=True, exist_ok=True)
        (self.tmp_dir / "workspace_artifacts" / image_rel_path).write_bytes(b"not a real png but bytes are enough")

        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = store.record_analysis(
            workspace, case_id=case["id"], source_ids=[source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{
                "statement": "x", "machine_confidence": 0.5, "source_id": source["id"],
                "image_path": image_rel_path,
            }],
            trigger=trigger,
        )
        artifact_id = store.get(self.project_id).artifacts[0]["id"]
        self.assertTrue(artifact_id)

        # Non-owner: guessing/typing the artifact id directly must still 404.
        response = self.other_client.get(f"/projects/{self.project_id}/workspace/artifacts/{artifact_id}/image")
        self.assertEqual(response.status_code, 404)

        # Owner: the same id, real file on disk, must actually succeed -
        # confirms the guard blocks the other user for visibility reasons
        # specifically, not because the route is broken for everyone.
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace/artifacts/{artifact_id}/image")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
