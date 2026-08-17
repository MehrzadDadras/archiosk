"""
CLAUDE-POSTCAMEL-CA1C - Constructive Professional Judgment /
Self-Capability Awareness.

A live Product Owner interaction found ARCHIOSK Go answering an
ordinary advice-seeking question ("Should I organize this RFP into
folders?") too defensively, and mixing Project evidence with knowledge
of ARCHIOSK's own capabilities. This tranche implements, as the
smallest safe slice:

  - a small, centralized, audited Application Capability Knowledge
    registry (services/capability_registry.py) - "Can ARCHIOSK create
    folders?" is now answered from this, never from Project evidence
    (the exact category error Section 4 names);
  - a real, deterministic "organize this" advice handler, grounded in
    this Project's own already-extracted candidate-Requirement
    categories (never a hardcoded universal taxonomy), presenting a
    real vertical structure and a genuinely executable "Create this
    structure" action wired to the pre-existing, real, governed
    Design-Builder Workspace Folder mechanism (services/case_workspace.py's
    own create_folder - confirmed real and safe by direct audit, not
    newly built);
  - a behavioral-contract update teaching the general LLM-based path
    the same "answer first, be concise, don't answer capability
    questions from Project evidence" discipline, for advice questions
    outside the one deterministic scenario above.

Run via:

    python -m unittest tests.test_ca1c_constructive_response -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument, RequirementItem
from services.capability_registry import (
    CAPABILITY_STATUS_IMPLEMENTED,
    CAPABILITY_STATUS_UNAVAILABLE,
    find_capability_by_phrase,
)
from services.case_workspace import CaseWorkspaceStore
from services.conversation_interpreter import (
    _looks_like_capability_question,
    _looks_like_organize_question,
    compute_organize_groups,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1c_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="ca1c_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(
            owner="ca1c_owner", project_name="CA1C RFP Test Project",
            candidate_items=[
                ("Proponents shall submit technical and commercial proposals separately.", "submission_instruction"),
                ("Evaluation shall weigh technical merit at 60%.", "evaluation_criteria"),
                ("The System shall support real-time monitoring.", "scope_of_work"),
                ("The System shall use redundant power supplies.", "technical_specification"),
                ("Proponent shall carry commercial general liability insurance.", "compliance_legal"),
                ("Milestone: Substantial Completion by Q4 2027.", "schedule_milestone"),
            ],
        )
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt", candidate_items=None):
        items = candidate_items or []

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
                requirements=[
                    RequirementItem(id=str(uuid.uuid4()), text=text, category=category, confidence=0.8, source_line=i)
                    for i, (text, category) in enumerate(items)
                ],
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "ca1c_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _discuss(self, client, text: str, **extra):
        data = {"text": text}
        data.update(extra)
        return client.post(f"/projects/{self.project_id}/workspace/discuss", data=data)


class CapabilityRegistryTests(unittest.TestCase):
    def test_folder_capability_is_implemented(self):
        cap = find_capability_by_phrase("can you create these folders")
        self.assertEqual(cap.status, CAPABILITY_STATUS_IMPLEMENTED)

    def test_physical_folder_capability_is_unavailable_with_alternative(self):
        cap = find_capability_by_phrase("can you create a real physical folder on disk")
        self.assertEqual(cap.status, CAPABILITY_STATUS_UNAVAILABLE)
        self.assertIsNotNone(cap.alternative)

    def test_email_capability_is_unavailable(self):
        cap = find_capability_by_phrase("can you send this to sarah by email")
        self.assertEqual(cap.status, CAPABILITY_STATUS_UNAVAILABLE)

    def test_unmatched_phrase_returns_none(self):
        self.assertIsNone(find_capability_by_phrase("what is the weather today"))


class PhraseDetectionTests(unittest.TestCase):
    def test_recognizes_capability_phrases(self):
        for phrase in ("Can you create these folders?", "Can ARCHIOSK send email?", "Does ARCHIOSK support voice?"):
            self.assertTrue(_looks_like_capability_question(phrase.lower()), phrase)

    def test_recognizes_organize_phrases(self):
        for phrase in ("Should I organize this into folders?", "How should I organize this RFP?"):
            self.assertTrue(_looks_like_organize_question(phrase.lower()), phrase)

    def test_ordinary_evidence_question_is_not_a_capability_question(self):
        self.assertFalse(_looks_like_capability_question("what does opr-3.5 require"))


class CapabilityQuestionConversationTests(_BaseTestCase):
    def test_folder_capability_answered_truthfully_no_rfp_search(self):
        client = self._client()
        self._discuss(client, "Can you create these folders for me?")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        # CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01 follow-up: this reply comes
        # from capability_registry.py's static, deliberately workspace-
        # blind capability description (CA1C's own "by construction, no
        # workspace consulted" design for self-referential "what can you
        # do" answers) - it names the mechanism by its canonical internal
        # name, not a per-project claim of coexistence with a Proponent
        # workspace, so it intentionally still says "Design-Builder
        # Workspace" even inside a CLIENT_OWNER project.
        self.assertIn("Design-Builder Workspace", body)
        self.assertNotIn("not covered by", body.lower())

    def test_physical_folder_capability_says_no_with_alternative(self):
        client = self._client()
        self._discuss(client, "Can you create real physical folders on disk?")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("No.", body)
        self.assertIn("What I can do instead", body)

    def test_email_capability_says_no_without_searching_project(self):
        client = self._client()
        self._discuss(client, "Can you send this to Sarah by email?")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("No.", body)
        self.assertIn("external communications", body.lower())


class OrganizeAdviceTests(_BaseTestCase):
    def test_no_referent_asks_which_source(self):
        client = self._client()
        self._discuss(client, "Should I organize this into folders?")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Which Source should I organize", body)

    def test_recommendation_first_and_source_preserved(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        client = self._client()
        self._discuss(client, "Should I organize this into folders?", selected_source_id=source_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Yes.", body)
        self.assertIn("intact", body)
        self.assertNotIn("only you can decide", body.lower())

    def test_vertical_structure_grounded_in_real_categories(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        client = self._client()
        self._discuss(client, "Should I organize this into folders?", selected_source_id=source_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        for group in ("Procurement", "Technical / Scope", "Commercial / Legal", "Schedule / Milestones"):
            self.assertIn(group, body)

    def test_create_structure_action_offered_and_real(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        client = self._client()
        self._discuss(client, "Should I organize this into folders?", selected_source_id=source_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Create this structure", body)

        resp = client.post(f"/projects/{self.project_id}/workspace/organize/create-structure")
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        folder_names = {f["name"] for f in workspace.folders if not f.get("removed_at")}
        self.assertIn("Procurement", folder_names)
        self.assertIn("Technical / Scope", folder_names)

    def test_create_structure_is_idempotent(self):
        client = self._client()
        client.post(f"/projects/{self.project_id}/workspace/organize/create-structure")
        resp = client.post(f"/projects/{self.project_id}/workspace/organize/create-structure")
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        procurement_folders = [f for f in workspace.folders if f["name"] == "Procurement" and not f.get("removed_at")]
        self.assertEqual(len(procurement_folders), 1)

    def test_insufficient_structure_is_honest_not_fabricated(self):
        empty_doc = self._ingest(owner="ca1c_owner", project_name="CA1C Empty Project", candidate_items=[])
        client = self._client()
        workspace = self._store().get(empty_doc.project_id)
        source_id = workspace.sources[0]["id"]
        client.post(
            f"/projects/{empty_doc.project_id}/workspace/discuss",
            data={"text": "Should I organize this into folders?", "selected_source_id": source_id},
        )
        body = client.get(f"/projects/{empty_doc.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("isn&#39;t enough extracted structure", body)

    def test_compute_organize_groups_is_shared_source_of_truth(self):
        workspace = self._store().get(self.project_id)
        groups = compute_organize_groups(self._store(), workspace)
        self.assertIn("Procurement", groups)
        self.assertNotIn("Appendices", groups)  # no "other"-category items were seeded


if __name__ == "__main__":
    unittest.main()
