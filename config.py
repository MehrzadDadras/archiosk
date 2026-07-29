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

    # -- Upload / parsing limits ------------------------------------------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"}

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
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").strip().lower() != "false"

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
    SESSION_COOKIE_SECURE = False
    # Hermetic tests must never attempt a real SMTP connection based on
    # whatever the developer's local .env happens to have configured -
    # same reasoning as app.py's ANTHROPIC_API_KEY clearing for "testing".
    SMTP_HOST = ""
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
