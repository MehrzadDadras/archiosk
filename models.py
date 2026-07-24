"""
SQLAlchemy models for ArchiOSK / B-Hive.

Single `db = SQLAlchemy()` instance, created unbound (app-factory pattern)
and attached in app.py via db.init_app(app). Lives at the repo root, not
under services/ or routes/, so it has no dependency on either package --
services/auth.py and tools/create_credentials.py import from here, and
app.py imports this to call init_app/create_all. This module must never
import app.py, routes/, or services/ back (that would create a cycle).

Bootstrapped with db.create_all() (see app.py), not a migration tool
(Alembic/Flask-Migrate) -- this is the project's only table, and
tools/dependency_fit.py's minimal-dependency stance argues against
tooling this app doesn't need yet. Revisit if a second model or a real
schema change ever arrives.
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

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"
