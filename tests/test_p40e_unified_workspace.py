"""
CLAUDE-P40-E - Unified Document Workspace, Compact Conversation Dock,
and Reviewer-Governed Pattern Suggestions.

Covers what was actually built:
  - the second, permanently-visible navigation column
    (.workspace-pane-nav as its own grid track) is gone - its content
    now stacks with the active work inside one shared "workspace"
    grid-area, and a compact, counted summary of it lives in the
    unified left rail (templates/base.html), only for an authorized
    project;
  - the visible heading is "Workspace", not "Case Workspace";
  - ?source=<id> opens a document/drawing inside the Workspace pane,
    resolved only against this project's own already-authorized
    Sources;
  - the conversation dock (one composer, real draft/scroll-position
    data attributes for the client-side preservation script);
  - services.case_workspace.resolve_conversation_hotlinks and the
    `hotlinks` Jinja filter - exact, governed-identity-only matches,
    safely escaped;
  - the authentication shell (P40-D1) and legacy-record persistence
    boundary (P40-D2) remain intact;
  - Sections F/H (conversation thread lifecycle, saved patterns) were
    deliberately left specified-but-unbuilt - these tests confirm the
    honest boundary holds (no fake controls, no auto-generated
    suggestion content), not operations that don't exist yet.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore, resolve_conversation_hotlinks
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_DRAWING_NAME = "sample_drawing.png"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e_owner", project_name="Riverside P40E Workspace")
        self.project_id = self.doc.project_id
        self._add_drawing_source()

    def tearDown(self):
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

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _add_drawing_source(self):
        drawing_path = self.tmp_dir / _DRAWING_NAME
        drawing_path.write_bytes(b"not a real png, just test bytes")

        store = self._store()
        workspace = store.get(self.project_id)
        workspace.sources.append({
            "id": "drawing-source-1", "project_id": self.project_id, "kind": "drawing",
            "name": _DRAWING_NAME, "added_at": "2026-01-01T00:00:00+00:00",
            "file_path": str(drawing_path),
        })
        store.save(workspace)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class SecondNavigationColumnRemovedTests(_BaseWorkspaceTestCase):
    def test_grid_no_longer_has_a_separate_nav_column(self):
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertNotIn('grid-template-areas: "nav conversation findings"', body)

    def test_project_navigation_appears_projected_in_display_not_the_left_panel(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 2): the pendulum swung back
        # - Documents/Investigations/Chats are Lists tree children of the
        # active Project again (the recursive hierarchy explicitly
        # re-authorized this stage), never projected into Display
        # (Section 4/5's own no-second-navigation-directory rule forbids
        # that direction now).
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertNotIn("display-branch-nav", body)
        self.assertIn(self.project_id, body)
        self.assertIn(">Documents", body)
        self.assertIn(">Investigations", body)
        # CLAUDE-P40-VW7A-QA added a <span class="launcher-count"> after
        # "Chats" (matching Documents/Investigations' own already-open-
        # ended pattern above) - was the one exact-closed-tag ">Chats<"
        # check in this file, now consistent with its siblings.
        self.assertIn(">Conversation", body)

    def test_unified_nav_absent_for_unauthorized_project(self):
        # p40e_outsider is authenticated but neither owner, allow-
        # listed, nor admin - the whole page 404s (P32 deny-by-default),
        # so the project nav never renders for them at all.
        client = self._client_as("p40e_outsider", 2, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)

    def test_unified_nav_absent_on_non_workspace_pages(self):
        client = self._client_as("p40e_owner", 1)
        resp = client.get("/")
        body = resp.get_data(as_text=True)
        self.assertNotIn("launcher-project-context", body)
        self.assertNotIn("display-branch-nav", body)


class WorkspaceHeadingRenameTests(_BaseWorkspaceTestCase):
    def test_case_open_heading_is_workspace_not_case_workspace(self):
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        resp = client.get(f"/projects/{self.project_id}/workspace?case={case_id}")
        body = resp.get_data(as_text=True)
        # CLAUDE-P40-E2B: the page_header <h1> was replaced by the new
        # top bar's own Project/Investigation breadcrumb - the identity
        # renamed here is now carried by that, not a heading tag.
        self.assertIn("workspace-topbar-context", body)
        self.assertNotIn("Case Workspace", body)


class DocumentViewerTests(_BaseWorkspaceTestCase):
    def test_selecting_a_drawing_source_opens_it_in_the_workspace(self):
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?source=drawing-source-1")
        body = resp.get_data(as_text=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("workspace-pane-document", body)
        self.assertIn(_DRAWING_NAME, body)

    def test_unknown_source_id_degrades_to_the_empty_state_not_an_error(self):
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?source=does-not-exist")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("workspace-pane-document", resp.get_data(as_text=True))

    def test_source_from_a_different_project_does_not_resolve(self):
        other_doc = self._ingest(owner="p40e_owner", project_name="A Different Project")
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?source={other_doc.project_id}")
        self.assertNotIn("workspace-pane-document", resp.get_data(as_text=True))

    def test_document_link_in_sources_list_points_at_workspace_not_a_raw_file(self):
        # CLAUDE-P40-E2B1: the Sources list lives in the Documents
        # directory (?view=documents), not bare Project Home.
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?view=documents")
        body = resp.get_data(as_text=True)
        self.assertIn(f"?source=drawing-source-1", body)


class ConversationDockTests(_BaseWorkspaceTestCase):
    def test_dock_has_exactly_one_composer_when_no_case_is_open(self):
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertEqual(body.count("conversation-dock-composer"), 1)

    def test_dock_has_exactly_one_composer_with_a_case_open(self):
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        resp = client.get(f"/projects/{self.project_id}/workspace?case={case_id}")
        body = resp.get_data(as_text=True)
        self.assertEqual(body.count("conversation-dock-composer"), 1)

    def test_draft_preservation_key_is_separate_per_conversation_context(self):
        # CLAUDE-P40-E1A, Section A: "Preserve a separate draft and
        # scroll position for each conversation context" - was a single
        # shared project_id key (P40-E); now data-conversation-draft
        # matches the same per-context scope_key data-conversation-scope
        # already uses ("project" vs "case-<id>"), so switching context
        # restores the RIGHT draft, not a shared one.
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        home_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        case_body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)

        self.assertIn('data-conversation-draft="project"', home_body)
        self.assertIn(f'data-conversation-draft="case-{case_id}"', case_body)

    def test_no_fake_conversation_lifecycle_controls(self):
        # Sections F/H were left specified-but-unbuilt - confirms no
        # dead/misleading "Start New Conversation"/"Archive"/"Save
        # Pattern" control exists.
        #
        # SUPERSEDED IN PART (CLAUDE-P40-E3A-QA, Section 10): the inline
        # "Named conversation history and saved investigation patterns
        # are planned, not available yet" disclosure this test used to
        # also require is removed outright - product-owner browser
        # observation named it clutter ("remove outdated or unnecessary
        # planning copy... when that copy merely clutters the working
        # surface"), and CLAUDE-P40-E3A, Section 13's own exclusion list
        # is the actual place that scope stays documented as unbuilt, not
        # a runtime disclaimer repeated on every Chat dock. The real
        # invariant this test protects - no fake lifecycle control
        # actually exists - is unchanged and still checked below.
        client = self._client_as("p40e_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("planned, not available yet", body)
        for control in ("Start New Conversation", "Archive Conversation", "Save Pattern"):
            self.assertNotIn(control, body)


class HotlinkTests(_BaseWorkspaceTestCase):
    def test_exact_source_filename_becomes_a_link(self):
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": f"Please check {_DRAWING_NAME} for consistency."},
        )
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?source=drawing-source-1"', body)
        self.assertIn(f">{_DRAWING_NAME}<", body)

    def test_text_resembling_a_filename_but_not_a_real_source_is_not_linked(self):
        segments = self._store().get(self.project_id)
        result = resolve_conversation_hotlinks("See totally_made_up_file.pdf for details.", segments)
        self.assertEqual(result, [{"text": "See totally_made_up_file.pdf for details.", "source_id": None}])

    def test_hotlink_resolution_is_xss_safe(self):
        workspace = self._store().get(self.project_id)
        workspace.sources.append({
            "id": "xss-source", "project_id": self.project_id, "kind": "rfq_rfp_document",
            "name": "<script>alert(1)</script>.txt", "added_at": "2026-01-01T00:00:00+00:00", "file_path": None,
        })
        self._store().save(workspace)

        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "XSS Check", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": "Refer to <script>alert(1)</script>.txt please."},
        )
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)


class OriginMessageIdPilotTests(_BaseWorkspaceTestCase):
    """CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01: bounded, reversible pilot -
    see governance/specified-unbuilt/navigation-context-operational-map.md
    ("Active pilot"). A Composer hotlink now carries the originating
    message's own id so the destination can offer a quiet "Return to
    conversation" link back to it - composing Anchor's own shape and the
    pre-existing ?case=&preview_finding_id= redirect precedent, never a
    new navigation framework."""

    def _post_message_and_get_workspace_body(self, text):
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Origin Pilot Case", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": text},
        )
        # The human message specifically - a synchronous assistant reply
        # may already have been appended after it, so conversation[-1]
        # is not reliably the message whose own text contains the hotlink.
        conversation = self._store().get(self.project_id).cases[0]["conversation"]
        message_id = next(m["id"] for m in conversation if m["role"] == "human" and m["text"] == text)
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        return client, body, message_id

    def test_hotlink_carries_the_originating_message_id(self):
        client, body, message_id = self._post_message_and_get_workspace_body(f"Please check {_DRAWING_NAME} for consistency.")
        self.assertIn(f"source=drawing-source-1&amp;origin_message_id={message_id}", body)

    def test_no_origin_message_id_no_return_link(self):
        # The overwhelming common case (a normal page load, no hotlink
        # click) must render nothing extra - no persistent breadcrumb
        # trail (Section 23/32's own "quiet surface" principle).
        client = self._client_as("p40e_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.context.return-to-conversation"', body)

    def test_following_the_hotlink_shows_the_return_link_pointing_at_the_real_message(self):
        # Follows the REAL, rendered hotlink href (not a hand-built URL) -
        # this is the actual end-to-end round trip a real click makes.
        client, body, message_id = self._post_message_and_get_workspace_body(f"Please check {_DRAWING_NAME} for consistency.")
        href_match = re.search(r'href="(/projects/[^"]*source=drawing-source-1[^"]*origin_message_id=[^"]*)"', body)
        self.assertIsNotNone(href_match, body)
        hotlink_href = href_match.group(1).replace("&amp;", "&")
        # Real pilot finding: the message id alone isn't enough for a
        # case-scoped conversation - the hotlink must ALSO carry the
        # originating case (anchor_case_id, already available at
        # generation time) or the conversation thread it points into
        # never renders on the destination page at all.
        self.assertIn(f"case={self._store().get(self.project_id).cases[0]['id']}", hotlink_href)

        follow_up = client.get(hotlink_href).get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.context.return-to-conversation"', follow_up)
        self.assertIn(f'href="#message-{message_id}"', follow_up)
        # The real anchor the link targets must actually exist on THIS
        # same page (the conversation dock still renders even when a
        # Source is the active Display target).
        self.assertIn(f'id="message-{message_id}"', follow_up)

    def test_stale_or_foreign_origin_message_id_degrades_silently_not_an_error(self):
        # Same "soft display hint, never an authorization boundary of its
        # own" treatment ?current=/?preview_finding_id= already get - a
        # made-up id must not 404 or crash, just render a link to a
        # fragment that happens not to exist (a harmless browser no-op).
        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?origin_message_id=not-a-real-message-id")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('href="#message-not-a-real-message-id"', body)

    def test_document_list_leaf_for_the_same_source_is_unaffected(self):
        # The pilot only touches Composer hotlinks (app.py's
        # render_conversation_hotlinks) - the unrelated Document List
        # sidebar leaf for the same Source must never gain this param.
        client, body, message_id = self._post_message_and_get_workspace_body(f"Please check {_DRAWING_NAME} for consistency.")
        list_leaf_idx = body.index('data-ui-ref="lists.project.documents.leaf"')
        list_leaf_tag = body[body.rindex("<a", 0, list_leaf_idx):body.index(">", list_leaf_idx)]
        self.assertNotIn("origin_message_id", list_leaf_tag)


class ResponsiveDomOrderTests(_BaseWorkspaceTestCase):
    def test_workspace_content_precedes_findings_in_dom_order(self):
        client = self._client_as("p40e_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        # CLAUDE-P40-E2B: .workspace-column (Lists+Display stacked
        # together) was split into standalone .workspace-pane-lists and
        # .workspace-pane-display columns - DOM order (Lists, then
        # Display, then Toolbox) is what this test now checks.
        # Matched against the actual container id, not a bare class-name
        # substring - base.html's own pre-paint <head> script legitimately
        # mentions ".workspace-pane-toolbox" in an explanatory comment
        # before Display ever appears in the body, which a bare substring
        # search would wrongly match.
        workspace_pos = body.find('id="workspace-display-panel"')
        toolbox_pos = body.find('id="workspace-toolbox-panel"')
        self.assertGreater(workspace_pos, -1)
        self.assertGreater(toolbox_pos, -1)
        self.assertLess(workspace_pos, toolbox_pos)


class LegacyProjectPersistenceBoundaryStillIntactTests(_BaseWorkspaceTestCase):
    """P40-D2's own invariant, re-verified: a GET against this stage's
    changed route/template must still never persist a structural
    rewrite - only view metadata (last_viewed_by)."""

    def test_get_on_a_legacy_case_missing_visibility_does_not_rewrite_the_record(self):
        from services.case_workspace import CASE_VISIBILITY_SHARED

        workspace = self._store().get(self.project_id)
        legacy_case = {
            "id": "legacy-case-no-visibility", "project_id": self.project_id, "title": "Legacy",
            "objective": "", "created_at": "2020-01-01T00:00:00+00:00", "status": "open",
            "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [], "activity_ids": [],
            "conversation": [],
        }
        workspace.cases.append(legacy_case)
        self._store().save(workspace)

        before_raw = json.loads((self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8"))

        client = self._client_as("p40e_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?case=legacy-case-no-visibility")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<h2>Legacy</h2>", resp.get_data(as_text=True))

        # SUPERSEDED (CLAUDE-P40-E3A): the visibility badge itself only
        # ever rendered in Overview's own "Active Work" case list - and
        # Overview/an open Investigation are now mutually exclusive
        # leaves (Section 4/5), so it can no longer be checked on the
        # SAME ?case=... request. A second GET (still a GET, still
        # covered by the no-rewrite assertion below) confirms the
        # default is applied without ever persisting it.
        overview_resp = client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn(CASE_VISIBILITY_SHARED, overview_resp.get_data(as_text=True))

        after_raw = json.loads((self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8"))
        changed_keys = {k for k in set(before_raw) | set(after_raw) if before_raw.get(k) != after_raw.get(k)}
        # A ?case=... view doesn't touch last_viewed_by at all (that
        # write is Project-Home-only, gated on active_case is None,
        # pre-existing and unrelated to this stage) - the real invariant
        # is that nothing beyond that one permitted key ever changes.
        self.assertTrue(changed_keys.issubset({"last_viewed_by"}), changed_keys)


class AuthShellStillIsolatedTests(_BaseWorkspaceTestCase):
    """P40-D1's own invariant, re-verified after this stage's base.html
    changes."""

    def test_login_still_has_no_project_nav(self):
        resp = self.flask_app.test_client().get("/login")
        body = resp.get_data(as_text=True)
        self.assertNotIn("side-rail-project-nav", body)
        self.assertNotIn("side-rail", body)


if __name__ == "__main__":
    unittest.main()
