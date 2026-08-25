"""
CLAUDE-DIAGNOSTIC-BRIDGE-01 - capture a live problem, investigate it, hand the
result back.

Product Owner: "I want to be able to receive Claude's diagnostic result and
paste it directly into ChatGPT without manually reconstructing the
investigation" - and, as the governing constraint on the whole bridge: "this
must not become a general user -> coding-agent channel... Also separate
investigate / report from modify / commit / deploy."

Most of this file is about that boundary rather than about the feature, because
the feature is small and the boundary is the part that would matter if it were
wrong. A capture surface reachable by an ordinary project user, or a report that
could authorize a deployment, would each be a serious defect; neither is
possible here, and these tests are how that stays true.

The bridge is deliberately a PULL. ARCHIOSK cannot call a development agent -
one runs on an operator's own machine when a human starts it - so capture writes
an inert row and a session reads it when asked. Several tests below assert the
ABSENCE of a transport, because the tempting thing to build here is a channel,
and a channel is exactly what must not exist.

Hermetic: no SMTP is configured under "testing", so the send path is exercised
through its refusal, never through a real connection.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVICE = _REPO_ROOT / "services" / "diagnostic_report.py"
_TOOL = _REPO_ROOT / "tools" / "diagnostic_report.py"
_ROUTES = _REPO_ROOT / "routes" / "portal.py"
_TEMPLATE = _REPO_ROOT / "templates" / "diagnostics.html"


class _BridgeTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.create_all()
            db.session.add(User(username="dx_admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="dx_user",
                                password_hash=generate_password_hash("x"), role="user"))
            db.session.commit()

    def _client_as(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _capture(self, client, **form):
        payload = {"summary": "Composer did not respond"}
        payload.update(form)
        return client.post("/developer/diagnostics", data=payload, follow_redirects=True)


class OnlyAnAdminCanReachItTests(_BridgeTestCase):
    """"This must not become a general user -> coding-agent channel." """

    def test_an_ordinary_user_cannot_capture(self):
        from models import DiagnosticReport
        response = self._capture(self._client_as("dx_user", 2, "user"))
        self.assertIn(response.status_code, (200, 302, 403, 404))
        with self.flask_app.app_context():
            self.assertEqual(DiagnosticReport.query.count(), 0)

    def test_an_ordinary_user_cannot_read_the_list(self):
        response = self._client_as("dx_user", 2, "user").get(
            "/developer/diagnostics", follow_redirects=False)
        self.assertNotEqual(response.status_code, 200)

    def test_an_anonymous_visitor_cannot_reach_either(self):
        anon = self.flask_app.test_client()
        for method, path in (("post", "/developer/diagnostics"), ("get", "/developer/diagnostics")):
            response = getattr(anon, method)(path, follow_redirects=False)
            self.assertNotEqual(response.status_code, 200, path)

    def test_both_routes_are_admin_gated_in_source(self):
        routes = _ROUTES.read_text(encoding="utf-8")
        block = routes[routes.index("def capture_diagnostic"):]
        preceding = routes[:routes.index("def capture_diagnostic")]
        self.assertIn("@admin_required", preceding[-120:])
        listing = routes[:routes.index("def list_diagnostics")]
        self.assertIn("@admin_required", listing[-120:])


class CaptureFillsInWhatTheAppKnowsTests(_BridgeTestCase):
    def test_a_report_is_recorded_with_derived_context(self):
        from models import DiagnosticReport
        client = self._client_as("dx_admin", 1, "admin")
        self._capture(client, detail="Typed a question on the phone; nothing came back.",
                      surface="/projects/p-1/workspace", project_id="p-1", case_id="c-1")
        with self.flask_app.app_context():
            report = DiagnosticReport.query.first()
            self.assertIsNotNone(report)
            self.assertEqual(report.reported_by, "dx_admin")
            self.assertEqual(report.project_id, "p-1")
            self.assertEqual(report.case_id, "c-1")
            self.assertEqual(report.status, DiagnosticReport.STATUS_OPEN)
            # Derived, not asked for - the whole point of the bridge.
            self.assertTrue(report.static_version)
            self.assertIsNotNone(report.reported_at)

    def test_an_empty_summary_is_refused(self):
        from models import DiagnosticReport
        self._capture(self._client_as("dx_admin", 1, "admin"), summary="   ")
        with self.flask_app.app_context():
            self.assertEqual(DiagnosticReport.query.count(), 0)

    def test_the_receipt_does_not_claim_anything_was_sent(self):
        response = self._capture(self._client_as("dx_admin", 1, "admin"))
        body = response.get_data(as_text=True)
        self.assertIn("Recorded as diagnostic", body)
        self.assertIn("nothing has been transmitted", body)
        self.assertNotIn("Sent to Claude", body)


class ThereIsNoTransportTests(unittest.TestCase):
    """The tempting thing to build here is a channel. There must not be one."""

    def setUp(self):
        self.service = _SERVICE.read_text(encoding="utf-8")
        self.tool = _TOOL.read_text(encoding="utf-8")
        # The prose in both files explains what must not exist, naming the very
        # things asserted absent - so comments are stripped before scanning.
        self.service_code = re.sub(r'"""[\s\S]*?"""', "", self.service)
        self.service_code = re.sub(r"#[^\n]*", "", self.service_code)
        self.tool_code = re.sub(r'"""[\s\S]*?"""', "", self.tool)
        self.tool_code = re.sub(r"#[^\n]*", "", self.tool_code)

    def test_the_service_opens_no_network_connection_of_its_own(self):
        for token in ("requests.", "urllib", "httpx", "websocket", "socket."):
            self.assertNotIn(token, self.service_code, token)

    def test_mail_goes_through_the_existing_subsystem(self):
        # "Reuse the existing email capability rather than creating another mail
        # subsystem."
        self.assertIn("from services.email import send_email", self.service)
        self.assertNotIn("smtplib", self.service_code)

    def test_nothing_here_can_change_code_or_deploy(self):
        for source, name in ((self.service_code, "service"), (self.tool_code, "tool")):
            for token in ("git commit", "git push", "rsync", "systemctl", "subprocess.Popen"):
                self.assertNotIn(token, source, f"{name}: {token}")

    def test_the_only_subprocess_use_reads_a_commit_id(self):
        # deployed_build_sha runs `git rev-parse HEAD` and nothing else.
        calls = re.findall(r"subprocess\.run\(\s*\[([^\]]*)\]", self.service_code)
        self.assertEqual(len(calls), 1)
        self.assertIn("rev-parse", calls[0])

    def test_status_has_no_deployed_or_committed_state(self):
        # Deployment is not a state this record can advance itself to.
        statuses = re.findall(r'STATUS_[A-Z_]+ = "([a-z_]+)"', self.service + _ROUTES.read_text(encoding="utf-8"))
        for forbidden in ("deployed", "committed", "merged"):
            self.assertNotIn(forbidden, statuses)


class InvestigationAndNotificationAreSeparateTests(_BridgeTestCase):
    def test_completing_does_not_send(self):
        from models import DiagnosticReport
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            report = service.record(reported_by="dx_admin", summary="s")
            service.complete(report.id, findings="Found it.")
            refreshed = DiagnosticReport.query.get(report.id)
            self.assertEqual(refreshed.status, DiagnosticReport.STATUS_INVESTIGATED)
            self.assertIsNone(refreshed.emailed_at)

    def test_an_uninvestigated_report_is_not_emailable(self):
        # An email whose findings say "not established" looks like an answer.
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            report = service.record(reported_by="dx_admin", summary="s")
            sent, reason = service.email_report(report.id, to_addr="someone@example.com")
            self.assertFalse(sent)
            self.assertIn("no findings yet", reason)

    def test_sending_without_smtp_configured_refuses_truthfully(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            report = service.record(reported_by="dx_admin", summary="s")
            service.complete(report.id, findings="Found it.")
            sent, reason = service.email_report(report.id, to_addr="someone@example.com")
            self.assertFalse(sent)
            self.assertIn("SMTP_HOST", reason)

    def test_an_unknown_report_is_reported_not_crashed(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            sent, reason = service.email_report(999999, to_addr="someone@example.com")
            self.assertFalse(sent)
            self.assertIn("No diagnostic report", reason)


class TheEmailIsCopyReadyTests(_BridgeTestCase):
    def _completed(self):
        from models import DiagnosticReport
        from services import diagnostic_report as service
        report = service.record(
            reported_by="dx_admin", summary="Composer did not respond",
            detail="Typed a question on the phone; nothing came back.",
            surface="/projects/p-1/workspace", project_id="p-1", case_id="c-1",
        )
        service.complete(
            report.id, findings="The turn persisted but no reply rendered.",
            root_cause="A missing branch.", affected="routes/workspace.py",
            recommendation="Add the branch.", commit_status="not committed",
            uncertainty="needs a phone reproduction",
        )
        return DiagnosticReport.query.get(report.id)

    def test_every_requested_section_is_present(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            subject, body = service.format_email(self._completed())
            self.assertIn("diagnostic", subject.lower())
            for heading in ("Live build", "Static version", "Surface", "Project",
                            "ISSUE REPORTED", "WHAT WAS FOUND", "ROOT CAUSE",
                            "AFFECTED CODE / SURFACE", "FIX / RECOMMENDATION",
                            "COMMIT / DEPLOYMENT STATUS", "STILL UNCERTAIN"):
                self.assertIn(heading, body, heading)

    def test_it_is_plain_text_for_pasting(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            _, body = service.format_email(self._completed())
            self.assertNotIn("<html", body.lower())
            self.assertNotIn("<div", body.lower())

    def test_a_missing_field_says_not_established_rather_than_nothing(self):
        # A silently absent section reads as an answer of "nothing".
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            report = service.record(reported_by="dx_admin", summary="s")
            service.complete(report.id, findings="Only findings were written.")
            _, body = service.format_email(report)
            self.assertIn("not established", body)

    def test_the_body_carries_identifiers_not_project_content(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            _, body = service.format_email(self._completed())
            self.assertIn("p-1", body)
            self.assertIn("identifiers rather than project content", body.lower())


class TheAdminViewIsReadOnlyTests(_BridgeTestCase):
    def test_the_list_renders_for_an_admin(self):
        from services import diagnostic_report as service
        with self.flask_app.app_context():
            service.record(reported_by="dx_admin", summary="A captured problem")
        response = self._client_as("dx_admin", 1, "admin").get("/developer/diagnostics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("A captured problem", response.get_data(as_text=True))

    def test_the_page_offers_no_action_that_mutates_anything(self):
        markup = _TEMPLATE.read_text(encoding="utf-8")
        body = re.sub(r"\{#[\s\S]*?#\}", "", markup)
        self.assertNotIn("<form", body)
        self.assertNotIn("method=\"post\"", body)

    def test_the_empty_state_is_honest(self):
        response = self._client_as("dx_admin", 1, "admin").get("/developer/diagnostics")
        self.assertIn("No diagnostics captured yet", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
