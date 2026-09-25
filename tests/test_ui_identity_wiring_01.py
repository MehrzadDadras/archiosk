"""MASTERUI-BLOCK1: `ui_identity()` and the opt-in Master UI shell partials.

Two things are proven here.

1. RESOLUTION. `resolve_ui_identity` names the open container and source from
   the governed records, the same way whatever shape a page passed them in
   (`workspace`, only `project_id`, `selected_source`, `result`, `report`), and
   resolves to NOTHING for someone the project access rule would refuse.

2. WIRING. A page that opts in with `{% block master_shell %}on{% endblock %}`
   renders the Master Menu, Identity Bar and Status Bar in place of the old top
   bars; a page that does not renders exactly as before and never calls the
   resolver. No production page opts in yet - that is a later, separate cutover.

Hermetic: the parser is stubbed, no provider is reached.
"""

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import render_template_string, session
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

import app as app_module
from app import create_app, resolve_ui_identity
from models import ROLE_CUSTOMER, User, db
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore
from services.ingestion import attach_document_shop_sources, ingest_upload

PW = "TestCustomer!2026"

OPTED_IN = ('{% extends "base.html" %}{% block master_shell %}on{% endblock %}'
            '{% block content %}<p id="page-body">body</p>{% endblock %}')
NOT_OPTED_IN = ('{% extends "base.html" %}'
                '{% block content %}<p id="page-body">body</p>{% endblock %}')


def _fake_parse(_self, raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
        text_extraction_status="extracted")


class _Case(unittest.TestCase):
    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ui_identity_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name in ("cust", "stranger"):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=ROLE_CUSTOMER)
                user.password_hash = generate_password_hash(PW)
                db.session.add(user)
        db.session.commit()
        self.request_contexts = []
        self.store = CaseWorkspaceStore(str(self.tmp))
        with patch.object(BHiveParser, "parse", _fake_parse):
            self.document = ingest_upload(
                FileStorage(stream=io.BytesIO(b"engagement"), filename="job.txt"),
                self.app, owner="cust", operating_environment=None,
                container_state=CONTAINER_STATE_BLACK_BOX,
                project_name="Castille Survey Set")
            attach_document_shop_sources(
                self.app, self.store.get(self.document.project_id),
                [FileStorage(stream=io.BytesIO(b"%PDF-1.4 x"), filename="RS501 site plan.pdf")],
                owner="cust")
        self.workspace = self.store.get(self.document.project_id)
        self.attached = next(s for s in self.workspace.sources
                             if s.get("original_filename") == "RS501 site plan.pdf")

    def tearDown(self):
        # Request contexts first: each one's teardown needs the app context.
        while self.request_contexts:
            self.request_contexts.pop().pop()
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def session_values(self, username):
        client = self.app.test_client()
        client.post("/login", data={"username": username, "password": PW})
        with client.session_transaction() as stored:
            return dict(stored)

    def as_user(self, username):
        """A request context signed in as `username`, the way a real login is."""
        values = self.session_values(username)
        context = self.app.test_request_context("/")
        context.push()
        self.request_contexts.append(context)
        session.update(values)


class ResolutionTests(_Case):
    def test_project_id_alone_resolves_the_governed_container(self):
        self.as_user("cust")
        identity = resolve_ui_identity({"project_id": self.document.project_id})
        self.assertEqual(identity["project"]["id"], self.document.project_id)
        self.assertEqual(identity["project"]["name"], "Castille Survey Set")
        self.assertEqual(identity["project"]["kind"], "documents")
        self.assertIsNone(identity["source"])

    def test_every_page_shape_names_the_same_source_the_same_way(self):
        self.as_user("cust")
        sid = self.attached["id"]
        shapes = {
            "selected_source": {"workspace": self.workspace, "selected_source": {"id": sid}},
            "source": {"project_id": self.document.project_id, "source": {"id": sid, "name": "stale copy"}},
            "result": {"project_id": self.document.project_id, "result": {"source_id": sid}},
            "report": {"project_id": self.document.project_id, "report": {"source": {"id": sid}}},
            "source_id": {"project_id": self.document.project_id, "source_id": sid},
        }
        expected = {"id": sid, "name": self.attached["name"],
                    "original_filename": "RS501 site plan.pdf"}
        for label, values in shapes.items():
            with self.subTest(shape=label):
                identity = resolve_ui_identity(values)
                self.assertEqual(identity["source"], expected,
                                 "a page-built dict leaked into the identity")
                self.assertEqual(identity["project"]["name"], "Castille Survey Set")

    def test_the_stored_name_is_never_offered_as_the_original_filename(self):
        self.as_user("cust")
        identity = resolve_ui_identity({"workspace": self.workspace,
                                        "selected_source": {"id": self.attached["id"]}})
        stored_name = Path(self.attached["file_path"]).name
        self.assertNotEqual(identity["source"]["original_filename"], stored_name)

    def test_a_source_that_does_not_belong_to_the_project_resolves_to_none(self):
        self.as_user("cust")
        identity = resolve_ui_identity({"workspace": self.workspace,
                                        "selected_source": {"id": "not-a-real-source"}})
        self.assertIsNotNone(identity["project"])
        self.assertIsNone(identity["source"])

    def test_someone_the_access_rule_refuses_gets_no_identity(self):
        self.as_user("stranger")
        for values in ({"project_id": self.document.project_id},
                       {"workspace": self.workspace, "selected_source": {"id": self.attached["id"]}}):
            with self.subTest(values=sorted(values)):
                self.assertEqual(resolve_ui_identity(values), {"project": None, "source": None})

    def test_no_context_means_no_identity(self):
        self.as_user("cust")
        for values in ({}, {"project_id": None}, {"project_id": "does-not-exist"}):
            with self.subTest(values=values):
                self.assertEqual(resolve_ui_identity(values), {"project": None, "source": None})

    def test_a_legacy_source_reads_as_not_recorded_rather_than_reconstructed(self):
        self.as_user("cust")
        legacy = SimpleNamespace(
            project_id="legacy-1", display_title="", container_state=None, owner="cust",
            access_allow_list=[], document_desk_state="active", project_code="LGC",
            sources=[{"id": "s1", "name": "Old sheet", "file_path": "/x/abc123_old.pdf"}])
        document = SimpleNamespace(project_id="legacy-1", filename="founding.pdf")
        identity = resolve_ui_identity({"workspace": legacy, "document": document,
                                        "source_id": "s1"})
        self.assertEqual(identity["project"]["name"], "founding.pdf",
                         "an empty display title falls back to the filename")
        self.assertEqual(identity["project"]["kind"], "project")
        self.assertEqual(identity["project"]["code"], "LGC")
        self.assertIsNone(identity["source"]["original_filename"])

    def test_resolution_writes_nothing(self):
        self.as_user("cust")
        before = {p: p.stat().st_mtime_ns for p in self.tmp.rglob("*") if p.is_file()}
        resolve_ui_identity({"project_id": self.document.project_id,
                             "source_id": self.attached["id"]})
        after = {p: p.stat().st_mtime_ns for p in self.tmp.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


class ShellWiringTests(_Case):
    def render(self, source, **context):
        return render_template_string(source, **context)

    def test_an_opted_in_page_renders_the_three_partials_in_place_of_the_old_bars(self):
        self.as_user("cust")
        html = self.render(OPTED_IN, project_id=self.document.project_id,
                           result={"source_id": self.attached["id"]})
        for region in ("menu", "identity", "actions", "status"):
            self.assertIn('data-master-shell="%s"' % region, html)
        self.assertIn("Castille Survey Set", html)
        self.assertIn(self.attached["name"], html)
        self.assertIn("RS501 site plan.pdf", html)
        self.assertNotIn('data-ui-ref="shell.customer-topbar"', html)
        self.assertNotIn("ui-primary-nav", html)
        self.assertIn('id="page-body"', html)
        self.assertIn('<meta name="archiosk-master-shell" content="on">', html)
        # Menu before identity before content before status: fixed anatomy.
        order = [html.index('data-master-shell="menu"'), html.index('data-master-shell="identity"'),
                 html.index('id="page-body"'), html.index('data-master-shell="status"')]
        self.assertEqual(order, sorted(order))

    def test_every_signed_in_page_is_the_master_workspace(self):
        """SUPERSEDED DELIBERATELY (MASTERUI cutover): this asserted a page that did
        not opt in stayed classic. The Master Workspace is now the only shell, so a
        page renders it without opting in, and the retired customer top bar is gone."""
        self.as_user("cust")
        html = self.render(NOT_OPTED_IN, project_id=self.document.project_id)
        self.assertIn('data-master-shell="menu"', html)
        self.assertNotIn('data-ui-ref="shell.customer-topbar"', html)

    def test_role_greys_what_a_customer_may_not_use_and_removes_nothing(self):
        """SUPERSEDED DELIBERATELY (MASTERUI-PREVIEW, Product Owner Master UI
        laws 6-8): this asserted that a customer's menu OMITTED staff commands.
        The Master UI rule is the opposite - role changes applicability, never
        presence - so those commands are now present, greyed with a reason, and
        carry no route."""
        self.as_user("cust")
        html = self.render(OPTED_IN, project_id=self.document.project_id)
        for label in ("New Project…", "Open Project…", "Security", "Diagnostics", "Developer Tools"):
            self.assertIn('>%s</span>' % label, html, label)
        for route in ("/upload", "/security/", "/developer/diagnostics", "/admin/developer-tools"):
            self.assertNotIn('href="%s"' % route, html, "a greyed command exposed its route")
        self.assertIn("Document Upload…", html)
        self.assertIn("Open My Documents", html)

    def test_state_greys_in_place_with_a_reason_instead_of_removing(self):
        self.as_user("cust")
        without = self.render(OPTED_IN, project_id=self.document.project_id)
        with_source = self.render(OPTED_IN, project_id=self.document.project_id,
                                  source_id=self.attached["id"])
        self.assertIn('<span aria-disabled="true" title="Open a document first">Open Original</span>',
                      without)
        self.assertIn("/workspace/sources/%s/file" % self.attached["id"], with_source)
        self.assertNotIn('title="Open a document first">Open Original', with_source)
        # The menu's families do not change with context: all 19, in order.
        families = lambda h: [line.split('data-family="')[1].split('"')[0]
                              for line in h.splitlines() if 'data-family="' in line]
        self.assertEqual(families(without), families(with_source))
        self.assertEqual(families(without), [
            "file", "edit", "view", "document", "data", "query", "model", "market",
            "compare", "check", "create", "project", "portfolio", "deal",
            "relationships", "trace", "tools", "window", "help"])

    def test_a_refused_viewer_keeps_the_anchor_but_learns_nothing(self):
        """SUPERSEDED DELIBERATELY: the identity line used to disappear for a
        refused viewer. It is a fixed anchor now, so it stays - saying nothing
        is open - and still names nothing."""
        self.as_user("stranger")
        html = self.render(OPTED_IN, project_id=self.document.project_id)
        self.assertIn('data-master-shell="menu"', html)
        self.assertIn('data-master-shell="identity"', html)
        self.assertIn("No project or document open", html)
        self.assertNotIn("Castille Survey Set", html)

    def test_real_pages_render_the_master_workspace(self):
        """SUPERSEDED DELIBERATELY (MASTERUI cutover): real pages used to render
        the classic shell until the opt-in; they are the Master Workspace now."""
        client = self.app.test_client()
        client.post("/login", data={"username": "cust", "password": PW})
        for url in ("/document-shop/jobs", "/document-shop/jobs/%s" % self.document.project_id):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('data-master-shell="on"', response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
