"""CLAUDE-ENTRY-REDUNDANCY-01 - one entry question instead of two.

Live review of the five-position gate found the creation form asking for the
Project Operating Environment and then immediately for the project position:
the same words ("Client / Owner") in two adjacent boxes meaning different
things, and an internal abstraction exposed as a user decision.

The correction removes the redundant USER DECISION, not the internal semantic
distinction. operating_environment is still its own locked, required, governed
field with its own meaning - it is now derived from the position the user
actually declared rather than asked for twice.

The consultant positions are the interesting case: they are the only ones whose
capability side cannot be read from the position alone, because the same
profession sits on the Owner's side when an Owner retains them and on the
delivery side when a design-builder does. Their upstream question is what
resolves it - which is why every option they offer resolves to a side, and why
they do not offer "not established".
"""
from __future__ import annotations

import unittest

from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.project_perspective import (
    ENTRY_CLIENT_OWNER,
    ENTRY_LEAD_DESIGN_CONSULTANT,
    ENTRY_PRIME_CONTRACTOR,
    ENTRY_SUBCONSULTANT,
    ENTRY_TRADE_BIDDER,
    RETAINED_BY_DESIGN_BUILDER,
    RETAINED_BY_LEAD_CONSULTANT,
    RETAINED_BY_NOT_ESTABLISHED,
    RETAINED_BY_OWNER,
    operating_environment_for,
    requires_retained_by,
    retained_by_options,
)


class EnvironmentIsDerivedNotAskedTests(unittest.TestCase):
    def test_positions_that_resolve_on_their_own(self):
        for choice, expected in (
            (ENTRY_CLIENT_OWNER, CLIENT_OWNER),
            (ENTRY_PRIME_CONTRACTOR, DESIGN_BUILDER_PROPONENT),
            (ENTRY_TRADE_BIDDER, DESIGN_BUILDER_PROPONENT),
        ):
            with self.subTest(position=choice):
                self.assertEqual(operating_environment_for(choice), expected)

    def test_a_consultant_resolves_through_who_engaged_them(self):
        """The same profession, opposite sides, decided by the upstream edge."""
        cases = (
            (ENTRY_LEAD_DESIGN_CONSULTANT, RETAINED_BY_OWNER, CLIENT_OWNER),
            (ENTRY_LEAD_DESIGN_CONSULTANT, RETAINED_BY_DESIGN_BUILDER, DESIGN_BUILDER_PROPONENT),
            (ENTRY_SUBCONSULTANT, RETAINED_BY_LEAD_CONSULTANT, CLIENT_OWNER),
            (ENTRY_SUBCONSULTANT, RETAINED_BY_DESIGN_BUILDER, DESIGN_BUILDER_PROPONENT),
        )
        for choice, retained, expected in cases:
            with self.subTest(position=choice, retained_by=retained):
                self.assertEqual(operating_environment_for(choice, retained), expected)

    def test_an_unresolved_consultant_is_not_guessed(self):
        """None means ask. The field is locked at creation and irreversible, so
        a wrong guess would cost the user their whole project."""
        for choice in (ENTRY_LEAD_DESIGN_CONSULTANT, ENTRY_SUBCONSULTANT):
            with self.subTest(position=choice):
                self.assertIsNone(operating_environment_for(choice))
                self.assertIsNone(operating_environment_for(choice, RETAINED_BY_NOT_ESTABLISHED))

    def test_an_unknown_position_resolves_to_nothing(self):
        self.assertIsNone(operating_environment_for(None))
        self.assertIsNone(operating_environment_for("not_a_position"))


class ConsultantPositionsMustResolveASideTests(unittest.TestCase):
    def test_only_the_consultant_positions_require_the_upstream_answer(self):
        self.assertTrue(requires_retained_by(ENTRY_LEAD_DESIGN_CONSULTANT))
        self.assertTrue(requires_retained_by(ENTRY_SUBCONSULTANT))
        for choice in (ENTRY_CLIENT_OWNER, ENTRY_PRIME_CONTRACTOR, ENTRY_TRADE_BIDDER):
            with self.subTest(position=choice):
                self.assertFalse(requires_retained_by(choice))

    def test_every_option_a_consultant_is_offered_resolves_a_side(self):
        for choice in (ENTRY_LEAD_DESIGN_CONSULTANT, ENTRY_SUBCONSULTANT):
            for option in retained_by_options(choice):
                with self.subTest(position=choice, option=option):
                    self.assertIsNotNone(operating_environment_for(choice, option))

    def test_consultants_are_not_offered_not_established(self):
        """It cannot resolve a side, so offering it would only produce a dead
        end at the point the project is created."""
        for choice in (ENTRY_LEAD_DESIGN_CONSULTANT, ENTRY_SUBCONSULTANT):
            with self.subTest(position=choice):
                self.assertNotIn(RETAINED_BY_NOT_ESTABLISHED, retained_by_options(choice))

    def test_positions_that_resolve_on_their_own_keep_the_honest_unknown(self):
        for choice in (ENTRY_PRIME_CONTRACTOR, ENTRY_TRADE_BIDDER):
            with self.subTest(position=choice):
                self.assertIn(RETAINED_BY_NOT_ESTABLISHED, retained_by_options(choice))


class TheFormAsksOnceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(
                username="redun", password_hash=generate_password_hash("x"), role="admin",
            ))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "redun"
            sess["role"] = "admin"
        self.body = self.client.get("/upload").get_data(as_text=True)

    def test_the_environment_question_is_no_longer_asked(self):
        self.assertNotIn("Project Operating Environment", self.body)
        self.assertNotIn('name="operating_environment"', self.body)

    def test_the_position_question_is_the_primary_one(self):
        self.assertIn("Your position on this project", self.body)
        self.assertIn('name="entry_choice"', self.body)

    def test_the_upstream_question_is_scoped_per_position(self):
        """A visitor is never offered a relationship that cannot apply to the
        position they picked."""
        for choice in ("lead_design_consultant", "subconsultant",
                       "prime_contractor", "trade_bidder"):
            with self.subTest(position=choice):
                self.assertIn(f'upload.retained-by.{choice}', self.body)
        self.assertNotIn("upload.retained-by.client_owner", self.body)

    def test_the_upstream_groups_work_without_javascript(self):
        """Progressive enhancement: the groups render visible and the script
        narrows them, rather than the question existing only with JS."""
        self.assertIn('class="retained-by-group"', self.body)
        self.assertIn("data-for-choice=", self.body)

    def test_the_confirmation_copy_is_no_longer_implementation_heavy(self):
        self.assertIn("Confirm project position", self.body)
        self.assertNotIn("configures the project environment", self.body)


class BackwardCompatibilityTests(unittest.TestCase):
    """Direct posters - and 84 existing test files - still work unchanged."""

    def test_an_explicitly_posted_environment_is_still_honoured(self):
        import routes.portal as portal

        app_ = __import__("app").create_app("testing")
        with app_.test_request_context(
            "/upload", method="POST", data={"operating_environment": CLIENT_OWNER},
        ):
            self.assertEqual(portal._resolved_operating_environment(), CLIENT_OWNER)

    def test_a_declared_position_wins_over_nothing_posted(self):
        import routes.portal as portal

        app_ = __import__("app").create_app("testing")
        with app_.test_request_context(
            "/upload", method="POST", data={"entry_choice": ENTRY_TRADE_BIDDER},
        ):
            self.assertEqual(portal._resolved_operating_environment(), DESIGN_BUILDER_PROPONENT)

    def test_an_unresolved_position_falls_through_to_ordinary_validation(self):
        """Rather than being quietly defaulted."""
        import routes.portal as portal

        app_ = __import__("app").create_app("testing")
        with app_.test_request_context(
            "/upload", method="POST", data={"entry_choice": ENTRY_LEAD_DESIGN_CONSULTANT},
        ):
            self.assertEqual(portal._resolved_operating_environment(), "")

    def test_the_per_position_field_is_read_for_the_chosen_position_only(self):
        """A stale answer left in another group by someone who changed their
        mind must never be attached to the position they settled on."""
        import routes.portal as portal

        app_ = __import__("app").create_app("testing")
        with app_.test_request_context("/upload", method="POST", data={
            "entry_choice": ENTRY_SUBCONSULTANT,
            "retained_by__subconsultant": RETAINED_BY_DESIGN_BUILDER,
            "retained_by__lead_design_consultant": RETAINED_BY_OWNER,
        }):
            self.assertEqual(portal._posted_retained_by(), RETAINED_BY_DESIGN_BUILDER)
            self.assertEqual(portal._resolved_operating_environment(), DESIGN_BUILDER_PROPONENT)


if __name__ == "__main__":
    unittest.main()
