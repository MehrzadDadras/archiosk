"""
CLAUDE-P40-VW2 - Move Project-Level Controls from Toolbox to the Left Panel.

Product-owner walkthrough correction: the no-selection Toolbox used to
show a project-level panel (explanatory text, Remove Project, the three
Add-a-Source forms, Removed Items, admin-only Project Data Management).
This belongs in the left Lists panel, within the active Project's own
hierarchy, not the contextual right Toolbox.

Root ownership/rendering path (diagnosed before moving any markup):
these controls were rendered entirely inside case_workspace.html's own
{% block toolbox %} no-selection branch, filled into the <aside
id="workspace-toolbox-panel"> that base.html's shell always owns.
Nothing about them was routed or scripted specially - plain forms
posting to existing routes/workspace.py endpoints (add_document_source,
add_text_record_source, remove_document_route's sibling
remove_project_route, restore_document_route) already reused
elsewhere, and macros.subdisclosure/macros.accordion from _macros.html.

Relocation performed: the exact same markup (forms, actions, CSRF
tokens via the app-wide auto-injection, confirm gates, authorization
ifs, macros.subdisclosure calls, unique ids) moved wholesale into
base.html's own Lists panel, as a new "Project Tools" branch sibling to
Overview/Documents/Investigations/RFIs/Chats inside the active
Project's tree - collapsed by default via the existing tree-toggle
mechanism, not a second navigation tree. base.html gained its own
`{% import "_macros.html" as macros %}` (case_workspace.html's import
is local to that template and does not propagate to the parent's own
directly-written markup). The Toolbox's no-selection branch was
reduced to a concise neutral empty state only.

No route in routes/workspace.py was touched - this is a pure template-
layer relocation, so route-level tests already covering these forms
(tests/test_project_home.py, tests/test_p40e2a_containment_and_restoration.py)
remain valid and are not duplicated here; this file adds only what
actually changed: ownership/placement, duplication, and authorization
visibility of the CONTROLS, not the underlying operations.

No browser/rendering tool exists in this environment - structural HTML
assertions verify what a browser would show; stated honestly rather
than skipped, matching this repo's established convention.
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

_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw2_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw2_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw2_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw2_granted_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="vw2_owner", project_name="Riverside Terminal VW2 Workspace")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="vw2_granted_reviewer", actor="vw2_owner", actor_role="admin")

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

    def _toolbox_html(self, body: str) -> str:
        start = body.index('id="workspace-toolbox-panel"')
        return body[start:body.index("</aside>", start)]

    def _lists_html(self, body: str) -> str:
        start = body.index('id="launcher-panel"')
        end = body.index('id="workspace-toolbox-panel"') if 'id="workspace-toolbox-panel"' in body else body.index("</body>")
        return body[start:end]


# ---------------------------------------------------------------------------
# Relocation: present in Lists' Project Tools branch, absent from Toolbox.
# ---------------------------------------------------------------------------

class RelocationOwnershipTests(_BaseTestCase):
    def test_project_tools_branch_present_in_lists_for_the_active_project(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): Remove Project moved OUT of this
        # branch into the Toolbox's own Project Administration disclosure
        # (a partial reversal of P40-VW2, for this one control only) - the
        # file-action controls this test otherwise covers (Add Documents,
        # Removed Items) are unchanged, still here.
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn("Project Tools", lists)
        self.assertIn('id="project-sources-add-document"', lists)
        self.assertIn('id="project-removed-items"', lists)
        self.assertNotIn(f'action="{"/projects/" + self.project_id + "/workspace/remove"}"', lists)

    def test_project_level_controls_absent_from_toolbox_entirely(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): "Remove Project" is the one
        # control that DID move (back) into the Toolbox - see
        # ProjectAdministrationRelocatedTests below for its own coverage.
        # Add a Document/Removed Items/Project Data Management remain
        # Lists-only, unchanged.
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        for forbidden in ("Add a Document", "Removed Items", "Project Data Management"):
            self.assertNotIn(forbidden, toolbox, forbidden)

    def test_toolbox_shows_project_intelligence_when_nothing_selected(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning) superseded this: the old bare
        # neutral empty state ("No Investigation or Document is currently
        # selected") was replaced by the always-present Project
        # Intelligence view (Requirements/Investigations/RFI/Work
        # Products/Conversation/Tasks/Tags/Project Administration) - see
        # governance/current/go-dna-01-composer-result-contract-and-panel-
        # zoning.md for the full record.
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertIn('data-ui-ref="toolbox.project-intelligence"', toolbox)

    def test_relocated_forms_point_at_the_same_unchanged_routes(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn(f'/projects/{self.project_id}/workspace/sources/document', lists)
        self.assertIn(f'/projects/{self.project_id}/workspace/sources/text-record', lists)
        # Remove Project posts to the same unchanged route, now from the
        # Toolbox's own Project Administration disclosure (CLAUDE-GO-DNA-01).
        toolbox = self._toolbox_html(body)
        self.assertIn(f'/projects/{self.project_id}/workspace/remove', toolbox)


class ProjectAdministrationRelocatedTests(_BaseTestCase):
    """CLAUDE-GO-DNA-01 (Panel Zoning): Remove Project's own new home -
    the Toolbox's Project Administration disclosure, owner/admin-gated
    exactly as before relocation."""

    def test_remove_project_present_in_toolbox_for_owner(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertIn('data-ui-ref="toolbox.project-admin"', toolbox)
        self.assertIn('data-ui-ref="toolbox.project-admin.remove-project"', toolbox)

    def test_remove_project_absent_from_toolbox_for_non_owner_non_admin(self):
        client = self._client_as("vw2_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertNotIn('data-ui-ref="toolbox.project-admin"', toolbox)


# ---------------------------------------------------------------------------
# No duplication: exactly one rendered instance, unique identifiers.
# ---------------------------------------------------------------------------

class NoDuplicationTests(_BaseTestCase):
    def test_each_relocated_control_id_appears_exactly_once(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for html_id in ("project-sources-add-document", "project-removed-items", "project-data-management"):
            self.assertEqual(body.count(f'id="{html_id}"'), 1, html_id)

    def test_add_document_form_action_appears_exactly_once(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count(f'action="/projects/{self.project_id}/workspace/sources/document"'), 1)

    def test_remove_project_form_appears_exactly_once(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count(f'action="/projects/{self.project_id}/workspace/remove"'), 1)


# ---------------------------------------------------------------------------
# Authorization: unauthorized users do not gain project actions.
# ---------------------------------------------------------------------------

class AuthorizationTests(_BaseTestCase):
    def test_owner_sees_remove_project(self):
        client = self._client_as("vw2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(">Remove Project<", body)

    def test_admin_sees_remove_project_even_if_not_owner(self):
        client = self._client_as("vw2_admin", 4, role="admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(">Remove Project<", body)

    def test_granted_non_owner_non_admin_reviewer_does_not_see_remove_project(self):
        client = self._client_as("vw2_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Remove Project", body)

    def test_granted_non_admin_reviewer_does_not_see_project_data_management(self):
        client = self._client_as("vw2_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Project Data Management", body)

    def test_admin_sees_project_data_management(self):
        client = self._client_as("vw2_admin", 4, role="admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Project Data Management", body)

    def test_granted_reviewer_still_sees_the_project_tools_branch_itself(self):
        # Add-a-Source/Removed Items were never owner/admin-gated before
        # relocation (any authorized project participant could use
        # them) - that stays true, only Remove Project/Project Data
        # Management are role-gated.
        client = self._client_as("vw2_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="project-sources-add-document"', body)
        self.assertIn('id="project-removed-items"', body)

    def test_outsider_with_no_access_still_gets_404_not_a_filtered_project_tools_branch(self):
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw2_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        client = self._client_as("vw2_outsider", 5, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Document/Investigation contextual Toolbox content remains intact.
# ---------------------------------------------------------------------------

class ContextualToolboxIntactTests(_BaseTestCase):
    def test_document_selected_toolbox_still_shows_document_tools(self):
        client = self._client_as("vw2_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertIn("<h3>Document</h3>", toolbox)
        self.assertIn(f'/projects/{self.project_id}/workspace/sources/{source_id}/remove', toolbox)

    def test_investigation_selected_toolbox_still_shows_findings(self):
        client = self._client_as("vw2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Foundation Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertIn("Investigation", toolbox)
        self.assertIn("Findings (", toolbox)


# ---------------------------------------------------------------------------
# Removal, restoration, and all three Add-source paths retain their
# existing behaviour - the routes themselves were never touched, but
# proven end-to-end here since the trigger markup moved.
# ---------------------------------------------------------------------------

class FunctionalBehaviourPreservedTests(_BaseTestCase):
    def test_add_document_source_still_works_from_the_relocated_form(self):
        client = self._client_as("vw2_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": (io.BytesIO(b"hello"), "note.txt")},
            content_type="multipart/form-data", follow_redirects=True,
        )
        self.assertIn("Document added as a Project Source.", resp.get_data(as_text=True))

    def test_add_text_record_source_still_works_from_the_relocated_form(self):
        client = self._client_as("vw2_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/text-record",
            data={"title": "Site note", "content": "Observed standing water."},
            follow_redirects=True,
        )
        self.assertIn("Text Record added as a Project Source.", resp.get_data(as_text=True))

    def test_remove_and_restore_document_still_works_from_the_relocated_form(self):
        client = self._client_as("vw2_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/remove",
            data={"confirm": "yes"},
        )
        workspace = self._store().get(self.project_id)
        removed = next(s for s in workspace.sources if s["id"] == source_id)
        self.assertIsNotNone(removed["removed_at"])

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/restore")
        workspace = self._store().get(self.project_id)
        restored = next(s for s in workspace.sources if s["id"] == source_id)
        self.assertIsNone(restored["removed_at"])

    def test_removed_items_list_reflects_a_real_removal(self):
        client = self._client_as("vw2_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/remove",
            data={"confirm": "yes"},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn("rfp.txt", lists)

    def test_remove_project_still_works_from_the_relocated_form(self):
        client = self._client_as("vw2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})
        workspace = self._store().get(self.project_id)
        self.assertIsNotNone(workspace.removed_at)


if __name__ == "__main__":
    unittest.main()
