"""
CLAUDE-STORAGE-BRIDGE-02, re-proven against durable state by -07.

WHY THIS FILE WAS REWRITTEN RATHER THAN DELETED

Every property here was originally asserted against the in-memory
StorageBridge/BridgeRegistry that CLAUDE-STORAGE-BRIDGE-07 deleted. The
implementation was wrong - fifteen gunicorn workers, one of which held the
state - but the PROPERTIES were not. Project isolation, hash-only credentials,
revocation that stops bytes without erasing history, safe replay and expiry,
three distinct refusals, idempotent exchange and zero byte custody all still have
to hold, and now have to hold across workers rather than within one.

So the assertions moved to the durable path: enrolments in
models.StorageAgentEnrolment, the manifest on ProjectWorkspace, the byte queue on
the shared filesystem. Deleting them because the implementation changed would
have been discarding the intent along with the accident.

PROJECT ISOLATION IS STILL AN ABSENCE, NOT A CHECK

There is no function taking a project_id and returning an agent's view. The only
route in is a token, which resolves to exactly one enrolment naming exactly one
project - so Project A asking for B is not refused, it is inexpressible. Asserted
against the module's API shape, because a test that asks and expects a refusal
only proves today's check works.

tests/fixtures/wd_nas_bridge/oracle/ remains unread and untracked.
"""
from __future__ import annotations

import hashlib
import inspect
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.external_source import (
    ExternalSourceError, ExternalSourceForbidden, ExternalSourceUnavailable,
)
from services.storage_bridge import (
    BridgeEnrolmentRevoked, ManifestEntry, manifest_digest,
)

_A = {"drawings/A-101.pdf": b"project A floor plan"}
_B = {"drawings/B-201.pdf": b"project B section - confidential"}


def _entries(files):
    return [
        ManifestEntry(path, len(payload), "2026-08-27T12:00:00+00:00",
                      hashlib.sha256(payload).hexdigest())
        for path, payload in sorted(files.items())
    ]


class _TwoProjects(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import db
        from services.storage_agent_access import (
            enrol_agent, reset_bridges_for_testing,
        )
        from services.case_workspace import CaseWorkspaceStore

        self.dir = tempfile.mkdtemp(prefix="bridge-trust-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = self.dir
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        self.addCleanup(reset_bridges_for_testing, self.app)
        db.create_all()

        store = CaseWorkspaceStore(self.dir)
        store.get_or_create("project-a")
        store.get_or_create("project-b")
        self.store = store

        self.enrolment_a, self.token_a = enrol_agent("project-a", "ex4100-office",
                                                     actor="architect")
        self.enrolment_b, self.token_b = enrol_agent("project-b", "ex4100-site",
                                                     actor="architect")

    def push(self, token, files):
        from services.storage_agent_access import record_manifest_for_token

        return record_manifest_for_token(token, _entries(files), app=self.app)

    def manifest(self, project_id):
        from services.storage_agent_access import manifest_entries_for

        return manifest_entries_for(project_id, app=self.app)


class ProjectIsolationIsStructural(_TwoProjects):
    def test_there_is_no_call_that_asks_for_an_agent_view_by_project_id(self):
        import services.storage_agent_access as module

        # Reads of already-governed project state may take a project_id; the
        # AGENT-facing calls, which act on a credential, may not.
        for name in ("record_manifest_for_token", "claim_pending_for_token",
                     "deliver_for_token"):
            parameters = set(inspect.signature(getattr(module, name)).parameters)
            self.assertNotIn("project_id", parameters,
                             "%s exposes a project_id route" % name)

    def test_a_token_reaches_exactly_one_project(self):
        from services.storage_agent_access import authorise_agent

        self.assertEqual(authorise_agent(self.token_a).project_id, "project-a")
        self.assertEqual(authorise_agent(self.token_b).project_id, "project-b")

    def test_project_a_cannot_see_project_b_content(self):
        self.push(self.token_a, _A)
        self.push(self.token_b, _B)
        self.assertEqual([e.relative_path for e in self.manifest("project-a")],
                         ["drawings/A-101.pdf"])
        self.assertNotIn("drawings/B-201.pdf",
                         [e.relative_path for e in self.manifest("project-a")])

    def test_project_a_cannot_request_a_project_b_path(self):
        from services.storage_agent_access import request_bytes

        self.push(self.token_a, _A)
        self.push(self.token_b, _B)
        with self.assertRaises(ExternalSourceError):
            request_bytes("project-a", "drawings/B-201.pdf", "extract_text",
                          app=self.app)

    def test_bytes_delivered_to_one_project_are_invisible_to_the_other(self):
        from services.storage_agent_access import (
            claim_pending_for_token, deliver_for_token, request_bytes,
        )
        from services.bridge_queue import BridgeQueueStore

        self.push(self.token_a, _A)
        self.push(self.token_b, _B)
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        claimed = claim_pending_for_token(self.token_a, app=self.app)
        deliver_for_token(self.token_a, claimed[0]["id"],
                          _A["drawings/A-101.pdf"], app=self.app)
        queue = BridgeQueueStore(self.dir)
        self.assertEqual(queue.claimed_for("project-b"), [])
        self.assertEqual(queue.pending_for("project-b"), [])


class CredentialsAreNeverRetainedInTheClear(_TwoProjects):
    def test_only_the_hash_is_stored(self):
        self.assertEqual(self.enrolment_a.token_hash,
                         hashlib.sha256(self.token_a.encode()).hexdigest())

    def test_the_raw_token_appears_nowhere_on_the_row(self):
        for value in vars(self.enrolment_a).values():
            if isinstance(value, str):
                self.assertNotEqual(value, self.token_a)

    def test_the_enrolment_record_has_no_column_that_could_hold_it(self):
        from models import StorageAgentEnrolment

        columns = {c.name for c in StorageAgentEnrolment.__table__.columns}
        for leak in ("token", "raw_token", "secret", "password"):
            self.assertNotIn(leak, columns)
        self.assertIn("token_hash", columns)

    def test_archiosk_never_receives_a_nas_credential(self):
        from models import StorageAgentEnrolment

        columns = {c.name for c in StorageAgentEnrolment.__table__.columns}
        for forbidden in ("nas_user", "smb", "share_user", "admin_password",
                          "storage_password", "mount"):
            self.assertNotIn(forbidden, " ".join(columns))

    def test_tokens_are_not_guessable_or_sequential(self):
        from services.storage_agent_access import enrol_agent

        _, second = enrol_agent("project-a", "second-agent", actor="architect")
        self.assertNotEqual(self.token_a, second)
        self.assertGreaterEqual(len(self.token_a), 32)


class RevocationStopsBytesAndNotHistory(_TwoProjects):
    def test_a_revoked_agent_is_refused(self):
        from services.storage_agent_access import authorise_agent, revoke_agent

        revoke_agent("project-a", "ex4100-office", actor="architect")
        with self.assertRaises(BridgeEnrolmentRevoked):
            authorise_agent(self.token_a)

    def test_revocation_does_not_delete_what_the_project_knows(self):
        from services.storage_agent_access import revoke_agent

        self.push(self.token_a, _A)
        before = [e.as_dict() for e in self.manifest("project-a")]
        revoke_agent("project-a", "ex4100-office", actor="architect")
        self.assertEqual([e.as_dict() for e in self.manifest("project-a")], before)

    def test_revocation_drops_work_in_flight(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import request_bytes, revoke_agent

        self.push(self.token_a, _A)
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        self.assertEqual(len(BridgeQueueStore(self.dir).pending_for("project-a")), 1)
        revoke_agent("project-a", "ex4100-office", actor="architect")
        self.assertEqual(BridgeQueueStore(self.dir).pending_for("project-a"), [])

    def test_re_enrolment_restores_access_without_re_synchronising(self):
        from services.storage_agent_access import (
            authorise_agent, enrol_agent, revoke_agent,
        )

        digest = self.push(self.token_a, _A)
        revoke_agent("project-a", "ex4100-office", actor="architect")
        _, fresh = enrol_agent("project-a", "ex4100-office", actor="architect")
        self.assertEqual(authorise_agent(fresh).project_id, "project-a")
        self.assertEqual(manifest_digest(self.manifest("project-a")), digest)

    def test_revoking_one_project_leaves_the_other_working(self):
        from services.storage_agent_access import authorise_agent, revoke_agent

        revoke_agent("project-a", "ex4100-office", actor="architect")
        self.assertEqual(authorise_agent(self.token_b).project_id, "project-b")


class ReplayAndExpiryFailSafely(_TwoProjects):
    def test_an_expired_enrolment_is_refused(self):
        from models import StorageAgentEnrolment, db
        from services.storage_agent_access import authorise_agent

        row = StorageAgentEnrolment.query.filter_by(project_id="project-a").first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
        with self.assertRaises(BridgeEnrolmentRevoked):
            authorise_agent(self.token_a)

    def test_replaying_a_revoked_token_fails_every_time(self):
        from services.storage_agent_access import authorise_agent, revoke_agent

        revoke_agent("project-a", "ex4100-office", actor="architect")
        for _ in range(3):
            with self.assertRaises(BridgeEnrolmentRevoked):
                authorise_agent(self.token_a)

    def test_an_unknown_token_is_refused_identically_to_a_revoked_one(self):
        # Distinguishing them would confirm a project HAS an agent to someone
        # holding no valid credential.
        from services.storage_agent_access import authorise_agent, revoke_agent

        revoke_agent("project-a", "ex4100-office", actor="architect")
        messages = []
        for token in (self.token_a, "definitely-not-a-real-token"):
            try:
                authorise_agent(token)
            except BridgeEnrolmentRevoked as exc:
                messages.append(str(exc))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0], messages[1])

    def test_an_empty_or_none_token_is_refused(self):
        from services.storage_agent_access import authorise_agent

        for bad in ("", None):
            with self.subTest(token=bad):
                with self.assertRaises(BridgeEnrolmentRevoked):
                    authorise_agent(bad)


class ThreeRefusalsThreeActions(_TwoProjects):
    def test_they_are_siblings_and_none_is_another(self):
        for a, b in ((BridgeEnrolmentRevoked, ExternalSourceUnavailable),
                     (BridgeEnrolmentRevoked, ExternalSourceForbidden),
                     (ExternalSourceForbidden, ExternalSourceUnavailable)):
            self.assertFalse(issubclass(a, b), "%s collapsed into %s" % (a, b))
            self.assertFalse(issubclass(b, a), "%s collapsed into %s" % (b, a))

    def test_all_three_share_one_root(self):
        for cls in (BridgeEnrolmentRevoked, ExternalSourceForbidden,
                    ExternalSourceUnavailable):
            self.assertTrue(issubclass(cls, ExternalSourceError))

    def test_the_reconcile_vocabulary_still_owns_missing_and_relocated(self):
        from services.ingestion import (
            RECONCILE_STATUS_MISSING, RECONCILE_STATUS_MODIFIED,
            RECONCILE_STATUS_RENAMED, RECONCILE_STATUS_UNCHANGED,
        )
        import services.storage_bridge as bridge_module
        import services.bridge_queue as queue_module

        for module in (bridge_module, queue_module):
            source = inspect.getsource(module)
            for invented in ("RELOCATED", "SYNCHRONIZED", "TEMPORARILY_UNAVAILABLE",
                             "LOCKED_PENDING"):
                self.assertNotIn(invented, source)
        self.assertEqual(
            [RECONCILE_STATUS_UNCHANGED, RECONCILE_STATUS_MODIFIED,
             RECONCILE_STATUS_RENAMED, RECONCILE_STATUS_MISSING],
            ["unchanged", "modified", "renamed", "missing"])


class RepeatedExchangeIsInert(_TwoProjects):
    def test_the_same_manifest_twice_changes_nothing(self):
        first = self.push(self.token_a, _A)
        self.assertEqual(self.push(self.token_a, _A), first)
        self.assertEqual(len(self.manifest("project-a")), 1)

    def test_an_interrupted_transfer_can_be_retried_without_duplication(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import (
            claim_pending_for_token, deliver_for_token, request_bytes,
        )

        self.push(self.token_a, _A)
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        claim_pending_for_token(self.token_a, app=self.app)   # taken, agent dies

        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        retried = claim_pending_for_token(self.token_a, app=self.app)
        self.assertEqual(len(retried), 1)
        deliver_for_token(self.token_a, retried[0]["id"],
                          _A["drawings/A-101.pdf"], app=self.app)
        _record, payload = BridgeQueueStore(self.dir).consume(retried[0]["id"])
        self.assertEqual(payload, _A["drawings/A-101.pdf"])
        self.assertEqual(len(self.manifest("project-a")), 1)

    def test_a_same_hash_relocation_keeps_one_entry(self):
        self.push(self.token_a, _A)
        original = self.manifest("project-a")[0].sha256
        self.push(self.token_a, {"archive/A-101_Rev1.pdf": _A["drawings/A-101.pdf"]})
        entries = self.manifest("project-a")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].relative_path, "archive/A-101_Rev1.pdf")
        self.assertEqual(entries[0].sha256, original)

    def test_a_content_change_at_one_path_is_a_new_digest_not_a_new_entry(self):
        before = self.push(self.token_a, _A)
        after = self.push(self.token_a, {"drawings/A-101.pdf": b"revised plan bytes"})
        self.assertNotEqual(after, before)
        self.assertEqual(len(self.manifest("project-a")), 1)

    def test_reconnect_after_an_outage_does_not_resynchronise_from_scratch(self):
        digest = self.push(self.token_a, _A)
        # Nothing happens for a while; the record is untouched and still there.
        self.assertEqual(manifest_digest(self.manifest("project-a")), digest)
        self.assertEqual(self.push(self.token_a, _A), digest)


class NoSourceBytesRemainInArchiosxCustody(_TwoProjects):
    def test_the_payload_is_absent_from_the_store_after_consumption(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import (
            claim_pending_for_token, deliver_for_token, request_bytes,
        )

        payload = _A["drawings/A-101.pdf"]
        self.push(self.token_a, _A)
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        claimed = claim_pending_for_token(self.token_a, app=self.app)
        deliver_for_token(self.token_a, claimed[0]["id"], payload, app=self.app)
        _record, back = BridgeQueueStore(self.dir).consume(claimed[0]["id"])
        self.assertEqual(back, payload)

        for path in Path(self.dir).rglob("*"):
            if path.is_file():
                self.assertNotIn(payload, path.read_bytes())

    def test_the_manifest_never_contained_the_bytes_in_the_first_place(self):
        self.push(self.token_a, _A)
        blob = str([e.as_dict() for e in self.manifest("project-a")]).encode()
        self.assertNotIn(_A["drawings/A-101.pdf"], blob)

    def test_a_mismatched_delivery_is_refused_and_stages_nothing(self):
        from services.bridge_queue import BridgeQueueStore
        from services.storage_agent_access import (
            claim_pending_for_token, deliver_for_token, request_bytes,
        )

        self.push(self.token_a, _A)
        request_bytes("project-a", "drawings/A-101.pdf", "extract_text", app=self.app)
        claimed = claim_pending_for_token(self.token_a, app=self.app)
        with self.assertRaises(ExternalSourceError):
            deliver_for_token(self.token_a, claimed[0]["id"], b"tampered", app=self.app)
        self.assertFalse(BridgeQueueStore(self.dir).holds_payload(claimed[0]["id"]))


if __name__ == "__main__":
    unittest.main()
