"""CLAUDE-DOCUMENT-SHOP-CUSTOMER-ROLE-01: an account identity, not an entitlement.

ROLE DESCRIBES ACCOUNT SEMANTICS. ENTITLEMENT AUTHORIZES DURABLE ACTION.

The audit that preceded this found `read_only` is not read-only: an owner
holding it can use As-Read, record governed decisions, and remove or restore
what it owns. Governance settles what that role was always meant to mean -
`kernel-object-model.md`: "an authorized read_only user remains unable to
perform admin_required actions inside a project they can now open" - so it
means NON-ADMIN, and the name is a misnomer for that contract rather than a
defect in the behaviour.

`customer` is therefore defined explicitly rather than by resemblance, and this
file pins both contracts so neither drifts into the other.

Three tests carry the weight:

`test_the_role_grants_no_creation_entitlement` - the whole point. Holding the
role must not, on its own, let anyone create durable storage.

`test_a_customer_cannot_reach_any_administrative_surface` - measured against
real routes, not assumed from the decorator list.

`test_read_only_behaviour_is_characterized_and_unchanged` - the behaviour this
tranche deliberately did NOT redefine, pinned so a later change is deliberate.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from models import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_READ_ONLY, ROLES, User, db
from services.auth import is_admin, user_can_upload_to_storage
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class RoleVocabularyTests(unittest.TestCase):

    def test_role_customer_exists_and_is_recognised(self):
        self.assertEqual(ROLE_CUSTOMER, "customer")
        self.assertIn(ROLE_CUSTOMER, ROLES)

    def test_the_existing_roles_are_preserved(self):
        self.assertEqual(ROLES, (ROLE_ADMIN, ROLE_READ_ONLY, ROLE_CUSTOMER))

    def test_customer_is_not_a_rename_of_read_only(self):
        self.assertNotEqual(ROLE_CUSTOMER, ROLE_READ_ONLY)
        self.assertIn(ROLE_READ_ONLY, ROLES, "read_only is preserved, not replaced")

    def test_no_general_rbac_framework_was_introduced(self):
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("rbac.py", "permissions.py", "authorization.py",
                         "role_registry.py"):
            self.assertNotIn(invented, services)

    def test_the_provisioning_tool_accepts_the_role(self):
        source = (_REPO_ROOT / "tools" / "create_credentials.py").read_text(encoding="utf-8")
        self.assertIn('choices=["admin", "read_only", "customer"]', source)

    def test_customer_is_not_a_project_participant_role(self):
        """A different vocabulary entirely - not extended by accident."""
        from services.case_workspace import KNOWN_PARTICIPANT_ROLES
        from routes.project_manage import ISSUABLE_ROLES

        self.assertNotIn(ROLE_CUSTOMER, KNOWN_PARTICIPANT_ROLES)
        self.assertNotIn(ROLE_CUSTOMER, ISSUABLE_ROLES)


class CustomerAuthorityTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_customer_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.owned = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="theirs.txt"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Customer Job")
                self.other = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="mine.txt"),
                    self.app, owner="someone-else", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Another Job")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="cust", role=ROLE_CUSTOMER):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 7
            session["username"] = username
            session["role"] = role
        return client

    def _source_id(self, document):
        return self.store.get(document.project_id).sources[0]["id"]

    # -- the point of the tranche --------------------------------------------

    def test_the_role_grants_no_creation_entitlement(self):
        """Holding the role must not, by itself, open durable creation."""
        client = self._client()
        for path in ("/document-shop", "/document-shop/jobs", "/upload"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)

    def test_the_entitlement_choke_point_was_not_changed(self):
        source = (_REPO_ROOT / "services" / "auth.py").read_text(encoding="utf-8")
        window = source[source.index("def user_can_upload_to_storage"):]
        window = window[:window.index("def log_in")]
        self.assertIn("return True", window)
        self.assertNotIn("customer", window,
                         "entitlement is a separate tranche; the role must not "
                         "have been wired into it here")

    def test_a_customer_is_not_an_admin(self):
        with self.app.test_request_context("/"):
            from flask import session
            session["role"] = ROLE_CUSTOMER
            self.assertFalse(is_admin())

    # -- what a customer CAN do on its own material --------------------------

    def test_a_customer_can_open_a_container_it_owns(self):
        client = self._client()
        self.assertEqual(
            client.get("/projects/%s/workspace" % self.owned.project_id).status_code, 200)

    def test_a_customer_can_use_as_read_on_its_own_source(self):
        client = self._client()
        response = client.get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.owned.project_id, self._source_id(self.owned)))
        self.assertEqual(response.status_code, 200)

    def test_a_customer_can_remove_and_restore_its_own_container(self):
        """Matches the accepted owner authority; not new authority."""
        workspace = self.store.get(self.owned.project_id)
        self.store.remove_project(workspace, actor="cust", actor_role=ROLE_CUSTOMER,
                                  reason="customer removed it")
        removed = self.store.get(self.owned.project_id)
        self.assertTrue(removed.removed_at)
        self.assertEqual(removed.removed_by, "cust")
        self.store.restore_project(removed, actor="cust", actor_role=ROLE_CUSTOMER)
        self.assertIsNone(self.store.get(self.owned.project_id).removed_at)

    # -- what a customer must NOT reach --------------------------------------

    def test_a_customer_cannot_reach_any_administrative_surface(self):
        client = self._client()
        for path in ("/security/", "/admin/developer-tools", "/operations/",
                     "/admin/reset-project-data"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)

    def test_a_customer_cannot_open_another_owners_container(self):
        client = self._client()
        self.assertEqual(
            client.get("/projects/%s/workspace" % self.other.project_id).status_code,
            404, "a generic 404, never a distinguishable refusal")

    def test_a_customer_cannot_read_another_owners_source_image(self):
        client = self._client()
        self.assertEqual(
            client.get("/projects/%s/workspace/sources/%s/image"
                       % (self.other.project_id, self._source_id(self.other))).status_code,
            404)

    def test_a_customer_cannot_see_another_owners_job_in_any_listing(self):
        client = self._client()
        for path in ("/projects", "/"):
            response = client.get(path)
            if response.status_code != 200:
                continue
            with self.subTest(path=path):
                self.assertNotIn(self.other.project_id, response.get_data(as_text=True))
                self.assertNotIn("Another Job", response.get_data(as_text=True))

    def test_the_role_alone_grants_no_capability(self):
        """Spin, procurement and project creation are not role-derived."""
        from services.environment_capabilities import (
            CAPABILITY_REGISTRY, capability_availability)

        # No capability resolution anywhere consults an account role - it is a
        # different axis entirely, and this asserts that stays true.
        source = (_REPO_ROOT / "services" / "environment_capabilities.py").read_text(
            encoding="utf-8")
        self.assertNotIn("ROLE_CUSTOMER", source)
        self.assertNotIn("read_only", source)
        self.assertTrue(CAPABILITY_REGISTRY)
        self.assertIsInstance(
            capability_availability(next(iter(CAPABILITY_REGISTRY)), None), bool)

    # -- account lifecycle ----------------------------------------------------

    def test_an_operator_can_provision_and_suspend_a_customer(self):
        from werkzeug.security import generate_password_hash

        with self.app.app_context():
            user = User(username="cust1", password_hash=generate_password_hash("pw"),
                        role=ROLE_CUSTOMER, email="cust1@example.invalid")
            db.session.add(user)
            db.session.commit()
            self.assertEqual(User.query.filter_by(username="cust1").first().role,
                             ROLE_CUSTOMER)
            self.assertTrue(user.is_active)

            from services.auth import check_credentials
            self.assertIsNotNone(check_credentials("cust1", "pw"))

            user.is_active = False
            db.session.commit()
            self.assertIsNone(check_credentials("cust1", "pw"),
                              "a suspended customer cannot sign in")
            self.assertIsNone(check_credentials("cust1", "wrong"),
                              "and the refusal is indistinguishable")

            user.is_active = True
            db.session.commit()
            self.assertIsNotNone(check_credentials("cust1", "pw"))

    def test_username_and_email_uniqueness_are_unchanged(self):
        from werkzeug.security import generate_password_hash

        with self.app.app_context():
            db.session.add(User(username="dupe", role=ROLE_CUSTOMER,
                                password_hash=generate_password_hash("pw"),
                                email="dupe@example.invalid"))
            db.session.commit()
            db.session.add(User(username="dupe", role=ROLE_CUSTOMER,
                                password_hash=generate_password_hash("pw")))
            with self.assertRaises(Exception):
                db.session.commit()
            db.session.rollback()

    def test_no_signup_invite_or_email_behaviour_was_added(self):
        rules = {str(rule) for rule in self.app.url_map.iter_rules()}
        for invented in ("/signup", "/register", "/invite", "/accept-invite",
                         "/customers/new"):
            self.assertNotIn(invented, rules)


class ReadOnlyCharacterizationTests(unittest.TestCase):
    """What read_only ACTUALLY does - pinned, deliberately not redefined."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ro_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.owned = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="ro.txt"),
                    self.app, owner="ro", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Read Only Owned")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_read_only_behaviour_is_characterized_and_unchanged(self):
        """read_only means NON-ADMIN, not "writes nothing".

        `governance/current/kernel-object-model.md` states the contract: an
        authorized read_only user remains unable to perform admin_required
        actions inside a project they can open. It says nothing about
        non-admin actions on their own material, and they can perform those.

        This tranche does NOT correct the misleading name. The established
        mechanism for narrowing one action is to gate that action - what
        CLAUDE-P38 (OBS-04) did for Go/No-Go - and redefining the role would
        change authority across every route relying on it. Pinned here so any
        future change to it is deliberate rather than incidental.
        """
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 8
            session["username"] = "ro"
            session["role"] = ROLE_READ_ONLY

        self.assertEqual(
            client.get("/projects/%s/workspace" % self.owned.project_id).status_code,
            200, "a read_only OWNER can open what it owns")
        self.assertEqual(client.get("/security/").status_code, 403,
                         "and still cannot perform admin_required actions")
        self.assertEqual(client.get("/document-shop").status_code, 403)

    def test_the_governance_contract_is_still_recorded(self):
        kernel_doc = (_REPO_ROOT / "governance" / "current" / "kernel-object-model.md")
        text = kernel_doc.read_text(encoding="utf-8")
        self.assertIn("read_only", text,
                      "the role contract must remain findable in governance")
