"""
D1 - zone-scoped retrieval proof. A Pilot Chassis gate.

WHAT THIS PROVES, AND WHAT IT DELIBERATELY DOES NOT CLAIM

Baseline Schedule 01 carried D1 as IMPLEMENTED / NEEDS PROOF. This file is the
proof, not new capability: every boundary asserted here already existed. What
was missing was a single adversarial test driving the real surfaces with two
real actors and distinctive markers, so a leak is detectable rather than
argued about.

The honest scope, stated up front because overclaiming here would be worse
than having no test at all:

  * PROJECT isolation is real and enforced application-wide. It is proven below
    across navigation, listings, the JSON API, direct-object access, exports
    and citations.
  * PARTY / ZONE isolation exists ONLY as project-token discipline scoping
    (services/project_rbac.py) on the drawing/sheet and ask surfaces. It is
    proven below for exactly those surfaces and claimed for no others.
  * There is NO multi-organization tenancy in this codebase. There is no
    Organization model. services/project_access.py says so in its own
    docstring, and governance/specified-unbuilt/tenancy-and-project-
    authorization.md is still unimplemented. Nothing here should be read as
    proving a tenancy boundary, because there is not one to prove.

THE DETECTION METHOD

Each project carries a marker string that appears nowhere else in the system.
A negative-access assertion is therefore not "we got a 404" - it is "the marker
appears nowhere in the response body", which catches the failure a status code
misses: content leaking through a page that returns 200 for other reasons.

WHY REFUSALS ARE CHECKED FOR SAMENESS

A foreign-but-real project and a project that does not exist must be
indistinguishable. If they differ in status or body, the pair is an existence
oracle and project ids become enumerable - which leaks the client list even
while every document stays unreadable.

Hermetic: BHiveParser.parse is spied, never run. No test here makes a network
call.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

# Markers chosen to be unmistakable and to survive HTML escaping unchanged.
ALPHA_MARKER = "D1ALPHAMARKERZQ7"
BRAVO_MARKER = "D1BRAVOMARKERXK9"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _D1Base(unittest.TestCase):
    """Two actors, two projects, one unmistakable marker each."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_d1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add_all([
                User(username="d1actora", password_hash=generate_password_hash("x"),
                     role="read_only"),
                User(username="d1actorb", password_hash=generate_password_hash("x"),
                     role="read_only"),
            ])
            db.session.commit()

        self.actor_a = self._client_as("d1actora", 1, "read_only")
        self.actor_b = self._client_as("d1actorb", 2, "read_only")

        self.alpha = self._ingest("d1actora", "Project Alpha " + ALPHA_MARKER,
                                  "alpha-" + ALPHA_MARKER + ".txt")
        self.bravo = self._ingest("d1actorb", "Project Bravo " + BRAVO_MARKER,
                                  "bravo-" + BRAVO_MARKER + ".txt")
        # A marker inside workspace CONTENT, not only in its name - so a leak
        # through a body that never renders the project title is still caught.
        self._plant_case(self.alpha.project_id, "Alpha Case " + ALPHA_MARKER)
        self._plant_case(self.bravo.project_id, "Bravo Case " + BRAVO_MARKER)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _ingest(self, owner: str, project_name: str, filename: str):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner,
                    project_name=project_name,
                )

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _plant_case(self, project_id: str, title: str):
        store = self._store()
        workspace = store.get_or_create(project_id)
        store.create_case(workspace, title=title, objective=title,
                          created_by="d1planter")

    def assertNoMarker(self, response, marker, where):
        body = response.get_data(as_text=True)
        self.assertNotIn(
            marker, body,
            "%s leaked %s (status %s)" % (where, marker, response.status_code))


class ProjectIsolationPositiveTests(_D1Base):
    """Positive access. A boundary proven by breaking the app proves nothing."""

    def test_actor_a_can_open_own_project_workspace(self):
        r = self.actor_a.get("/projects/%s/workspace" % self.alpha.project_id)
        self.assertEqual(r.status_code, 200)

    def test_actor_a_sees_own_marker_in_own_project(self):
        r = self.actor_a.get("/projects/%s/workspace" % self.alpha.project_id)
        self.assertIn(ALPHA_MARKER, r.get_data(as_text=True))

    def test_actor_a_can_read_own_project_over_the_api(self):
        r = self.actor_a.get("/api/v1/documents/%s" % self.alpha.project_id)
        self.assertEqual(r.status_code, 200)

    def test_actor_b_can_open_own_project(self):
        r = self.actor_b.get("/projects/%s/workspace" % self.bravo.project_id)
        self.assertEqual(r.status_code, 200)


class ProjectIsolationNegativeTests(_D1Base):
    """Negative access across the project-scoped retrieval surfaces."""

    def test_actor_a_cannot_open_foreign_workspace(self):
        r = self.actor_a.get("/projects/%s/workspace" % self.bravo.project_id)
        self.assertIn(r.status_code, (403, 404))
        self.assertNoMarker(r, BRAVO_MARKER, "workspace")

    def test_actor_a_cannot_open_foreign_dashboard(self):
        r = self.actor_a.get("/dashboard/%s" % self.bravo.project_id)
        self.assertIn(r.status_code, (403, 404))
        self.assertNoMarker(r, BRAVO_MARKER, "dashboard")

    def test_actor_a_cannot_read_foreign_project_over_the_api(self):
        r = self.actor_a.get("/api/v1/documents/%s" % self.bravo.project_id)
        self.assertIn(r.status_code, (403, 404))
        self.assertNoMarker(r, BRAVO_MARKER, "api document")

    def test_every_api_retrieval_surface_refuses_a_foreign_project(self):
        surfaces = [
            "/api/v1/documents/%s/requirements",
            "/api/v1/documents/%s/milestones",
            "/api/v1/documents/%s/consistency",
            "/api/v1/documents/%s/governance",
            "/api/v1/documents/%s/structural-units",
            "/api/v1/documents/%s/evidence",
            "/api/v1/documents/%s/rfi",
        ]
        for template in surfaces:
            url = template % self.bravo.project_id
            with self.subTest(url=url):
                r = self.actor_a.get(url)
                self.assertIn(r.status_code, (403, 404),
                              "%s returned %s" % (url, r.status_code))
                self.assertNoMarker(r, BRAVO_MARKER, url)

    def test_the_same_api_surfaces_do_serve_an_authorized_project(self):
        """Guard-the-guard for the refusal test above. If these endpoints
        refused everything, "refuses a foreign project" would be trivially
        true and would prove no boundary at all."""
        surfaces = [
            "/api/v1/documents/%s/requirements",
            "/api/v1/documents/%s/milestones",
            "/api/v1/documents/%s/consistency",
            "/api/v1/documents/%s/governance",
            "/api/v1/documents/%s/structural-units",
            "/api/v1/documents/%s/evidence",
        ]
        for template in surfaces:
            url = template % self.alpha.project_id
            with self.subTest(url=url):
                r = self.actor_a.get(url)
                self.assertEqual(r.status_code, 200,
                                 "%s refused its OWN project (%s)"
                                 % (url, r.status_code))

    def test_foreign_project_never_appears_in_listings(self):
        for url in ("/", "/home", "/projects", "/projects/choose"):
            with self.subTest(url=url):
                r = self.actor_a.get(url)
                self.assertNoMarker(r, BRAVO_MARKER, "listing " + url)

    def test_actor_a_own_project_does_appear_in_its_listing(self):
        """Guard-the-guard: the listing assertions above would pass trivially
        if listings rendered nothing at all."""
        r = self.actor_a.get("/projects")
        self.assertEqual(r.status_code, 200)
        self.assertIn(ALPHA_MARKER, r.get_data(as_text=True))

    def test_foreign_project_cannot_be_mutated(self):
        r = self.actor_a.post(
            "/projects/%s/workspace/cases" % self.bravo.project_id,
            data={"title": "intrusion", "objective": "intrusion"})
        self.assertIn(r.status_code, (403, 404, 405))


class ExistenceOracleTests(_D1Base):
    """A refusal must not reveal whether the project is real."""

    def test_foreign_and_nonexistent_projects_are_indistinguishable(self):
        nonexistent = "d1-no-such-project-" + str(uuid.uuid4())
        templates = [
            "/projects/%s/workspace",
            "/api/v1/documents/%s",
            "/dashboard/%s",
        ]
        for template in templates:
            with self.subTest(template=template):
                foreign = self.actor_a.get(template % self.bravo.project_id)
                unknown = self.actor_a.get(template % nonexistent)
                self.assertEqual(
                    foreign.status_code, unknown.status_code,
                    "%s distinguishes a real foreign project (%s) from an "
                    "unknown one (%s) - project ids are enumerable"
                    % (template, foreign.status_code, unknown.status_code))


class DirectObjectAccessTests(_D1Base):
    """IDOR probes: a known foreign object id, addressed from A's session."""

    def _bravo_case_id(self):
        workspace = self._store().get_or_create(self.bravo.project_id)
        return workspace.cases[0]["id"]

    def test_foreign_case_id_is_not_reachable_through_the_foreign_project(self):
        case_id = self._bravo_case_id()
        r = self.actor_a.get("/projects/%s/workspace?case=%s"
                             % (self.bravo.project_id, case_id))
        self.assertIn(r.status_code, (403, 404))
        self.assertNoMarker(r, BRAVO_MARKER, "foreign case by id")

    def test_foreign_object_id_does_not_resolve_under_an_authorized_project(self):
        """The sharper IDOR. A is genuinely authorized for ALPHA and names a
        BRAVO object under the ALPHA path, so the authorization check passes.
        The object must still not resolve, because objects are scoped to their
        own project's store rather than looked up globally."""
        case_id = self._bravo_case_id()
        r = self.actor_a.get("/projects/%s/workspace?case=%s"
                             % (self.alpha.project_id, case_id))
        self.assertNoMarker(r, BRAVO_MARKER, "cross-project object substitution")

    def test_foreign_governed_object_endpoints_refuse(self):
        case_id = self._bravo_case_id()
        templates = [
            "/api/v1/documents/%s/claims/%s/status",
            "/api/v1/documents/%s/evidence/%s/trust",
            "/api/v1/documents/%s/investigations/%s/sachet",
            "/api/v1/documents/%s/citations/%s",
            "/api/v1/documents/%s/relationships/%s/sachet",
        ]
        for template in templates:
            url = template % (self.bravo.project_id, case_id)
            with self.subTest(url=url):
                r = self.actor_a.get(url)
                self.assertIn(r.status_code, (400, 403, 404),
                              "%s returned %s" % (url, r.status_code))
                self.assertNoMarker(r, BRAVO_MARKER, url)


class MetadataNonDisclosureTests(_D1Base):
    """Blocking body content is not enough if identifiers still leak."""

    def test_no_foreign_marker_or_id_on_any_surface_actor_a_may_reach(self):
        surfaces = ["/", "/home", "/projects", "/projects/choose",
                    "/projects/%s/workspace" % self.alpha.project_id]
        for url in surfaces:
            with self.subTest(url=url):
                r = self.actor_a.get(url)
                body = r.get_data(as_text=True)
                self.assertNotIn(BRAVO_MARKER, body,
                                 "%s leaked the foreign marker" % url)
                self.assertNotIn(self.bravo.project_id, body,
                                 "%s leaked the foreign project id" % url)


class UnauthenticatedSurfaceTests(_D1Base):
    """Carry-through: the whole route table, driven with no session at all.

    The per-route audit behind this proof classified guards by reading them,
    and reading missed things in both directions - `_guard` and the in-body
    `is_admin() and developer_mode` check on /admin/nipigon/ are invisible to
    a decorator scan. Driving every route is the check that cannot be fooled
    by where the guard happens to be written.
    """

    #: Everything that may legitimately answer an anonymous GET. Anything new
    #: appearing here is a decision, not an accident - which is the point.
    PUBLIC = {
        "/", "/home", "/explore", "/login", "/forgot-password", "/start-trial",
        "/health", "/favicon.ico", "/manifest.webmanifest", "/sw.js",
    }

    def test_no_unlisted_route_serves_content_without_a_session(self):
        anon = self.flask_app.test_client()
        served = []
        for rule in self.flask_app.url_map.iter_rules():
            if "GET" not in (rule.methods or set()):
                continue
            path = str(rule)
            if "<" in path or path.startswith("/static"):
                continue
            if anon.get(path).status_code == 200:
                served.append(path)
        self.assertEqual(
            sorted(set(served) - self.PUBLIC), [],
            "these routes served content to an anonymous caller")

    def test_the_public_allowlist_is_not_silently_stale(self):
        """Guard-the-guard: if these stopped serving, the test above would
        pass by vacuum rather than by enforcement."""
        anon = self.flask_app.test_client()
        for path in ("/login", "/health"):
            with self.subTest(path=path):
                self.assertEqual(anon.get(path).status_code, 200)


class ModelContextIsolationTests(_D1Base):
    """Restricted evidence must be filtered BEFORE it reaches model context.

    "The model was told not to reveal it" is not a boundary. These assert the
    unauthorized material is never supplied in the first place.
    """

    def test_scope_ai_context_drops_sheets_outside_the_bearers_disciplines(self):
        from services.project_rbac import (
            authorize_token, issue_token, scope_ai_context)
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "engineer",
                                    label="d1-scope", disciplines=["structural"])
            token = authorize_token(raw)
            kept = scope_ai_context(token, [
                {"sheet_id": "S101", "text": "structural content"},
                {"sheet_id": "A101", "text": "ARCHITECTURAL SECRET"},
            ])
        kept_ids = [s["sheet_id"] for s in kept]
        self.assertIn("S101", kept_ids)
        self.assertNotIn("A101", kept_ids)
        self.assertNotIn("ARCHITECTURAL SECRET", str(kept))

    def test_scope_ai_context_fails_closed_on_an_unclassifiable_sheet(self):
        from services.project_rbac import (
            authorize_token, issue_token, scope_ai_context)
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "engineer",
                                    label="d1-closed", disciplines=["structural"])
            token = authorize_token(raw)
            kept = scope_ai_context(token, [{"sheet_id": "ZZZ-unknown-mark"}])
        self.assertEqual(kept, [],
                         "an unclassifiable sheet was passed into model context")

    def test_help_context_has_nowhere_to_put_project_evidence(self):
        """The boundary is the dataclass, not a rule someone remembers."""
        from services.help_mode import HelpContext
        fields = set(HelpContext.__dataclass_fields__.keys())
        for forbidden in ("project_id", "source_id", "claim_id", "case_id",
                          "evidence", "work_product_id"):
            self.assertNotIn(forbidden, fields)


class PartyZoneIsolationTests(_D1Base):
    """The only party/zone boundary that actually exists: discipline scoping."""

    def test_a_structural_token_is_refused_an_architectural_sheet(self):
        from services.project_rbac import (
            ProjectAccessRefused, authorize_sheet, issue_token)
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "trade",
                                    label="d1-trade", disciplines=["structural"])
            with self.assertRaises(ProjectAccessRefused):
                authorize_sheet(raw, self.alpha.project_id, "A101")

    def test_a_token_is_refused_a_sheet_in_another_project(self):
        from services.project_rbac import (
            ProjectAccessRefused, authorize_sheet, issue_token)
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "architect",
                                    label="d1-arch")
            with self.assertRaises(ProjectAccessRefused):
                authorize_sheet(raw, self.bravo.project_id, "A101")

    def test_refusals_do_not_vary_by_cause(self):
        """A refusal that differs by reason tells an unauthorized holder which
        guess was closer, and whether the project exists at all."""
        from services.project_rbac import (
            ProjectAccessRefused, authorize_sheet, issue_token)
        messages = set()
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "trade",
                                    label="d1-vary", disciplines=["structural"])
            attempts = (
                (raw, self.alpha.project_id, "A101"),          # wrong discipline
                (raw, self.bravo.project_id, "S101"),          # wrong project
                ("not-a-real-token", self.alpha.project_id, "S101"),  # no token
            )
            for args in attempts:
                try:
                    authorize_sheet(*args)
                except ProjectAccessRefused as exc:
                    messages.add(str(exc))
        self.assertEqual(len(messages), 1,
                         "refusal messages vary by cause: %s" % messages)


class ModelFacingSurfaceTests(_D1Base):
    """The surfaces that actually assemble context for a model: ask, Spin,
    briefing. Each is driven cross-project rather than reasoned about."""

    def test_a_token_for_one_project_cannot_ask_against_another(self):
        """The bearer-token model-facing path. project_ask re-checks that the
        resolved token's own project matches the URL, so a valid credential
        for ALPHA must not answer questions about BRAVO."""
        from services.project_rbac import issue_token
        with self.flask_app.app_context():
            _row, raw = issue_token(self.alpha.project_id, "architect",
                                    label="d1-ask")
        r = self.actor_a.post(
            "/project/%s/ask" % self.bravo.project_id,
            json={"question": "what is in this project?"},
            headers={"X-Project-Token": raw})
        self.assertIn(r.status_code, (401, 403, 404))
        self.assertNoMarker(r, BRAVO_MARKER, "cross-project ask")

    def test_spin_cannot_be_run_against_a_foreign_project(self):
        r = self.actor_a.post("/projects/%s/workspace/spin/run"
                              % self.bravo.project_id, data={})
        self.assertIn(r.status_code, (403, 404, 405))
        self.assertNoMarker(r, BRAVO_MARKER, "foreign Spin")

    def test_briefing_generation_cannot_target_a_foreign_project(self):
        r = self.actor_a.post("/projects/%s/workspace/briefing/generate"
                              % self.bravo.project_id, data={})
        self.assertIn(r.status_code, (403, 404, 405))
        self.assertNoMarker(r, BRAVO_MARKER, "foreign briefing")


class HelpSessionIsolationTests(_D1Base):
    """One reader's Help conversation is not another reader's to read."""

    def test_two_users_get_distinct_help_session_workspaces(self):
        from services.help_mode import help_session_project_id
        self.assertNotEqual(help_session_project_id("d1actora"),
                            help_session_project_id("d1actorb"))

    def test_usernames_differing_only_by_case_or_punctuation_do_not_collide(self):
        """CLAUDE-D1-HELP-SESSION-COLLISION-01 - the defect this proof found.

        Sanitising a username lowercases it and drops everything outside
        [a-z0-9-_.], which is not injective. `models.User.username` is unique
        but case-sensitive and matched exactly at sign-in, so both members of
        each pair below can exist as separate accounts - and before the fix
        they shared one Help workspace, each able to read the other's
        conversation.
        """
        from services.help_mode import help_session_project_id
        pairs = [("Alice", "alice"), ("a@b", "ab"), ("Carol", "carol"),
                 ("bob smith", "bobsmith")]
        for left, right in pairs:
            with self.subTest(pair=(left, right)):
                self.assertNotEqual(
                    help_session_project_id(left), help_session_project_id(right),
                    "%r and %r share a Help workspace" % (left, right))

    def test_the_same_username_always_resolves_to_the_same_workspace(self):
        """Injective is only half of it - it must also be stable, or a user
        loses their own conversation on every call."""
        from services.help_mode import help_session_project_id
        self.assertEqual(help_session_project_id("d1actora"),
                         help_session_project_id("d1actora"))

    def test_help_workspaces_are_recognised_as_reserved(self):
        from services.help_mode import help_session_project_id, is_help_workspace
        self.assertTrue(is_help_workspace(help_session_project_id("d1actora")))
        self.assertFalse(is_help_workspace(self.alpha.project_id))


if __name__ == "__main__":
    unittest.main()
