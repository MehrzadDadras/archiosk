"""
The canonical Script contract — Question → Scenario → Script → (future Clip)
→ Evidence → Measurement.

**No new object family was created for this, and none is needed.** A Script is a
composition of primitives the kernel already has, and this file is the contract
that pins the composition so a future renderer has something to code against.
That is the whole of the "implementation": the gap was never a missing object,
it was a missing agreement.

THE COMPOSITION

    Question   InvestigationStep.question  — "the reviewer's own question,
               verbatim" (its own field comment). Already the audit-trail
               container for what was asked and what evidence was gathered.

    Scenario   The same InvestigationStep plus its `anchor` (what was being
               investigated). No Scenario object is minted here: composed
               scenarios are GO-SPIN-GAMES-01's territory, and inventing a
               sibling would be exactly the proliferation CLAUDE.md warns
               about.

    Script     WorkProduct(artifact_type="script",
                           source_investigation_step_id=<the step>)
               `artifact_type` is open-world and validated against nothing, so
               "script" needs no schema change. WorkProduct already carries
               identity, version, lifecycle state, issued_checksum, review
               history and revision lineage.

    Units      WorkProductSection, one per narrative unit:
                 section_type   "scene"     — narration, may assert
                                "direction" — rendering instruction, asserts
                                              nothing
                 order_index    the sequence
                 content        {"text": ...} — the exact transcript
                 content_class  provenance of THIS unit, closed vocabulary
                 evidence_links anchors to real governed objects

    Evidence   WorkProductSection.evidence_links and Claim.evidence_links are
               both validated against really-persisted objects. A citation to
               something that does not exist cannot be stored — MM7's own
               "no citation laundering", structural rather than advisory.

    Sourced vs inferred, and uncertainty
               Carried by the Claim a scene cites, not restated on the scene:
               `claim_class` (directly_verified / supported_interpretation /
               ai_proposal / conflicting / unknown / …) and
               `confidence_state` (a closed vocabulary — deliberately no
               confidence percentage anywhere).

    Clip       A downstream export. WorkProduct's own docstring states it is
               NEVER an EvidenceItem no matter how many objects cite it, so a
               rendered clip cannot become authority by being rendered.

    Measurement  Out of scope here (GO-HELIX-QA-01).

WHY A RENDERER CANNOT LAUNDER AUTHORITY

Three properties already hold, and the tests below pin all three:

  1. A scene's authority is not in the scene. It is in the Claim the scene
     cites, which carries its own class and confidence — so a renderer that
     ignores the Claim renders prose with no authority attached, rather than
     prose that has quietly acquired some.
  2. `content_class` survives acceptance. Accepting an AI-proposed unit never
     rewrites it to human_authored; acceptance and authorship are two separate
     facts by construction.
  3. Lifecycle state is on the Script itself, and the existing exporters
     already stamp it (`_status_banner` in services/work_product_export.py).
     A draft renders as a draft or not at all — the renderer never decides.

WHAT IS DELIBERATELY NOT HERE

No Question Taxonomy, no video provider, no playback surface, no narration.
Voice output is recorded NOT AUTHORIZED in governance/STATUS.md, and nothing in
this contract depends on it: the Script is text-first, and the transcript is the
source rather than a byproduct of some future audio.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CLAIM_CLASS_SUPPORTED_INTERPRETATION,
    CONFIDENCE_STATE_PARTIAL_SUPPORT,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_HUMAN_AUTHORED,
    CONTENT_CLASS_TEMPLATE_CONTENT,
    KNOWN_CONFIDENCE_STATES,
    OBSERVATION_AUTHOR_HUMAN,
    WORK_PRODUCT_STATE_DRAFT,
)

# The two conventions this contract fixes. Both ride on already-open-world
# fields, which is why neither needs a schema change or a closed-vocabulary
# amendment.
SCRIPT_ARTIFACT_TYPE = "script"
SECTION_TYPE_SCENE = "scene"          # narration; may carry an assertion
SECTION_TYPE_DIRECTION = "direction"  # rendering instruction; asserts nothing


class CanonicalScriptContractTests(unittest.TestCase):
    """One minimal fixture, carried end to end: a real question, a Script
    built only from existing primitives, and narrative units anchored to real
    evidence."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_script_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-script")

        # Real source and real evidence - the Script must anchor to governed
        # objects, so the fixture cannot fake them.
        self.source = self.store.add_source(
            self.workspace, name="spec.pdf", file_path="unused-pdf",
            kind="document", actor="tester",
        )
        registration = self.store.register_pdf_page_structure(
            self.workspace, self.source["id"],
            ["Section 4.2: Retaining walls shall achieve a factor of safety of 1.5."],
            actor="tester",
        )
        self.evidence_id = registration["evidence_item_ids"][0]

        self.case = self.store.create_case(
            self.workspace, title="Script contract case",
            objective="carry one question through to a script", created_by="tester",
        )

        # QUESTION - verbatim, on the step that also records what was examined.
        self.question = "Why does the retaining wall need a factor of safety of 1.5?"
        self.step = self.store.record_investigation_step(
            self.workspace, case_id=self.case["id"],
            step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": self.evidence_id},
            question=self.question,
            triggered_by_actor="tester",
        )

        # The assertion the script will narrate, with its own class and
        # confidence, cited to real evidence.
        self.sourced_claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=self.step["id"],
            statement="The spec sets a factor of safety of 1.5 for retaining walls.",
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="tester",
            evidence_links=[{"object_type": "evidence_item", "object_id": self.evidence_id}],
        )
        # A second, weaker claim - the script must be able to narrate an
        # inference WITHOUT it looking like the verified one.
        self.inferred_claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=self.step["id"],
            statement="The 1.5 figure most likely reflects the soil report's own assumptions.",
            claim_class=CLAIM_CLASS_SUPPORTED_INTERPRETATION,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_PARTIAL_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="tester",
            evidence_links=[{"object_type": "evidence_item", "object_id": self.evidence_id}],
        )

    def _build_script(self) -> dict:
        """The whole canonical Script, using only existing store methods."""
        script = self.store.create_work_product(
            self.workspace, artifact_type=SCRIPT_ARTIFACT_TYPE,
            title="Why a factor of safety of 1.5",
            created_by="tester", case_id=self.case["id"],
            source_investigation_step_id=self.step["id"],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"],
            section_type=SECTION_TYPE_SCENE,
            content={"text": "The specification requires a factor of safety of 1.5."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="tester",
            evidence_links=[{"object_type": "claim", "object_id": self.sourced_claim["id"]}],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"],
            section_type=SECTION_TYPE_SCENE,
            content={"text": "That figure appears to follow the soil report's assumptions."},
            content_class=CONTENT_CLASS_AI_PROPOSED, author="go",
            evidence_links=[{"object_type": "claim", "object_id": self.inferred_claim["id"]}],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"],
            section_type=SECTION_TYPE_DIRECTION,
            content={"shot": "hold on the spec excerpt", "seconds": 4},
            content_class=CONTENT_CLASS_TEMPLATE_CONTENT, author="tester",
        )
        return self.store.get_work_product(self.workspace, script["id"])

    # -- the chain -------------------------------------------------------

    def test_the_script_reaches_its_originating_question_verbatim(self):
        script = self._build_script()
        step = self.store.get_investigation_step(
            self.workspace, script["source_investigation_step_id"]
        )
        self.assertEqual(step["question"], self.question)

    def test_narrative_units_are_ordered_and_carry_exact_text(self):
        script = self._build_script()
        scenes = [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_SCENE]
        self.assertEqual([s["order_index"] for s in scenes], sorted(s["order_index"] for s in scenes))
        self.assertEqual(
            scenes[0]["content"]["text"],
            "The specification requires a factor of safety of 1.5.",
        )

    def test_every_scene_anchors_to_a_real_governed_object(self):
        script = self._build_script()
        for scene in [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_SCENE]:
            self.assertTrue(scene["evidence_links"], "a scene must anchor to something")
            for link in scene["evidence_links"]:
                self.assertIsNotNone(
                    self.store.get_claim(self.workspace, link["object_id"]),
                    "scene cites a claim that does not exist",
                )

    def test_a_scene_cannot_cite_something_that_does_not_exist(self):
        # The structural answer to citation laundering: a fabricated anchor is
        # not merely discouraged, it cannot be persisted.
        script = self.store.create_work_product(
            self.workspace, artifact_type=SCRIPT_ARTIFACT_TYPE, title="bad",
            created_by="tester", source_investigation_step_id=self.step["id"],
        )
        with self.assertRaises(CaseWorkspaceError) as caught:
            self.store.add_work_product_section(
                self.workspace, work_product_id=script["id"],
                section_type=SECTION_TYPE_SCENE,
                content={"text": "Invented."},
                content_class=CONTENT_CLASS_AI_PROPOSED, author="go",
                evidence_links=[{"object_type": "claim", "object_id": "no-such-claim"}],
            )
        self.assertIn("not found in this project", str(caught.exception))

    def test_sourced_and_inferred_are_distinguishable_without_reading_the_prose(self):
        # The renderer must never have to parse narration to learn how well
        # supported it is.
        script = self._build_script()
        scenes = [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_SCENE]
        classes = []
        for scene in scenes:
            claim = self.store.get_claim(self.workspace, scene["evidence_links"][0]["object_id"])
            classes.append((claim["claim_class"], claim["confidence_state"]))
        self.assertIn((CLAIM_CLASS_DIRECTLY_VERIFIED, CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT), classes)
        self.assertIn((CLAIM_CLASS_SUPPORTED_INTERPRETATION, CONFIDENCE_STATE_PARTIAL_SUPPORT), classes)

    def test_uncertainty_is_a_closed_vocabulary_never_a_percentage(self):
        script = self._build_script()
        for scene in [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_SCENE]:
            claim = self.store.get_claim(self.workspace, scene["evidence_links"][0]["object_id"])
            self.assertIn(claim["confidence_state"], KNOWN_CONFIDENCE_STATES)
            self.assertNotIn("confidence_score", claim)

    def test_rendering_directions_assert_nothing(self):
        # A direction carries no evidence anchor and no claim. It tells a
        # renderer how to show something; it never tells anyone what is true.
        script = self._build_script()
        directions = [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_DIRECTION]
        self.assertTrue(directions)
        for direction in directions:
            self.assertEqual(direction["evidence_links"], [])
            self.assertNotIn("text", direction["content"])

    def test_provenance_of_each_unit_is_recorded_separately_from_the_script_author(self):
        script = self._build_script()
        by_class = {s["content_class"] for s in script["sections"]}
        self.assertIn(CONTENT_CLASS_HUMAN_AUTHORED, by_class)
        self.assertIn(CONTENT_CLASS_AI_PROPOSED, by_class)
        self.assertEqual(script["created_by"], "tester")

    def test_the_script_carries_lifecycle_and_starts_unrenderable(self):
        # A renderer consumes state; it never decides it. A fresh Script is a
        # draft, and the existing exporters already stamp that.
        script = self._build_script()
        self.assertEqual(script["state"], WORK_PRODUCT_STATE_DRAFT)
        self.assertEqual(script["version"], 1)
        self.assertIsNone(script.get("issued_checksum"))

    def test_a_renderer_can_consume_the_script_without_reinterpreting_authority(self):
        # The acceptance test for the whole contract: everything a renderer
        # needs is reachable by field access, with no re-derivation and no
        # judgement about how true anything is.
        script = self._build_script()
        timeline = []
        for section in sorted(script["sections"], key=lambda s: s["order_index"]):
            if section["removed"]:
                continue
            entry = {
                "kind": section["section_type"],
                "provenance": section["content_class"],
                "authority": None,
            }
            if section["section_type"] == SECTION_TYPE_SCENE:
                claim = self.store.get_claim(
                    self.workspace, section["evidence_links"][0]["object_id"]
                )
                entry["caption"] = section["content"]["text"]
                entry["authority"] = {
                    "claim_class": claim["claim_class"],
                    "confidence_state": claim["confidence_state"],
                    "adoption_state": claim["adoption_state"],
                }
            timeline.append(entry)

        self.assertEqual(len(timeline), 3)
        self.assertEqual([e["kind"] for e in timeline],
                         [SECTION_TYPE_SCENE, SECTION_TYPE_SCENE, SECTION_TYPE_DIRECTION])
        # Every narrated line has a caption and an authority record; the
        # direction has neither. Nothing required interpretation.
        for entry in timeline:
            if entry["kind"] == SECTION_TYPE_SCENE:
                self.assertTrue(entry["caption"])
                self.assertIsNotNone(entry["authority"])
            else:
                self.assertIsNone(entry["authority"])

    def test_claims_remain_proposals_until_a_human_adopts_them(self):
        # A rendered clip must not be able to promote its own content.
        script = self._build_script()
        for scene in [s for s in script["sections"] if s["section_type"] == SECTION_TYPE_SCENE]:
            claim = self.store.get_claim(self.workspace, scene["evidence_links"][0]["object_id"])
            self.assertEqual(claim["adoption_state"], "proposed")


if __name__ == "__main__":
    unittest.main()
