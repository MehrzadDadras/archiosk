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

from config import get_config


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object(get_config(config_name))

    _configure_logging(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)

    return app


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _register_blueprints(app: Flask) -> None:
    from routes.portal import portal_bp
    from routes.api import api_bp

    app.register_blueprint(portal_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify, render_template

    @app.errorhandler(404)
    def not_found(_err):
        if _wants_json():
            return jsonify(error="not_found", message="Resource not found."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(err):
        app.logger.exception("Unhandled server error: %s", err)
        if _wants_json():
            return jsonify(error="server_error", message="Something went wrong."), 500
        return render_template("errors/500.html"), 500

    def _wants_json() -> bool:
        from flask import request
        return request.path.startswith("/api/")


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        from datetime import datetime, timezone
        return {
            "current_year": datetime.now(timezone.utc).year,
            "static_version": app.config["STATIC_VERSION"],
        }


# Local dev entrypoint: `python app.py`
if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
