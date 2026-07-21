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
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'bhive.db'}")
    REGISTRY_STORE_PATH = os.getenv("REGISTRY_STORE_PATH", str(BASE_DIR / "instance" / "registry"))

    # -- Upload / parsing limits ------------------------------------------
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv"}

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


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("FLASK_ENV", "production")
    return _CONFIGS.get(name, ProductionConfig)
