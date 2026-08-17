#!/usr/bin/env python
"""
CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: create or revoke the one,
fixed-name live-verification identity (services/verification_access.py)
used for bounded, auditable real-browser proof work against archiosk.com.

This is a MAINTAINER-run tool, same as tools/create_credentials.py --
account provisioning in this codebase has always been CLI-only, never a
web route, never something an automated agent runs itself. Run this on
the server (or anywhere with access to the same REGISTRY_STORE_PATH/
DATABASE_URL the running app uses), then hand ONLY the printed one-time
URL to whoever is doing the live-browser verification -- never a
username/password, and never this command's own invocation.

    python tools/manage_verification_access.py create
    python tools/manage_verification_access.py create --ttl-minutes 30
    python tools/manage_verification_access.py revoke

`create` is safe to re-run: it reuses the existing identity if one is
already active (superseding any of its still-unused prior tokens) rather
than erroring, so a maintainer who forgets whether one is already active
never needs to check first. `revoke` deletes the identity and every token
that ever referenced it, then re-queries to prove zero rows remain --
printed explicitly, not merely asserted.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create/reuse the verification identity and issue a fresh one-time login link.")
    create_parser.add_argument(
        "--ttl-minutes", type=int, default=None,
        help="Minutes before the issued link expires (default: services.verification_access.DEFAULT_TOKEN_TTL_MINUTES).",
    )
    create_parser.add_argument(
        "--base-url", default="https://archiosk.com",
        help="Scheme+host to build the printed link against (default: https://archiosk.com).",
    )

    subparsers.add_parser("revoke", help="Delete the verification identity and every token that ever referenced it.")

    args = parser.parse_args(argv)

    from app import create_app
    from services.verification_access import (
        DEFAULT_TOKEN_TTL_MINUTES, VERIFICATION_ACCOUNT_USERNAME, create_verification_access,
        revoke_verification_access,
    )
    from models import User

    app = create_app()
    with app.app_context():
        if args.command == "create":
            ttl_minutes = args.ttl_minutes or DEFAULT_TOKEN_TTL_MINUTES
            user, raw_token = create_verification_access(ttl_minutes=ttl_minutes)
            login_url = f"{args.base_url.rstrip('/')}/verification-access/{raw_token}"
            print(f"\nVerification identity {user.username!r} (role={user.role!r}) is active.")
            print(f"One-time login link (expires in {ttl_minutes} minutes, single use):\n\n  {login_url}\n")
            print(
                "Hand ONLY this link to whoever is doing the live-browser verification -- "
                "never a username/password. Run this script's own `revoke` command when the "
                "verification pass is done, or let the link/session end on its own."
            )
            return 0

        if args.command == "revoke":
            existed = revoke_verification_access()
            remaining = User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).count()
            if existed:
                print(f"Verification identity {VERIFICATION_ACCOUNT_USERNAME!r} and all its tokens removed.")
            else:
                print(f"No verification identity {VERIFICATION_ACCOUNT_USERNAME!r} was active -- nothing to remove.")
            print(f"Residue check: {remaining} matching account row(s) remain (expected: 0).")
            return 0 if remaining == 0 else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
