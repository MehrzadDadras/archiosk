"""
Case-Scoped Route Authorization Hardening.

Every Case-scoped write/download route that receives a case_id (or an
object id whose Case must be derived) now verifies the actual,
server-derived Case against the requester's own visible_cases_for
result before acting - never trusting a URL/form case_id, and never
trusting that an object id (Finding/RFIDraft) actually belongs to
whichever case_id happened to be supplied alongside it.

These tests drive the real Flask app through real HTTP requests with
genuinely separate authenticated sessions, proving:

- a caller cannot post/mutate into another user's PRIVATE Case merely
  by changing the URL's case_id;
- a caller cannot smuggle a write by pairing a real, visible case_id
  with an object id (finding_id/draft_id) that actually belongs to a
  DIFFERENT, private Case;
- an object id from one Project cannot be operated on through a
  different Project's URL;
- legitimate SHARED-Case collaboration still works unhindered;
- archived-Case write rejection is untouched by this hardening.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import AnalysisTrigger, CaseWorkspaceStore
from services.ingestion import document_source_payload
from services.requirements_registry import RequirementsRegistry


class RouteAuthorizationHardeningTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_route_hardening_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-hardening"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

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

        # CLAUDE-P32: this class's whole subject is Case-scoped route
        # spoofing between two authenticated sessions that both need to
        # be able to open the project at all -- see
        # tests/test_case_privacy.py's own identical setUp comment for
        # the full reasoning.
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(self.project_id, register_document_source=document_source_payload(document))
        store.set_project_owner(workspace, owner="owner1", actor="owner1")
        store.grant_project_access(workspace, username="other-user", actor="owner1", actor_role="read_only")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _create_case(self, client, title="Investigation"):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return next(c for c in self._store().get(self.project_id).cases if c["title"] == title)

    def _rfq_source_id(self, project_id=None):
        workspace = self._store().get(project_id or self.project_id)
        return next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")["id"]

    def _create_finding(self, case_id, statement="Beam undersized per drawing S-101.", project_id=None):
        store = self._store()
        workspace = store.get(project_id or self.project_id)
        trigger = AnalysisTrigger(trigger_type="user_initiated", triggered_by_actor="owner1")
        analysis = store.record_analysis(
            workspace, case_id=case_id, source_ids=[self._rfq_source_id(project_id)], objective="x",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": statement, "machine_confidence": 0.7, "source_id": self._rfq_source_id(project_id)}],
            trigger=trigger,
        )
        return analysis["finding_ids"][0]

    def _validated_disposed_finding(self, case_id):
        finding_id = self._create_finding(case_id)
        store = self._store()
        workspace = store.get(self.project_id)  # re-fetch after _create_finding's own save()
        store.record_reviewer_validation(workspace, finding_id=finding_id, validation="Correct", reviewer="owner1")
        store.record_disposition(workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1")
        return finding_id

    # -- case spoofing: URL case_id ----------------------------------------

    def test_cannot_post_message_to_private_case_via_url_spoofing(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{private_case['id']}/messages",
            data={"text": "trying to sneak in"},
        )
        self.assertEqual(response.status_code, 404)

        reloaded = next(c for c in self._store().get(self.project_id).cases if c["id"] == private_case["id"])
        self.assertEqual(reloaded["conversation"], [])

    def test_cannot_add_drawing_source_to_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{private_case['id']}/sources",
            data={}, content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_apply_findings_in_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{private_case['id']}/apply",
            data={"confirm": "once"},
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_promote_requirement_item_in_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{private_case['id']}/requirement-items/whatever/promote",
            data={"source_id": self._rfq_source_id()},
        )
        self.assertEqual(response.status_code, 404)

    # -- case spoofing: object id (Finding) derives the real Case -----------

    def test_cannot_validate_finding_belonging_to_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        finding_id = self._create_finding(private_case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct"},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        self.assertEqual(
            [v for v in workspace.reviewer_validations if v["finding_id"] == finding_id], [],
        )

    def test_hidden_case_id_form_field_cannot_launder_a_private_findings_case(self):
        """The most direct spoofing attempt this hardening closes: pair a
        real finding_id from the attacker's OWN Private Case with a
        legitimate-looking case_id belonging to someone else's Case in
        the hidden form field. The route must derive the Finding's own
        real case_id server-side and ignore the form value entirely."""
        other_owned_case = self._create_case(self.other_client, title="Attacker's own case")
        private_case = self._create_case(self.owner_client, title="Victim's private case")
        finding_id = self._create_finding(private_case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct", "case_id": other_owned_case["id"]},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        self.assertEqual(
            [v for v in workspace.reviewer_validations if v["finding_id"] == finding_id], [],
        )

    def test_cannot_set_disposition_on_finding_belonging_to_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        finding_id = self._create_finding(private_case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/disposition",
            data={"disposition": "Confirmed"},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        self.assertEqual([d for d in workspace.dispositions if d["finding_id"] == finding_id], [])

    def test_cannot_create_rfi_draft_by_pairing_own_case_with_someone_elses_finding(self):
        """The URL case_id belongs to the attacker (visible to them), but
        finding_id belongs to a different, private Case - the route must
        reject based on the Finding's own real Case, not the URL's."""
        attacker_case = self._create_case(self.other_client, title="Attacker's own visible case")
        victim_case = self._create_case(self.owner_client, title="Victim's private case")
        finding_id = self._validated_disposed_finding(victim_case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{attacker_case['id']}/rfi-drafts",
            data={"finding_id": finding_id, "question_text": "smuggled RFI"},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        self.assertEqual([d for d in workspace.rfi_drafts if d["finding_id"] == finding_id], [])

    def test_cannot_update_or_issue_rfi_draft_belonging_to_private_case(self):
        private_case = self._create_case(self.owner_client, title="Owner's Private Case")
        finding_id = self._validated_disposed_finding(private_case["id"])
        store = self._store()
        workspace = store.get(self.project_id)
        draft = store.create_rfi_draft(workspace, finding_id=finding_id, question_text="", created_by="owner1")

        update_response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/rfi-drafts/{draft['id']}/question",
            data={"question_text": "hijacked question"},
        )
        self.assertEqual(update_response.status_code, 404)

        issue_response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/rfi-drafts/{draft['id']}/issue",
            data={},
        )
        self.assertEqual(issue_response.status_code, 404)

        workspace = self._store().get(self.project_id)
        reloaded_draft = next(d for d in workspace.rfi_drafts if d["id"] == draft["id"])
        self.assertEqual(reloaded_draft["question_text"], "")
        self.assertEqual(reloaded_draft["status"], "draft")

    # -- project spoofing --------------------------------------------------

    def test_finding_from_project_a_cannot_be_validated_via_project_b_url(self):
        other_project_id = "test-project-hardening-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        b_client = self.flask_app.test_client()
        with b_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"
        b_client.get(f"/projects/{other_project_id}/workspace")  # seed the workspace file

        case_a = self._create_case(self.owner_client, title="Case in Project A")
        finding_id = self._create_finding(case_a["id"])

        response = self.owner_client.post(
            f"/projects/{other_project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct"}, follow_redirects=True,
        )
        # The finding simply doesn't exist in Project B's own workspace -
        # the store layer's own not-found check rejects it; either way,
        # no ReviewerValidation is ever recorded against it from there.
        self.assertIn(response.status_code, (200, 404))

        project_a_workspace = self._store().get(self.project_id)
        self.assertEqual(
            [v for v in project_a_workspace.reviewer_validations if v["finding_id"] == finding_id], [],
        )
        project_b_workspace = self._store().get(other_project_id)
        self.assertEqual(project_b_workspace.reviewer_validations, [])

    # -- shared/collaborative continuity -----------------------------------

    def test_shared_case_participant_can_still_validate_finding(self):
        case = self._create_case(self.owner_client, title="Shared Investigation")
        self._store().share_case(self._store().get(self.project_id), case_id=case["id"], actor="owner1")
        finding_id = self._create_finding(case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = self._store().get(self.project_id)
        validations = [v for v in workspace.reviewer_validations if v["finding_id"] == finding_id]
        self.assertEqual(len(validations), 1)
        self.assertEqual(validations[0]["reviewer"], "other-user")

    def test_shared_case_participant_can_still_post_message(self):
        case = self._create_case(self.owner_client, title="Shared Investigation")
        self._store().share_case(self._store().get(self.project_id), case_id=case["id"], actor="owner1")

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/messages",
            data={"text": "A genuine collaborative contribution."}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = self._store().get(self.project_id)
        reloaded = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertTrue(any(m["text"] == "A genuine collaborative contribution." for m in reloaded["conversation"]))

    def test_owner_can_still_apply_findings_in_own_case(self):
        case = self._create_case(self.owner_client, title="Own Investigation")
        finding_id = self._create_finding(case["id"])
        store = self._store()
        workspace = store.get(self.project_id)
        store.record_reviewer_validation(workspace, finding_id=finding_id, validation="Correct", reviewer="owner1")
        store.record_disposition(workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1")

        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/apply",
            data={"confirm": "once"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = self._store().get(self.project_id)
        applied_finding = next(f for f in workspace.findings if f["id"] == finding_id)
        self.assertEqual(applied_finding["claim_status"], "applied")

    # -- archive -------------------------------------------------------------

    def test_archived_case_write_still_rejected_after_hardening(self):
        case = self._create_case(self.owner_client, title="To Be Archived")
        finding_id = self._create_finding(case["id"])
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/findings/{finding_id}/validate",
            data={"validation": "Correct"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)  # rejected via flash+redirect, not a 404

        workspace = self._store().get(self.project_id)
        self.assertEqual(
            [v for v in workspace.reviewer_validations if v["finding_id"] == finding_id], [],
        )


if __name__ == "__main__":
    unittest.main()
