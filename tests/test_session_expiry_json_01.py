"""
CLAUDE-SESSION-EXPIRY-JSON-01 - an expired session must not look like a network
error to a script.

WHAT WAS WRONG

`login_required` returned a 302 to /login for every caller. For a browser that is
correct and stays correct. For a `fetch()` it is not: fetch follows redirects
transparently, so the script received **200 and a page of HTML**, and the
`resp.json()` that followed threw a parse error. An expired session therefore
surfaced as "a network error occurred" - a wrong diagnosis of a routine timeout.

That is the same failure `CLAUDE-CSRF-EXPIRY-01` already fixed for CSRF, left
unfixed for session expiry, and it became reachable the moment
`static/js/chunked_upload.js` started POSTing to a `@login_required` route.

WHAT THIS ASSERTS

Both halves, because fixing one by breaking the other would be no fix at all:
a browser still gets its 302, and only a script gets the 401 JSON.

The detection is asserted against the STRICT-Accept trap specifically -
`Accept: */*` scores application/json and text/html equally, and treating that
tie as "wants JSON" would turn an ordinary browser form POST into a JSON reply.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.requirements_registry import RequirementsRegistry

# A @login_required workspace route that exists regardless of project state, and
# a project-scoped one. Both must behave identically for an absent session.
GUARDED_PATHS = [
    ("GET", "/projects/some-project/workspace"),
    ("POST", "/projects/some-project/workspace/sources/upload-chunk"),
    ("POST", "/projects/some-project/workspace/sources/upload-complete"),
    ("POST", "/projects/some-project/workspace/sources/document"),
]


class _Base(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_session_expiry_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="some-project", filename="rfp.md",
            ingested_at="2026-01-01T00:00:00+00:00",
        ))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def anonymous(self):
        return self.app.test_client()


class ABrowserStillGetsItsRedirectTests(_Base):
    """The behaviour that was already correct, and must stay correct."""

    def test_plain_request_redirects_to_login_with_next(self):
        for method, path in GUARDED_PATHS:
            with self.subTest(method=method, path=path):
                response = self.anonymous().open(path, method=method)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])
                self.assertIn("next=", response.headers["Location"])

    def test_an_html_accepting_request_redirects(self):
        response = self.anonymous().get(
            "/projects/some-project/workspace",
            headers={"Accept": "text/html,application/xhtml+xml"})
        self.assertEqual(response.status_code, 302)

    def test_a_wildcard_accept_is_treated_as_a_browser_not_a_script(self):
        """The strict-Accept trap. `*/*` scores json and html equally; treating
        that tie as "wants JSON" would turn an ordinary form POST into JSON."""
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/document",
            headers={"Accept": "*/*"})
        self.assertEqual(response.status_code, 302,
                         "Accept: */* must not be read as a JSON client")

    def test_no_accept_header_at_all_redirects(self):
        response = self.anonymous().get("/projects/some-project/workspace")
        self.assertEqual(response.status_code, 302)


class AScriptGetsJsonTests(_Base):
    """The gap this closes."""

    def _assert_session_expired_json(self, response, path):
        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertIsNotNone(payload, "the body must be parseable JSON")
        self.assertEqual(payload["error"], "session_expired")
        self.assertIn("/login", payload["redirect"])
        self.assertIn("next=", payload["redirect"])

    def test_x_requested_with_gets_401_json(self):
        for method, path in GUARDED_PATHS:
            with self.subTest(method=method, path=path):
                response = self.anonymous().open(
                    path, method=method,
                    headers={"X-Requested-With": "XMLHttpRequest"})
                self._assert_session_expired_json(response, path)

    def test_accept_application_json_gets_401_json(self):
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/upload-chunk",
            headers={"Accept": "application/json"})
        self._assert_session_expired_json(response, "upload-chunk")

    def test_the_csrf_header_alone_marks_a_script(self):
        # Every fetch() in static/js sets it and no rendered <form> can, which
        # is why it is the strongest available signal.
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/upload-chunk",
            headers={"X-CSRFToken": "irrelevant-value"})
        self._assert_session_expired_json(response, "upload-chunk")

    def test_a_json_content_type_marks_a_script(self):
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/upload-complete",
            json={"upload_id": "x"})
        self._assert_session_expired_json(response, "upload-complete")

    def test_the_redirect_payload_names_the_path_that_was_refused(self):
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/upload-chunk",
            headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertIn("upload-chunk", response.get_json()["redirect"])

    def test_it_is_401_and_not_a_redirect(self):
        """401 specifically, because fetch() cannot silently follow it the way
        it silently follows a 302 - which is the whole defect."""
        response = self.anonymous().post(
            "/projects/some-project/workspace/sources/upload-chunk",
            headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Location", response.headers)


class TheHelperIsSharedNotCopiedTests(unittest.TestCase):
    """app.py's CSRF handler and the login gate must agree about one request."""

    def test_app_delegates_to_the_auth_helper(self):
        source = (Path(__file__).resolve().parent.parent / "app.py").read_text(
            encoding="utf-8")
        self.assertIn("from services.auth import wants_json_response", source)
        self.assertNotIn("accept[\"application/json\"] > accept[\"text/html\"]", source,
                         "the heuristic must live in exactly one place")

    def test_the_helper_exists_and_is_strict_about_wildcard_accept(self):
        import app as app_module
        from services.auth import wants_json_response

        app = app_module.create_app("testing")
        with app.test_request_context("/x", headers={"Accept": "*/*"}):
            self.assertFalse(wants_json_response())
        with app.test_request_context("/x", headers={"Accept": "application/json"}):
            self.assertTrue(wants_json_response())
        with app.test_request_context("/x", headers={"X-Requested-With": "XMLHttpRequest"}):
            self.assertTrue(wants_json_response())
        with app.test_request_context("/x"):
            self.assertFalse(wants_json_response())


class TheClientHandlesItTests(unittest.TestCase):
    """The server half is useless if the script still reports a network error.

    Asserted against the shipped source. The full truth table for needsReauth()
    is exercised directly under node during development; what must not silently
    regress in the repository is the presence of each branch, which is what
    these check.
    """

    def setUp(self):
        self.js = (Path(__file__).resolve().parent.parent /
                   "static" / "js" / "chunked_upload.js").read_text(encoding="utf-8")

    def test_it_redirects_on_401(self):
        self.assertIn("response.status === 401", self.js)
        self.assertIn("window.location.href", self.js)

    def test_it_also_redirects_on_a_csrf_expiry(self):
        """The case that actually happens.

        Verifying the previous deploy against the live endpoints showed a POST
        never reaches the 401: Flask-WTF's CSRF check is a before_request hook
        and so runs BEFORE the view's @login_required, and the CSRF token is
        bound to the session. Every request this file makes is a POST, so
        handling only the 401 would have handled only the case that cannot
        occur here.
        """
        self.assertIn("csrf_expired", self.js)
        self.assertIn("CSRF token expired", self.js)

    def test_a_successful_response_can_never_trigger_a_login_redirect(self):
        """The trap. upload-complete returns `redirect` on SUCCESS - the
        workspace URL to return to. Treating a bare `redirect` as a re-auth
        signal without checking status first would send a completed upload to
        the login page."""
        self.assertIn("if (response.ok) { return false; }", self.js)

    def test_an_ordinary_refusal_is_not_treated_as_a_login_problem(self):
        # An unsupported format or a bad chunk index is a 400 too. The check
        # keys off the error CODE, not merely the status.
        self.assertIn("payload.error || payload.reason", self.js)

    def test_it_prefers_the_servers_redirect_target(self):
        self.assertIn("payload.redirect", self.js)

    def test_it_falls_back_to_login_with_the_current_path(self):
        self.assertIn("encodeURIComponent(window.location.pathname)", self.js)

    def test_a_reauth_is_never_retried(self):
        # Retrying three times into a session that is gone delays the redirect
        # and re-sends bytes that cannot land.
        self.assertIn("error.message === 'SESSION_EXPIRED'", self.js)

    def test_it_does_not_blame_the_upload_for_an_expired_sign_in(self):
        self.assertIn("Your sign-in expired. Redirecting to sign in again...", self.js)

    def test_it_asks_for_json_explicitly(self):
        self.assertIn("'Accept': 'application/json'", self.js)


class TheProgressUiTests(unittest.TestCase):
    """CLAUDE-CHUNKED-UPLOAD-PROGRESS-01.

    A long upload with no visible progress is indistinguishable from a hung
    one, and the reviewer's only recourse is to guess. These assert the states
    exist in the shipped source; the arithmetic and the state machine are
    exercised directly under node against the same file.
    """

    def setUp(self):
        self.js = (Path(__file__).resolve().parent.parent /
                   "static" / "js" / "chunked_upload.js").read_text(encoding="utf-8")

    def test_it_uses_the_native_progress_element(self):
        # Native <progress> is accessible with no ARIA authoring and needs no
        # addition to main.css's semantic colour grammar, so it cannot drift
        # from that grammar later. A bespoke bar would have to earn its place.
        self.assertIn("createElement('progress')", self.js)

    def test_it_reports_an_explicit_percentage_and_both_byte_counts(self):
        self.assertIn("percent + '% ('", self.js)
        self.assertIn("humanSize(sent)", self.js)
        self.assertIn("humanSize(file.size)", self.js)

    def test_it_names_the_active_chunk_and_the_total(self):
        self.assertIn("'Uploading chunk ' + (index + 1) + ' of ' + total", self.js)

    def test_assembling_is_indeterminate_not_a_stalled_hundred_percent(self):
        """A bar pinned at 100% while the server hashes reads as a hang."""
        self.assertIn("status.progress(null, 'Assembling & verifying file...')", self.js)
        self.assertIn("removeAttribute('value')", self.js)

    def test_completion_is_marked_with_a_checkmark(self):
        self.assertIn("Upload complete", self.js)
        self.assertIn(r"\u2713", self.js)

    def test_failure_hides_the_bar_rather_than_freezing_it(self):
        # A bar frozen mid-way reads as "still going" to someone who just
        # looked away, which is the opposite of what a failure should convey.
        self.assertIn("Status.prototype.fail", self.js)
        self.assertIn("this.bar.hidden = true", self.js)

    def test_the_live_region_is_polite_not_assertive(self):
        # This updates on every chunk; assertive would interrupt a screen
        # reader continuously for the length of the upload.
        self.assertIn("'aria-live', 'polite'", self.js)

    def test_the_submit_control_is_gated_while_uploading(self):
        self.assertIn("submit.disabled = true", self.js)
        self.assertIn("input.disabled = true", self.js)

    def test_the_controls_are_released_again_on_failure(self):
        # A dead form after a failed upload is its own defect.
        self.assertIn("submit.disabled = false", self.js)
        self.assertIn("input.disabled = false", self.js)


if __name__ == "__main__":
    unittest.main()
