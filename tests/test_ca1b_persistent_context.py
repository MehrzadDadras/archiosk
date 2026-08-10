"""
CLAUDE-POSTCAMEL-CA1B - Persistent Professional Context / Requirement &
Finding Selection.

Closes CA1A's own named limitation: Requirement and Finding selection
were anchor-only and did not persist as reliably as Source selection
(Source already had a real, bookmarkable, project-scoped `?source=`
convention). Implements, as the smallest safe slice:

  - `?requirement=`/`?finding=` query-param selection, mirroring the
    pre-existing `?source=` convention exactly (real per-workspace
    lookup, `None` for any stale/foreign id, never an error);
  - ONE unified, project-scoped "professional context" session slot
    (`selected_object:{project_id}`) - not one per object type, so a
    new explicit selection of any kind naturally replaces whatever was
    there before;
  - a real clear-selection route and a small, truthful visibility
    indicator, resolved fresh on every render;
  - `services/auth.py`'s `log_out()` now also clears this state - a
    real gap found during this stage's own audit (sign-out previously
    only popped the three auth keys, leaving persisted selection
    reachable by a fresh sign-in in the same browser).

Run via:

    python -m unittest tests.test_ca1b_persistent_context -v
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

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceStore,
)
from services.conversation_interpreter import _resolve_anchor_object
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1b_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="ca1b_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="ca1b_owner", project_name="CA1B Context Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
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
            sess["username"] = "ca1b_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _discuss(self, client, text: str, project_id=None, **extra):
        data = {"text": text}
        data.update(extra)
        return client.post(f"/projects/{project_id or self.project_id}/workspace/discuss", data=data)

    def _register_requirement(self, identifier: str, project_id=None) -> str:
        project_id = project_id or self.project_id
        store = self._store()
        workspace = store.get(project_id)
        source_id = workspace.sources[0]["id"]
        store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier=identifier,
            text_reference=f"The system shall {identifier}.", created_by="ca1b_owner",
            registration_method="human_registered",
        )
        return next(r["id"] for r in store.get(project_id).requirements
                    if r["original_requirement_identifier"] == identifier)

    def _create_finding(self, statement: str, project_id=None) -> str:
        project_id = project_id or self.project_id
        store = self._store()
        workspace = store.get(project_id)
        case = store.create_case(workspace, title="A Case", objective="", created_by="ca1b_owner")
        workspace = store.get(project_id)
        source_id = workspace.sources[0]["id"]
        analysis = store.record_analysis(
            workspace, source_ids=[source_id], objective="test",
            engine_name="test-engine", engine_version="1",
            findings=[{"statement": statement, "machine_confidence": 0.7}],
            trigger=AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="ca1b_owner"),
            case_id=case["id"],
        )
        return analysis["finding_ids"][0]


class QueryParamSelectionTests(_BaseTestCase):
    def test_requirement_query_param_selects_and_persists(self):
        req_id = self._register_requirement("REQ-1")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")

        # Persistence: a later request with NO query param must still
        # resolve the same Requirement via conversation.
        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-1", body)

    def test_finding_query_param_selects_and_persists(self):
        finding_id = self._create_finding("The datum is inconsistent with Schedule 4.")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?finding={finding_id}")

        self._discuss(client, "what should i do with this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("datum is inconsistent", body)

    def test_source_selection_still_works(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        source_name = workspace.sources[0]["name"]
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?source={source_id}")
        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn(source_name, body)


class ContextIndicatorTests(_BaseTestCase):
    """CLAUDE-CA1D-COMPOSER-CONTEXT-LABEL-01: the indicator was
    repositioned from a standalone "Currently working with" div above
    the composer into a compact label embedded in the composer's own
    upper rule (data-ui-ref="chat.context-indicator" is unchanged, only
    its DOM position/text moved) - assertions updated to match the new
    text, not reverted to the old wording."""

    def test_indicator_shows_current_selection(self):
        req_id = self._register_requirement("REQ-IND")
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="chat.context-indicator"', body)
        self.assertIn("REQ-IND", body)

    def test_no_indicator_when_nothing_selected(self):
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="chat.context-indicator"', body)

    def test_clear_route_removes_the_indicator(self):
        req_id = self._register_requirement("REQ-CLR")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")
        resp = client.post(f"/projects/{self.project_id}/workspace/context/clear")
        self.assertEqual(resp.status_code, 302)
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="chat.context-indicator"', body)

    def test_stale_selection_never_shown_as_current(self):
        """A deleted/foreign persisted selection must never render as if
        it still existed (Section 2's own explicit requirement)."""
        client = self._client()
        with client.session_transaction() as sess:
            sess[f"selected_object:{self.project_id}"] = {"anchor_type": "requirement", "anchor_id": "not-a-real-id"}
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="chat.context-indicator"', body)

    def test_clear_button_uses_formaction_not_a_nested_form(self):
        """The label is now embedded inside the composer's own <form> -
        a nested <form> for Clear would be invalid HTML, so it must use
        formaction on a real <button> instead (still a genuine POST to
        the same, pre-existing clear-selection route)."""
        req_id = self._register_requirement("REQ-FA")
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}").get_data(as_text=True)
        self.assertIn("composer-context-clear", body)
        self.assertIn("workspace/context/clear", body)
        # Only ONE <form> should wrap the composer region - confirm the
        # clear control did not introduce a second, nested one.
        composer_start = body.index('data-ui-ref="chat.composer"')
        clear_idx = body.index("composer-context-clear", composer_start)
        between = body[composer_start:clear_idx]
        self.assertNotIn("<form", between)


class ExplicitReselectionTests(_BaseTestCase):
    def test_new_finding_selection_overrides_stale_requirement_selection(self):
        req_id = self._register_requirement("REQ-A")
        finding_id = self._create_finding("Finding B statement.")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")
        client.get(f"/projects/{self.project_id}/workspace?finding={finding_id}")

        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Finding B statement", body)
        self.assertNotIn("REQ-A", body)

    def test_source_to_requirement_transition(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        req_id = self._register_requirement("REQ-TRANS")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?source={source_id}")
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")

        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-TRANS", body)

    def test_fresh_anchor_overrides_stale_persisted_selection(self):
        """This message's own explicit anchor must always win over a
        stale persisted selection - Section 5's own explicit rule."""
        old_req_id = self._register_requirement("REQ-OLD")
        new_req_id = self._register_requirement("REQ-NEW")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={old_req_id}")

        self._discuss(client, "tell me about this", anchor_type="requirement", anchor_id=new_req_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-NEW", body)


class CrossProjectIsolationTests(_BaseTestCase):
    def test_requirement_selection_never_leaks_across_projects(self):
        req_id = self._register_requirement("REQ-A-ONLY")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")

        other_doc = self._ingest(owner="ca1b_owner", project_name="CA1B Other Project")
        self._discuss(client, "tell me about this", project_id=other_doc.project_id)
        body = client.get(f"/projects/{other_doc.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("don&#39;t have anything specific selected", body)
        self.assertNotIn("REQ-A-ONLY", body)

    def test_switching_back_restores_original_project_selection(self):
        """Per this stage's own persistence policy: per-project session
        keys are independent, so switching away and back restores the
        original Project's own selection unchanged - not cleared, not
        overwritten by the other Project's activity."""
        req_id = self._register_requirement("REQ-PERSIST")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")

        other_doc = self._ingest(owner="ca1b_owner", project_name="CA1B Second Project")
        other_finding_id = self._create_finding("Other project finding.", project_id=other_doc.project_id)
        client.get(f"/projects/{other_doc.project_id}/workspace?finding={other_finding_id}")

        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-PERSIST", body)

    def test_cross_project_requirement_id_rejected_via_interpreter(self):
        req_id = self._register_requirement("REQ-FOREIGN")
        other_doc = self._ingest(owner="ca1b_owner", project_name="CA1B Third Project")
        other_workspace = self._store().get(other_doc.project_id)

        obj_type, obj = _resolve_anchor_object(other_workspace, {"anchor_type": "requirement", "anchor_id": req_id})
        self.assertEqual(obj_type, "requirement")
        self.assertIsNone(obj)

    def test_cross_project_finding_id_rejected_via_interpreter(self):
        finding_id = self._create_finding("Belongs to project A only.")
        other_doc = self._ingest(owner="ca1b_owner", project_name="CA1B Fourth Project")
        other_workspace = self._store().get(other_doc.project_id)

        obj_type, obj = _resolve_anchor_object(other_workspace, {"anchor_type": "finding", "anchor_id": finding_id})
        self.assertEqual(obj_type, "finding")
        self.assertIsNone(obj)


class RefreshAndLogoutBoundaryTests(_BaseTestCase):
    def test_selection_survives_a_plain_refresh(self):
        req_id = self._register_requirement("REQ-REFRESH")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")
        # A "refresh" here is simply a second GET with no selection
        # param at all - the same test client/session, no new browser.
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("REQ-REFRESH", body)

    def test_logout_clears_persisted_selection(self):
        """Real gap found during this stage's own audit: log_out()
        previously popped only the three auth keys, leaving
        selected_object:{project_id} reachable by a fresh sign-in in the
        same browser session."""
        req_id = self._register_requirement("REQ-LOGOUT")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")

        client.get("/logout")
        with client.session_transaction() as sess:
            self.assertNotIn(f"selected_object:{self.project_id}", sess)


class NoSurpriseInvestigationTests(_BaseTestCase):
    def test_persisted_selection_alone_still_offers_investigation_when_no_case_open(self):
        req_id = self._register_requirement("REQ-OFFER")
        client = self._client()
        client.get(f"/projects/{self.project_id}/workspace?requirement={req_id}")
        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Start an Investigation from this", body)

    def test_persisted_selection_does_not_offer_investigation_inside_an_open_case(self):
        from services.conversation_interpreter import interpret_message

        req_id = self._register_requirement("REQ-NOOFFER")
        store = self._store()
        workspace = store.get(self.project_id)
        case = store.create_case(workspace, title="Open Case", objective="", created_by="ca1b_owner")

        result = interpret_message(
            text="tell me about this", workspace=workspace, case=case, store=store,
            artifacts_dir=self.tmp_dir, reviewer="ca1b_owner", focused_finding_id=None,
            triggering_message_id="msg-1", anchor=None,
            selected_object={"anchor_type": "requirement", "anchor_id": req_id},
        )
        self.assertIn("REQ-NOOFFER", result.reply_text)
        self.assertFalse(result.action_taken.startswith("needs_case:"))


if __name__ == "__main__":
    unittest.main()
