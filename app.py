"""
ArchiOSK / B-Hive — Flask application factory.

Run locally with:
    flask --app app run --debug

Run in production via Gunicorn (see deploy/gunicorn.service):
    gunicorn -c deploy/gunicorn.conf.py wsgi:app
"""
import logging
import os
import secrets

from flask import Flask
from flask_wtf import CSRFProtect
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
    _register_csrf(app)
    _register_security_headers(app)
    _register_error_handlers(app)
    _register_context_processors(app)
    _register_template_filters(app)
    _recover_registry_before_serving(app)
    _register_registry_guard(app)

    return app


def _recover_registry_before_serving(app: Flask) -> None:
    """
    CLAUDE-P40-E2A2, Section B: "Before application code reads the
    registry ... detect an incomplete transaction." create_app() fully
    completes before app.run()/the WSGI server ever accepts a request,
    so calling this here - unconditionally, in every config including
    "testing" (Section E's own failure-injection tests instantiate the
    app exactly this way to prove recovery runs automatically on
    "restart", not via a separate step a test has to remember to call) -
    guarantees no route handler in this process can read
    REGISTRY_STORE_PATH before any interrupted Reset/Restore from a
    prior process has already been resolved. A no-op, near-free, for
    the overwhelming majority of boots where no transaction was ever
    left mid-flight (no reset_transactions/ directory exists yet).
    """
    from routes.portal import _recover_interrupted_transactions

    _recover_interrupted_transactions(app)


def _register_registry_guard(app: Flask) -> None:
    """
    CLAUDE-P40-E2A2, Section B: "Do not start the application against a
    missing, mixed, or unverified registry." If
    _recover_registry_before_serving (or a later on-demand recovery
    pass triggered from the Reset/Restore admin pages themselves) could
    not resolve some interrupted transaction safely, it sets
    app.config["REGISTRY_RECOVERY_FAILED"] rather than guessing - this
    hook then fails EVERY request closed with a plain 503 instead of
    letting ordinary pages silently read a registry nobody has verified,
    except /health (the one diagnostic surface that must keep reporting
    the real failure - see that route's own registry check) and static
    assets (so the 503 page itself can still be styled).
    """
    @app.before_request
    def _block_when_registry_recovery_failed():
        from flask import request

        if not app.config.get("REGISTRY_RECOVERY_FAILED"):
            return None
        if request.path == "/health" or request.path.startswith("/static/"):
            return None
        return (
            "Registry needs administrator attention - an interrupted Reset/Restore "
            "operation could not be automatically recovered. See /admin/reset-project-data "
            "/snapshots for diagnostics once this is resolved.",
            503,
        )


def _register_database(app: Flask) -> None:
    from pathlib import Path

    from flask_migrate import Migrate
    from models import db

    # app.instance_path defaults to <repo_root>/instance, matching
    # config.py's BASE_DIR / 'instance' -- creates the directory SQLite
    # needs before it tries to open a file there.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    # CLAUDE-P27-B: registers the `flask db ...` CLI (migrations/) for
    # THE NEXT schema change onward -- models.py's own docstring already
    # flagged that a third genuine schema change (this session's
    # tenancy design package, governance/specified-unbuilt/) should be
    # the trigger to stop hand-writing ALTER TABLE blocks. Does NOT
    # replace or change how this already-deployed schema is created/
    # migrated below -- create_all() and the two _migrate_users_*
    # functions are untouched, still the mechanism that actually runs
    # at every boot. The live database was `flask db stamp`-ed to this
    # migration's baseline revision (see migrations/README, not
    # re-executed) so `flask db upgrade` is ready to use starting with
    # the next real schema change.
    Migrate(app, db)
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
    _validate_smtp_config(app)


def _validate_smtp_config(app: Flask) -> None:
    """
    SMTP finalization (CLAUDE-P27-B): SMTP_HOST unset is a fully
    supported, deliberate state (config.py's own comment) -- nothing
    here fires unless an operator has started configuring SMTP at all.
    Every check below only warns, never hard-fails: a misconfigured
    SMTP setup should degrade to "password reset silently doesn't
    deliver, visible in the log" (services/password_reset.py already
    logs delivery success/failure per request), never take down the
    whole app the way a missing FLASK_SECRET_KEY does -- there's no
    equivalent "everything is broken" consequence to a bad SMTP_FROM.
    """
    if not app.config.get("SMTP_HOST"):
        return

    if app.config.get("SMTP_USE_SSL") and app.config.get("SMTP_USE_TLS"):
        app.logger.warning(
            "SMTP_USE_SSL and SMTP_USE_TLS are both true -- these are mutually "
            "exclusive transports (implicit TLS vs. STARTTLS), not additive. "
            "services/email.py uses SMTP_USE_SSL when both are set; if that "
            "wasn't the intent, unset the one you don't mean.",
        )
    if not app.config.get("SMTP_FROM"):
        app.logger.warning(
            "SMTP_HOST is set but SMTP_FROM resolves empty (SMTP_FROM and "
            "SMTP_USERNAME both unset) -- outgoing mail would have a blank "
            "From: header and most providers will reject it outright.",
        )
    if app.config.get("SMTP_USERNAME") and not app.config.get("SMTP_PASSWORD"):
        app.logger.warning(
            "SMTP_USERNAME is set but SMTP_PASSWORD is blank -- authentication "
            "will fail on every send attempt.",
        )


def _register_csrf(app: Flask) -> None:
    """
    CLAUDE-P27-B: every state-changing route was previously unprotected
    against CSRF. templates/base.html injects a hidden csrf_token field
    into every POST <form> on every page (see that file's own comment)
    -- CSRFProtect() here is what actually validates it on the way in,
    and what makes the csrf_token() Jinja global those templates call
    exist at all.

    routes/api.py is exempted: it's documented (README, CLAUDE-P27-B's
    own Step 1) as a curl/script-consumed JSON API, not a browser page a
    third-party site could trick into submitting a form -- the classic
    CSRF attack shape. The primary CSRF vector (a forged cross-site POST
    silently carrying the victim's session cookie) is already blocked
    app-wide by SESSION_COOKIE_SAMESITE="Lax" (config.py) regardless of
    this exemption; requiring API callers to also juggle a CSRF token
    would regress the plain curl -b cookies.txt usage Step 1 documented,
    for a client population this protection doesn't meaningfully target.
    """
    from routes.api import api_bp

    csrf = CSRFProtect()
    csrf.init_app(app)
    csrf.exempt(api_bp)


def get_csp_nonce() -> str:
    """
    CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01: one fresh, unguessable value per
    request, cached on flask.g so every template/script tag in the same
    response shares the identical nonce the response header advertises.

    Root cause this exists to fix: deploy/nginx.conf's own
    Content-Security-Policy header (default-src 'self', no
    'unsafe-inline') was blocking every inline <script> tag on every page
    in production, silently and with no console error -- confirmed by a
    live-browser comparison (works with no CSP on the local dev server,
    fails identically to a real user report against archiosk.com) and
    already independently diagnosed once before for a narrower case
    (tests/test_ca1d_reception_fix_01.py's login-password-toggle fix).
    That fix externalized one small script to a static file; this one
    generalizes properly instead of externalizing all ~18 remaining
    inline scripts (several of which interpolate a Jinja value like
    project_id directly into the script body, which a static file
    can't do) -- CSP ownership moves from nginx (which can't vary
    per-request) to Flask, which can mint a fresh nonce every request.
    """
    from flask import g

    if not hasattr(g, "csp_nonce"):
        g.csp_nonce = secrets.token_urlsafe(16)
    return g.csp_nonce


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def set_csp_header(response):
        nonce = get_csp_nonce()
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'none'; object-src 'none'; "
            # CLAUDE-EYE-COMPARE-01: img-src has no directive of its own,
            # so it silently fell back to default-src 'self' - which does
            # NOT cover the data: scheme (a different scheme, not "same
            # origin" under CSP's own matching rules). This is the real
            # root cause of "pasted images do not display" (Eye's own
            # preview, static/js/eye_pane.js's showCanvas(), has always
            # rendered via `image.src = <a data: URL from FileReader>`,
            # confirmed live: a real, well-formed data: image URL fails
            # to load with img-src absent, and succeeds once data: is
            # explicitly allowed here) - not a bug in that code itself.
            # data: is safe to allow broadly for img-src specifically
            # (unlike script-src) - a data: URI can only ever decode to
            # pixels, never execute as script.
            "img-src 'self' data:; "
            f"script-src 'self' 'nonce-{nonce}'"
        )
        return response


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
    from routes.security import security_bp
    from routes.operations import operations_bp

    app.register_blueprint(portal_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(workspace_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(operations_bp)


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify, render_template, url_for

    # All three dead-end error pages (403/404/500) are the same shape - one
    # message, one way out, no ongoing state - so they're one parameterized
    # template (errors/error.html), not three near-identical files.
    def _render_error(code, heading, message, action_url, action_label, ui_ref=None):
        return render_template(
            "errors/error.html", code=code, heading=heading, message=message,
            action_url=action_url, action_label=action_label, ui_ref=ui_ref,
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

    @app.errorhandler(413)
    def file_too_large(_err):
        # CLAUDE-P40-VW8-QA (Project-Creation Upload-Capacity Correction):
        # RequestEntityTooLarge is raised by Werkzeug's own form parser,
        # BEFORE routes/portal.py:upload's view function ever runs - no
        # Project/Document/workspace/temp file is ever created for a
        # request that fails here (ingest_upload is never called), so
        # there is nothing to roll back, only a clear message and a way
        # back to the same form. routes/api.py's own blueprint-scoped
        # RequestEntityTooLarge handler (JSON) still applies to /api/v1/*
        # requests specifically - this app-level one is what every OTHER
        # route (chiefly the real upload FORM) previously fell through to
        # Werkzeug's raw, unstyled default page for.
        if _wants_json():
            return jsonify(error="file_too_large", message=_upload_too_large_message(app)), 413
        return _render_error(
            413, "File too large", _upload_too_large_message(app),
            url_for("portal.upload"), "Choose a different file",
            ui_ref="errors.upload-too-large",
        ), 413

    def _upload_too_large_message(app) -> str:
        max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return (
            f"That file is larger than the current maximum of {max_mb}MB. "
            "Choose a smaller file, or reduce its size, and try again."
        )

    def _wants_json() -> bool:
        from flask import request
        return request.path.startswith("/api/")


_STANDALONE_AUTH_ENDPOINTS = {"portal.login", "portal.forgot_password", "portal.reset_password"}

# CLAUDE-P40-VW5: the Gateway (templates/gateway_shell.html) is a
# SECOND standalone shell, distinct from the auth pages above - it
# genuinely needs real authenticated/is_admin/current_username (its
# own minimal account menu), unlike /login etc., which mask those
# outright. What it never needs is nav_recent_projects - it has no
# Lists panel to feed at all. Same principle as the auth-page guard's
# own comment below ("the query and the data being present at all was
# the defect, not just its rendering") applied to the one query that's
# actually irrelevant here, not the whole context.
_NO_PROJECT_LISTING_ENDPOINTS = _STANDALONE_AUTH_ENDPOINTS | {"portal.gateway"}


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        from datetime import datetime, timezone

        from flask import request, session

        from services.auth import is_admin, is_authenticated
        from services.case_workspace import CaseWorkspaceStore
        from services.verification_access import is_verification_session

        # CLAUDE-P40-D1: /login, /forgot-password, /reset-password render
        # templates/auth_shell.html, a standalone shell that never
        # references authenticated/is_admin/nav_recent_projects at all -
        # but this context processor runs for EVERY render_template call
        # regardless of which template is actually used. Without this
        # guard, an already-authenticated session hitting one of these
        # routes would still silently run the real nav_recent_projects
        # store query (a real information-boundary problem even before
        # any markup renders it) and this response's own template
        # context would still say authenticated=True. Hiding leaked
        # markup with CSS was never the actual defect - the query and
        # the context data being present at all was.
        on_standalone_auth_page = request.endpoint in _STANDALONE_AUTH_ENDPOINTS
        authenticated = is_authenticated() and not on_standalone_auth_page
        skip_project_listing = request.endpoint in _NO_PROJECT_LISTING_ENDPOINTS

        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum G: File >
        # Open Project must list only projects "authorized to open in the
        # currently established operating environment" - the rail's own
        # _nav_recent_projects call (below) is reused for the choice list
        # itself, never a second project query. Scope is: the OPEN
        # project's own environment when one is genuinely open
        # (request.view_args carries project_id on every workspace.*
        # route - looked up directly, a single bounded per-project read,
        # never searched for inside the capped recent list below, which
        # could omit an older project entirely and silently mis-scope
        # this); otherwise, an environment only if every one of this
        # user's own (up to `limit`) accessible projects shares the same
        # one - never a guess when they don't. Known, accepted edge case
        # for that second branch only: a user with 30+ projects in one
        # environment and at least one in a second could have that second
        # environment's projects excluded from the up-to-30 list this
        # reads, rather than doing a second full accessible-projects scan
        # just to rule that out exactly - same "bounded, not unbounded"
        # cost tradeoff this function's own docstring already makes for
        # the rail.
        menu_open_project_choices = []
        menu_open_project_environment = None
        if authenticated and not skip_project_listing:
            menu_open_project_choices = _nav_recent_projects(app, limit=30)
            open_project_id = request.view_args.get('project_id') if request.view_args else None
            if open_project_id:
                try:
                    open_workspace = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"]).get(open_project_id)
                except TypeError:
                    open_workspace = None
                menu_open_project_environment = open_workspace.operating_environment if open_workspace else None
            else:
                environments = {
                    p["operating_environment"] for p in menu_open_project_choices if p["operating_environment"]
                }
                if len(environments) == 1:
                    menu_open_project_environment = next(iter(environments))

        return {
            "current_year": datetime.now(timezone.utc).year,
            "static_version": app.config["STATIC_VERSION"],
            # CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01: every inline <script>
            # tag needs this exact request's nonce (set_csp_header, above,
            # puts the same value in the response's own CSP header) or
            # the browser silently refuses to run it -- see get_csp_nonce's
            # own docstring for the incident this fixes.
            "csp_nonce": get_csp_nonce(),
            "authenticated": authenticated,
            "is_admin": is_admin() and not on_standalone_auth_page,
            # CLAUDE-DEVELOPER-MODE-COCKPIT-01, Addendum E: the one place
            # this flag is ever read into template context - a plain
            # reviewer-session boolean (routes/portal.py's
            # toggle_developer_mode, admin_required-gated), never a
            # localStorage/client-only flag like UI Reference Mode below,
            # precisely because this one is authorization-sensitive: the
            # server, not the browser, is the source of truth for whether
            # it is on. `and is_admin()` here is defense-in-depth, not the
            # only gate (the toggle route itself is admin_required) - a
            # session that somehow carried a stale developer_mode=True
            # after a role change still can't display as developer_mode
            # in any template once is_admin() itself goes false. Same
            # standalone-auth-page guard as is_admin above - no menu bar
            # exists there for a badge to appear in anyway.
            "developer_mode": is_admin() and not on_standalone_auth_page and bool(session.get("developer_mode")),
            # CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: a persistent,
            # unmistakable indicator whenever the CURRENT session is the
            # dedicated ephemeral verification identity (services.
            # verification_access.is_verification_session - a fixed-
            # username check, never a client-settable flag), so this
            # session's own real product authority is never confusable
            # with a real admin's, on either operating environment.
            "verification_session": authenticated and is_verification_session(),
            # CLAUDE-CA1D-INSTRUMENT-RAIL-01: the one quiet global machine
            # fact proven this tranche -- reads the exact same
            # AI_CALLS_DISABLED env var services/bhive_parser.py's own
            # kill switch already reads (CLAUDE-P27-B), live per request,
            # never cached. Admin-gated in the template, not here (same
            # split every other is_admin-conditioned template block uses).
            "ai_calls_disabled": os.getenv("AI_CALLS_DISABLED", "false").strip().lower() == "true",
            # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum G:
            # was its own separate _nav_recent_projects(app) call (limit
            # 15) - now a slice of the SAME up-to-30 list already fetched
            # above for menu_open_project_choices, so this stays exactly
            # one project query per request, not two.
            "nav_recent_projects": menu_open_project_choices[:15],
            "menu_open_project_choices": menu_open_project_choices,
            "menu_open_project_environment": menu_open_project_environment,
            # CLAUDE-P40-E2B1, Section B: the single launcher panel's
            # identity/menu anchored at the bottom needs the reviewer's
            # own username - session["username"] already exists (set at
            # login, services/auth.py), just not previously exposed here.
            "current_username": session.get("username") if authenticated else None,
        }


def _register_template_filters(app: Flask) -> None:
    from services.formatting import humanize_timestamp, source_kind_label

    app.jinja_env.filters["humanize"] = humanize_timestamp
    app.jinja_env.filters["source_kind_label"] = source_kind_label

    @app.template_filter("hotlinks")
    def render_conversation_hotlinks(text, workspace, project_id, message_id=None, anchor_scope=None, anchor_case_id=None):
        """
        CLAUDE-P40-E, Section G: the template-facing half of
        services.case_workspace.resolve_conversation_hotlinks - that
        function only ever returns plain {"text", "source_id"} segments
        (it deliberately doesn't import Flask), so the actual safe
        `<a href="...">` markup (url_for + markupsafe escaping) is
        built here, where both are natural, ordinary template-layer
        concerns. Every plain-text segment is still escaped exactly
        like {{ message.text }} always was - only a real, resolved
        Source match ever becomes a link.

        CLAUDE-P40-VW8-QA, Section 11: `message_id`/`anchor_scope`/
        `anchor_case_id` are optional (backward-compatible - a caller
        that omits them gets exactly the pre-VW8-QA hotlinks-only
        behavior) and, when given, additionally wrap any tagged
        substring in a `<mark>` - "the selected text must receive an
        identifiable, accessible tagged treatment", the corrected
        behavior for CLAUDE-P40-VW7's own "Add Tag" action, which
        previously had no visible consequence on the source text at
        all. Composed in ONE pass against the raw text (never two
        independent substring-wrapping passes stacked on each other's
        already-escaped HTML output, which corrupts nesting) - hotlink
        segment boundaries and tag-occurrence boundaries are merged
        into one ordered boundary list first, then rendered outward-in
        (<mark> wraps <a>, never the reverse) so both remain valid,
        correctly-nested HTML regardless of how they overlap.
        """
        from flask import url_for
        from markupsafe import Markup, escape

        from services.case_workspace import resolve_conversation_hotlinks

        segments = resolve_conversation_hotlinks(text, workspace)

        tag_ranges = []
        if message_id and anchor_scope:
            from services.case_workspace import BUILT_IN_TAGS

            occurrences = [
                occ for occ in workspace.tag_occurrences
                if occ["source_anchor"].get("scope") == anchor_scope
                and occ["source_anchor"].get("message_id") == message_id
                and (anchor_scope != "case" or occ["source_anchor"].get("case_id") == anchor_case_id)
            ]
            occurrences.sort(key=lambda occ: occ["source_anchor"]["start_offset"])
            occupied_until = 0
            for occ in occurrences:
                start = occ["source_anchor"]["start_offset"]
                end = occ["source_anchor"]["end_offset"]
                # Overlap resolution (Section 11 - "duplicate application
                # must be handled coherently"): the earliest-starting
                # occurrence at a given position wins the inline
                # highlight; a later, overlapping one still persists,
                # still counts in Lists/Tags, just isn't ALSO drawn as a
                # second nested <mark> here (nested/overlapping <mark>
                # ranges would require re-splitting already-drawn spans,
                # not worth the complexity this stage's own scope calls
                # for - see this comment, not a silent gap).
                if start < occupied_until or start >= end or end > len(text):
                    continue
                tag = BUILT_IN_TAGS.get(occ["tag_id"])
                if tag is None:
                    tag = next((t for t in workspace.tags if t["id"] == occ["tag_id"]), None)
                if tag is None:
                    continue
                tag_ranges.append((start, end, tag["color"], tag["name"], occ["id"], occ["tag_id"]))
                occupied_until = end

        if not tag_ranges:
            rendered = []
            for segment in segments:
                if segment["source_id"]:
                    # CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01 pilot: carry the
                    # originating message's own id so the destination can
                    # offer a "Return to conversation" link - see
                    # governance/specified-unbuilt/navigation-context-
                    # operational-map.md ("Active pilot") and
                    # routes/workspace.py's own origin_message_id comment.
                    # A real pilot finding: the message id alone isn't
                    # enough for a CASE-scoped conversation - that thread
                    # only renders at all when ?case=<id> also selects it
                    # (show_workspace's own active_case resolution), so
                    # anchor_case_id (already an existing parameter here)
                    # must ALSO be carried, or the return link would point
                    # at a fragment that never renders on the destination
                    # page. Project-scoped messages need no such param -
                    # that thread renders unconditionally.
                    url = url_for(
                        "workspace.show_workspace", project_id=project_id, source=segment["source_id"],
                        origin_message_id=message_id,
                        case=(anchor_case_id if anchor_scope == "case" else None),
                    )
                    rendered.append(Markup('<a href="{}">{}</a>').format(url, segment["text"]))
                else:
                    rendered.append(escape(segment["text"]))
            return Markup("").join(rendered)

        # Merge hotlink-segment boundaries and tag-range boundaries into
        # one ordered set of cut points, then render each atomic
        # sub-span exactly once - this is what guarantees correct
        # nesting even when a tagged range only partially overlaps a
        # hotlinked filename (rare, but a naive two-pass wrap would
        # produce unbalanced tags in exactly that case).
        boundaries = {0, len(text)}
        cursor = 0
        segment_source_at = {}
        for segment in segments:
            seg_len = len(segment["text"])
            boundaries.add(cursor)
            boundaries.add(cursor + seg_len)
            segment_source_at[cursor] = segment["source_id"]
            cursor += seg_len
        for start, end, _color, _name, _occ_id, _tag_id in tag_ranges:
            boundaries.add(start)
            boundaries.add(end)
        cut_points = sorted(boundaries)

        def _source_id_at(pos):
            best = None
            for seg_start in sorted(segment_source_at):
                if seg_start > pos:
                    break
                best = segment_source_at[seg_start]
            return best

        def _tag_at(pos):
            for start, end, color, name, occ_id, tag_id in tag_ranges:
                if start <= pos < end:
                    return color, name, occ_id, tag_id
            return None

        rendered = []
        for i in range(len(cut_points) - 1):
            start, end = cut_points[i], cut_points[i + 1]
            if start >= end:
                continue
            chunk = escape(text[start:end])
            source_id = _source_id_at(start)
            if source_id:
                # CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01 pilot - see the
                # no-tag-ranges branch above for the full comment.
                url = url_for(
                    "workspace.show_workspace", project_id=project_id, source=source_id,
                    origin_message_id=message_id,
                    case=(anchor_case_id if anchor_scope == "case" else None),
                )
                chunk = Markup('<a href="{}">{}</a>').format(url, chunk)
            tag_here = _tag_at(start)
            if tag_here:
                color, name, occ_id, tag_id = tag_here
                chunk = Markup(
                    '<mark class="tag-highlight-inline conv-tag-color-{}" '
                    'data-tag-occurrence-id="{}" data-tag-id="{}" data-tag-name="{}" '
                    'data-ui-ref="chat.tag-highlight" '
                    'title="Tagged: {}">{}</mark>'
                ).format(color, occ_id, escape(tag_id), escape(name), name, chunk)
            rendered.append(chunk)
        return Markup("").join(rendered)


def _nav_recent_projects(app: Flask, limit: int = 15) -> list:
    """
    Read-only project list feeding the sidebar's "Projects" tree node -
    and, since CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01 Addendum G,
    the File > Open Project menu chooser too (same list, sliced two
    different ways by the context processor below - never a second
    query). Reuses the same RequirementsRegistry already used by
    routes/portal.py's project directory; no new storage or domain
    behavior. Runs on every authenticated page render (the rail is part
    of the shared shell) and is capped at `limit` projects - the context
    processor below calls this ONCE at a higher limit and slices the
    result two different ways in plain Python (rail: first 15; menu:
    all of it) rather than querying twice, so the added per-project
    CaseWorkspaceStore.get() below (needed for
    display_name - see pagescape correction #11: a project's visible
    identity should be its own display_title, not whichever filename
    happened to be
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
    from flask import session

    from services.auth import is_admin
    from services.case_workspace import CaseWorkspaceStore
    from services.governance import GovernanceLog
    from services.ingestion import get_registry
    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    try:
        registry = get_registry(app)
        documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    except OSError:
        return []
    documents.sort(key=lambda d: d.ingested_at, reverse=True)

    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])

    # CLAUDE-P32: this sidebar renders on every authenticated page
    # (including error pages, since it runs inside inject_globals) --
    # discovered as a real, unfiltered project-content leak during that
    # stage's own bypass inventory (a denied project's own name was
    # still visible in the nav rail on the very 404 page proving access
    # was denied). Filtered to accessible projects BEFORE the limit cap
    # below, not after -- capping first could under-fill the sidebar
    # with fewer than `limit` items even when more accessible projects
    # exist further down the list.
    governance_log = GovernanceLog(app.config["REGISTRY_STORE_PATH"])
    usernames = known_usernames()
    username = session.get("username")
    admin = is_admin()
    accessible_documents = []
    for d in documents:
        # A workspace file that predates the current schema must not
        # crash the sidebar on every authenticated page (the original,
        # pre-P32 defensive reasoning this function already had for its
        # own display-only re-fetch below, now needed here too since
        # this new code path also loads every project's workspace).
        # Fails CLOSED on a load error -- excluded from the nav rather
        # than shown, the same "can't determine access -> deny" default
        # can_access_project itself uses for a None workspace.
        try:
            workspace = store.get_or_create(d.project_id)
            ensure_owner_backfilled(store, workspace, governance_log, usernames)
            allowed = can_access_project(workspace, username, admin) and not workspace.removed_at
        except TypeError:
            allowed = False
        if allowed:
            accessible_documents.append(d)
        if len(accessible_documents) >= limit:
            break

    result = []
    for d in accessible_documents:
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
        result.append({
            "project_id": d.project_id,
            "filename": d.filename,
            "display_name": display_name,
            # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum G:
            # additive field - nothing before this stage read it. Lets
            # the File > Open Project menu chooser (built from this SAME
            # already-access-scoped list, never a second query) scope
            # itself to the caller's current operating environment
            # without a second per-project workspace load.
            "operating_environment": workspace.operating_environment if workspace else None,
        })
    return result


def _interactive_debugger_enabled() -> bool:
    """
    CLAUDE-P40-C: whether Werkzeug's interactive debugger/console may be
    enabled for the local `python app.py` entrypoint below. Extracted
    into its own function (rather than inlined in the `__main__` block)
    specifically so this decision can be exercised directly by a test
    against constructed environment state, not just read as source.
    Requires BOTH a narrowly-named, exact-match opt-in
    (ARCHIOSK_ENABLE_DEBUGGER == "1", never a loose truthy parse of an
    arbitrary variable) AND an explicit development environment
    (FLASK_ENV == "development") - neither alone is sufficient, so a
    single generic setting (e.g. some other tool setting DEBUG=1, or a
    deployment accidentally leaving FLASK_ENV=development set) can never
    activate it by itself.
    """
    return (
        os.getenv("ARCHIOSK_ENABLE_DEBUGGER") == "1"
        and os.getenv("FLASK_ENV", "production") == "development"
    )


# Local dev entrypoint: `python app.py`
#
# CLAUDE-P40-C: this used to pass debug=True unconditionally to
# Werkzeug's dev server - not merely a log-verbosity setting. debug=True
# activates Werkzeug's INTERACTIVE DEBUGGER: any unhandled exception (a
# legacy-record KeyError, or anything else) rendered a raw traceback
# page with a clickable console icon opening an unauthenticated-except-
# for-a-PIN Python REPL with full process access - reachable by anyone
# who could reach the port, and confirmed to have been the actual path
# a real incident followed (see this stage's own final report). A
# literal debug=True passed here OVERRIDES app.config['DEBUG'] entirely
# (Flask's run() sets self.debug from this argument before deriving
# use_reloader/use_debugger from it), so config.py's otherwise-correct
# environment-based DEBUG defaults never had any effect on this
# specific code path regardless of FLASK_ENV or .env.
#
# The reloader (auto-restart on file change, and the specific orphaned-
# parent/child-chain behavior the restart-app skill exists to handle)
# is a genuinely used dev convenience, independent of the interactive
# debugger - kept on unconditionally. The interactive debugger/console
# itself is OFF by default and requires BOTH a narrowly-named, exact-
# match opt-in (never a loose truthy parse of some generic variable)
# AND an explicit development environment - never activated by a
# single generic setting, and never reachable at all outside this
# `__main__` block (wsgi.py, Gunicorn's real entrypoint, never calls
# .run() and never executes this branch). host stays loopback-only
# (127.0.0.1) unconditionally either way.
if __name__ == "__main__":
    application = create_app()
    _enable_debugger = _interactive_debugger_enabled()
    application.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=True,
        use_debugger=_enable_debugger,
        use_evalex=_enable_debugger,
    )
