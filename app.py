"""
ArchiOSK / B-Hive — Flask application factory.

Run locally with:
    flask --app app run --debug

Run in production via Gunicorn (see deploy/gunicorn.service):
    gunicorn -c deploy/gunicorn.conf.py wsgi:app
"""
import logging
import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config


def create_app(config_name: str | None = None) -> Flask:
    if (config_name or os.getenv("FLASK_ENV", "production")) == "testing":
        # Tests must be hermetic regardless of what's configured in the
        # developer's local .env — a real ANTHROPIC_API_KEY set for local
        # dev/live verification must never cause the automated suite to
        # make real (billed, network-dependent, non-deterministic) model
        # calls. services/bhive_parser.py's classify/consistency stages
        # and services/requirement_investigation.py both read this env
        # var directly (not via app.config), so clearing it here, before
        # anything else runs, is the one point that actually controls
        # every call site. A test that wants to exercise the real-call
        # code path patches this back in locally for just that test (see
        # tests/test_requirement_investigation.py) rather than relying on
        # ambient environment state.
        os.environ["ANTHROPIC_API_KEY"] = ""

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    # CLAUDE-P27-B: deploy/nginx.conf is the one reverse proxy in front of
    # Gunicorn (deploy/gunicorn.conf.py binds 127.0.0.1 only -- nginx is
    # the sole path in), so trusting exactly one X-Forwarded-* hop is
    # correct here, not a blanket "trust everything" -- without this,
    # request.remote_addr is always nginx's own address for every
    # request, which would silently break any future per-IP control
    # (rate limiting, abuse blocking) rather than merely being imprecise.
    # In local dev (no nginx in front), these headers are simply absent
    # and remote_addr behaves exactly as it already does today.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    config_cls = get_config(config_name)
    app.config.from_object(config_cls)

    _configure_logging(app)
    _validate_production_config(app, config_cls)
    _register_database(app)
    _register_rate_limiter(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)
    _register_template_filters(app)

    return app


def _register_database(app: Flask) -> None:
    from pathlib import Path

    from models import db

    # app.instance_path defaults to <repo_root>/instance, matching
    # config.py's BASE_DIR / 'instance' -- creates the directory SQLite
    # needs before it tries to open a file there.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        # Idempotent -- safe to call on every worker boot. Fine for this
        # app's small handful of tables; revisit with real migration
        # tooling if the schema ever needs a change create_all() can't do.
        db.create_all()
        # create_all() only creates missing TABLES -- a `users` table
        # that already existed on disk before CLAUDE-P28 (password reset)
        # added User.email keeps missing that column forever otherwise,
        # breaking every query that touches User (including login) with
        # "no such column: users.email". Runs before any blueprint/route
        # is reachable, so this always executes ahead of the first login
        # query.
        _migrate_users_email_column(app)
        _migrate_users_email_case_insensitive_index(app)
        _migrate_users_is_active_column(app)


def _migrate_users_email_column(app: Flask) -> None:
    """
    Adds `users.email` in place, without touching any existing row, if
    it's missing -- column-presence check rather than a version table,
    so this is safe to call on every boot: a fresh install already has
    the column from create_all() above and this is a no-op there; an
    existing pre-P28 database gets exactly one ALTER, once, and every
    boot after that also no-ops. SQLite-specific (ALTER TABLE ADD COLUMN
    / CREATE UNIQUE INDEX IF NOT EXISTS), matching the rest of this
    project's SQLite-only stance for the `users` table -- not written to
    be portable to a different database engine.
    """
    from sqlalchemy import inspect, text

    from models import db

    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return  # brand-new install -- create_all() above just made it, with email already
    if "email" in {col["name"] for col in inspector.get_columns("users")}:
        return

    app.logger.info("Migrating 'users' table: adding missing 'email' column.")
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
        # Matches the UNIQUE INDEX name/shape SQLAlchemy itself generates
        # for `email = db.Column(..., unique=True, index=True)` on a
        # fresh install (verified against a fresh create_all() output) --
        # a later fresh install and a migrated old one end up with an
        # identical schema, not two different paths to the same effect.
        # Not yet case-insensitive -- _migrate_users_email_case_
        # insensitive_index (below) fixes that separately, since
        # models.py didn't declare COLLATE NOCASE until CLAUDE-P30.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)"))


def _migrate_users_email_case_insensitive_index(app: Flask) -> None:
    """
    CLAUDE-P30: the UNIQUE index on `users.email` (created either just
    above, or by create_all() on a database old enough to predate this
    function) is case-sensitive by default -- 'Admin@x.com' and
    'admin@x.com' could each exist as a different row while being the
    same real-world identity, which would make password-reset's email
    lookup (services/password_reset.py's _find_user_by_email, itself
    already case-insensitive) genuinely AMBIGUOUS between two accounts,
    not merely inconvenient. models.py's User.email column now declares
    COLLATE NOCASE, so a truly fresh install's own create_all() already
    gets this right from the start; this migration brings an EXISTING
    database's index up to the same guarantee without needing to
    rebuild the users table itself -- SQLite can't ALTER a column's
    collation in place, but a replacement index can specify its own
    COLLATE independent of the underlying column's declared one
    (verified empirically: a COLLATE NOCASE unique index rejects a
    case-variant duplicate insert even against a plain, uncollated
    column).

    Checked via the index's own recorded SQL text in sqlite_master
    (idempotent -- a NOCASE index found already is a no-op), not a
    version table. If creating the replacement index ever fails here,
    that means real case-variant duplicate emails already exist in the
    table -- a genuine data problem this deliberately does not paper
    over by silently deleting/merging rows on someone's behalf; the
    IntegrityError is left to surface so a human resolves which of the
    colliding accounts is correct.
    """
    from sqlalchemy import inspect, text

    from models import db

    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return

    with db.engine.begin() as conn:
        existing_sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='index' AND name='ix_users_email'"),
        ).scalar()
        if existing_sql and "NOCASE" in existing_sql:
            return  # already case-insensitive

        app.logger.info("Migrating 'users' table: making the email UNIQUE index case-insensitive.")
        if existing_sql:
            conn.execute(text("DROP INDEX ix_users_email"))
        conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email COLLATE NOCASE)"))


def _migrate_users_is_active_column(app: Flask) -> None:
    """
    CLAUDE-P27-B: same column-presence-check pattern as
    _migrate_users_email_column above -- adds `users.is_active` in place,
    defaulted True, if it's missing. A fresh install's create_all()
    already has it (models.py); an existing pre-P27-B database gets
    exactly one ALTER, once, and every boot after that no-ops. SQLite's
    ALTER TABLE ADD COLUMN requires a constant DEFAULT to satisfy the new
    NOT NULL on existing rows -- `1` (true), matching every existing
    account being unaffected until explicitly suspended.
    """
    from sqlalchemy import inspect, text

    from models import db

    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return
    if "is_active" in {col["name"] for col in inspector.get_columns("users")}:
        return

    app.logger.info("Migrating 'users' table: adding missing 'is_active' column.")
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))


def _validate_production_config(app: Flask, config_cls) -> None:
    """
    Hard-fail-fast boot check under ProductionConfig specifically
    (CLAUDE-P27-B). config.py's own BaseConfig.validate() existed but was
    never called anywhere -- a misconfigured "production" deploy (e.g.
    FLASK_SECRET_KEY unset) previously booted and served traffic with
    broken session integrity, only surfacing the problem reactively if
    something happened to poll /health.

    Deliberately narrower than validate()'s own missing-vars list:
    FLASK_SECRET_KEY has no safe fallback and must hard-fail; a missing
    ANTHROPIC_API_KEY is the one deliberately optional cloud dependency
    (tools/dependency_fit.py's graceful-degradation stance; README's
    "Without an Anthropic API key" section) and must keep degrading to
    the rule-based classifier, not crash the app -- so it only warns.
    """
    from config import ProductionConfig

    if config_cls is not ProductionConfig:
        return

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "Refusing to start under ProductionConfig: FLASK_SECRET_KEY is unset. "
            "Set it in .env before starting the production server.",
        )
    if app.debug or app.testing:
        # Structurally impossible today -- ProductionConfig sets neither
        # DEBUG nor TESTING true (config.py) -- kept as an explicit
        # assertion so a future change to that class can't silently
        # reopen the dev-only password-reset-link fallback
        # (services/password_reset.py's is_dev_fallback_active(), gated
        # on exactly these two flags) in a real production deploy.
        raise RuntimeError(
            "Refusing to start: ProductionConfig resolved with DEBUG or TESTING "
            "true, which would also reopen the dev-only password-reset fallback.",
        )
    if not app.config.get("ANTHROPIC_API_KEY"):
        app.logger.warning(
            "ANTHROPIC_API_KEY is unset under ProductionConfig -- classification "
            "will use the deterministic rule-based fallback instead of the model. "
            "This is a supported, deliberate degradation, not a boot failure.",
        )


def _register_rate_limiter(app: Flask) -> None:
    from services.rate_limit import limiter

    limiter.init_app(app)


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _register_blueprints(app: Flask) -> None:
    from routes.portal import portal_bp
    from routes.api import api_bp
    from routes.workspace import workspace_bp

    app.register_blueprint(portal_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(workspace_bp)


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify, render_template, url_for

    # All three dead-end error pages (403/404/500) are the same shape - one
    # message, one way out, no ongoing state - so they're one parameterized
    # template (errors/error.html), not three near-identical files.
    def _render_error(code, heading, message, action_url, action_label):
        return render_template(
            "errors/error.html", code=code, heading=heading, message=message,
            action_url=action_url, action_label=action_label,
        )

    @app.errorhandler(404)
    def not_found(_err):
        if _wants_json():
            return jsonify(error="not_found", message="Resource not found."), 404
        return _render_error(
            404, "Page not found", "The page or document you're looking for doesn't exist.",
            url_for("portal.index"), "Back to home",
        ), 404

    @app.errorhandler(500)
    def server_error(err):
        app.logger.exception("Unhandled server error: %s", err)
        if _wants_json():
            return jsonify(error="server_error", message="Something went wrong."), 500
        return _render_error(
            500, "Something went wrong", "The error has been logged. Please try again shortly.",
            url_for("portal.index"), "Back to home",
        ), 500

    @app.errorhandler(403)
    def forbidden(_err):
        if _wants_json():
            return jsonify(error="forbidden", message="You do not have permission to access this resource."), 403
        return _render_error(
            403, "Access restricted", "Your account doesn't have permission to view this page.",
            url_for("portal.projects_list"), "Back to Projects",
        ), 403

    def _wants_json() -> bool:
        from flask import request
        return request.path.startswith("/api/")


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        from datetime import datetime, timezone

        from services.auth import is_admin, is_authenticated

        return {
            "current_year": datetime.now(timezone.utc).year,
            "static_version": app.config["STATIC_VERSION"],
            "authenticated": is_authenticated(),
            "is_admin": is_admin(),
            "nav_recent_projects": _nav_recent_projects(app) if is_authenticated() else [],
        }


def _register_template_filters(app: Flask) -> None:
    from services.formatting import humanize_timestamp

    app.jinja_env.filters["humanize"] = humanize_timestamp


def _nav_recent_projects(app: Flask, limit: int = 15) -> list:
    """
    Read-only project list feeding the sidebar's "Projects" tree node.
    Reuses the same RequirementsRegistry already used by
    routes/portal.py's project directory; no new storage or domain
    behavior. Runs on every authenticated page render (the rail is part
    of the shared shell) and is capped at `limit` projects, so the added
    per-project CaseWorkspaceStore.get() below (needed for display_name -
    see pagescape correction #11: a project's visible identity should be
    its own display_title, not whichever filename happened to be
    ingested first) stays a bounded cost, not an unbounded one - the
    same per-project store-load cost portal.py's own _project_summary
    already pays for the Projects directory and Home.

    OPEN, NOT YET JUSTIFIED TO FIX: "recent" here means ingested_at - a
    timestamp set once, at creation, that never changes. A project
    ingested weeks ago but actively worked on today can rank below one
    ingested yesterday and never opened since, in the one navigation
    element shown on every authenticated page. routes/portal.py's
    _project_summary already computes a truer signal
    (last_activity = the most recent GovernanceLog event, falling back
    to ingested_at) for the Projects directory's own "Last Updated"
    sort - but it needs each project's governance log read to get it,
    and this function's whole cost structure depends on sorting+capping
    on a free, already-in-memory field before paying any per-project
    I/O (see above). Sorting by last_activity here would mean reading
    every project's governance log on every authenticated page load,
    not just the capped 15 - trading a real, currently-bounded cost for
    a real, worse one, not a free correctness win. A real fix needs
    last_activity cached cheaply (e.g. a field on the registry record
    itself, updated incrementally when a governance event is appended)
    so it's as free to sort on as ingested_at is now - not attempted
    here.
    """
    from services.case_workspace import CaseWorkspaceStore
    from services.ingestion import get_registry

    try:
        registry = get_registry(app)
        documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    except OSError:
        return []
    documents.sort(key=lambda d: d.ingested_at, reverse=True)
    documents = documents[:limit]

    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    result = []
    for d in documents:
        # Best-effort, display-only: a workspace file that predates the
        # current schema must not crash the sidebar on every authenticated
        # page (including error pages, since this runs in inject_globals)
        # - discovered live during this pass against a pre-existing
        # instance/registry project. Degrades to the plain filename for
        # that one project rather than taking the whole render down.
        try:
            workspace = store.get(d.project_id)
        except TypeError:
            workspace = None
        display_name = (workspace.display_title if workspace else None) or d.filename
        result.append({"project_id": d.project_id, "filename": d.filename, "display_name": display_name})
    return result


# Local dev entrypoint: `python app.py`
# debug=True's reloader can leave orphaned parent/child chains behind
# across repeated restarts in some environments; a stale process in that
# chain keeps serving a stale .env snapshot. Use the `restart-app` skill
# (.claude/skills/restart-app/) for a clean restart instead of trusting
# that killing the PID on the port is enough.
if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
