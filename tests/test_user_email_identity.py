"""
User.email identity rule (CLAUDE-P30).

Password reset (services/password_reset.py) looks a user up by email
and takes the first match - if two accounts could ever hold the same
email in different letter-casing, that lookup would be genuinely
ambiguous between them, not just inconvenient. This covers the
database-level guarantee that prevents that:

- the UNIQUE constraint on users.email is case-insensitive (COLLATE
  NOCASE) - a fresh install gets this directly from models.py's own
  column declaration, which is what these tests exercise (TestingConfig
  uses a fresh in-memory sqlite database per test, going through
  create_all(), not the hand-written migration app.py also carries for
  an already-existing pre-P30 database - that migration is verified
  separately, against a real copy of the deployed db, not via pytest);
- multiple NULL emails never collide (every legacy/dev account without
  one attached yet coexists fine);
- User.email is normalized (stripped + lower-cased) on every
  assignment via a `@validates` hook, not just by callers remembering
  to do it themselves.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash


class UserEmailIdentityTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_user_email_identity_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_case_variant_duplicate_email_is_rejected_by_the_database(self):
        from sqlalchemy.exc import IntegrityError

        from models import User, db

        with self.flask_app.app_context():
            db.session.add(User(
                username="user_one", password_hash=generate_password_hash("pw"), role="read_only",
                email="Someone@Example.com",
            ))
            db.session.commit()

            db.session.add(User(
                username="user_two", password_hash=generate_password_hash("pw"), role="read_only",
                email="someone@example.com",
            ))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_multiple_null_emails_do_not_collide(self):
        from models import User, db

        with self.flask_app.app_context():
            db.session.add(User(username="no_email_one", password_hash=generate_password_hash("pw"), role="read_only"))
            db.session.add(User(username="no_email_two", password_hash=generate_password_hash("pw"), role="read_only"))
            db.session.commit()  # must not raise
            self.assertEqual(User.query.filter_by(email=None).count(), 2)

    def test_email_is_normalized_on_assignment(self):
        from models import User, db

        with self.flask_app.app_context():
            user = User(username="normalize_me", password_hash=generate_password_hash("pw"), role="read_only")
            user.email = "  MixedCase@EXAMPLE.com  "
            db.session.add(user)
            db.session.commit()
            self.assertEqual(user.email, "mixedcase@example.com")

    def test_empty_string_email_normalizes_to_none_not_a_collidable_value(self):
        from models import User, db

        with self.flask_app.app_context():
            user_a = User(username="blank_email_a", password_hash=generate_password_hash("pw"), role="read_only")
            user_a.email = "   "
            user_b = User(username="blank_email_b", password_hash=generate_password_hash("pw"), role="read_only")
            user_b.email = ""
            db.session.add_all([user_a, user_b])
            db.session.commit()  # must not raise -- both normalize to None, not two equal "" values
            self.assertIsNone(user_a.email)
            self.assertIsNone(user_b.email)


if __name__ == "__main__":
    unittest.main()
