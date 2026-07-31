"""Production WSGI entrypoint. Gunicorn points at `wsgi:app`."""
from app import create_app
from config import BaseConfig

# CLAUDE-P40-C: was create_app() (config resolved from FLASK_ENV, "production"
# only as a fallback when that var is absent entirely). This file's own
# existence and purpose already say "this is the production entrypoint"
# unambiguously - it should never depend on an environment variable to
# find that out. Without this, a production .env accidentally carrying
# FLASK_ENV=development (e.g. copied from a local dev template) would
# silently run this process with DevelopmentConfig (DEBUG=True) - not
# enough to expose Werkzeug's interactive debugger on its own (Gunicorn's
# sync worker never calls werkzeug.serving.run_simple()/DebuggedApplication
# at all, so that specific exposure path is structurally impossible here
# regardless of this config value), but it could still degrade Flask's
# own exception routing away from the registered, safe @app.errorhandler
# (500) page. Hard-coded here removes the ambiguity entirely rather than
# documenting it as an operator caveat.
app = create_app("production")

missing = BaseConfig.validate()
if missing:
    app.logger.warning(
        "Missing required environment variables: %s. "
        "The app will start but dependent features will fail at runtime.",
        ", ".join(missing),
    )
