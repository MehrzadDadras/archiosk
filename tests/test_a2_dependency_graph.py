"""
A2 - the governed dependency graph, proven against real governed objects.

Every endpoint below is a real Requirement, Source, AddressableRegion or
StructuralUnit created through the store's own registration paths. Nothing here
uses a toy class, because the claim being tested is that the EXISTING substrate
answers the dependency question - a claim a stand-in object would not test.

The four properties that carry the weight:

  * dependency, supporting and contradicting edges do not collapse into
    each other;
  * explicit and inferred stay distinguishable, and inferred is never promoted;
  * a superseded endpoint keeps its lineage rather than vanishing;
  * a drawing endpoint participates today, so B3-B inherits a model rather
    than a rewrite.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import dependency_graph as dg
from services.case_workspace import (
    CaseWorkspaceStore,
    EVIDENCE_CLASS_DIRECT_SOURCE,
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_STRUCTURAL_UNIT,
    RELATIONSHIP_TYPE_AFFECTS,
    RELATIONSHIP_TYPE_BLOCKS,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_DEPENDS_ON,
    RELATIONSHIP_TYPE_DEPICTS,
    RELATIONSHIP_TYPE_IMPLEMENTS,
    RELATIONSHIP_TYPE_SUPPORTS,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
)
from services.governance import GovernanceLog


def _png(width=60, height=40, color=(20, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


class _A2Base(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_a2_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-a2")

        (self.tmp_dir / "spec.png").write_bytes(_png())
        self.source = self.store.add_drawing_source(
            self.workspace, name="spec.png",
            file_path=str(self.tmp_dir / "spec.png"), width=60, height=40,
        )
        self.req_smoke = self._requirement("R-1", "Smoke control shall be provided.")
        self.req_damper = self._requirement("R-2", "Dampers shall close on alarm.")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _requirement(self, identifier: str, text: str) -> dict:
        return self.store.register_requirement(
            self.workspace, source_id=self.source["id"],
            original_requirement_identifier=identifier, text_reference=text,
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov,
        )

    def _drawing_region(self):
        (self.tmp_dir / "sheet.png").write_bytes(_png(100, 80, (160, 40, 40)))
        drawing = self.store.add_drawing_source(
            self.workspace, name="sheet.png",
            file_path=str(self.tmp_dir / "sheet.png"), width=100, height=80,
        )
        reg = self.store.register_drawing_sheet_structure(
            self.workspace, drawing["id"],
            [{"index": 0, "label": "A204", "width": 100, "height": 80,
              "source_rotation": 0, "metadata": {}}],
            actor="tester",
        )
        unit_id = reg["structural_unit_ids"][0]
        region = self.store.create_addressable_drawing_region(
            self.workspace, unit_id, x=0.1, y=0.1, width=0.2, height=0.2, actor="tester",
        )
        return drawing, unit_id, region

    def _rel(self, from_type, from_id, to_type, to_id, rel_type, **kw):
        return self.store.record_relationship(
            self.workspace, from_type=from_type, from_id=from_id,
            to_type=to_type, to_id=to_id, relationship_type=rel_type, **kw)


class SemanticsTests(_A2Base):
    """The vocabulary must not collapse."""

    def test_dependency_supporting_and_contradiction_are_distinct_classes(self):
        self.assertEqual(dg.classify(RELATIONSHIP_TYPE_DEPENDS_ON), dg.CLASS_DEPENDENCY)
        self.assertEqual(dg.classify(RELATIONSHIP_TYPE_SUPPORTS), dg.CLASS_SUPPORTING)
        self.assertEqual(dg.classify(RELATIONSHIP_TYPE_CONTRADICTS), dg.CLASS_CONTRADICTION)

    def test_an_unrecognised_type_is_not_treated_as_a_dependency(self):
        """An edge nobody classified must not become a carry-through
        obligation by default."""
        self.assertEqual(dg.classify("some_future_edge"), dg.CLASS_OTHER)

    def test_forward_and_reverse_types_are_recorded_separately(self):
        self.assertEqual(dg._DIRECTION[RELATIONSHIP_TYPE_DEPENDS_ON], dg.DIRECTION_FORWARD)
        self.assertEqual(dg._DIRECTION[RELATIONSHIP_TYPE_BLOCKS], dg.DIRECTION_REVERSE)


class ExplicitDependencyTests(_A2Base):

    def test_what_depends_on_this_requirement(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False, created_by="tester")
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 1)
        self.assertEqual(result["edges"][0]["other"]["id"], self.req_damper["id"])
        self.assertEqual(result["edges"][0]["role"], "dependent")

    def test_reverse_lookup_returns_the_mirror(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        forward = dg.dependencies_of(self.store, self.workspace,
                                     OBJECT_KIND_REQUIREMENT, self.req_damper["id"])
        self.assertEqual(forward["counts"]["total"], 1)
        self.assertEqual(forward["edges"][0]["other"]["id"], self.req_smoke["id"])
        self.assertEqual(forward["edges"][0]["role"], "dependency")

    def test_the_two_questions_do_not_return_the_same_answer(self):
        """Guard against a resolver that ignores direction and returns every
        neighbour to both questions."""
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        dependents = dg.dependents_of(self.store, self.workspace,
                                      OBJECT_KIND_REQUIREMENT, self.req_damper["id"])
        self.assertEqual(dependents["counts"]["total"], 0,
                         "the dependent side must not report itself as depended-upon")

    def test_a_reverse_direction_type_inverts_correctly(self):
        """`A blocks B` means B depends on A - the opposite of depends_on."""
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  RELATIONSHIP_TYPE_BLOCKS, provisional=False)
        dependents = dg.dependents_of(self.store, self.workspace,
                                      OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual([e["other"]["id"] for e in dependents["edges"]],
                         [self.req_damper["id"]])

    def test_multiple_dependents_are_all_returned(self):
        extra = [self._requirement("R-%d" % n, "Dependent %d" % n) for n in range(3, 6)]
        for r in extra:
            self._rel(OBJECT_KIND_REQUIREMENT, r["id"],
                      OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                      RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 3)
        self.assertEqual(sorted(e["other"]["id"] for e in result["edges"]),
                         sorted(r["id"] for r in extra))


class InferredVersusExplicitTests(_A2Base):
    """GOV-P-006: a model may constrain a transition, never authorize one."""

    def test_an_inferred_dependency_is_labelled_not_promoted(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=True, confidence=0.8,
                  created_by="model")
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        edge = result["edges"][0]
        self.assertTrue(edge["inferred"])
        self.assertEqual(edge["confidence"], 0.8)
        self.assertEqual(edge["status"], "proposed")
        self.assertEqual(result["counts"], {"total": 1, "explicit": 0, "inferred": 1})

    def test_explicit_and_inferred_are_counted_separately(self):
        other = self._requirement("R-9", "Explicit dependent")
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=True)
        self._rel(OBJECT_KIND_REQUIREMENT, other["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"], {"total": 2, "explicit": 1, "inferred": 1})

    def test_inferred_edges_can_be_excluded_entirely(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=True)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                                  include_inferred=False)
        self.assertEqual(result["counts"]["total"], 0)

    def test_a_rejected_edge_is_reported_but_not_traversed_through(self):
        """Suppressing it would hide a human judgment; traversing through it
        would carry a dependency the human refused."""
        middle = self._requirement("R-M", "Middle")
        far = self._requirement("R-F", "Far side")
        rejected = self._rel(OBJECT_KIND_REQUIREMENT, middle["id"],
                             OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                             RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self.store.reject_relationship(self.workspace, rejected["id"], actor="tester")
        self._rel(OBJECT_KIND_REQUIREMENT, far["id"],
                  OBJECT_KIND_REQUIREMENT, middle["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)

        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                                  max_depth=3)
        ids = [e["other"]["id"] for e in result["edges"]]
        self.assertIn(middle["id"], ids, "the rejected edge must still be reported")
        self.assertNotIn(far["id"], ids,
                         "traversal continued through a rejected relationship")


class ContradictionAndSupportTests(_A2Base):
    """Conflicting evidence must not collapse into the dependency answer."""

    def test_a_contradiction_is_not_returned_as_a_dependency(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_CONTRADICTS, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 0)

    def test_a_contradiction_is_still_reachable_separately(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_CONTRADICTS, provisional=False)
        related = dg.related_non_dependencies(self.store, self.workspace,
                                              OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(len(related["contradicting"]), 1)
        self.assertEqual(related["supporting"], [])

    def test_dependency_and_contradiction_coexist_without_merging(self):
        supporter = self._requirement("R-S", "Supporting")
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self._rel(OBJECT_KIND_REQUIREMENT, supporter["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_CONTRADICTS, provisional=False)
        deps = dg.dependents_of(self.store, self.workspace,
                                OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        related = dg.related_non_dependencies(self.store, self.workspace,
                                              OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual([e["other"]["id"] for e in deps["edges"]], [self.req_damper["id"]])
        self.assertEqual(len(related["contradicting"]), 1)

    def test_a_supporting_edge_is_not_a_dependency(self):
        self._rel(OBJECT_KIND_SOURCE, self.source["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_SUPPORTS, provisional=False)
        deps = dg.dependents_of(self.store, self.workspace,
                                OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        related = dg.related_non_dependencies(self.store, self.workspace,
                                              OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(deps["counts"]["total"], 0)
        self.assertEqual(len(related["supporting"]), 1)


class SupersessionLineageTests(_A2Base):
    """A superseded endpoint must not silently erase lineage."""

    def test_a_superseded_requirement_keeps_its_dependency_edge(self):
        successor = self._requirement("R-2b", "Dampers shall close on alarm (rev B).")
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self.store.record_supersession(
            self.workspace, predecessor_type=OBJECT_KIND_REQUIREMENT,
            predecessor_id=self.req_damper["id"], successor_type=OBJECT_KIND_REQUIREMENT,
            successor_id=successor["id"], actor="tester", reason="Addendum 3")

        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 1,
                         "superseding an endpoint deleted its dependency edge")
        self.assertEqual(result["edges"][0]["other"]["id"], self.req_damper["id"])

    def test_supersession_is_reachable_but_is_not_a_dependency_edge(self):
        successor = self._requirement("R-2c", "Rev C")
        self.store.record_supersession(
            self.workspace, predecessor_type=OBJECT_KIND_REQUIREMENT,
            predecessor_id=self.req_damper["id"], successor_type=OBJECT_KIND_REQUIREMENT,
            successor_id=successor["id"], actor="tester")
        lineage = dg.supersession_lineage(self.store, self.workspace,
                                          OBJECT_KIND_REQUIREMENT, self.req_damper["id"])
        self.assertTrue(lineage)
        deps = dg.dependents_of(self.store, self.workspace,
                                OBJECT_KIND_REQUIREMENT, self.req_damper["id"])
        self.assertEqual(deps["counts"]["total"], 0,
                         "supersession leaked into the dependency answer")


class DrawingCompatibilityTests(_A2Base):
    """B3-B must inherit this model, not rewrite it."""

    def test_a_drawing_region_can_depend_on_a_requirement(self):
        _drawing, _unit, region = self._drawing_region()
        self._rel(OBJECT_KIND_ADDRESSABLE_REGION, region["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPICTS, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 1)
        edge = result["edges"][0]
        self.assertEqual(edge["other"]["type"], OBJECT_KIND_ADDRESSABLE_REGION)
        self.assertEqual(edge["other"]["id"], region["id"])

    def test_a_spatial_endpoint_resolves_rather_than_reading_as_broken(self):
        """The claim is structural: a drawing endpoint is a first-class
        participant today, with real endpoint status, not a placeholder."""
        _drawing, unit_id, region = self._drawing_region()
        self._rel(OBJECT_KIND_STRUCTURAL_UNIT, unit_id,
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_IMPLEMENTS, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        edge = result["edges"][0]
        self.assertNotEqual(edge["status"], "broken")
        self.assertTrue(edge["endpoint_status"]["from"]["resolved"])
        self.assertTrue(edge["endpoint_status"]["to"]["resolved"])

    def test_both_spatial_kinds_are_named_for_b3b(self):
        self.assertIn(OBJECT_KIND_ADDRESSABLE_REGION, dg.SPATIAL_ENDPOINT_KINDS)
        self.assertIn(OBJECT_KIND_STRUCTURAL_UNIT, dg.SPATIAL_ENDPOINT_KINDS)


class EndpointResolutionTests(_A2Base):
    """The one change A2 made to the substrate."""

    def test_a_requirement_endpoint_resolves(self):
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_damper["id"],
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        edge = result["edges"][0]
        self.assertEqual(edge["status"], "confirmed",
                         "a requirement endpoint still reads as broken")

    def test_a_genuinely_missing_endpoint_still_reads_broken(self):
        """Guard-the-guard: making requirements resolve must not make
        everything resolve."""
        self._rel(OBJECT_KIND_REQUIREMENT, "ghost-requirement-id",
                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                  RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["edges"][0]["status"], "broken")


class BoundedTraversalTests(_A2Base):

    def test_traversal_is_depth_limited(self):
        a = self._requirement("R-A", "A")
        b = self._requirement("R-B", "B")
        self._rel(OBJECT_KIND_REQUIREMENT, a["id"], OBJECT_KIND_REQUIREMENT,
                  self.req_smoke["id"], RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self._rel(OBJECT_KIND_REQUIREMENT, b["id"], OBJECT_KIND_REQUIREMENT,
                  a["id"], RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)

        one = dg.dependents_of(self.store, self.workspace,
                               OBJECT_KIND_REQUIREMENT, self.req_smoke["id"], max_depth=1)
        two = dg.dependents_of(self.store, self.workspace,
                               OBJECT_KIND_REQUIREMENT, self.req_smoke["id"], max_depth=2)
        self.assertEqual(one["counts"]["total"], 1)
        self.assertEqual(two["counts"]["total"], 2)
        self.assertEqual({e["depth"] for e in two["edges"]}, {1, 2})

    def test_a_cycle_terminates(self):
        a = self._requirement("R-C1", "C1")
        self._rel(OBJECT_KIND_REQUIREMENT, a["id"], OBJECT_KIND_REQUIREMENT,
                  self.req_smoke["id"], RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self._rel(OBJECT_KIND_REQUIREMENT, self.req_smoke["id"], OBJECT_KIND_REQUIREMENT,
                  a["id"], RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                                  max_depth=10)
        self.assertLessEqual(result["counts"]["total"], 4)

    def test_the_node_cap_reports_truncation_rather_than_lying(self):
        for n in range(6):
            r = self._requirement("R-T%d" % n, "T%d" % n)
            self._rel(OBJECT_KIND_REQUIREMENT, r["id"], OBJECT_KIND_REQUIREMENT,
                      self.req_smoke["id"], RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"],
                                  max_depth=2, max_nodes=3)
        self.assertTrue(result["truncated"],
                        "a capped traversal reported a complete answer")

    def test_an_affects_edge_carries_impact_in_the_right_direction(self):
        self._rel(OBJECT_KIND_SOURCE, self.source["id"], OBJECT_KIND_REQUIREMENT,
                  self.req_smoke["id"], RELATIONSHIP_TYPE_AFFECTS, provisional=False)
        dependents = dg.dependents_of(self.store, self.workspace,
                                      OBJECT_KIND_SOURCE, self.source["id"])
        self.assertEqual([e["other"]["id"] for e in dependents["edges"]],
                         [self.req_smoke["id"]])


class ProjectBoundaryTests(_A2Base):
    """D1's boundary must hold here too."""

    def test_another_projects_relationships_are_not_visible(self):
        other_ws = self.store.get_or_create("test-project-a2-other")
        (self.tmp_dir / "other.png").write_bytes(_png())
        other_source = self.store.add_drawing_source(
            other_ws, name="other.png", file_path=str(self.tmp_dir / "other.png"),
            width=60, height=40)
        other_req = self.store.register_requirement(
            other_ws, source_id=other_source["id"],
            original_requirement_identifier="X-1", text_reference="Foreign requirement",
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov)
        self.store.record_relationship(
            other_ws, from_type=OBJECT_KIND_REQUIREMENT, from_id=other_req["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.req_smoke["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)

        result = dg.dependents_of(self.store, self.workspace,
                                  OBJECT_KIND_REQUIREMENT, self.req_smoke["id"])
        self.assertEqual(result["counts"]["total"], 0,
                         "a foreign project's dependency edge was returned")

    def test_the_foreign_edge_does_exist_in_its_own_project(self):
        """Guard-the-guard: the isolation assertion above must not pass
        because nothing was created."""
        other_ws = self.store.get_or_create("test-project-a2-other2")
        (self.tmp_dir / "o2.png").write_bytes(_png())
        src = self.store.add_drawing_source(
            other_ws, name="o2.png", file_path=str(self.tmp_dir / "o2.png"),
            width=60, height=40)
        a = self.store.register_requirement(
            other_ws, source_id=src["id"], original_requirement_identifier="Y-1",
            text_reference="A", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov)
        b = self.store.register_requirement(
            other_ws, source_id=src["id"], original_requirement_identifier="Y-2",
            text_reference="B", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov)
        self.store.record_relationship(
            other_ws, from_type=OBJECT_KIND_REQUIREMENT, from_id=b["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=a["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        result = dg.dependents_of(self.store, other_ws, OBJECT_KIND_REQUIREMENT, a["id"])
        self.assertEqual(result["counts"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
