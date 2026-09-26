"""MASTERUI: every surface family migrated into the one Master Workspace.

Since the cutover the Master Workspace is the only shell. Each surface renders the 19-family Master Menu, the identity line
and the Navigator / Work / Context / GO anchors, and its superseded page-local
commands are ABSENT - not merely hidden - because a Master command now owns
them. The classic shell and its duplicate chrome are gone.

Hermetic: the parser is stubbed, no provider is reached.
"""

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app
from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
from services import master_commands as mc
from services.bhive_parser import BHiveParser, ParsedDocument
from services.capability_registry import ACTION_REGISTRY

PW = "TestCustomer!2026"
FAMILIES = [f for f in mc.FAMILIES]


def _fake_parse(_self, raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="no_native_text")


def _jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (300, 200), (240, 240, 235)).save(buffer, "JPEG")
    return buffer.getvalue()


def families_in(html):
    return [line.split('data-family="')[1].split('"')[0].upper()
            for line in html.splitlines() if 'class="master-family' in line]


class _Case(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_master_migration_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("boss", ROLE_ADMIN), ("cust", ROLE_CUSTOMER)):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=role)
                user.password_hash = generate_password_hash(PW)
                db.session.add(user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client_for(self, username, master=True):
        client = self.app.test_client()
        client.post("/login", data={"username": username, "password": PW})
        return client

    def upload(self, client, name="Castille survey"):
        with patch.object(BHiveParser, "parse", _fake_parse):
            response = client.post("/document-shop", data={
                "file": (io.BytesIO(_jpeg()), "Castille survey.jpg"), "name": name},
                content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True)[:300])
        return response.headers["Location"].rstrip("/").split("/")[-1]

    def page(self, client, url, status=200):
        response = client.get(url)
        self.assertEqual(response.status_code, status, url)
        html = response.get_data(as_text=True)
        self.assertEqual(families_in(html), FAMILIES, url)
        for anchor in ("menu", "identity", "actions", "status"):
            self.assertIn('data-master-shell="%s"' % anchor, html, (url, anchor))
        return html


class DocumentShopFamily(_Case):
    def test_desk_commands_are_master_commands_and_the_locals_are_gone(self):
        boss = self.client_for("boss")
        self.upload(boss)
        html = self.page(boss, "/document-shop/jobs")
        for ref in ("document-shop.jobs.reload", "document-shop.jobs.delete", "document-shop.jobs.new"):
            self.assertNotIn('data-ui-ref="%s"' % ref, html)
        self.assertNotIn('aria-label="Document desk views"', html)
        # Selection verbs submit the page's own selection form, through GO's registry values.
        for value in ("archive", "delete", "reanalyze", "compare"):
            self.assertIn('form="document-bulk" name="action" value="%s"' % value, html)
        # SUPERSEDED DELIBERATELY (UNIVERSAL COMPOSER INVARIANT): the retired GO
        # anchor partial (data-master-shell="go") and its page-local #document-command field ->
        # the ONE canonical Composer inside base.html's #chat-region.
        # Ask GO to act lives in the GO anchor, once.
        go = html.index('id="chat-region"')
        self.assertGreater(html.index('name="action" value="command"'), go)
        self.assertEqual(html.count('name="command_text"'), 1)
        self.assertGreater(html.index('name="command_text"'), go)
        self.assertIn('data-go-selection="document-bulk"', html)

    def test_result_has_one_action_place_and_its_conversation_in_the_go_anchor(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        html = self.page(boss, "/document-shop/jobs/%s" % project_id)
        for ref in ("document-shop.result.breadcrumb", "document-shop.result.doc-actions",
                    "document-shop.result.next"):
            self.assertNotIn('data-ui-ref="%s"' % ref, html)
        # SUPERSEDED DELIBERATELY (UNIVERSAL COMPOSER INVARIANT): the retired GO
        # anchor partial (data-master-shell="go") and its page-local #ds-question ->
        # the ONE canonical Composer inside base.html's #chat-region.
        self.assertEqual(html.count('name="question"'), 1)
        self.assertGreater(html.index('name="question"'), html.index('id="chat-region"'))
        self.assertIn('data-go-scope="DOCUMENT"', html)
        actions = html[html.index('data-master-shell="actions"'):html.index('data-master-shell="actions"') + 3000]
        for label in ("Open Original", "Examine", "Delete Document"):
            self.assertIn(label, actions)
        self.assertIn("Castille survey.jpg", html)

    def test_history_keeps_machine_ids_at_inspect_depth(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        boss.post("/projects/%s/examine" % project_id)
        plain = self.page(boss, "/document-shop/jobs/%s/analysis-history" % project_id)
        self.assertNotIn("Engine ", plain)
        self.assertIn("Initial analysis", plain)
        self.assertIn("TRACE ▸ Analysis History", plain)
        deep = self.page(boss, "/document-shop/jobs/%s/analysis-history?density=inspect" % project_id)
        self.assertIn("Engine ", deep)
        self.assertNotIn(">Back to analysis<", plain)


class ProjectsChooserSearchFamily(_Case):
    def test_projects_directory_uses_master_commands_and_the_go_anchor(self):
        boss = self.client_for("boss")
        html = self.page(boss, "/projects")
        self.assertNotIn('data-ui-ref="projects-directory.new-project"', html)
        self.assertNotIn("Other ways to start or recover work", html)
        # SUPERSEDED DELIBERATELY (UNIVERSAL COMPOSER INVARIANT): the retired GO
        # anchor partial (data-master-shell="go") and its page-local index-orientation composer ->
        # the ONE canonical Composer inside base.html's #chat-region.
        self.assertEqual(html.count('id="dock-composer-input"'), 1)
        self.assertGreater(html.index('action="/gateway/orientation"'), html.index('id="chat-region"'))
        self.assertNotIn("index-orientation", html)

    def test_chooser_is_a_state_of_the_one_shell(self):
        html = self.page(self.client_for("boss"), "/projects/choose")
        self.assertNotIn('class="gateway-shell', html)
        self.assertIn("FILE ▸ Open Project", html)

    def test_search(self):
        html = self.page(self.client_for("boss"), "/find")
        self.assertIn("QUERY ▸ Search", html)


class WorkspaceFamily(_Case):
    def test_workspace_states_have_no_local_back_links(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        for view in ("overview", "requirements", "files", "spin", "new-case"):
            with self.subTest(view=view):
                html = self.page(boss, "/projects/%s/workspace?view=%s" % (project_id, view))
                self.assertNotIn("&larr; Overview</a>", html)
                self.assertNotIn("&larr; Projects</a>", html)
                self.assertNotIn("&larr; Back to Overview</a>", html)

    def test_a_confirm_page_keeps_the_identity(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        from services.case_workspace import CaseWorkspaceStore
        source = CaseWorkspaceStore(str(self.tmp)).get(project_id).sources[0]
        response = boss.post("/document-shop/jobs/%s/sources/%s/remove" % (project_id, source["id"]))
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertEqual(families_in(html), FAMILIES)
        self.assertIn("Castille survey", html[html.index('data-master-shell="identity"'):])


class PlanningInspectHelpFamilies(_Case):
    def test_planning(self):
        html = self.page(self.client_for("boss"), "/planning-zoning")
        self.assertIn("MODEL ▸ Planning &amp; Zoning Analysis", html)
        self.assertNotIn(">Saved Planning &amp; Zoning studies</a>", html)

    def test_help_renders_inside_the_one_shell(self):
        html = self.page(self.client_for("boss"), "/help")
        self.assertIn("HELP ▸ Help Centre", html)
        self.assertNotIn('<body class="pm">', html)

    def test_developer_tools(self):
        boss = self.client_for("boss")
        boss.post("/developer-mode/toggle")
        html = self.page(boss, "/admin/developer-tools")
        self.assertIn("TOOLS ▸ Developer Tools", html)
        self.assertNotIn("&larr; Back to Projects</a>", html)


class CustomerConvergence(_Case):
    def test_customers_get_the_same_workspace(self):
        cust = self.client_for("cust")
        project_id = self.upload(cust)
        for url in ("/document-shop/jobs", "/document-shop/jobs/%s" % project_id):
            with self.subTest(url=url):
                html = self.page(cust, url)
                self.assertNotIn('data-ui-ref="shell.customer-topbar"', html)
                self.assertIn('data-master-shell="navigator"', html)
                # Role greys; it never removes, and a greyed command exposes no route.
                self.assertIn('>New Project…</span>', html)
                self.assertNotIn('href="/admin/developer-tools"', html)
        self.assertIn("Castille survey", self.page(cust, "/document-shop/jobs/%s" % project_id))


class RegistryConvergence(unittest.TestCase):
    def test_master_selection_commands_are_gos_governed_actions(self):
        linked = [c for c in mc.COMMANDS if c.capability]
        self.assertEqual({c.capability for c in linked},
                         {"ARCHIVE_ITEMS", "DELETE_ITEMS", "REANALYZE_ITEMS", "COMPARE_ITEMS"})
        for command in linked:
            self.assertIn(command.capability, ACTION_REGISTRY)
            self.assertEqual(mc.registry_bulk(command.capability),
                             ACTION_REGISTRY[command.capability]["bulk_action"])


if __name__ == "__main__":
    unittest.main()
