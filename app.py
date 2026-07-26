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
    _register_database(app)
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
        # app's single small table; revisit with real migration tooling
        # if the schema ever needs a change that create_all() can't do.
        db.create_all()


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

    @app.errorhandler(403)
    def forbidden(_err):
        if _wants_json():
            return jsonify(error="forbidden", message="You do not have permission to access this resource."), 403
        return render_template("errors/403.html"), 403

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
if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
