"""
GOV-P-004 / GOV-P-005 — the decoupled two-sided procurement boundary.

Two governance principles meet in this module, and each contributes one half
of its shape:

    GOV-P-004 (Decoupled Two-Sided Procurement Foundation) — the two sides are
    independent workflows over one shared kernel. The boundary between them is
    an artifact moved out-of-band by a human, "never a shared runtime, network,
    application instance, or database."

    GOV-P-005 (Airlock is movement; Vestibule is admission) — arrival is not
    admission. Crossing a movement boundary never confers project authority.

WHY THIS IS FLAT JSON AND NOT A DATABASE TABLE

`models.py` is this repository's SQLAlchemy layer and holds only
infrastructure: `User`, password/verification tokens, storage enrolments,
diagnostics. **No domain object has ever lived there.** The domain model is
dataclasses persisted as flat JSON (`services/case_workspace.py`,
`services/requirements_registry.py`, `services/governance.py`), and a
SQLite-backed rewrite of that was explicitly proposed and explicitly rejected —
`tools/dependency_fit.py --requires-database` returns WARN for exactly this
reason and asks for a documented justification rather than "it's more
standard".

Flat files are not a compromise here; for a write-once record they are the
better instrument. `open(path, "x")` is an atomic, filesystem-enforced
exclusive create — it is *not possible* to write a second snapshot at the same
identity, with no read-then-write race to lose, and no reliance on a
model-level hook that a future `session.bulk_update()` could route around.
Immutability is likewise carried by the type (`@dataclass(frozen=True)`)
rather than by a validator that has to be remembered.

HOW THE TWO SIDES ARE KEPT APART (GOV-P-004, Invariant 1)

Two separate store roots, and one direction of travel:

    <root>/issued_snapshots/<project_id>/ADD-<seq>.json      write-once
    <root>/proponent_receipts/<workspace_id>/<id>.json       mutable

The Owner side writes only the first. The Proponent side writes only the
second. A receipt names a snapshot by id and carries its own copy of the
digest; nothing on the Proponent side can write into the issued record, and no
row, file or object is shared between them. `receive_into_airlock` is the only
function that reads across the boundary, and it only ever reads.

WHY THE RECEIPT CARRIES ITS OWN COPY OF THE DIGEST

If the only recorded digest lived inside the snapshot file next to the payload
it describes, tampering with both together would be self-consistent and
undetectable. The receipt captures the digest at arrival, in a different file
under a different root, so `evaluate_vestibule_admission` can compare three
independently-stored facts: the payload as it reads today, the digest the
issuer recorded, and the digest the receiver observed on arrival. Any single
one of them being altered is caught.

WHAT ADMISSION HERE DOES AND DOES NOT MEAN — read this before extending

`ADMITTED` in this module means **"evaluated at the vestibule and recorded as
having passed"**. It does not confer project authority, and it must not be
made to. `evidence_class` is pinned to `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED`
for the entire life of a receipt, in every state including `ADMITTED`, and
there is deliberately no parameter, no setter and no code path in this module
that changes it. That is GOV-P-005's central invariant expressed as a type
rather than as a rule someone has to remember.

The act of conferring project authority on admitted material is a separate,
human-authorized act that this module does not implement and does not
authorize. `GO-EXTERNAL-VESTIBULE-01` (the External Source Vestibule admission
*workflow*) remains `DEFERRED`, and GOV-P-005 says of itself, in its own
Prohibited drift section, that it does not authorize it either. Anyone adding
a promotion path here is leaving what this module is allowed to be.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from services.case_workspace import EVIDENCE_CLASS_EXTERNALLY_RESEARCHED

# --- Admission states (GOV-P-005) -----------------------------------------
# A closed vocabulary, for the same reason KNOWN_EVIDENCE_CLASSES is closed in
# services/case_workspace.py: this is the distinction the no-silent-promotion
# discipline leans on, so a caller inventing a state is a defect to surface
# immediately, not a value to store verbatim.
ADMISSION_ARRIVED_IN_AIRLOCK = "ARRIVED_IN_AIRLOCK"
ADMISSION_VESTIBULE_EVALUATING = "VESTIBULE_EVALUATING"
ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"

KNOWN_ADMISSION_STATES = (
    ADMISSION_ARRIVED_IN_AIRLOCK,
    ADMISSION_VESTIBULE_EVALUATING,
    ADMISSION_ADMITTED,
    ADMISSION_REJECTED,
)

# Terminal states. A receipt that has reached one is not re-evaluated: an
# admission decision that can be quietly re-run is not a decision.
TERMINAL_ADMISSION_STATES = (ADMISSION_ADMITTED, ADMISSION_REJECTED)

# Path components are derived from caller-supplied ids, so the charset is
# restricted rather than sanitised. Sanitising silently maps two different
# project ids onto one file; refusing does not. UUIDs, the real id shape here,
# pass unchanged.
_SAFE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")

_ISSUED_ROOT = "issued_snapshots"
_RECEIPT_ROOT = "proponent_receipts"


class ProcurementGovernanceError(Exception):
    """
    A governed procurement-boundary rule was violated: a second issue at an
    identity already used, a tampered payload, a re-decided receipt, an
    unusable id. Mirrors CaseWorkspaceError's role — an honest, specific
    refusal rather than an IOError or a KeyError escaping from the internals.
    """


class SnapshotImmutabilityError(ProcurementGovernanceError):
    """
    An attempt to change an issued snapshot after it was persisted. Separate
    from the base class because this is the one failure that means a caller
    tried to rewrite history rather than merely got an argument wrong, and a
    test asserting immutability should not pass just because *some* error was
    raised.
    """


def canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    """
    The exact bytes the digest is taken over.

    Determinism is the whole point, so every source of encoder freedom is
    pinned: `sort_keys` (so key insertion order cannot change the digest),
    the tightest separators (so whitespace cannot), `ensure_ascii=False` with
    an explicit UTF-8 encode (so a non-ASCII character has one representation
    rather than depending on the encoder's escaping mood), and `allow_nan=False`
    (so a NaN, which no JSON reader agrees on, is refused at issue time rather
    than producing a package that re-reads differently on the other side).
    """
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProcurementGovernanceError(
            f"Payload is not canonically serializable, so it cannot be issued: {exc}"
        ) from exc
    return text.encode("utf-8")


def payload_digest(payload: dict[str, Any]) -> str:
    """SHA-256 of the canonical bytes, lowercase hex."""
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def _require_safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise ProcurementGovernanceError(
            f"{label} must be 1-128 characters of letters, digits, '_', '.' or '-' "
            f"and start with a letter or digit; got {value!r}."
        )
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IssuedProcurementSnapshot:
    """
    One issued procurement package, as fixed at the moment of issue.

    Frozen by type. GOV-P-004's invariant is that "Owner-side issuance
    concludes in an immutable baseline: the issued set, its clause identities,
    and its provenance are fixed at the moment of issue and are never mutated
    afterwards" — `frozen=True` makes an attempted mutation a
    `dataclasses.FrozenInstanceError` at the assignment itself, before any
    store is involved, rather than something a persistence hook has to catch
    on the way out.
    """

    id: str
    project_id: str
    addendum_sequence: int
    payload_json: str
    payload_sha256: str
    issued_by_user_id: str
    issued_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def payload(self) -> dict[str, Any]:
        """The payload as data. Re-parsed each call — never cached onto the
        instance, which would mean writing to a frozen dataclass."""
        return json.loads(self.payload_json)

    def recomputed_digest(self) -> str:
        """
        The digest of what this snapshot *currently* holds, which is the whole
        point of storing `payload_json` verbatim rather than a parsed dict:
        re-canonicalising the stored text and re-hashing it detects an edit to
        the file, where re-serialising a dict we had just parsed from that same
        file would only ever agree with itself.
        """
        return payload_digest(self.payload)


@dataclass
class ProponentProcurementReceipt:
    """
    The Proponent side's own record of an artifact that arrived.

    Deliberately NOT frozen: this is a state machine, and its whole purpose is
    to carry a decision that has not been made yet. That asymmetry is the
    structural decoupling — the immutable thing and the mutable thing are
    different types, in different files, under different roots, written by
    different sides.

    `evidence_class` is fixed at construction and never varies. See this
    module's docstring: admission records that an evaluation passed, it does
    not promote anything.
    """

    id: str
    proponent_workspace_id: str
    issued_snapshot_id: str
    observed_sha256: str
    admission_state: str = ADMISSION_ARRIVED_IN_AIRLOCK
    arrived_at: str = field(default_factory=_now)
    admitted_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    evidence_class: str = EVIDENCE_CLASS_EXTERNALLY_RESEARCHED

    def __post_init__(self):
        if self.admission_state not in KNOWN_ADMISSION_STATES:
            raise ProcurementGovernanceError(
                f"'{self.admission_state}' is not a recognized admission state. "
                f"Use one of: {', '.join(KNOWN_ADMISSION_STATES)}."
            )
        if self.evidence_class != EVIDENCE_CLASS_EXTERNALLY_RESEARCHED:
            # Not "one of a set" — exactly this one. Material that arrived from
            # outside the governed corpus is externally researched evidence for
            # as long as this record describes it (GOV-P-005).
            raise ProcurementGovernanceError(
                "A procurement receipt is always "
                f"'{EVIDENCE_CLASS_EXTERNALLY_RESEARCHED}'; got "
                f"'{self.evidence_class}'. Admission records an evaluation, it "
                "never promotes arrived material to project authority."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProcurementBoundaryStore:
    """
    Flat-JSON persistence for both sides, with the two roots kept apart.

    Constructed with a store root the caller owns (`REGISTRY_STORE_PATH` in
    the app, a tmp_path in tests), the same shape `RequirementsRegistry` and
    `GovernanceLog` already use.
    """

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.issued_root = self.store_path / _ISSUED_ROOT
        self.receipt_root = self.store_path / _RECEIPT_ROOT
        self.issued_root.mkdir(parents=True, exist_ok=True)
        self.receipt_root.mkdir(parents=True, exist_ok=True)

    # -- Owner side ---------------------------------------------------------

    def _snapshot_path(self, project_id: str, addendum_sequence: int) -> Path:
        return self.issued_root / project_id / f"ADD-{addendum_sequence:04d}.json"

    def write_snapshot_once(self, snapshot: IssuedProcurementSnapshot) -> None:
        """
        Persist a snapshot, or refuse because that identity is already issued.

        `open(..., "x")` rather than `exists()` then `write_text()`: the
        exclusive-create flag makes the check and the write one atomic
        filesystem operation, so two concurrent issuers cannot both observe
        "not there yet" and both write. That is also what enforces uniqueness
        on (project_id, addendum_sequence) — the pair *is* the path, so a
        duplicate is not a constraint that has to be declared and checked, it
        is a file that already exists.
        """
        path = self._snapshot_path(snapshot.project_id, snapshot.addendum_sequence)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False)
        try:
            with open(path, "x", encoding="utf-8") as handle:
                handle.write(payload)
        except FileExistsError as exc:
            existing = self.get_snapshot(snapshot.project_id, snapshot.addendum_sequence)
            raise SnapshotImmutabilityError(
                f"Sequence {snapshot.addendum_sequence} is already issued for project "
                f"{snapshot.project_id} as {existing.id if existing else 'an existing snapshot'}. "
                "An issued snapshot is write-once and is never replaced or re-issued."
            ) from exc

    def get_snapshot(
        self, project_id: str, addendum_sequence: int
    ) -> Optional[IssuedProcurementSnapshot]:
        path = self._snapshot_path(project_id, addendum_sequence)
        if not path.exists():
            return None
        return IssuedProcurementSnapshot(**json.loads(path.read_text(encoding="utf-8")))

    def get_snapshot_by_id(self, snapshot_id: str) -> Optional[IssuedProcurementSnapshot]:
        for path in sorted(self.issued_root.glob("*/ADD-*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") == snapshot_id:
                return IssuedProcurementSnapshot(**data)
        return None

    def list_snapshots(self, project_id: str) -> list[IssuedProcurementSnapshot]:
        directory = self.issued_root / project_id
        if not directory.exists():
            return []
        return [
            IssuedProcurementSnapshot(**json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(directory.glob("ADD-*.json"))
        ]

    # -- Proponent side -----------------------------------------------------

    def _receipt_path(self, workspace_id: str, receipt_id: str) -> Path:
        return self.receipt_root / workspace_id / f"{receipt_id}.json"

    def save_receipt(self, receipt: ProponentProcurementReceipt) -> ProponentProcurementReceipt:
        path = self._receipt_path(receipt.proponent_workspace_id, receipt.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
        tmp_path.write_text(
            json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tmp_path.replace(path)
        return receipt

    def get_receipt(self, receipt_id: str) -> Optional[ProponentProcurementReceipt]:
        for path in sorted(self.receipt_root.glob(f"*/{receipt_id}.json")):
            return ProponentProcurementReceipt(**json.loads(path.read_text(encoding="utf-8")))
        return None

    def list_receipts(self, proponent_workspace_id: str) -> list[ProponentProcurementReceipt]:
        directory = self.receipt_root / proponent_workspace_id
        if not directory.exists():
            return []
        return [
            ProponentProcurementReceipt(**json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(directory.glob("*.json"))
            if not p.name.startswith(".") and ".tmp-" not in p.name
        ]


# --- The three governed acts ----------------------------------------------


def issue_publication_snapshot(
    store: ProcurementBoundaryStore,
    project_id: str,
    addendum_seq: int,
    payload: dict[str, Any],
    issuer_user_id: str,
) -> IssuedProcurementSnapshot:
    """
    Owner side. Fix a payload as an immutable issued baseline and return it.

    The digest is taken over canonical bytes (see `canonical_payload_bytes`),
    and `payload_json` stores those exact bytes as text rather than a
    re-serialisation of the dict, so what was hashed and what was stored are
    the same object rather than two things that ought to agree.

    Note on `addendum_seq`: this is issuance *ordering* only. Nothing here
    relates one sequence to another, computes a delta, supersedes an earlier
    issue, or triggers re-adjudication on receipt — addendum lineage and
    delta-ingestion are NOT AUTHORIZED (`STATUS.md`'s Owner/Proponent
    publication row; GOV-P-004's own OUT OF SCOPE), and the absence of any
    relate-back machinery in this module is deliberate rather than unfinished.
    """
    _require_safe_id(project_id, "project_id")
    if not isinstance(addendum_seq, int) or isinstance(addendum_seq, bool) or addendum_seq < 0:
        raise ProcurementGovernanceError(
            f"addendum_seq must be a non-negative integer; got {addendum_seq!r}."
        )
    if not isinstance(payload, dict):
        raise ProcurementGovernanceError(
            f"payload must be a dict; got {type(payload).__name__}."
        )
    if not isinstance(issuer_user_id, str) or not issuer_user_id.strip():
        raise ProcurementGovernanceError("issuer_user_id is required.")

    canonical = canonical_payload_bytes(payload)
    digest = hashlib.sha256(canonical).hexdigest()
    snapshot = IssuedProcurementSnapshot(
        id=f"ISSUED-{project_id}-ADD-{addendum_seq:04d}-{digest[:8]}",
        project_id=project_id,
        addendum_sequence=addendum_seq,
        payload_json=canonical.decode("utf-8"),
        payload_sha256=digest,
        issued_by_user_id=issuer_user_id,
        issued_at=_now(),
    )
    store.write_snapshot_once(snapshot)
    return snapshot


def receive_into_airlock(
    store: ProcurementBoundaryStore,
    issued_snapshot_id: str,
    proponent_workspace_id: str,
) -> ProponentProcurementReceipt:
    """
    Proponent side. Record that an artifact arrived. Admit nothing.

    This is GOV-P-005's movement boundary and only that: the receipt lands in
    `ARRIVED_IN_AIRLOCK`, `admitted_at` is None, and `evidence_class` is
    `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED`. Arrival is not admission, and no
    argument to this function can make it one.

    Reading the snapshot here does not couple the two sides in the sense
    GOV-P-004 forbids. In deployment the artifact reaches the Proponent as a
    file a human moved; the store lookup is how a test and a co-located
    development environment stand in for that, and the direction is read-only
    in one direction. Nothing on this side ever writes to the issued store —
    which is what the invariant actually requires, and what
    `write_snapshot_once` would refuse anyway.
    """
    _require_safe_id(proponent_workspace_id, "proponent_workspace_id")
    snapshot = store.get_snapshot_by_id(issued_snapshot_id)
    if snapshot is None:
        raise ProcurementGovernanceError(
            f"No issued snapshot {issued_snapshot_id!r}. Nothing arrived, so nothing is staged."
        )

    receipt = ProponentProcurementReceipt(
        id=f"RECEIPT-{proponent_workspace_id}-{uuid.uuid4().hex[:12]}",
        proponent_workspace_id=proponent_workspace_id,
        issued_snapshot_id=snapshot.id,
        # Captured here, stored under the other root. See the module docstring
        # on why the receipt keeps its own copy of the digest.
        observed_sha256=snapshot.payload_sha256,
    )
    return store.save_receipt(receipt)


def evaluate_vestibule_admission(
    store: ProcurementBoundaryStore,
    receipt_id: str,
    validator_func: Optional[Callable[[dict[str, Any]], Optional[str]]] = None,
) -> ProponentProcurementReceipt:
    """
    Proponent side. Evaluate an arrived artifact at the vestibule and record
    the outcome.

    Integrity is checked three ways, against facts stored independently of one
    another: the payload as it reads on disk right now, the digest the issuer
    recorded inside the snapshot, and the digest the receiver observed at
    arrival and wrote under a different root. Editing the payload alone fails
    the first comparison; editing the payload and its digest together — the
    self-consistent tamper — still fails against the receipt.

    `validator_func` is an optional structural check over the payload. It
    returns None to accept, or a non-empty reason string to reject. A returned
    *reason* rather than a bool is what lets the rejection be recorded with
    something a person can act on, and it cannot accidentally pass by
    returning a truthy object the way `if validator(payload):` would.

    `ADMITTED` records that this evaluation passed. It confers no project
    authority: `evidence_class` is unchanged, and this function has no path
    that could change it. See the module docstring.
    """
    receipt = store.get_receipt(receipt_id)
    if receipt is None:
        raise ProcurementGovernanceError(f"No receipt {receipt_id!r}.")
    if receipt.admission_state in TERMINAL_ADMISSION_STATES:
        raise ProcurementGovernanceError(
            f"Receipt {receipt.id} is already {receipt.admission_state}. An admission "
            "decision is made once; re-evaluating it would let a rejection be quietly "
            "retried until it passed."
        )

    receipt.admission_state = ADMISSION_VESTIBULE_EVALUATING
    store.save_receipt(receipt)

    def _reject(reason: str) -> ProponentProcurementReceipt:
        receipt.admission_state = ADMISSION_REJECTED
        receipt.rejection_reason = reason
        receipt.admitted_at = None
        return store.save_receipt(receipt)

    snapshot = store.get_snapshot_by_id(receipt.issued_snapshot_id)
    if snapshot is None:
        return _reject(
            f"Issued snapshot {receipt.issued_snapshot_id} is no longer readable; "
            "integrity cannot be established."
        )

    try:
        recomputed = snapshot.recomputed_digest()
    except ProcurementGovernanceError as exc:
        return _reject(f"Payload is no longer canonically readable: {exc}")

    if recomputed != snapshot.payload_sha256:
        return _reject(
            "Payload integrity check failed: the issued payload does not match the "
            f"digest recorded with it (expected {snapshot.payload_sha256}, "
            f"recomputed {recomputed})."
        )
    if snapshot.payload_sha256 != receipt.observed_sha256:
        return _reject(
            "Payload integrity check failed: the issued digest does not match the "
            f"digest observed on arrival (issued {snapshot.payload_sha256}, "
            f"observed {receipt.observed_sha256})."
        )

    if validator_func is not None:
        reason = validator_func(snapshot.payload)
        if reason is not None:
            return _reject(str(reason))

    receipt.admission_state = ADMISSION_ADMITTED
    receipt.admitted_at = _now()
    receipt.rejection_reason = None
    return store.save_receipt(receipt)
