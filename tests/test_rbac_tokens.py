"""CLAUDE-RBAC-TOKENS-01 — project-scoped roles, tokens, and asset protection.

Written BEFORE the implementation, on the Product Owner's instruction, against
the pilot project `222109-1860-alstep-dr`.

WHAT THIS FILE IS DEFENDING, AND WHY EACH ONE IS HERE

1. **A platform admin does not implicitly see drawings.** Product Owner
   decision, explicit: *"Platform Admins manage infrastructure/tenants but do
   NOT implicitly bypass project drawing confidentiality."* This resolves
   Decision 4 of `governance/specified-unbuilt/tenancy-and-project-
   authorization.md` §5, which had blocked this work as "a genuine either/or
   with no engineering-only answer." It is the opposite of
   `services/project_access.py`'s `can_access_project`, whose first line is
   `if is_admin: return True` — that function governs whether an account may
   OPEN a project and is deliberately untouched here. Two different questions,
   two different answers, and conflating them is how an admin bypass gets
   reintroduced by accident.

2. **Assets must not be reachable without the check.** Measured before any of
   this was written: `/static/nipigon/A204.svg` returned **200
   unauthenticated**. A role check on a route that sits beside a world-readable
   file tree is authorisation theatre — the tests pass and nobody is stopped.
   So sheets live outside `static/` entirely and the only way to bytes is a
   route that authorises first.

3. **Cross-project isolation should be structural, not vigilant.**
   `services/storage_agent_access.py` already records the right instinct:
   *"There is deliberately no companion taking a project_id: an agent enrolled
   for one project cannot express a request for another… the ability was
   removed rather than a check added."* A token here carries its own project,
   and a request naming a different one is refused rather than reconciled.

4. **Refusals must not be an oracle.** Unknown, expired and revoked all refuse
   identically. Distinguishing them tells someone holding no valid credential
   whether a project exists and whether it has tokens.

Hermetic by construction rather than by mocking: this file imports no
ingestion path at all, so there is no `BHiveParser.parse` to remember to
patch. Nothing here reaches the Anthropic API, SMTP, or a network.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

# No ingestion import, and therefore no BHiveParser to patch: these tests write
# sheet bytes straight to the configured asset root. That is not a shortcut -
# it is what makes the file hermetic BY CONSTRUCTION rather than by remembering
# to mock, which is the failure mode CLAUDE.md records as having once cost an
# 8.5-hour test run. A token carries a plain-string project_id (the precedent
# StorageAgentEnrolment already sets, because projects live in the flat-JSON
# store and have no table to point at), so nothing here needs a real ingest.

PILOT_PROJECT_ID = "222109-1860-alstep-dr"
PILOT_PROJECT_NAME = "222109 1860 Alstep Dr"


class _RbacTestCase(unittest.TestCase):
    """One pilot project, one foreign project, and a sheet of each discipline."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_rbac_"))
        self.asset_dir = Path(tempfile.mkdtemp(prefix="beehive_test_assets_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["PROJECT_ASSET_PATH"] = str(self.asset_dir)

        with self.flask_app.app_context():
            db.session.add_all([
                User(username="admin_user",
                     password_hash=generate_password_hash("x"), role="admin"),
                User(username="architect_user",
                     password_hash=generate_password_hash("x"), role="read_only"),
            ])
            db.session.commit()

        # Real sheets on disk, outside static/. Two disciplines so a
        # discipline-scoped token has something to be refused.
        self._write_sheet(PILOT_PROJECT_ID, "A204", b"<svg>architectural</svg>")
        self._write_sheet(PILOT_PROJECT_ID, "RS501", b"<svg>structural</svg>")
        self._write_sheet("some-other-project", "A101", b"<svg>foreign</svg>")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        shutil.rmtree(self.asset_dir, ignore_errors=True)

    def _write_sheet(self, project_id: str, sheet_id: str, body: bytes):
        folder = self.asset_dir / project_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{sheet_id}.svg").write_bytes(body)

    def _issue(self, role, *, project_id=PILOT_PROJECT_ID, disciplines=None,
               ttl_seconds=3600, label="test token"):
        from services import project_rbac

        with self.flask_app.app_context():
            token_row, raw = project_rbac.issue_token(
                project_id, role, disciplines=disciplines, label=label,
                actor="architect_user", ttl_seconds=ttl_seconds)
            return token_row.id, raw

    def _issue_expired(self, role, **kwargs):
        """A token that has EXPIRED, made by aging it rather than by birth.

        issue_token now refuses a deadline already in the past - a pass that is
        dead on arrival is a configuration mistake, and refusing it is the
        point. So an expired credential is produced the way a real one becomes
        expired: it is issued valid, then time passes. Backdating expires_at is
        that, without the waiting.
        """
        from datetime import datetime, timedelta, timezone

        from models import ProjectAccessToken, db

        token_id, raw = self._issue(role, **kwargs)
        with self.flask_app.app_context():
            row = db.session.get(ProjectAccessToken, token_id)
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.session.commit()
        return token_id, raw

    def _get_sheet(self, raw_token, sheet_id, project_id=PILOT_PROJECT_ID):
        client = self.flask_app.test_client()
        headers = {}
        if raw_token is not None:
            headers["X-Project-Token"] = raw_token
        return client.get(f"/project/{project_id}/sheet/{sheet_id}", headers=headers)


# ===========================================================================
# Roles
# ===========================================================================
class RoleScopingTests(_RbacTestCase):
    def test_the_role_vocabulary_is_a_closed_set(self):
        from services import project_rbac

        self.assertEqual(
            set(project_rbac.PROJECT_ROLES),
            {"platform_admin", "architect", "owner", "engineer", "trade"})

    def test_an_unknown_role_cannot_be_issued(self):
        from services import project_rbac

        with self.flask_app.app_context():
            with self.assertRaises(project_rbac.ProjectAccessRefused):
                project_rbac.issue_token(PILOT_PROJECT_ID, "superuser",
                                         label="x", actor="architect_user")

    def test_a_platform_admin_token_does_not_open_a_drawing(self):
        """The Product Owner's Decision 4, and the whole point of the file.

        A platform admin manages infrastructure and tenants. Reading a
        confidential drawing is not infrastructure."""
        _id, raw = self._issue("platform_admin")
        for sheet in ("A204", "RS501"):
            with self.subTest(sheet=sheet):
                self.assertEqual(self._get_sheet(raw, sheet).status_code, 403)

    def test_architect_and_owner_read_every_discipline(self):
        for role in ("architect", "owner"):
            _id, raw = self._issue(role)
            for sheet in ("A204", "RS501"):
                with self.subTest(role=role, sheet=sheet):
                    self.assertEqual(self._get_sheet(raw, sheet).status_code, 200)

    def test_a_scoped_role_must_name_its_disciplines(self):
        """An engineer or trade token with no discipline set would silently
        mean either "all" or "none". Neither is safe to guess, so it is
        refused at issue time rather than resolved at read time."""
        from services import project_rbac

        with self.flask_app.app_context():
            for role in ("engineer", "trade"):
                with self.subTest(role=role):
                    with self.assertRaises(project_rbac.ProjectAccessRefused):
                        project_rbac.issue_token(PILOT_PROJECT_ID, role,
                                                 disciplines=None, label="x",
                                                 actor="architect_user")


# ===========================================================================
# Discipline isolation
# ===========================================================================
class DisciplineIsolationTests(_RbacTestCase):
    def test_a_structural_trade_token_is_refused_an_architectural_sheet(self):
        _id, raw = self._issue("trade", disciplines=["structural"])
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 200)
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)

    def test_an_architectural_engineer_token_is_refused_a_structural_sheet(self):
        _id, raw = self._issue("engineer", disciplines=["architectural"])
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 200)
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 403)

    def test_sheet_marks_map_to_the_disciplines_the_cover_index_uses(self):
        """The mapping is the one read off 5 Nipigon's own A100 drawing index:
        RS and S are both structural, SP is civil, and there is no P series."""
        from services import project_rbac

        cases = {
            "A204": "architectural", "A902": "architectural",
            "RS501": "structural", "S10": "structural",
            "M1": "mechanical", "E2": "electrical",
            "SP1": "civil", "L1": "landscape",
        }
        for sheet, expected in cases.items():
            with self.subTest(sheet=sheet):
                self.assertEqual(project_rbac.discipline_for_sheet(sheet), expected)

    def test_an_unrecognised_sheet_mark_is_refused_not_guessed(self):
        """A mark whose discipline cannot be determined must not fall through
        to "allowed". Refusing an unknown is recoverable; guessing is not."""
        from services import project_rbac

        self.assertIsNone(project_rbac.discipline_for_sheet("ZZ999"))
        _id, raw = self._issue("trade", disciplines=["structural"])
        self.assertEqual(self._get_sheet(raw, "ZZ999").status_code, 403)


# ===========================================================================
# Token lifecycle
# ===========================================================================
class TokenLifecycleTests(_RbacTestCase):
    def test_the_raw_token_is_never_persisted(self):
        """Same shape as PasswordResetToken, VerificationAccessToken and
        StorageAgentEnrolment: only the digest is stored."""
        from models import ProjectAccessToken, db

        token_id, raw = self._issue("architect")
        with self.flask_app.app_context():
            row = db.session.get(ProjectAccessToken, token_id)
            self.assertNotEqual(row.token_hash, raw)
            self.assertEqual(len(row.token_hash), 64)
            for column in row.__table__.columns:
                value = getattr(row, column.name)
                if isinstance(value, str):
                    self.assertNotIn(raw, value)

    def test_revoking_refuses_the_very_next_request(self):
        from services import project_rbac

        token_id, raw = self._issue("architect")
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 200)
        with self.flask_app.app_context():
            project_rbac.revoke_token(token_id, actor="architect_user")
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)

    def test_revoking_keeps_the_row_because_the_audit_trail_must_survive(self):
        from models import ProjectAccessToken, db
        from services import project_rbac

        token_id, _raw = self._issue("architect")
        with self.flask_app.app_context():
            project_rbac.revoke_token(token_id, actor="architect_user")
            row = db.session.get(ProjectAccessToken, token_id)
            self.assertIsNotNone(row)
            self.assertIsNotNone(row.revoked_at)
            self.assertEqual(row.revoked_by, "architect_user")

    def test_an_expired_token_is_refused(self):
        _id, raw = self._issue_expired("architect")
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)

    def test_unknown_expired_and_revoked_refuse_identically(self):
        """A refusal that varies tells an attacker which guess was closer."""
        from services import project_rbac

        revoked_id, revoked_raw = self._issue("architect")
        with self.flask_app.app_context():
            project_rbac.revoke_token(revoked_id, actor="architect_user")
        _eid, expired_raw = self._issue_expired("architect")

        bodies = set()
        for raw in ("never-issued-at-all", expired_raw, revoked_raw):
            response = self._get_sheet(raw, "A204")
            self.assertEqual(response.status_code, 403)
            bodies.add(response.get_data(as_text=True))
        self.assertEqual(len(bodies), 1, f"refusals differ: {bodies}")

    def test_no_token_at_all_is_refused(self):
        self.assertEqual(self._get_sheet(None, "A204").status_code, 403)

    def test_listing_active_tokens_excludes_revoked_and_expired(self):
        from services import project_rbac

        live_id, _ = self._issue("architect", label="live")
        revoked_id, _ = self._issue("owner", label="revoked")
        self._issue_expired("engineer", disciplines=["architectural"],
                            label="expired")
        with self.flask_app.app_context():
            project_rbac.revoke_token(revoked_id, actor="architect_user")
            active = project_rbac.list_active_tokens(PILOT_PROJECT_ID)
            self.assertEqual([t.id for t in active], [live_id])

    def test_listing_never_exposes_a_usable_secret(self):
        from services import project_rbac

        _id, raw = self._issue("architect")
        with self.flask_app.app_context():
            for row in project_rbac.list_active_tokens(PILOT_PROJECT_ID):
                for column in row.__table__.columns:
                    value = getattr(row, column.name)
                    if isinstance(value, str):
                        self.assertNotIn(raw, value)


# ===========================================================================
# Cross-project isolation
# ===========================================================================
class CrossProjectIsolationTests(_RbacTestCase):
    def test_a_pilot_token_cannot_read_another_projects_sheet(self):
        _id, raw = self._issue("architect")
        response = self._get_sheet(raw, "A101", project_id="some-other-project")
        self.assertEqual(response.status_code, 403)

    def test_the_refusal_does_not_reveal_whether_the_other_project_exists(self):
        _id, raw = self._issue("architect")
        real = self._get_sheet(raw, "A101", project_id="some-other-project")
        invented = self._get_sheet(raw, "A101", project_id="no-such-project")
        self.assertEqual(real.status_code, invented.status_code)
        self.assertEqual(real.get_data(as_text=True), invented.get_data(as_text=True))

    def test_the_token_carries_its_own_project_and_cannot_be_retargeted(self):
        """Structural, not vigilant: `authorize_token` resolves a project FROM
        the token. There is no parameter that could ask for a different one."""
        from services import project_rbac

        _id, raw = self._issue("architect")
        with self.flask_app.app_context():
            token = project_rbac.authorize_token(raw)
            self.assertEqual(token.project_id, PILOT_PROJECT_ID)

    def test_a_traversal_in_the_sheet_id_cannot_escape_the_project_folder(self):
        _id, raw = self._issue("architect")
        for attempt in ("../some-other-project/A101", "..%2fsome-other-project%2fA101",
                        "....//some-other-project//A101"):
            with self.subTest(attempt=attempt):
                self.assertIn(self._get_sheet(raw, attempt).status_code, (403, 404))


# ===========================================================================
# Assets are not reachable without the check
# ===========================================================================
class AssetsAreNotWorldReadableTests(_RbacTestCase):
    def test_the_pilot_projects_sheets_are_not_under_static(self):
        """The measurement that started this work: /static/nipigon/A204.svg
        answered 200 unauthenticated. A protected route beside a readable file
        tree protects nothing."""
        repo_static = Path(__file__).resolve().parents[1] / "static"
        stray = list(repo_static.rglob(f"{PILOT_PROJECT_ID}*"))
        self.assertEqual(stray, [])

    def test_the_asset_root_is_configured_outside_the_static_tree(self):
        configured = Path(self.flask_app.config["PROJECT_ASSET_PATH"]).resolve()
        repo_static = (Path(__file__).resolve().parents[1] / "static").resolve()
        self.assertFalse(str(configured).startswith(str(repo_static)))

    def test_a_valid_token_really_does_return_the_bytes(self):
        """The counterpart to every refusal above: this must actually work,
        or the tests are only proving that nothing serves anything."""
        _id, raw = self._issue("architect")
        response = self._get_sheet(raw, "A204")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"architectural", response.get_data())


# ===========================================================================
# Scoped AI context
# ===========================================================================
class ScopedAiContextTests(_RbacTestCase):
    SHEETS = [
        {"sheet_id": "A204", "title": "Ground Floor Plan"},
        {"sheet_id": "RS501", "title": "Structural Framing"},
        {"sheet_id": "M1", "title": "Plumbing and HVAC"},
    ]

    def test_context_drops_sheets_outside_the_tokens_discipline(self):
        from services import project_rbac

        _id, raw = self._issue("trade", disciplines=["structural"])
        with self.flask_app.app_context():
            token = project_rbac.authorize_token(raw)
            scoped = project_rbac.scope_ai_context(token, self.SHEETS)
        self.assertEqual([s["sheet_id"] for s in scoped], ["RS501"])

    def test_a_platform_admin_token_gets_an_empty_context(self):
        """Consistent with being refused the sheets themselves. A context
        builder that quietly included them would leak through the model what
        the route refuses over HTTP."""
        from services import project_rbac

        _id, raw = self._issue("platform_admin")
        with self.flask_app.app_context():
            token = project_rbac.authorize_token(raw)
            self.assertEqual(project_rbac.scope_ai_context(token, self.SHEETS), [])

    def test_an_architect_token_keeps_everything(self):
        from services import project_rbac

        _id, raw = self._issue("architect")
        with self.flask_app.app_context():
            token = project_rbac.authorize_token(raw)
            scoped = project_rbac.scope_ai_context(token, self.SHEETS)
        self.assertEqual(len(scoped), 3)

    def test_an_unrecognised_sheet_is_dropped_from_context_not_included(self):
        from services import project_rbac

        _id, raw = self._issue("engineer", disciplines=["architectural"])
        with self.flask_app.app_context():
            token = project_rbac.authorize_token(raw)
            scoped = project_rbac.scope_ai_context(
                token, self.SHEETS + [{"sheet_id": "ZZ999", "title": "Unknown"}])
        self.assertEqual([s["sheet_id"] for s in scoped], ["A204"])


# ===========================================================================
# CLAUDE-RBAC-TOKENS-02 — friction, and the honest hand-off to a human
# ===========================================================================
class _EscalationTestCase(_RbacTestCase):
    def _escalate(self, raw_token, *, query="where is the washroom detail?",
                  sheet_id="A204", view_box="0 0 24000 16000",
                  signal="unresolved_query", project_id=PILOT_PROJECT_ID):
        client = self.flask_app.test_client()
        headers = {"X-Project-Token": raw_token} if raw_token else {}
        return client.post(
            f"/project/{project_id}/escalation",
            headers=headers,
            json={"query": query, "sheet_id": sheet_id,
                  "view_box": view_box, "signal": signal})

    def _friction(self, raw_token, *, signal, sheet_id="A204",
                  callout_target=None, project_id=PILOT_PROJECT_ID):
        client = self.flask_app.test_client()
        headers = {"X-Project-Token": raw_token} if raw_token else {}
        return client.post(
            f"/project/{project_id}/friction",
            headers=headers,
            json={"signal": signal, "sheet_id": sheet_id,
                  "callout_target": callout_target})


class OutOfLeagueEscalationTests(_EscalationTestCase):
    def test_the_reply_carries_the_exact_words_specified(self):
        from services.project_rbac import OUT_OF_LEAGUE_MESSAGE

        self.assertEqual(OUT_OF_LEAGUE_MESSAGE,
                         "Sorry, this is out of my league. Help is underway.")
        _id, raw = self._issue("architect")
        response = self._escalate(raw)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["message"], OUT_OF_LEAGUE_MESSAGE)

    def test_the_payload_records_role_sheet_viewbox_and_the_verbatim_query(self):
        from services import project_rbac

        _id, raw = self._issue("trade", disciplines=["structural"])
        asked = "why does RS501 not match the slab edge?"
        self._escalate(raw, query=asked, sheet_id="RS501",
                       view_box="1200 900 4000 3000", signal="unresolved_query")
        with self.flask_app.app_context():
            queue = project_rbac.list_escalations(PILOT_PROJECT_ID)
            self.assertEqual(len(queue), 1)
            row = queue[0]
            self.assertEqual(row.asked_by_role, "trade")
            self.assertEqual(row.sheet_id, "RS501")
            self.assertEqual(row.view_box, "1200 900 4000 3000")
            self.assertEqual(row.query_text, asked)   # verbatim, not rewritten
            self.assertEqual(row.friction_signal, "unresolved_query")

    def test_the_role_and_project_come_from_the_token_not_the_payload(self):
        """A trade contractor must not be able to file an escalation that
        claims to be an architect's, or one belonging to another project.
        There is no parameter for either - this asserts the absence."""
        from services import project_rbac

        _id, raw = self._issue("trade", disciplines=["structural"])
        client = self.flask_app.test_client()
        client.post(
            f"/project/{PILOT_PROJECT_ID}/escalation",
            headers={"X-Project-Token": raw},
            json={"query": "q", "sheet_id": "RS501",
                  "asked_by_role": "architect",          # ignored
                  "project_id": "some-other-project"})   # ignored
        with self.flask_app.app_context():
            row = project_rbac.list_escalations(PILOT_PROJECT_ID)[0]
            self.assertEqual(row.asked_by_role, "trade")
            self.assertEqual(row.project_id, PILOT_PROJECT_ID)
            self.assertEqual(project_rbac.list_escalations("some-other-project"), [])

    def test_a_revoked_token_cannot_escalate(self):
        from services import project_rbac

        token_id, raw = self._issue("architect")
        self.assertEqual(self._escalate(raw).status_code, 202)
        with self.flask_app.app_context():
            project_rbac.revoke_token(token_id, actor="architect_user")
        self.assertEqual(self._escalate(raw).status_code, 403)

    def test_no_token_cannot_escalate(self):
        self.assertEqual(self._escalate(None).status_code, 403)

    def test_cannot_escalate_about_a_sheet_you_may_not_read(self):
        """A sheet id is itself information. A structural trade asking about
        an architectural sheet would put that sheet's identity into an
        operator-facing queue."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        self.assertEqual(self._escalate(raw, sheet_id="A204").status_code, 403)
        self.assertEqual(self._escalate(raw, sheet_id="RS501").status_code, 202)

    def test_cannot_escalate_into_another_project(self):
        _id, raw = self._issue("architect")
        response = self._escalate(raw, project_id="some-other-project")
        self.assertEqual(response.status_code, 403)

    def test_an_empty_or_oversized_question_is_refused(self):
        _id, raw = self._issue("architect")
        self.assertEqual(self._escalate(raw, query="   ").status_code, 403)
        self.assertEqual(self._escalate(raw, query="x" * 5000).status_code, 403)

    def test_one_bearer_cannot_flood_the_architects_queue(self):
        """Rage-tap detection means a frustrated person generates events fast.
        The cap is what stops the detector becoming the flood."""
        from services.project_rbac import MAX_OPEN_ESCALATIONS_PER_TOKEN

        _id, raw = self._issue("architect")
        for _ in range(MAX_OPEN_ESCALATIONS_PER_TOKEN):
            self.assertEqual(self._escalate(raw).status_code, 202)
        self.assertEqual(self._escalate(raw).status_code, 403)

    def test_resolving_frees_the_cap_and_keeps_the_record(self):
        from services import project_rbac
        from services.project_rbac import MAX_OPEN_ESCALATIONS_PER_TOKEN

        _id, raw = self._issue("architect")
        for _ in range(MAX_OPEN_ESCALATIONS_PER_TOKEN):
            self._escalate(raw)
        with self.flask_app.app_context():
            first = project_rbac.list_escalations(PILOT_PROJECT_ID)[0]
            project_rbac.resolve_escalation(first.id, actor="architect_user")
        self.assertEqual(self._escalate(raw).status_code, 202)
        with self.flask_app.app_context():
            everything = project_rbac.list_escalations(
                PILOT_PROJECT_ID, include_resolved=True)
            resolved = [e for e in everything if e.resolved_at is not None]
            self.assertEqual(len(resolved), 1)
            self.assertEqual(resolved[0].resolved_by, "architect_user")

    def test_nothing_is_transmitted_anywhere(self):
        """The queue is inert data an architect reads. ARCHIOSK does not dial
        out on a friction event, and this asserts the absence of any path that
        would - not a promise in a docstring."""
        import ast

        source = (Path(__file__).resolve().parents[1]
                  / "services" / "project_rbac.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for forbidden in ("send_email", "urlopen", "requests", "Anthropic",
                          "call_llm_json", "smtplib"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, names)


class ProactiveSuggestionTests(_EscalationTestCase):
    def test_a_dead_callout_offers_the_sheet_the_callout_itself_names(self):
        """Deterministic, not inferred: the callout reads 1/A801 and already
        names its target. No model is consulted."""
        _id, raw = self._issue("architect")
        response = self._friction(raw, signal="dead_callout", callout_target="A801")
        self.assertEqual(response.status_code, 200)
        suggestion = response.get_json()["suggestion"]
        self.assertEqual(suggestion["kind"], "open_sheet")
        self.assertEqual(suggestion["sheet_id"], "A801")

    def test_erratic_panning_offers_to_fit_the_sheet(self):
        _id, raw = self._issue("architect")
        suggestion = self._friction(raw, signal="erratic_pan").get_json()["suggestion"]
        self.assertEqual(suggestion["kind"], "reset_view")

    def test_nothing_is_offered_when_there_is_nothing_honest_to_offer(self):
        """An unhelpful suggestion is worse than silence: it costs a tap to
        dismiss, on a surface the person is already frustrated with."""
        _id, raw = self._issue("architect")
        response = self._friction(raw, signal="rage_tap", callout_target=None)
        self.assertIsNone(response.get_json()["suggestion"])

    def test_an_unknown_signal_produces_no_suggestion(self):
        _id, raw = self._issue("architect")
        response = self._friction(raw, signal="made_up_signal", callout_target="A801")
        self.assertIsNone(response.get_json()["suggestion"])

    def test_friction_reporting_is_authorised_like_everything_else(self):
        _id, raw = self._issue("trade", disciplines=["structural"])
        # Reporting friction on a sheet this bearer cannot read is refused,
        # or it becomes a probe for which sheet ids exist.
        self.assertEqual(
            self._friction(raw, signal="dead_callout", sheet_id="A204").status_code, 403)
        self.assertEqual(
            self._friction(raw, signal="dead_callout", sheet_id="RS501").status_code, 200)
        self.assertEqual(self._friction(None, signal="dead_callout").status_code, 403)


class FrictionTelemetryClientTests(unittest.TestCase):
    """The browser half. Asserted against the source, since this suite runs no
    JS - but what is asserted is behaviour that would be wrong to lose: a
    detector that reports continuously is a detector nobody keeps enabled."""

    @classmethod
    def setUpClass(cls):
        cls.js = (Path(__file__).resolve().parents[1]
                  / "static" / "js" / "friction_telemetry.js").read_text(encoding="utf-8")

    def test_all_three_signals_the_directive_named_are_detected(self):
        for signal in ("rage_tap", "dead_callout", "erratic_pan"):
            with self.subTest(signal=signal):
                self.assertIn(signal, self.js)

    def test_it_reports_at_most_once_per_signal_per_cooldown(self):
        self.assertIn("COOLDOWN_MS", self.js)
        self.assertIn("lastReported", self.js)

    def test_it_never_reports_a_successful_interaction(self):
        """A dead-click detector that fires on live controls too is just a
        click logger, and turns an assistance feature into surveillance."""
        self.assertIn("closest(", self.js)
        self.assertIn("INTERACTIVE", self.js)

    def test_it_sends_no_page_content_only_the_signal_and_its_own_context(self):
        """READING page content and WRITING into the page are not the same
        thing, and an assertion that cannot tell them apart is worse than none:
        it fails on the comment describing the rule, and it would forbid
        rendering the suggestion at all.

        So: comments stripped first (this file's own prose names the tokens it
        forbids, exactly the trap test_voice_optin_and_mic_cue_01 already
        solved), then innerText/innerHTML/cookies must be absent outright, and
        every surviving `textContent` must be an ASSIGNMENT — text going into
        the page, never text coming out of it."""
        import re

        code = re.sub(r"/\*.*?\*/", "", self.js, flags=re.S)
        code = re.sub(r"(?<![:\w])//.*$", "", code, flags=re.M)

        for forbidden in ("innerText", "innerHTML", "document.cookie", "outerHTML"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, code)

        reads = [m.group(0) for m in re.finditer(r"\.textContent(?!\s*=)", code)]
        self.assertEqual(reads, [], f"textContent read rather than written: {reads}")

    def test_the_request_body_carries_only_three_named_fields(self):
        """The payload is enumerated in the source, so it can be read off
        rather than trusted: a signal name, the sheet already in the URL, and
        a callout target this application itself wrote into a data attribute."""
        import re

        body = self.js[self.js.index("var body = {"):]
        body = body[: body.index("};")]
        keys = set(re.findall(r"^\s*(\w+):", body, flags=re.M))
        self.assertEqual(keys, {"signal", "sheet_id", "callout_target"})

    def test_it_degrades_to_silence_rather_than_erroring(self):
        """A telemetry feature must never be the reason a drawing surface
        stops working - so no token means no listeners, and every failure path
        is swallowed."""
        self.assertIn("if (!projectId || !token) { return; }", self.js)
        self.assertIn(".catch(function () {", self.js)


class BiddingPortalIsScaffoldOnlyTests(_RbacTestCase):
    """CLAUDE-RBAC-TOKENS-03. The component must not be clickable, focusable
    or visible until it is deliberately activated.

    The strong version of that is ABSENT, not hidden. These assert absence,
    because `display: none` leaves the markup in the DOM where it is readable
    in devtools, ships to every visitor, and returns the moment any stylesheet
    is overridden.
    """

    def _render(self, **context):
        """Render the partial through the Jinja environment directly.

        NOT flask.render_template: that runs the application's context
        processors, which need a request context this test has no reason to
        build. The guard being tested belongs to the template itself, so the
        template is what gets rendered.
        """
        return self.flask_app.jinja_env.get_template(
            "_bidding_portal.html").render(**context)

    def test_the_flag_ships_off(self):
        self.assertIs(self.flask_app.config["ENABLE_BIDDING_PORTAL"], False)

    def test_the_flag_is_not_environment_switchable(self):
        """A marketplace must not be turnable on by a stray env var on a host
        somebody forgot about. Turning it on is a reviewed code change."""
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "config.py").read_text(encoding="utf-8")
        line = next(l for l in source.splitlines() if "ENABLE_BIDDING_PORTAL" in l and "=" in l)
        self.assertNotIn("getenv", line)
        self.assertNotIn("environ", line)

    def test_no_role_reaches_it_while_the_flag_is_off(self):
        """Not "trade and owner are refused" - NOBODY is admitted. There is no
        combination of arguments that returns True with the flag off."""
        from services import project_rbac

        for role, disciplines in (("architect", None), ("owner", None),
                                  ("platform_admin", None),
                                  ("engineer", ["architectural"]),
                                  ("trade", ["structural"])):
            with self.subTest(role=role):
                _id, raw = self._issue(role, disciplines=disciplines)
                with self.flask_app.app_context():
                    token = project_rbac.authorize_token(raw)
                    self.assertFalse(
                        project_rbac.bidding_portal_visible(token, enabled=False))

    def test_when_enabled_it_is_for_trade_and_owner_only(self):
        """The audience is on the record. `architect` is excluded on purpose:
        the architect ISSUES the work, and an issuer who could bid is a
        conflict of interest built into the software."""
        from services import project_rbac

        self.assertEqual(set(project_rbac.BIDDING_PORTAL_ROLES), {"trade", "owner"})
        admitted, refused = [], []
        for role, disciplines in (("architect", None), ("owner", None),
                                  ("platform_admin", None),
                                  ("engineer", ["architectural"]),
                                  ("trade", ["structural"])):
            _id, raw = self._issue(role, disciplines=disciplines)
            with self.flask_app.app_context():
                token = project_rbac.authorize_token(raw)
                target = admitted if project_rbac.bidding_portal_visible(
                    token, enabled=True) else refused
                target.append(role)
        self.assertEqual(set(admitted), {"trade", "owner"})
        self.assertEqual(set(refused), {"architect", "platform_admin", "engineer"})

    def test_a_missing_token_is_never_admitted(self):
        from services import project_rbac

        self.assertFalse(project_rbac.bidding_portal_visible(None, enabled=True))

    def test_the_template_emits_nothing_at_all_when_not_visible(self):
        """The property that matters: absent, not hidden."""
        rendered = self._render(bidding_portal_visible=False)
        self.assertEqual(rendered.strip(), "")
        for token in ("bidding-portal", "Submit a bid", "data-ui-ref"):
            with self.subTest(token=token):
                self.assertNotIn(token, rendered)

    def test_the_scaffold_cannot_be_pressed_or_tabbed_into_even_when_shown(self):
        """If somebody flips the flag before the feature exists, the controls
        must still refuse to behave like controls - a scaffold that could be
        tabbed into and pressed is a promise the product cannot keep."""
        rendered = self._render(bidding_portal_visible=True)
        self.assertIn("bidding-portal", rendered)
        import re

        buttons = re.findall(r"<button[^>]*>", rendered)
        self.assertTrue(buttons)
        for button in buttons:
            with self.subTest(button=button[:60]):
                self.assertIn("disabled", button)
                self.assertIn('tabindex="-1"', button)
                self.assertIn('aria-hidden="true"', button)

    def test_the_scaffold_invents_no_bid_packages(self):
        """Example rows would be a fabricated record of work that does not
        exist. The list is empty and says so."""
        rendered = self._render(bidding_portal_visible=True)
        self.assertIn("No bid packages issued.", rendered)
        self.assertIn("Not open", rendered)

    def test_there_is_no_route_behind_it(self):
        """Hiding a component while its endpoint answers would be the same
        authorisation theatre the sheet route was built to avoid."""
        rules = [str(r) for r in self.flask_app.url_map.iter_rules()]
        offenders = [r for r in rules if "bid" in r.lower()]
        self.assertEqual(offenders, [])


# ===========================================================================
# CLAUDE-RBAC-TOKENS-04 — the architect provisions access before anyone arrives
# ===========================================================================
class _ManagePanelTestCase(_RbacTestCase):
    """The panel is session-gated; the passes it issues are token-gated."""

    def setUp(self):
        super().setUp()
        from services.case_workspace import CaseWorkspaceStore

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(PILOT_PROJECT_ID)
        workspace.owner = "architect_user"
        store.save(workspace)

    def _session(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _architect(self):
        return self._session("architect_user", 2, "read_only")

    def _admin(self):
        return self._session("admin_user", 1, "admin")

    def _create(self, client, **form):
        payload = {"label": "Framing Subcontractor", "role": "trade",
                   "disciplines": ["structural"], "expires_in": "24h"}
        payload.update(form)
        return client.post(f"/project/{PILOT_PROJECT_ID}/manage/access", data=payload)


class AccessPanelGatingTests(_ManagePanelTestCase):
    def test_the_project_owner_reaches_the_panel(self):
        response = self._architect().get(f"/project/{PILOT_PROJECT_ID}/manage/access")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Issue a pass", response.get_data(as_text=True))

    def test_an_unauthenticated_visitor_does_not(self):
        response = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}/manage/access")
        self.assertIn(response.status_code, (302, 401, 403))

    def test_a_stranger_with_a_session_does_not(self):
        response = self._session("nobody", 99, "read_only").get(
            f"/project/{PILOT_PROJECT_ID}/manage/access")
        self.assertEqual(response.status_code, 403)

    def test_an_admin_may_manage_passes_and_still_cannot_read_a_drawing(self):
        """The separation Decision 4 asked for, asserted in one test.

        Managing access is not the same capability as having it: an admin can
        hand out a pass, and their session still buys them nothing at the sheet
        route, which takes only a project token."""
        admin = self._admin()
        self.assertEqual(
            admin.get(f"/project/{PILOT_PROJECT_ID}/manage/access").status_code, 200)
        self.assertEqual(
            admin.get(f"/project/{PILOT_PROJECT_ID}/sheet/A204").status_code, 403)

    def test_the_panel_never_renders_drawing_content(self):
        """Which is WHY an admin may reach it. If this page showed what is on a
        sheet, gating it by session would reopen the bypass."""
        body = self._architect().get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        self.assertNotIn("<svg", body)
        self.assertNotIn("architectural</svg>", body)


class PreProvisionedPassTests(_ManagePanelTestCase):
    def test_generating_a_pass_shows_a_link_exactly_once(self):
        response = self._create(self._architect())
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("manage.access.issued-link", body)
        self.assertIn(f"/project/{PILOT_PROJECT_ID}?token=", body)

    def test_the_raw_token_is_not_written_into_the_session_cookie(self):
        """`flash()` stores its message in the session cookie, which would put
        a live credential into the architect's own browser and into anything
        that logs cookies. The link is rendered in the response instead."""
        client = self._architect()
        response = self._create(client)
        import re

        match = re.search(r"\?token=([A-Za-z0-9_\-]+)", response.get_data(as_text=True))
        self.assertIsNotNone(match)
        raw = match.group(1)
        cookies = "".join(str(h) for k, h in response.headers if k == "Set-Cookie")
        self.assertNotIn(raw, cookies)

    def test_a_generated_pass_really_opens_the_sheets_it_was_scoped_to(self):
        import re

        response = self._create(self._architect(),
                                role="trade", disciplines=["structural"])
        raw = re.search(r"\?token=([A-Za-z0-9_\-]+)",
                        response.get_data(as_text=True)).group(1)
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 200)
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)

    def test_a_custom_calendar_date_is_honoured_to_the_end_of_that_day(self):
        """"Until Jan 21" must still work ON Jan 21. Expiring at 00:00 would
        cut the pass a full day short of what the architect wrote down."""
        from datetime import datetime, timezone
        from services import project_rbac

        self._create(self._architect(), expires_on="2027-01-21", expires_in="")
        with self.flask_app.app_context():
            row = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"]
            expires = row.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            self.assertEqual(expires.date(), datetime(2027, 1, 21).date())
            self.assertEqual((expires.hour, expires.minute), (23, 59))

    def test_a_date_already_past_is_refused_at_issue_time(self):
        """A pass that is dead on arrival is a configuration mistake, and the
        moment to surface it is while the architect is still looking at the
        form - not when a subcontractor is standing on a site."""
        response = self._create(self._architect(),
                                expires_on="2020-01-01", expires_in="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("could not be issued", response.get_data(as_text=True))

    def test_an_unparseable_date_is_refused_rather_than_guessed(self):
        response = self._create(self._architect(),
                                expires_on="21 Jan 2027", expires_in="")
        self.assertEqual(response.status_code, 400)

    def test_a_scoped_role_with_no_disciplines_is_refused(self):
        response = self._create(self._architect(), role="trade", disciplines=[])
        self.assertEqual(response.status_code, 400)

    def test_a_pass_with_no_name_is_refused_because_it_cannot_be_audited(self):
        response = self._create(self._architect(), label="   ")
        self.assertEqual(response.status_code, 400)

    def test_the_form_cannot_mint_an_architect_or_platform_admin_pass(self):
        """A form that issues another architect pass is a privilege-escalation
        control wearing a form label."""
        from routes.project_manage import ISSUABLE_ROLES

        self.assertEqual(set(ISSUABLE_ROLES), {"owner", "engineer", "trade"})
        for role in ("architect", "platform_admin"):
            with self.subTest(role=role):
                self.assertEqual(self._create(self._architect(), role=role).status_code, 400)

    def test_expiry_actually_stops_the_pass_and_the_table_says_so(self):
        from services import project_rbac

        _id, raw = self._issue_expired("architect")
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)
        with self.flask_app.app_context():
            statuses = {e["status"] for e in project_rbac.list_all_tokens(PILOT_PROJECT_ID)}
            self.assertIn("expired", statuses)

    def test_issuing_a_dead_on_arrival_pass_is_refused(self):
        """The invariant that made the helper above necessary, asserted
        directly so it cannot be lost."""
        from services import project_rbac

        with self.flask_app.app_context():
            with self.assertRaises(project_rbac.ProjectAccessRefused):
                project_rbac.issue_token(PILOT_PROJECT_ID, "architect",
                                         label="dead", actor="architect_user",
                                         ttl_seconds=-1)


class PassRevocationFromThePanelTests(_ManagePanelTestCase):
    def test_revoke_now_cuts_access_off_on_the_very_next_request(self):
        import re
        from services import project_rbac

        client = self._architect()
        response = self._create(client, role="trade", disciplines=["structural"])
        raw = re.search(r"\?token=([A-Za-z0-9_\-]+)",
                        response.get_data(as_text=True)).group(1)
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 200)

        with self.flask_app.app_context():
            token_id = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"].id
        revoked = client.post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/revoke")
        self.assertEqual(revoked.status_code, 302)
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 403)

    def test_a_pass_from_another_project_cannot_be_revoked_from_this_panel(self):
        """Or the page becomes a lever on projects it does not own."""
        from services import project_rbac

        with self.flask_app.app_context():
            foreign, _raw = project_rbac.issue_token(
                "some-other-project", "architect", label="foreign",
                actor="someone", ttl_seconds=3600)
            foreign_id = foreign.id
        response = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{foreign_id}/revoke")
        self.assertEqual(response.status_code, 403)
        with self.flask_app.app_context():
            still = project_rbac.list_all_tokens("some-other-project")[0]
            self.assertEqual(still["status"], "active")

    def test_the_table_keeps_revoked_and_expired_rows(self):
        """The table answers "who has access". One that dropped withdrawn
        passes could not answer "who used to", which is the question asked
        after an incident."""
        from services import project_rbac

        client = self._architect()
        self._create(client, label="live one")
        self._create(client, label="to be revoked")
        with self.flask_app.app_context():
            rows = project_rbac.list_all_tokens(PILOT_PROJECT_ID)
            project_rbac.revoke_token(rows[0]["token"].id, actor="architect_user")
        body = client.get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        self.assertIn("live one", body)
        self.assertIn("to be revoked", body)
        self.assertIn("revoked", body)

    def test_revoked_beats_expired_in_the_status_word(self):
        """A pass that was withdrawn and then also lapsed should read as
        withdrawn: "expired" would suggest it merely ran out and could be
        renewed, when somebody actually took it away."""
        from services import project_rbac

        with self.flask_app.app_context():
            row, _raw = project_rbac.issue_token(
                PILOT_PROJECT_ID, "architect", label="both",
                actor="architect_user", ttl_seconds=1)
            project_rbac.revoke_token(row.id, actor="architect_user")
            from datetime import datetime, timedelta, timezone

            later = datetime.now(timezone.utc) + timedelta(days=2)
            self.assertEqual(project_rbac.token_status(row, now=later), "revoked")


class StakeholderEntryPageTests(_ManagePanelTestCase):
    def test_the_issued_link_lands_on_a_real_page(self):
        """A management panel that hands out dead links is worse than one that
        hands out none."""
        import re

        response = self._create(self._architect(),
                                role="trade", disciplines=["structural"])
        link = re.search(r'value="([^"]*\?token=[^"]+)"',
                         response.get_data(as_text=True)).group(1)
        landed = self.flask_app.test_client().get(link)
        self.assertEqual(landed.status_code, 200)

    def test_it_lists_only_the_sheets_that_pass_may_read(self):
        """A sheet mark is itself information. Showing refused rows would leak
        the shape of the drawing set to everyone holding any pass."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn("RS501", body)
        self.assertNotIn("A204", body)

    def test_an_architect_pass_sees_every_sheet_on_disk(self):
        _id, raw = self._issue("architect")
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn("RS501", body)
        self.assertIn("A204", body)

    def test_no_token_and_a_foreign_token_are_both_refused(self):
        _id, raw = self._issue("architect")
        client = self.flask_app.test_client()
        self.assertEqual(client.get(f"/project/{PILOT_PROJECT_ID}").status_code, 403)
        self.assertEqual(
            client.get(f"/project/some-other-project?token={raw}").status_code, 403)

    def test_the_bidding_scaffold_is_absent_from_the_entry_page(self):
        """The flag ships off, so there is nothing in the DOM to reveal."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertNotIn("bidding-portal", body)
        self.assertNotIn("Submit a bid", body)


# ===========================================================================
# CLAUDE-TRIAL-SAFE-LANDING-01 — running out of fuel without crashing
# ===========================================================================
class _SafeLandingTestCase(_RbacTestCase):
    """A small allowance and a SPY where the model would be.

    The spy is the point of the whole file: "we stop calling the API" is a
    claim about cost and about a data boundary, so it is proved by counting
    calls rather than by reading a branch. It is also what keeps these tests
    hermetic - no key, no network, no Anthropic client is ever constructed.
    """

    ALLOWANCE = 3

    def setUp(self):
        super().setUp()
        self.flask_app.config["TRIAL_QUERY_ALLOWANCE"] = self.ALLOWANCE
        self.flask_app.config["ADMIN_CONTACT_EMAIL"] = "admin@archiosk.com"
        self.model_calls = []

    def _ask(self, raw_token, question="what is on this sheet?",
             project_id=PILOT_PROJECT_ID, sheets=None, view_box="0 0 100 100"):
        from unittest.mock import patch

        def spy(question_text, context):
            self.model_calls.append({"question": question_text, "context": context})
            return "A complete answer about the drawing."

        client = self.flask_app.test_client()
        headers = {"X-Project-Token": raw_token} if raw_token else {}
        with patch("routes.project_query._invoke_model", side_effect=spy):
            return client.post(
                f"/project/{project_id}/ask",
                headers=headers,
                json={"question": question, "view_box": view_box,
                      "sheets": sheets if sheets is not None
                                else [{"sheet_id": "RS501"}, {"sheet_id": "A204"}]})


class SafeLandingMessageTests(_SafeLandingTestCase):
    def test_the_message_is_exactly_the_words_specified(self):
        from services.trial_allowance import SAFE_LANDING_MESSAGE

        self.assertEqual(
            SAFE_LANDING_MESSAGE,
            "You have run out of fuel, but the system allows you to get home "
            "safely. Contact admin for further help.")

    def test_queries_below_the_cap_carry_no_message_at_all(self):
        _id, raw = self._issue("architect")
        for _ in range(self.ALLOWANCE - 1):
            body = self._ask(raw).get_json()
            self.assertIsNone(body["safe_landing"])
            self.assertTrue(body["model_called"])

    def test_the_quota_exhausting_prompt_completes_in_full_before_locking(self):
        """The failure this feature exists to prevent is being cut off
        mid-thought. The query that crosses the line is answered properly, and
        the warning arrives attached to a complete response."""
        _id, raw = self._issue("architect")
        for _ in range(self.ALLOWANCE - 1):
            self._ask(raw)

        body = self._ask(raw).get_json()          # the one that exhausts it
        self.assertEqual(body["answer"], "A complete answer about the drawing.")
        self.assertTrue(body["model_called"])
        self.assertEqual(len(self.model_calls), self.ALLOWANCE)
        self.assertIsNotNone(body["safe_landing"])
        self.assertIn("run out of fuel", body["safe_landing"]["message"])

    def test_the_final_delivery_still_carries_the_vector_coordinates(self):
        """"Deliver the full response AND the viewBox" - truncating the
        coordinates would leave the viewer unable to show what was answered."""
        _id, raw = self._issue("architect")
        for _ in range(self.ALLOWANCE - 1):
            self._ask(raw)
        body = self._ask(raw, view_box="1200 900 4000 3000").get_json()
        self.assertEqual(body["view_box"], "1200 900 4000 3000")
        self.assertIsNotNone(body["safe_landing"])


class PostQuotaGateTests(_SafeLandingTestCase):
    def _exhaust(self, raw):
        for _ in range(self.ALLOWANCE):
            self._ask(raw)
        self.model_calls.clear()

    def test_the_next_prompt_is_intercepted_with_the_courtesy_message(self):
        _id, raw = self._issue("architect")
        self._exhaust(raw)

        body = self._ask(raw).get_json()
        self.assertIsNone(body["answer"])
        self.assertFalse(body["model_called"])
        self.assertIn("run out of fuel", body["safe_landing"]["message"])

    def test_no_external_model_api_is_invoked_after_exhaustion(self):
        """The claim, proved by counting rather than by reading the branch."""
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        for _ in range(5):
            self._ask(raw)
        self.assertEqual(self.model_calls, [])

    def test_refused_queries_do_not_inflate_the_counter(self):
        """Counting refusals would let anyone push the number arbitrarily high
        against a project that is already stopped, corrupting the only record
        of what a trial actually used."""
        from services import trial_allowance

        _id, raw = self._issue("architect")
        self._exhaust(raw)
        for _ in range(4):
            self._ask(raw)
        with self.flask_app.app_context():
            self.assertEqual(
                trial_allowance.usage(PILOT_PROJECT_ID, limit=self.ALLOWANCE)["used"],
                self.ALLOWANCE)

    def test_the_response_still_carries_a_working_admin_link(self):
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        triggers = self._ask(raw).get_json()["safe_landing"]["triggers"]
        contact = next(t for t in triggers if t["kind"] == "contact_admin")
        self.assertTrue(contact["href"].startswith("mailto:admin%40archiosk.com"))
        self.assertIn("Refuel%20AI%20Access%20-%20222109-1860-alstep-dr",
                      contact["href"])

    def test_both_action_triggers_are_offered(self):
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        kinds = {t["kind"] for t in self._ask(raw).get_json()["safe_landing"]["triggers"]}
        self.assertEqual(kinds, {"byok", "contact_admin"})

    def test_the_mailto_carries_project_organization_and_timestamp(self):
        from urllib.parse import unquote

        _id, raw = self._issue("architect")
        self._exhaust(raw)
        triggers = self._ask(raw).get_json()["safe_landing"]["triggers"]
        body = unquote(next(t for t in triggers if t["kind"] == "contact_admin")["href"])
        self.assertIn(PILOT_PROJECT_ID, body)
        self.assertIn("Organization:", body)
        self.assertIn("Timestamp:", body)

    def test_the_mailto_never_carries_the_token_or_the_question(self):
        """A mailto opens in the sender's own client: its contents land in
        their sent folder, their drafts and any client-side sync. Neither a
        credential nor somebody's question belongs there."""
        from urllib.parse import unquote

        _id, raw = self._issue("architect")
        self._exhaust(raw)
        secret_question = "zebra-marker-question-text"
        triggers = self._ask(raw, question=secret_question).get_json()["safe_landing"]["triggers"]
        href = unquote(next(t for t in triggers if t["kind"] == "contact_admin")["href"])
        self.assertNotIn(raw, href)
        self.assertNotIn(secret_question, href)


class DrawingToolImmunityTests(_SafeLandingTestCase):
    """The second half of the promise: "the system allows you to get home
    safely". Every one of these runs with the allowance fully spent."""

    def _exhaust(self, raw):
        for _ in range(self.ALLOWANCE):
            self._ask(raw)

    def test_sheets_still_open_after_the_quota_is_gone(self):
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        for sheet in ("A204", "RS501"):
            with self.subTest(sheet=sheet):
                self.assertEqual(self._get_sheet(raw, sheet).status_code, 200)

    def test_discipline_scoping_still_holds_after_the_quota_is_gone(self):
        """Running out of fuel must not quietly widen access either."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        self._exhaust(raw)
        self.assertEqual(self._get_sheet(raw, "RS501").status_code, 200)
        self.assertEqual(self._get_sheet(raw, "A204").status_code, 403)

    def test_sheet_navigation_still_lists_sheets_after_the_quota_is_gone(self):
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn("RS501", body)
        self.assertIn("A204", body)

    def test_escalating_to_a_human_still_works_after_the_quota_is_gone(self):
        """The moment somebody most needs a person is the moment the machine
        stopped answering."""
        _id, raw = self._issue("architect")
        self._exhaust(raw)
        client = self.flask_app.test_client()
        response = client.post(
            f"/project/{PILOT_PROJECT_ID}/escalation",
            headers={"X-Project-Token": raw},
            json={"query": "the model stopped, can someone help", "sheet_id": "A204"})
        self.assertEqual(response.status_code, 202)

    def test_the_viewer_routes_never_import_the_meter(self):
        """Structural, not vigilant: there is no code path through which quota
        state could reach a drawing, because the modules that serve drawings do
        not import the module that holds it."""
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for module in ("routes/project_assets.py", "routes/project_entry.py"):
            with self.subTest(module=module):
                tree = ast.parse((root / module).read_text(encoding="utf-8"))
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
                    elif isinstance(node, ast.Import):
                        imported.update(a.name for a in node.names)
                self.assertNotIn("services.trial_allowance", imported)


class ByokOverrideTests(_SafeLandingTestCase):
    def test_a_byok_key_unblocks_inference_immediately(self):
        """The cap bounds OUR cost. A project paying with its own key is not
        on the meter at all."""
        _id, raw = self._issue("architect")
        for _ in range(self.ALLOWANCE):
            self._ask(raw)
        self.assertFalse(self._ask(raw).get_json()["model_called"])

        from services.case_workspace import CaseWorkspaceStore

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(PILOT_PROJECT_ID)
        setattr(workspace, "byok_api_key_encrypted", "an-encrypted-blob")
        store.save(workspace)

        body = self._ask(raw).get_json()
        self.assertTrue(body["model_called"])
        self.assertIsNone(body["safe_landing"])

    def test_byok_does_not_advance_the_trial_counter(self):
        from services import trial_allowance

        with self.flask_app.app_context():
            for _ in range(10):
                state = trial_allowance.consume_query(
                    PILOT_PROJECT_ID, limit=self.ALLOWANCE, byok=True)
                self.assertEqual(state, "allowed")
            self.assertEqual(
                trial_allowance.usage(PILOT_PROJECT_ID, limit=self.ALLOWANCE)["used"], 0)

    def test_presence_is_all_that_is_read_never_the_value(self):
        """`byok_key_present` returns a bool. Nothing in the module returns,
        logs or compares the key itself, so it cannot leak by accident."""
        import ast
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "services" / "trial_allowance.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        func = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "byok_key_present")
        returns = [n for n in ast.walk(func) if isinstance(n, ast.Return)]
        self.assertTrue(returns)
        for node in returns:
            rendered = ast.dump(node.value)
            self.assertTrue("bool" in rendered or "Constant" in rendered,
                            f"byok_key_present may return a raw value: {rendered}")

    def test_the_ai_context_is_still_scoped_when_byok_is_in_use(self):
        """Paying your own way buys inference, not other disciplines."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        from services.case_workspace import CaseWorkspaceStore

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(PILOT_PROJECT_ID)
        setattr(workspace, "byok_api_key_encrypted", "an-encrypted-blob")
        store.save(workspace)

        body = self._ask(raw).get_json()
        self.assertEqual(body["sheets_in_scope"], ["RS501"])


# ===========================================================================
# CLAUDE-FISH-TANK-01 / CLAUDE-PUBLIC-FOOTER-01
# ===========================================================================
class FishTankContainerTests(_ManagePanelTestCase):
    def test_the_sheet_directory_renders_inside_the_tank(self):
        _id, raw = self._issue("architect")
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn('data-ui-ref="tank.container"', body)
        self.assertIn("tank-canvas", body)
        self.assertIn("tank-grid", body)

    def test_every_node_is_the_whole_link_not_a_card_with_a_button_in_it(self):
        """A card that is decorative except for a button inside it teaches
        people to aim, and aiming is what fails on a phone held at arm's length
        on a site. It also keeps keyboard and screen-reader support for free."""
        import re

        _id, raw = self._issue("architect")
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        nodes = re.findall(r'<a class="tank-node[^"]*"[^>]*>(.*?)</a>', body, re.S)
        self.assertTrue(nodes, "no tank nodes rendered")
        for node in nodes:
            with self.subTest(node=node[:40]):
                self.assertNotIn("<button", node)
                self.assertNotIn("<a ", node)

    def test_the_hud_marks_the_current_step_rather_than_linking_to_it(self):
        """A breadcrumb whose final crumb navigates to the page you are on is
        a control that does nothing."""
        _id, raw = self._issue("architect")
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn('aria-label="Breadcrumb"', body)
        self.assertIn('aria-current="page"', body)

    def test_the_tank_scopes_to_what_the_pass_permits(self):
        """The container changes nothing about authorisation: a structural
        trade sees one node, not four with three refused."""
        _id, raw = self._issue("trade", disciplines=["structural"])
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn("RS501", body)
        self.assertNotIn("A204", body)
        self.assertIn("1 sheet(s) available", body)

    def test_an_empty_tank_says_what_is_missing(self):
        """A blank bounded box reads as a loading failure, which is a worse
        answer than "nothing here yet"."""
        # Exercised through the real page: a pass scoped to a discipline that
        # has nothing on disk.
        _id, raw = self._issue("engineer", disciplines=["landscape"])
        body = self.flask_app.test_client().get(
            f"/project/{PILOT_PROJECT_ID}?token={raw}").get_data(as_text=True)
        self.assertIn("tank-empty", body)
        self.assertIn("No sheets are available to this pass.", body)

    def test_the_multi_project_index_uses_the_same_container(self):
        source = (Path(__file__).resolve().parents[1]
                  / "templates" / "projects.html").read_text(encoding="utf-8")
        self.assertIn("components/fish_tank_container.html", source)
        self.assertIn('data-ui-ref="tank.container"', source)
        # The rich cards survive: unifying a container must not cost
        # information the node macro has no room for.
        self.assertIn("project-card-list", source)
        self.assertIn("unresolved_conflict_count", source)


class FooterPlacementTests(_ManagePanelTestCase):
    """Where the footer belongs, and - more importantly - where it must not."""

    def test_the_footer_is_on_the_public_landing_page(self):
        body = self.flask_app.test_client().get("/").get_data(as_text=True)
        self.assertIn('data-ui-ref="footer.public"', body)
        self.assertIn("ARCHIOSK Platform", body)
        # Whitespace-normalised: the legal line wraps across two source lines,
        # and asserting the rendered FORMATTING rather than the words would
        # fail on a reflow that changed nothing anyone reads.
        import re

        flat = re.sub(r"\s+", " ", body)
        self.assertIn("Confidential &amp; Project-Scoped Spatial Coordination.", flat)

    def test_the_footer_is_on_the_access_panel(self):
        body = self._architect().get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        self.assertIn('data-ui-ref="footer.public"', body)

    def test_the_footer_is_never_on_a_drawing_viewport(self):
        """A coordination desk is full-bleed on purpose: every pixel of chrome
        is a pixel of drawing somebody cannot see. Asserted against the
        TEMPLATES, because these surfaces are developer-gated and a route-level
        check would silently pass on a redirect."""
        root = Path(__file__).resolve().parents[1] / "templates"
        for name in ("nipigon_coordination.html", "calm_lake_prototype.html"):
            with self.subTest(template=name):
                source = (root / name).read_text(encoding="utf-8")
                self.assertNotIn("public_footer", source)
                self.assertNotIn("site-footer", source)

    def test_the_footer_is_never_on_an_authentication_surface(self):
        """Learned the hard way, in this session.

        The footer was added to auth_shell.html and
        tests/test_p40d1_auth_shell_isolation.py failed immediately - because
        the footer NAMES A REAL PILOT PROJECT, and CLAUDE-P40-D1 exists
        because a Product Owner screenshot once showed /login rendering
        project names. That is an authentication-boundary disclosure, not a
        styling complaint, and the shell is safe precisely because project
        markup does not EXIST in it to leak.

        Asserted here as well as there, because the two tests fail for
        different reasons: that one checks for leaked markers generally, this
        one names the specific door it came through."""
        root = Path(__file__).resolve().parents[1] / "templates"
        source = (root / "auth_shell.html").read_text(encoding="utf-8")
        self.assertNotIn('include "components/public_footer.html"', source)
        for path in ("/login", "/forgot-password"):
            with self.subTest(path=path):
                body = self.flask_app.test_client().get(path).get_data(as_text=True)
                self.assertNotIn('data-ui-ref="footer.public"', body)
                self.assertNotIn("Alstep", body)

    def test_the_sheet_route_returns_bytes_not_a_page(self):
        """The strongest form of "no footer on a drawing": the sheet endpoint
        serves the asset itself, so there is no document to put chrome in."""
        _id, raw = self._issue("architect")
        response = self._get_sheet(raw, "A204")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertNotIn("site-footer", body)
        self.assertNotIn("<footer", body)

    def test_every_footer_entry_is_a_real_route_or_plain_text(self):
        """A footer is where dead links breed, and a dead link in a product
        about evidence is a lie in the worst possible place. Anything that is
        not a resolvable route is rendered as text, never as a link."""
        import re

        body = self.flask_app.test_client().get("/").get_data(as_text=True)
        start = body.index('data-ui-ref="footer.public"')
        footer = body[start:body.index("</footer>", start)]
        hrefs = re.findall(r'href="([^"]+)"', footer)
        self.assertTrue(hrefs, "footer renders no links at all")
        for href in hrefs:
            with self.subTest(href=href):
                self.assertFalse(href.startswith("#"), "placeholder anchor")
                if href.startswith("mailto:"):
                    continue
                self.assertTrue(href.startswith("/"), href)
                self.assertNotEqual(
                    self.flask_app.test_client().get(href).status_code, 404,
                    f"footer link 404s: {href}")


# ===========================================================================
# CLAUDE-QR-PASS-01 — a pass you can hold up and someone can scan
# ===========================================================================
class QrRenderingTests(unittest.TestCase):
    """The renderer itself. No app, no database - it is a pure function."""

    URL = "https://10.0.0.177:8643/project/222109-1860-alstep-dr?token=AbC-123_xyz"

    def test_the_svg_parses_as_xml(self):
        import xml.etree.ElementTree as ET

        from services.qr_pass import render_token_qr_svg

        ET.fromstring(render_token_qr_svg(self.URL))

    def test_it_carries_no_xml_declaration_because_it_is_embedded(self):
        """A second <?xml ...?> mid-document is invalid HTML."""
        from services.qr_pass import render_token_qr_svg

        self.assertFalse(render_token_qr_svg(self.URL).lstrip().startswith("<?xml"))

    def test_nothing_is_fetched_from_anywhere(self):
        """The payload IS a live credential. Handing it to an external image
        service would mail every stakeholder pass to a company nobody chose -
        so the renderer is local, and the markup references no host but the SVG
        namespace itself."""
        from services.qr_pass import render_token_qr_svg

        svg = render_token_qr_svg(self.URL)
        stripped = svg.replace("http://www.w3.org/2000/svg", "")
        for forbidden in ("http://", "https://", "chart.googleapis", "<image", "xlink:href"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, stripped)

    def test_the_symbol_is_black_on_white_regardless_of_theme(self):
        """A scanner needs contrast, not brand. A dark-mode QR in muted greys
        is the classic way to make a code that looks correct on screen and
        reads unreliably in daylight."""
        from services.qr_pass import render_token_qr_svg

        svg = render_token_qr_svg(self.URL).lower()
        self.assertIn("#000", svg)

    def test_an_empty_target_is_refused_rather_than_encoded(self):
        """A QR of an empty string scans to nothing and looks identical to a
        working one from three feet away."""
        from services.qr_pass import render_token_qr_svg

        for bad in ("", "   ", None):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    render_token_qr_svg(bad)

    def test_the_url_builder_produces_the_exact_expected_scheme(self):
        from services.qr_pass import pass_target_url

        self.assertEqual(
            pass_target_url("https://host:8643/", "222109-1860-alstep-dr", "TOK"),
            "https://host:8643/project/222109-1860-alstep-dr?token=TOK")

    def test_remaining_duration_never_rounds_optimistically(self):
        """A pass that says 2 days and dies in 25 hours strands somebody on a
        deck, so the error is always in the safe direction."""
        from datetime import datetime, timedelta, timezone

        from services.qr_pass import remaining_duration

        now = datetime.now(timezone.utc)
        cases = {
            timedelta(hours=47): "1 day",
            timedelta(hours=25): "1 day",
            timedelta(minutes=119): "1 hour",
            timedelta(seconds=90): "1 minute",
            timedelta(seconds=-1): "expired",
        }
        for delta, expected in cases.items():
            with self.subTest(delta=str(delta)):
                self.assertEqual(remaining_duration(now + delta, now=now), expected)


class QrFlowATests(_ManagePanelTestCase):
    """Flow A — the one-time reveal, at issue time."""

    def test_issuing_a_pass_renders_a_scannable_code_beside_the_link(self):
        response = self._create(self._architect())
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('data-ui-ref="manage.access.bb-pass"', body)
        self.assertIn('data-ui-ref="manage.access.qr"', body)
        self.assertIn("Building Box (BB)", body)

    def test_the_qr_encodes_the_exact_url_that_was_shown(self):
        """The code and the copyable link must be the same credential. Two
        call sites assembling it separately is how one of them ends up
        scanning to a 403."""
        import re
        import xml.etree.ElementTree as ET

        from services.qr_pass import render_token_qr_svg

        body = self._create(self._architect()).get_data(as_text=True)
        link = re.search(r'class="pm-issued-link"[^>]*value="([^"]+)"', body).group(1)
        self.assertIn("/project/" + PILOT_PROJECT_ID + "?token=", link)

        # Re-render the same URL and compare the path data: identical input
        # must give an identical symbol.
        expected = render_token_qr_svg(link)
        shown_start = body.index('data-ui-ref="manage.access.qr"')
        shown = body[body.index("<svg", shown_start):body.index("</svg>", shown_start) + 6]
        ET.fromstring(shown)
        self.assertEqual(
            re.findall(r'd="([^"]+)"', shown), re.findall(r'd="([^"]+)"', expected))

    def test_the_scanned_url_actually_opens_the_project(self):
        """End to end: whatever the QR encodes must work when followed."""
        import re

        body = self._create(self._architect(),
                            role="trade", disciplines=["structural"]).get_data(as_text=True)
        link = re.search(r'class="pm-issued-link"[^>]*value="([^"]+)"', body).group(1)
        path = link[link.index("/project/"):]
        landed = self.flask_app.test_client().get(path)
        self.assertEqual(landed.status_code, 200)
        self.assertIn("RS501", landed.get_data(as_text=True))

    def test_the_table_offers_no_qr_for_an_existing_pass(self):
        """It cannot: only sha256(token) was ever stored. A button promising
        one would be lying about the property that makes the table safe."""
        self._create(self._architect())
        body = self._architect().get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="manage.access.qr"', body)
        self.assertIn('data-ui-ref="manage.access.rotate"', body)


class QrFlowBRotationTests(_ManagePanelTestCase):
    """Flow B — re-issue, which mints a replacement and kills the original."""

    def _issue_and_capture(self, **form):
        import re

        body = self._create(self._architect(), **form).get_data(as_text=True)
        link = re.search(r'class="pm-issued-link"[^>]*value="([^"]+)"', body).group(1)
        return re.search(r"\?token=([A-Za-z0-9_\-]+)", link).group(1)

    def test_rotating_invalidates_the_previous_credential_immediately(self):
        from services import project_rbac

        old_raw = self._issue_and_capture(role="trade", disciplines=["structural"])
        self.assertEqual(self._get_sheet(old_raw, "RS501").status_code, 200)

        with self.flask_app.app_context():
            token_id = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"].id
        response = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate")
        self.assertEqual(response.status_code, 200)

        # The old link is dead on the very next request.
        self.assertEqual(self._get_sheet(old_raw, "RS501").status_code, 403)

    def test_the_replacement_works_and_keeps_the_same_scope(self):
        """Rotation is a new CREDENTIAL, never a new GRANT - anything else
        would make "re-issue" a quiet way to widen access."""
        import re

        from services import project_rbac

        self._issue_and_capture(role="trade", disciplines=["structural"])
        with self.flask_app.app_context():
            token_id = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"].id
        body = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate").get_data(as_text=True)
        new_raw = re.search(r"\?token=([A-Za-z0-9_\-]+)", body).group(1)

        self.assertEqual(self._get_sheet(new_raw, "RS501").status_code, 200)
        self.assertEqual(self._get_sheet(new_raw, "A204").status_code, 403)

    def test_the_replacement_does_not_extend_the_expiry(self):
        from datetime import timezone

        from services import project_rbac

        self._issue_and_capture(role="trade", disciplines=["structural"])
        with self.flask_app.app_context():
            before = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"]
            original_expiry = before.expires_at
            token_id = before.id
        self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate")
        with self.flask_app.app_context():
            after = [e for e in project_rbac.list_all_tokens(PILOT_PROJECT_ID)
                     if e["status"] == "active"][0]["token"]
            self.assertEqual(after.expires_at, original_expiry)

    def test_a_revoked_pass_cannot_produce_a_scannable_code(self):
        from services import project_rbac

        self._issue_and_capture()
        with self.flask_app.app_context():
            token_id = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"].id
            project_rbac.revoke_token(token_id, actor="architect_user")
        response = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('data-ui-ref="manage.access.qr"',
                         response.get_data(as_text=True))

    def test_an_expired_pass_cannot_be_rotated_into_a_live_one(self):
        """Rotating an expired pass would silently extend it. Reissuing is the
        architect's decision on the form, not something rotation does on their
        behalf."""
        from services import project_rbac

        token_id, _raw = self._issue_expired("architect")
        response = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('data-ui-ref="manage.access.qr"',
                         response.get_data(as_text=True))

    def test_a_pass_from_another_project_cannot_be_rotated_here(self):
        from services import project_rbac

        with self.flask_app.app_context():
            foreign, _ = project_rbac.issue_token(
                "some-other-project", "architect", label="foreign",
                actor="someone", ttl_seconds=3600)
            foreign_id = foreign.id
        response = self._architect().post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{foreign_id}/rotate")
        self.assertEqual(response.status_code, 403)

    def test_rotation_requires_the_same_session_gate_as_everything_else(self):
        from services import project_rbac

        self._issue_and_capture()
        with self.flask_app.app_context():
            token_id = project_rbac.list_all_tokens(PILOT_PROJECT_ID)[0]["token"].id
        stranger = self._session("nobody", 99, "read_only")
        self.assertEqual(stranger.post(
            f"/project/{PILOT_PROJECT_ID}/manage/access/{token_id}/rotate").status_code, 403)


# ===========================================================================
# CLAUDE-HELP-CENTER-01 — the guides, and what the desks stopped saying
# ===========================================================================
class HelpCenterTests(_ManagePanelTestCase):
    def test_every_guide_renders(self):
        client = self._architect()
        for guide in ("field-access-passes", "spatial-coordination",
                      "building-box-meetings"):
            with self.subTest(guide=guide):
                self.assertEqual(client.get(f"/help/{guide}").status_code, 200)
        self.assertEqual(client.get("/help").status_code, 200)

    def test_the_guide_list_is_a_closed_set(self):
        """A help route that renders any template name it is handed is a
        template-injection surface, and "guides" is not a directory anyone
        should be able to walk."""
        client = self._architect()
        for attempt in ("nope", "../base", "..%2fbase", "index"):
            with self.subTest(attempt=attempt):
                self.assertIn(client.get(f"/help/{attempt}").status_code, (404, 308))

    def test_help_is_authenticated_because_it_names_real_surfaces(self):
        """These guides name project surfaces and role scopes. The sign-in page
        is deliberately isolated from exactly that content (CLAUDE-P40-D1), so
        the guides sit behind the session boundary too."""
        self.assertIn(self.flask_app.test_client().get("/help").status_code,
                      (302, 401, 403))

    def test_the_index_uses_the_shared_container(self):
        body = self._architect().get("/help").get_data(as_text=True)
        self.assertIn('data-ui-ref="tank.container"', body)
        self.assertIn('data-ui-ref="help.guide"', body)

    def test_every_help_link_on_the_access_panel_resolves(self):
        """Zero dead hrefs: each [?] is fetched and must not 404."""
        import re

        client = self._architect()
        body = client.get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        links = re.findall(r'class="pm-help"\s+href="([^"]+)"', body)
        self.assertTrue(links, "no contextual help links rendered")
        for href in links:
            with self.subTest(href=href):
                self.assertFalse(href.startswith("#"), "bare anchor, no route")
                self.assertNotEqual(client.get(href.split("#")[0]).status_code, 404)

    def test_the_desk_no_longer_carries_the_long_explanations(self):
        """The paragraphs moved; the panel keeps controls and micro-copy."""
        body = self._architect().get(
            f"/project/{PILOT_PROJECT_ID}/manage/access").get_data(as_text=True)
        for moved in ("there is no password and", "not something to resolve later",
                      "should still work on Jan 21"):
            with self.subTest(phrase=moved):
                self.assertNotIn(moved, body)

    def test_the_one_time_warning_did_NOT_move(self):
        """Not an explanation - the only warning before an unrecoverable
        credential disappears. Trimming this one to look clean costs somebody
        real work."""
        body = self._create(self._architect()).get_data(as_text=True)
        self.assertIn("Shown <b>once</b>", body)
        self.assertIn("Re-issue", body)

    def test_the_building_box_guide_does_not_describe_unbuilt_sync(self):
        """The brief asked for step-by-step presenter/follower, Lead Room,
        Free Roam and LERP tracking. None of it exists - there is no
        routes/bb_sync.py and no static/js/bb_sync_engine.js - and the relay it
        needs fails this project's own dependency check on two settled
        constraints.

        Documenting it in the present tense would put a procedure in front of
        somebody in a site trailer for a feature that will not respond. The
        guide names it as NOT BUILT instead, and this asserts that it keeps
        doing so."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "routes" / "bb_sync.py").exists())
        self.assertFalse((root / "static" / "js" / "bb_sync_engine.js").exists())

        body = self._architect().get(
            "/help/building-box-meetings").get_data(as_text=True)
        self.assertIn("not built", body.lower())
        self.assertIn("does not exist in this product", body)

    def test_the_guides_describe_only_capabilities_that_exist(self):
        """Spot-check: the field-access guide's claims are things the suite
        elsewhere proves, not aspirations."""
        body = self._architect().get(
            "/help/field-access-passes").get_data(as_text=True)
        self.assertIn("Reads no drawings at all", body)   # platform_admin
        self.assertIn("shown once", body.lower())         # hash-only storage
        self.assertIn("run out of fuel", body)            # safe landing


if __name__ == "__main__":
    unittest.main()
