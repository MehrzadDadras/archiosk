"""
CLAUDE-P40-C - Legacy Record Compatibility, P40-B Regression Audit,
Safe Failure Containment, and Debugger Elimination.

A real incident: opening a project whose Cases predate Case-level
visibility (commit 04fc14a) crashed with KeyError: 'visibility', and
because `python app.py` unconditionally passed debug=True to Werkzeug,
the resulting traceback page exposed the interactive debugger and a
PIN prompt - a real failure-containment/security defect, confirmed
independent of CLAUDE-P40-B (reproduced identically, via an isolated
worktree, at both the P40-B baseline 4f97a6b and final 448fe2d).

Three layers:
  - LegacyCaseVisibilityHydrationTests: the compatibility fix itself
    (CaseWorkspaceStore._hydrate_legacy_cases), using a fixture that
    reproduces the missing-field shape without copying any real
    project content.
  - AccessInvariantTests: project authorization is unaffected by the
    hydration - deny-by-default, owner/allow-list/admin unchanged.
  - SafeFailureContainmentTests / DebuggerConfigurationTests: an
    unhandled exception never reaches the browser as a Werkzeug
    traceback/console/PIN, in a production-like configuration, for
    both HTML and JSON routes; the interactive debugger cannot be
    enabled without an explicit, narrow, two-part opt-in.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CASE_VISIBILITY_COLLABORATIVE, CASE_VISIBILITY_PRIVATE, CASE_VISIBILITY_SHARED, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry

_LEGACY_PROJECT_ID = "legacy-fixture-project"


def _write_legacy_fixture(tmp_dir: Path, owner: str = "legacyowner") -> None:
    """
    A minimal, synthetic fixture reproducing the missing-field shape
    that crashed - NOT a copy of any real project's content. Two
    Cases: one with no "visibility" or "created_by" key at all (the
    exact pre-04fc14a shape), one with a normal current-schema shape,
    to prove the fix only ever ADDS the missing key and never disturbs
    an already-complete record.
    """
    RequirementsRegistry(tmp_dir).save(ParsedDocument(
        project_id=_LEGACY_PROJECT_ID, filename="legacy_probe.txt", ingested_at="2020-01-01T00:00:00+00:00",
        requirements=[RequirementItem(id="r1", text="Legacy requirement text.", category="other", confidence=0.5, source_line=1)],
    ))
    import json
    workspace_path = tmp_dir / f"{_LEGACY_PROJECT_ID}.workspace.json"
    workspace_data = {
        "project_id": _LEGACY_PROJECT_ID,
        "owner": owner,
        "access_allow_list": [],
        "cases": [
            {
                "id": "legacy-case-no-visibility",
                "project_id": _LEGACY_PROJECT_ID,
                "title": "Legacy Investigation",
                "objective": "",
                "created_at": "2020-01-01T00:00:00+00:00",
                "status": "open",
                "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [], "activity_ids": [],
                "conversation": [],
                # deliberately no "visibility", no "created_by" key at all
            },
            {
                "id": "current-case-with-visibility",
                "project_id": _LEGACY_PROJECT_ID,
                "title": "Current-Schema Investigation",
                "objective": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "status": "open",
                "visibility": CASE_VISIBILITY_COLLABORATIVE,
                "created_by": owner,
                "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [], "activity_ids": [],
                "conversation": [],
            },
        ],
        "version": 1,
    }
    workspace_path.write_text(json.dumps(workspace_data), encoding="utf-8")


class LegacyCaseVisibilityHydrationTests(unittest.TestCase):
    """The compatibility fix: CaseWorkspaceStore._hydrate_legacy_cases,
    exercised through the real .get() load path."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40c_"))
        _write_legacy_fixture(self.tmp_dir)
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_legacy_case_without_visibility_hydrates_without_crashing(self):
        workspace = self.store.get(_LEGACY_PROJECT_ID)
        legacy_case = next(c for c in workspace.cases if c["id"] == "legacy-case-no-visibility")
        self.assertEqual(legacy_case["visibility"], CASE_VISIBILITY_SHARED)

    def test_hydration_never_downgrades_a_visibility_that_already_exists(self):
        workspace = self.store.get(_LEGACY_PROJECT_ID)
        current_case = next(c for c in workspace.cases if c["id"] == "current-case-with-visibility")
        self.assertEqual(current_case["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_get_alone_never_writes_back_to_the_persisted_file(self):
        # A read-only .get() call, on its own, never mutates the file on
        # disk - _hydrate_legacy_cases never calls save(). This is
        # distinct from (and does not contradict) the fact that an
        # ordinary, pre-existing, unrelated write elsewhere in the app
        # (routes/workspace.py's show_workspace recording
        # last_viewed_by on every Project Home view - already true
        # before this stage) may later persist the hydrated value as a
        # byproduct of doing its own job; see _hydrate_legacy_cases'
        # own docstring.
        raw_before = (self.tmp_dir / f"{_LEGACY_PROJECT_ID}.workspace.json").read_text(encoding="utf-8")
        self.store.get(_LEGACY_PROJECT_ID)  # triggers hydration in memory
        raw_after = (self.tmp_dir / f"{_LEGACY_PROJECT_ID}.workspace.json").read_text(encoding="utf-8")
        self.assertEqual(raw_before, raw_after)
        self.assertNotIn("visibility", raw_after.split('"legacy-case-no-visibility"')[1].split("}")[0])

    def test_visible_cases_for_no_longer_raises_keyerror(self):
        workspace = self.store.get(_LEGACY_PROJECT_ID)
        try:
            result = self.store.visible_cases_for(workspace, "legacyowner")
        except KeyError:
            self.fail("visible_cases_for raised KeyError on a legacy Case missing visibility")
        self.assertEqual(len(result), 2)

    def test_record_ids_and_relationships_are_preserved(self):
        workspace = self.store.get(_LEGACY_PROJECT_ID)
        self.assertEqual(workspace.project_id, _LEGACY_PROJECT_ID)
        self.assertEqual(workspace.owner, "legacyowner")
        case_ids = {c["id"] for c in workspace.cases}
        self.assertEqual(case_ids, {"legacy-case-no-visibility", "current-case-with-visibility"})

    def test_legacy_record_survives_a_fresh_store_load_after_restart(self):
        # Simulates "after an application restart" - a brand new
        # CaseWorkspaceStore instance loading fresh from disk.
        fresh_store = CaseWorkspaceStore(self.tmp_dir)
        workspace = fresh_store.get(_LEGACY_PROJECT_ID)
        legacy_case = next(c for c in workspace.cases if c["id"] == "legacy-case-no-visibility")
        self.assertEqual(legacy_case["visibility"], CASE_VISIBILITY_SHARED)

    def test_repeated_reads_are_idempotent(self):
        first = self.store.get(_LEGACY_PROJECT_ID)
        second = self.store.get(_LEGACY_PROJECT_ID)
        self.assertEqual(
            [c["visibility"] for c in first.cases],
            [c["visibility"] for c in second.cases],
        )


class AccessInvariantTests(unittest.TestCase):
    """3.1/P40-C requirement: the hydration fix must never grant,
    widen, or substitute for project-level access authorization."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40c_access_"))
        _write_legacy_fixture(self.tmp_dir, owner="legacyowner")
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="legacyowner", password_hash=generate_password_hash("x"), role="admin"))
            # CLAUDE-P40-C: role="read_only", NOT "admin" - services.
            # project_access.can_access_project's own admin bypass
            # (`if is_admin: return True`, unconditional) means an admin
            # is never actually "unauthorized" for any project by design
            # - a real, governed, deliberate behavior this stage must
            # preserve, not accidentally test against. A genuinely
            # unauthorized user is a non-owner, non-allow-listed,
            # non-admin account.
            db.session.add(User(username="unauthorized_user", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def test_unauthenticated_request_is_rejected(self):
        client = self.flask_app.test_client()
        resp = client.get(f"/projects/{_LEGACY_PROJECT_ID}/workspace", follow_redirects=False)
        self.assertIn(resp.status_code, (302, 401, 403))
        if resp.status_code == 302:
            self.assertIn("/login", resp.headers["Location"])

    def test_owner_can_open_the_legacy_project_workspace(self):
        client = self._client_as("legacyowner", 1)
        resp = client.get(f"/projects/{_LEGACY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("KeyError", resp.get_data(as_text=True))

    def test_unauthorized_authenticated_user_is_denied_by_direct_url(self):
        client = self._client_as("unauthorized_user", 2, role="read_only")
        resp = client.get(f"/projects/{_LEGACY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 404)

    def test_hydration_does_not_add_the_project_to_an_unauthorized_users_nav(self):
        client = self._client_as("unauthorized_user", 2, role="read_only")
        resp = client.get("/gateway")
        body = resp.get_data(as_text=True)
        self.assertNotIn("legacy_probe.txt", body)
        self.assertNotIn(_LEGACY_PROJECT_ID, body)


class SafeFailureContainmentTests(unittest.TestCase):
    """An unhandled exception, in a production-like configuration
    (DEBUG=False, TESTING=False - NOT the hermetic unit-test config,
    which itself sets TESTING=True and could mask this), must never
    reach the client as a Werkzeug traceback/console/PIN prompt."""

    def setUp(self):
        # Unique per test (not just a unique DB file) - Flask-SQLAlchemy's
        # db object is a process-wide singleton, and re-pointing
        # DATABASE_URL at a fresh file per test does not reliably force a
        # fresh engine/connection for it within the same test process.
        self._username = f"produser_{self.id().rsplit('.', 1)[-1]}"
        self.tmp_db_dir = tempfile.mkdtemp(prefix="beehive_test_p40c_prod_db_")
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(self.tmp_db_dir) / 'prodlike.db'}"
        import app as app_module
        self.flask_app = app_module.create_app("production")
        self.tmp_registry = Path(tempfile.mkdtemp(prefix="beehive_test_p40c_prod_registry_"))
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_registry)
        _write_legacy_fixture(self.tmp_registry, owner=self._username)

        with self.flask_app.app_context():
            from models import User, db
            db.create_all()
            if not User.query.filter_by(username=self._username).first():
                db.session.add(User(username=self._username, password_hash=generate_password_hash("x"), role="admin"))
                db.session.commit()

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = self._username
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_db_dir, ignore_errors=True)
        shutil.rmtree(self.tmp_registry, ignore_errors=True)
        os.environ.pop("DATABASE_URL", None)

    def _assert_no_debugger_artifacts(self, body: str):
        for marker in (
            "Werkzeug Debugger", "Traceback (most recent call last)", "__debugger__=yes",
            "interactive-console", "Console Locked", "debugger PIN", "PIN:",
            str(Path(__file__).resolve().parent.parent),  # repo root path
        ):
            self.assertNotIn(marker, body, f"response leaked debugger/traceback artifact: {marker!r}")

    def test_production_config_has_debug_and_testing_off(self):
        self.assertFalse(self.flask_app.config["DEBUG"])
        self.assertFalse(self.flask_app.config["TESTING"])

    def test_html_route_unhandled_exception_shows_the_safe_error_page(self):
        with patch.object(CaseWorkspaceStore, "visible_cases_for", side_effect=RuntimeError("induced test failure")):
            resp = self.client.get(f"/projects/{_LEGACY_PROJECT_ID}/workspace")
        self.assertEqual(resp.status_code, 500)
        body = resp.get_data(as_text=True)
        self.assertIn("Something went wrong", body)
        self._assert_no_debugger_artifacts(body)
        self.assertNotIn("induced test failure", body)

    def test_api_route_unhandled_exception_returns_json_not_html(self):
        with patch("routes.api.get_registry", side_effect=RuntimeError("induced api failure")):
            resp = self.client.get("/api/v1/documents")
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.content_type, "application/json")
        body = resp.get_data(as_text=True)
        self.assertNotIn("<html", body)
        self._assert_no_debugger_artifacts(body)
        self.assertNotIn("induced api failure", body)

    def test_intentional_404_is_unaffected(self):
        resp = self.client.get("/projects/does-not-exist-at-all/workspace")
        self.assertEqual(resp.status_code, 404)
        self._assert_no_debugger_artifacts(resp.get_data(as_text=True))


class DebuggerConfigurationTests(unittest.TestCase):
    """Exercises the actual decision function against constructed
    environment state - not a string search against source."""

    def setUp(self):
        self._saved_env = {
            k: os.environ.get(k) for k in ("ARCHIOSK_ENABLE_DEBUGGER", "FLASK_ENV", "FLASK_DEBUG")
        }

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_startup_has_debugger_off(self):
        os.environ.pop("ARCHIOSK_ENABLE_DEBUGGER", None)
        os.environ.pop("FLASK_ENV", None)
        import app as app_module
        self.assertFalse(app_module._interactive_debugger_enabled())

    def test_production_like_startup_has_debugger_off_even_with_an_unrelated_dev_variable_present(self):
        os.environ.pop("ARCHIOSK_ENABLE_DEBUGGER", None)
        os.environ["FLASK_ENV"] = "production"
        os.environ["SOME_OTHER_DEBUG_FLAG"] = "true"  # unrelated, must not activate anything
        import app as app_module
        self.assertFalse(app_module._interactive_debugger_enabled())
        os.environ.pop("SOME_OTHER_DEBUG_FLAG", None)

    def test_opt_in_alone_without_development_env_is_not_enough(self):
        os.environ["ARCHIOSK_ENABLE_DEBUGGER"] = "1"
        os.environ["FLASK_ENV"] = "production"
        import app as app_module
        self.assertFalse(app_module._interactive_debugger_enabled())

    def test_development_env_alone_without_the_opt_in_is_not_enough(self):
        os.environ.pop("ARCHIOSK_ENABLE_DEBUGGER", None)
        os.environ["FLASK_ENV"] = "development"
        import app as app_module
        self.assertFalse(app_module._interactive_debugger_enabled())

    def test_loose_truthy_values_do_not_count_as_the_opt_in(self):
        import app as app_module
        os.environ["FLASK_ENV"] = "development"
        for loose_value in ("true", "True", "yes", "on", "1 "):
            os.environ["ARCHIOSK_ENABLE_DEBUGGER"] = loose_value
            self.assertFalse(
                app_module._interactive_debugger_enabled(),
                f"loose value {loose_value!r} must not enable the debugger",
            )

    def test_legacy_flask_debug_env_var_alone_is_not_enough(self):
        # CLAUDE-P40-D: _interactive_debugger_enabled() never reads
        # FLASK_DEBUG at all (only ARCHIOSK_ENABLE_DEBUGGER + FLASK_ENV
        # gate it) - a stray legacy FLASK_DEBUG=1 (e.g. copied from a
        # generic Flask tutorial/template) must not enable the debugger
        # on its own, without both authorized conditions also present.
        os.environ.pop("ARCHIOSK_ENABLE_DEBUGGER", None)
        os.environ["FLASK_ENV"] = "production"
        os.environ["FLASK_DEBUG"] = "1"
        import app as app_module
        self.assertFalse(app_module._interactive_debugger_enabled())
        os.environ.pop("FLASK_DEBUG", None)

    def test_both_explicit_conditions_together_enable_it(self):
        os.environ["ARCHIOSK_ENABLE_DEBUGGER"] = "1"
        os.environ["FLASK_ENV"] = "development"
        import app as app_module
        self.assertTrue(app_module._interactive_debugger_enabled())

    def test_production_config_class_has_debug_off(self):
        from config import ProductionConfig
        self.assertFalse(ProductionConfig.DEBUG)

    def test_wsgi_entrypoint_never_calls_run_or_touches_debug(self):
        # wsgi.py (Gunicorn's real entrypoint) must never execute the
        # debug-enabling code path at all - confirmed by inspecting
        # what it actually does when imported, not by string search.
        import importlib
        import wsgi as wsgi_module
        importlib.reload(wsgi_module)
        self.assertTrue(hasattr(wsgi_module, "app"))
        self.assertFalse(wsgi_module.app.config["DEBUG"])


if __name__ == "__main__":
    unittest.main()
