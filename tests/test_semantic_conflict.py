"""
CLAUDE-P16 - hermetic tests for the semantic-conflict tier: Golden
Corpus/mutation construction (real store calls - Requirements, real
Relationships for Case D, real Supersession for Case E), and
conversation_interpreter.py's production wiring that now gathers
Supersession neighbors AND direct Relationships for EVERY real
investigation, not just when a test supplies them. Proven with a mocked
model call. The real, billed, blind model run against this exact corpus
is tools/self_test_lab_004_semantic.py - hand-run, never invoked by the
automated suite.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.bhive_parser import ParsedDocument
from services.case_workspace import (
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_QUALIFIES,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry
from tests.self_test.golden_corpus_semantic import build_semantic_clean_baseline
from tests.self_test.mutations_semantic import (
    apply_semantic_drift,
    build_exception_resolves_conflict_project,
    build_hidden_qualification_conflict_project,
    build_jointly_impossible_project,
)


class SemanticGoldenCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_semantic_corpus_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clean_baseline_registers_six_real_requirements(self):
        project = build_semantic_clean_baseline(self.store, "proj-x", self.tmp_dir / "sources")
        self.assertEqual(len(project["workspace"].requirements), 6)

    def test_paraphrase_pair_is_genuinely_different_wording(self):
        project = build_semantic_clean_baseline(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = project["workspace"]
        record_drawings = next(r for r in workspace.requirements if r["id"] == project["record_drawings_id"])
        as_built = next(r for r in workspace.requirements if r["id"] == project["as_built_id"])
        self.assertNotEqual(record_drawings["text_reference"], as_built["text_reference"])


class CaseAJointlyImpossibleTests(unittest.TestCase):
    def test_two_requirements_registered_with_real_provenance(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_a_"))
        try:
            store = CaseWorkspaceStore(tmp_dir)
            project = build_jointly_impossible_project(store, "proj-x", tmp_dir / "sources")
            workspace = project["workspace"]
            self.assertEqual(len(workspace.sources), 2)
            operational = next(r for r in workspace.requirements if r["id"] == project["operational_id"])
            shutdown = next(r for r in workspace.requirements if r["id"] == project["shutdown_id"])
            self.assertIn("continuously operational", operational["text_reference"])
            self.assertIn("shut down automatically", shutdown["text_reference"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class CaseDRealRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_d_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project = build_exception_resolves_conflict_project(self.store, "proj-x", self.tmp_dir / "sources")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_two_real_qualifies_relationships_are_recorded(self):
        workspace = self.project["workspace"]
        exception_relationships = self.store.relationships_for(
            workspace, OBJECT_KIND_REQUIREMENT, self.project["exception_id"],
        )
        self.assertEqual(len(exception_relationships), 2)
        for rel in exception_relationships:
            self.assertEqual(rel["relationship_type"], RELATIONSHIP_TYPE_QUALIFIES)
            self.assertEqual(rel["from_id"], self.project["exception_id"])

    def test_relationships_for_finds_it_from_the_unlocked_side_too(self):
        workspace = self.project["workspace"]
        rels = self.store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, self.project["unlocked_id"])
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]["from_id"], self.project["exception_id"])


class CaseESemanticDriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_e_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project = build_semantic_clean_baseline(self.store, "proj-x", self.tmp_dir / "sources")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_drift_is_a_real_supersession_not_a_dict_edit(self):
        answer_key = apply_semantic_drift(
            self.store, self.project["workspace"], self.project["autonomy_rfp_id"],
            self.project["autonomy_schedule_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)
        original = next(r for r in workspace.requirements if r["id"] == self.project["autonomy_schedule_id"])
        drifted = next(r for r in workspace.requirements if r["id"] == answer_key.secondary_location)

        self.assertEqual(original["status"], "superseded")
        self.assertIn("maintain operation", original["text_reference"])
        self.assertEqual(drifted["status"], "active")
        self.assertIn("nominally equivalent", drifted["text_reference"])

    def test_rfp_autonomy_requirement_is_never_touched(self):
        answer_key = apply_semantic_drift(
            self.store, self.project["workspace"], self.project["autonomy_rfp_id"],
            self.project["autonomy_schedule_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)
        rfp_requirement = next(r for r in workspace.requirements if r["id"] == self.project["autonomy_rfp_id"])
        self.assertEqual(rfp_requirement["status"], "active")
        self.assertIn("maintain operation", rfp_requirement["text_reference"])
        self.assertEqual(answer_key.location, self.project["autonomy_rfp_id"])


class ProductionRelationshipWiringTests(unittest.TestCase):
    """
    CLAUDE-P16: proves conversation_interpreter.py gathers real
    Relationships and Supersession neighbors for EVERY real investigation
    automatically - the production path, not only when a lab script
    supplies related_requirements by hand.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_relationship_wiring_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-relationship-wiring"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _mock_response(self, payload: dict):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_real_qualifies_relationship_reaches_the_model_prompt(self):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        main_req = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Main",
            text_reference="Unrestricted access required.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        exception_req = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Exception",
            text_reference="Emergency override mechanism resolves the access/security tension.",
            created_by="owner1", registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.store.record_relationship(
            workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=exception_req["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=main_req["id"],
            relationship_type=RELATIONSHIP_TYPE_QUALIFIES, created_by="owner1",
        )

        case_resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Case A", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.8, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": False, "flagged_stale_ids": [],
            })
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={
                    "text": "Check this", "anchor_type": "requirement",
                    "anchor_id": main_req["id"], "anchor_description": "Main",
                },
            )
            workspace = self.store.get(self.project_id)
            system_message = workspace.project_conversation[-1]
            message_id = system_message["action_taken"].split(":", 1)[1]
            self.client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")

            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

        self.assertIn(f"[{RELATIONSHIP_TYPE_QUALIFIES}]", prompt)
        self.assertIn("Emergency override mechanism", prompt)

    def test_supersession_neighbor_reaches_the_model_prompt(self):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        original = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="R1",
            text_reference="96 hours.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        current, _ = self.store.revise_requirement(
            workspace, requirement_id=original["id"], actor="owner1", reason="Addendum", text_reference="120 hours.",
        )

        self.store.create_case(workspace, title="Case A", objective="x", created_by="owner1")
        case = self.store.get(self.project_id).cases[0]

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.8, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": False, "flagged_stale_ids": [],
            })
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={
                    "text": "Check this", "anchor_type": "requirement",
                    "anchor_id": current["id"], "anchor_description": "R1",
                },
            )
            workspace = self.store.get(self.project_id)
            system_message = workspace.project_conversation[-1]
            message_id = system_message["action_taken"].split(":", 1)[1]
            self.client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")

            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

        self.assertIn("superseded_by_this", prompt)
        self.assertIn("96 hours.", prompt)


if __name__ == "__main__":
    unittest.main()
