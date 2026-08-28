"""
CLAUDE-CA1D-ATTENTION-STATE-02 -- the minimum per-item review-state proof:
CaseWorkspaceStore.record_item_reviewed / has_unreviewed_change, first
wired for Finding disposition/reviewer-validation.

Answers, truthfully: "has this Finding materially changed since this
particular user last meaningfully reviewed it" -- derived from the
already-governed `finding_reviewed` GovernanceLog events, never a second,
competing history of what changed. No UI in this tranche.

Run via:

    python -m unittest tests.test_ca1d_attention_state_02 -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class _BaseAttentionStateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_attention_state_02_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-attention-state-02"
        self.workspace = self.store.get_or_create(self.project_id)
        self.case = self.store.create_case(self.workspace, title="Case", objective="")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="setup")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[], objective="find things",
            engine_name="human-review", engine_version="0.0",
            findings=[{"statement": "A material finding statement.", "machine_confidence": 0.8}],
            trigger=trigger,
        )
        self.finding_id = analysis["finding_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _review_as(self, reviewer: str, validation: str = "Correct") -> None:
        """Reproduces the exact real ordering routes/workspace.py's
        validate_finding uses: record the ReviewerValidation, log the
        finding_reviewed GovernanceLog event, THEN record the review -
        never the other way around (see record_item_reviewed's own
        docstring for why the order is load-bearing)."""
        self.store.record_reviewer_validation(
            self.workspace, finding_id=self.finding_id, validation=validation, reviewer=reviewer,
        )
        self.gov.append(
            project_id=self.project_id, event_type="finding_reviewed", actor=reviewer, role="human",
            payload={"finding_id": self.finding_id, "reviewer_validation": validation},
        )
        self.store.record_item_reviewed(self.workspace, reviewer=reviewer, object_id=self.finding_id)


class LegacyAndDefaultStateTests(_BaseAttentionStateTestCase):
    def test_never_reviewed_is_unreviewed(self):
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_legacy_on_disk_record_with_no_item_reviewed_at_key_loads_safely(self):
        path = self.tmp_dir / f"{self.project_id}.workspace.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        # CLAUDE-VIEW-STATE-ISOLATION-01: `item_reviewed_at` is no longer
        # persisted in the workspace document at all - it lives in
        # _view_state/<project_id>.json, because a whole-document patch from a
        # GET could revert a governed write in another worker process. The
        # assertIn precondition that used to stand here is therefore obsolete:
        # every record is now written in exactly the shape this test simulates.
        # The pop stays, tolerant of either shape, so the test keeps asserting
        # what it is named for - that a record WITHOUT the key loads safely.
        raw.pop("item_reviewed_at", None)
        path.write_text(json.dumps(raw), encoding="utf-8")

        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.item_reviewed_at, {})  # safe default, not a KeyError
        self.assertTrue(self.store.has_unreviewed_change(reloaded, self.gov, "alice", self.finding_id))


class SingleUserReviewTests(_BaseAttentionStateTestCase):
    def test_first_meaningful_review_is_recorded(self):
        self._review_as("alice")
        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_review_persists_and_reloads_correctly(self):
        self._review_as("alice")
        reloaded = self.store.get(self.project_id)
        self.assertIn("alice", reloaded.item_reviewed_at)
        self.assertIn(self.finding_id, reloaded.item_reviewed_at["alice"])
        self.assertFalse(self.store.has_unreviewed_change(reloaded, self.gov, "alice", self.finding_id))


class MultiUserIsolationTests(_BaseAttentionStateTestCase):
    def test_different_user_remains_unreviewed(self):
        self._review_as("alice")
        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "bob", self.finding_id))

    def test_review_state_does_not_leak_across_projects(self):
        other_project_id = "test-attention-state-02-other"
        other_workspace = self.store.get_or_create(other_project_id)
        other_case = self.store.create_case(other_workspace, title="Other Case", objective="")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="setup")
        other_analysis = self.store.record_analysis(
            other_workspace, case_id=other_case["id"], source_ids=[], objective="find other things",
            engine_name="human-review", engine_version="0.0",
            findings=[{"statement": "An unrelated finding in a different project.", "machine_confidence": 0.8}],
            trigger=trigger,
        )
        other_finding_id = other_analysis["finding_ids"][0]

        self._review_as("alice")  # reviews self.finding_id in self.project_id only

        self.assertTrue(self.store.has_unreviewed_change(other_workspace, self.gov, "alice", other_finding_id))
        self.assertNotIn("alice", other_workspace.item_reviewed_at)


class ChangeAfterReviewTests(_BaseAttentionStateTestCase):
    def test_material_change_after_review_makes_it_unreviewed_again(self):
        """The named failure mode, actually exercised: review -> later
        material change (here: a DIFFERENT user's own disposition, the
        multi-user case the Product Owner specifically asked to be
        proven) -> unreviewed again for the reviewer whose review is now
        stale."""
        self._review_as("alice")
        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

        self._review_as("bob")  # a second, later, real reviewer action on the same Finding

        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))
        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "bob", self.finding_id))

    def test_second_review_by_the_same_user_clears_the_condition_again(self):
        self._review_as("alice")
        self._review_as("bob")
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

        self._review_as("alice")  # alice reviews again, after bob's change

        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_reviewers_own_action_never_immediately_looks_stale_against_itself(self):
        """Direct proof of the ordering-correctness concern named in
        record_item_reviewed's own docstring: a reviewer's own review
        must never be immediately flagged unreviewed against the very
        finding_reviewed event their own action just created."""
        self._review_as("alice")
        self.assertFalse(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))


class MalformedDataTests(_BaseAttentionStateTestCase):
    def test_non_dict_item_reviewed_at_fails_conservatively(self):
        self.workspace.item_reviewed_at = "not-a-dict"  # type: ignore[assignment]
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_non_dict_per_reviewer_entry_fails_conservatively(self):
        self.workspace.item_reviewed_at = {"alice": "not-a-dict-either"}
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_non_string_timestamp_fails_conservatively(self):
        self.workspace.item_reviewed_at = {"alice": {self.finding_id: 12345}}
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))

    def test_empty_string_timestamp_fails_conservatively(self):
        self.workspace.item_reviewed_at = {"alice": {self.finding_id: ""}}
        self.assertTrue(self.store.has_unreviewed_change(self.workspace, self.gov, "alice", self.finding_id))


class ConcurrencyTests(_BaseAttentionStateTestCase):
    def test_two_users_reviewing_the_same_finding_sequentially_both_persist(self):
        self._review_as("alice")
        self._review_as("bob")

        reloaded = self.store.get(self.project_id)
        self.assertIn("alice", reloaded.item_reviewed_at)
        self.assertIn("bob", reloaded.item_reviewed_at)
        self.assertIn(self.finding_id, reloaded.item_reviewed_at["alice"])
        self.assertIn(self.finding_id, reloaded.item_reviewed_at["bob"])

    def test_concurrent_record_item_reviewed_calls_do_not_clobber_each_other(self):
        """Real threads, not just sequential calls - proves _save_lock's
        same-process serialization actually holds under genuine
        concurrent write attempts for two different users' entries."""
        usernames = [f"user{i}" for i in range(8)]
        errors = []

        def _record(username: str) -> None:
            try:
                self.store.record_item_reviewed(self.workspace, reviewer=username, object_id=self.finding_id)
            except Exception as exc:  # pragma: no cover - failure path only
                errors.append(exc)

        threads = [threading.Thread(target=_record, args=(u,)) for u in usernames]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        reloaded = self.store.get(self.project_id)
        for username in usernames:
            self.assertIn(username, reloaded.item_reviewed_at)
            self.assertIn(self.finding_id, reloaded.item_reviewed_at[username])

        # Documented, accepted residual (matches record_last_viewed's own
        # disclosed gap, not a new one): _save_lock is a threading.Lock,
        # same-process only. A concurrent write from a DIFFERENT gunicorn
        # WORKER process is not serialized by it - the raw-JSON
        # read-patch-write in record_item_reviewed could still lose a
        # concurrent cross-process update the same way record_last_viewed
        # already can. Not exercised here (this test suite runs
        # in-process), named so it isn't silently assumed solved.

    def test_review_write_does_not_disturb_an_unrelated_findings_review_state(self):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="setup")
        analysis2 = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[], objective="find more things",
            engine_name="human-review", engine_version="0.0",
            findings=[{"statement": "A second, unrelated finding.", "machine_confidence": 0.6}],
            trigger=trigger,
        )
        other_finding_id = analysis2["finding_ids"][0]

        self._review_as("alice")  # reviews self.finding_id only

        reloaded = self.store.get(self.project_id)
        self.assertIn(self.finding_id, reloaded.item_reviewed_at.get("alice", {}))
        self.assertNotIn(other_finding_id, reloaded.item_reviewed_at.get("alice", {}))
        self.assertTrue(self.store.has_unreviewed_change(reloaded, self.gov, "alice", other_finding_id))


class ReviewThreadAttentionUnaffectedTests(_BaseAttentionStateTestCase):
    """Regression guard: CLAUDE-CA1D-ATTENTION-STATE-02 must not touch
    ReviewThread/ReviewMessage/Attention at all - they remain a separate,
    explicit human-directed-escalation concept, per CLAUDE-CA1D-
    ATTENTION-STATE-01A's own explicit boundary."""

    def test_review_thread_and_attention_lifecycle_still_works_unchanged(self):
        thread = self.store.create_review_thread(
            self.workspace, title="A discussion", anchor_type="finding", anchor_id=self.finding_id,
            created_by="alice", case_id=self.case["id"],
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin="human", actor="alice",
            message_type="observation", text="Please look at this.",
        )
        attention = self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=message["id"],
            intended_actor="bob", created_by="alice",
        )
        self.assertEqual(attention["status"], "pending")

        response = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin="human", actor="bob",
            message_type="response", text="Looked at it.",
        )
        self.store.respond_to_attention(self.workspace, attention_id=attention["id"], response_message_id=response["id"])

        reloaded = self.store.get(self.project_id)
        reloaded_attention = self.store._find(reloaded.attentions, attention["id"])
        self.assertEqual(reloaded_attention["status"], "responded")
        # Unaffected by, and unrelated to, item_reviewed_at entirely.
        self.assertEqual(reloaded.item_reviewed_at, {})


class RouteIntegrationTests(unittest.TestCase):
    """Proves the real wiring, not just the service-layer methods in
    isolation: routes/workspace.py's validate_finding/set_disposition
    actually call record_item_reviewed, in the correct order, through a
    real Flask test client and a real project."""

    def setUp(self):
        import io
        import uuid as uuid_module
        from datetime import datetime, timezone
        from unittest.mock import patch

        import app as app_module
        from models import User, db
        from werkzeug.datastructures import FileStorage
        from werkzeug.security import generate_password_hash

        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.environment_capabilities import CLIENT_OWNER
        from services.ingestion import ingest_upload

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_attention_state_02_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="attn_alice", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="attn_bob", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        # Hermetic ingestion (per this repo's own established convention -
        # never let a test path reach the real BHiveParser.parse/Anthropic
        # API): _load_workspace_or_404 requires a real RequirementsRegistry
        # document to exist for the project, not just a ProjectWorkspace.
        def fake_parse(self_parser, raw_bytes, filename):
            return ParsedDocument(
                project_id=str(uuid_module.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                doc = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"content"), filename="a.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="attn_alice", project_name="Attention State 02 Route Test",
                )
        self.project_id = doc.project_id

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get(self.project_id)
        # Finding/Artifact remain Case-scoped (a project-level Analysis
        # cannot carry real findings) - so the Case is required, but must
        # be SHARED, not left PRIVATE, or attn_bob's own POST below would
        # 404 at _require_visible_case before ever reaching
        # record_reviewer_validation (Case visibility is a separate
        # authorization axis from the admin/read_only project role).
        self.case = self.store.create_case(self.workspace, title="Case", objective="", created_by="attn_alice")
        self.store.share_case(self.workspace, self.case["id"], actor="attn_alice")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="setup")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[], objective="find things",
            engine_name="human-review", engine_version="0.0",
            findings=[{"statement": "A material finding statement.", "machine_confidence": 0.8}],
            trigger=trigger,
        )
        self.finding_id = analysis["finding_ids"][0]
        self.gov = GovernanceLog(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self, username: str):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1 if username == "attn_alice" else 2
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def test_validate_finding_route_records_review_for_the_acting_user(self):
        client = self._client("attn_alice")
        response = client.post(
            f"/projects/{self.project_id}/workspace/findings/{self.finding_id}/validate",
            data={"validation": "Correct"},
        )
        self.assertEqual(response.status_code, 302)

        reloaded = self.store.get(self.project_id)
        self.assertFalse(self.store.has_unreviewed_change(reloaded, self.gov, "attn_alice", self.finding_id))
        self.assertTrue(self.store.has_unreviewed_change(reloaded, self.gov, "attn_bob", self.finding_id))

    def test_disposition_route_records_review_and_a_later_disposition_by_another_user_unreviews_the_first(self):
        alice = self._client("attn_alice")
        alice.post(
            f"/projects/{self.project_id}/workspace/findings/{self.finding_id}/validate",
            data={"validation": "Correct"},
        )
        alice.post(
            f"/projects/{self.project_id}/workspace/findings/{self.finding_id}/disposition",
            data={"disposition": "Confirmed"},
        )
        reloaded = self.store.get(self.project_id)
        self.assertFalse(self.store.has_unreviewed_change(reloaded, self.gov, "attn_alice", self.finding_id))

        bob = self._client("attn_bob")
        bob.post(
            f"/projects/{self.project_id}/workspace/findings/{self.finding_id}/validate",
            data={"validation": "Partial", "correction_note": "Needs a second look."},
        )

        reloaded = self.store.get(self.project_id)
        self.assertFalse(self.store.has_unreviewed_change(reloaded, self.gov, "attn_bob", self.finding_id))
        self.assertTrue(self.store.has_unreviewed_change(reloaded, self.gov, "attn_alice", self.finding_id))


if __name__ == "__main__":
    unittest.main()
