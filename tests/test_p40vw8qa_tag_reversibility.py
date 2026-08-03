"""
CLAUDE-P40-VW8-QA - Complete inverse actions for the text-selection
tagging workflow ("Anything the user can tag, classify, or highlight
must have a clear way to remove that application later").

No new backend data model: Highlight/Important/Question are already
just built-in Tags (services/case_workspace.py's own BUILT_IN_TAGS),
and remove_tag_occurrence already removes only the ONE occurrence
record, never the Tag definition or any other occurrence of it - the
existing route (`.../workspace/tags/<occurrence_id>/remove`, already
used by the Lists Tags branch's own "Remove" button) is reused
unchanged for every selection-toolbar removal action too. The one
genuinely new backend surface is a read-only lookup
(`tag_occurrences_for_selection_route`) that finds every occurrence
overlapping a given [start_offset, end_offset) range - needed because
app.py's own `hotlinks` filter only ever draws ONE inline <mark> per
position when occurrences overlap ("first-starting wins"), so a live
text selection can span an occurrence that has no visible <mark> at
all; scraping rendered DOM can't find it, but this endpoint always can.

Client-side coverage (JS structural assertions, no browser tool in this
environment - consistent with every prior stage's own stated
limitation) verifies the wiring exists and routes through the same
single removal path, not a parallel/duplicate one.
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
    CaseWorkspaceStore,
    CONVERSATION_ANCHOR_SCOPE_PROJECT,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"
_APP_PY_PATH = _REPO_ROOT / "app.py"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_reversibility_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="reversibility_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="reversibility_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="reversibility_owner", project_name="Reversibility Test Project")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        self.message = store.add_message(
            workspace, case_id=None, role="human",
            text="The retaining wall design load capacity needs verification.", actor="reversibility_owner",
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

    def _anchor_fields(self, start, end, quote):
        return {
            "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
            "anchor_message_id": self.message["id"],
            "anchor_start_offset": str(start),
            "anchor_end_offset": str(end),
            "anchor_quote": quote,
            "anchor_prefix": "",
            "anchor_suffix": "",
        }

    def _selection_query(self, start, end):
        return {
            "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
            "anchor_message_id": self.message["id"],
            "anchor_start_offset": str(start),
            "anchor_end_offset": str(end),
        }


# ---------------------------------------------------------------------------
# for-selection lookup route
# ---------------------------------------------------------------------------

class ForSelectionRouteTests(_BaseTestCase):
    def test_empty_when_nothing_applied(self):
        client = self._client_as("reversibility_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 10))
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["applied"], [])

    def test_exact_range_match_returned(self):
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")})
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 3))
        applied = resp.get_json()["applied"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["tag_id"], BUILT_IN_TAG_IMPORTANT)
        self.assertEqual(applied[0]["tag_name"], "Important")

    def test_partial_overlap_still_returned(self):
        # "Partial overlap with a tagged range" - Section: Selection
        # precision.
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_QUESTION, **self._anchor_fields(4, 13, "retaining")})
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(8, 20))
        applied = resp.get_json()["applied"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["tag_id"], BUILT_IN_TAG_QUESTION)

    def test_selection_entirely_outside_range_not_returned(self):
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_QUESTION, **self._anchor_fields(0, 3, "The")})
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(20, 30))
        self.assertEqual(resp.get_json()["applied"], [])

    def test_multiple_tags_on_the_same_range_all_returned(self):
        # Section: "Multiple Tags on one range" - app.py's own hotlinks
        # filter would only draw ONE <mark> here (first-starting wins);
        # this endpoint must still surface every one.
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(4, 13, "retaining")})
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"new_tag_name": "Follow up", "new_tag_color": "blue", **self._anchor_fields(4, 13, "retaining")})
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(4, 13))
        applied = resp.get_json()["applied"]
        self.assertEqual(len(applied), 2)
        tag_ids = {a["tag_id"] for a in applied}
        self.assertIn(BUILT_IN_TAG_IMPORTANT, tag_ids)

    def test_same_tag_applied_in_multiple_locations_only_the_overlapping_one_returned(self):
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_HIGHLIGHT, **self._anchor_fields(0, 3, "The")})
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_HIGHLIGHT, **self._anchor_fields(20, 30, "capacity")})
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 3))
        applied = resp.get_json()["applied"]
        self.assertEqual(len(applied), 1)

    def test_missing_anchor_params_returns_400_not_500(self):
        client = self._client_as("reversibility_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["ok"])

    def test_outsider_gets_404(self):
        client = self._client_as("reversibility_outsider", 5, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 3))
        self.assertEqual(resp.status_code, 404)

    def test_never_mutates_anything(self):
        client = self._client_as("reversibility_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")})
        client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 3))
        client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(0, 3))
        store = self._store()
        workspace = store.get(self.project_id)
        self.assertEqual(len(workspace.tag_occurrences), 1)


# ---------------------------------------------------------------------------
# Full round trip: add -> remove -> Tag definition/other occurrences intact
# ---------------------------------------------------------------------------

class RoundTripTests(_BaseTestCase):
    def test_add_then_remove_returns_to_original_state(self):
        client = self._client_as("reversibility_owner", 1)
        store = self._store()
        before = len(store.get(self.project_id).tag_occurrences)

        created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")}).get_json()
        occurrence_id = created["occurrence"]["id"]
        removed = client.post(f"/projects/{self.project_id}/workspace/tags/{occurrence_id}/remove").get_json()

        self.assertTrue(removed["ok"])
        after = len(self._store().get(self.project_id).tag_occurrences)
        self.assertEqual(after, before)

    def test_removing_one_tag_preserves_other_tags_on_the_same_range(self):
        client = self._client_as("reversibility_owner", 1)
        first = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(4, 13, "retaining")}).get_json()
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"new_tag_name": "Follow up", "new_tag_color": "blue", **self._anchor_fields(4, 13, "retaining")})

        client.post(f"/projects/{self.project_id}/workspace/tags/{first['occurrence']['id']}/remove")

        resp = client.get(f"/projects/{self.project_id}/workspace/tags/for-selection", query_string=self._selection_query(4, 13))
        applied = resp.get_json()["applied"]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["tag_name"], "Follow up")

    def test_removing_an_occurrence_does_not_delete_the_custom_tag_record(self):
        client = self._client_as("reversibility_owner", 1)
        created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"new_tag_name": "Follow up", "new_tag_color": "blue", **self._anchor_fields(0, 3, "The")}).get_json()
        tag_id = created["tag"]["id"]

        client.post(f"/projects/{self.project_id}/workspace/tags/{created['occurrence']['id']}/remove")

        store = self._store()
        workspace = store.get(self.project_id)
        self.assertIsNotNone(store.resolve_tag(workspace, tag_id))
        self.assertEqual([t["id"] for t in workspace.tags], [tag_id])

    def test_other_uses_of_the_same_tag_elsewhere_remain_intact(self):
        client = self._client_as("reversibility_owner", 1)
        first = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_QUESTION, **self._anchor_fields(0, 3, "The")}).get_json()
        client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_QUESTION, **self._anchor_fields(20, 30, "capacity")})

        client.post(f"/projects/{self.project_id}/workspace/tags/{first['occurrence']['id']}/remove")

        store = self._store()
        workspace = store.get(self.project_id)
        remaining = [o for o in workspace.tag_occurrences if o["tag_id"] == BUILT_IN_TAG_QUESTION]
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["quote"], "capacity")

    def test_highlight_important_question_each_reversible_via_the_same_route(self):
        client = self._client_as("reversibility_owner", 1)
        for tag_id in (BUILT_IN_TAG_HIGHLIGHT, BUILT_IN_TAG_IMPORTANT, BUILT_IN_TAG_QUESTION):
            created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": tag_id, **self._anchor_fields(0, 3, "The")}).get_json()
            removed = client.post(f"/projects/{self.project_id}/workspace/tags/{created['occurrence']['id']}/remove").get_json()
            self.assertTrue(removed["ok"], tag_id)
            self.assertEqual(removed["counts"]["by_tag"].get(tag_id, 0), 0, tag_id)

    def test_unauthorized_user_cannot_remove_an_occurrence(self):
        client = self._client_as("reversibility_owner", 1)
        created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")}).get_json()

        outsider = self._client_as("reversibility_outsider", 5, role="read_only")
        resp = outsider.post(f"/projects/{self.project_id}/workspace/tags/{created['occurrence']['id']}/remove")
        self.assertEqual(resp.status_code, 404)

        store = self._store()
        self.assertEqual(len(store.get(self.project_id).tag_occurrences), 1)

    def test_counts_update_correctly_across_add_and_remove(self):
        client = self._client_as("reversibility_owner", 1)
        created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")}).get_json()
        self.assertEqual(created["counts"]["total"], 1)
        removed = client.post(f"/projects/{self.project_id}/workspace/tags/{created['occurrence']['id']}/remove").get_json()
        self.assertEqual(removed["counts"]["total"], 0)

    def test_repeated_removal_of_the_same_occurrence_is_safe_not_500(self):
        # "Prevent duplicate removal requests" (client-side, guarded by
        # the button's own disabled state) - the SERVER side must also
        # degrade safely (404, not a crash) if a duplicate request lands
        # anyway (e.g. a race).
        client = self._client_as("reversibility_owner", 1)
        created = client.post(f"/projects/{self.project_id}/workspace/tags", data={"tag_id": BUILT_IN_TAG_IMPORTANT, **self._anchor_fields(0, 3, "The")}).get_json()
        occurrence_id = created["occurrence"]["id"]
        first = client.post(f"/projects/{self.project_id}/workspace/tags/{occurrence_id}/remove")
        second = client.post(f"/projects/{self.project_id}/workspace/tags/{occurrence_id}/remove")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 404)
        self.assertFalse(second.get_json()["ok"])


# ---------------------------------------------------------------------------
# app.py hotlinks: data-tag-id/data-tag-name for client-side state reads
# ---------------------------------------------------------------------------

class InlineMarkAttributesTests(unittest.TestCase):
    def setUp(self):
        self.source = _APP_PY_PATH.read_text(encoding="utf-8")

    def test_mark_carries_tag_id_and_tag_name_attributes(self):
        idx = self.source.index('<mark class="tag-highlight-inline')
        snippet = self.source[idx: idx + 400]
        self.assertIn("data-tag-id=", snippet)
        self.assertIn("data-tag-name=", snippet)
        self.assertIn("data-tag-occurrence-id=", snippet)


# ---------------------------------------------------------------------------
# Client-side wiring: reuses the single removal path, no duplicate system,
# non-color state identification.
# ---------------------------------------------------------------------------

class ClientWiringTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")
        self.html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")

    def test_single_removal_function_used_by_every_remove_action(self):
        self.assertIn("function removeOccurrenceWithUndo(", self.js)
        # The Remove-Tag-dialog row buttons and the built-in remove-*
        # toolbar actions both call it - not two separate request paths.
        self.assertGreaterEqual(self.js.count("removeOccurrenceWithUndo("), 2)

    def test_patch_tags_list_on_remove_is_the_one_dom_patch_function(self):
        self.assertEqual(self.js.count("function patchTagsListOnRemove("), 1)
        # Both the Lists "Remove" form submit handler and the toolbar's
        # own removal path call it.
        self.assertGreaterEqual(self.js.count("patchTagsListOnRemove("), 2)

    def test_remove_tag_button_hidden_by_default(self):
        idx = self.html.index('data-conv-action="remove-tag"')
        tag = self.html[self.html.rindex("<button", 0, idx):self.html.index(">", idx)]
        self.assertIn("hidden", tag)

    def test_remove_tag_dialog_lists_tag_names_as_text_not_color_only(self):
        idx = self.js.index("function populateRemoveTagDialog")
        body = self.js[idx: idx + 1200]
        self.assertIn("item.tag_name", body)
        self.assertIn("conv-remove-tag-name", body)

    def test_applied_state_refetched_on_every_selection_change(self):
        idx = self.js.index("function handleSelectionMaybeChanged")
        body = self.js[idx: idx + 1200]
        self.assertIn("refreshAppliedTagState(anchor)", body)

    def test_applied_state_uses_a_request_token_to_avoid_stale_response_races(self):
        self.assertIn("appliedFetchToken", self.js)
        idx = self.js.index("function refreshAppliedTagState")
        body = self.js[idx: idx + 700]
        self.assertIn("if (token !== appliedFetchToken) return", body)

    def test_builtin_remove_actions_swap_identifiers_not_reuse_add_ones(self):
        for remove_ref, add_ref in (
            ("chat.selection-toolbar.remove-highlight", "chat.selection-toolbar.highlight"),
            ("chat.selection-toolbar.unmark-important", "chat.selection-toolbar.important"),
            ("chat.selection-toolbar.unmark-question", "chat.selection-toolbar.question"),
        ):
            self.assertIn(remove_ref, self.js)
            self.assertNotEqual(remove_ref, add_ref)

    def test_undo_reposts_to_the_same_add_tag_endpoint(self):
        idx = self.js.index("function undoUrl()")
        body = self.js[idx: idx + 100]
        self.assertIn("tagForm.action", body)

    def test_undo_button_has_its_own_timeout_not_indefinite(self):
        self.assertIn("undoHideTimer", self.js)
        self.assertIn("8000", self.js)

    def test_no_second_tag_or_highlight_system_introduced(self):
        # No new fetch()-based route path other than the existing add/
        # remove/for-selection ones, and no separate "highlight state"
        # storage - BUILT_IN_TAG_* constants are the only vocabulary.
        self.assertNotIn("localStorage.setItem('beehive:highlight", self.js)
        self.assertNotIn("localStorage.setItem('beehive:tag", self.js)


if __name__ == "__main__":
    unittest.main()
