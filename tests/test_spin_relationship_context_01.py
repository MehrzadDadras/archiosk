"""Bounded relationship/supersession context supplied to Spin."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from services.case_workspace import SPIN_KIND_FIRST
from services.spin import (
    _MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT,
    _MAX_SUPERSESSION_EVIDENCE_IN_PROMPT,
    _build_prompt,
    _shape_relationship_evidence,
    _shape_supersession_evidence,
    run_spin,
)


def _relationship(**overrides):
    value = {
        "id": "rel-1", "project_id": "project-1", "from_type": "source",
        "from_id": "source-a", "to_type": "requirement", "to_id": "req-1",
        "relationship_type": "contradicts", "created_at": "2026-08-21T10:00:00Z",
        "provisional": True, "validation_state": "disputed", "status": "disputed",
        "reason": "Reviewer has not confirmed the edge.",
    }
    value.update(overrides)
    return value


def _supersession(**overrides):
    value = {
        "id": "sup-1", "project_id": "project-1", "predecessor_type": "source",
        "predecessor_id": "source-a", "successor_type": "source",
        "successor_id": "source-b", "actor": "owner", "authorized_at": "2026-08-21T11:00:00Z",
        "reason": "Revision issued.", "authority_class": "approval_gate:source_revision",
    }
    value.update(overrides)
    return value


class SpinRelationshipContextTests(unittest.TestCase):
    def test_defensive_shapes_preserve_provenance_and_unknown_vocabulary(self):
        shaped = _shape_relationship_evidence([_relationship(relationship_type="future_edge")])
        self.assertEqual(shaped[0]["relationship_type"], "future_edge")
        self.assertEqual(shaped[0]["validation_state"], "disputed")
        self.assertEqual(shaped[0]["status"], "disputed")
        self.assertEqual(_shape_supersession_evidence([_supersession()])[0]["predecessor_id"], "source-a")

    def test_both_payloads_are_bounded_by_explicit_caps(self):
        relationships = [_relationship(id=f"rel-{i}") for i in range(_MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT + 5)]
        supersessions = [_supersession(id=f"sup-{i}") for i in range(_MAX_SUPERSESSION_EVIDENCE_IN_PROMPT + 5)]
        self.assertEqual(len(_shape_relationship_evidence(relationships)), _MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT)
        self.assertEqual(len(_shape_supersession_evidence(supersessions)), _MAX_SUPERSESSION_EVIDENCE_IN_PROMPT)

    def test_prompt_keeps_relationships_and_supersessions_distinct_and_bounded(self):
        prompt = _build_prompt(
            SPIN_KIND_FIRST, "rfp.pdf", [], [], [],
            relationship_evidence=[_relationship()],
            supersession_evidence=[_supersession()],
        )
        self.assertIn("Relationship evidence", prompt)
        self.assertIn("Supersession evidence", prompt)
        self.assertIn("rel-1", prompt)
        self.assertIn("sup-1", prompt)
        self.assertIn("CONTRADICTS may indicate tension, not automatic noncompliance", prompt)
        self.assertIn("does not prove downstream propagation", prompt)
        self.assertNotIn("therefore coordinated", prompt.lower())

    def test_relationship_confidence_is_visible_without_becoming_authority(self):
        prompt = _build_prompt(
            SPIN_KIND_FIRST, "rfp.pdf", [], [], [],
            relationship_evidence=[_relationship(confidence=0.42)],
        )
        self.assertIn("confidence=0.42", prompt)
        self.assertIn("provisional=True", prompt)

    def test_run_spin_forwards_both_payloads_to_prompt_without_persisting_them(self):
        captured = {}

        def fake_call(**kwargs):
            captured["prompt"] = kwargs["user_prompt"]
            return SimpleNamespace(ran=False, skipped_reason="test seam")

        with patch("services.spin.call_llm_json", side_effect=fake_call):
            result = run_spin(
                SPIN_KIND_FIRST, "rfp.pdf", [], [], [],
                relationship_evidence=[_relationship()],
                supersession_evidence=[_supersession()],
            )
        self.assertFalse(result.ran)
        self.assertIn("rel-1", captured["prompt"])
        self.assertIn("sup-1", captured["prompt"])
        self.assertFalse(hasattr(result, "relationship_evidence"))
        self.assertFalse(hasattr(result, "supersession_evidence"))


if __name__ == "__main__":
    unittest.main()
