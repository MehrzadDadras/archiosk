"""
SQLAlchemy models for ArchiOSK / B-Hive.

Single `db = SQLAlchemy()` instance, created unbound (app-factory pattern)
and attached in app.py via db.init_app(app). Lives at the repo root, not
under services/ or routes/, so it has no dependency on either package --
services/auth.py and tools/create_credentials.py import from here, and
app.py imports this to call init_app/create_all. This module must never
import app.py, routes/, or services/ back (that would create a cycle).

Bootstrapped with db.create_all() (see app.py), not a migration tool
(Alembic/Flask-Migrate) -- tools/dependency_fit.py's minimal-dependency
stance argues against tooling this app doesn't need yet.
create_all() only creates missing TABLES, never adds a missing COLUMN to
one that already exists on disk -- CLAUDE-P28 added `User.email` to an
already-deployed `users` table, so app.py's _register_database() also
runs one small, idempotent `ALTER TABLE` for that specific case. A
second genuine schema change (not just a second table) should prompt
revisiting real migration tooling rather than growing that by hand
again.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

ROLE_ADMIN = "admin"
ROLE_READ_ONLY = "read_only"
ROLES = (ROLE_ADMIN, ROLE_READ_ONLY)


class User(db.Model):
    """A named account for the session-based web UI login gate
    (services/auth.py). Provisioned exclusively via
    tools/create_credentials.py -- there is deliberately no
    self-registration route.

    role is a plain string, validated at the application layer (the CLI's
    --role choices), not a DB-level CHECK constraint -- with no migration
    tooling, a DB-level constraint would be painful to loosen later.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_READ_ONLY)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # Nullable -- every account provisioned before CLAUDE-P28 (password
    # reset) lacks one; SQLite's UNIQUE constraint permits any number of
    # NULL rows, so this doesn't collide across those legacy accounts.
    # An account with no email set simply can't use self-service reset
    # yet (see services/password_reset.py) -- tools/create_credentials.py
    # can add one to an existing account at any time.
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"


class PasswordResetToken(db.Model):
    """A single-use, expiring password-reset token (services/
    password_reset.py). Only `token_hash` (a SHA-256 digest) is ever
    stored -- the raw token exists solely in memory and in the link sent
    to the user, the same "never store the real secret" shape as
    User.password_hash never storing a plain password.

    This row IS the request/completion audit record required by
    CLAUDE-P28: `created_at` is the request, `used_at` (once set) is the
    completion -- no separate audit log was introduced for this.
    """
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PasswordResetToken user_id={self.user_id} used={self.used_at is not None}>"
