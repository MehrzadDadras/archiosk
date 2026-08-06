"""
CLAUDE-MM6 (Cross-Document and Cross-Modal Relationship River) tests:
CaseWorkspaceStore.record_evidence_relationship/resolve_relationship_status/
dispute_relationship/reject_relationship/supersede_relationship/
build_relationship_sachet/explain_evidence_trust - the safe, endpoint-
validated relationship layer built on top of the pre-existing Relationship/
Supersession primitives (Batch H/Prompt 8, reused unchanged).

No external library involved (pure store-layer logic over already-governed
MM1-MM5 evidence-contract objects), so this file needs no real-file
fixtures the way test_mm4/test_mm5 do - real PNG/PDF bytes are built once
via Pillow purely to have real Source/StructuralUnit/AddressableRegion/
EvidenceItem records to link, mirroring the established hermetic pattern.

Run via:

    python -m unittest tests.test_mm6_relationship_river -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.case_workspace import (
    AnalysisTrigger,
    ANALYSIS_TRIGGER_USER_INITIATED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ConcurrentModificationError,
    EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
    EVIDENCE_CLASS_DIRECT_SOURCE,
    KNOWN_RELATIONSHIP_TYPES,
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_DERIVED_OBSERVATION,
    OBJECT_KIND_EVIDENCE_ITEM,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_TASK,
    OBSERVATION_AUTHOR_HUMAN,
    RELATIONSHIP_STATUS_BROKEN,
    RELATIONSHIP_STATUS_CONFIRMED,
    RELATIONSHIP_STATUS_DISPUTED,
    RELATIONSHIP_STATUS_PROPOSED,
    RELATIONSHIP_STATUS_REJECTED,
    RELATIONSHIP_STATUS_STALE,
    RELATIONSHIP_STATUS_SUPERSEDED,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_SUPPORTS,
    TASK_STATUS_OPEN,
)
from services.governance import GovernanceLog


def _build_png(width: int = 60, height: int = 40, color=(20, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


class RelationshipRiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm6_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm6"
        self.workspace = self.store.get_or_create(self.project_id)

        # Two real drawing sources with real registered sheets/regions/
        # evidence, so relationship endpoints are real MM1-MM4 records,
        # not placeholder ids.
        self.source_a = self.store.add_drawing_source(
            self.workspace, name="architectural.png", file_path=str(self.tmp_dir / "a.png"), width=100, height=80,
        )
        (self.tmp_dir / "a.png").write_bytes(_build_png(100, 80))
        reg_a = self.store.register_drawing_sheet_structure(
            self.workspace, self.source_a["id"],
            [{"index": 0, "label": "Sheet 1", "width": 100, "height": 80, "source_rotation": 0, "metadata": {}}],
            actor="tester",
        )
        self.unit_a = reg_a["structural_unit_ids"][0]
        self.region_a = self.store.create_addressable_drawing_region(
            self.workspace, self.unit_a, x=0.1, y=0.1, width=0.2, height=0.2, actor="tester",
        )
        self.evidence_a = self.store.register_evidence_item(
            self.workspace, source_id=self.source_a["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="Architectural region content", content_type="drawing_region", region_id=self.region_a["id"],
            actor="tester",
        )

        self.source_b = self.store.add_drawing_source(
            self.workspace, name="structural.png", file_path=str(self.tmp_dir / "b.png"), width=100, height=80,
        )
        (self.tmp_dir / "b.png").write_bytes(_build_png(100, 80, (160, 40, 40)))
        reg_b = self.store.register_drawing_sheet_structure(
            self.workspace, self.source_b["id"],
            [{"index": 0, "label": "Sheet 1", "width": 100, "height": 80, "source_rotation": 0, "metadata": {}}],
            actor="tester",
        )
        self.unit_b = reg_b["structural_unit_ids"][0]
        self.region_b = self.store.create_addressable_drawing_region(
            self.workspace, self.unit_b, x=0.3, y=0.3, width=0.2, height=0.2, actor="tester",
        )
        self.evidence_b = self.store.register_evidence_item(
            self.workspace, source_id=self.source_b["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="Structural region content", content_type="drawing_region", region_id=self.region_b["id"],
            actor="tester",
        )

        self.other_workspace = self.store.get_or_create("test-project-mm6-other")
        self.other_source = self.store.add_drawing_source(
            self.other_workspace, name="other.png", file_path=str(self.tmp_dir / "other.png"), width=10, height=10,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_finding(self, statement="A cross-modal Finding", case_title="MM6 test case"):
        case = self.store.create_case(self.workspace, title=case_title, objective="test", created_by="tester")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        result = self.store.record_analysis(
            self.workspace, source_ids=[self.source_a["id"]], objective="test analysis",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": statement, "machine_confidence": 0.8}],
            trigger=trigger, case_id=case["id"],
        )
        return result["finding_ids"][0]

    # -- relationship identity/direction/vocabulary -----------------------

    def test_relationship_identity_and_direction(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, reason="A supports B", created_by="tester",
        )
        self.assertTrue(rel["id"])
        self.assertEqual(rel["from_id"], self.evidence_a["id"])
        self.assertEqual(rel["to_id"], self.evidence_b["id"])
        self.assertEqual(rel["reason"], "A supports B")

        from_side = self.store.relationships_for(self.workspace, OBJECT_KIND_EVIDENCE_ITEM, self.evidence_a["id"], direction="from")
        to_side = self.store.relationships_for(self.workspace, OBJECT_KIND_EVIDENCE_ITEM, self.evidence_b["id"], direction="to")
        self.assertEqual([r["id"] for r in from_side], [rel["id"]])
        self.assertEqual([r["id"] for r in to_side], [rel["id"]])
        # Querying B's own "from" side (B is never the FROM here) finds nothing.
        self.assertEqual(self.store.relationships_for(self.workspace, OBJECT_KIND_EVIDENCE_ITEM, self.evidence_b["id"], direction="from"), [])

    def test_new_relationship_types_are_known(self):
        for rt in ("observes", "deviates_from", "requires_follow_up"):
            self.assertIn(rt, KNOWN_RELATIONSHIP_TYPES)

    def test_task_object_kind_supported_as_endpoint(self):
        task = self.store.create_task(
            self.workspace,
            source_anchor={
                "scope": "guidance",
                "guidance_key": "project-conversation-intro",
                "quote": "Follow up on crack",
                "start_offset": 0,
                "end_offset": 5,
            },
            title="Follow up on crack",
            actor="tester",
        )
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_TASK, to_id=task["id"], relationship_type="requires_follow_up",
            reason="Needs follow-up", created_by="tester",
        )
        self.assertEqual(rel["to_type"], OBJECT_KIND_TASK)

    # -- endpoint validation / falsification -------------------------------

    def test_falsification_nonexistent_from_endpoint_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_evidence_relationship(
                self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id="does-not-exist",
                to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
                relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
            )

    def test_falsification_nonexistent_to_endpoint_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_evidence_relationship(
                self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
                to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id="does-not-exist",
                relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
            )

    def test_falsification_cross_project_endpoint_rejected(self):
        """The real, guarded method rejects an endpoint id that exists but
        belongs to ANOTHER project - proves the project_id check is
        load-bearing, not merely that a nonexistent id is rejected."""
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_evidence_relationship(
                self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
                to_type=OBJECT_KIND_SOURCE, to_id=self.other_source["id"],
                relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
            )

    def test_falsification_unsupported_endpoint_type_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_evidence_relationship(
                self.workspace, from_type="requirement", from_id="anything",
                to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_a["id"],
                relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
            )

    def test_falsification_unguarded_primitive_would_have_allowed_it(self):
        """Proves the guard in record_evidence_relationship is genuinely
        load-bearing: the SAME nonexistent endpoint, passed to the
        pre-existing unguarded record_relationship, succeeds - the
        opposite of the guarded method's own refusal above."""
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id="does-not-exist",
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.assertTrue(rel["id"])  # succeeded despite the broken endpoint

    # -- status resolution: proposed/confirmed/broken/stale ----------------

    def test_status_proposed_by_default(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_PROPOSED)
        self.assertTrue(status["from"]["resolved"])
        self.assertTrue(status["to"]["resolved"])

    def test_status_confirmed_after_confirm_relationship(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.store.confirm_relationship(self.workspace, rel["id"], actor="tester")
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_CONFIRMED)

    def test_status_unresolved_for_unknown_relationship(self):
        status = self.store.resolve_relationship_status(self.workspace, "not-a-real-id")
        self.assertEqual(status["status"], "unresolved")

    def test_status_broken_when_endpoint_no_longer_resolves(self):
        """A relationship recorded via the UNGUARDED primitive against a
        nonexistent endpoint (matching a real-world case: the endpoint
        object type this store cannot yet existence-check, or a future
        deletion path) resolves as broken, not confirmed/proposed."""
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id="ghost-evidence-id",
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_BROKEN)
        self.assertFalse(status["to"]["resolved"])

    def test_status_stale_when_endpoint_source_superseded(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_ADDRESSABLE_REGION, from_id=self.region_a["id"],
            to_type=OBJECT_KIND_ADDRESSABLE_REGION, to_id=self.region_b["id"],
            relationship_type="compares_with", created_by="tester",
        )
        self.store.register_source_revision(
            self.workspace, old_source_id=self.source_a["id"], name="architectural-r2.png",
            file_path=str(self.tmp_dir / "a-r2.png"), width=100, height=80, actor="tester",
        )
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_STALE)
        self.assertTrue(status["from"]["stale"])

    # -- dispute / reject / correction history -----------------------------

    def test_dispute_relationship(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.store.dispute_relationship(self.workspace, rel["id"], actor="reviewer", reason="Not convinced")
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_DISPUTED)
        # The record itself is preserved, not deleted (Section 15).
        still_there = self.store._find(self.workspace.relationships, rel["id"])
        self.assertIsNotNone(still_there)

    def test_reject_relationship(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.store.reject_relationship(self.workspace, rel["id"], actor="reviewer", reason="Wrong link entirely")
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_REJECTED)

    def test_dispute_and_reject_are_falsification_proof_against_silent_confirmation(self):
        """A disputed/rejected relationship must NEVER resolve as
        confirmed even if it was separately confirmed first - human
        rejection always wins (Section 6's own precedence)."""
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.store.confirm_relationship(self.workspace, rel["id"], actor="tester")
        self.store.reject_relationship(self.workspace, rel["id"], actor="reviewer", reason="Actually wrong")
        status = self.store.resolve_relationship_status(self.workspace, rel["id"])
        self.assertEqual(status["status"], RELATIONSHIP_STATUS_REJECTED)
        self.assertNotEqual(status["status"], RELATIONSHIP_STATUS_CONFIRMED)

    def test_supersede_relationship_preserves_original_and_history(self):
        original = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="tester",
        )
        result = self.store.supersede_relationship(
            self.workspace, original["id"], to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, reason="Corrected: these actually agree", actor="reviewer",
        )
        new_rel = result["new_relationship"]
        self.assertNotEqual(new_rel["id"], original["id"])

        # Original preserved, unmutated in its own core fields.
        original_still = self.store._find(self.workspace.relationships, original["id"])
        self.assertEqual(original_still["relationship_type"], RELATIONSHIP_TYPE_CONTRADICTS)

        old_status = self.store.resolve_relationship_status(self.workspace, original["id"])
        self.assertEqual(old_status["status"], RELATIONSHIP_STATUS_SUPERSEDED)
        self.assertEqual(old_status["superseded_by_relationship_id"], new_rel["id"])

        history = self.store.supersessions_for(self.workspace, "relationship", original["id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["reason"], "Corrected: these actually agree")
        self.assertEqual(history[0]["actor"], "reviewer")

    def test_falsification_supersede_unknown_relationship_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.supersede_relationship(
                self.workspace, "not-a-real-id", to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
                relationship_type=RELATIONSHIP_TYPE_SUPPORTS, reason="x", actor="reviewer",
            )

    # -- contradiction / Trustworthy Answer Contract ------------------------

    def test_explain_evidence_trust_directly_verified(self):
        explanation = self.store.explain_evidence_trust(self.workspace, self.evidence_a["id"])
        self.assertEqual(explanation["status"], "assembled")
        self.assertEqual(explanation["basis"], "directly_verified_evidence")
        self.assertIsNotNone(explanation["citation"])
        self.assertFalse(explanation["has_contradictions"])

    def test_explain_evidence_trust_ai_generated_proposal_requires_authority(self):
        ai_evidence = self.store.register_evidence_item(
            self.workspace, source_id=self.source_a["id"], evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
            content="AI proposed reading", content_type="text", actor="system",
        )
        explanation = self.store.explain_evidence_trust(self.workspace, ai_evidence["id"])
        self.assertEqual(explanation["basis"], "ai_generated_proposal")
        self.assertEqual(explanation["authority_boundary"], "requires_human_authority")

    def test_explain_evidence_trust_surfaces_contradiction_as_first_class(self):
        self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, reason="These disagree", created_by="tester",
        )
        explanation = self.store.explain_evidence_trust(self.workspace, self.evidence_a["id"])
        self.assertTrue(explanation["has_contradictions"])
        self.assertEqual(len(explanation["contradicting_relationships"]), 1)
        self.assertEqual(explanation["contradicting_relationships"][0]["relationship_type"], RELATIONSHIP_TYPE_CONTRADICTS)

    def test_explain_evidence_trust_never_hides_a_contradiction_behind_support(self):
        """Falsification: even with a SUPPORTS edge also present, the
        CONTRADICTS edge must still surface - proves contradiction is not
        silently dropped or overridden by co-existing support."""
        self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="tester",
        )
        other_evidence = self.store.register_evidence_item(
            self.workspace, source_id=self.source_a["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="A third, supporting piece of evidence", content_type="text", actor="tester",
        )
        self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=other_evidence["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        explanation = self.store.explain_evidence_trust(self.workspace, self.evidence_a["id"])
        self.assertEqual(len(explanation["contradicting_relationships"]), 1)
        self.assertEqual(len(explanation["supporting_relationships"]), 1)

    def test_evidence_to_observation_to_finding_chain_visible_in_trust_explanation(self):
        observation = self.store.record_derived_observation(
            self.workspace, statement="Grid lines appear misaligned between drawings",
            author_type=OBSERVATION_AUTHOR_HUMAN, author="tester", method="visual_inspection",
            supporting_evidence_ids=[self.evidence_a["id"]], actor="tester",
        )
        self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_DERIVED_OBSERVATION, to_id=observation["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        finding_id = self._make_finding()
        self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_FINDING, to_id=finding_id,
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        explanation = self.store.explain_evidence_trust(self.workspace, self.evidence_a["id"])
        self.assertIn(observation["id"], explanation["derived_observation_ids"])
        self.assertIn(finding_id, explanation["finding_ids"])

    # -- Governed Evidence Sachet (relationship path) -----------------------

    def test_build_relationship_sachet_assembles_both_endpoints(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_ADDRESSABLE_REGION, from_id=self.region_a["id"],
            to_type=OBJECT_KIND_ADDRESSABLE_REGION, to_id=self.region_b["id"],
            relationship_type="compares_with", reason="Compare grids", created_by="tester",
        )
        sachet = self.store.build_relationship_sachet(self.workspace, rel["id"], task_description="Check grid alignment")
        self.assertEqual(sachet["status"], "assembled")
        self.assertEqual(sachet["task"], "Check grid alignment")
        self.assertIn("citation", sachet["from"])
        self.assertIn("citation", sachet["to"])
        self.assertIn("excluded", sachet)

    def test_build_relationship_sachet_unavailable_for_unknown_relationship(self):
        sachet = self.store.build_relationship_sachet(self.workspace, "not-a-real-id")
        self.assertEqual(sachet["status"], "unavailable")

    # -- concurrency / persistence / backward compatibility -----------------

    def test_concurrent_mutation_protection(self):
        copy_one = self.store.get(self.project_id)
        copy_two = self.store.get(self.project_id)
        self.store.record_evidence_relationship(
            copy_one, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        with self.assertRaises(ConcurrentModificationError):
            self.store.record_evidence_relationship(
                copy_two, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
                to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
                relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="tester",
            )

    def test_relationship_persists_across_reload(self):
        rel = self.store.record_evidence_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=self.evidence_a["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=self.evidence_b["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, reason="Persist me", created_by="tester",
        )
        reloaded = self.store.get(self.project_id)
        found = self.store._find(reloaded.relationships, rel["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["reason"], "Persist me")

    def test_backward_compatible_with_pre_mm6_relationship_creation(self):
        """The original, unguarded record_relationship (used by dozens of
        pre-MM6 tests/fixtures) still works exactly as before - no
        required new arguments, no behavior change for existing callers."""
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=self.source_a["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=self.source_b["id"], relationship_type="same_subject_as",
        )
        self.assertTrue(rel["id"])
        self.assertIsNone(rel.get("reason"))
        self.assertIsNone(rel.get("validation_state"))

    def test_backward_compatible_citation_resolution_unaffected(self):
        """Citation resolution for MM4's own regions is completely
        unaffected by anything MM6 added."""
        citation = self.store.resolve_region_citation(self.workspace, self.region_a["id"])
        self.assertEqual(citation["status"], "resolved")
        self.assertIn("region 1", citation["label"])


if __name__ == "__main__":
    unittest.main()
