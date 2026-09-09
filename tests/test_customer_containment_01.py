"""CLAUDE-CUSTOMER-CONTAINMENT-01: an error must not change which product you are in.

The Product Owner's own phone session ended in All Projects. Nothing had gone
wrong with the document; a duplicate conversation submit lost a write race, and
the only exit offered was "Back to home" - and home meant the Projects
directory, an operating line a Document Shop customer has no authority in and
no business seeing.

The defect was never one link. Sign-in was the ONLY role-aware destination in
the application; the root and every generic error handler each held their own
hard-coded answer, so every one of them disagreed with it. That is why this
file tests the RULE and its consumers separately: `role_home_endpoint` is now
the single place the policy lives, and the tests below prove each surface asks
it rather than re-deciding.

Both directions are pinned deliberately. A customer must not be moved into
Projects by an error - and a Project user must not be moved out of Projects by
the fix. A containment change that quietly relocates the other role is not a
fix, it is the same defect facing the other way.
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

from models import ROLE_ADMIN, ROLE_CUSTOMER
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class _CustomerCase(unittest.TestCase):
    """One Document Shop container owned by `cust`, and a real app."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_containment_"))
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

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="cust", role=ROLE_CUSTOMER):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 7
            session["username"] = username
            session["role"] = role
        return client

    def _customer(self):
        return self._client()

    def _project_user(self):
        return self._client(username="admin", role=ROLE_ADMIN)

    def _anonymous(self):
        return self.app.test_client()


class TheRuleItself(_CustomerCase):
    """`role_home_endpoint` - one function, consulted, never copied."""

    def _resolve(self, role):
        from services.auth import role_home_endpoint, role_home_label

        with self.app.test_request_context("/"):
            from flask import session
            session["role"] = role
            return role_home_endpoint(), role_home_label()

    def test_a_customers_home_is_their_documents(self):
        endpoint, label = self._resolve(ROLE_CUSTOMER)
        self.assertEqual(endpoint, "portal.document_shop_jobs")
        self.assertEqual(label, "Back to my documents")

    def test_a_project_users_home_is_unchanged(self):
        endpoint, label = self._resolve(ROLE_ADMIN)
        self.assertEqual(endpoint, "portal.projects_list")
        self.assertEqual(label, "Back to home")

    def test_the_rule_is_defined_exactly_once(self):
        """A second copy is how the root and the handlers diverged the first time."""
        source = (_REPO_ROOT / "services" / "auth.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("\ndef role_home_endpoint("), 1)
        self.assertEqual(source.count("\ndef role_home_label("), 1)

    def test_it_returns_an_endpoint_name_not_a_url(self):
        """So the policy module stays free of request-time routing."""
        endpoint, _ = self._resolve(ROLE_CUSTOMER)
        self.assertFalse(endpoint.startswith("/"))
        self.assertIn(".", endpoint)


class TheRoot(_CustomerCase):
    """`/` is a home, and home is not the same place for everyone."""

    def test_a_customer_lands_on_their_documents(self):
        response = self._customer().get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/document-shop/jobs", response.headers["Location"])

    def test_a_project_user_still_lands_on_projects(self):
        response = self._project_user().get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/projects"))

    def test_an_anonymous_visitor_still_sees_the_landing_page(self):
        self.assertEqual(self._anonymous().get("/").status_code, 200)

    def test_the_gateway_route_inherits_the_same_answer(self):
        """`/gateway` only redirects to the root, so fixing the root fixed it."""
        response = self._customer().get("/gateway", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        second = self._customer().get("/gateway", follow_redirects=True)
        self.assertNotIn("All projects", second.get_data(as_text=True))


class ErrorRecovery(_CustomerCase):
    """Every generic handler, both roles. The dead ends are the whole defect."""

    def _error_exit(self, client, path):
        """The status, and the single way out errors/error.html offers."""
        import re

        response = client.get(path)
        body = response.get_data(as_text=True)
        match = re.search(r'<a class="btn btn-primary" href="([^"]+)"', body)
        self.assertIsNotNone(
            match, "expected errors/error.html's one action link, got: %s"
            % body[:400])
        return response.status_code, match.group(1)

    def test_a_customers_404_returns_to_their_documents(self):
        status, href = self._error_exit(self._customer(), "/no-such-page")
        self.assertEqual(status, 404)
        self.assertIn("/document-shop/jobs", href)

    def test_a_project_users_404_is_unchanged(self):
        status, href = self._error_exit(self._project_user(), "/no-such-page")
        self.assertEqual(status, 404)
        self.assertTrue(href.endswith("/projects"))

    def test_an_anonymous_404_still_offers_the_public_root(self):
        status, href = self._error_exit(self._anonymous(), "/no-such-page")
        self.assertEqual(status, 404)
        self.assertEqual(href, "/")

    def test_a_customers_403_no_longer_says_back_to_projects(self):
        """/upload is a real 403 for a customer - the one they actually hit."""
        response = self._customer().get("/upload")
        self.assertEqual(response.status_code, 403)
        body = response.get_data(as_text=True)
        self.assertIn("/document-shop/jobs", body)
        self.assertNotIn("Back to Projects", body)

    def test_no_generic_handler_hard_codes_a_destination(self):
        """Read as source, because a handler nobody exercised is how this got here."""
        source = (_REPO_ROOT / "app.py").read_text(encoding="utf-8")
        start = source.index("def _register_error_handlers")
        window = source[start:]
        self.assertNotIn('url_for("portal.projects_list"), "Back to Projects"', window)
        self.assertEqual(
            window.count('url_for("portal.index"), "Back to home"'), 1,
            "only the anonymous branch of _home() may name a fixed destination")

    def test_the_413_no_longer_offers_a_customer_the_project_upload_form(self):
        """Found by re-reading the handlers rather than trusting the list of six."""
        source = (_REPO_ROOT / "app.py").read_text(encoding="utf-8")
        window = source[source.index("def file_too_large"):]
        window = window[:window.index("@app.errorhandler(CSRFError)")]
        self.assertIn("user_is_document_shop_customer", window)
        self.assertIn("portal.document_shop_intake", window)
        self.assertIn("portal.upload", window,
                      "a Project user must still be sent back to their own form")

    def test_a_write_collision_page_resolves_the_destination_too(self):
        source = (_REPO_ROOT / "app.py").read_text(encoding="utf-8")
        window = source[source.index("def write_collision"):]
        window = window[:window.index("@app.errorhandler(ExternalSourceUnavailable)")]
        self.assertIn("*_home()", window)

    def test_the_external_source_handlers_resolve_the_destination_too(self):
        source = (_REPO_ROOT / "app.py").read_text(encoding="utf-8")
        for handler, following in (
                ("def external_source_unavailable",
                 "@app.errorhandler(ExternalSourceForbidden)"),
                ("def external_source_forbidden", "@app.errorhandler(403)")):
            with self.subTest(handler=handler):
                window = source[source.index(handler):]
                window = window[:window.index(following)]
                self.assertIn("*_home()", window)


class ProjectDirectoriesAreNotACustomersSurface(_CustomerCase):
    """Closing the links was not the whole condition - the URLs stayed open."""

    def test_a_customer_asking_for_the_project_directory_is_sent_to_their_own(self):
        response = self._customer().get("/projects")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/document-shop/jobs", response.headers["Location"])

    def test_a_customer_asking_for_the_project_chooser_is_sent_to_their_own(self):
        response = self._customer().get("/projects/choose")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/document-shop/jobs", response.headers["Location"])

    def test_a_project_user_reaches_both_exactly_as_before(self):
        client = self._project_user()
        for path in ("/projects", "/projects/choose"):
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)

    def test_it_is_a_redirect_not_a_refusal(self):
        """403 would say "you may not"; nothing was ever refused to them."""
        self.assertNotEqual(self._customer().get("/projects").status_code, 403)


class TheCustomerShellOffersNoProjectDoor(_CustomerCase):
    """A page reached without an error must not contain the escape either."""

    def test_the_result_page_offers_only_document_shop_destinations(self):
        response = self._customer().get(
            "/document-shop/jobs/%s" % self.owned.project_id)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("/document-shop/jobs", body)
        self.assertNotIn('href="/projects"', body)
        self.assertNotIn('href="/upload"', body)

    def test_the_application_menu_is_not_rendered_for_a_customer(self):
        response = self._customer().get(
            "/document-shop/jobs/%s" % self.owned.project_id)
        body = response.get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.file.all-projects"', body)
        self.assertIn('data-ui-ref="shell.customer-topbar"', body)


class TheConversationSurvivesBeingAskedTwice(_CustomerCase):
    """Section 4: the collision the Product Owner actually hit."""

    def _workspace(self):
        return self.store.get(self.owned.project_id)

    def test_a_turn_is_retried_when_the_record_moved_underneath_it(self):
        """The worker writing evidence mid-question is the ordinary case."""
        from services import document_conversation
        from services.case_workspace import ConcurrentModificationError

        workspace = self._workspace()
        real_add = CaseWorkspaceStore.add_message
        calls = {"n": 0}

        def flaky(store_self, ws, case_id, role, text, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConcurrentModificationError("the worker saved first")
            return real_add(store_self, ws, case_id, role, text, *args, **kwargs)

        with patch.object(CaseWorkspaceStore, "add_message", flaky):
            document_conversation.record_turn(
                self.store, workspace, actor="cust",
                question="What does this say?", answer="It says nothing yet.")

        conversation = self._workspace().project_conversation
        self.assertEqual(len(conversation), 2, "one question, one answer")

    def test_the_retry_does_not_re_post_a_question_already_stored(self):
        """Retrying the PAIR would duplicate the human turn; it retries each."""
        from services import document_conversation
        from services.case_workspace import ConcurrentModificationError

        workspace = self._workspace()
        real_add = CaseWorkspaceStore.add_message
        seen = {"n": 0}

        def fail_on_the_answer(store_self, ws, case_id, role, text, *a, **kw):
            seen["n"] += 1
            if seen["n"] == 2:
                raise ConcurrentModificationError("collided on the answer")
            return real_add(store_self, ws, case_id, role, text, *a, **kw)

        with patch.object(CaseWorkspaceStore, "add_message", fail_on_the_answer):
            document_conversation.record_turn(
                self.store, workspace, actor="cust",
                question="Only once please", answer="Understood.")

        texts = [m.get("text") for m in self._workspace().project_conversation]
        self.assertEqual(texts.count("Only once please"), 1)

    def test_an_unrelated_failure_is_never_swallowed_as_contention(self):
        from services import document_conversation

        workspace = self._workspace()

        def broken(*_a, **_kw):
            raise ValueError("something genuinely wrong")

        with patch.object(CaseWorkspaceStore, "add_message", broken):
            with self.assertRaises(ValueError):
                document_conversation.record_turn(
                    self.store, workspace, actor="cust",
                    question="q", answer="a")

    def test_the_tolerance_matches_the_workers_own(self):
        """Same contention from opposite ends - one number, not two policies."""
        from services import document_conversation, perception_worker

        self.assertEqual(document_conversation.CONCURRENT_WRITE_RETRIES,
                         perception_worker.CONCURRENT_WRITE_RETRIES)

    def test_the_composer_cannot_fire_twice_from_one_page(self):
        template = (_REPO_ROOT / "templates" / "document_shop_result.html").read_text(
            encoding="utf-8")
        self.assertIn("ds-conversation-send", template)
        self.assertIn("send.disabled = true", template)

    def test_the_guard_still_lets_an_empty_box_through_to_the_server(self):
        """The server says "Type a question first"; the guard must not eat that."""
        template = (_REPO_ROOT / "templates" / "document_shop_result.html").read_text(
            encoding="utf-8")
        window = template[template.index("ds-conversation-send"):]
        self.assertIn("!input.value.trim()", window)


if __name__ == "__main__":
    unittest.main()
