"""
CLAUDE-P40-E2B1A - Recursive Projection Conformance Audit and
Product-Owner Visual Gate.

P40-E2B1's own audit found that its single left panel, while physically
one panel, still violated the interaction rule this stage enforced: "the
single left panel is a root launcher, not an expandable navigation
tree." Project names were listed inline under "Projects", and Documents/
Investigations/Chats were listed inline under the active Project - both
duplicated a child hierarchy directly in the panel rather than
projecting it into Display. This stage's fix: the panel held ONLY root
launchers (Projects, New Project, identity); everything else was
projected recursively into Display.

REVERSED (CLAUDE-P40-E3A, Section 2, explicit product-owner decision):
"Your E3 planning report correctly found that the prototype hierarchy
conflicts with P40-E2B1A's pure-root-launcher rule. The product owner
now resolves that conflict in favour of the newer prototype. P40-E2B1
and P40-E2B1A were never accepted... This is a deliberate design change,
not an accidental regression." The ONE left panel now legitimately IS a
recursive hierarchy (Projects > Project name > Overview/Documents/
Investigations/RFIs/Chats, real names, hover-reveal + click-to-pin); the
old Display-projected branch-nav/directory levels this file originally
tested are retired (Section 4: those names live only in Lists now,
Section 5: Display never duplicates them). Tests below have been
rewritten in place to assert the current (P40-E3A) contract; the
"exactly one panel"/authorization/stable-URL/auth-isolation coverage
this file also provided remains valid and is preserved.

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
# REVERSED (CLAUDE-P40-E3A, Section 2): the panel IS a recursive
# hierarchy now - only the ACTIVE Project's own branch expands to real
# Documents/Investigations/RFIs/Chats children; every other Project is a
# plain leaf. What must still never happen is the SAME hierarchy being
# duplicated a second time in Display (Section 4).
# ---------------------------------------------------------------------------

class NoDuplicatedChildHierarchyTests(_BaseTestCase):
    def test_panel_recursively_expands_the_active_project(self):
        base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("nav_recent_projects", base_html)
        self.assertIn("data-tree-root", base_html)
        self.assertIn("data-tree-parent", base_html)

    def test_other_project_names_appear_once_as_plain_leaves_never_duplicated_in_display(self):
        # "A Second Distinct Project" legitimately appears as a plain
        # Lists leaf on the portfolio dashboard (Section 2's own
        # reversal) - CLAUDE-P40-VW7B then removed the portfolio (every
        # OTHER Project's name included) from the opened-Project Lists
        # panel entirely (Section 3) - it must appear ZERO times on a
        # DIFFERENT, already-open Project's own workspace page now,
        # never even once as a plain leaf there.
        other = self._ingest(owner="p40e2b1a_owner", project_name="A Second Distinct Project")
        client = self._client_as("p40e2b1a_owner", 1)
        dashboard_body = client.get("/").get_data(as_text=True)
        self.assertEqual(dashboard_body.count("A Second Distinct Project"), 1)
        other_project_open_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(other_project_open_body.count("A Second Distinct Project"), 0)

        own_page = client.get(f"/projects/{other.project_id}/workspace").get_data(as_text=True)
        # On its own page it legitimately appears three times now
        # (CLAUDE-P40-VW7B, Section 5): the top bar's own breadcrumb
        # link (visible text), that SAME link's own aria-label (real
        # text, "<name> — Switch Project" - not a visible SECOND
        # occurrence on screen, only present in the accessibility tree,
        # needed since the bare visible text alone would not otherwise
        # communicate that activating the link navigates away), and the
        # expanded Lists branch heading - what must never happen is a
        # FOURTH occurrence inside Display itself (a duplicated card/
        # heading, Section 4's own rule) - that check is unaffected and
        # still the real point of this test.
        self.assertEqual(own_page.count("A Second Distinct Project"), 3)
        display_start = own_page.index('class="workspace-pane-display"')
        display_html = own_page[display_start:]
        self.assertNotIn("A Second Distinct Project", display_html)

    def test_documents_investigations_chats_are_listed_in_the_panel_for_the_active_project(self):
        client = self._client_as("p40e2b1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        launcher_start = body.index('<nav class="launcher-panel"')
        launcher_end = body.index("</nav>", launcher_start)
        panel_html = body[launcher_start:launcher_end]
        self.assertIn("Documents", panel_html)
        self.assertIn("Investigations", panel_html)
        self.assertIn("Conversation", panel_html)
        self.assertIn("rfp.txt", panel_html)

    def test_panel_content_differs_between_home_and_an_open_workspace(self):
        # REVERSED from the old invariant: the active Project's own
        # branch legitimately grows a nested, real-data subtree once its
        # Workspace is open (Section 2) - the panel is NOT required to
        # render identically everywhere anymore.
        client = self._client_as("p40e2b1a_owner", 1)

        def panel_html(body):
            start = body.index('<nav class="launcher-panel"')
            end = body.index("</nav>", start)
            return body[start:end]

        home_panel = panel_html(client.get("/").get_data(as_text=True))
        workspace_panel = panel_html(client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True))
        self.assertNotEqual(home_panel, workspace_panel)
        self.assertNotIn("Documents", home_panel)
        self.assertIn("Documents", workspace_panel)


# ---------------------------------------------------------------------------
# Recursive projection through at least three levels
# ---------------------------------------------------------------------------

class RecursiveProjectionTests(_BaseTestCase):
    def test_four_level_projection_chain(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 2/4): levels 1-3 of this
        # chain now live entirely in Lists' own recursive tree, not
        # projected into Display - only the final leaf's real content
        # (level 4) still lands in Display.
        client = self._client_as("p40e2b1a_owner", 1)

        # Level 1: "Projects" root launcher -> the Project directory
        # (still a real page, /projects).
        level1 = client.get("/projects").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace"', level1)
        self.assertIn("Riverside P40E2B1A Workspace", level1)

        # Level 2: opening a Project -> its own branch, expanded in Lists
        # (not Display) - Documents/Investigations/RFIs/Chats children.
        level2 = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-tree-owns="case"', level2)
        self.assertIn('data-tree-owns="source"', level2)
        self.assertNotIn("display-branch-nav", level2)

        # Level 3: the "Investigations" tree-toggle's own children list
        # real Investigation names with real ?case= hrefs, still inside
        # Lists.
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Deep Link Investigation", "objective": ""})
        level3 = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
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
        # SUPERSEDED (CLAUDE-P40-E3A, Section 5): the retired
        # ?view=documents/investigations/chats URLs, and the bare
        # workspace URL, all now degrade to the SAME blank-Display state
        # (empty division-0 header) rather than each rendering distinct
        # "Project Home"/"Documents"/"Investigations"/"Chats" header text
        # - only ?view=overview and a real ?case=/?source= selection
        # still produce real header text. The underlying property this
        # test verifies (a plain GET, no server session state, always
        # reproduces the same projected state on refetch) still holds
        # and is still checked below.
        client = self._client_as("p40e2b1a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Restorable Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        checks = {
            f"/projects/{self.project_id}/workspace": "",
            f"/projects/{self.project_id}/workspace?view=documents": "",
            f"/projects/{self.project_id}/workspace?view=investigations": "",
            f"/projects/{self.project_id}/workspace?view=chats": "",
            f"/projects/{self.project_id}/workspace?view=overview": "Overview",
            f"/projects/{self.project_id}/workspace?case={case_id}": "Restorable Investigation",
        }
        for url, expected_header_text in checks.items():
            first = client.get(url).get_data(as_text=True)
            second = client.get(url).get_data(as_text=True)
            first_header = re.search(r'display-division-header-name">\s*(.*?)\s*</span>', first, re.S)
            second_header = re.search(r'display-division-header-name">\s*(.*?)\s*</span>', second, re.S)
            self.assertEqual(first_header.group(1), expected_header_text, url)
            # Not a strict full-body byte comparison: Overview
            # legitimately varies slightly between successive visits
            # (the pre-existing "since your last visit" marker updates
            # last_viewed_by on every GET). What must stay identical is
            # the STATE itself - which division header/branch is active.
            self.assertEqual(first_header.group(1), second_header.group(1), url)

    def test_navigating_away_and_back_via_fresh_requests_restores_identical_state(self):
        # Simulates Back/Forward: no server session field remembers
        # "which view was open" - only the URL does. Uses the retired
        # ?view=documents URL (now a stable blank Display, unlike
        # ?view=overview which legitimately varies visit-to-visit via
        # the "since your last visit" marker) so page STATE is a genuine
        # strict comparison.
        #
        # CLAUDE-P40-E3A-F1: the raw HTTP body is NOT byte-stable across
        # two different requests, even in the identical test-client
        # session - the <meta name="csrf-token"> value changes.
        # Root-caused via a fast, deterministic 400-iteration
        # reproduction (isolated single-request timing never surfaces it
        # - full-suite timing sometimes does): Flask-WTF's generate_csrf()
        # re-signs the session's own stable CSRF secret with a FRESH
        # itsdangerous timestamp on every call, by design (the timestamp
        # is what lets a token later be checked for expiry) - it does not
        # cache the fully-signed string across requests, only the raw
        # secret in session[csrf_token_key]. Two requests landing in
        # different wall-clock seconds get a different signed token
        # even though nothing about the session or the page's own state
        # changed; two requests completing within the same second get an
        # identical one, which is why this only ever surfaced under
        # full-suite-scale system load (GC/IO pressure widening the gap
        # between the two requests enough to cross a second boundary),
        # never in isolation. This is expected, correct CSRF behavior,
        # not a defect in routes/workspace.py or its templates - the
        # test's own prior comment ("so this is a genuine strict byte
        # comparison, not a flaky one") was simply wrong about that one
        # tag. Confirmed harmless to normalize out: the encoded SECRET
        # segment (before the first ".") is asserted identical below in
        # both requests every time - only the re-signed wrapper around it
        # changes, never the underlying token itself.
        csrf_re = re.compile(r'<meta name="csrf-token" content="([^"]+)">')

        def csrf_secret_segment(html: str) -> str:
            match = csrf_re.search(html)
            self.assertIsNotNone(match, "no csrf-token meta tag found")
            return match.group(1).split(".")[0]

        client = self._client_as("p40e2b1a_owner", 1)
        docs_before = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        client.get(f"/projects/{self.project_id}/workspace?view=investigations")
        docs_after_navigating_away_and_back = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)

        self.assertEqual(csrf_secret_segment(docs_before), csrf_secret_segment(docs_after_navigating_away_and_back))
        normalized_before = csrf_re.sub('<meta name="csrf-token" content="NORMALIZED">', docs_before)
        normalized_after = csrf_re.sub('<meta name="csrf-token" content="NORMALIZED">', docs_after_navigating_away_and_back)
        self.assertEqual(normalized_before, normalized_after)


# ---------------------------------------------------------------------------
# Toolbox and Chat remain correctly contextual
# ---------------------------------------------------------------------------

class ToolboxAndChatContextualTests(_BaseTestCase):
    def test_toolbox_and_chat_track_the_active_leaf_across_the_projection_chain(self):
        client = self._client_as("p40e2b1a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Contextual Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        # SUPERSEDED (CLAUDE-P40-E3A, Section 8): the generic "<h3>Project</h3>"
        # Toolbox section label was removed outright ("remove generic
        # section labels...when they add no information") - the
        # nothing-selected state now reads as a plain note instead.
        project_home = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("No Investigation or Document is currently selected", project_home)

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
