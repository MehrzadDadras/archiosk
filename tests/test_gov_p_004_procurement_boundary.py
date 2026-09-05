"""
GOV-P-004 / GOV-P-005 — the decoupled two-sided procurement boundary.

Verifies `services/procurement_governance.py` against the three invariants the
mission named, and against the two governance records those invariants come
from:

  1. **Structural decoupling** — the Owner drafting state and the issued record
     share no mutable storage, and the Proponent side cannot write into the
     issued record.
  2. **Immutability** — an issued snapshot is write-once with a deterministic
     SHA-256 canonical digest.
  3. **GOV-P-005** — arrival is `ARRIVED_IN_AIRLOCK`, not admission; admission
     requires vestibule evaluation; `evidence_class` is strictly
     `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED`.

Hermetic and app-free by construction (`tests/conftest.py` Tier 0 rules): no
`create_app`, no `test_client`, no store outside `tmp_path`, no network. The
only import from the application is the evidence-class constant, which is the
point — the class this module pins is the real one from
`services/case_workspace.py`, not a copy that could drift away from it.
"""
from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
    EVIDENCE_CLASS_DIRECT_SOURCE,
    EVIDENCE_CLASS_EXTERNALLY_RESEARCHED,
)
from services.procurement_governance import (
    ADMISSION_ADMITTED,
    ADMISSION_ARRIVED_IN_AIRLOCK,
    ADMISSION_REJECTED,
    IssuedProcurementSnapshot,
    ProcurementBoundaryStore,
    ProcurementGovernanceError,
    ProponentProcurementReceipt,
    SnapshotImmutabilityError,
    canonical_payload_bytes,
    evaluate_vestibule_admission,
    issue_publication_snapshot,
    payload_digest,
    receive_into_airlock,
)

_PAYLOAD = {
    "instrument": "Request for Proposals",
    "clauses": [
        {"id": "OPR-1.1", "text": "Smoke management analysis shall be provided."},
        {"id": "OPR-1.2", "text": "Compartmentation shall be maintained."},
    ],
    "issued_documents": ["rfp-main.pdf", "appendix-a.pdf"],
}


class _BoundaryTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="beehive_gov_p_004_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.store = ProcurementBoundaryStore(self.root)

    def _issue(self, seq: int = 1, payload: dict | None = None, project_id: str = "PROJECT-PSD"):
        return issue_publication_snapshot(
            self.store,
            project_id=project_id,
            addendum_seq=seq,
            payload=_PAYLOAD if payload is None else payload,
            issuer_user_id="owner-user-1",
        )


class CanonicalDigestTests(_BoundaryTestCase):
    """Invariant 2, the digest half: deterministic, and genuinely a function
    of content rather than of how the content happened to be spelled."""

    def test_digest_is_stable_across_key_order_and_whitespace(self):
        a = {"b": 2, "a": 1, "nested": {"y": [1, 2], "x": "value"}}
        b = {"a": 1, "nested": {"x": "value", "y": [1, 2]}, "b": 2}
        self.assertEqual(payload_digest(a), payload_digest(b))

    def test_digest_is_a_real_sha256_of_the_canonical_bytes(self):
        import hashlib

        expected = hashlib.sha256(canonical_payload_bytes(_PAYLOAD)).hexdigest()
        self.assertEqual(payload_digest(_PAYLOAD), expected)
        self.assertEqual(len(expected), 64)

    def test_any_content_change_changes_the_digest(self):
        altered = json.loads(json.dumps(_PAYLOAD))
        altered["clauses"][0]["text"] += " "
        self.assertNotEqual(payload_digest(_PAYLOAD), payload_digest(altered))

    def test_list_order_is_content_not_formatting(self):
        # sort_keys normalizes mappings. It must NOT normalize sequences -
        # clause order is meaning in a procurement instrument.
        reordered = {"clauses": list(reversed(_PAYLOAD["clauses"]))}
        self.assertNotEqual(payload_digest({"clauses": _PAYLOAD["clauses"]}),
                            payload_digest(reordered))

    def test_non_serializable_and_nan_payloads_are_refused_at_issue_time(self):
        for bad in ({"when": object()}, {"value": float("nan")}, {"value": float("inf")}):
            with self.assertRaises(ProcurementGovernanceError):
                payload_digest(bad)


class WriteOnceImmutabilityTests(_BoundaryTestCase):
    """Invariant 2: an issued snapshot is strictly write-once."""

    def test_the_snapshot_object_itself_cannot_be_mutated(self):
        snapshot = self._issue()
        for field_name, value in (
            ("payload_json", '{"tampered": true}'),
            ("payload_sha256", "0" * 64),
            ("addendum_sequence", 99),
            ("issued_by_user_id", "someone-else"),
        ):
            with self.assertRaises(dataclasses.FrozenInstanceError, msg=field_name):
                setattr(snapshot, field_name, value)

    def test_a_second_issue_at_the_same_identity_is_refused(self):
        self._issue(seq=1)
        with self.assertRaises(SnapshotImmutabilityError):
            self._issue(seq=1, payload={"instrument": "a different package"})

    def test_the_refused_second_issue_does_not_overwrite_the_first(self):
        first = self._issue(seq=1)
        with self.assertRaises(SnapshotImmutabilityError):
            self._issue(seq=1, payload={"instrument": "a different package"})
        stored = self.store.get_snapshot("PROJECT-PSD", 1)
        self.assertEqual(stored.payload_sha256, first.payload_sha256)
        self.assertEqual(stored.payload, _PAYLOAD)

    def test_re_issuing_byte_identical_content_is_still_refused(self):
        # "It was the same anyway" is exactly the reasoning that turns a
        # write-once record into a last-writer-wins one.
        self._issue(seq=2)
        with self.assertRaises(SnapshotImmutabilityError):
            self._issue(seq=2)

    def test_uniqueness_is_scoped_per_project_not_globally(self):
        self._issue(seq=1, project_id="PROJECT-ONE")
        other = self._issue(seq=1, project_id="PROJECT-TWO")
        self.assertEqual(other.addendum_sequence, 1)
        self.assertEqual(len(self.store.list_snapshots("PROJECT-ONE")), 1)

    def test_different_sequences_coexist(self):
        self._issue(seq=1)
        self._issue(seq=2)
        self.assertEqual([s.addendum_sequence for s in self.store.list_snapshots("PROJECT-PSD")], [1, 2])


class IssuedIdentityTests(_BoundaryTestCase):
    def test_id_carries_project_sequence_and_digest_prefix(self):
        snapshot = self._issue(seq=7)
        self.assertEqual(
            snapshot.id, f"ISSUED-PROJECT-PSD-ADD-0007-{snapshot.payload_sha256[:8]}"
        )

    def test_stored_payload_json_is_the_exact_bytes_that_were_hashed(self):
        snapshot = self._issue()
        self.assertEqual(
            snapshot.payload_json, canonical_payload_bytes(_PAYLOAD).decode("utf-8")
        )
        self.assertEqual(snapshot.recomputed_digest(), snapshot.payload_sha256)

    def test_unusable_ids_and_arguments_are_refused_rather_than_sanitized(self):
        for bad_project in ("../escape", "with/slash", "", "x" * 200):
            with self.assertRaises(ProcurementGovernanceError, msg=bad_project):
                self._issue(project_id=bad_project)
        with self.assertRaises(ProcurementGovernanceError):
            issue_publication_snapshot(self.store, "PROJECT-PSD", -1, _PAYLOAD, "u")
        with self.assertRaises(ProcurementGovernanceError):
            issue_publication_snapshot(self.store, "PROJECT-PSD", 1, _PAYLOAD, "  ")
        with self.assertRaises(ProcurementGovernanceError):
            issue_publication_snapshot(self.store, "PROJECT-PSD", 1, ["not", "a", "dict"], "u")

    def test_booleans_are_not_accepted_as_a_sequence_number(self):
        # bool is an int subclass; True would otherwise silently issue as 1.
        with self.assertRaises(ProcurementGovernanceError):
            issue_publication_snapshot(self.store, "PROJECT-PSD", True, _PAYLOAD, "u")


class AirlockArrivalTests(_BoundaryTestCase):
    """Invariant 3, GOV-P-005: arrival is movement, not admission."""

    def test_arrival_stages_in_the_airlock_and_admits_nothing(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        self.assertEqual(receipt.admission_state, ADMISSION_ARRIVED_IN_AIRLOCK)
        self.assertIsNone(receipt.admitted_at)
        self.assertIsNone(receipt.rejection_reason)
        self.assertNotEqual(receipt.admission_state, ADMISSION_ADMITTED)

    def test_arrived_material_is_externally_researched_evidence(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        self.assertEqual(receipt.evidence_class, EVIDENCE_CLASS_EXTERNALLY_RESEARCHED)

    def test_a_receipt_cannot_be_constructed_with_any_other_evidence_class(self):
        for wrong in (EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, "invented"):
            with self.assertRaises(ProcurementGovernanceError, msg=wrong):
                ProponentProcurementReceipt(
                    id="R1",
                    proponent_workspace_id="WS",
                    issued_snapshot_id="S",
                    observed_sha256="0" * 64,
                    evidence_class=wrong,
                )

    def test_an_unknown_admission_state_is_refused(self):
        with self.assertRaises(ProcurementGovernanceError):
            ProponentProcurementReceipt(
                id="R1",
                proponent_workspace_id="WS",
                issued_snapshot_id="S",
                observed_sha256="0" * 64,
                admission_state="ADMITTED_PROBABLY",
            )

    def test_arrival_of_an_unknown_snapshot_is_refused(self):
        with self.assertRaises(ProcurementGovernanceError):
            receive_into_airlock(self.store, "ISSUED-NOPE-ADD-0001-deadbeef", "PROPONENT-WS-1")

    def test_the_receipt_records_the_digest_it_observed(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        self.assertEqual(receipt.observed_sha256, snapshot.payload_sha256)


class StructuralDecouplingTests(_BoundaryTestCase):
    """Invariant 1: no shared mutable storage between the two sides."""

    def test_the_two_sides_persist_under_separate_roots(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        issued_files = {p.name for p in (self.root / "issued_snapshots").rglob("*.json")}
        receipt_files = {p.name for p in (self.root / "proponent_receipts").rglob("*.json")}
        self.assertTrue(issued_files)
        self.assertTrue(receipt_files)
        self.assertEqual(issued_files & receipt_files, set())

    def test_the_full_proponent_lifecycle_never_writes_into_the_issued_store(self):
        snapshot = self._issue()
        issued_dir = self.root / "issued_snapshots"
        before = {p: p.read_bytes() for p in sorted(issued_dir.rglob("*"))if p.is_file()}

        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        evaluate_vestibule_admission(self.store, receipt.id)

        after = {p: p.read_bytes() for p in sorted(issued_dir.rglob("*")) if p.is_file()}
        self.assertEqual(before, after, "the Proponent side modified the issued record")

    def test_two_proponents_receiving_the_same_issue_do_not_share_a_record(self):
        snapshot = self._issue()
        one = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        two = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-2")
        self.assertNotEqual(one.id, two.id)

        evaluate_vestibule_admission(self.store, one.id, validator_func=lambda p: "declined")
        self.assertEqual(self.store.get_receipt(two.id).admission_state, ADMISSION_ARRIVED_IN_AIRLOCK)
        self.assertEqual(self.store.list_receipts("PROPONENT-WS-2"), [self.store.get_receipt(two.id)])


class VestibuleTamperingTests(_BoundaryTestCase):
    """Invariant 2 meeting Invariant 3: the vestibule is where integrity is
    actually established, and it must catch both shapes of tampering."""

    def _tamper(self, project_id: str, seq: int, mutate) -> None:
        path = self.root / "issued_snapshots" / project_id / f"ADD-{seq:04d}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def test_payload_tampering_is_rejected(self):
        snapshot = self._issue(seq=1)
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        self._tamper("PROJECT-PSD", 1, lambda d: d.__setitem__(
            "payload_json", json.dumps({"instrument": "swapped"}, separators=(",", ":"))
        ))
        decided = evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(decided.admission_state, ADMISSION_REJECTED)
        self.assertIn("integrity", decided.rejection_reason.lower())
        self.assertIsNone(decided.admitted_at)

    def test_self_consistent_tampering_is_still_caught_by_the_receipt(self):
        # The interesting case: rewrite the payload AND its recorded digest, so
        # the snapshot file agrees with itself. Only the receipt's independently
        # stored observation catches this.
        snapshot = self._issue(seq=1)
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        swapped = {"instrument": "swapped"}

        def rewrite(data):
            data["payload_json"] = canonical_payload_bytes(swapped).decode("utf-8")
            data["payload_sha256"] = payload_digest(swapped)

        self._tamper("PROJECT-PSD", 1, rewrite)
        decided = evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(decided.admission_state, ADMISSION_REJECTED)
        self.assertIn("observed on arrival", decided.rejection_reason)

    def test_a_vanished_snapshot_is_rejected_not_crashed(self):
        snapshot = self._issue(seq=1)
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        (self.root / "issued_snapshots" / "PROJECT-PSD" / "ADD-0001.json").unlink()
        decided = evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(decided.admission_state, ADMISSION_REJECTED)

    def test_a_failing_structural_validator_rejects_with_its_own_reason(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        decided = evaluate_vestibule_admission(
            self.store, receipt.id, validator_func=lambda p: "no bid-closing date"
        )
        self.assertEqual(decided.admission_state, ADMISSION_REJECTED)
        self.assertEqual(decided.rejection_reason, "no bid-closing date")

    def test_the_validator_sees_the_real_payload(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        seen = {}
        evaluate_vestibule_admission(
            self.store, receipt.id, validator_func=lambda p: seen.update(p) or None
        )
        self.assertEqual(seen, _PAYLOAD)

    def test_a_decided_receipt_is_not_re_evaluated(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        evaluate_vestibule_admission(self.store, receipt.id, validator_func=lambda p: "rejected once")
        with self.assertRaises(ProcurementGovernanceError):
            evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(self.store.get_receipt(receipt.id).admission_state, ADMISSION_REJECTED)

    def test_evaluating_an_unknown_receipt_is_refused(self):
        with self.assertRaises(ProcurementGovernanceError):
            evaluate_vestibule_admission(self.store, "RECEIPT-NOPE")


class EndToEndBoundaryTests(_BoundaryTestCase):
    """Issuance -> airlock arrival -> vestibule admission, in full."""

    def test_the_whole_flow(self):
        snapshot = issue_publication_snapshot(
            self.store,
            project_id="PROJECT-PSD",
            addendum_seq=1,
            payload=_PAYLOAD,
            issuer_user_id="owner-user-1",
        )
        self.assertEqual(snapshot.payload_sha256, payload_digest(_PAYLOAD))

        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        self.assertEqual(receipt.admission_state, ADMISSION_ARRIVED_IN_AIRLOCK)
        self.assertIsNone(receipt.admitted_at)

        admitted = evaluate_vestibule_admission(
            self.store,
            receipt.id,
            validator_func=lambda p: None if p.get("clauses") else "no clauses",
        )
        self.assertEqual(admitted.admission_state, ADMISSION_ADMITTED)
        self.assertIsNotNone(admitted.admitted_at)
        self.assertIsNone(admitted.rejection_reason)

    def test_admission_confers_no_authority_on_the_admitted_material(self):
        # GOV-P-005's central claim, asserted rather than assumed: passing the
        # vestibule changes the state and the timestamp, and NOTHING about how
        # authoritative the material is. If a promotion path is ever added,
        # this is the test that must be argued with first.
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        before = receipt.evidence_class
        admitted = evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(admitted.admission_state, ADMISSION_ADMITTED)
        self.assertEqual(admitted.evidence_class, before)
        self.assertEqual(admitted.evidence_class, EVIDENCE_CLASS_EXTERNALLY_RESEARCHED)
        self.assertEqual(
            self.store.get_receipt(receipt.id).evidence_class,
            EVIDENCE_CLASS_EXTERNALLY_RESEARCHED,
        )

    def test_the_issued_snapshot_survives_a_round_trip_unchanged(self):
        snapshot = self._issue()
        reloaded = self.store.get_snapshot_by_id(snapshot.id)
        self.assertEqual(reloaded, snapshot)
        self.assertIsInstance(reloaded, IssuedProcurementSnapshot)
        self.assertEqual(reloaded.payload, _PAYLOAD)

    def test_admission_of_one_receipt_leaves_the_issued_baseline_untouched(self):
        snapshot = self._issue()
        receipt = receive_into_airlock(self.store, snapshot.id, "PROPONENT-WS-1")
        evaluate_vestibule_admission(self.store, receipt.id)
        self.assertEqual(self.store.get_snapshot_by_id(snapshot.id), snapshot)


if __name__ == "__main__":
    unittest.main()
