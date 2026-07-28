"""
CLAUDE-P12R - represented-party perspective: canonical governed object +
represented Participant -> perspective-sensitive interpretation. The
governed Requirement is never rewritten; a PerspectiveAssessment is a
purely additive, attributed annotation of what it looks like FROM one
Participant's position, recorded identically whether the origin is a
human's explicit act or the machine's independently-reached assessment.

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
    PARTICIPANT_ROLE_DESIGN_BUILDER,
    PERSPECTIVE_ORIGIN_HUMAN,
    PERSPECTIVE_ORIGIN_MACHINE,
    PERSPECTIVE_POLARITY_OPPORTUNITY,
    PERSPECTIVE_POLARITY_RISK,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry


class ParticipantAndRepresentedPartyStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_participant_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_register_and_list_participants(self):
        p = self.store.record_participant(
            self.workspace, name="Cedar Harbour DB JV", role_type=PARTICIPANT_ROLE_DESIGN_BUILDER,
            created_by="owner1",
        )
        self.assertEqual(len(self.store.participants_for_project(self.workspace)), 1)
        self.assertEqual(p["role_type"], PARTICIPANT_ROLE_DESIGN_BUILDER)

    def test_name_required(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_participant(self.workspace, name="  ", role_type="owner", created_by="owner1")

    def test_no_represented_party_by_default(self):
        self.assertIsNone(self.store.represented_party_for(self.workspace, "owner1"))

    def test_set_represented_party(self):
        p = self.store.record_participant(
            self.workspace, name="Cedar Harbour DB JV", role_type=PARTICIPANT_ROLE_DESIGN_BUILDER,
            created_by="owner1",
        )
        self.store.set_represented_party(self.workspace, reviewer="owner1", participant_id=p["id"])
        self.assertEqual(self.store.represented_party_for(self.workspace, "owner1")["id"], p["id"])

    def test_set_represented_party_requires_a_real_participant(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.set_represented_party(self.workspace, reviewer="owner1", participant_id="nonexistent")

    def test_represented_party_is_per_reviewer(self):
        p = self.store.record_participant(self.workspace, name="Owner Org", role_type="owner", created_by="owner1")
        self.store.set_represented_party(self.workspace, reviewer="owner1", participant_id=p["id"])
        self.assertIsNone(self.store.represented_party_for(self.workspace, "owner2"))


class PerspectiveAssessmentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_perspective_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")
        self.participant = self.store.record_participant(
            self.workspace, name="Cedar Harbour DB JV", role_type=PARTICIPANT_ROLE_DESIGN_BUILDER,
            created_by="owner1",
        )
        self.anchor = {"anchor_type": OBJECT_KIND_REQUIREMENT, "anchor_id": "req-1"}

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_record_a_human_assessment(self):
        record = self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="This obligation falls on us if the site conditions differ.",
            recorded_by="owner1",
        )
        self.assertEqual(record["polarity"], PERSPECTIVE_POLARITY_RISK)
        self.assertEqual(record["recorded_by"], "owner1")

    def test_human_origin_requires_recorded_by(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_perspective_assessment(
                self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
                polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
                reasoning="x",
            )

    def test_machine_origin_must_not_carry_recorded_by(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_perspective_assessment(
                self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
                polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_MACHINE,
                reasoning="x", recorded_by="owner1",
            )

    def test_reasoning_required(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_perspective_assessment(
                self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
                polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
                reasoning="   ", recorded_by="owner1",
            )

    def test_unrecognized_polarity_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_perspective_assessment(
                self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
                polarity="catastrophic", origin=PERSPECTIVE_ORIGIN_HUMAN,
                reasoning="x", recorded_by="owner1",
            )

    def test_participant_must_exist(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_perspective_assessment(
                self.workspace, anchor=self.anchor, participant_id="nonexistent",
                polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
                reasoning="x", recorded_by="owner1",
            )

    def test_convergence_with_no_records_is_all_none(self):
        convergence = self.store.perspective_convergence_for(
            self.workspace, OBJECT_KIND_REQUIREMENT, "req-1", self.participant["id"],
        )
        self.assertIsNone(convergence["human"])
        self.assertIsNone(convergence["machine"])
        self.assertIsNone(convergence["agree"])

    def test_convergence_agree(self):
        self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="Our exposure.", recorded_by="owner1",
        )
        self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_MACHINE,
            reasoning="Independently found the same exposure.", confidence=0.7,
        )
        convergence = self.store.perspective_convergence_for(
            self.workspace, OBJECT_KIND_REQUIREMENT, "req-1", self.participant["id"],
        )
        self.assertTrue(convergence["agree"])

    def test_convergence_disagreement(self):
        self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="Our exposure.", recorded_by="owner1",
        )
        self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_OPPORTUNITY, origin=PERSPECTIVE_ORIGIN_MACHINE,
            reasoning="Reads as an opportunity given the contract terms.", confidence=0.6,
        )
        convergence = self.store.perspective_convergence_for(
            self.workspace, OBJECT_KIND_REQUIREMENT, "req-1", self.participant["id"],
        )
        self.assertFalse(convergence["agree"])

    def test_convergence_is_scoped_to_the_participant(self):
        other_participant = self.store.record_participant(
            self.workspace, name="Owner Org", role_type="owner", created_by="owner1",
        )
        self.store.record_perspective_assessment(
            self.workspace, anchor=self.anchor, participant_id=self.participant["id"],
            polarity=PERSPECTIVE_POLARITY_RISK, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="Our exposure.", recorded_by="owner1",
        )
        # Same anchor, a DIFFERENT participant - must not see the first one's mark.
        convergence = self.store.perspective_convergence_for(
            self.workspace, OBJECT_KIND_REQUIREMENT, "req-1", other_participant["id"],
        )
        self.assertIsNone(convergence["human"])


class PerspectiveRouteAndRenderTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_perspective_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-perspective"

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

    def _register_requirement(self):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def test_marking_perspective_without_a_represented_party_is_rejected(self):
        requirement = self._register_requirement()
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement['id']}/perspective",
            data={"polarity": PERSPECTIVE_POLARITY_RISK, "reasoning": "x"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.store.get(self.project_id).perspective_assessments, [])

    def test_full_flow_register_represent_mark_and_render(self):
        requirement = self._register_requirement()

        self.client.post(
            f"/projects/{self.project_id}/workspace/participants",
            data={"name": "Cedar Harbour DB JV", "role_type": PARTICIPANT_ROLE_DESIGN_BUILDER},
        )
        participant = self.store.get(self.project_id).participants[0]

        self.client.post(
            f"/projects/{self.project_id}/workspace/represented-party",
            data={"participant_id": participant["id"]},
        )

        self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement['id']}/perspective",
            data={"polarity": PERSPECTIVE_POLARITY_RISK, "reasoning": "This falls on us if conditions differ."},
        )

        page = self.client.get(f"/projects/{self.project_id}/workspace")
        body = page.get_data(as_text=True)
        self.assertIn("Cedar Harbour DB JV", body)
        self.assertIn("This falls on us if conditions differ.", body)
        self.assertIn(PERSPECTIVE_POLARITY_RISK, body)

    def test_machine_investigation_records_a_perspective_assessment_when_represented_party_set(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/participants",
            data={"name": "Cedar Harbour DB JV", "role_type": PARTICIPANT_ROLE_DESIGN_BUILDER},
        )
        participant = self.store.get(self.project_id).participants[0]
        self.client.post(
            f"/projects/{self.project_id}/workspace/represented-party",
            data={"participant_id": participant["id"]},
        )

        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps({
            "assessment": "No conflicting evidence on record.",
            "confidence": 0.6,
            "supporting_points": [],
            "open_questions": [],
            "needs_human_judgment": True,
            "risk_polarity": PERSPECTIVE_POLARITY_RISK,
            "risk_confidence": 0.65,
            "risk_reasoning": "The as-built obligation falls on the Design-Builder.",
        })
        fake_response = MagicMock()
        fake_response.content = [fake_block]

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = fake_response
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={
                    "text": "Something is wrong here",
                    "anchor_type": "requirement",
                    "anchor_id": requirement["id"],
                    "anchor_description": "Section 3.1",
                },
            )
            workspace = self.store.get(self.project_id)
            system_message = workspace.project_conversation[1]
            message_id = system_message["action_taken"].split(":", 1)[1]
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation",
            )

        workspace = self.store.get(self.project_id)
        machine_assessments = [a for a in workspace.perspective_assessments if a["origin"] == PERSPECTIVE_ORIGIN_MACHINE]
        self.assertEqual(len(machine_assessments), 1)
        self.assertEqual(machine_assessments[0]["polarity"], PERSPECTIVE_POLARITY_RISK)
        self.assertIsNone(machine_assessments[0]["recorded_by"])
        self.assertIsNotNone(machine_assessments[0]["investigation_step_id"])

        case_id = resp.headers["Location"].rsplit("case=", 1)[1]
        page = self.client.get(f"/projects/{self.project_id}/workspace?case={case_id}")
        self.assertIn("Design-Builder", page.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
