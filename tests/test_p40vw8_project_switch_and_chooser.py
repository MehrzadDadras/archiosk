"""
CLAUDE-P40-VW8 / CLAUDE-P40-VW8-QA - Project-switching interruption
dialog and the focused existing-Project chooser (routes/portal.py's
`choose_project`, templates/project_chooser.html).

No browser-automation tool is connected in this environment (consistent
with every prior VW stage) - coverage here is structural HTML/route/JS-
source assertions, not pixel/interaction-level. Client-side branching
(Stay/Switch/Open-in-New-Tab, Escape/outside-click) is verified by
asserting the exact conditions the inline script depends on (gating
selector, handler wiring), not by executing the script.
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
# Project-switching interruption dialog: markup gating.
# ---------------------------------------------------------------------------

class DialogGatingTests(_BaseTestCase):
    def test_dialog_markup_absent_on_bare_projects_listing(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('<div class="project-switch-dialog"', body)

    def test_dialog_markup_present_inside_an_open_project(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="project-switch-dialog"', body)
        self.assertIn('data-ui-ref="lists.project-switch-dialog"', body)

    def test_dialog_hidden_by_default(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="project-switch-dialog"')
        # The `hidden` attribute must appear on the dialog's own opening
        # tag, before the tag closes.
        tag_end = body.index(">", start)
        self.assertIn("hidden", body[start:tag_end])

    def test_dialog_has_real_dialog_semantics(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="project-switch-dialog"')
        tag_end = body.index(">", start)
        opening_tag = body[start:tag_end]
        self.assertIn('role="dialog"', opening_tag)
        self.assertIn('aria-modal="true"', opening_tag)
        self.assertIn('aria-labelledby="project-switch-dialog-heading"', opening_tag)

    def test_dialog_offers_all_three_choices_with_stable_refs(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project-switch-dialog.stay"', body)
        self.assertIn('data-ui-ref="lists.project-switch-dialog.switch"', body)
        self.assertIn('data-ui-ref="lists.project-switch-dialog.open-new-tab"', body)


# ---------------------------------------------------------------------------
# Project-switching interruption dialog: leaf attribute gating (the
# mechanism the click-interceptor actually keys off).
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

    def test_other_open_projects_leaf_carries_correct_switch_attributes(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        # Deliberately no data-project-name assertion here - the name is
        # read from the link's own visible text (see the JS wiring test
        # below), never duplicated into an attribute value, so as not to
        # reintroduce CLAUDE-P40-E2B1's "name appears twice" regression.
        other_leaf_match = re.search(
            r'<a[^>]*data-ui-ref="lists\.projects\.leaf"[^>]*data-project-id="([^"]+)"[^>]*>([^<]+)</a>',
            body,
        )
        self.assertIsNotNone(other_leaf_match)
        self.assertEqual(other_leaf_match.group(1), self.doc2.project_id)
        self.assertEqual(other_leaf_match.group(2), "Beta Substation")

    def test_other_projects_leaf_has_no_redundant_name_attribute(self):
        # A project name appearing a second time as an attribute value
        # (in addition to the leaf's own visible text) previously broke
        # CLAUDE-P40-E2B1's "a Project name must never appear a second
        # time" invariant - this pins that down as a regression test.
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count("Beta Substation"), 1)

    def test_no_project_leaf_carries_switch_attributes_on_bare_listing(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIsNone(re.search(r'<a[^>]*data-project-id="', body))

    def test_unauthorized_project_never_appears_as_a_switch_target(self):
        client = self._client_as("vw8_owner", 1)
        body = client.get(f"/projects/{self.doc1.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn(self.other_doc.project_id, body)


# ---------------------------------------------------------------------------
# Project-switching interruption dialog: client-side wiring (regex checks
# against the inline script, matching this codebase's established
# no-browser-tool testing pattern - see test_p40vw7b's own JS assertions).
# ---------------------------------------------------------------------------

class DialogScriptWiringTests(unittest.TestCase):
    def setUp(self):
        self.source = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_interceptor_gates_on_data_project_id_selector(self):
        self.assertIn("a[data-project-id]", self.source)

    def test_switch_reuses_existing_href_no_new_route(self):
        # Switch/Open-in-New-Tab must navigate to the link's own real
        # href (already-authorized workspace.show_workspace URL) - no
        # separate client-side-constructed URL or new endpoint.
        script_start = self.source.index("var dialog = document.getElementById('project-switch-dialog')")
        script = self.source[script_start:script_start + 4000]
        self.assertIn("link.getAttribute('href')", script)
        self.assertIn("window.location.href = pendingUrl", script)
        self.assertIn("window.open(pendingUrl", script)

    def test_popup_blocked_handled_non_destructively(self):
        script_start = self.source.index("var dialog = document.getElementById('project-switch-dialog')")
        script = self.source[script_start:script_start + 4000]
        self.assertIn("project-switch-popup-note", script)
        self.assertIn("catch", script)

    def test_escape_and_outside_click_close_the_dialog(self):
        script_start = self.source.index("var dialog = document.getElementById('project-switch-dialog')")
        script = self.source[script_start:script_start + 4000]
        self.assertIn("Escape", script)
        self.assertIn("closeDialog", script)

    def test_names_rendered_via_textcontent_not_innerhtml(self):
        script_start = self.source.index("var dialog = document.getElementById('project-switch-dialog')")
        script = self.source[script_start:script_start + 4000]
        self.assertIn("currentNameEl.textContent", script)
        self.assertIn("targetNameEl.textContent", script)
        # A code comment may explain the textContent-over-innerHTML choice;
        # what must never appear is an actual assignment to .innerHTML.
        self.assertNotIn(".innerHTML =", script)
        self.assertNotIn(".innerHTML=", script)


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
        self.assertNotIn("Delete", body)

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
    def test_gateway_open_existing_points_at_the_chooser_not_management(self):
        source = _GATEWAY_HTML_PATH.read_text(encoding="utf-8")
        match = re.search(r'data-ui-ref="gateway\.open-existing"[^>]*href="([^"]+)"', source)
        if match is None:
            match = re.search(r'href="\{\{ url_for\(\'([^\']+)\'\)[^}]*\}\}"[^>]*data-ui-ref="gateway\.open-existing"', source)
        self.assertIsNotNone(match, "gateway.open-existing link not found")

    def test_gateway_open_existing_uses_choose_project_endpoint(self):
        source = _GATEWAY_HTML_PATH.read_text(encoding="utf-8")
        anchor_start = source.index('data-ui-ref="gateway.open-existing"')
        window = source[max(0, anchor_start - 200):anchor_start + 150]
        self.assertIn("portal.choose_project", window)
        self.assertNotIn("portal.projects_list", window)


if __name__ == "__main__":
    unittest.main()
