"""
Central configuration, sourced entirely from environment variables.
Never hardcode secrets here — this file is committed to version control.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Explicit path so this loads regardless of the process's cwd (e.g. when
# Flask/Gunicorn is launched from outside the project root). Never
# overrides real env vars already set — systemd's EnvironmentFile in
# deploy/gunicorn.service takes precedence over this in production.
load_dotenv(BASE_DIR / ".env")


class BaseConfig:
    """Shared defaults. Subclasses override per-environment behavior."""

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
    DEBUG = False
    TESTING = False

    # -- Third-party / model access -----------------------------------
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # -- Storage ---------------------------------------------------------
    # `or` (not getenv's own default arg) so a blank .env value -- e.g.
    # "DATABASE_URL=" -- falls through too, not just a fully unset var:
    # os.getenv only applies its default when the key is absent entirely,
    # and returns "" as-is when the key is present but empty.
    DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'instance' / 'bhive.db'}"
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REGISTRY_STORE_PATH = os.getenv("REGISTRY_STORE_PATH") or str(BASE_DIR / "instance" / "registry")

    # CLAUDE-RBAC-TOKENS-01. Drawing sheets live HERE, under instance/, and
    # never under static/. That is the whole protection: Flask serves static/
    # with no authorization at all (measured - /static/nipigon/A204.svg
    # answered 200 unauthenticated), so a role check on a route beside a
    # world-readable tree stops nobody. Bytes are reachable only through
    # routes/project_assets.py, which authorizes first.
    PROJECT_ASSET_PATH = os.getenv("PROJECT_ASSET_PATH") or str(BASE_DIR / "instance" / "project_assets")

    # CLAUDE-RBAC-TOKENS-03. The bidding marketplace is SCAFFOLD ONLY and this
    # flag is the switch. It is False, and while it is False the component's
    # markup is NEVER RENDERED - not rendered-and-hidden.
    #
    # That distinction is the whole point. `display: none; visibility: hidden`
    # leaves the element in the DOM: it is readable in devtools, it ships to
    # every visitor, one overriding stylesheet or one `hidden` attribute
    # removed brings it back, and any route behind it stays live regardless of
    # what CSS says. A server-side gate means there is nothing on the page to
    # reveal. The CSS in main.css is defence in depth behind this, never the
    # mechanism.
    #
    # Deliberately not read from the environment: a marketplace must not be
    # switchable by a stray env var on a host somebody forgot about. Turning it
    # on is a code change, reviewed, with its own authorization.
    ENABLE_BIDDING_PORTAL = False

    # CLAUDE-TRIAL-SAFE-LANDING-01. How many model-backed queries a trial
    # project gets before the safe landing. Only OUTBOUND LLM calls are
    # metered - reading drawings, zooming, panning and navigating are never
    # counted and never blocked, which is the entire promise of the message.
    TRIAL_QUERY_ALLOWANCE = int(os.getenv("TRIAL_QUERY_ALLOWANCE", "50"))

    # Where the "contact admin" link points. A real default rather than an
    # empty string: an unconfigured address here would render a mailto: to
    # nowhere, which reads as a dead end at precisely the moment the product
    # is promising help.
    ADMIN_CONTACT_EMAIL = os.getenv("ADMIN_CONTACT_EMAIL", "admin@archiosk.com")

    # -- Upload / parsing limits ------------------------------------------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    # CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01: .xlsx added here - a real,
    # already-hardened extraction/security pipeline for it already existed
    # (services/spreadsheet_intelligence.py, CLAUDE-MM3) and was already
    # reachable for adding a spreadsheet to an EXISTING project, but this
    # specific list (new-project/folder-upload/Data-Room-Reconcile
    # eligibility, services/ingestion.py) was never revisited to include
    # it - a legacy scope gap, not a security boundary or parser
    # limitation. See services/ingestion.py's own extension branch for
    # where .xlsx is routed to that pipeline instead of BHiveParser.
    ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md", ".xlsx"}

    # -- Static asset cache-busting ----------------------------------------
    # Appended as a ?v= query string on static asset URLs (see base.html).
    # deploy/nginx.conf serves /static/ with a 30-day immutable cache, which
    # is only safe because changing this value changes the requested URL —
    # bump it any time main.css or dashboard.js changes, or browsers that
    # already cached the old file won't see the update for up to 30 days.
    # NOTE: the "19" default below is dead in practice once .env sets a
    # real STATIC_VERSION - python-dotenv never overrides an already-set
    # env var. .env is the actual source of truth; bump it there.
    STATIC_VERSION = os.getenv("STATIC_VERSION", "19")

    # -- Password reset email (optional; see services/email.py) ------------
    # "Configured" means SMTP_HOST is non-blank (services/password_reset.py's
    # only gate) -- blank is a valid, supported state (no SMTP server
    # available), not a misconfiguration, and degrades to the dev-only
    # fallback rather than erroring.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USERNAME
    # STARTTLS (typically port 587): connect in plaintext, then upgrade.
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"
    # Implicit TLS (typically port 465): the whole connection is
    # encrypted from the first byte (smtplib.SMTP_SSL) -- a different,
    # mutually exclusive transport from STARTTLS above, not an
    # additional layer on top of it. Off by default so existing STARTTLS
    # setups (SMTP_USE_TLS's own default) are completely unaffected.
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").strip().lower() == "true"

    # -- Trial access request notification (optional) ----------------------
    # CLAUDE-CA1D-TRIAL-ACCESS-HOTFIX-01: where a public /start-trial
    # request gets emailed via the same SMTP transport above. Blank is a
    # valid, supported state (services/trial_request.py degrades to
    # logging only) -- never a hard dependency, matching SMTP_HOST's own
    # "optional, best-effort" shape immediately above. Must be set in
    # production for a human to actually receive these requests by email;
    # every request is also always logged regardless, as a second,
    # zero-configuration trace.
    TRIAL_REQUEST_NOTIFY_EMAIL = os.getenv("TRIAL_REQUEST_NOTIFY_EMAIL", "")

    # CLAUDE-DIAGNOSTIC-BRIDGE-01: where a finished diagnostic investigation is
    # sent. Same "blank means skip, never error" contract as SMTP_HOST and
    # TRIAL_REQUEST_NOTIFY_EMAIL above - an unconfigured address makes the send
    # a truthful refusal, never a failed request. Deliberately its own variable
    # rather than reusing the trial address: these are different audiences and
    # one of them should not silently start receiving the other's mail.
    DIAGNOSTIC_NOTIFY_EMAIL = os.getenv("DIAGNOSTIC_NOTIFY_EMAIL", "")

    # HTTPOnly/SameSite are safe in every environment; Secure requires HTTPS,
    # which only nginx terminates in production — off in dev so the login
    # cookie still works over plain http://127.0.0.1.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate(cls) -> list[str]:
        """Return a list of missing required env vars. Call at startup."""
        missing = []
        if not cls.SECRET_KEY:
            missing.append("FLASK_SECRET_KEY")
        if not cls.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
        return missing


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # Local dev serves plain http://127.0.0.1 -- a Secure cookie would
    # never actually be sent back by the browser, breaking login entirely.
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # CLAUDE-ATTRIBUTION-01: tests get their own registry.
    #
    # This was inherited from BaseConfig, so every test that built a real
    # workspace wrote it into instance/registry - the DEV data. It is not a
    # tidiness point: it silently contaminated a real measurement. 99 of 100
    # "unattributed human conversation turns" in the dev registry turned out to
    # be one fixture string from tests/test_mobile_continuation_01.py, which
    # produced a reported 46% attribution-decay rate where the true figure was
    # 0.8%.
    #
    # Set unconditionally rather than via os.getenv, for the same hermeticity
    # reasoning as SMTP_HOST and TRIAL_REQUEST_NOTIFY_EMAIL below: a test must
    # never touch real state because of whatever a developer's .env happens to
    # say. A fixed path rather than a per-process temp dir so the artifacts stay
    # inspectable after a failure.
    REGISTRY_STORE_PATH = str(BASE_DIR / "instance" / "test_registry")
    PROJECT_ASSET_PATH = str(BASE_DIR / "instance" / "test_project_assets")
    SESSION_COOKIE_SECURE = False
    # Hermetic tests must never attempt a real SMTP connection based on
    # whatever the developer's local .env happens to have configured -
    # same reasoning as app.py's ANTHROPIC_API_KEY clearing for "testing".
    SMTP_HOST = ""
    # Same hermeticity reasoning as SMTP_HOST directly above -- a test
    # must never attempt a real send based on a developer's local .env.
    TRIAL_REQUEST_NOTIFY_EMAIL = ""
    DIAGNOSTIC_NOTIFY_EMAIL = ""
    # CLAUDE-P27-B: Flask-Limiter's default in-memory storage is a single
    # process-wide singleton (services/rate_limit.py) -- without this,
    # every test method's real HTTP requests against /login,
    # /forgot-password, etc. across the whole suite would accumulate
    # toward one shared limit and start producing spurious 429s. Tests
    # that specifically want to exercise rate limiting turn this back on
    # and call limiter.reset() first (see tests/test_rate_limiting.py).
    RATELIMIT_ENABLED = False
    # CLAUDE-P27-B: real HTTP POSTs across hundreds of existing tests
    # never carry a csrf_token field -- CSRFProtect (app.py) would 400
    # every one of them otherwise. Tests that specifically want to
    # exercise CSRF enforcement turn this back on (see
    # tests/test_csrf_protection.py), same pattern as RATELIMIT_ENABLED
    # just above.
    WTF_CSRF_ENABLED = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("FLASK_ENV", "production")
    return _CONFIGS.get(name, ProductionConfig)
