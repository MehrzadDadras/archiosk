"""Production WSGI entrypoint. Gunicorn points at `wsgi:app`."""
from app import create_app
from config import BaseConfig

app = create_app()

missing = BaseConfig.validate()
if missing:
    app.logger.warning(
        "Missing required environment variables: %s. "
        "The app will start but dependent features will fail at runtime.",
        ", ".join(missing),
    )
