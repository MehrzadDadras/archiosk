"""
CLAUDE-STORAGE-BRIDGE-03 - the three endpoints, end to end, over real HTTP.

WHAT THIS ADDS OVER THE PROTOCOL TESTS

test_storage_bridge_01/02 prove the protocol and its trust boundary against the
objects directly. This drives the same protocol through the Flask stack, because
several things can only be wrong at that layer: a missing CSRF exemption, a
credential accepted from a query string, a refusal rendered as an HTML page to a
machine, a route that resolves a project from anything other than the token.

THE CSRF EXEMPTION IS ASSERTED AT SOURCE LEVEL, DELIBERATELY

config.py sets WTF_CSRF_ENABLED = False under testing. So a missing exemption
would pass every test here and fail only in production, on the first real POST
an agent ever made. Reading app.py is the only way to catch that from a test
suite, and it is worth the ugliness.

WHAT IS DELIBERATELY NOT PROVEN HERE

That a governed Source gets created. Nothing in this path writes one - wiring
the bridge into ingestion must go through the existing Reconcile machinery, and
is a separate change. Asserting it here would be asserting something that has
not been built.

tests/fixtures/wd_nas_bridge/oracle/ remains unread and untracked.
"""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.storage_agent_access import (
    enrol_agent, reset_bridges_for_testing, revoke_agent,
)

_ROOT = Path(__file__).resolve().parent.parent

_A101 = b"%PDF-1.4 project A floor plan bytes"
_B201 = b"project B section - must never cross"


def _entry(path, payload):
    return {"relative_path": path, "size_bytes": len(payload),
            "mtime_iso": "2026-08-27T12:00:00+00:00",
            "sha256": hashlib.sha256(payload).hexdigest()}


class _BridgeApp(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile

        import app as app_module
        from models import db
        from services.case_workspace import CaseWorkspaceStore

        self.app = app_module.create_app("testing")
        # CLAUDE-STORAGE-BRIDGE-07: the manifest now lands on the PROJECT
        # record, so the project has to exist. The in-memory bridge never
        # checked, which is exactly the sort of thing durable state makes
        # honest - a manifest for a project that does not exist was always
        # nonsense, it just had nowhere to be noticed.
        self.registry = tempfile.mkdtemp(prefix="bridge-endpoints-")
        self.addCleanup(shutil.rmtree, self.registry, ignore_errors=True)
        self.app.config["REGISTRY_STORE_PATH"] = self.registry
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        self.addCleanup(reset_bridges_for_testing, self.app)
        db.create_all()
        store = CaseWorkspaceStore(self.registry)
        store.get_or_create("project-a")
        store.get_or_create("project-b")
        _, self.token_a = enrol_agent("project-a", "ex4100-office", actor="architect")
        _, self.token_b = enrol_agent("project-b", "ex4100-site", actor="architect")
        self.client = self.app.test_client()

    def _auth(self, token):
        return {"Authorization": "Bearer %s" % token}

    def push_manifest(self, token, entries):
        return self.client.post("/api/bridge/manifest", json={"entries": entries},
                                headers=self._auth(token))

    def poll(self, token):
        return self.client.get("/api/bridge/pending", headers=self._auth(token))

    def deliver(self, token, request_id, payload):
        headers = self._auth(token)
        headers["X-Bridge-Request-Id"] = request_id
        return self.client.post("/api/bridge/deliver", data=payload, headers=headers)


class TheAgentCanCompleteAFullExchange(_BridgeApp):
    def test_a_manifest_is_accepted_and_digested(self):
        response = self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["accepted_entries"], 1)
        self.assertEqual(len(body["manifest_digest"]), 64)

    def test_an_empty_poll_is_a_valid_answer(self):
        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        response = self.poll(self.token_a)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["requests"], [])

    def test_request_poll_deliver_round_trip(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import request_bytes

        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)

        polled = self.poll(self.token_a).get_json()["requests"]
        self.assertEqual(len(polled), 1)
        self.assertEqual(polled[0]["relative_path"], "drawings/A-101.pdf")
        self.assertEqual(polled[0]["purpose"], "extract_text")

        delivered = self.deliver(self.token_a, polled[0]["id"], _A101)
        self.assertEqual(delivered.status_code, 200)
        self.assertEqual(delivered.get_json()["bytes_received"], len(_A101))

        queue = BridgeQueueStore(self.registry)
        _record, payload = queue.consume(polled[0]["id"])
        self.assertEqual(payload, _A101)
        self.assertFalse(queue.holds_payload(polled[0]["id"]))

    def test_the_agents_last_contact_is_recorded_for_a_human(self):
        from models import StorageAgentEnrolment

        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        row = StorageAgentEnrolment.query.filter_by(project_id="project-a").first()
        self.assertIsNotNone(row.last_seen_at)


class CredentialsAreHandledSafely(_BridgeApp):
    def test_no_token_is_refused_401(self):
        response = self.client.post("/api/bridge/manifest", json={"entries": []})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "enrolment_not_authorised")

    def test_a_wrong_token_is_refused_401(self):
        response = self.push_manifest("not-a-real-token", [])
        self.assertEqual(response.status_code, 401)

    def test_a_token_in_the_query_string_does_not_work(self):
        # Query strings land in access logs, proxy logs and history. A
        # credential that survives in a log is one that leaks later.
        response = self.client.get("/api/bridge/pending?token=%s" % self.token_a)
        self.assertEqual(response.status_code, 401)

    def test_a_revoked_agent_is_refused_and_told_nothing_extra(self):
        revoke_agent("project-a", "ex4100-office", actor="architect")
        response = self.poll(self.token_a)
        self.assertEqual(response.status_code, 401)
        # Identical to an unknown token: distinguishing them would confirm a
        # project has an agent to someone holding no valid credential.
        unknown = self.client.get("/api/bridge/pending",
                                  headers=self._auth("definitely-not-real"))
        self.assertEqual(response.get_json(), unknown.get_json())

    def test_an_expired_enrolment_is_refused(self):
        from models import StorageAgentEnrolment, db

        row = StorageAgentEnrolment.query.filter_by(project_id="project-a").first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        self.assertEqual(self.poll(self.token_a).status_code, 401)

    def test_only_the_hash_is_in_the_database(self):
        from models import StorageAgentEnrolment

        row = StorageAgentEnrolment.query.filter_by(project_id="project-a").first()
        self.assertEqual(row.token_hash,
                         hashlib.sha256(self.token_a.encode()).hexdigest())
        for value in vars(row).values():
            if isinstance(value, str):
                self.assertNotEqual(value, self.token_a)

    def test_the_model_has_no_column_that_could_hold_a_nas_credential(self):
        from models import StorageAgentEnrolment

        columns = {c.name for c in StorageAgentEnrolment.__table__.columns}
        for forbidden in ("password", "secret", "nas_user", "share_password",
                          "smb_password", "token"):
            self.assertNotIn(forbidden, columns)
        self.assertIn("token_hash", columns)


class ProjectIsolationHoldsOverHttp(_BridgeApp):
    def test_one_agents_manifest_is_invisible_to_the_other(self):
        from services.storage_agent_access import manifest_entries_for

        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        self.push_manifest(self.token_b, [_entry("drawings/B-201.pdf", _B201)])
        paths_a = [e.relative_path for e in manifest_entries_for("project-a", app=self.app)]
        paths_b = [e.relative_path for e in manifest_entries_for("project-b", app=self.app)]
        self.assertEqual(paths_a, ["drawings/A-101.pdf"])
        self.assertEqual(paths_b, ["drawings/B-201.pdf"])

    def test_no_endpoint_accepts_a_project_id_from_the_caller(self):
        # The project comes from the token or from nowhere. A project_id
        # parameter anywhere here would be a second, weaker route in.
        source = (_ROOT / "routes" / "storage_bridge.py").read_text(encoding="utf-8")
        for smell in ('args.get("project_id"', "args.get('project_id'",
                      '<project_id>', 'json.get("project_id"'):
            self.assertNotIn(smell, source)

    def test_delivering_against_another_projects_request_id_fails(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import request_bytes

        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        self.push_manifest(self.token_b, [_entry("drawings/B-201.pdf", _B201)])
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        stolen = self.poll(self.token_a).get_json()["requests"][0]["id"]
        # Agent B presents A's request id. The queue is shared, so this is the
        # test that scoping is enforced rather than merely implied by storage.
        response = self.deliver(self.token_b, stolen, _A101)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(BridgeQueueStore(self.registry).holds_payload(stolen))


class MalformedInputIsRefusedOnItsMerits(_BridgeApp):
    def test_a_non_list_manifest_is_400(self):
        response = self.client.post("/api/bridge/manifest",
                                    json={"entries": "everything"},
                                    headers=self._auth(self.token_a))
        self.assertEqual(response.status_code, 400)

    def test_a_manifest_entry_missing_a_field_is_400(self):
        response = self.push_manifest(self.token_a, [{"relative_path": "a.pdf"}])
        self.assertEqual(response.status_code, 400)

    def test_delivery_without_a_request_id_is_400(self):
        response = self.client.post("/api/bridge/deliver", data=b"x",
                                    headers=self._auth(self.token_a))
        self.assertEqual(response.status_code, 400)

    def test_an_unknown_request_id_is_422_not_500(self):
        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        response = self.deliver(self.token_a, "req-9999", _A101)
        self.assertEqual(response.status_code, 422)

    def test_bytes_that_do_not_match_the_manifest_are_422(self):
        from services.storage_agent_access import request_bytes

        self.push_manifest(self.token_a, [_entry("drawings/A-101.pdf", _A101)])
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        request_id = self.poll(self.token_a).get_json()["requests"][0]["id"]
        response = self.deliver(self.token_a, request_id, b"tampered")
        self.assertEqual(response.status_code, 422)
        self.assertIn("hash", response.get_json()["message"])

    def test_a_traversal_path_in_a_manifest_is_refused_and_never_stored(self):  # noqa: D401
        """422, not 400: the JSON was well formed and the CONTENT was refused.

        The refusal comes from normalize_relative_reference - the containment
        rule services/external_source.py already owns - so a compromised or
        buggy agent cannot smuggle `..` into ARCHIOSK's view of the corpus by
        way of a manifest. The property that matters is the second assertion:
        whatever the status code, nothing traversing upward is ever recorded.
        """
        from services.storage_agent_access import manifest_entries_for

        response = self.push_manifest(
            self.token_a, [_entry("../../etc/passwd", _A101)])
        self.assertEqual(response.status_code, 422)
        self.assertIn("traverse", response.get_json()["message"])
        self.assertEqual(manifest_entries_for("project-a", app=self.app), [])

    def test_an_absolute_path_in_a_manifest_is_also_refused_or_neutralised(self):
        from services.storage_agent_access import manifest_entries_for

        self.push_manifest(self.token_a, [_entry("/etc/shadow", _A101)])
        for entry in manifest_entries_for("project-a", app=self.app):
            self.assertFalse(entry.relative_path.startswith("/"))


class TheCsrfExemptionExistsAndIsNarrow(unittest.TestCase):
    """Asserted from source: testing config disables CSRF, so behaviour cannot
    show this and production is where it would first bite."""

    def test_the_bridge_blueprint_is_exempt(self):
        source = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("csrf.exempt(storage_bridge_bp)", source)

    def test_csrf_is_still_enabled_globally(self):
        source = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("csrf.init_app(app)", source)

    def test_only_bearer_token_blueprints_are_exempt(self):
        """Was: "only the TWO machine blueprints". The list is now four, and
        the change is deliberate rather than drift.

        CLAUDE-RBAC-TOKENS-01/02 added `project_assets_bp` and
        `project_query_bp`. Both authenticate by BEARER TOKEN in a request
        header, never by the session cookie - so the attack CSRF exists to
        prevent does not apply to them: a browser will not attach an
        X-Project-Token to a cross-site request, and an attacker who already
        holds the token does not need the victim's browser at all.

        What this test protects is NARROWNESS, not the number two. It is still
        an exact allow-list, so a session-authenticated blueprint appearing
        here fails immediately - which is the property worth keeping, and the
        reason this is asserted by exact equality rather than by a count."""
        source = (_ROOT / "app.py").read_text(encoding="utf-8")
        exempted = [line.strip() for line in source.splitlines()
                    if "csrf.exempt(" in line]
        self.assertEqual(sorted(exempted), [
            "csrf.exempt(api_bp)",
            "csrf.exempt(project_assets_bp)",
            "csrf.exempt(project_query_bp)",
            "csrf.exempt(storage_bridge_bp)",
        ])


class TheMigrationChainIsIntact(unittest.TestCase):
    def test_the_new_revision_follows_the_previous_head(self):
        migration = (_ROOT / "migrations" / "versions"
                     / "b41ce7a9d305_storage_agent_enrolments.py").read_text(encoding="utf-8")
        self.assertIn("revision = 'b41ce7a9d305'", migration)
        self.assertIn("down_revision = 'a3f1c07d92b4'", migration)

    def test_exactly_one_revision_claims_to_be_head(self):
        versions = (_ROOT / "migrations" / "versions")
        revisions, parents = set(), set()
        for path in versions.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("revision = "):
                    revisions.add(line.split("=", 1)[1].strip().strip("'\""))
                if line.startswith("down_revision = "):
                    parents.add(line.split("=", 1)[1].strip().strip("'\""))
        heads = revisions - parents
        self.assertEqual(len(heads), 1, "migration chain has forked: %s" % heads)


if __name__ == "__main__":
    unittest.main()
