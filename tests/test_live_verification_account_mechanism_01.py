"""
CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01 - the sanctioned,
auditable, ephemeral verification identity (services/verification_
access.py, models.VerificationAccessToken, tools/manage_verification_
access.py, routes/portal.py's verification_access_login/
verification_access_end).

Covers the full lifecycle: create -> token is single-use/expiring/only-
its-hash-stored -> login via the token establishes a real admin session
-> the session is visibly, unmistakably distinct from a real admin's own
-> both operating environments are reachable (is_admin has zero
operating_environment coupling, same as every other admin session) ->
self-revoke deletes the identity and ends the session in one step ->
residue check (no matching User row remains) -> the SAME token can never
be replayed -> ordinary/non-admin sessions cannot invoke self-revoke at
all, and a real admin's own session is never mistaken for the
verification identity.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT


class _BaseVerificationAccessTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_verify_access_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="real_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="real_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class ServiceLayerLifecycleTests(_BaseVerificationAccessTestCase):
    """Direct services.verification_access function-level coverage -
    mirrors this repo's own established pattern of testing the service
    layer independent of the HTTP layer (see test_p40vw9_files_display_
    and_folder_architecture.py's own service/route split)."""

    def test_create_produces_admin_role_account_and_unusable_password(self):
        from services.verification_access import VERIFICATION_ACCOUNT_USERNAME, create_verification_access
        from werkzeug.security import check_password_hash

        with self.flask_app.app_context():
            user, raw_token = create_verification_access()
            self.assertEqual(user.username, VERIFICATION_ACCOUNT_USERNAME)
            self.assertEqual(user.role, "admin")
            self.assertTrue(user.is_active)
            # Genuinely unusable via ordinary username/password login - no
            # password anyone was ever given could match this hash.
            self.assertFalse(check_password_hash(user.password_hash, ""))
            self.assertFalse(check_password_hash(user.password_hash, "password"))
            self.assertTrue(len(raw_token) > 20)

    def test_only_the_token_hash_is_ever_persisted_not_the_raw_secret(self):
        from models import VerificationAccessToken
        from services.verification_access import create_verification_access

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
            token_row = VerificationAccessToken.query.first()
            self.assertIsNotNone(token_row)
            self.assertNotEqual(token_row.token_hash, raw_token)
            self.assertEqual(len(token_row.token_hash), 64)  # sha256 hex digest

    def test_create_is_idempotent_and_supersedes_the_prior_unused_token(self):
        from services.verification_access import create_verification_access, get_valid_verification_token

        with self.flask_app.app_context():
            user_1, raw_token_1 = create_verification_access()
            user_2, raw_token_2 = create_verification_access()
            self.assertEqual(user_1.id, user_2.id)  # same account reused, not a second one
            self.assertIsNone(get_valid_verification_token(raw_token_1))  # superseded
            self.assertIsNotNone(get_valid_verification_token(raw_token_2))  # the fresh one still works

    def test_expired_token_is_rejected(self):
        from datetime import datetime, timedelta, timezone
        from models import VerificationAccessToken, db
        from services.verification_access import create_verification_access, get_valid_verification_token

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
            token_row = VerificationAccessToken.query.first()
            token_row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            db.session.commit()
            self.assertIsNone(get_valid_verification_token(raw_token))

    def test_token_is_single_use(self):
        from services.verification_access import (
            consume_verification_token, create_verification_access, get_valid_verification_token,
        )

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
            token_row = get_valid_verification_token(raw_token)
            self.assertIsNotNone(token_row)
            consume_verification_token(token_row)
            self.assertIsNone(get_valid_verification_token(raw_token))  # cannot be replayed

    def test_revoke_removes_account_and_all_its_tokens_residue_check(self):
        from models import User, VerificationAccessToken
        from services.verification_access import (
            VERIFICATION_ACCOUNT_USERNAME, create_verification_access, revoke_verification_access,
        )

        with self.flask_app.app_context():
            user, _raw_token = create_verification_access()
            user_id = user.id
            self.assertTrue(revoke_verification_access())
            self.assertEqual(User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).count(), 0)
            self.assertEqual(VerificationAccessToken.query.filter_by(user_id=user_id).count(), 0)

    def test_revoke_with_nothing_active_is_a_safe_no_op(self):
        from services.verification_access import revoke_verification_access

        with self.flask_app.app_context():
            self.assertFalse(revoke_verification_access())


class RouteLevelLifecycleTests(_BaseVerificationAccessTestCase):
    """Full HTTP round trip - the actual mechanism a real browser
    (or this session's own browser-automation tool) exercises."""

    def test_valid_link_logs_in_as_the_verification_identity(self):
        from services.verification_access import VERIFICATION_ACCOUNT_USERNAME, create_verification_access

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client = self.flask_app.test_client()
        resp = client.get(f"/verification-access/{raw_token}")
        self.assertEqual(resp.status_code, 302)
        with client.session_transaction() as sess:
            self.assertEqual(sess["username"], VERIFICATION_ACCOUNT_USERNAME)
            self.assertEqual(sess["role"], "admin")

    def test_the_same_link_cannot_be_used_twice(self):
        from services.verification_access import create_verification_access

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client_a = self.flask_app.test_client()
        client_a.get(f"/verification-access/{raw_token}")

        client_b = self.flask_app.test_client()
        client_b.get(f"/verification-access/{raw_token}")
        with client_b.session_transaction() as sess:
            self.assertNotIn("username", sess)  # second attempt never established a session

    def test_invalid_link_never_establishes_a_session(self):
        client = self.flask_app.test_client()
        resp = client.get("/verification-access/not-a-real-token")
        self.assertEqual(resp.status_code, 302)
        with client.session_transaction() as sess:
            self.assertNotIn("username", sess)

    def test_verification_session_badge_renders_and_is_distinguishable_from_developer_mode(self):
        from services.verification_access import create_verification_access

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client = self.flask_app.test_client()
        client.get(f"/verification-access/{raw_token}")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.verification-session-badge"', body)
        self.assertIn('data-ui-ref="menu.verification-session-end"', body)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)

    def test_real_admin_session_never_shows_the_verification_badge(self):
        client = self._client_as("real_admin", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.verification-session-badge"', body)

    def test_self_revoke_ends_session_and_leaves_no_residue(self):
        from models import User
        from services.verification_access import VERIFICATION_ACCOUNT_USERNAME, create_verification_access

        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client = self.flask_app.test_client()
        client.get(f"/verification-access/{raw_token}")

        resp = client.post("/verification-access/end")
        self.assertEqual(resp.status_code, 302)
        with client.session_transaction() as sess:
            self.assertNotIn("username", sess)  # logged out

        with self.flask_app.app_context():
            self.assertEqual(User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).count(), 0)

        # A subsequent admin-gated request with this same (now stale)
        # client must behave as unauthenticated, not silently privileged.
        resp2 = client.post("/verification-access/end")
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/login", resp2.headers["Location"])

    def test_ordinary_anonymous_session_cannot_invoke_self_revoke(self):
        client = self.flask_app.test_client()
        resp = client.post("/verification-access/end")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_real_readonly_session_cannot_invoke_self_revoke(self):
        client = self._client_as("real_reader", 2, role="read_only")
        resp = client.post("/verification-access/end")
        self.assertEqual(resp.status_code, 403)

    def test_real_admin_session_cannot_invoke_self_revoke_even_though_admin(self):
        # CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01's own explicit
        # "no backdoor" requirement: being an admin is not sufficient -
        # the session must actually BE the verification identity, so a
        # real admin can never accidentally (or deliberately) use this
        # route to delete the verification account out from under an
        # in-progress verification pass, nor use it against any other
        # account.
        from services.verification_access import create_verification_access

        with self.flask_app.app_context():
            create_verification_access()
        client = self._client_as("real_admin", 1)
        resp = client.post("/verification-access/end")
        self.assertEqual(resp.status_code, 403)

        # The verification identity this test seeded must be untouched.
        from models import User
        from services.verification_access import VERIFICATION_ACCOUNT_USERNAME
        with self.flask_app.app_context():
            self.assertEqual(User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).count(), 1)

    def test_real_admin_own_account_is_never_touched_by_this_mechanism(self):
        from models import User, db
        from services.verification_access import create_verification_access

        with self.flask_app.app_context():
            create_verification_access()
            real_admin_before = User.query.filter_by(username="real_admin").first()
            self.assertIsNotNone(real_admin_before)
            real_admin_id = real_admin_before.id

        with self.flask_app.app_context():
            from services.verification_access import revoke_verification_access
            revoke_verification_access()
            real_admin_after = db.session.get(User, real_admin_id)
            self.assertIsNotNone(real_admin_after)
            self.assertEqual(real_admin_after.username, "real_admin")


class OperatingEnvironmentReachabilityTests(_BaseVerificationAccessTestCase):
    """CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01's own explicit
    requirement: 'safe for both CLIENT_OWNER and DESIGN_BUILDER_PROPONENT
    verification where appropriate' - is_admin() has zero coupling to
    operating_environment anywhere in this codebase (confirmed earlier
    this session, row 2 of the navigation-context operational map), so
    the verification identity should reach both exactly like any other
    admin session does."""

    def _ingest_project(self, environment, name, owner="real_admin"):
        import io
        import uuid
        from datetime import datetime, timezone
        from unittest.mock import patch

        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.ingestion import ingest_upload
        from werkzeug.datastructures import FileStorage

        def _fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        file_storage = FileStorage(stream=io.BytesIO(b"content"), filename="doc.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            return ingest_upload(
                file_storage, self.flask_app, operating_environment=environment,
                owner=owner, project_name=name,
            )

    def test_verification_session_can_open_a_client_owner_project(self):
        from services.verification_access import create_verification_access

        doc = self._ingest_project(CLIENT_OWNER, "Verify Owner Project")
        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client = self.flask_app.test_client()
        client.get(f"/verification-access/{raw_token}")
        resp = client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)

    def test_verification_session_can_open_a_design_builder_proponent_project(self):
        from services.verification_access import create_verification_access

        doc = self._ingest_project(DESIGN_BUILDER_PROPONENT, "Verify Proponent Project")
        with self.flask_app.app_context():
            _user, raw_token = create_verification_access()
        client = self.flask_app.test_client()
        client.get(f"/verification-access/{raw_token}")
        resp = client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
