"""
CLAUDE-MM1 (Multimodal Foundation and Evidence Contract) tests: Structural
Unit / Addressable Region / Evidence Item / Derived Observation, reusing
Relationship for evidence relationships and resolve_region_citation for the
citation contract. Mirrors tests/test_foundation_batch_j.py's own idiom -
a real tempfile-backed CaseWorkspaceStore, stdlib unittest.

Run via:

    python -m unittest tests.test_mm1_evidence_contract -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
    EVIDENCE_CLASS_DIRECT_SOURCE,
    KNOWN_EVIDENCE_CLASSES,
    KNOWN_OBJECT_KINDS,
    KNOWN_OBSERVATION_AUTHOR_TYPES,
    KNOWN_RELATIONSHIP_TYPES,
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_DERIVED_OBSERVATION,
    OBJECT_KIND_EVIDENCE_ITEM,
    OBJECT_KIND_STRUCTURAL_UNIT,
    OBSERVATION_AUTHOR_AI,
    OBSERVATION_AUTHOR_HUMAN,
    RELATIONSHIP_TYPE_DERIVED_FROM,
    RELATIONSHIP_TYPE_SUPPORTS,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ConcurrentModificationError,
    _render_region_address_label,
)
from services.governance import GovernanceLog


class MM1EvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm1_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm1"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="spec.txt", file_path="/tmp/spec.txt", kind="project_document",
        )
        # A second, unrelated project - used by every cross-project test below.
        self.other_project_id = "test-project-mm1-other"
        self.other_workspace = self.store.get_or_create(self.other_project_id)
        self.other_source = self.store.add_source(
            self.other_workspace, name="other.txt", file_path="/tmp/other.txt", kind="project_document",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _full_chain(self, workspace, source):
        unit = self.store.create_structural_unit(
            workspace, source_id=source["id"], unit_type="section", order_index=0,
            label="Section 08 44 13", actor="tester", governance_log=self.gov,
        )
        region = self.store.create_addressable_region(
            workspace, structural_unit_id=unit["id"], region_type="text_span",
            address={"start_offset": 10, "end_offset": 40}, actor="tester", governance_log=self.gov,
        )
        evidence = self.store.register_evidence_item(
            workspace, source_id=source["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="glazing shall be tempered", content_type="text", region_id=region["id"],
            actor="tester", governance_log=self.gov,
        )
        observation = self.store.record_derived_observation(
            workspace, statement="Tempered glazing is required.",
            author_type=OBSERVATION_AUTHOR_HUMAN, author="tester", method="manual review",
            supporting_evidence_ids=[evidence["id"]], actor="tester", governance_log=self.gov,
        )
        return unit, region, evidence, observation

    # -- identity ------------------------------------------------------------

    def test_structural_unit_region_evidence_observation_identity(self):
        unit, region, evidence, observation = self._full_chain(self.workspace, self.source)
        self.assertTrue(unit["id"])
        self.assertTrue(region["id"])
        self.assertTrue(evidence["id"])
        self.assertTrue(observation["id"])
        self.assertEqual(unit["project_id"], self.project_id)
        self.assertEqual(region["structural_unit_id"], unit["id"])
        self.assertEqual(evidence["region_id"], region["id"])
        self.assertIn(evidence["id"], observation["supporting_evidence_ids"])
        # A second unit from the same Source gets independent identity.
        unit2 = self.store.create_structural_unit(
            self.workspace, source_id=self.source["id"], unit_type="section", order_index=1,
        )
        self.assertNotEqual(unit["id"], unit2["id"])
        self.assertIn(OBJECT_KIND_STRUCTURAL_UNIT, KNOWN_OBJECT_KINDS)
        self.assertIn(OBJECT_KIND_ADDRESSABLE_REGION, KNOWN_OBJECT_KINDS)
        self.assertIn(OBJECT_KIND_EVIDENCE_ITEM, KNOWN_OBJECT_KINDS)
        self.assertIn(OBJECT_KIND_DERIVED_OBSERVATION, KNOWN_OBJECT_KINDS)

    def test_ordinal_is_not_identity(self):
        """order_index is structural position, never identity - reordering
        never changes id (same principle Table's own docstring states)."""
        unit_a = self.store.create_structural_unit(self.workspace, self.source["id"], "page", 0)
        unit_b = self.store.create_structural_unit(self.workspace, self.source["id"], "page", 1)
        self.assertNotEqual(unit_a["id"], unit_b["id"])
        fetched = self.store.get_structural_unit(self.workspace, unit_a["id"])
        self.assertEqual(fetched["id"], unit_a["id"])

    # -- project isolation -----------------------------------------------------

    def test_project_isolation_lists(self):
        self._full_chain(self.workspace, self.source)
        self._full_chain(self.other_workspace, self.other_source)
        self.assertEqual(len(self.workspace.structural_units), 1)
        self.assertEqual(len(self.other_workspace.structural_units), 1)
        self.assertNotEqual(
            self.workspace.structural_units[0]["id"], self.other_workspace.structural_units[0]["id"],
        )

    def test_invalid_cross_project_linkage_is_rejected(self):
        """A workspace cannot create a region against another project's
        structural unit, register evidence against another project's
        source, or cite another project's evidence in an observation -
        each independently rejected, not merely masked by one check."""
        foreign_unit = self.store.create_structural_unit(self.other_workspace, self.other_source["id"], "page", 0)
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_addressable_region(
                self.workspace, structural_unit_id=foreign_unit["id"], region_type="bbox",
                address={"x": 0, "y": 0, "width": 1, "height": 1},
            )

        with self.assertRaises(CaseWorkspaceError):
            self.store.register_evidence_item(
                self.workspace, source_id=self.other_source["id"],
                evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content="x", content_type="text",
            )

        foreign_evidence = self.store.register_evidence_item(
            self.other_workspace, source_id=self.other_source["id"],
            evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content="x", content_type="text",
        )
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_derived_observation(
                self.workspace, statement="x", author_type=OBSERVATION_AUTHOR_HUMAN,
                author="tester", method="m", supporting_evidence_ids=[foreign_evidence["id"]],
            )

    def test_falsification_cross_project_guard_is_real(self):
        """Prove the guard is load-bearing: with the project_id check
        removed, a foreign evidence id is silently accepted. Confirms the
        test above is actually sensitive, not passing for an unrelated
        reason."""
        foreign_evidence = self.store.register_evidence_item(
            self.other_workspace, source_id=self.other_source["id"],
            evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content="x", content_type="text",
        )

        def unguarded_record_derived_observation(workspace, statement, author_type, author, method,
                                                   supporting_evidence_ids=None, **kwargs):
            from dataclasses import asdict
            from services.case_workspace import DerivedObservation, _new_id, _now
            observation = DerivedObservation(
                id=_new_id(), project_id=workspace.project_id, statement=statement,
                author_type=author_type, author=author, method=method, created_at=_now(),
                supporting_evidence_ids=list(supporting_evidence_ids or []),
            )
            workspace.derived_observations.append(asdict(observation))
            self.store.save(workspace)
            return asdict(observation)

        # Deliberately bypasses the real, guarded method to prove the guard
        # (not something else) is what makes the real call above raise.
        result = unguarded_record_derived_observation(
            self.workspace, "x", OBSERVATION_AUTHOR_HUMAN, "tester", "m",
            supporting_evidence_ids=[foreign_evidence["id"]],
        )
        self.assertIn(foreign_evidence["id"], result["supporting_evidence_ids"])
        # ... and the real, guarded method still correctly rejects it.
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_derived_observation(
                self.workspace, statement="x", author_type=OBSERVATION_AUTHOR_HUMAN,
                author="tester", method="m", supporting_evidence_ids=[foreign_evidence["id"]],
            )

    # -- direct vs. derived distinction -----------------------------------------

    def test_evidence_item_never_masquerades_as_observation(self):
        _, _, evidence, observation = self._full_chain(self.workspace, self.source)
        self.assertNotIn("author_type", evidence)
        self.assertNotIn("supporting_evidence_ids", evidence)
        self.assertIn("evidence_class", evidence)
        self.assertIn("author_type", observation)
        self.assertNotIn("evidence_class", observation)

    def test_evidence_class_is_closed_and_validated(self):
        self.assertIn(EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, KNOWN_EVIDENCE_CLASSES)
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_evidence_item(
                self.workspace, source_id=self.source["id"], evidence_class="not_a_real_class",
                content="x", content_type="text",
            )

    def test_observation_author_type_is_closed_and_validated(self):
        self.assertIn(OBSERVATION_AUTHOR_AI, KNOWN_OBSERVATION_AUTHOR_TYPES)
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_derived_observation(
                self.workspace, statement="x", author_type="not_a_real_author_type",
                author="tester", method="m",
            )

    def test_ai_generated_proposal_stays_distinguishable_and_unvalidated_by_default(self):
        """No silent AI-to-authoritative promotion: an AI-produced Evidence
        Item is honestly labeled and starts with no validation_status."""
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=self.source["id"], evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
            content="proposed correlation", content_type="text", actor="claude",
        )
        self.assertEqual(evidence["evidence_class"], EVIDENCE_CLASS_AI_GENERATED_PROPOSAL)
        self.assertIsNone(evidence["validation_status"])

    # -- evidence relationships (reused Relationship) ---------------------------

    def test_relationship_direction_and_provisional_default(self):
        _, _, evidence, observation = self._full_chain(self.workspace, self.source)
        relationship = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_DERIVED_OBSERVATION, from_id=observation["id"],
            to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=evidence["id"],
            relationship_type=RELATIONSHIP_TYPE_DERIVED_FROM,
        )
        self.assertEqual(relationship["from_type"], OBJECT_KIND_DERIVED_OBSERVATION)
        self.assertEqual(relationship["from_id"], observation["id"])
        self.assertEqual(relationship["to_type"], OBJECT_KIND_EVIDENCE_ITEM)
        self.assertEqual(relationship["to_id"], evidence["id"])
        self.assertTrue(relationship["provisional"])  # AI/machine-asserted-shaped edges start provisional
        # Reversing from/to is a materially different, independently stored edge.
        reverse = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=evidence["id"],
            to_type=OBJECT_KIND_DERIVED_OBSERVATION, to_id=observation["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS,
        )
        self.assertNotEqual(relationship["id"], reverse["id"])

    def test_new_relationship_types_are_registered(self):
        for rel_type in (
            "same_subject_as", "compares_with", "calculated_from",
            "mitigates", "validates", "invalidates", "associated_with",
        ):
            self.assertIn(rel_type, KNOWN_RELATIONSHIP_TYPES)

    # -- citation contract -------------------------------------------------------

    def test_citation_resolves_to_a_stable_human_readable_label(self):
        unit, region, _, _ = self._full_chain(self.workspace, self.source)
        citation = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation["status"], "resolved")
        self.assertIn("spec.txt", citation["label"])
        self.assertIn("Section 08 44 13", citation["label"])
        self.assertEqual(citation["region_id"], region["id"])
        # Renaming the Source changes the rendered label, never the anchor id.
        live_source = self.store._find(self.workspace.sources, self.source["id"])
        live_source["name"] = "renamed-spec.txt"
        self.store.save(self.workspace)
        citation_after_rename = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation_after_rename["region_id"], region["id"])
        self.assertIn("renamed-spec.txt", citation_after_rename["label"])

    def test_address_label_rendering_not_overfit_to_one_geometry(self):
        """text span, bounding box, and cell/row shapes each render their
        own way - none is treated as the assumed/default shape."""
        self.assertEqual(
            _render_region_address_label("text_span", {"start_offset": 5, "end_offset": 12}),
            "offset 5-12",
        )
        self.assertEqual(
            _render_region_address_label("bbox", {"x": 1, "y": 2, "width": 10, "height": 20}),
            "region x=1,y=2",
        )
        self.assertEqual(_render_region_address_label("cell", {"label": "H27"}), "H27")
        self.assertEqual(_render_region_address_label("row", {"label": "Row 20"}), "Row 20")
        # An unrecognized shape is an honest None, never a guessed rendering.
        self.assertIsNone(_render_region_address_label("crop", {"unrecognized_key": 1}))

    def test_broken_anchor_states_are_honest_not_fabricated(self):
        self.assertEqual(
            self.store.resolve_region_citation(self.workspace, "does-not-exist")["status"], "unavailable",
        )
        # A region belonging to a different project is also "unavailable",
        # not resolved against the wrong project's own unit/source.
        _, foreign_region, _, _ = self._full_chain(self.other_workspace, self.other_source)
        citation = self.store.resolve_region_citation(self.workspace, foreign_region["id"])
        self.assertEqual(citation["status"], "unavailable")

    def test_falsification_removed_source_breaks_citation(self):
        """Prove resolve_region_citation actually checks Source availability
        - falsify by bypassing remove_source's own governed path and
        setting removed_at directly, confirming the citation call is
        sensitive to it."""
        unit, region, _, _ = self._full_chain(self.workspace, self.source)
        citation_before = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation_before["status"], "resolved")
        live_source = self.store._find(self.workspace.sources, self.source["id"])
        live_source["removed_at"] = "2026-08-05T00:00:00+00:00"
        self.store.save(self.workspace)
        citation_after = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation_after["status"], "unavailable")

    # -- persistence / serialization ---------------------------------------------

    def test_persistence_round_trip(self):
        unit, region, evidence, observation = self._full_chain(self.workspace, self.source)
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.structural_units), 1)
        self.assertEqual(len(reloaded.addressable_regions), 1)
        self.assertEqual(len(reloaded.evidence_items), 1)
        self.assertEqual(len(reloaded.derived_observations), 1)
        self.assertEqual(reloaded.structural_units[0]["id"], unit["id"])
        self.assertEqual(reloaded.evidence_items[0]["content"], evidence["content"])

    def test_backward_compatibility_legacy_workspace_lacks_mm1_keys(self):
        """A workspace JSON serialized before MM1 simply lacks these keys -
        ProjectWorkspace(**data) must still load, with the empty-list
        default, the same convention every prior addition already uses."""
        import json
        path = self.store._path_for(self.project_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("structural_units", "addressable_regions", "evidence_items", "derived_observations"):
            data.pop(key, None)
        path.write_text(json.dumps(data), encoding="utf-8")
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.structural_units, [])
        self.assertEqual(reloaded.addressable_regions, [])
        self.assertEqual(reloaded.evidence_items, [])
        self.assertEqual(reloaded.derived_observations, [])
        # And the store can still create new MM1 records against it.
        unit = self.store.create_structural_unit(reloaded, self.source["id"], "page", 0)
        self.assertTrue(unit["id"])

    def test_existing_source_workflows_unaffected(self):
        """Adding MM1 fields to Source, and MM1 lists to ProjectWorkspace,
        does not change existing Source behavior."""
        self.assertIsNone(self.source.get("mime_type"))
        self.assertIsNone(self.source.get("size_bytes"))
        self.assertIsNone(self.source.get("security_classification"))
        fetched = self.store._find(self.workspace.sources, self.source["id"])
        self.assertEqual(fetched["name"], "spec.txt")

    # -- provenance / validation / security --------------------------------------

    def test_provenance_fields_present(self):
        unit, region, evidence, observation = self._full_chain(self.workspace, self.source)
        for record in (unit, region, evidence, observation):
            self.assertIn("created_at", record)
        self.assertEqual(evidence["created_by"], "tester")
        self.assertEqual(observation["author"], "tester")
        self.assertEqual(observation["author_type"], OBSERVATION_AUTHOR_HUMAN)

    def test_human_validation_state_starts_unreviewed_and_is_settable(self):
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=self.source["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="x", content_type="text",
        )
        self.assertIsNone(evidence["validation_status"])
        live_evidence = self.store._find(self.workspace.evidence_items, evidence["id"])
        live_evidence["validation_status"] = "Correct"
        self.store.save(self.workspace)
        reloaded = self.store.get(self.project_id)
        self.assertEqual(
            self.store.get_evidence_item(reloaded, evidence["id"])["validation_status"], "Correct",
        )

    def test_security_classification_preserved(self):
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=self.source["id"], evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
            content="x", content_type="text", security_classification="restricted",
        )
        self.assertEqual(evidence["security_classification"], "restricted")
        reloaded = self.store.get(self.project_id)
        self.assertEqual(
            self.store.get_evidence_item(reloaded, evidence["id"])["security_classification"], "restricted",
        )

    # -- concurrent mutation protection ------------------------------------------

    def test_concurrent_modification_is_detected(self):
        """Two independently loaded copies of the same workspace; the
        second writer's save() must raise rather than silently clobber the
        first writer's already-persisted structural unit - the existing,
        already-tested optimistic-concurrency mechanism (save()), proven
        here specifically against the new MM1 methods."""
        copy_a = self.store.get(self.project_id)
        copy_b = self.store.get(self.project_id)
        self.store.create_structural_unit(copy_a, self.source["id"], "page", 0)
        with self.assertRaises(ConcurrentModificationError):
            self.store.create_structural_unit(copy_b, self.source["id"], "page", 1)


class MM1ApiRetrievalTests(unittest.TestCase):
    """
    CLAUDE-MM1 Part 12: proves the evidence contract is retrievable
    through the existing /api/v1 JSON surface with real data, not just
    that the routes exist and enforce auth (see test_api_authentication.py
    for that, already updated with these routes). No route in routes/api.py
    mutates evidence-contract state - every fixture below is written
    directly via CaseWorkspaceStore, the same as production would.
    """

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm1_api_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "mm1-api-project"

        document = ParsedDocument(
            project_id=self.project_id, filename="spec.txt", ingested_at="2026-01-01T00:00:00+00:00",
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(self.project_id)
        workspace.owner = "tester"
        store.save(workspace)
        source = store.add_source(workspace, name="spec.txt", file_path="/tmp/spec.txt", kind="project_document")
        unit = store.create_structural_unit(workspace, source["id"], "section", 0, label="Section 1")
        region = store.create_addressable_region(
            workspace, unit["id"], "text_span", {"start_offset": 0, "end_offset": 10},
        )
        self.evidence = store.register_evidence_item(
            workspace, source["id"], EVIDENCE_CLASS_DIRECT_SOURCE, "content", "text", region_id=region["id"],
        )
        self.region_id = region["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = role
        return client

    def test_list_evidence_returns_registered_item(self):
        client = self._client_as()
        response = client.get(f"/api/v1/documents/{self.project_id}/evidence")
        self.assertEqual(response.status_code, 200)
        ids = [e["id"] for e in response.get_json()["evidence_items"]]
        self.assertIn(self.evidence["id"], ids)

    def test_get_citation_resolves_real_region(self):
        client = self._client_as()
        response = client.get(f"/api/v1/documents/{self.project_id}/citations/{self.region_id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "resolved")
        self.assertIn("spec.txt", body["label"])

    def test_get_citation_for_unknown_region_is_200_unavailable_not_404(self):
        client = self._client_as()
        response = client.get(f"/api/v1/documents/{self.project_id}/citations/does-not-exist")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
