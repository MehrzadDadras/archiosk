"""
CLAUDE-CA1D-GATEWAY-VISUAL-CONTINUITY-01 - Make the post-login Gateway
visually belong to the same public front door.

Covers reuse of the existing deep-ocean background mechanism
(landing.css's .landing-page/.landing-field-canvas + the shared
static/js/ocean_field.js, already proven for /, /explore, /start-trial,
and the sign-in family) on templates/gateway_shell.html (/gateway and
/projects/choose) -- the same .gateway-shell wrapper is confirmed
(grep -rln "gateway-shell" templates/) to appear nowhere else, so the
CSS token redefinition scoped to it cannot leak into base.html's own,
separate, app-wide .workspace-topbar usage.

Run via:

    python -m unittest discover -s tests -v
"""
# CLAUDE-HOME-UNIFY-01: same intent, new refs. The neutral entry actions moved with the home destination - index.resolved.new-project is now the directory's own projects-directory.new-project (same admin gate, same /upload target, still exactly one), and index.resolved.open-existing is the directory's project list. What is asserted is unchanged: one neutral create action, one way to open an existing project, never one pair per stakeholder category.
from __future__ import annotations

import unittest

from werkzeug.security import generate_password_hash


class _BaseGatewayVisualTestCase(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile
        from pathlib import Path

        import app as app_module
        from models import User, db

        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C addendum:
        # this class's tests were originally read-only (never called
        # ingest_upload), so it never needed its own isolated registry
        # path - config.py's own REGISTRY_STORE_PATH default falls back
        # to the real on-disk instance/registry directory otherwise.
        # test_gateway_neutral_entry_actions_still_present now needs a
        # real fixture project to reach index.html's resolved-environment
        # state, so this must be isolated like every other test file that
        # calls ingest_upload.
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_gv_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="gv_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class GatewayShellVisualContinuityTests(_BaseGatewayVisualTestCase):
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: /gateway
    itself no longer renders gateway_shell.html at all (it now only
    redirects to the consolidated /, per routes/portal.py's gateway()
    docstring) - every test below that used to hit /gateway for this
    shell's own visual-continuity markup now hits /projects/choose
    instead, the one remaining route that genuinely still extends
    gateway_base.html/gateway_shell.html unchanged. The two tests
    checking gateway.html's own specific New Project/Open Existing
    Project/account-menu CONTENT (not just the shared background shell)
    are retargeted to / (index.html) under their new index.* refs -
    project_chooser.html never had that content even before this stage."""

    def test_gateway_page_loads_landing_css(self):
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("css/landing.css", body)

    def test_gateway_page_has_the_ocean_background_markup(self):
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn('class="gateway-shell landing-page"', body)
        self.assertIn('id="landing-field-canvas"', body)

    def test_gateway_page_no_longer_has_the_old_blueprint_grid(self):
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertNotIn("blueprint-grid", body)

    def test_gateway_page_loads_ocean_field_js_not_the_full_landing_js(self):
        """Same reasoning as the sign-in family: the authenticated
        Gateway shell must reuse only the shared background script,
        never landing.js itself (spoken welcome greeting, voice input,
        knowledge field -- none of which belong here)."""
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("js/ocean_field.js", body)
        self.assertNotIn("js/landing.js", body)

    def test_project_chooser_shares_the_same_treatment(self):
        """The shared gateway_shell.html means /projects/choose gets
        this consistently too - now the only route this whole family
        of markup checks (see the class's own docstring)."""
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("css/landing.css", body)
        self.assertIn('id="landing-field-canvas"', body)
        self.assertIn("js/ocean_field.js", body)
        self.assertNotIn("blueprint-grid", body)

    def test_gateway_neutral_entry_actions_still_present(self):
        """A pure visual-continuity correction must not touch the
        CLAUDE-GO-NEUTRAL-ENTRY-01 restructure (the two-door
        Client/Owner vs Design-Builder/Proponent split it replaced is
        gone; the single neutral New Project / Open Existing Project
        pair must still render). CLAUDE-POST-SIGNIN-GATEWAY-
        SIMPLIFICATION-01, Option C: this content itself ported from
        the retired gateway.html to / (index.html) under new refs. A
        zero-project fixture would land in index.html's own State 1
        (genuine first-time entry - no Open Existing disclosure at all,
        since nothing exists to open yet, a deliberate difference from
        gateway.html's own always-present-even-when-empty disclosure) -
        this test ingests one project so the fixture resolves a single
        environment (State 3), the state with both actions present,
        matching this test's own original full intent."""
        import io
        import uuid
        from datetime import datetime, timezone
        from unittest.mock import patch

        from werkzeug.datastructures import FileStorage

        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.environment_capabilities import CLIENT_OWNER
        from services.ingestion import ingest_upload

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                ingest_upload(
                    FileStorage(stream=io.BytesIO(b"content"), filename="rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="gv_admin", project_name="Gateway Continuity Fixture",
                )

        client = self._client_as("gv_admin", 1)
        body = client.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertNotIn("Client / Owner Projects", body)
        self.assertNotIn("Design-Builder / Proponent Projects", body)
        self.assertIn('data-ui-ref="projects-directory.new-project"', body)
        self.assertIn('data-ui-ref="projects-directory.list"', body)

    def test_account_menu_still_present_and_functional_markup(self):
        client = self._client_as("gv_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.account"', body)
        self.assertIn('id="workspace-user-menu"', body)
        self.assertIn("Sign out", body)


class GatewayShellReThemeCssTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_gateway_shell_redefines_the_text_and_surface_tokens(self):
        """.gateway-shell { } appears twice - the original P40-VW5
        layout rule (display/flex-direction/min-height) and this
        tranche's own token-redefinition rule further down; find the
        SECOND occurrence."""
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        first_start = css.index(".gateway-shell {")
        rule_start = css.index(".gateway-shell {", first_start + 1)
        rule_end = css.index("}", rule_start)
        rule = css[rule_start:rule_end]
        for token in ("--text-primary", "--surface-primary", "--border", "--brand-gold", "--failure-red"):
            self.assertIn(token, rule)

    def test_card_and_flash_stack_sit_above_the_canvas(self):
        """.workspace-topbar deliberately isn't repeated here -- it
        already has its own pre-existing position:relative/z-index:31,
        which is more than enough once .gateway-shell becomes the
        isolated stacking context via its landing-page class."""
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        rule_start = css.index(".gateway-shell .gateway-page,")
        rule_end = css.index("}", rule_start)
        rule = css[rule_start:rule_end]
        self.assertIn("z-index: 2", rule)

    def test_workspace_user_options_selector_group_unmodified(self):
        """Asserted verbatim by test_p40e3a_qa_reconciliation.py and
        test_p40vw6_theme_correction.py -- this tranche must only rely
        on token cascade, never restructure the selector itself."""
        # Newlines normalized before matching: core.autocrlf=true checks
        # main.css out as CRLF on Windows (.gitattributes covers only the
        # NREOCRC fixtures and vendored PDF.js), so the served bytes carry
        # a carriage return this assertion is not written with. The claim
        # being made is about the SELECTOR GROUP's structure, never about
        # which line terminator a given working copy happens to use.
        css = self.client.get("/static/css/main.css").get_data(as_text=True).replace("\r\n", "\n")
        self.assertIn(
            ".workspace-layout-options,\n.workspace-appearance-options,\n.workspace-user-options {",
            css,
        )


class GatewayShellScopeIsolationTests(_BaseGatewayVisualTestCase):
    def test_base_shell_topbar_is_untouched_light_theme(self):
        """base.html's own, separate authenticated-workspace top bar
        must not pick up any of this tranche's dark re-theme -- proven
        by confirming a real workspace page's markup never nests inside
        .gateway-shell (the only scope the new tokens are defined on)."""
        client = self._client_as("gv_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        # The account/workspace-topbar controls here are genuinely
        # inside .gateway-shell (gateway_shell.html's own top-level
        # wrapper), never .app-shell/.app-main (base.html's).
        self.assertNotIn('class="app-shell"', body)


if __name__ == "__main__":
    unittest.main()
