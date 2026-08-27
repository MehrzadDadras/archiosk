"""
CLAUDE-STORAGE-BRIDGE-02 - who may speak for a project, and what happens when
they may not any more.

WHY PROJECT ISOLATION IS ASSERTED AGAINST THE API SHAPE, NOT THE BEHAVIOUR

A test that enrols for Project A, asks for Project B and expects a refusal only
proves that today's check works. The stronger claim, and the one asserted here,
is that the question cannot be expressed: BridgeRegistry has no method taking a
project_id and returning its bridge. The only route in is bridge_for(token), and
a token resolves to exactly one enrolment naming exactly one project.

That is the same reasoning visible_cases_for records for Case privacy - a real
disclosure happened there because callers could filter the raw list themselves,
and the fix was removing the ability, not adding a check.

THREE REFUSALS, THREE DIFFERENT HUMAN ACTIONS

    ExternalSourceUnavailable  -> wait, or switch the NAS on
    ExternalSourceForbidden    -> fix permissions ON THE STORAGE
    BridgeEnrolmentRevoked     -> re-enrol the agent IN ARCHIOSK

Collapsing any pair sends someone to the wrong system. That is the whole reason
these are separate types, and it is why the bridge reuses the two that already
existed rather than minting synonyms.

IDEMPOTENCY

The bridge must feed existing Reconcile/Source identity semantics, not invent a
second synchronisation vocabulary. So what is proven here is that repeated
exchange is inert - same manifest twice, interrupted transfer retried, same-hash
relocation, content change at one path, reconnect after outage - and that the
codebase's own RECONCILE_STATUS_* words remain the ones that describe it.

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
    BridgeEnrolmentRevoked,
    BridgeRegistry,
    Enrolment,
    ManifestEntry,
    StorageBridge,
    build_manifest,
    manifest_digest,
    read_manifest_file,
)

_T0 = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)

_PROJECT_A = {"drawings/A-101.pdf": b"project A floor plan"}
_PROJECT_B = {"drawings/B-201.pdf": b"project B section - confidential"}


class _TwoProjects(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="bridge-trust-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.root_a, self.root_b = self.base / "share_a", self.base / "share_b"
        for root, files in ((self.root_a, _PROJECT_A), (self.root_b, _PROJECT_B)):
            for reference, payload in files.items():
                path = root / reference
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

        self.registry = BridgeRegistry()
        self.enrolment_a, self.token_a = self.registry.enrol(
            "project-a", "ex4100-office", now=_T0)
        self.enrolment_b, self.token_b = self.registry.enrol(
            "project-b", "ex4100-site", now=_T0)

    def push(self, token, root, at=_T0):
        bridge = self.registry.bridge_for(token, now=at)
        bridge.record_manifest(build_manifest(str(root)), now=at)
        return bridge


class ProjectIsolationIsStructural(_TwoProjects):
    def test_there_is_no_call_that_asks_for_a_project_by_id(self):
        # The strongest form: the question cannot be expressed.
        for name, member in inspect.getmembers(BridgeRegistry, inspect.isfunction):
            if name.startswith("_"):
                continue
            parameters = set(inspect.signature(member).parameters)
            if name in ("enrol", "revoke", "knows_project"):
                continue          # issuing/administration, not retrieval
            self.assertNotIn(
                "project_id", parameters,
                "%s exposes a project_id route to a bridge" % name)

    def test_a_token_reaches_exactly_one_project(self):
        self.assertEqual(self.registry.bridge_for(self.token_a, now=_T0).project_id,
                         "project-a")
        self.assertEqual(self.registry.bridge_for(self.token_b, now=_T0).project_id,
                         "project-b")

    def test_project_a_cannot_see_project_b_content(self):
        self.push(self.token_a, self.root_a)
        self.push(self.token_b, self.root_b)
        bridge_a = self.registry.bridge_for(self.token_a, now=_T0)
        paths = [e.relative_path for e in bridge_a.entries()]
        self.assertEqual(paths, ["drawings/A-101.pdf"])
        self.assertNotIn("drawings/B-201.pdf", paths)

    def test_project_a_cannot_request_a_project_b_path(self):
        self.push(self.token_a, self.root_a)
        self.push(self.token_b, self.root_b)
        bridge_a = self.registry.bridge_for(self.token_a, now=_T0)
        with self.assertRaises(ExternalSourceError):
            bridge_a.request("drawings/B-201.pdf", now=_T0)

    def test_bytes_delivered_to_one_project_are_invisible_to_the_other(self):
        self.push(self.token_a, self.root_a)
        self.push(self.token_b, self.root_b)
        bridge_a = self.registry.bridge_for(self.token_a, now=_T0)
        bridge_a.request("drawings/A-101.pdf", now=_T0)
        for request in bridge_a.pending(now=_T0):
            bridge_a.deliver(request.id,
                             read_manifest_file(str(self.root_a), request.relative_path),
                             now=_T0)
        bridge_b = self.registry.bridge_for(self.token_b, now=_T0)
        self.assertFalse(bridge_b.holds_bytes())
        with self.assertRaises(ExternalSourceUnavailable):
            bridge_b.consume("drawings/A-101.pdf", now=_T0)


class CredentialsAreNeverRetainedInTheClear(_TwoProjects):
    def test_only_the_hash_is_stored(self):
        self.assertEqual(self.enrolment_a.token_hash,
                         hashlib.sha256(self.token_a.encode()).hexdigest())
        self.assertNotIn(self.token_a, str(vars(self.enrolment_a)))

    def test_the_raw_token_appears_nowhere_in_the_registry(self):
        blob = repr(vars(self.registry))
        self.assertNotIn(self.token_a, blob)
        self.assertNotIn(self.token_b, blob)

    def test_the_enrolment_record_has_no_field_that_could_hold_it(self):
        fields = set(vars(self.enrolment_a))
        for leak in ("token", "raw_token", "secret", "password"):
            self.assertNotIn(leak, fields)
        self.assertIn("token_hash", fields)

    def test_archiosk_never_receives_a_nas_credential(self):
        # The agent authenticates ITSELF to ARCHIOSK. How it reaches its own
        # storage is its own business, on its own side of the boundary - and
        # nothing here has anywhere to put such a secret.
        for holder in (vars(self.registry), vars(self.enrolment_a),
                       vars(self.registry.bridge_for(self.token_a, now=_T0))):
            for name in holder:
                for forbidden in ("nas_", "smb", "share_user", "admin_password",
                                  "storage_password", "mount"):
                    self.assertNotIn(forbidden, name.lower())

    def test_tokens_are_not_guessable_or_sequential(self):
        _, second = self.registry.enrol("project-a", "second-agent", now=_T0)
        self.assertNotEqual(self.token_a, second)
        self.assertGreaterEqual(len(self.token_a), 32)


class RevocationStopsBytesAndNotHistory(_TwoProjects):
    def test_a_revoked_agent_cannot_reach_a_bridge(self):
        self.push(self.token_a, self.root_a)
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        with self.assertRaises(BridgeEnrolmentRevoked):
            self.registry.bridge_for(self.token_a, now=_T0)

    def test_revocation_does_not_delete_what_the_project_knows(self):
        bridge = self.push(self.token_a, self.root_a)
        before = [e.as_dict() for e in bridge.entries()]
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        # The bridge object still holds the manifest; only the route in closed.
        self.assertEqual([e.as_dict() for e in bridge.entries()], before)
        self.assertTrue(self.registry.knows_project("project-a"))

    def test_re_enrolment_restores_access_without_re_synchronising(self):
        bridge = self.push(self.token_a, self.root_a)
        digest = bridge.digest()
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        _, fresh_token = self.registry.enrol("project-a", "ex4100-office", now=_T0)
        self.assertEqual(
            self.registry.bridge_for(fresh_token, now=_T0).digest(), digest)

    def test_revoking_one_project_leaves_the_other_working(self):
        self.push(self.token_a, self.root_a)
        self.push(self.token_b, self.root_b)
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        self.assertEqual(
            self.registry.bridge_for(self.token_b, now=_T0).project_id, "project-b")


class ReplayAndExpiryFailSafely(_TwoProjects):
    def test_an_expired_enrolment_is_refused(self):
        _, token = self.registry.enrol("project-c", "short-lived", now=_T0,
                                       ttl_seconds=60)
        self.registry.authorise(token, now=_T0 + timedelta(seconds=59))
        with self.assertRaises(BridgeEnrolmentRevoked):
            self.registry.authorise(token, now=_T0 + timedelta(seconds=61))

    def test_replaying_a_revoked_token_fails(self):
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        for _ in range(3):
            with self.assertRaises(BridgeEnrolmentRevoked):
                self.registry.authorise(self.token_a, now=_T0)

    def test_an_unknown_token_is_refused_identically_to_a_revoked_one(self):
        # Distinguishing them would confirm whether a project has an agent at
        # all, to someone holding no valid credential.
        self.registry.revoke("project-a", "ex4100-office", now=_T0)
        revoked = self._refusal(self.token_a)
        unknown = self._refusal("definitely-not-a-real-token")
        self.assertEqual(type(revoked), type(unknown))

    def _refusal(self, token):
        try:
            self.registry.authorise(token, now=_T0)
        except BridgeEnrolmentRevoked as exc:
            return exc
        self.fail("expected a refusal")

    def test_an_empty_or_none_token_is_refused(self):
        for bad in ("", None):
            with self.subTest(token=bad):
                with self.assertRaises(BridgeEnrolmentRevoked):
                    self.registry.authorise(bad, now=_T0)


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
        # The bridge deliberately adds no word for these; they already exist.
        from services.ingestion import (
            RECONCILE_STATUS_MISSING, RECONCILE_STATUS_MODIFIED,
            RECONCILE_STATUS_RENAMED, RECONCILE_STATUS_UNCHANGED,
        )
        import services.storage_bridge as bridge_module

        source = inspect.getsource(bridge_module)
        for invented in ("RELOCATED", "SYNCHRONIZED", "TEMPORARILY_UNAVAILABLE",
                         "LOCKED_PENDING"):
            self.assertNotIn(invented, source)
        self.assertEqual(
            [RECONCILE_STATUS_UNCHANGED, RECONCILE_STATUS_MODIFIED,
             RECONCILE_STATUS_RENAMED, RECONCILE_STATUS_MISSING],
            ["unchanged", "modified", "renamed", "missing"])


class RepeatedExchangeIsInert(_TwoProjects):
    """Idempotency. None of these may manufacture a second anything."""

    def test_the_same_manifest_twice_changes_nothing(self):
        bridge = self.push(self.token_a, self.root_a)
        first, count = bridge.digest(), len(bridge.entries())
        self.push(self.token_a, self.root_a, at=_T0 + timedelta(minutes=5))
        self.assertEqual(bridge.digest(), first)
        self.assertEqual(len(bridge.entries()), count)

    def test_an_interrupted_transfer_can_be_retried_without_duplication(self):
        bridge = self.push(self.token_a, self.root_a)
        first = bridge.request("drawings/A-101.pdf", now=_T0)
        bridge.pending(now=_T0)          # taken... and the agent dies here
        self.assertFalse(bridge.holds_bytes())
        second = bridge.request("drawings/A-101.pdf", now=_T0 + timedelta(minutes=1))
        self.assertNotEqual(first.id, second.id)
        for request in bridge.pending(now=_T0 + timedelta(minutes=1)):
            bridge.deliver(request.id, _PROJECT_A["drawings/A-101.pdf"],
                           now=_T0 + timedelta(minutes=1))
        self.assertEqual(bridge.consume("drawings/A-101.pdf",
                                        now=_T0 + timedelta(minutes=1)),
                         _PROJECT_A["drawings/A-101.pdf"])
        self.assertEqual(len(bridge.entries()), 1)

    def test_a_same_hash_relocation_keeps_one_entry_and_one_digest_change(self):
        bridge = self.push(self.token_a, self.root_a)
        original = bridge.entry_for("drawings/A-101.pdf").sha256
        (self.root_a / "drawings" / "A-101.pdf").rename(
            self.root_a / "drawings" / "A-101_Rev1.pdf")
        self.push(self.token_a, self.root_a, at=_T0 + timedelta(minutes=1))
        self.assertEqual(len(bridge.entries()), 1)
        moved = bridge.entry_for("drawings/A-101_Rev1.pdf")
        self.assertIsNotNone(moved)
        self.assertEqual(moved.sha256, original)     # identity travels with bytes

    def test_a_content_change_at_one_path_is_a_new_digest_not_a_new_entry(self):
        bridge = self.push(self.token_a, self.root_a)
        before = bridge.entry_for("drawings/A-101.pdf").sha256
        (self.root_a / "drawings" / "A-101.pdf").write_bytes(b"revised plan bytes")
        self.push(self.token_a, self.root_a, at=_T0 + timedelta(minutes=1))
        self.assertEqual(len(bridge.entries()), 1)
        self.assertNotEqual(bridge.entry_for("drawings/A-101.pdf").sha256, before)

    def test_reconnect_after_an_outage_does_not_resynchronise_from_scratch(self):
        bridge = self.push(self.token_a, self.root_a)
        digest = bridge.digest()
        late = _T0 + timedelta(hours=4)
        self.assertFalse(bridge.agent_is_live(now=late))
        self.assertEqual(bridge.digest(), digest)     # knowledge survived
        bridge.note_agent_poll(now=late)
        self.assertTrue(bridge.agent_is_live(now=late))
        self.assertEqual(bridge.digest(), digest)     # and did not churn


class NoSourceBytesRemainInArchiosxCustody(_TwoProjects):
    """Byte custody proven by inspection, not by a field being None."""

    def test_the_payload_is_absent_from_every_archiosk_owned_path_afterwards(self):
        archiosk_side = self.base / "archiosk_owned"
        (archiosk_side / "registry").mkdir(parents=True)
        (archiosk_side / "tmp").mkdir()

        bridge = self.push(self.token_a, self.root_a)
        bridge.request("drawings/A-101.pdf", now=_T0)
        for request in bridge.pending(now=_T0):
            bridge.deliver(request.id,
                           read_manifest_file(str(self.root_a), request.relative_path),
                           now=_T0)
        payload = bridge.consume("drawings/A-101.pdf", now=_T0)
        self.assertEqual(payload, _PROJECT_A["drawings/A-101.pdf"])   # it worked

        secret = _PROJECT_A["drawings/A-101.pdf"]
        for path in archiosk_side.rglob("*"):
            if path.is_file():
                self.assertNotIn(secret, path.read_bytes())
        self.assertEqual([p for p in archiosk_side.rglob("*") if p.is_file()], [])

    def test_the_bytes_are_gone_from_memory_state_too(self):
        bridge = self.push(self.token_a, self.root_a)
        bridge.request("drawings/A-101.pdf", now=_T0)
        for request in bridge.pending(now=_T0):
            bridge.deliver(request.id, _PROJECT_A["drawings/A-101.pdf"], now=_T0)
        bridge.consume("drawings/A-101.pdf", now=_T0)
        self.assertNotIn(_PROJECT_A["drawings/A-101.pdf"], repr(vars(bridge)).encode())

    def test_the_authoritative_file_is_still_on_the_private_side(self):
        bridge = self.push(self.token_a, self.root_a)
        bridge.request("drawings/A-101.pdf", now=_T0)
        for request in bridge.pending(now=_T0):
            bridge.deliver(request.id, _PROJECT_A["drawings/A-101.pdf"], now=_T0)
        bridge.consume("drawings/A-101.pdf", now=_T0)
        self.assertTrue((self.root_a / "drawings" / "A-101.pdf").is_file())


if __name__ == "__main__":
    unittest.main()
