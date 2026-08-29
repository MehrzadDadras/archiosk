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
create_all() only creates missing TABLES, never adds a missing COLUMN
(or changes a column's collation) on one that already exists on disk --
CLAUDE-P28 added `User.email` to an already-deployed `users` table, and
CLAUDE-P30 needed that column's UNIQUE constraint to become case-
insensitive after the fact, so app.py's _register_database() runs two
small, idempotent hand-written migrations for those specific cases. A
third genuine schema change (not just a second/third table) should
prompt revisiting real migration tooling rather than growing this by
hand again.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates

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
    # CLAUDE-P27-B: a suspended account can't sign in (services.auth.
    # check_credentials) but is otherwise left alone -- no data touched,
    # no cascading effect on projects/cases, reversible by flipping this
    # back. Defaults True so every pre-existing and newly-created account
    # is unaffected until an operator explicitly suspends one via
    # tools/create_credentials.py --suspend.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Nullable -- every account provisioned before CLAUDE-P28 (password
    # reset) lacks one; SQLite's UNIQUE constraint permits any number of
    # NULL rows, so this doesn't collide across those legacy accounts.
    # An account with no email set simply can't use self-service reset
    # yet (see services/password_reset.py) -- tools/create_credentials.py
    # can add one to an existing account at any time. NEVER give a real
    # human's email to a development/test account "just because a field
    # exists for it" -- test accounts should only get one at all when a
    # test genuinely needs it, and then a distinct, non-deliverable
    # *.invalid address (RFC 2606), never a real inbox.
    #
    # CLAUDE-P30: declared COLLATE NOCASE so a fresh install's
    # create_all()-generated UNIQUE constraint is case-insensitive from
    # day one (matching app.py's hand-migrated fix for the DB that
    # already existed before this - see _migrate_users_email_case_
    # insensitive_index there). Without this, 'Admin@x.com' and
    # 'admin@x.com' could each satisfy a case-SENSITIVE UNIQUE
    # constraint as two different rows while being the same real-world
    # identity - _find_user_by_email's own .first() would then pick
    # between them arbitrarily, making password reset genuinely
    # ambiguous between two accounts. SQLite's NOCASE only folds ASCII
    # A-Z, not full Unicode case-folding -- an accepted limitation for
    # email addresses, which are ASCII-dominant in practice; not hidden.
    email = db.Column(db.String(255, collation="NOCASE"), unique=True, nullable=True, index=True)

    @validates("email")
    def _normalize_email(self, key, value):
        """
        Every write path normalizes through here (not just
        tools/create_credentials.py's own .strip().lower() call) -- a
        future caller that sets user.email directly without remembering
        to normalize first must not be able to create a case-variant
        near-duplicate the UNIQUE constraint's collation would still
        catch, but inconsistently-cased data would still be an honesty
        problem (e.g. two lookups that ought to be the same query
        rendering differently in an audit log).
        """
        if value is None:
            return None
        value = value.strip().lower()
        return value or None

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


class VerificationAccessToken(db.Model):
    """CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: a single-use, expiring
    LOGIN token (not a password-reset token) for a dedicated, ephemeral
    verification identity (see services/verification_access.py). Same
    "never store the real secret" shape as PasswordResetToken -- only
    `token_hash` is ever persisted, the raw token exists solely in the
    one-time link a maintainer generates via tools/manage_verification_
    access.py's own `create` command, never through a web route (this
    codebase has no self-registration route for ACCOUNTS, and this is
    account provisioning, not a self-service password change like
    PasswordResetToken's own use case).

    `created_at`/`used_at` are this token's own audit record, same
    precedent as PasswordResetToken. The linked User row (see
    services/verification_access.py's VERIFICATION_ACCOUNT_USERNAME) is
    itself deleted by the `revoke` CLI command, cascading this token away
    with it -- there is deliberately no long-lived verification account
    sitting at rest between uses.
    """
    __tablename__ = "verification_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<VerificationAccessToken user_id={self.user_id} used={self.used_at is not None}>"


class StorageAgentEnrolment(db.Model):
    """CLAUDE-STORAGE-BRIDGE-03: which agent may speak for which project.

    A private-network agent (on or beside a WD My Cloud EX4100, a file server, a
    NAS in a cupboard) authenticates ITSELF to ARCHIOSK with this token, then
    polls outbound over HTTPS. ARCHIOSK never dials in, and never learns a NAS
    credential - how the agent reaches its own storage stays on its own side of
    the boundary, and there is deliberately no column here that could hold such
    a secret even if someone tried.

    SAME "NEVER STORE THE REAL SECRET" SHAPE as PasswordResetToken and
    VerificationAccessToken: only `token_hash` is persisted. The raw token
    exists once, in what the enrolling maintainer is shown, and nowhere after.

    WHY THE DATABASE AND NOT THE FLAT-JSON STORE. The same reason
    DiagnosticReport records: routes/portal.py's Reset/Restore RENAMES the whole
    registry store directory away and installs a staged replacement. An
    enrolment living there would be destroyed by a project-data reset, which
    would silently disconnect a working agent and look, from the outside, like
    the NAS had failed. It also sits naturally beside the operator-scoped rows
    that are already here.

    `project_id` is a plain string, not a foreign key - deliberately, because
    projects live in the flat-JSON store and have no table to point at. That
    matches how ProjectWorkspace.owner already works.

    REVOKING IS NOT DELETING. `revoked_at` is set; the row stays. A withdrawn
    credential means bytes stop arriving, and must never mean the project forgets
    what it knew or that the audit trail of who could read it disappears.
    """
    __tablename__ = "storage_agent_enrolments"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(255), nullable=False, index=True)
    agent_label = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by = db.Column(db.String(255), nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return (f"<StorageAgentEnrolment project={self.project_id} "
                f"agent={self.agent_label} revoked={self.revoked_at is not None}>")


class DiagnosticReport(db.Model):
    """CLAUDE-DIAGNOSTIC-BRIDGE-01: one live product problem, captured in the
    application that produced it, for a development agent to investigate.

    WHY THIS IS A DATABASE ROW AND NOT A WORKSPACE RECORD

    The same reasoning that governs access requests: routes/portal.py's
    Reset/Restore RENAMES the whole registry store directory away and installs a
    staged replacement, so anything living in the flat-JSON store is wholesale
    replaced by a project reset. A diagnostic about the APPLICATION must not die
    because somebody reset a PROJECT. It is also not project data - it is about
    the product, and its natural neighbours are the other operator-scoped rows
    already here.

    WHAT THIS DELIBERATELY IS NOT

    Not a message queue, and not a channel. Nothing here is transmitted to a
    development agent: ARCHIOSK cannot call one, because it runs on an operator's
    own machine when a human starts it. This row is INERT DATA that a Claude Code
    session reads when asked to. That is the boundary the Product Owner required,
    and it holds structurally rather than by policy - a record with no mechanism
    cannot grant permission to change code or deploy anything.

    IDENTIFIERS, NOT CONTENT. `project_id`/`case_id` are recorded so an
    investigator can go and read the real thing from the repository and the
    store; the project's documents and conversation text are NOT copied here.
    `detail` carries what the Product Owner chose to type, never anything
    harvested from a project behind them.

    STATUS makes the Product Owner's required separation structural: capture
    (`open`) -> investigation (`investigated`, findings written by the agent) ->
    notification (`emailed_at`). Code modification and deployment are
    deliberately NOT states here, because they are not this record's business and
    must never look like a step it can advance itself to.
    """
    __tablename__ = "diagnostic_reports"

    STATUS_OPEN = "open"
    STATUS_INVESTIGATED = "investigated"
    STATUS_CLOSED = "closed"

    id = db.Column(db.Integer, primary_key=True)

    # --- what the Product Owner reported ------------------------------------
    reported_by = db.Column(db.String(120), nullable=False)
    reported_at = db.Column(db.DateTime, nullable=False,
                            default=lambda: datetime.now(timezone.utc))
    summary = db.Column(db.String(300), nullable=False)
    detail = db.Column(db.Text, nullable=True)

    # --- what the application already knew, so nobody retypes it ------------
    surface = db.Column(db.String(300), nullable=True)
    project_id = db.Column(db.String(64), nullable=True, index=True)
    case_id = db.Column(db.String(64), nullable=True)
    build_sha = db.Column(db.String(64), nullable=True)
    static_version = db.Column(db.String(32), nullable=True)
    trace = db.Column(db.Text, nullable=True)

    # --- what the investigation concluded -----------------------------------
    status = db.Column(db.String(24), nullable=False, default=STATUS_OPEN, index=True)
    findings = db.Column(db.Text, nullable=True)
    root_cause = db.Column(db.Text, nullable=True)
    affected = db.Column(db.Text, nullable=True)
    recommendation = db.Column(db.Text, nullable=True)
    commit_status = db.Column(db.Text, nullable=True)
    uncertainty = db.Column(db.Text, nullable=True)
    investigated_at = db.Column(db.DateTime, nullable=True)

    # --- notification, a separate act again ---------------------------------
    emailed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<DiagnosticReport {self.id} {self.status}>"


class ProjectAccessToken(db.Model):
    """CLAUDE-RBAC-TOKENS-01: which stakeholder may read which discipline of
    which project, and until when.

    THE SHAPE IS DELIBERATELY THE ONE THIS CODEBASE ALREADY USES, four times
    over -- PasswordResetToken, VerificationAccessToken, StorageAgentEnrolment
    and now this: only `token_hash` (a SHA-256 digest) is ever persisted. The
    raw token exists once, in what the issuing architect is shown, and nowhere
    after. There is no column here capable of holding a usable secret, which is
    a stronger statement than a promise not to write one.

    `project_id` is a plain string, not a foreign key, for the same reason
    StorageAgentEnrolment's is: projects live in the flat-JSON registry store
    and have no table to point at.

    WHY THE DATABASE AND NOT THE FLAT-JSON STORE. Identical to
    StorageAgentEnrolment's own recorded reasoning: `routes/portal.py`'s
    Reset/Restore RENAMES the whole registry store directory away and installs
    a staged replacement. An access grant living there would be destroyed by a
    project-data reset -- silently widening or revoking access as a side effect
    of an unrelated operation, which is the worst possible way for an
    authorization record to change.

    REVOKING IS NOT DELETING. `revoked_at` is set and the row stays. A
    withdrawn credential must mean access stops, never that the record of who
    could once read the drawings disappears.

    `disciplines` is a comma-separated subset of services.project_rbac's own
    closed DISCIPLINES vocabulary, or NULL meaning "every discipline". NULL is
    only ever written for roles that genuinely span the project (architect,
    owner); services.project_rbac.issue_token REFUSES to issue a scoped role
    with no disciplines named, because an empty scope that could be read as
    either "all" or "none" is not a thing to resolve later at read time.
    """
    __tablename__ = "project_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(255), nullable=False, index=True)
    role = db.Column(db.String(32), nullable=False)
    disciplines = db.Column(db.String(255), nullable=True)
    label = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by = db.Column(db.String(255), nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return (f"<ProjectAccessToken project={self.project_id} role={self.role} "
                f"revoked={self.revoked_at is not None}>")


class ArchitectEscalation(db.Model):
    """CLAUDE-RBAC-TOKENS-02: a question GO could not answer, handed to a human.

    WHEN GO CANNOT RESOLVE something, the honest reply is that it cannot ("Sorry,
    this is out of my league. Help is underway.") and the useful action is to put
    the question in front of the project's architect with enough context to answer
    it quickly. This row IS that queue.

    WHY THE DATABASE AND NOT THE FLAT-JSON STORE. Same reasoning DiagnosticReport
    and StorageAgentEnrolment already record: `routes/portal.py`'s Reset/Restore
    RENAMES the whole registry store directory away. An unanswered question must
    not vanish because somebody reset project data - that is precisely the moment
    somebody is waiting for a reply.

    WHAT IT DELIBERATELY IS NOT. Not a message channel and not a notification
    transport. Nothing here is emailed, pushed or sent anywhere; ARCHIOSK does not
    dial out on a friction event. It is inert data an architect reads. Adding a
    transport is a separate, consequential decision with its own authorization -
    see services/email.py's own gating for the precedent.

    `asked_by_role` and `project_id` are copied FROM the presenting token, never
    from anything the caller typed. A trade contractor cannot file an escalation
    that claims to be an architect's, or one belonging to another project, because
    there is no parameter through which either could be supplied.

    `query_text` is the person's own words, verbatim. It is stored as given and
    never rewritten: an escalation that paraphrases the question makes the
    architect answer a question nobody asked.
    """
    __tablename__ = "architect_escalations"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(255), nullable=False, index=True)
    token_id = db.Column(db.Integer, db.ForeignKey("project_access_tokens.id"),
                         nullable=True, index=True)
    asked_by_role = db.Column(db.String(32), nullable=False)
    sheet_id = db.Column(db.String(64), nullable=True)
    view_box = db.Column(db.String(128), nullable=True)
    query_text = db.Column(db.Text, nullable=False)
    friction_signal = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (f"<ArchitectEscalation project={self.project_id} "
                f"sheet={self.sheet_id} resolved={self.resolved_at is not None}>")


class TrialAllowance(db.Model):
    """CLAUDE-TRIAL-SAFE-LANDING-01: how much model-backed work a trial project
    has used.

    ONE ROW PER PROJECT, counting OUTBOUND LLM CALLS ONLY. Nothing about
    reading a drawing, zooming, panning, navigating sheets or opening a split
    pane is recorded here or affected by it - that is the promise the safe
    landing message makes ("the system allows you to get home safely"), and a
    counter that also metered the viewer would quietly make it false.

    WHY THE DATABASE. Same reasoning as ProjectAccessToken and
    ArchitectEscalation: `routes/portal.py`'s Reset/Restore renames the whole
    registry store away, so a quota living in the flat-JSON store would silently
    reset itself - handing out unlimited trial usage to anyone who noticed.

    `used_count` only ever increases. There is deliberately no decrement and no
    expiry sweep: a trial allowance that quietly refilled would make the message
    a lie the second time somebody saw it.
    """
    __tablename__ = "trial_allowances"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    used_count = db.Column(db.Integer, nullable=False, default=0)
    first_used_at = db.Column(db.DateTime, nullable=True)
    exhausted_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return (f"<TrialAllowance project={self.project_id} "
                f"used={self.used_count} exhausted={self.exhausted_at is not None}>")
