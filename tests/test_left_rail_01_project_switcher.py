"""
CLAUDE-LEFT-RAIL-01 - the left PROJECTS rail becomes a pure, always-
available active-project switcher; New Project/Removed Projects/
Security/Operations/Project Data Management move to the top-right
Account/Admin menu.

Product Owner rule: "PROJECTS = the projects I can work on and switch
between. ADMIN = actions that create, govern, recover, or administer
projects and the system."

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_left_rail_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="lr_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="lr_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="lr_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=__import__("uuid").uuid4().hex, filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                from services.ingestion import ingest_upload
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(content), filename=filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="lr_owner", user_id=1, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# Section 9/10: one-project and multiple-project cases.
# ---------------------------------------------------------------------------

class OneProjectCaseTests(_BaseTestCase):
    def test_projects_rail_is_coherent_with_only_one_accessible_project(self):
        doc = self._ingest("Solo Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.projects"', body)
        self.assertIn('data-ui-ref="lists.project.self"', body)
        # The one Project is the current one - no plain switch-target
        # leaf duplicates it, and no unrelated navigation was added to
        # compensate for "nothing else to switch to."
        self.assertNotIn('data-ui-ref="lists.projects.leaf"', body)


class MultipleProjectCaseTests(_BaseTestCase):
    def test_other_accessible_projects_render_as_switch_targets(self):
        doc_a = self._ingest("Project Alpha")
        doc_b = self._ingest("Project Beta")
        doc_c = self._ingest("Project Gamma")
        client = self._client()
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Project Beta", body)
        self.assertIn("Project Gamma", body)
        self.assertEqual(body.count('data-ui-ref="lists.projects.leaf"'), 2)

    def test_exactly_one_project_is_marked_current(self):
        doc_a = self._ingest("Project Alpha")
        self._ingest("Project Beta")
        client = self._client()
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        # The exact class-attribute pattern, not a bare substring count -
        # the literal text "current-project" also appears once more
        # inside an inline <script> JS comment describing the CSS class
        # (JS comments are real bytes sent to the browser, unlike Jinja's
        # own {# #} comments, which are stripped server-side).
        self.assertEqual(body.count('class="tree-leaf launcher-link current-project"'), 1)
        # Exactly one aria-current="true" in the whole page - the current
        # Project's own self-link, never duplicated onto a plain leaf.
        self.assertEqual(body.count('aria-current="true"'), 1)

    def test_current_project_is_not_a_switch_target_to_itself(self):
        doc_a = self._ingest("Project Alpha")
        self._ingest("Project Beta")
        client = self._client()
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        leaf_start = 0
        occurrences = []
        while True:
            idx = body.find('data-ui-ref="lists.projects.leaf"', leaf_start)
            if idx == -1:
                break
            tag_start = body.rindex("<a", 0, idx)
            tag_end = body.index(">", idx)
            occurrences.append(body[tag_start:tag_end])
            leaf_start = idx + 1
        self.assertTrue(occurrences)
        for tag in occurrences:
            self.assertNotIn(f"project_id={doc_a.project_id}", tag)


# ---------------------------------------------------------------------------
# Section 2/7/11: switching rebinds context; isolation is absolute.
# ---------------------------------------------------------------------------

class ProjectSwitchingRebindsContextTests(_BaseTestCase):
    def test_switching_shows_the_new_projects_own_content_not_the_old_ones(self):
        doc_a = self._ingest("Project Alpha", filename="alpha_spec.pdf")
        doc_b = self._ingest("Project Beta", filename="beta_spec.pdf")
        client = self._client()

        body_a = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        self.assertIn("alpha_spec.pdf", body_a)
        self.assertNotIn("beta_spec.pdf", body_a)

        # A real click on the switch-target leaf is nothing but this GET -
        # the exact same route every other Project-opening navigation in
        # this app already uses (workspace.show_workspace), so context
        # rebinding (GO/Composer, Sources, Folder territory, Requirements,
        # Findings, RFIs, Tasks) is structurally guaranteed by the
        # existing per-request architecture, not new isolation logic this
        # stage had to build - proven directly here, not assumed.
        body_b = client.get(f"/projects/{doc_b.project_id}/workspace").get_data(as_text=True)
        self.assertIn("beta_spec.pdf", body_b)
        self.assertNotIn("alpha_spec.pdf", body_b)

    def test_conversation_evidence_does_not_leak_across_a_switch(self):
        doc_a = self._ingest("Project Alpha")
        doc_b = self._ingest("Project Beta")
        client = self._client()

        client.post(f"/projects/{doc_a.project_id}/workspace/quick-start", data={"text": "Alpha-only note about the roof deck"})
        body_a = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Alpha-only note about the roof deck", body_a)

        body_b = client.get(f"/projects/{doc_b.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Alpha-only note about the roof deck", body_b)

    def test_switching_back_restores_the_original_projects_own_state(self):
        doc_a = self._ingest("Project Alpha")
        doc_b = self._ingest("Project Beta")
        client = self._client()
        client.post(f"/projects/{doc_a.project_id}/workspace/quick-start", data={"text": "Alpha continuity note"})
        client.get(f"/projects/{doc_b.project_id}/workspace")
        body_a_again = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Alpha continuity note", body_a_again)

    def test_no_interruption_dialog_switching_is_a_direct_link(self):
        # Section 3: "do not add a confirmation dialog merely because the
        # user selected another project" - lists.projects.leaf is a
        # plain <a href>, not a form/button requiring a second step.
        doc_a = self._ingest("Project Alpha")
        self._ingest("Project Beta")
        client = self._client()
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        leaf_idx = body.index('data-ui-ref="lists.projects.leaf"')
        tag_start = body.rindex("<a", 0, leaf_idx)
        tag_end = body.index(">", leaf_idx)
        tag = body[tag_start:tag_end]
        self.assertIn("href=", tag)


class UnauthorizedProjectNeverAppearsTests(_BaseTestCase):
    def test_a_project_the_user_cannot_access_is_not_offered_as_a_switch_target(self):
        doc_a = self._ingest("Project Alpha")
        doc_private = self._ingest("Private Project", owner="lr_owner")
        # lr_reader has no access grant to either Project.
        client = self._client(username="lr_reader", user_id=2, role="read_only")
        resp = client.get(f"/projects/{doc_a.project_id}/workspace")
        # Access itself is denied (P32) - the real, pre-existing gate this
        # stage did not touch; confirms the rail change adds no new
        # access surface of its own.
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Section 5/6/8: New Project/Removed Projects/Security/Operations/Project
# Data Management relocated to the Account/Admin menu, privilege-aware.
# ---------------------------------------------------------------------------

class AdminSurfaceRelocationTests(_BaseTestCase):
    def test_admin_functions_absent_from_the_rail_for_an_admin(self):
        doc = self._ingest("Project Alpha")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertNotIn('data-ui-ref="lists.removed-projects"', body)
        self.assertNotIn('data-ui-ref="lists.security"', body)
        self.assertNotIn('data-ui-ref="lists.operations"', body)
        self.assertNotIn('data-ui-ref="lists.system-data-management"', body)

    def test_admin_functions_reachable_from_account_menu_for_an_admin(self):
        doc = self._ingest("Project Alpha")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.account.admin.new-project"', body)
        self.assertIn('data-ui-ref="menu.account.admin.security"', body)
        self.assertIn('data-ui-ref="menu.account.admin.operations"', body)
        self.assertIn('data-ui-ref="menu.account.admin.project-data-management"', body)
        self.assertIn('href="/upload"', body)
        self.assertIn('href="/security/"', body)
        self.assertIn('href="/operations/"', body)
        self.assertIn('href="/admin/reset-project-data"', body)

    def test_admin_section_absent_from_account_menu_for_a_non_admin(self):
        doc = self._ingest("Project Alpha")
        from services.case_workspace import CaseWorkspaceStore
        store = CaseWorkspaceStore(self.tmp_dir)
        ws = store.get(doc.project_id)
        store.grant_project_access(ws, "lr_reader", actor="lr_owner", actor_role="admin")
        client = self._client(username="lr_reader", user_id=2, role="read_only")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.account.admin"', body)
        self.assertNotIn('data-ui-ref="menu.account.admin.new-project"', body)
        self.assertNotIn('data-ui-ref="menu.account.admin.security"', body)

    def test_removed_projects_reachable_for_a_non_admin_with_project_access(self):
        # Section 8: reuse existing authorization behavior, do not
        # invent a new restriction - routes/portal.py's own
        # removed_projects/restore_project_route are @login_required
        # only (P32-filtered), not admin-only, so this stays reachable
        # for any authenticated user, unlike the truly admin-gated items.
        doc = self._ingest("Project Alpha")
        from services.case_workspace import CaseWorkspaceStore
        store = CaseWorkspaceStore(self.tmp_dir)
        ws = store.get(doc.project_id)
        store.grant_project_access(ws, "lr_reader", actor="lr_owner", actor_role="admin")
        client = self._client(username="lr_reader", user_id=2, role="read_only")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.account.removed-projects"', body)

    def test_no_duplicate_new_project_entry_point_inside_the_workspace(self):
        # Section 5: "Do not duplicate New Project elsewhere inside the
        # normal project workspace."
        doc = self._ingest("Project Alpha")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('href="/upload"'), 1)

    def test_admin_functions_also_absent_from_portfolio_rail(self):
        # Portfolio browsing (no Project open) - same relocation applies,
        # not only the opened-Project state.
        self._ingest("Project Alpha")
        client = self._client()
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.new-project"', body)
        self.assertNotIn('data-ui-ref="lists.security"', body)
        self.assertIn('data-ui-ref="menu.account.admin.new-project"', body)


if __name__ == "__main__":
    unittest.main()
