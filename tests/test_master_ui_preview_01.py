"""MASTERUI-PREVIEW: the Master command registry and the admin-only session
preview of the Master Workspace, exercised through real routes.

Proves the Product Owner's Master UI laws on the preview:
- 19 families, one fixed order, for every role, page and object;
- context changes a command's STATE (active / grey / current), never its
  presence, family, position or name;
- a grey command exposes no route;
- Project > Object identity and the current operation come from the governed
  identity and the registry;
- the preview is admin-only and session-scoped: customers never get it, and
  with it off every page renders the classic shell.

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
from services.case_workspace import CaseWorkspaceStore

PW = "TestCustomer!2026"
FAMILY_ORDER = ["FILE", "EDIT", "VIEW", "DOCUMENT", "DATA", "QUERY", "MODEL", "MARKET",
                "COMPARE", "CHECK", "CREATE", "PROJECT", "PORTFOLIO", "DEAL",
                "RELATIONSHIPS", "TRACE", "TOOLS", "WINDOW", "HELP"]


def _fake_parse(_self, raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="no_native_text")


def _jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (300, 200), (240, 240, 235)).save(buffer, "JPEG")
    return buffer.getvalue()


def _url_for(endpoint, **values):
    return "/" + endpoint + "?" + "&".join("%s=%s" % kv for kv in sorted(values.items()))


def _ctx(**kw):
    base = dict(identity=None, endpoint="", args={}, admin=False, developer=False,
                customer=False, username="u", url_for=_url_for, path="/x")
    base.update(kw)
    return mc.Ctx(**base)


class RegistryLaws(unittest.TestCase):
    CONTEXTS = {
        "nothing open": dict(),
        "customer": dict(customer=True),
        "admin developer": dict(admin=True, developer=True),
        "document set": dict(identity={"project": {"id": "p", "name": "P", "kind": "documents",
                                                   "source_ids": ["a"], "owned": True},
                                       "source": {"id": "a", "name": "A", "original_filename": "a.pdf"}},
                             endpoint="portal.document_shop_result", result={"examinable": True}),
        "project with two documents": dict(identity={"project": {"id": "p", "name": "P", "kind": "project",
                                                                 "source_ids": ["a", "b"], "owned": True},
                                                     "source": None},
                                           endpoint="workspace.show_workspace", args={"view": "overview"}),
    }

    def resolved(self):
        return {name: mc.resolve_master_menu(_ctx(**kw)) for name, kw in self.CONTEXTS.items()}

    def test_nineteen_families_in_one_order_everywhere(self):
        self.assertEqual(list(mc.FAMILIES), FAMILY_ORDER)
        for name, menu in self.resolved().items():
            with self.subTest(context=name):
                self.assertEqual([f["name"] for f in menu["families"]], FAMILY_ORDER)

    def test_context_changes_state_never_presence_position_or_name(self):
        shapes = {name: [(f["name"], [(c["id"], c["label"]) for c in f["items"]])
                         for f in menu["families"]]
                  for name, menu in self.resolved().items()}
        first = next(iter(shapes.values()))
        for name, shape in shapes.items():
            with self.subTest(context=name):
                self.assertEqual(shape, first)

    def test_a_grey_command_carries_no_route(self):
        for name, menu in self.resolved().items():
            for family in menu["families"]:
                for command in family["items"]:
                    if command["state"] == "grey":
                        with self.subTest(context=name, command=command["id"]):
                            self.assertTrue(command["reason"])
                            self.assertIsNone(command["href"])
                            self.assertIsNone(command["post"])
                            self.assertIsNone(command["proxy"])
                            self.assertIsNone(command["action"])

    def test_only_genuinely_missing_capability_is_marked_not_yet(self):
        not_yet = {c.id for c in mc.COMMANDS if c.not_yet}
        self.assertTrue({"market.data", "market.comparables", "market.indices",
                         "deal.pipeline", "portfolio.analytics"} <= not_yet)
        for command in mc.COMMANDS:
            if command.not_yet:
                self.assertFalse(command.href or command.post or command.proxy or command.action,
                                 command.id)

    def test_every_family_has_at_least_one_command_and_ids_are_unique(self):
        ids = [c.id for c in mc.COMMANDS]
        self.assertEqual(len(ids), len(set(ids)))
        for family in FAMILY_ORDER:
            self.assertTrue(any(c.family == family for c in mc.COMMANDS), family)

    def test_one_current_operation_names_its_family(self):
        menu = mc.resolve_master_menu(_ctx(**self.CONTEXTS["document set"]))
        self.assertEqual(menu["operation"], {"family": "DOCUMENT", "label": "View Document"})
        self.assertEqual([f["name"] for f in menu["families"] if f["current"]], ["DOCUMENT"])

    def test_examine_and_compare_follow_real_applicability(self):
        docs = mc.resolve_master_menu(_ctx(**self.CONTEXTS["document set"]))
        by_id = {c["id"]: c for f in docs["families"] for c in f["items"]}
        self.assertEqual(by_id["document.examine"]["state"], "active")
        self.assertIn("examine", by_id["document.examine"]["post"])
        done = mc.resolve_master_menu(_ctx(**dict(self.CONTEXTS["document set"], result={"examinable": False})))
        self.assertEqual({c["id"]: c for f in done["families"] for c in f["items"]}["document.examine"]["reason"],
                         "Already examined")
        two = mc.resolve_master_menu(_ctx(**self.CONTEXTS["project with two documents"]))
        compare = {c["id"]: c for f in two["families"] for c in f["items"]}["compare.documents"]
        self.assertEqual(compare["state"], "active")
        self.assertIn("compare_a=a", compare["href"])
        self.assertIn("compare_b=b", compare["href"])


class PreviewThroughRealRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_master_preview_"))
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
        self.store = CaseWorkspaceStore(str(self.tmp))

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client_for(self, username):
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

    @staticmethod
    def families_in(html):
        return [line.split('data-family="')[1].split('"')[0].upper()
                for line in html.splitlines() if 'class="master-family' in line]

    def test_off_by_default_and_the_classic_shell_is_unchanged(self):
        html = self.client_for("boss").get("/projects").get_data(as_text=True)
        self.assertNotIn('data-master-shell="on"', html)
        self.assertIn("ui-primary-nav", html)
        self.assertIn('data-ui-ref="menu.archiosk.admin.master-ui-preview"', html)

    def test_the_admin_journey_keeps_one_geography_and_one_identity(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        response = boss.post("/master-ui-preview/toggle", headers={"Referer": "http://localhost/projects"})
        self.assertEqual(response.status_code, 302)
        pages = {
            "projects": "/projects",
            "documents": "/document-shop/jobs",
            "result": "/document-shop/jobs/%s" % project_id,
            "history": "/document-shop/jobs/%s/analysis-history" % project_id,
            "search": "/find",
        }
        seen = {}
        for name, url in pages.items():
            with self.subTest(page=name):
                page = boss.get(url)
                self.assertEqual(page.status_code, 200)
                html = page.get_data(as_text=True)
                self.assertIn('data-master-shell="on"', html)
                self.assertNotIn("ui-primary-nav", html, "the classic menu rendered beside the Master Menu")
                self.assertEqual(self.families_in(html), FAMILY_ORDER)
                for anchor in ("menu", "identity", "actions", "status"):
                    self.assertIn('data-master-shell="%s"' % anchor, html)
                seen[name] = html
        # Identity: the document's set and the document itself, with its upload name.
        for name in ("result", "history"):
            self.assertIn("Castille survey", seen[name])
        self.assertIn("Castille survey.jpg", seen["result"])
        self.assertIn("No project or document open", seen["projects"])
        # Operation: the current Master command, in its family.
        self.assertIn("PORTFOLIO ▸ All Projects", seen["projects"])
        self.assertIn("FILE ▸ Open My Documents", seen["documents"])
        self.assertIn("DOCUMENT ▸ View Document", seen["result"])
        self.assertIn("TRACE ▸ Analysis History", seen["history"])
        self.assertIn("QUERY ▸ Search", seen["search"])
        # The existing Examine action, reached through the Master grammar.
        self.assertIn('action="/projects/%s/examine"' % project_id, seen["result"])
        # Unavailable capability is visible, greyed, with a reason.
        self.assertIn('title="Not available yet">Market Data</span>', seen["result"])

    def test_examine_through_the_master_action_starts_the_real_examination(self):
        boss = self.client_for("boss")
        project_id = self.upload(boss)
        boss.post("/master-ui-preview/toggle")
        html = boss.get("/document-shop/jobs/%s" % project_id).get_data(as_text=True)
        self.assertIn("Not yet examined", html)
        from services import perception_jobs
        jobs = perception_jobs.PerceptionJobStore(str(self.tmp))
        self.assertEqual(jobs.for_workspace(project_id), [])
        # The admin does not own this set? They do - they uploaded it.
        response = boss.post("/projects/%s/examine" % project_id)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(jobs.for_workspace(project_id))
        after = boss.get("/document-shop/jobs/%s" % project_id).get_data(as_text=True)
        self.assertIn("DOCUMENT ▸ View Document", after)
        self.assertIn('title="Already examined">Examine</span>', after)

    def test_the_preview_is_admin_only_and_never_reaches_a_customer(self):
        cust = self.client_for("cust")
        self.assertEqual(cust.post("/master-ui-preview/toggle").status_code, 403)
        with cust.session_transaction() as stored:
            stored["master_ui_preview"] = True
        html = cust.get("/document-shop/jobs").get_data(as_text=True)
        self.assertNotIn('data-master-shell="on"', html)
        self.assertIn('data-ui-ref="shell.customer-topbar"', html)

    def test_the_toggle_turns_it_back_off(self):
        boss = self.client_for("boss")
        boss.post("/master-ui-preview/toggle")
        self.assertIn('data-master-shell="on"', boss.get("/projects").get_data(as_text=True))
        boss.post("/master-ui-preview/toggle")
        self.assertNotIn('data-master-shell="on"', boss.get("/projects").get_data(as_text=True))

    def test_an_off_site_referrer_is_not_followed(self):
        boss = self.client_for("boss")
        response = boss.post("/master-ui-preview/toggle", headers={"Referer": "https://evil.example/x"})
        self.assertTrue(response.headers["Location"].endswith("/projects"))


if __name__ == "__main__":
    unittest.main()
