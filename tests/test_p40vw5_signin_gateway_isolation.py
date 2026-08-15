"""
CLAUDE-P40-VW5 - Restore Standalone Sign-In and Project Gateway Shell
Isolation.

Product-owner walkthrough correction: the Project Gateway (/gateway)
displayed the left Lists panel. Required journey: fresh unauthenticated
entry -> standalone Sign-in -> successful sign-in -> Project Gateway
(no Lists/workspace shell) -> open/create a Project -> full Project
workspace (with its Lists panel).

Root cause, diagnosed before changing anything: templates/
gateway_base.html extended base.html and overrode only {% block
content %} - base.html's own Lists panel (<nav class="launcher-panel">)
is gated on bare `authenticated`, unlike Toolbox/Chat/Display-Layout
(already gated on `project_id is defined and workspace is defined`),
so it rendered around Gateway's centered card on every visit.

Fix: templates/gateway_shell.html, a genuinely standalone shell (the
same principle templates/auth_shell.html already established for
/login et al. - see CLAUDE-P40-D1) that gateway_base.html now extends
instead of base.html. app.py's inject_globals() skips the
nav_recent_projects store query for the Gateway endpoint specifically
(not just its rendering - the same "don't fetch Project content merely
to conceal it" principle the auth-page guard already used).
routes/portal.py's index() now redirects an unauthenticated "/" visit
straight to /login instead of rendering an intermediate marketing page.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (this repo's established convention). No browser-
automation tool is actually connected in this session (confirmed
directly via tool search, consistent with every prior VW stage) -
verification here is structural HTML/route assertions; the real-
browser walkthrough this stage's own prompt requires is stated as a
limitation in the final report, not fabricated.
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
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_DISTINCTIVE_PROJECT_NAME = "Riverside Terminal VW5 Confidential Workspace"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw5_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw5_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw5_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="vw5_admin", project_name=_DISTINCTIVE_PROJECT_NAME)
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

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


# ---------------------------------------------------------------------------
# 1. Normal unauthenticated entry begins at the public landing page
# ---------------------------------------------------------------------------

class UnauthenticatedEntryTests(_BaseTestCase):
    def test_fresh_unauthenticated_entry_renders_the_public_landing_page(self):
        # CLAUDE-CA1D-PUBLIC-LANDING-01: superseded CLAUDE-P40-VW5's own
        # "redirect straight to Sign-in" behavior by explicit, later
        # Product Owner decision - archiosk.com's root is now a real
        # public front door (templates/landing.html), not an immediate
        # redirect to a bare credentials form. 200, not 302 - the
        # landing page itself is what's now served at "/".
        client = self.flask_app.test_client()
        resp = client.get("/", follow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("landing-page", body)
        self.assertIn("Archiosk", body)

    def test_landing_page_sign_in_action_reaches_the_standalone_sign_in_page(self):
        # The landing page's own "Sign In" action still leads to exactly
        # the same standalone auth shell this test previously reached via
        # an automatic redirect - direct /login access is fully preserved,
        # only the ROOT route's own behavior changed.
        client = self.flask_app.test_client()
        resp = client.get("/login", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("auth-shell-page", body)
        self.assertIn("Sign in", body)

    def test_landing_page_never_shows_authenticated_shell_or_project_data(self):
        # Same isolation guarantee SignInIsolationTests below already
        # holds /login to - the new public landing page is an even
        # earlier, even-more-public surface, so it must clear the same bar.
        client = self.flask_app.test_client()
        body = client.get("/", follow_redirects=False).get_data(as_text=True)
        for marker in ("launcher-panel", "app-shell", "workspace-topbar", _DISTINCTIVE_PROJECT_NAME, self.project_id):
            self.assertNotIn(marker, body)


# ---------------------------------------------------------------------------
# 2. Sign-in HTML contains no Lists/workspace shell, no Project data
# ---------------------------------------------------------------------------

class SignInIsolationTests(_BaseTestCase):
    def _assert_fully_isolated(self, body: str):
        for marker in (
            "launcher-panel", "app-shell", "app-main", "workspace-pane-toolbox",
            "workspace-topbar", "chat-region", "display-divisions",
            "workspace-layout-menu", "workspace-appearance-menu",
            "conversation-dock", "Removed Items", "gateway-actions",
            _DISTINCTIVE_PROJECT_NAME, self.project_id,
        ):
            self.assertNotIn(marker, body, f"Sign-in leaked: {marker!r}")

    def test_sign_in_html_is_fully_isolated(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self._assert_fully_isolated(body)

    def test_sign_in_does_not_query_the_project_listing_store(self):
        with patch("app._nav_recent_projects") as mock_nav:
            self.flask_app.test_client().get("/login")
        mock_nav.assert_not_called()

    def test_sign_in_exposes_no_project_derived_counts(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        for marker in ("launcher-count", "Documents <span", "Investigations <span", "RFIs <span"):
            self.assertNotIn(marker, body)


# ---------------------------------------------------------------------------
# 3. Unauthenticated /gateway and Project workspace access remain protected
# ---------------------------------------------------------------------------

class ProtectedRouteTests(_BaseTestCase):
    def test_unauthenticated_gateway_redirects_to_sign_in(self):
        client = self.flask_app.test_client()
        resp = client.get("/gateway", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])
        self.assertIn("next=/gateway", resp.headers["Location"])

    def test_unauthenticated_project_workspace_redirects_to_sign_in(self):
        client = self.flask_app.test_client()
        resp = client.get(f"/projects/{self.project_id}/workspace", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_following_protected_redirect_leaks_no_project_data(self):
        client = self.flask_app.test_client()
        resp = client.get(f"/projects/{self.project_id}/workspace", follow_redirects=True)
        body = resp.get_data(as_text=True)
        self.assertNotIn(_DISTINCTIVE_PROJECT_NAME, body)
        self.assertNotIn(self.project_id, body)


# ---------------------------------------------------------------------------
# 4. Successful sign-in reaches the Gateway; safe next= preserved
# ---------------------------------------------------------------------------

class SuccessfulSignInTests(_BaseTestCase):
    def test_normal_sign_in_reaches_the_gateway(self):
        client = self.flask_app.test_client()
        resp = client.post("/login", data={"username": "vw5_admin", "password": "x"}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/gateway"))

    def test_safe_next_after_a_direct_protected_link_is_preserved(self):
        # Existing, already-security-tested behaviour (test_p40d1_auth_
        # shell_isolation.py) - untouched by this stage, re-confirmed
        # here as part of this stage's own required journey coverage.
        client = self.flask_app.test_client()
        resp = client.post(
            f"/login?next=/projects/{self.project_id}/workspace",
            data={"username": "vw5_admin", "password": "x"}, follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith(f"/projects/{self.project_id}/workspace"))

    def test_off_site_next_is_ignored_on_sign_in(self):
        client = self.flask_app.test_client()
        resp = client.post(
            "/login?next=https://evil.example/steal",
            data={"username": "vw5_admin", "password": "x"}, follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example", resp.headers["Location"])


# ---------------------------------------------------------------------------
# 5. Logout returns to standalone Sign-in
# ---------------------------------------------------------------------------

class LogoutTests(_BaseTestCase):
    def test_logout_returns_to_standalone_sign_in(self):
        client = self._client_as("vw5_admin", 1)
        resp = client.get("/logout", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("auth-shell-page", body)
        self.assertNotIn("gateway-shell", body)
        self.assertNotIn("app-shell", body)

    def test_logout_actually_clears_the_session(self):
        client = self._client_as("vw5_admin", 1)
        client.get("/logout")
        resp = client.get("/gateway", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])


# ---------------------------------------------------------------------------
# 6-9. Gateway itself: no Lists, no empty column, no Toolbox/Display/dock
# ---------------------------------------------------------------------------

class GatewayShellIsolationTests(_BaseTestCase):
    def test_gateway_contains_no_lists_panel(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("launcher-panel", body)
        self.assertNotIn("tree-root", body)
        self.assertNotIn("+ New Project", body)
        self.assertNotIn("tree-children", body)

    def test_gateway_reserves_no_empty_left_column(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("panel-divider", body)
        self.assertNotIn("lists-divider", body)
        self.assertNotIn("app-shell-body", body)

    def test_gateway_contains_no_toolbox_display_or_chat_dock(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        for marker in (
            "workspace-pane-toolbox", "workspace-pane-display", "display-divisions",
            "display-context-menu", "workspace-layout-menu", "workspace-appearance-menu",
            "chat-region", "conversation-dock",
        ):
            self.assertNotIn(marker, body, marker)

    def test_gateway_does_not_query_the_project_listing_store(self):
        with patch("app._nav_recent_projects") as mock_nav:
            self._client_as("vw5_admin", 1).get("/gateway")
        mock_nav.assert_not_called()

    def test_gateway_uses_the_standalone_shell_and_wide_centered_card(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        # CLAUDE-CA1D-GATEWAY-VISUAL-CONTINUITY-01 added the shared
        # deep-ocean background (landing-page) alongside gateway-shell -
        # unrelated to the shell-isolation property this test guards.
        self.assertIn('class="gateway-shell landing-page"', body)
        self.assertIn("gateway-card-wide", body)
        self.assertIn('class="gateway-page"', body)


# ---------------------------------------------------------------------------
# 10-11. Gateway project-creation and open-existing-project remain functional
# ---------------------------------------------------------------------------

class GatewayFunctionalChoicesTests(_BaseTestCase):
    def test_admin_sees_one_neutral_create_project_action(self):
        """CLAUDE-GO-NEUTRAL-ENTRY-01: Gateway used to be two context
        groups (Client/Owner, Design-Builder/Proponent), each with its
        own "New Project" action - a real Product Owner report named
        that two-door split itself as the defect (the user enters
        ARCHIOSK, not a stakeholder category). Now one neutral action,
        no `?environment=` preset - the real commissioning step is
        `/upload`'s own required radio + confirmation checkbox,
        unchanged."""
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("Client / Owner Projects", body)
        self.assertNotIn("Design-Builder / Proponent Projects", body)
        self.assertIn('data-ui-ref="gateway.new-project"', body)
        self.assertIn('href="/upload"', body)
        self.assertNotIn('href="/upload?environment=', body)

    def test_non_admin_does_not_see_create_project_action(self):
        client = self._client_as("vw5_reviewer", 2, role="read_only")
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="gateway.new-project"', body)

    def test_open_existing_project_action_present_and_functional(self):
        # CLAUDE-GO-NEUTRAL-ENTRY-01: one unfiltered inline reveal over
        # every authorized project, regardless of operating environment
        # - not partitioned into two context-scoped controls.
        # CLAUDE-CA1D-GATEWAY-INLINE-REOPEN-01: "Open Existing Project"
        # is an inline reveal on the Gateway itself (fewest possible
        # transitions to reopen a Project) rather than a navigating link
        # to /projects/choose - the fixture's own project must appear
        # directly in the Gateway's own inline list.
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.open-existing-projects"', body)
        self.assertIn(_DISTINCTIVE_PROJECT_NAME, body)
        # /projects/choose itself is unchanged and still independently
        # reachable (the header's "Switch Project" Vestibule uses it).
        resp = client.get("/projects/choose")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(_DISTINCTIVE_PROJECT_NAME, resp.get_data(as_text=True))
        # The management directory itself is unchanged and still works.
        management_resp = client.get("/projects")
        self.assertEqual(management_resp.status_code, 200)
        self.assertIn(_DISTINCTIVE_PROJECT_NAME, management_resp.get_data(as_text=True))

    def test_create_project_action_actually_reaches_the_admin_only_route(self):
        client = self._client_as("vw5_admin", 1)
        resp = client.get("/upload")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 12-13. Removed Projects / Security discoverable and authorization enforced
# ---------------------------------------------------------------------------

class NonWorkspaceFunctionAccessTests(_BaseTestCase):
    def test_removed_projects_reachable_from_gateway_for_any_authenticated_user(self):
        for username, uid, role in (("vw5_admin", 1, "admin"), ("vw5_reviewer", 2, "read_only")):
            client = self._client_as(username, uid, role=role)
            body = client.get("/gateway").get_data(as_text=True)
            self.assertIn('href="/removed-projects"', body, username)
            resp = client.get("/removed-projects")
            self.assertEqual(resp.status_code, 200, username)

    def test_security_reachable_from_gateway_for_admin_only(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn('href="/security/"', body)

    def test_security_link_absent_from_gateway_for_non_admin(self):
        client = self._client_as("vw5_reviewer", 2, role="read_only")
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn('href="/security/"', body)
        self.assertNotIn(">Security<", body)

    def test_non_admin_still_gets_403_hitting_security_directly(self):
        # Server-side enforcement is the real protection - hiding the
        # link is discoverability only (VW5's own explicit instruction).
        client = self._client_as("vw5_reviewer", 2, role="read_only")
        resp = client.get("/security/")
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_still_gets_403_hitting_upload_directly(self):
        client = self._client_as("vw5_reviewer", 2, role="read_only")
        resp = client.get("/upload")
        self.assertEqual(resp.status_code, 403)

    def test_unauthenticated_security_and_upload_redirect_to_sign_in(self):
        client = self.flask_app.test_client()
        for url in ("/security/", "/upload"):
            resp = client.get(url, follow_redirects=False)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn("/login", resp.headers["Location"], url)


# ---------------------------------------------------------------------------
# 14-15. Opening a Project restores the full shell; returning to Gateway
# removes all stale Project-specific content
# ---------------------------------------------------------------------------

class ShellTransitionTests(_BaseTestCase):
    def test_opening_a_project_restores_the_complete_workspace_shell(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("app-shell", body)
        self.assertIn("launcher-panel", body)
        self.assertIn(_DISTINCTIVE_PROJECT_NAME, body)

    def test_returning_to_gateway_shows_no_stale_project_content(self):
        # CLAUDE-CA1D-GATEWAY-INLINE-REOPEN-01: the fixture's own Project
        # NAME legitimately appears now, inside Gateway's own inline
        # "Open Existing Project" picker - that is the intended feature,
        # not a leak. What must never appear is actual WORKSPACE shell
        # content (Toolbox/Display/Chat/Lists) rendering around it - the
        # original VW5 defect this test guards against.
        client = self._client_as("vw5_admin", 1)
        client.get(f"/projects/{self.project_id}/workspace")  # open the Project first
        body = client.get("/gateway").get_data(as_text=True)
        for marker in (
            "workspace-pane-toolbox", "display-divisions", "chat-region",
            "launcher-panel", "app-shell",
        ):
            self.assertNotIn(marker, body, marker)

    def test_gateway_then_project_then_gateway_round_trip_leaks_nothing(self):
        # See test_returning_to_gateway_shows_no_stale_project_content
        # above: the Project's own name is now expected inline (the
        # Gateway's own "Open Existing Project" picker); the workspace
        # SHELL (Lists/launcher-panel) must still never leak.
        client = self._client_as("vw5_admin", 1)
        client.get("/gateway")
        client.get(f"/projects/{self.project_id}/workspace")
        second_gateway = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("launcher-panel", second_gateway)


# ---------------------------------------------------------------------------
# 16. VW1-VW4 behaviour remains clean inside Project workspaces
# ---------------------------------------------------------------------------

class PriorStagePreservationTests(_BaseTestCase):
    def test_vw1_context_menu_still_hidden_by_default_in_workspace(self):
        # CLAUDE-P40-VW8-QA added data-ui-ref="display.context-menu"
        # between the id and hidden attributes - window widened to
        # +120 to still reach it.
        client = self._client_as("vw5_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="display-context-menu"')
        tag = body[start - 40:start + 120]
        self.assertIn("hidden", tag)

    def test_vw2_project_tools_no_longer_in_lists_or_toolbox(self):
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 supersedes this test's
        # own "still relocated to Lists" premise: Project Tools/Add
        # Documents is retired from the rail entirely now (promoted to
        # Admin -> Project Data Management instead, see
        # governance/spare-parts-yard.md), not merely moved from Toolbox
        # to Lists. Absent from both surfaces is now the correct check.
        client = self._client_as("vw5_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('id="project-sources-add-document"', body)
        toolbox_start = body.index('id="workspace-toolbox-panel"')
        toolbox = body[toolbox_start:body.index("</aside>", toolbox_start)]
        self.assertNotIn("Add a Document", toolbox)

    def test_vw3_appearance_matrix_still_present_in_workspace(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-appearance-menu"', body)
        self.assertEqual(body.count('id="appearance-menu-light"'), 1)

    def test_vw4_independent_vertical_horizontal_steppers_still_present(self):
        client = self._client_as("vw5_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for control in ("display-vertical-decrement", "display-vertical-increment",
                         "display-horizontal-decrement", "display-horizontal-increment"):
            self.assertIn(f'id="{control}"', body, control)

    def test_stable_url_restoration_still_intact(self):
        # ?view=documents, not ?view=overview - the latter legitimately
        # varies visit-to-visit via the "since your last visit" marker
        # (documented in test_p40e2b1a_recursive_projection.py's own
        # StableUrlRestorationTests), which is not what this check means
        # to verify.
        client = self._client_as("vw5_admin", 1)
        first = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        second = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        import re
        csrf_re = re.compile(r'<meta name="csrf-token" content="([^"]+)">')
        # CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01: every inline <script> tag
        # now also carries a fresh per-request nonce (app.py's
        # get_csp_nonce) - same reasoning as the CSRF token normalization
        # below (test_p40e2b1a_recursive_projection.py's own
        # StableUrlRestorationTests has the fuller explanation).
        nonce_re = re.compile(r'nonce="[^"]+"')
        normalized_first = csrf_re.sub('<meta name="csrf-token" content="NORMALIZED">', first)
        normalized_second = csrf_re.sub('<meta name="csrf-token" content="NORMALIZED">', second)
        normalized_first = nonce_re.sub('nonce="NORMALIZED"', normalized_first)
        normalized_second = nonce_re.sub('nonce="NORMALIZED"', normalized_second)
        self.assertEqual(normalized_first, normalized_second)


if __name__ == "__main__":
    unittest.main()
