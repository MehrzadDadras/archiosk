"""CLAUDE-DOCUMENT-SHOP-CUSTOMER-ENTITLEMENT-01A: two authorities, not one.

PROJECT UPLOAD AUTHORITY AND DOCUMENT SHOP CONTAINER-CREATION AUTHORITY ARE
DISTINCT.

The first attempt at this treated them as one question and made
`user_can_upload_to_storage` role-based. The full gate caught it: 21 existing
tests establish that a `read_only` account can add documents to a Project it
owns, and folding origination into that helper would have removed real
authority to make a new feature fit. This tranche is the correction - the
Project helper is untouched, and a sibling answers the narrower question.

Four tests carry the weight:

`test_read_only_retains_project_upload_authority` - the regression contract.
`test_read_only_cannot_originate_a_document_shop_container` - the other half.
`test_a_filename_cannot_choose_how_bytes_are_rendered` - the source_file seam.
`test_customer_a_cannot_learn_anything_about_customer_b` - isolation.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from models import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_READ_ONLY
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _png(width=40, height=30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (250, 250, 250)).save(buffer, "PNG")
    return buffer.getvalue()


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class AuthorityDistinctionTests(unittest.TestCase):
    """The two questions, asked directly."""

    def setUp(self):
        import app as app_module
        self.app = app_module.create_app("testing")

    def _ask(self, helper, role):
        with self.app.test_request_context("/"):
            from flask import session
            session["role"] = role
            return helper()

    def test_project_upload_authority_is_unchanged_for_every_role(self):
        """The helper 21 existing tests depend on. Untouched."""
        from services.auth import user_can_upload_to_storage

        for role in (ROLE_ADMIN, ROLE_READ_ONLY, ROLE_CUSTOMER, None, ""):
            with self.subTest(role=role):
                self.assertTrue(self._ask(user_can_upload_to_storage, role))

    def test_origination_authority_is_narrower(self):
        from services.auth import user_can_create_document_shop_container

        self.assertTrue(self._ask(user_can_create_document_shop_container, ROLE_ADMIN))
        self.assertTrue(self._ask(user_can_create_document_shop_container, ROLE_CUSTOMER))
        self.assertFalse(self._ask(user_can_create_document_shop_container, ROLE_READ_ONLY))

    def test_origination_fails_closed_for_an_unknown_role(self):
        from services.auth import user_can_create_document_shop_container

        for role in (None, "", "something_new"):
            with self.subTest(role=role):
                self.assertFalse(
                    self._ask(user_can_create_document_shop_container, role))

    def test_the_two_helpers_are_genuinely_different_questions(self):
        from services.auth import (
            user_can_create_document_shop_container, user_can_upload_to_storage)

        self.assertTrue(self._ask(user_can_upload_to_storage, ROLE_READ_ONLY))
        self.assertFalse(
            self._ask(user_can_create_document_shop_container, ROLE_READ_ONLY),
            "read_only is the case that proves the axes are not the same")

    def test_no_route_re_derives_either_answer(self):
        for module in ("routes/portal.py", "routes/workspace.py"):
            source = (_REPO_ROOT / module).read_text(encoding="utf-8")
            with self.subTest(module=module):
                self.assertNotIn("ROLE_CUSTOMER", source)
                self.assertNotIn("ROLE_READ_ONLY", source)

    def test_no_permissions_framework_was_introduced(self):
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("rbac.py", "permissions.py", "authorization.py",
                         "entitlements.py"):
            self.assertNotIn(invented, services)


class ReadOnlyRegressionTests(unittest.TestCase):
    """The contract the first attempt broke. Now a required regression."""

    def setUp(self):
        import app as app_module
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ro_reg_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.project = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="rfp.pdf"),
                    self.app, owner="ro", operating_environment=CLIENT_OWNER,
                    project_name="Read Only Project")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, role=ROLE_READ_ONLY, username="ro"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 3
            session["username"] = username
            session["role"] = role
        return client

    def test_read_only_retains_project_upload_authority(self):
        """Established by 21 pre-existing tests; not superseded here."""
        from services.auth import user_can_upload_to_storage

        with self.app.test_request_context("/"):
            from flask import session
            session["role"] = ROLE_READ_ONLY
            self.assertTrue(user_can_upload_to_storage())

    def test_read_only_can_still_reach_the_add_document_surface(self):
        client = self._client()
        response = client.get("/projects/%s/workspace" % self.project.project_id)
        self.assertEqual(response.status_code, 200,
                         "existing Project participation is untouched")

    def test_read_only_cannot_originate_a_document_shop_container(self):
        client = self._client()
        self.assertEqual(client.get("/document-shop").status_code, 403)

    def test_read_only_may_still_view_document_shop_jobs_it_can_access(self):
        """Viewing is not originating - the listing must not use the stronger gate."""
        client = self._client()
        self.assertEqual(client.get("/document-shop/jobs").status_code, 200)

    def test_read_only_is_not_offered_an_intake_control_it_cannot_use(self):
        body = self._client().get("/document-shop/jobs").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="document-shop.jobs.new"', body)


class CustomerJourneyTests(unittest.TestCase):

    def setUp(self):
        import app as app_module
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ent_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="anna", role=ROLE_CUSTOMER, user_id=11):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user_id
            session["username"] = username
            session["role"] = role
        return client

    def _csrf(self, client, path="/document-shop"):
        body = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf-token" content="([^"]+)"', body).group(1)

    def _create_job(self, client, name="scan.png", label=None):
        return client.post("/document-shop", data={
            "csrf_token": self._csrf(client),
            "file": (io.BytesIO(_png()), name),
            "name": label or ("Job %s" % uuid.uuid4().hex[:8])},
            content_type="multipart/form-data")

    def test_a_customer_completes_the_whole_journey(self):
        client = self._client()
        self.assertEqual(client.get("/document-shop").status_code, 200)

        created = self._create_job(client, label="Anna Job")
        self.assertEqual(created.status_code, 302)
        location = created.headers["Location"]
        project_id = location.rstrip("/").split("/")[-1]  # CLAUDE-DOCUMENT-SHOP-DOOR-01
        workspace = self.store.get(project_id)
        source_id = workspace.sources[0]["id"]

        self.assertEqual(workspace.owner, "anna")
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX)
        self.assertEqual(workspace.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)

        self.assertEqual(client.get(location).status_code, 200)
        self.assertEqual(client.get(
            "/projects/%s/workspace/sources/%s/image"
            % (project_id, source_id)).status_code, 200)

        jobs = client.get("/document-shop/jobs")
        self.assertEqual(jobs.status_code, 200)
        self.assertIn(project_id, jobs.get_data(as_text=True))
        self.assertIn('data-ui-ref="document-shop.jobs.new"',
                      jobs.get_data(as_text=True))

        page = client.get("/projects/%s/workspace" % project_id).get_data(as_text=True)
        token = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
        client.post("/projects/%s/workspace/remove" % project_id,
                    data={"csrf_token": token, "confirm": "yes", "reason": "done"})
        self.assertTrue(self.store.get(project_id).removed_at)
        client.post("/projects/%s/workspace/restore" % project_id,
                    data={"csrf_token": token})
        self.assertIsNone(self.store.get(project_id).removed_at)

        self.assertIn(client.get("/logout").status_code, (200, 302))

    def test_an_admin_is_unaffected(self):
        client = self._client(username="root", role=ROLE_ADMIN, user_id=13)
        self.assertEqual(client.get("/document-shop").status_code, 200)
        self.assertEqual(self._create_job(client, label="Admin Job").status_code, 302)

    def test_customer_a_cannot_learn_anything_about_customer_b(self):
        anna = self._client(username="anna", user_id=11)
        ben = self._client(username="ben", user_id=12)
        created = self._create_job(anna, label="Anna Private")
        pid = created.headers["Location"].rstrip("/").split("/")[-1]
        sid = self.store.get(pid).sources[0]["id"]

        for label, path in {
            "workspace": "/projects/%s/workspace" % pid,
            "as-read": "/projects/%s/workspace/sources/%s/understanding" % (pid, sid),
            "source image": "/projects/%s/workspace/sources/%s/image" % (pid, sid),
            "source file": "/projects/%s/workspace/sources/%s/file" % (pid, sid),
        }.items():
            with self.subTest(surface=label):
                self.assertEqual(ben.get(path).status_code, 404)

        jobs = ben.get("/document-shop/jobs").get_data(as_text=True)
        self.assertNotIn(pid, jobs)
        self.assertNotIn("Anna Private", jobs)

    def test_the_role_alone_grants_no_project_or_admin_authority(self):
        client = self._client()
        for path in ("/upload", "/security/", "/admin/developer-tools",
                     "/operations/", "/admin/reset-project-data"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)

    def test_a_customer_job_carries_no_project_semantics(self):
        client = self._client()
        created = self._create_job(client, label="No Project Semantics")
        pid = created.headers["Location"].rstrip("/").split("/")[-1]
        workspace = self.store.get(pid)
        self.assertIsNone(workspace.operating_environment)
        self.assertIsNone(workspace.lifecycle_stage)
        body = client.get("/projects/%s/workspace?view=overview" % pid).get_data(as_text=True)
        for engagement in ("Project Operating Environment", "Go / No-Go",
                           "Project Briefing"):
            with self.subTest(offer=engagement):
                self.assertNotIn(engagement, body)
        self.assertNotIn('data-ui-ref="toolbox.spin"', body)


class SourceFileHardeningTests(unittest.TestCase):
    """CONTENT TYPE MUST COME FROM VERIFIED SOURCE FACTS, NOT A FILENAME."""

    def setUp(self):
        import app as app_module
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_sf_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.doc = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="real.png"),
                    self.app, owner="anna", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Hardening Job")
        self.pid = self.doc.project_id
        self.sid = self.store.get(self.pid).sources[0]["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 11
            session["username"] = "anna"
            session["role"] = ROLE_CUSTOMER
        return client

    def _url(self, download=False):
        return "/projects/%s/workspace/sources/%s/file%s" % (
            self.pid, self.sid, "?download=1" if download else "")

    def _rename_source(self, new_name):
        workspace = self.store.get(self.pid)
        workspace.sources[0]["name"] = new_name
        self.store.save(workspace)

    def test_a_genuine_file_still_serves_correctly(self):
        response = self._client().get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.get_data(), _png())

    def test_a_filename_cannot_choose_how_bytes_are_rendered(self):
        self._rename_source("evil.jpg")
        response = self._client().get(self._url())
        self.assertEqual(response.mimetype, "application/octet-stream")
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))

    def test_an_unknown_extension_never_guesses_a_type(self):
        for name in ("payload.html", "payload.svg", "payload.js", "payload.xyz"):
            with self.subTest(name=name):
                self._rename_source(name)
                response = self._client().get(self._url())
                self.assertEqual(response.mimetype, "application/octet-stream")
                self.assertIn("attachment",
                              response.headers.get("Content-Disposition", ""))

    def test_guess_type_is_no_longer_called_for_governed_sources(self):
        source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        window = source[source.index("def source_file("):
                        source.index("def replace_source_form(")]
        code = [line for line in window.splitlines()
                if not line.strip().startswith("#")]
        self.assertNotIn("guess_type", "\n".join(code))

    def test_the_content_type_map_is_closed(self):
        from routes.workspace import _GOVERNED_SOURCE_CONTENT_TYPES

        for extension in self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]:
            with self.subTest(extension=extension):
                self.assertIn(extension, _GOVERNED_SOURCE_CONTENT_TYPES)
        for active in (".html", ".htm", ".svg", ".js", ".xml"):
            with self.subTest(active=active):
                self.assertNotIn(active, _GOVERNED_SOURCE_CONTENT_TYPES)

    def test_nosniff_is_set(self):
        self.assertEqual(
            self._client().get(self._url()).headers.get("X-Content-Type-Options"),
            "nosniff")

    def test_download_behaviour_remains_usable(self):
        response = self._client().get(self._url(download=True))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.get_data(), _png())

    def test_image_preview_route_is_unchanged(self):
        response = self._client().get(
            "/projects/%s/workspace/sources/%s/image" % (self.pid, self.sid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertEqual(response.get_data(), _png())

    def test_the_two_routes_were_not_merged(self):
        source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertIn("def source_image(", source)
        self.assertIn("def source_file(", source)

    def test_no_upload_format_was_widened(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        for never in (".html", ".svg", ".tif", ".tiff", ".heic", ".webp"):
            self.assertNotIn(never, allowed)

    def test_serving_causes_no_provider_egress(self):
        from services import llm_gateway

        def detonate(*_args, **_kwargs):
            raise AssertionError("source serving attempted external egress")

        with patch.object(llm_gateway, "call_llm_json", detonate), \
                patch.object(llm_gateway, "call_gemini_json", detonate), \
                patch.object(llm_gateway, "anthropic_client", detonate):
            client = self._client()
            self.assertEqual(client.get(self._url()).status_code, 200)
            self.assertEqual(client.get(
                "/projects/%s/workspace/sources/%s/image"
                % (self.pid, self.sid)).status_code, 200)
