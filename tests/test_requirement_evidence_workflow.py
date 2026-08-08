"""
Connect Accepted Knowledge to Requirement Impact - end-to-end tests.

Makes the Requirement-compliance rollup explainable: a governed
Requirement's own RequirementAdjudication.evidence_finding_ids/
evidence_relationship_ids (already the real, existing link a human
creates when adjudicating) is resolved and displayed alongside the
Requirement, and AcceptedKnowledge entries trace back to their source
Finding/Case and any Requirement(s) that cite that Finding as evidence.
No new compliance engine, no invented linkage object - purely
wiring/query/UI over data that already exists.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import AnalysisTrigger, CaseWorkspaceStore
from services.ingestion import document_source_payload
from services.requirements_registry import RequirementsRegistry


class RequirementEvidenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_requirement_evidence_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-requirement-evidence"

        self.item = RequirementItem(
            id="req-item-1", text="Contractor shall provide licensed and insured labor.",
            category="compliance_legal", confidence=0.7, source_line=6,
        )
        document = ParsedDocument(
            project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[self.item],
        )
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

        # CLAUDE-P32: see tests/test_case_privacy.py's identical setUp
        # comment. register_document_source is required here (unlike
        # that file) because _rfq_source_id below relies on the
        # auto-registered rfq_rfp_document Source.
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(self.project_id, register_document_source=document_source_payload(document))
        store.set_project_owner(workspace, owner="owner1", actor="owner1")
        store.grant_project_access(workspace, username="other-user", actor="owner1", actor_role="read_only")

        self.case = self._create_case(self.owner_client)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _create_case(self, client, title="Structural Drawing Review"):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return next(c for c in self._store().get(self.project_id).cases if c["title"] == title)

    def _rfq_source_id(self):
        return next(s for s in self._store().get(self.project_id).sources if s["kind"] == "rfq_rfp_document")["id"]

    def _promote_requirement(self):
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases/{self.case['id']}/requirement-items/{self.item.id}/promote",
            data={"source_id": self._rfq_source_id()}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return next(
            r for r in self._store().get(self.project_id).requirements
            if r["original_requirement_identifier"] == self.item.id
        )

    def _create_finding(self, case_id, statement="Certificates confirm current labor licensure."):
        store = self._store()
        workspace = store.get(self.project_id)
        trigger = AnalysisTrigger(trigger_type="user_initiated", triggered_by_actor="owner1")
        analysis = store.record_analysis(
            workspace, case_id=case_id, source_ids=[self._rfq_source_id()], objective="x",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": statement, "machine_confidence": 0.7, "source_id": self._rfq_source_id()}],
            trigger=trigger,
        )
        return analysis["finding_ids"][0]

    def _adjudicate(self, requirement_id, outcome, reasoning, evidence_finding_ids=None):
        data = {"outcome": outcome, "reasoning": reasoning, "case_id": self.case["id"]}
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data=data if not evidence_finding_ids else {**data, "evidence_finding_id": evidence_finding_ids},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    def _validate_dispose_apply(self, case_id, finding_id):
        store = self._store()
        workspace = store.get(self.project_id)
        store.record_reviewer_validation(workspace, finding_id=finding_id, validation="Correct", reviewer="owner1")
        workspace = store.get(self.project_id)
        store.record_disposition(workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1")
        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/apply",
            data={"confirm": "once"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    # -- Requirement -> connected Finding ------------------------------------

    def test_requirement_shows_linked_finding_as_evidence(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("Certificates confirm current labor licensure.", body)
        self.assertIn(self.case["title"], body)
        self.assertIn("Satisfied", body)

    def test_requirement_with_no_evidence_displays_honestly(self):
        requirement = self._promote_requirement()
        self._adjudicate(requirement["id"], "Not Applicable", "This clause does not apply to this scope.")

        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements render on their own page.
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = response.get_data(as_text=True)
        self.assertIn("No connected Findings or Accepted Knowledge cited as evidence yet.", body)

    # -- Accepted Knowledge -> source Finding/Case/Requirement ---------------

    def test_accepted_knowledge_traces_back_to_source_finding_and_case(self):
        finding_id = self._create_finding(self.case["id"], "Beam undersized per drawing S-101.")
        self._validate_dispose_apply(self.case["id"], finding_id)

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("Beam undersized per drawing S-101.", body)
        self.assertIn(f"from {self.case['title']}", body)
        self.assertIn("No linked Requirement", body)

    def test_accepted_knowledge_shows_linked_requirement_when_evidenced(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])
        self._validate_dispose_apply(self.case["id"], finding_id)

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("Linked Requirement(s):", body)
        self.assertIn(requirement["text_reference"][:40], body)

    # -- AcceptedKnowledge != compliance --------------------------------------

    def test_adjudication_unchanged_merely_because_finding_applied(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])

        store = self._store()
        workspace = store.get(self.project_id)
        state_before = store.requirement_adjudication_state(workspace, requirement["id"])

        self._validate_dispose_apply(self.case["id"], finding_id)

        workspace = store.get(self.project_id)
        state_after = store.requirement_adjudication_state(workspace, requirement["id"])
        self.assertEqual(state_before, "Satisfied")
        self.assertEqual(state_after, "Satisfied")  # Apply never creates/alters a RequirementAdjudication
        adjudications = [a for a in workspace.requirement_adjudications if a["requirement_id"] == requirement["id"]]
        self.assertEqual(len(adjudications), 1)  # still exactly the one explicit human adjudication

    def test_adjudication_changes_only_through_explicit_human_action(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"])

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("Not Yet Assessed", response.get_data(as_text=True))

        self._adjudicate(requirement["id"], "Satisfied", "Initial determination.", [finding_id])
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("Satisfied", response.get_data(as_text=True))

        self._adjudicate(requirement["id"], "Not Satisfied", "New evidence changed the determination.", [finding_id])
        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("Not Satisfied", response.get_data(as_text=True))

    # -- privacy -------------------------------------------------------------

    def test_private_case_finding_evidence_redacted_for_other_user(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])

        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements render on their own page.
        response = self.other_client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = response.get_data(as_text=True)
        self.assertIn("Satisfied", body)  # the adjudication outcome/reasoning is project-wide, unchanged
        self.assertIn("Evidence from an Investigation you don't have access to.", body)
        self.assertNotIn("Certificates confirm current labor licensure.", body)
        self.assertNotIn(self.case["title"], body)

    # -- cross-project isolation ---------------------------------------------

    def test_requirement_evidence_does_not_leak_across_projects(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])

        other_project_id = "test-project-requirement-evidence-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        response = self.owner_client.get(f"/projects/{other_project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertNotIn("Certificates confirm current labor licensure.", body)
        self.assertNotIn(requirement["text_reference"], body)

    # -- persistence across a fresh session ---------------------------------

    def test_evidence_links_survive_fresh_session(self):
        requirement = self._promote_requirement()
        finding_id = self._create_finding(self.case["id"], "Certificates confirm current labor licensure.")
        self._adjudicate(requirement["id"], "Satisfied", "Confirmed via submitted certificates.", [finding_id])
        self._validate_dispose_apply(self.case["id"], finding_id)

        fresh_client = self.flask_app.test_client()
        with fresh_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        response = fresh_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("Certificates confirm current labor licensure.", body)
        self.assertIn("Linked Requirement(s):", body)
        self.assertIn("Satisfied", body)


if __name__ == "__main__":
    unittest.main()
