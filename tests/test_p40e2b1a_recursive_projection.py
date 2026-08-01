"""
CLAUDE-P40-E2B1A - Recursive Projection Conformance Audit and
Product-Owner Visual Gate.

P40-E2B1's own audit found that its single left panel, while physically
one panel, still violated the interaction rule this stage enforces: "the
single left panel is a root launcher, not an expandable navigation
tree." Project names were listed inline under "Projects", and Documents/
Investigations/Chats were listed inline under the active Project - both
duplicated a child hierarchy directly in the panel rather than
projecting it into Display. This stage's fix: the panel now holds ONLY
root launchers (Projects, New Project, identity); everything else is
projected recursively into Display - Projects (root) -> the Project
directory (/projects, level 1) -> a specific Project's own branch-nav
(Overview/Documents/Investigations/Chats, level 2, case_workspace.html's
own Display) -> a directory's own children (level 3) -> a leaf's real
content (level 4, activating the shared conversation dock where
relevant).

No browser/rendering tool exists in this environment - these tests
verify what IS provable without one: server-rendered HTML/attributes
and real route behavior across repeated GETs (the definition of
"survives refresh/Back/Forward" for a route with no client-side router).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore, CASE_VISIBILITY_PRIVATE
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e2b1a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e2b1a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e2b1a_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e2b1a_owner", project_name="Riverside P40E2B1A Workspace")
        self.project_id = self.doc.project_id

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

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# Exactly one physical left panel
# ---------------------------------------------------------------------------

class SingleLeftPanelTests(_BaseTestCase):
    def test_exactly_one_launcher_panel_everywhere(self):
        client = self._client_as("p40e2b1a_owner", 1)
        for url in (
            "/", "/projects",
            f"/projects/{self.project_id}/workspace",
            f"/projects/{self.project_id}/workspace?view=documents",
            f"/projects/{self.project_id}/workspace?view=investigations",
            f"/projects/{self.project_id}/workspace?view=chats",
        ):
            body = client.get(url).get_data(as_text=True)
            self.assertEqual(body.count('id="launcher-panel"'), 1, url)
            self.assertEqual(body.count("<nav class=\"launcher-panel\""), 1, url)


# ---------------------------------------------------------------------------
# No duplicated child hierarchy in the panel itself
# ---------------------------------------------------------------------------

class NoDuplicatedChildHierarchyTests(_BaseTestCase):
    def test_panel_holds_only_root_launchers(self):
        base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        # The panel must not contain a loop over Project names, or the
        # per-Project Documents/Investigations/Chats block - those were
        # the two violations this stage's own audit found.
        self.assertNotIn("nav_recent_projects", base_html)
        self.assertNotIn("launcher-project-context", base_html)
        self.assertNotIn("workspace.show_workspace', project_id=project_id, view=", base_html)

    def test_no_project_names_listed_inline_in_the_panel_on_any_page(self):
        # "A Second Distinct Project" legitimately appears on ITS OWN
        # workspace page (the top bar's current-context breadcrumb) -
        # the thing under test is that it never leaks onto Home or a
        # DIFFERENT Project's own page via an inline panel listing.
        other = self._ingest(owner="p40e2b1a_owner", project_name="A Second Distinct Project")
        client = self._client_as("p40e2b1a_owner", 1)
        for url in ("/", f"/projects/{self.project_id}/workspace"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn("A Second Distinct Project", body, url)

        own_page = client.get(f"/projects/{other.project_id}/workspace").get_data(as_text=True)
        self.assertIn("A Second Distinct Project", own_page)

    def test_no_documents_investigations_chats_listed_in_the_panel(self):
        client = self._client_as("p40e2b1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        launcher_start = body.index('<nav class="launcher-panel"')
        launcher_end = body.index("</nav>", launcher_start)
        panel_html = body[launcher_start:launcher_end]
        self.assertNotIn("Documents", panel_html)
        self.assertNotIn("Investigations", panel_html)
        self.assertNotIn("Chats", panel_html)

    def test_panel_content_is_identical_whether_or_not_a_project_is_open(self):
        # A root launcher's own markup must not grow a nested branch just
        # because a Project happens to be open - that would itself be an
        # expandable tree.
        client = self._client_as("p40e2b1a_owner", 1)

        def panel_html(body):
            start = body.index('<nav class="launcher-panel"')
            end = body.index("</nav>", start)
            # Strip the one legitimate difference (active-state class on
            # the Projects heading) before comparing structure.
            return re.sub(r'class="launcher-heading[^"]*"', 'class="launcher-heading"', body[start:end])

        home_panel = panel_html(client.get("/").get_data(as_text=True))
        workspace_panel = panel_html(client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True))
        self.assertEqual(home_panel, workspace_panel)


# ---------------------------------------------------------------------------
# Recursive projection through at least three levels
# ---------------------------------------------------------------------------

class RecursiveProjectionTests(_BaseTestCase):
    def test_four_level_projection_chain(self):
        client = self._client_as("p40e2b1a_owner", 1)

        # Level 1: "Projects" root launcher -> the Project directory,
        # projected into the main content area.
        level1 = client.get("/projects").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace"', level1)
        self.assertIn("Riverside P40E2B1A Workspace", level1)

        # Level 2: clicking a Project -> its own branch-nav, projected
        # into Display (not the left panel).
        level2 = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("display-branch-nav", level2)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?view=investigations"', level2)

        # Level 3: clicking "Investigations" -> the Investigations
        # directory, listing individual Investigation names.
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Deep Link Investigation", "objective": ""})
        level3 = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertIn("Deep Link Investigation", level3)
        case_id = self._store().get(self.project_id).cases[0]["id"]
        self.assertIn(f'href="/projects/{self.project_id}/workspace?case={case_id}"', level3)

        # Level 4 (leaf): clicking the Investigation -> its real content,
        # in the active Display division.
        level4 = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("<h2>Deep Link Investigation</h2>", level4)
        self.assertIn('class="workspace-pane workspace-pane-conversation"', level4)

    def test_documents_branch_also_projects_through_to_a_leaf_document(self):
        client = self._client_as("p40e2b1a_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]

        directory = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?source={source_id}"', directory)

        leaf = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("workspace-pane-document", leaf)


# ---------------------------------------------------------------------------
# A leaf opens its actual content in the active Display division
# ---------------------------------------------------------------------------

class LeafContentInDisplayTests(_BaseTestCase):
    def test_leaf_content_is_a_child_of_the_display_division_not_the_panel(self):
        client = self._client_as("p40e2b1a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Leaf Check", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)

        division_start = body.index('id="display-division-0"')
        panel_end = body.index("</nav>", body.index('<nav class="launcher-panel"'))
        heading_pos = body.index("<h2>Leaf Check</h2>")
        self.assertGreater(heading_pos, division_start)
        self.assertGreater(heading_pos, panel_end)


# ---------------------------------------------------------------------------
# Authorization-filtered children only, at every projected level
# ---------------------------------------------------------------------------

class AuthorizationFilteredChildrenTests(_BaseTestCase):
    def test_outsider_gets_404_at_every_level_not_a_filtered_tree(self):
        client = self._client_as("p40e2b1a_outsider", 2, role="read_only")
        for suffix in ("", "?view=documents", "?view=investigations", "?view=chats"):
            resp = client.get(f"/projects/{self.project_id}/workspace{suffix}")
            self.assertEqual(resp.status_code, 404, suffix)

    def test_private_investigation_absent_from_the_investigations_directory_for_a_non_owner(self):
        owner = self._client_as("p40e2b1a_owner", 1)
        owner.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Private Branch Content"})
        store = self._store()
        workspace = store.get(self.project_id)
        workspace.cases[0]["visibility"] = CASE_VISIBILITY_PRIVATE
        store.save(workspace)

        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="p40e2b1a_allowed_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        store.grant_project_access(workspace, username="p40e2b1a_allowed_reader", actor="p40e2b1a_owner", actor_role="admin")

        reader = self._client_as("p40e2b1a_allowed_reader", 3, role="read_only")
        body = reader.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertNotIn("Private Branch Content", body)

    def test_other_projects_documents_never_appear_in_this_projects_directory(self):
        other = self._ingest(owner="p40e2b1a_owner", project_name="Sibling Project", filename="other.txt")
        other_source_id = self._store().get(other.project_id).sources[0]["id"]

        client = self._client_as("p40e2b1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        self.assertNotIn(other_source_id, body)
        self.assertNotIn("other.txt", body)


# ---------------------------------------------------------------------------
# Back/Forward and direct URLs restore the same projected state
# ---------------------------------------------------------------------------

class StableUrlRestorationTests(_BaseTestCase):
    def test_direct_url_to_each_projected_level_renders_that_exact_state(self):
        client = self._client_as("p40e2b1a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Restorable Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        # Each URL is a plain GET with no server-side session state
        # driving which branch renders - fetching it fresh (simulating a
        # direct link, a refresh, or a Back/Forward navigation) always
        # reproduces the same projected state.
        checks = {
            f"/projects/{self.project_id}/workspace": "Project Home",
            f"/projects/{self.project_id}/workspace?view=documents": "Documents",
            f"/projects/{self.project_id}/workspace?view=investigations": "Investigations",
            f"/projects/{self.project_id}/workspace?view=chats": "Chats",
            f"/projects/{self.project_id}/workspace?case={case_id}": "Restorable Investigation",
        }
        for url, expected_header_text in checks.items():
            first = client.get(url).get_data(as_text=True)
            second = client.get(url).get_data(as_text=True)
            self.assertIn(expected_header_text, first, url)
            # Not a strict full-body byte comparison: Project Home
            # legitimately varies slightly between successive visits
            # (the pre-existing "since your last visit" marker updates
            # last_viewed_by on every GET). What must stay identical is
            # the STATE itself - which division header/branch is active.
            self.assertIn(expected_header_text, second, url)
            first_header = re.search(r'display-division-header-name">\s*(.*?)\s*</span>', first, re.S)
            second_header = re.search(r'display-division-header-name">\s*(.*?)\s*</span>', second, re.S)
            self.assertEqual(first_header.group(1), second_header.group(1), url)

    def test_navigating_away_and_back_via_fresh_requests_restores_identical_state(self):
        # Simulates Back/Forward: no server session field remembers
        # "which view was open" - only the URL does.
        client = self._client_as("p40e2b1a_owner", 1)
        docs_before = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        client.get(f"/projects/{self.project_id}/workspace?view=investigations")
        docs_after_navigating_away_and_back = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        self.assertEqual(docs_before, docs_after_navigating_away_and_back)


# ---------------------------------------------------------------------------
# Toolbox and Chat remain correctly contextual
# ---------------------------------------------------------------------------

class ToolboxAndChatContextualTests(_BaseTestCase):
    def test_toolbox_and_chat_track_the_active_leaf_across_the_projection_chain(self):
        client = self._client_as("p40e2b1a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Contextual Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        project_home = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("<h3>Project</h3>", project_home)

        opened = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("Investigation &middot; Findings", opened)
        self.assertEqual(opened.count('id="conversation-dock"'), 1)
        self.assertIn(f'data-conversation-scope="case-{case_id}"', opened)

    def test_exactly_one_toolbox_and_dock_on_every_projected_level(self):
        client = self._client_as("p40e2b1a_owner", 1)
        for url in (
            f"/projects/{self.project_id}/workspace",
            f"/projects/{self.project_id}/workspace?view=documents",
            f"/projects/{self.project_id}/workspace?view=investigations",
            f"/projects/{self.project_id}/workspace?view=chats",
        ):
            body = client.get(url).get_data(as_text=True)
            self.assertEqual(body.count('id="workspace-toolbox-panel"'), 1, url)
            self.assertEqual(body.count('id="conversation-dock"'), 1, url)


# ---------------------------------------------------------------------------
# Authentication pages remain isolated
# ---------------------------------------------------------------------------

class AuthPagesIsolatedTests(_BaseTestCase):
    def test_login_has_no_launcher_panel_or_branch_nav(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn('id="launcher-panel"', body)
        self.assertNotIn("display-branch-nav", body)
        self.assertNotIn('class="workspace-topbar"', body)

    def test_auth_shell_still_does_not_extend_base_html(self):
        auth_shell = (Path(__file__).resolve().parent.parent / "templates" / "auth_shell.html").read_text(encoding="utf-8")
        self.assertNotIn('{% extends "base.html"', auth_shell)


if __name__ == "__main__":
    unittest.main()
