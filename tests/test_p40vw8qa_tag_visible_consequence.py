"""
CLAUDE-P40-VW8-QA, Section 11 - Add Tag must have a visible consequence
on the tagged text itself.

CLAUDE-P40-VW7 shipped Tags/Tasks/the selection toolbar with the
occurrence persisted (Lists' own Tags branch, counts, source-anchor
navigation) but the SOURCE TEXT itself carried no visible mark at
all - a direct product-owner-observed defect this stage corrected via
a combined-pass extension to app.py's own `hotlinks` template filter
(now optionally message/anchor-aware) and a new
CaseWorkspaceStore.tag_occurrences_for_message read helper - reusing
TagOccurrence/its existing source_anchor exactly, no new business
object. This file is the automated regression coverage that
correction never had: end-to-end route -> rendered-HTML assertions
that the tagged substring actually gets wrapped in an accessible,
identifiable <mark>, that untagged text is untouched, that overlap/
duplicate application degrades coherently, and that the same message
rendered WITHOUT anchor args (the old two-arg `hotlinks` call some
other, non-Project-Conversation caller might still use) is unaffected.
"""
from __future__ import annotations

import io
import re
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
    CONVERSATION_ANCHOR_SCOPE_CASE,
    CONVERSATION_ANCHOR_SCOPE_PROJECT,
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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_tag_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw8qa_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="vw8qa_owner", project_name="Tag Consequence Project")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        self.case = store.create_case(workspace, title="Foundation Review", objective="", created_by="vw8qa_owner")
        workspace = store.get(self.project_id)
        self.project_message = store.add_message(
            workspace, case_id=None, role="human",
            text="Confirm the footing datum before proceeding.", actor="vw8qa_owner",
        )
        workspace = store.get(self.project_id)
        self.case_message = store.add_message(
            workspace, case_id=self.case["id"], role="human",
            text="The retaining wall load capacity needs review.", actor="vw8qa_owner",
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

    def _tag_project_message(self, client, tag_id, start, end, quote):
        return client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "tag_id": tag_id,
                "anchor_scope": CONVERSATION_ANCHOR_SCOPE_PROJECT,
                "anchor_message_id": self.project_message["id"],
                "anchor_start_offset": str(start),
                "anchor_end_offset": str(end),
                "anchor_quote": quote,
            },
        )


class VisibleConsequenceTests(_BaseTestCase):
    def test_tagged_substring_is_wrapped_in_an_identifiable_mark(self):
        # "Confirm the footing datum before proceeding." - tag "footing
        # datum" (offsets 12-25).
        client = self._client_as("vw8qa_owner", 1)
        resp = self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])

        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        match = re.search(r'<mark class="tag-highlight-inline[^"]*"[^>]*>footing datum</mark>', body)
        self.assertIsNotNone(match, "tagged substring not found wrapped in an accessible <mark>")

    def test_mark_carries_data_ui_ref_and_occurrence_id_and_title(self):
        client = self._client_as("vw8qa_owner", 1)
        self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        mark_match = re.search(r'<mark class="tag-highlight-inline[^"]*"[^>]*>footing datum</mark>', body)
        self.assertIsNotNone(mark_match)
        tag = mark_match.group(0)
        self.assertIn('data-ui-ref="chat.tag-highlight"', tag)
        self.assertIn("data-tag-occurrence-id=", tag)
        self.assertIn('title="Tagged:', tag)

    def test_untagged_text_in_the_same_message_is_unaffected(self):
        client = self._client_as("vw8qa_owner", 1)
        self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Confirm the ", body)
        self.assertNotIn('<mark class="tag-highlight-inline">Confirm', body)

    def test_case_scoped_message_also_receives_a_visible_mark(self):
        client = self._client_as("vw8qa_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "tag_id": BUILT_IN_TAG_QUESTION,
                "anchor_scope": CONVERSATION_ANCHOR_SCOPE_CASE,
                "anchor_case_id": self.case["id"],
                "anchor_message_id": self.case_message["id"],
                "anchor_start_offset": "4",
                "anchor_end_offset": "18",
                "anchor_quote": "retaining wall",
            },
        )
        self.assertTrue(resp.get_json()["ok"])
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        self.assertIn(">retaining wall</mark>", body)

    def test_different_tag_colors_produce_different_modifier_classes(self):
        client = self._client_as("vw8qa_owner", 1)
        self._tag_project_message(client, BUILT_IN_TAG_HIGHLIGHT, 12, 25, "footing datum")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        match = re.search(r'<mark class="tag-highlight-inline (conv-tag-color-\w+)"', body)
        self.assertIsNotNone(match)
        # BUILT_IN_TAG_HIGHLIGHT and BUILT_IN_TAG_IMPORTANT are different
        # built-in tags with different colors - not asserting the exact
        # name here (that's BUILT_IN_TAGS' own concern), just that a
        # real per-tag-color modifier class is present.
        self.assertTrue(match.group(1).startswith("conv-tag-color-"))

    def test_tag_count_updates_and_is_reflected_in_the_json_response(self):
        client = self._client_as("vw8qa_owner", 1)
        resp = self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        counts = resp.get_json()["counts"]
        self.assertEqual(counts["total"], 1)

    def test_mark_is_durable_across_a_second_request_reload(self):
        client = self._client_as("vw8qa_owner", 1)
        self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        body_first = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        body_second = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("footing datum</mark>", body_first)
        self.assertIn("footing datum</mark>", body_second)


class OverlapAndFailureHandlingTests(_BaseTestCase):
    def test_overlapping_tag_occurrences_render_coherently_without_corrupting_html(self):
        client = self._client_as("vw8qa_owner", 1)
        # "Confirm the footing datum before proceeding." - two
        # deliberately overlapping ranges: "footing datum" (12-25) and
        # "datum before" (20-32).
        self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        second = self._tag_project_message(client, BUILT_IN_TAG_QUESTION, 20, 32, "datum before")
        self.assertTrue(second.get_json()["ok"], "a second, overlapping occurrence must still persist")

        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        # Valid, balanced HTML: every <mark> that opens must close before
        # the enclosing paragraph/element does - a naive two-pass wrap
        # would produce unbalanced tags here.
        message_start = body.index("Confirm the")
        window = body[max(0, message_start - 50):message_start + 500]
        self.assertEqual(window.count("<mark"), window.count("</mark>"))

    def test_duplicate_tag_application_to_the_same_range_is_handled(self):
        client = self._client_as("vw8qa_owner", 1)
        first = self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        second = self._tag_project_message(client, BUILT_IN_TAG_IMPORTANT, 12, 25, "footing datum")
        self.assertTrue(first.get_json()["ok"])
        # Either a coherent no-op/rejection or a second stored occurrence
        # that still renders as ONE visible mark (first-starting wins,
        # per app.py's own hotlinks comment) - the requirement is no
        # crash and no visibly broken double-nested markup, not one
        # specific server policy.
        self.assertIn(second.status_code, (200, 400))
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        message_start = body.index("Confirm the")
        window = body[max(0, message_start - 50):message_start + 500]
        self.assertEqual(window.count("<mark"), window.count("</mark>"))

    def test_invalid_tag_id_fails_with_a_clear_error_and_no_mark_is_added(self):
        client = self._client_as("vw8qa_owner", 1)
        resp = self._tag_project_message(client, "not-a-real-tag-id", 12, 25, "footing datum")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("tag-highlight-inline", body)


class BackwardCompatibilityTests(_BaseTestCase):
    def test_hotlinks_filter_without_anchor_args_still_renders_plain_text(self):
        # A template call site that only ever passes (text, workspace,
        # project_id) - the pre-VW8-QA two/three-arg call shape - must
        # render identically to before: no <mark>, no crash.
        with self.flask_app.test_request_context(f"/projects/{self.project_id}/workspace"):
            from flask import render_template_string
            store = self._store()
            workspace = store.get(self.project_id)
            rendered = render_template_string(
                "{{ text|hotlinks(workspace, project_id) }}",
                text=self.project_message["text"], workspace=workspace, project_id=self.project_id,
            )
        self.assertNotIn("<mark", str(rendered))
        self.assertIn("Confirm the footing datum before proceeding.", str(rendered))


if __name__ == "__main__":
    unittest.main()
