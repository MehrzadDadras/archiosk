"""
CLAUDE-CA1D-TRIAL-ACCESS-HOTFIX-01 - Remove the Public Dead End.

Covers the replacement of the former dead-end /start-trial page (a
static "isn't self-serve yet... check back soon" rejection) with a real,
minimal Request Access flow: GET renders the form, POST validates a
plausible email and hands the request to services/trial_request.py
(always logged; emailed via the existing best-effort SMTP transport only
when TRIAL_REQUEST_NOTIFY_EMAIL is configured - never a new persistent
PII store, never a new external service, never new account creation).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch


class StartTrialRequestFormTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_get_renders_the_request_form_not_the_old_rejection(self):
        """CLAUDE-REQUEST-ACCESS-PRUNE-01 removed the explanatory paragraph
        this used to assert on by its copy ("opening trial access
        gradually").

        The assertion is not weakened by dropping it, because the paragraph
        was never what this test protects. The requirement is that the old
        DEAD END never returns and that a real request action is here
        instead - the two `assertNotIn`s and the form/submit refs say that
        directly, and they are unaffected. A page can satisfy every one of
        them with no prose at all, which is now the case."""
        body = self.client.get("/start-trial").get_data(as_text=True)
        self.assertNotIn("isn&rsquo;t self-serve yet", body)
        self.assertNotIn("check back soon", body)
        self.assertIn('data-ui-ref="start-trial.request-form"', body)
        self.assertIn('data-ui-ref="start-trial.request-submit"', body)
        self.assertIn(">Request Access<", body)

    def test_the_title_is_not_printed_twice(self):
        """The eyebrow above the h1 repeated it verbatim - the same three
        words stacked on themselves. One title, once."""
        body = self.client.get("/start-trial").get_data(as_text=True)
        # Counted inside the document body only. <title> legitimately carries
        # the same words and is not a second visible heading - asserting
        # against the whole response would fail for a reason that has nothing
        # to do with what a visitor sees.
        visible = body[body.index('<div class="landing-doc">'):]
        self.assertEqual(visible.count("Request Trial Access"), 1)
        self.assertIn("<h1>Request Trial Access</h1>", visible)
        self.assertNotIn("landing-doc-kicker", visible)

    def test_form_carries_a_real_csrf_token_field(self):
        body = self.client.get("/start-trial").get_data(as_text=True)
        self.assertIn('name="csrf_token"', body)

    def test_request_access_is_the_only_action_on_the_page(self):
        """Was: "Request Access is primary, Sign In and Explore are
        secondary", asserted by source order.

        CLAUDE-REQUEST-ACCESS-PRUNE-01 removed the secondary pair entirely on
        Product Owner direction, which satisfies the original intent more
        strongly than ordering did - there is nothing left for the primary
        action to be primary OVER. Inverted rather than deleted: the risk
        worth guarding is now that competing CTAs come back, and an empty
        space in the suite guards nothing.

        The exit path is deliberately not zero. `start-trial.back` is the
        top-left link, and it is asserted here so "sole exit path" cannot
        quietly become "no exit path"."""
        body = self.client.get("/start-trial").get_data(as_text=True)
        self.assertIn('data-ui-ref="start-trial.request-submit"', body)
        self.assertIn('data-ui-ref="start-trial.back"', body)
        for gone in ('data-ui-ref="start-trial.sign-in"',
                     'data-ui-ref="start-trial.explore"',
                     "Already have an account?"):
            with self.subTest(token=gone):
                self.assertNotIn(gone, body)

    def test_no_billing_or_payment_fields_present(self):
        body = self.client.get("/start-trial").get_data(as_text=True).lower()
        for forbidden in ("card number", "credit card", "payment", "billing", "subscription"):
            self.assertNotIn(forbidden, body)

    def test_post_without_email_is_rejected_with_a_visible_error(self):
        resp = self.client.post("/start-trial", data={"name": "Jamie", "message": "curious"})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="start-trial.request-error"', body)
        # Preserves what the visitor already typed rather than discarding it.
        self.assertIn("Jamie", body)
        self.assertIn("curious", body)

    def test_post_with_implausible_email_is_rejected(self):
        for bad_email in ("not-an-email", "@nohost.com", "trailing@"):
            resp = self.client.post("/start-trial", data={"email": bad_email})
            self.assertEqual(resp.status_code, 400, f"expected rejection for {bad_email!r}")

    def test_post_with_valid_email_shows_truthful_acknowledgement(self):
        resp = self.client.post("/start-trial", data={"name": "Jamie", "email": "jamie@example.com", "message": "curious"})
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Request received", body)
        self.assertIn(
            "Archiosk trial access is currently provisioned through controlled access.",
            body,
        )
        # Never promises a response time, never implies an account already exists.
        self.assertNotIn("business day", body.lower())
        self.assertNotIn("hours", body.lower())
        self.assertNotIn("your account has been created", body.lower())

    def test_success_state_is_not_a_dead_end(self):
        """The footer pair went from BOTH states, not just the form - so the
        thing actually worth asserting is that a visitor who has just
        submitted can still leave. They can: the top-left link is outside the
        submitted/not-submitted branch and renders in both.

        Recorded plainly because it is a real narrowing: the confirmation
        screen now offers one way onward where it used to offer three."""
        resp = self.client.post("/start-trial", data={"email": "jamie@example.com"})
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="start-trial.back"', body)
        # The form itself is gone once submitted - no re-submission encouraged.
        self.assertNotIn('data-ui-ref="start-trial.request-form"', body)

    def test_name_and_message_are_optional(self):
        resp = self.client.post("/start-trial", data={"email": "jamie@example.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Request received", resp.get_data(as_text=True))


class TrialRequestServiceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")

    def test_submit_always_succeeds_without_raising_when_notify_email_unset(self):
        from services.trial_request import submit_trial_request
        with self.flask_app.app_context():
            self.flask_app.config["TRIAL_REQUEST_NOTIFY_EMAIL"] = ""
            submit_trial_request(name="Jamie", email="jamie@example.com", message="curious")  # must not raise

    def test_submit_emails_the_configured_notify_address_when_smtp_and_notify_are_set(self):
        from services.trial_request import submit_trial_request
        with self.flask_app.app_context():
            self.flask_app.config["TRIAL_REQUEST_NOTIFY_EMAIL"] = "ops@archiosk.com"
            self.flask_app.config["SMTP_HOST"] = "smtp.example.com"
            with patch("services.trial_request.send_email", return_value=True) as mock_send:
                submit_trial_request(name="Jamie", email="jamie@example.com", message="curious about RFPs")
            mock_send.assert_called_once()
            kwargs = mock_send.call_args.kwargs
            self.assertEqual(kwargs["to_addr"], "ops@archiosk.com")
            self.assertIn("Jamie", kwargs["body"])
            self.assertIn("jamie@example.com", kwargs["body"])
            self.assertIn("curious about RFPs", kwargs["body"])

    def test_submit_skips_email_entirely_when_notify_unset_even_if_smtp_configured(self):
        from services.trial_request import submit_trial_request
        with self.flask_app.app_context():
            self.flask_app.config["TRIAL_REQUEST_NOTIFY_EMAIL"] = ""
            self.flask_app.config["SMTP_HOST"] = "smtp.example.com"
            with patch("services.trial_request.send_email") as mock_send:
                submit_trial_request(name="Jamie", email="jamie@example.com", message="")
            mock_send.assert_not_called()

    def test_submit_skips_email_when_smtp_unconfigured_even_if_notify_set(self):
        from services.trial_request import submit_trial_request
        with self.flask_app.app_context():
            self.flask_app.config["TRIAL_REQUEST_NOTIFY_EMAIL"] = "ops@archiosk.com"
            self.flask_app.config["SMTP_HOST"] = ""
            with patch("services.trial_request.send_email") as mock_send:
                submit_trial_request(name="Jamie", email="jamie@example.com", message="")
            mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
