"""
CLAUDE-P40-VW7 - Conversation Text Selection, OneNote-Style Tags, and
Tasks.

Bounded, project-scoped authorization (see this stage's own comment in
routes/workspace.py and services/case_workspace.py) for a OneNote-like
selection toolbar on Project Conversation text, one-click built-in
Important/Question/Highlight tags, a small custom-tag color picker, real
persisted Tasks, and two new Lists branches (Tasks/Tags) that update
live via fetch() without a full reload.

Coverage here is everything genuinely automatable from this side (store
methods, route authorization/JSON contracts/CSRF-equivalent behavior,
template anchor/markup structure, sanitization, cross-project
isolation, "Source unavailable" fallback) - no browser-automation tool
is connected in this environment (consistent with every prior VW stage,
see e.g. test_p40vw5_signin_gateway_isolation.py's own note), so the
selection-toolbar's actual client-side interaction (positioning,
keyboard nav, live DOM patching) is exercised for markup/JSON-contract
correctness only, not pixel/interaction-level; the real-browser
walkthrough this stage's own prompt asks for is reported as a stated
limitation, not fabricated.

Conversation messages used as anchor targets are created directly via
CaseWorkspaceStore.add_message (a pure data write, no LLM call) rather
than through the post_message/quick_start routes, which route through
services.conversation_interpreter.interpret_message and, depending on
message content, real grounded-Q&A/Anthropic calls
(services/project_qa.py, services/requirement_investigation.py) - the
same class of external-call risk CLAUDE.md's hermetic-test rule warns
about for ingest_upload/BHiveParser.parse, applied here to the
conversation pipeline instead. Ingestion itself still spies on
BHiveParser.parse per that same rule.
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
    BUILT_IN_TAG_HIGHLIGHT,
    BUILT_IN_TAG_IMPORTANT,
    BUILT_IN_TAG_QUESTION,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    CONVERSATION_ANCHOR_SCOPE_CASE,
    CONVERSATION_ANCHOR_SCOPE_GUIDANCE,
    CONVERSATION_ANCHOR_SCOPE_PROJECT,
    CONVERSATION_GUIDANCE_PROJECT_INTRO,
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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw7_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7_granted_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add(User(username="vw7_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="vw7_owner", project_name="Riverside Terminal VW7 Workspace")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="vw7_granted_reviewer", actor="vw7_owner", actor_role="admin")

        workspace = store.get(self.project_id)
        self.case = store.create_case(workspace, title="Foundation Review", objective="", created_by="vw7_owner")
        workspace = store.get(self.project_id)
        self.case_message = store.add_message(
            workspace, case_id=self.case["id"], role="human",
            text="The footing schedule references datum NAVD88 on sheet S-2.", actor="vw7_owner",
        )
        workspace = store.get(self.project_id)
        self.project_message = store.add_message(
            workspace, case_id=None, role="human",
            text="What is the retaining wall's design load capacity?", actor="vw7_owner",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _case_anchor_fields(self, quote="datum NAVD88", start=0, end=11):
        return {
            "anchor_scope": CONVERSATION_ANCHOR_SCOPE_CASE,
            "anchor_case_id": self.case["id"],
            "anchor_message_id": self.case_message["id"],
            "anchor_start_offset": str(start),
            "anchor_end_offset": str(end),
            "anchor_quote": quote,
            "anchor_prefix": "",
            "anchor_suffix": "",
        }

    def _project_anchor_fields(self, quote="design load", start=0, end=11):
        return {
            "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
            "anchor_message_id": self.project_message["id"],
            "anchor_start_offset": str(start),
            "anchor_end_offset": str(end),
            "anchor_quote": quote,
            "anchor_prefix": "",
            "anchor_suffix": "",
        }

    def _guidance_anchor_fields(self, quote="Talk to the Project", start=0, end=19):
        return {
            "anchor_scope": CONVERSATION_ANCHOR_SCOPE_GUIDANCE,
            "anchor_guidance_key": CONVERSATION_GUIDANCE_PROJECT_INTRO,
            "anchor_start_offset": str(start),
            "anchor_end_offset": str(end),
            "anchor_quote": quote,
            "anchor_prefix": "",
            "anchor_suffix": "",
        }

    def _lists_html(self, body: str) -> str:
        start = body.index('id="launcher-panel"')
        end = body.index('id="workspace-toolbox-panel"') if 'id="workspace-toolbox-panel"' in body else body.index("</body>")
        return body[start:end]


# ---------------------------------------------------------------------------
# Store layer: tag normalization/dedup, anchor validation, task lifecycle.
# ---------------------------------------------------------------------------

class StoreLayerTests(_BaseTestCase):
    def test_normalize_tag_name_collapses_whitespace_and_casefolds(self):
        store = self._store()
        self.assertEqual(store._normalize_tag_name("  Follow   Up  "), "follow up")

    def test_create_custom_tag_is_idempotent_by_normalized_name(self):
        store = self._store()
        workspace = store.get(self.project_id)
        first = store.create_custom_tag(workspace, "Follow up", "blue", actor="vw7_owner")
        workspace = store.get(self.project_id)
        second = store.create_custom_tag(workspace, "  follow   UP ", "green", actor="vw7_owner")
        self.assertEqual(first["id"], second["id"])
        workspace = store.get(self.project_id)
        self.assertEqual(len(workspace.tags), 1)

    def test_create_custom_tag_rejects_empty_name(self):
        store = self._store()
        workspace = store.get(self.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.create_custom_tag(workspace, "   ", "blue", actor="vw7_owner")

    def test_create_custom_tag_rejects_unknown_color(self):
        store = self._store()
        workspace = store.get(self.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.create_custom_tag(workspace, "Follow up", "chartreuse", actor="vw7_owner")

    def test_create_custom_tag_collapses_into_matching_builtin(self):
        store = self._store()
        workspace = store.get(self.project_id)
        tag = store.create_custom_tag(workspace, "important", "blue", actor="vw7_owner")
        self.assertEqual(tag["id"], BUILT_IN_TAG_IMPORTANT)
        workspace = store.get(self.project_id)
        self.assertEqual(workspace.tags, [])

    def test_add_tag_occurrence_with_builtin_tag(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_CASE, "case_id": self.case["id"],
            "message_id": self.case_message["id"], "start_offset": 0, "end_offset": 5,
            "quote": "datum",
        }
        occurrence = store.add_tag_occurrence(workspace, BUILT_IN_TAG_QUESTION, anchor, actor="vw7_owner")
        self.assertEqual(occurrence["tag_id"], BUILT_IN_TAG_QUESTION)
        self.assertEqual(occurrence["quote"], "datum")

    def test_add_tag_occurrence_rejects_unknown_tag(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_CASE, "case_id": self.case["id"],
            "message_id": self.case_message["id"], "start_offset": 0, "end_offset": 5,
            "quote": "datum",
        }
        with self.assertRaises(CaseWorkspaceError):
            store.add_tag_occurrence(workspace, "no-such-tag", anchor, actor="vw7_owner")

    def test_validate_source_anchor_rejects_empty_quote(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_CASE, "case_id": self.case["id"],
            "message_id": self.case_message["id"], "start_offset": 0, "end_offset": 5, "quote": "   ",
        }
        with self.assertRaises(CaseWorkspaceError):
            store._validate_source_anchor(workspace, anchor)

    def test_validate_source_anchor_rejects_bad_offsets(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_CASE, "case_id": self.case["id"],
            "message_id": self.case_message["id"], "start_offset": 10, "end_offset": 5, "quote": "datum",
        }
        with self.assertRaises(CaseWorkspaceError):
            store._validate_source_anchor(workspace, anchor)

    def test_validate_source_anchor_rejects_nonexistent_message(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_CASE, "case_id": self.case["id"],
            "message_id": "not-a-real-message-id", "start_offset": 0, "end_offset": 5, "quote": "datum",
        }
        with self.assertRaises(CaseWorkspaceError):
            store._validate_source_anchor(workspace, anchor)

    def test_validate_source_anchor_accepts_guidance_scope(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_GUIDANCE, "guidance_key": CONVERSATION_GUIDANCE_PROJECT_INTRO,
            "start_offset": 0, "end_offset": 4, "quote": "Talk",
        }
        validated = store._validate_source_anchor(workspace, anchor)
        self.assertEqual(validated["scope"], CONVERSATION_ANCHOR_SCOPE_GUIDANCE)

    def test_validate_source_anchor_rejects_unknown_guidance_key(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_GUIDANCE, "guidance_key": "some-other-key",
            "start_offset": 0, "end_offset": 4, "quote": "Talk",
        }
        with self.assertRaises(CaseWorkspaceError):
            store._validate_source_anchor(workspace, anchor)

    def test_resolve_conversation_anchor_false_for_fabricated_message(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {"scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": "not-real"}
        self.assertFalse(store.resolve_conversation_anchor(workspace, anchor))

    def test_resolve_conversation_anchor_true_for_real_message(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {"scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"]}
        self.assertTrue(store.resolve_conversation_anchor(workspace, anchor))

    def test_remove_tag_occurrence_does_not_touch_source_message_text(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        occurrence = store.add_tag_occurrence(workspace, BUILT_IN_TAG_HIGHLIGHT, anchor, actor="vw7_owner")
        workspace = store.get(self.project_id)
        store.remove_tag_occurrence(workspace, occurrence["id"])
        workspace = store.get(self.project_id)
        self.assertEqual(workspace.tag_occurrences, [])
        message = store._find(workspace.project_conversation, self.project_message["id"])
        self.assertEqual(message["text"], "What is the retaining wall's design load capacity?")

    def test_create_task_truncates_long_titles(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        task = store.create_task(workspace, anchor, title="x" * 250, actor="vw7_owner")
        self.assertEqual(len(task["title"]), 200)
        self.assertTrue(task["title"].endswith("..."))

    def test_create_task_rejects_empty_title(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        with self.assertRaises(CaseWorkspaceError):
            store.create_task(workspace, anchor, title="   ", actor="vw7_owner")

    def test_complete_task_then_reopen_task_round_trip(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        task = store.create_task(workspace, anchor, title="Check load capacity", actor="vw7_owner")
        workspace = store.get(self.project_id)
        completed = store.complete_task(workspace, task["id"], actor="vw7_owner")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["completed_by"], "vw7_owner")
        workspace = store.get(self.project_id)
        reopened = store.reopen_task(workspace, task["id"], actor="vw7_owner")
        self.assertEqual(reopened["status"], "open")
        self.assertEqual(reopened["reopened_by"], "vw7_owner")

    def test_complete_task_twice_raises(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        task = store.create_task(workspace, anchor, title="Check load capacity", actor="vw7_owner")
        workspace = store.get(self.project_id)
        store.complete_task(workspace, task["id"], actor="vw7_owner")
        workspace = store.get(self.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.complete_task(workspace, task["id"], actor="vw7_owner")


# ---------------------------------------------------------------------------
# Route authorization: same rules as the source conversation; ID tampering
# across projects is rejected exactly like every other workspace route.
# ---------------------------------------------------------------------------

class RouteAuthorizationTests(_BaseTestCase):
    def test_outsider_gets_404_on_add_tag_occurrence_route(self):
        client = self._client_as("vw7_outsider", 5, role="read_only")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 404)

    def test_outsider_gets_404_on_create_task_route(self):
        client = self._client_as("vw7_outsider", 5, role="read_only")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check this", **self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 404)

    def test_outsider_gets_404_on_remove_tag_occurrence_route(self):
        client = self._client_as("vw7_outsider", 5, role="read_only")
        resp = client.post(f"/projects/{self.project_id}/workspace/tags/anything/remove")
        self.assertEqual(resp.status_code, 404)

    def test_outsider_gets_404_on_complete_task_route(self):
        client = self._client_as("vw7_outsider", 5, role="read_only")
        resp = client.post(f"/projects/{self.project_id}/workspace/tasks/anything/complete")
        self.assertEqual(resp.status_code, 404)

    def test_granted_reviewer_can_add_tag_and_create_task(self):
        # Section 8: "the same Project owner, allow-list, and admin-bypass
        # rules governing the source conversation must govern its Tasks
        # and Tags" - a granted (non-owner, non-admin) reviewer already
        # has conversation access, so they can use Tags/Tasks too.
        client = self._client_as("vw7_granted_reviewer", 3, role="read_only")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_HIGHLIGHT, **self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])

    def test_occurrence_id_from_one_project_is_404_via_a_different_projects_route(self):
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        occurrence = store.add_tag_occurrence(workspace, BUILT_IN_TAG_IMPORTANT, anchor, actor="vw7_owner")

        other_doc = self._ingest(owner="vw7_owner", project_name="Second VW7 Project")
        client = self._client_as("vw7_owner", 1)
        resp = client.post(f"/projects/{other_doc.project_id}/workspace/tags/{occurrence['id']}/remove")
        self.assertEqual(resp.status_code, 404)
        # And the original occurrence is untouched.
        workspace = store.get(self.project_id)
        self.assertEqual(len(workspace.tag_occurrences), 1)


# ---------------------------------------------------------------------------
# Route behavior: JSON contract for the fetch()-driven routes, redirect
# contract for complete/reopen, 400 (not 500) on an invalid anchor.
# ---------------------------------------------------------------------------

class RouteBehaviorTests(_BaseTestCase):
    def test_add_tag_occurrence_route_returns_json_with_counts(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._case_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["tag"]["id"], BUILT_IN_TAG_IMPORTANT)
        self.assertEqual(data["counts"]["total"], 1)
        self.assertEqual(data["counts"]["by_tag"][BUILT_IN_TAG_IMPORTANT], 1)

    def test_add_tag_occurrence_route_creates_custom_tag_when_new_tag_name_given(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"new_tag_name": "Follow up", "new_tag_color": "blue", **self._project_anchor_fields()},
        )
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["tag"]["name"], "Follow up")
        self.assertEqual(data["tag"]["color"], "blue")

    def test_add_tag_occurrence_route_reuses_existing_tag_on_duplicate_name(self):
        client = self._client_as("vw7_owner", 1)
        first = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"new_tag_name": "Follow up", "new_tag_color": "blue", **self._project_anchor_fields()},
        ).get_json()
        second = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"new_tag_name": "follow up", "new_tag_color": "red", **self._case_anchor_fields()},
        ).get_json()
        self.assertEqual(first["tag"]["id"], second["tag"]["id"])
        self.assertEqual(second["counts"]["total"], 2)

    def test_add_tag_occurrence_route_missing_tag_returns_400(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={**self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["ok"])

    def test_add_tag_occurrence_route_invalid_anchor_returns_400_not_500(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "tag_id": BUILT_IN_TAG_IMPORTANT,
                "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
                "anchor_message_id": "not-a-real-message",
                "anchor_start_offset": "0", "anchor_end_offset": "5", "anchor_quote": "hello",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["ok"])

    def test_remove_tag_occurrence_route_updates_counts(self):
        client = self._client_as("vw7_owner", 1)
        created = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_QUESTION, **self._project_anchor_fields()},
        ).get_json()
        occurrence_id = created["occurrence"]["id"]
        resp = client.post(f"/projects/{self.project_id}/workspace/tags/{occurrence_id}/remove")
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["counts"]["total"], 0)

    def test_remove_nonexistent_tag_occurrence_returns_404(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(f"/projects/{self.project_id}/workspace/tags/not-real/remove")
        self.assertEqual(resp.status_code, 404)

    def test_create_task_route_returns_json_with_task_and_counts(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["task"]["title"], "Check load capacity")
        self.assertEqual(data["task"]["status"], "open")
        self.assertEqual(data["counts"], {"total": 1, "open": 1, "completed": 0})

    def test_create_task_route_rejects_empty_title(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "   ", **self._project_anchor_fields()},
        )
        self.assertEqual(resp.status_code, 400)

    def test_complete_task_route_redirects_and_updates_status(self):
        client = self._client_as("vw7_owner", 1)
        created = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        ).get_json()
        task_id = created["task"]["id"]
        resp = client.post(f"/projects/{self.project_id}/workspace/tasks/{task_id}/complete")
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        task = self._store()._find(workspace.tasks, task_id)
        self.assertEqual(task["status"], "completed")

    def test_reopen_task_route_redirects_and_updates_status(self):
        client = self._client_as("vw7_owner", 1)
        created = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        ).get_json()
        task_id = created["task"]["id"]
        client.post(f"/projects/{self.project_id}/workspace/tasks/{task_id}/complete")
        resp = client.post(f"/projects/{self.project_id}/workspace/tasks/{task_id}/reopen")
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        task = self._store()._find(workspace.tasks, task_id)
        self.assertEqual(task["status"], "open")

    def test_guidance_scope_anchor_creates_a_valid_occurrence(self):
        client = self._client_as("vw7_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_HIGHLIGHT, **self._guidance_anchor_fields()},
        )
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["occurrence"]["source_anchor"]["scope"], CONVERSATION_ANCHOR_SCOPE_GUIDANCE)


# ---------------------------------------------------------------------------
# Template rendering: message/guidance anchors, selection toolbar/dialogs,
# Lists Tasks/Tags branches and their counts, navigate-to-source URLs.
# ---------------------------------------------------------------------------

class TemplateRenderingTests(_BaseTestCase):
    def test_case_message_carries_stable_anchor_attributes(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        self.assertIn(f'id="message-{self.case_message["id"]}"', body)
        self.assertIn(f'data-message-id="{self.case_message["id"]}"', body)
        self.assertIn(f'data-anchor-scope="case" data-anchor-case-id="{self.case["id"]}"', body)
        self.assertIn('class="conv-message-text" data-message-text', body)

    def test_project_message_carries_stable_anchor_attributes(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(f'id="message-{self.project_message["id"]}"', body)
        self.assertIn('data-anchor-scope="project"', body)

    def test_guidance_paragraph_carries_stable_anchor(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="project-conversation-guidance"', body)
        self.assertIn(f'data-guidance-key="{CONVERSATION_GUIDANCE_PROJECT_INTRO}"', body)

    def test_selection_toolbar_and_dialogs_render_with_expected_actions(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="conv-selection-toolbar"', body)
        for action in ("tag", "task", "highlight", "important", "question", "copy"):
            self.assertIn(f'data-conv-action="{action}"', body)
        self.assertIn('id="conv-tag-dialog"', body)
        self.assertIn('id="conv-task-dialog"', body)
        self.assertIn(f'action="/projects/{self.project_id}/workspace/tags"', body)
        self.assertIn(f'action="/projects/{self.project_id}/workspace/tasks"', body)

    def test_lists_tasks_and_tags_branches_absent_when_empty_but_present(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn("Tasks", lists)
        self.assertIn("Tags", lists)
        self.assertIn('id="lists-tasks-count">0<', lists)
        self.assertIn('id="lists-tags-count">0<', lists)
        self.assertIn("No open Tasks.", lists)
        self.assertIn("No Tags yet.", lists)

    def test_lists_shows_task_with_open_count_and_source_link(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn('id="lists-tasks-count">1<', lists)
        self.assertIn('id="lists-tasks-open-count">1<', lists)
        self.assertIn('id="lists-tasks-completed-count">0<', lists)
        self.assertIn("Check load capacity", lists)
        self.assertIn(f"/projects/{self.project_id}/workspace#conv-source-{self.project_message['id']}", lists)

    def test_lists_shows_completed_task_in_completed_group(self):
        client = self._client_as("vw7_owner", 1)
        created = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        ).get_json()
        client.post(f"/projects/{self.project_id}/workspace/tasks/{created['task']['id']}/complete")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn('id="lists-tasks-open-count">0<', lists)
        self.assertIn('id="lists-tasks-completed-count">1<', lists)
        self.assertIn(f'action="/projects/{self.project_id}/workspace/tasks/{created["task"]["id"]}/reopen"', lists)

    def test_lists_shows_tag_group_with_swatch_and_source_link(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._case_anchor_fields()},
        )
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn('id="lists-tags-count">1<', lists)
        self.assertIn('data-tag-group="built-in:important"', lists)
        self.assertIn("conv-tag-color-red", lists)  # Important's built-in color
        self.assertIn(f"/projects/{self.project_id}/workspace?case={self.case['id']}#conv-source-{self.case_message['id']}", lists)

    def test_guidance_tag_source_url_uses_the_guidance_fragment(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_HIGHLIGHT, **self._guidance_anchor_fields()},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn(f"/projects/{self.project_id}/workspace#conv-source-guidance", lists)

    def test_source_unavailable_fallback_when_anchor_cannot_resolve(self):
        # Simulate data drift (the write path itself can never create an
        # unresolvable anchor - _validate_source_anchor blocks that) by
        # directly editing the persisted record, then confirming the
        # READ side (resolve_conversation_anchor / show_workspace) shows
        # "Source unavailable" instead of a broken or wrong-navigating
        # link, per Section 4's own explicit requirement.
        store = self._store()
        workspace = store.get(self.project_id)
        anchor = {
            "scope": CONVERSATION_ANCHOR_SCOPE_PROJECT, "message_id": self.project_message["id"],
            "start_offset": 0, "end_offset": 11, "quote": "design load",
        }
        task = store.create_task(workspace, anchor, title="Orphaned task", actor="vw7_owner")
        workspace = store.get(self.project_id)
        stored_task = store._find(workspace.tasks, task["id"])
        stored_task["source_anchor"]["message_id"] = "deleted-message-id"
        store.save(workspace)

        client = self._client_as("vw7_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn("Orphaned task", lists)
        self.assertIn("Source unavailable", lists)


# ---------------------------------------------------------------------------
# Sanitization: tag names, task titles, and quotations can never become
# executable HTML/script in the rendered Lists panel.
# ---------------------------------------------------------------------------

class SanitizationTests(_BaseTestCase):
    def test_custom_tag_name_with_html_is_escaped(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"new_tag_name": "<script>alert(1)</script>", "new_tag_color": "blue", **self._project_anchor_fields()},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)

    def test_task_title_with_html_is_escaped(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "<img src=x onerror=alert(1)>", **self._project_anchor_fields()},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("<img src=x onerror=alert(1)>", body)

    def test_tag_occurrence_quote_with_html_is_escaped(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "tag_id": BUILT_IN_TAG_IMPORTANT,
                "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
                "anchor_message_id": self.project_message["id"],
                "anchor_start_offset": "0", "anchor_end_offset": "11",
                "anchor_quote": "<b onmouseover=alert(1)>design</b>",
            },
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("<b onmouseover=alert(1)>design</b>", body)


# ---------------------------------------------------------------------------
# Preservation: the workspace page still renders correctly with Tags/Tasks
# present, and a plain Investigation-scoped URL (Stable URL Restoration)
# still resolves. Full VW1-VW6 regression coverage lives in its own
# existing files (see test_p40vw1..test_p40vw6) and is not duplicated
# here - proven instead by the full suite run this stage's own prompt
# requires before committing.
# ---------------------------------------------------------------------------

class PreservationTests(_BaseTestCase):
    def test_workspace_page_still_200_with_tags_and_tasks_present(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._project_anchor_fields()},
        )
        client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={"title": "Check load capacity", **self._project_anchor_fields()},
        )
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)

    def test_stable_case_url_still_resolves_with_tags_present(self):
        client = self._client_as("vw7_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={"tag_id": BUILT_IN_TAG_QUESTION, **self._case_anchor_fields()},
        )
        resp = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.case["title"], resp.get_data(as_text=True))

    def test_sign_in_page_has_no_tasks_or_tags_markup(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn("conv-selection-toolbar", body)
        self.assertNotIn("lists-tasks-branch", body)
        self.assertNotIn("lists-tags-branch", body)

    def test_gateway_page_has_no_tasks_or_tags_markup(self):
        client = self._client_as("vw7_owner", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("conv-selection-toolbar", body)
        self.assertNotIn("lists-tasks-branch", body)
        self.assertNotIn("lists-tags-branch", body)


if __name__ == "__main__":
    unittest.main()
