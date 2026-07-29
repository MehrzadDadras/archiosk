"""
SMTP finalization (CLAUDE-P27-B). No existing test mocked smtplib
directly -- services/password_reset.py's own tests mock send_email()
itself, proving the caller's behavior, not send_email()'s own
transport logic. These tests cover that gap: STARTTLS vs. implicit-SSL
transport selection, conditional starttls()/login() calls, and
exception handling -- all against a mocked smtplib, no real network
access, no real credentials.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import smtplib
import unittest
from unittest import mock

from services.email import send_email


class SendEmailTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.flask_app.config.update(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=587,
            SMTP_USERNAME="",
            SMTP_PASSWORD="",
            SMTP_FROM="noreply@example.com",
            SMTP_USE_TLS=True,
            SMTP_USE_SSL=False,
        )
        self.ctx = self.flask_app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_starttls_mode_uses_plain_smtp_and_calls_starttls(self):
        with mock.patch("smtplib.SMTP") as MockSMTP, mock.patch("smtplib.SMTP_SSL") as MockSMTPSSL:
            server = MockSMTP.return_value.__enter__.return_value
            result = send_email("someone@example.com", "Subject", "Body")

        self.assertTrue(result)
        MockSMTP.assert_called_once_with("smtp.example.com", 587, timeout=10)
        MockSMTPSSL.assert_not_called()
        server.starttls.assert_called_once()
        server.login.assert_not_called()  # no SMTP_USERNAME configured
        server.send_message.assert_called_once()

    def test_implicit_ssl_mode_uses_smtp_ssl_and_never_calls_starttls(self):
        self.flask_app.config.update(SMTP_USE_SSL=True, SMTP_PORT=465)
        with mock.patch("smtplib.SMTP") as MockSMTP, mock.patch("smtplib.SMTP_SSL") as MockSMTPSSL:
            server = MockSMTPSSL.return_value.__enter__.return_value
            result = send_email("someone@example.com", "Subject", "Body")

        self.assertTrue(result)
        MockSMTPSSL.assert_called_once_with("smtp.example.com", 465, timeout=10)
        MockSMTP.assert_not_called()
        server.starttls.assert_not_called()  # implicit TLS -- no upgrade step

    def test_login_called_when_username_configured(self):
        self.flask_app.config.update(SMTP_USERNAME="mailer", SMTP_PASSWORD="secret-not-asserted")
        with mock.patch("smtplib.SMTP") as MockSMTP:
            server = MockSMTP.return_value.__enter__.return_value
            send_email("someone@example.com", "Subject", "Body")

        server.login.assert_called_once_with("mailer", "secret-not-asserted")

    def test_smtp_exception_returns_false_without_raising(self):
        with mock.patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "nope")):
            result = send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)

    def test_os_error_returns_false_without_raising(self):
        with mock.patch("smtplib.SMTP", side_effect=OSError("connection refused")):
            result = send_email("someone@example.com", "Subject", "Body")
        self.assertFalse(result)

    def test_no_recipient_returns_false_without_attempting_a_connection(self):
        with mock.patch("smtplib.SMTP") as MockSMTP:
            result = send_email("", "Subject", "Body")
        self.assertFalse(result)
        MockSMTP.assert_not_called()

    def test_message_headers_are_set_correctly(self):
        with mock.patch("smtplib.SMTP") as MockSMTP:
            server = MockSMTP.return_value.__enter__.return_value
            send_email("someone@example.com", "Test Subject", "Test Body")

        sent_message = server.send_message.call_args[0][0]
        self.assertEqual(sent_message["To"], "someone@example.com")
        self.assertEqual(sent_message["From"], "noreply@example.com")
        self.assertEqual(sent_message["Subject"], "Test Subject")


if __name__ == "__main__":
    unittest.main()
