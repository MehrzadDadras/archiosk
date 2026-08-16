"""
CLAUDE-P40-VW8 / CLAUDE-P40-VW8-QA - Project-switching interruption
dialog (RETIRED, CLAUDE-P40-VW7B - see DialogRetirementTests below) and
the focused existing-Project chooser (routes/portal.py's
`choose_project`, templates/project_chooser.html - still current, now
also VW7B's own Project Vestibule; see that stage's own test file for
its "Current Project" extension).

The interruption dialog's only trigger was activating a DIFFERENT
Project's own `lists.projects.leaf` row while a Project was already
open - CLAUDE-P40-VW7B removed that whole portfolio branch from the
opened-Project Lists panel (Section 3), so the dialog's markup/JS
(#project-switch-dialog, the `a[data-project-id]` click-interceptor)
were dead code and removed outright rather than left unreachable. The
five DialogGatingTests/DialogScriptWiringTests classes that used to
cover it are gone; DialogRetirementTests below is the explicit
regression guard against reintroducing it.

No browser-automation tool is connected in this environment (consistent
with every prior VW stage) - coverage here is structural HTML/route/JS-
source assertions, not pixel/interaction-level.
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
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CHOOSER_HTML_PATH = _REPO_ROOT / "templates" / "project_chooser.html"
_GATEWAY_HTML_PATH = _REPO_ROOT / "templates" / "gateway.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw8_owner", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add(User(username="vw8_stranger", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc1 = self._ingest(owner="vw8_owner", project_name="Alpha Terminal", filename="alpha_rfp.txt")
        self.doc2 = self._ingest(owner="vw8_owner", project_name="Beta Substation", filename="beta_rfp.txt")
        self.other_doc = self._ingest(owner="vw8_stranger", project_name="Stranger Only Project", filename="stranger_rfp.txt")

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

    def _client_as(self, username, user_id, role="read_only"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


# ---------------------------------------------------------------------------
# Project-switching interruption dialog: retirement regression guard
# (CLAUDE-P40-VW7B). The five classes that used to test this dialog's
# markup gating and client-side wiring are gone - this is what replaces
# them: an explicit assertion that the dialog and its interceptor do
# NOT exist, not merely that some earlier test stopped checking them.
# ---------------------------------------------------------------------------

class DialogRetirementTests(_BaseTestCase):
    def test_dialog_markup_does_not_render_anywhere(self):
        client = self._client_as("vw8_owner", 1)
        for url in ("/projects", f"/projects/{self.doc1.project_id}/workspace"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn("project-switch-dialog", body, url)

    def test_interceptor_script_is_gone(self):
        source = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn("project-switch-dialog", source)
        self.assertNotIn("a[data-project-id]", source)

    def test_no_leaf_anywhere_carries_the_retired_switch_attribute(self):
        client = self._client_as("vw8_owner", 1)
        for url in ("/projects", f"/projects/{self.doc1.project_id}/workspace"):
            body = client.get(url).get_data(as_text=True)
            self.assertIsNone(re.search(r'<a[^>]*data-project-id="', body), url)


# ---------------------------------------------------------------------------
# lists.projects.leaf attribute checks that remain meaningful after the
# dialog's retirement.
# ---------------------------------------------------------------------------

class LeafAttributeTests(_BaseTestCase):
    def test_active_projects_own_leaf_carries_no_switch_attributes(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        # The active Project's own row uses a different data-ui-ref
        # (lists.project.self) and must never carry data-project-id -
        # that is what makes "activating the already-current Project
        # never opens the dialog" true by construction.
        self_leaf_match = re.search(r'<a[^>]*data-ui-ref="lists\.project\.self"[^>]*>', body)
        self.assertIsNotNone(self_leaf_match)
        self.assertNotIn("data-project-id", self_leaf_match.group(0))
        self.assertNotIn("data-project-name", self_leaf_match.group(0))

    def test_other_projects_leaf_appears_as_a_switch_target_inside_an_open_project(self):
        # CLAUDE-LEFT-RAIL-01: supersedes CLAUDE-P40-VW7B's own Section 3
        # assertion (immediately above, in this test's own prior form)
        # that other Projects were absent entirely while one was open -
        # the Product Owner has since reversed this: PROJECTS is now a
        # live active-project switcher, always showing every OTHER
        # accessible Project ("Beta Substation", Project 2, not the one
        # open here) as a direct switch target via lists.projects.leaf,
        # exactly so a PM can move between Projects without leaving the
        # one currently open.
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Beta Substation", body)
        self.assertIsNotNone(re.search(r'data-ui-ref="lists\.projects\.leaf"', body))

    def test_no_project_leaf_carries_switch_attributes_on_bare_listing(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIsNone(re.search(r'<a[^>]*data-project-id="', body))

    def test_unauthorized_project_never_appears_as_a_switch_target(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn(self.other_doc.project_id, body)


# ---------------------------------------------------------------------------
# Focused existing-Project chooser (Section 12).
# ---------------------------------------------------------------------------

class ChooserRouteTests(_BaseTestCase):
    def test_chooser_route_lists_only_accessible_projects(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("Alpha Terminal", body)
        self.assertIn("Beta Substation", body)
        self.assertNotIn("Stranger Only Project", body)

    def test_chooser_search_filters_by_query(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects/choose?q=Alpha").get_data(as_text=True)
        self.assertIn("Alpha Terminal", body)
        self.assertNotIn("Beta Substation", body)

    def test_chooser_requires_login(self):
        client = self.flask_app.test_client()
        resp = client.get("/projects/choose")
        self.assertNotEqual(resp.status_code, 200)

    def test_chooser_does_not_render_the_full_lists_workspace_shell(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        # The chooser extends gateway_base.html, not base.html - no
        # Lists panel, no per-project Delete forms, no sort control.
        self.assertNotIn('id="launcher-panel"', body)
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the
        # shared application menu bar (templates/_app_menu.html) now
        # renders on this page too, and its real Edit/Tools items
        # legitimately say "Delete Annotation"/"Select / Delete
        # Annotation" - narrow the check to those two known, real
        # controls (same "exclude the genuinely real one, not the
        # invariant" precedent test_p40e3a_layout_reconciliation.py's
        # own test_no_nonfunctional_drawing_or_tagging_controls already
        # established) rather than a bare substring check.
        body_without_menu_controls = body
        for ref in ("menu.edit.delete", "menu.tools.annotate-select"):
            idx = body_without_menu_controls.find(f'data-ui-ref="{ref}"')
            if idx == -1:
                continue
            start = body_without_menu_controls.rindex("<button", 0, idx)
            end = body_without_menu_controls.index("</button>", idx) + len("</button>")
            body_without_menu_controls = body_without_menu_controls[:start] + body_without_menu_controls[end:]
        self.assertNotIn("Delete", body_without_menu_controls)

    def test_chooser_leaf_links_to_the_real_authorized_workspace_route(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn(f"/projects/{self.doc1.project_id}/workspace", body)

    def test_management_page_remains_separately_reachable(self):
        client = self._client_as("vw8_owner", 1)
        resp = client.get("/projects")
        self.assertEqual(resp.status_code, 200)


class ChooserEmptyStateTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8_empty_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="vw8_lonely", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_projects_shows_coherent_empty_state(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "vw8_lonely"
            sess["role"] = "admin"
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("No projects yet.", body)


class GatewayLinkTests(unittest.TestCase):
    """CLAUDE-CA1D-PROJECT-GATEWAY-LABELS-01 originally retired the single
    environment-agnostic gateway.open-existing ref in favor of two
    context-scoped ones; CLAUDE-GO-NEUTRAL-ENTRY-01 later retired THOSE
    too, converging back to one neutral, unfiltered reveal -
    gateway.open-existing-projects - see UI_REFERENCE_MAP.md's own
    retired-references table for the full lineage."""

    def test_gateway_open_existing_is_present_as_an_inline_reveal(self):
        """CLAUDE-CA1D-GATEWAY-INLINE-REOPEN-01: a PO correction replaced
        the navigating `<a>` (to `portal.choose_project`) with an inline
        `<details>` reveal on the Gateway itself - fewest transitions to
        reopen a Project. `portal.choose_project`/project_chooser.html
        are unchanged and still serve the header's "Switch Project"
        Vestibule (menu.context.switch-project) - just no longer the
        Gateway's own default reopening path."""
        source = _GATEWAY_HTML_PATH.read_text(encoding="utf-8")
        # Passed as a macros.subdisclosure(..., ui_ref=...) call argument,
        # not a literal data-ui-ref="..." HTML attribute in this file's
        # own source (the attribute itself lives in _macros.html).
        self.assertIn('ui_ref="gateway.open-existing-projects"', source)
        self.assertNotIn("portal.choose_project", source)


if __name__ == "__main__":
    unittest.main()
