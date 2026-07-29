#!/usr/bin/env python
"""
Seed or update a User row (models.User) in the SQLite database for the web
UI's session-based login gate (services/auth.py).

There is no self-registration route -- provisioning is master-admin/
maintainer-only, via this CLI. Run it once per person you want to grant
access to:

    python tools/create_credentials.py --username admin --role admin
    python tools/create_credentials.py --username jdoe --role read_only

Re-running with an existing --username updates that user's password/role
in place (upsert), rather than erroring on the unique username constraint.
Omitting --role on an existing account leaves its current role unchanged
(it does NOT reset to read_only).

To attach/change an email on an EXISTING account without touching its
password (e.g. enabling the "Forgot password?" flow for an admin account
that already works fine day-to-day):

    python tools/create_credentials.py --username admin --email you@example.com --keep-password

Treat every non-primary account (a QA/reader/workspacetester-style
account) as development/test unless its purpose is proven otherwise --
never attach a real person's email to one "just because the field
exists." If a test genuinely needs an account to have SOME email (to
exercise the reset flow against, say), give it a distinct,
non-deliverable *.invalid address (RFC 2606 reserves that TLD for
exactly this) -- e.g. --email reader-test@archiosk.invalid -- never a
real inbox. One normalized (lower-cased) email may only ever belong to
one account -- models.py's User.email is a case-insensitive UNIQUE
constraint (COLLATE NOCASE) enforced by the database itself, and this
script also checks for a collision up front with a clear error rather
than a raw IntegrityError traceback.

Also fills in FLASK_SECRET_KEY in .env if it's blank -- Flask raises at
session-write time with no secret key configured, and log_in() writes
session data on every successful sign-in.
"""
from __future__ import annotations

import argparse
import getpass
import re
import secrets
import shutil
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"

# Run via `python tools/create_credentials.py` -- BASE_DIR (repo root) isn't
# on sys.path by default in that invocation, but `import app` / `import
# models` below need it to be.
sys.path.insert(0, str(BASE_DIR))


def _set_env_line(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^{key}=.*$")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


def _get_env_value(lines: list[str], key: str) -> str:
    pattern = re.compile(rf"^{key}=(.*)$")
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).split("#", 1)[0].strip()
    return ""


def _ensure_secret_key() -> bool:
    """Returns True if a new FLASK_SECRET_KEY was generated."""
    if not ENV_PATH.exists():
        if ENV_EXAMPLE_PATH.exists():
            shutil.copy(ENV_EXAMPLE_PATH, ENV_PATH)
            print(f"Created {ENV_PATH} from .env.example.")
        else:
            ENV_PATH.write_text("", encoding="utf-8")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    if _get_env_value(lines, "FLASK_SECRET_KEY"):
        return False

    lines = _set_env_line(lines, "FLASK_SECRET_KEY", secrets.token_hex(32))
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--username", help="Login username (prompted if omitted).")
    parser.add_argument(
        "--role", choices=["admin", "read_only"], default=None,
        help=(
            "Account role -- 'admin' can use /upload, 'read_only' cannot. "
            "Required when creating a new account (defaults to read_only if "
            "omitted); on an EXISTING account, omitting this leaves its "
            "current role unchanged rather than silently resetting it."
        ),
    )
    parser.add_argument(
        "--email", default=None,
        help=(
            "Account email, required for this account to use the self-service "
            "'Forgot password?' recovery flow (services/password_reset.py). "
            "Optional -- omit to leave unset (or unchanged, on an existing account)."
        ),
    )
    parser.add_argument(
        "--keep-password", action="store_true",
        help=(
            "Update only --role/--email on an EXISTING account, without "
            "prompting for or changing its password. Errors if the account "
            "doesn't exist yet (a brand-new account always needs a password)."
        ),
    )
    args = parser.parse_args(argv)

    username = args.username or input("Username: ").strip()
    if not username:
        print("Username cannot be empty.", file=sys.stderr)
        return 1

    from app import create_app
    from models import User, db

    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(username=username).first()

        if args.keep_password and existing is None:
            print(f"No existing user {username!r} -- --keep-password requires an account that already exists.", file=sys.stderr)
            return 1

        password = None
        if not args.keep_password:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if not password:
                print("Password cannot be empty.", file=sys.stderr)
                return 1
            if password != confirm:
                print("Passwords did not match.", file=sys.stderr)
                return 1

        generated_secret = _ensure_secret_key()

        user = existing
        verb = "Updated"
        if user is None:
            user = User(username=username)
            db.session.add(user)
            verb = "Created"

        if password is not None:
            user.password_hash = generate_password_hash(password)
        # Preserve the existing role on an update unless --role was given
        # explicitly -- the previous unconditional default("read_only")
        # silently demoted an existing admin account if you forgot to
        # repeat --role admin (real footgun this exact assignment surfaced,
        # not a hypothetical).
        user.role = args.role or (existing.role if existing is not None else "read_only")

        if args.email is not None:
            # Friendly, explicit check before commit -- the case-
            # insensitive UNIQUE index (models.py's User.email,
            # COLLATE NOCASE) is the real, authoritative backstop no
            # matter what calls this, but a bare IntegrityError
            # traceback here would be a bad way for an operator to
            # learn "one email may only belong to one account."
            candidate_email = args.email.strip().lower() or None
            if candidate_email is not None:
                collision_query = User.query.filter(db.func.lower(User.email) == candidate_email)
                if existing is not None:
                    collision_query = collision_query.filter(User.id != existing.id)
                collision = collision_query.first()
                if collision is not None:
                    print(
                        f"Email {candidate_email!r} is already assigned to user {collision.username!r} -- "
                        "one email may only belong to one account, and password reset requires that to "
                        "stay unambiguous. Choose a different address.",
                        file=sys.stderr,
                    )
                    return 1
            user.email = candidate_email

        db.session.commit()

        role_for_message = user.role
        password_note = "password unchanged" if password is None else "password updated"

    print(f"\n{verb} user {username!r} -- role: {role_for_message!r}, {password_note}.")
    if args.email is not None:
        print(f"Email set to {args.email.strip().lower() or None!r}.")
    if generated_secret:
        print(f"Generated FLASK_SECRET_KEY in {ENV_PATH} (was blank).")
    print("Restart the Flask app if it's running, then sign in at /login.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
