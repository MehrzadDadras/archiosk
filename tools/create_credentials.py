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
        "--role", choices=["admin", "read_only"], default="read_only",
        help="Account role -- 'admin' can use /upload, 'read_only' cannot. Default: read_only.",
    )
    args = parser.parse_args(argv)

    username = args.username or input("Username: ").strip()
    if not username:
        print("Username cannot be empty.", file=sys.stderr)
        return 1

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        return 1

    generated_secret = _ensure_secret_key()

    from app import create_app
    from models import User, db

    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        verb = "Updated"
        if user is None:
            user = User(username=username)
            db.session.add(user)
            verb = "Created"
        user.password_hash = generate_password_hash(password)
        user.role = args.role
        db.session.commit()

    print(f"\n{verb} user {username!r} with role {args.role!r}.")
    if generated_secret:
        print(f"Generated FLASK_SECRET_KEY in {ENV_PATH} (was blank).")
    print("Restart the Flask app if it's running, then sign in at /login.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
