"""
CLAUDE-STORAGE-BRIDGE-01 - reading private storage without being able to reach it.

THE SHAPE OF THE PROBLEM

Authoritative project files live on storage the company controls - a WD My Cloud
EX4100, a file server, a NAS in an office cupboard. ARCHIOSK must be able to
discover and read them without SMB or port 445 being exposed to the internet,
and without keeping the bytes.

Every inbound answer to that fails for the same reason: it requires something on
the private network to accept a connection from outside. So the connection has
to run the other way, and this module is the ARCHIOSK-side half of a protocol
where the private network always speaks first.

OUTBOUND-ONLY IS STRUCTURAL HERE, NOT A POLICY

`StorageBridge` holds no address, no socket, no client, no credential, and no
method that reaches anything. It cannot contact the agent because there is
nothing in it capable of contacting anything - the same discipline
services/external_source.py uses for custody, where `file_path is None` IS the
claim rather than describing it. A test asserts the absence, because a promise
that ARCHIOSK never dials out is worth less than an object that cannot.

What ARCHIOSK does instead is leave requests on a shelf. The agent, running
inside the private network, polls outbound over HTTPS, takes what is on the
shelf, and comes back with bytes. If the agent stops polling, requests simply
sit there - which is exactly the honest failure, and is reported as
ExternalSourceUnavailable so the 503 + Retry-After handler that already exists
answers it. No new exception type, no second handler.

WHAT CROSSES, AND WHAT DOES NOT

A manifest crosses constantly: relative path, size, mtime, SHA-256. That is
metadata, it is small, and it is what makes ARCHIOSK's knowledge survive the
storage going away - the epistemic retention claim.

Bytes cross only when something actually needs them, once, and are consumed
rather than stored. `consume()` removes the payload as it returns it, so a
second read has to ask the agent again. That is deliberate friction: a buffer
that quietly kept bytes around would be permanent custody arriving by accident.

INTEGRITY IS CHECKED ON ARRIVAL

A delivery whose bytes do not hash to the manifest's own digest is refused with
ExternalSourceError, not Unavailable. A tampered or stale payload is a defect to
surface, never a transient condition to retry - retrying would just fetch the
wrong bytes again, more confidently.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from services.external_source import (
    ExternalSourceError,
    ExternalSourceForbidden,
    ExternalSourceUnavailable,
    normalize_relative_reference,
    resolve_within_root,
)

# How long after the agent's last contact ARCHIOSK stops believing in it. Long
# enough to ride out one missed poll on a domestic connection, short enough that
# "the NAS is off" does not look like "working" for minutes.
DEFAULT_AGENT_STALE_AFTER_SECONDS = 180

# What the 503 handler advertises. The agent's own poll interval is the floor -
# telling a client to come back sooner than the agent can possibly have answered
# is telling it to waste a request.
DEFAULT_RETRY_AFTER_SECONDS = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ManifestEntry:
    """One file as the private side sees it. Never its contents."""

    relative_path: str
    size_bytes: int
    mtime_iso: str
    sha256: str

    def as_dict(self) -> dict:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "mtime_iso": self.mtime_iso,
            "sha256": self.sha256,
        }

    @staticmethod
    def from_dict(payload: dict) -> "ManifestEntry":
        return ManifestEntry(
            relative_path=normalize_relative_reference(payload["relative_path"]),
            size_bytes=int(payload["size_bytes"]),
            mtime_iso=str(payload["mtime_iso"]),
            sha256=str(payload["sha256"]).lower(),
        )


def build_manifest(root: str) -> list[ManifestEntry]:
    """Runs on the PRIVATE side, never here.

    Kept in this module so both halves of the protocol are read together and
    cannot drift into disagreeing about what a manifest is - but nothing in
    ARCHIOSK's request path calls it. It walks a real filesystem, which is
    precisely the thing the ARCHIOSK side must never do.
    """
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise ExternalSourceUnavailable("The storage root is not reachable: %s" % root)
    entries = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        entries.append(ManifestEntry(
            relative_path=normalize_relative_reference(str(path.relative_to(root_path))),
            size_bytes=stat.st_size,
            mtime_iso=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        ))
    return entries


def read_manifest_file(root: str, reference: str) -> bytes:
    """Also private-side. Containment is reused, not re-implemented."""
    return resolve_within_root(root, reference).read_bytes()


def manifest_digest(entries: Iterable[ManifestEntry]) -> str:
    """One value that changes when anything about the corpus changes.

    Lets ARCHIOSK answer "has anything moved?" without diffing the whole list,
    and lets the agent skip an upload when nothing has.
    """
    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: e.relative_path):
        hasher.update(("%s\x00%d\x00%s\x00%s\x1e" % (
            entry.relative_path, entry.size_bytes, entry.mtime_iso, entry.sha256)).encode())
    return hasher.hexdigest()


@dataclass
class ByteRequest:
    id: str
    relative_path: str
    requested_at: datetime
    taken_at: Optional[datetime] = None


class StorageBridge:
    """The ARCHIOSK half. Deliberately incapable of reaching anything.

    There is no host, no port, no session, no token to present outward - only a
    shelf of requests the agent collects, and a slot the agent drops bytes into.
    """

    def __init__(self, project_id: str, *,
                 stale_after_seconds: int = DEFAULT_AGENT_STALE_AFTER_SECONDS,
                 retry_after_seconds: int = DEFAULT_RETRY_AFTER_SECONDS):
        self.project_id = project_id
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self.retry_after_seconds = retry_after_seconds
        self._entries: dict[str, ManifestEntry] = {}
        self._requests: dict[str, ByteRequest] = {}
        self._delivered: dict[str, bytes] = {}
        self.agent_last_seen: Optional[datetime] = None
        self.manifest_recorded_at: Optional[datetime] = None
        self._sequence = 0

    # -- what the agent pushes inbound ------------------------------------
    def record_manifest(self, entries: Iterable[ManifestEntry], *,
                        now: Optional[datetime] = None) -> str:
        """The agent has walked the storage and is telling us what is there."""
        moment = now or _now()
        entries = list(entries)
        self._entries = {entry.relative_path: entry for entry in entries}
        self.manifest_recorded_at = moment
        self.agent_last_seen = moment
        return manifest_digest(entries)

    def note_agent_poll(self, *, now: Optional[datetime] = None) -> None:
        """An empty poll is still proof of life, and must count as one."""
        self.agent_last_seen = now or _now()

    # -- what ARCHIOSK knows without any contact ---------------------------
    def entries(self) -> list[ManifestEntry]:
        return sorted(self._entries.values(), key=lambda e: e.relative_path)

    def entry_for(self, relative_path: str) -> Optional[ManifestEntry]:
        return self._entries.get(normalize_relative_reference(relative_path))

    def digest(self) -> str:
        return manifest_digest(self._entries.values())

    def agent_is_live(self, *, now: Optional[datetime] = None) -> bool:
        if self.agent_last_seen is None:
            return False
        return (now or _now()) - self.agent_last_seen <= self.stale_after

    # -- the shelf ---------------------------------------------------------
    def request(self, relative_path: str, *, now: Optional[datetime] = None) -> ByteRequest:
        """Leave a request. This does NOT reach the agent - nothing here can.

        Refuses a path the manifest has never mentioned: ARCHIOSK asking for a
        file it has no evidence exists would be guessing at the private side's
        contents, and the agent should never be handed a path to go looking for.
        """
        reference = normalize_relative_reference(relative_path)
        if reference not in self._entries:
            raise ExternalSourceError(
                "%s is not in the last manifest; ARCHIOSK will not ask the agent "
                "for a path it has no evidence of." % reference)
        self._sequence += 1
        request = ByteRequest(id="req-%04d" % self._sequence, relative_path=reference,
                              requested_at=now or _now())
        self._requests[request.id] = request
        return request

    def pending(self, *, now: Optional[datetime] = None) -> list[ByteRequest]:
        """Called by the agent's outbound poll. Marks the requests as taken."""
        moment = now or _now()
        self.agent_last_seen = moment
        outstanding = [r for r in self._requests.values() if r.taken_at is None]
        for request in outstanding:
            request.taken_at = moment
        return outstanding

    def deliver(self, request_id: str, payload: bytes, *,
                now: Optional[datetime] = None) -> None:
        """The agent has come back with bytes.

        Verified against the manifest before acceptance. A mismatch is
        ExternalSourceError, never Unavailable - retrying a wrong payload just
        fetches it again.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise ExternalSourceError("Unknown byte request %s." % request_id)
        entry = self._entries.get(request.relative_path)
        if entry is None:
            raise ExternalSourceError(
                "%s left the manifest while its bytes were in flight."
                % request.relative_path)
        digest = hashlib.sha256(payload).hexdigest()
        if digest != entry.sha256:
            raise ExternalSourceError(
                "Delivered bytes for %s hash to %s but the manifest says %s."
                % (request.relative_path, digest, entry.sha256))
        self._delivered[request.relative_path] = payload
        self.agent_last_seen = now or _now()
        self._requests.pop(request_id, None)

    # -- transient consumption --------------------------------------------
    def consume(self, relative_path: str, *, now: Optional[datetime] = None) -> bytes:
        """Take the bytes AND drop them. One read, then they are gone.

        A cache here would be permanent custody arriving by accident, so a
        second read must go back to the agent. That is the point, not an
        oversight.
        """
        reference = normalize_relative_reference(relative_path)
        if reference in self._delivered:
            return self._delivered.pop(reference)
        if not self.agent_is_live(now=now):
            raise ExternalSourceUnavailable(
                "The storage agent for %s has not been heard from; %s cannot be "
                "read right now." % (self.project_id, reference))
        raise ExternalSourceUnavailable(
            "%s has been requested from the storage agent but has not arrived "
            "yet." % reference)

    def holds_bytes(self) -> bool:
        """True only between a delivery and its single consumption."""
        return bool(self._delivered)


# ---------------------------------------------------------------------------
# enrolment: which agent may speak for which project
# ---------------------------------------------------------------------------

DEFAULT_ENROLMENT_TTL_SECONDS = 90 * 24 * 3600


class BridgeEnrolmentRevoked(ExternalSourceError):
    """This agent is no longer authorised to speak for this project.

    A SIBLING of ExternalSourceUnavailable/Forbidden rather than either of them,
    because the required human action differs and that is the only thing an
    error type is really for:

        Unavailable      -> wait, or go and switch the NAS on
        Forbidden        -> fix permissions ON THE STORAGE
        EnrolmentRevoked -> re-enrol the agent IN ARCHIOSK

    Answering any of the three with another's advice sends someone to the wrong
    system. Same reasoning that already separates "currently unavailable" from
    "deliberately removed".

    Revocation deliberately does NOT touch governed Sources. A withdrawn
    credential means bytes stop arriving; it never means the project forgets
    what it knew.
    """


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass
class Enrolment:
    """A project's agent. The raw token is NOT here and never was.

    Mirrors the shape PasswordResetToken and VerificationAccessToken already
    established: only `token_hash` is ever retained, so the stored record cannot
    be replayed even by whoever holds it.
    """

    project_id: str
    agent_label: str
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None

    def is_valid(self, *, now: Optional[datetime] = None) -> bool:
        moment = now or _now()
        return self.revoked_at is None and moment <= self.expires_at


class BridgeRegistry:
    """The one place a bridge can be obtained, and only ever by presenting a token.

    Project isolation is STRUCTURAL here. There is no method that takes a
    project_id and returns its bridge; the only route in is `bridge_for(token)`,
    and a token resolves to exactly one enrolment, which names exactly one
    project. An agent enrolled for Project A cannot ask for Project B because
    there is no call that would express the question - the same reasoning
    visible_cases_for records for Case privacy, where filtering the raw list
    directly is what caused a real disclosure.

    ARCHIOSK never learns a NAS credential. The agent authenticates ITSELF to
    ARCHIOSK; how it reaches its own storage is its own business, on its own
    side of the boundary, and nothing in this class could carry such a secret
    even if someone tried to pass one.
    """

    def __init__(self, *, stale_after_seconds: int = DEFAULT_AGENT_STALE_AFTER_SECONDS):
        self._enrolments: dict[str, Enrolment] = {}      # token_hash -> Enrolment
        self._bridges: dict[str, StorageBridge] = {}     # project_id -> bridge
        self._stale_after_seconds = stale_after_seconds

    # -- issuing ----------------------------------------------------------
    def enrol(self, project_id: str, agent_label: str, *,
              now: Optional[datetime] = None,
              ttl_seconds: int = DEFAULT_ENROLMENT_TTL_SECONDS) -> tuple[Enrolment, str]:
        """Returns the record and the raw token, which is shown exactly once.

        The raw value exists in this return and nowhere else - not in the
        registry, not in the Enrolment, not in any log.
        """
        moment = now or _now()
        raw_token = secrets.token_urlsafe(32)
        enrolment = Enrolment(
            project_id=project_id, agent_label=agent_label,
            token_hash=_hash_token(raw_token), issued_at=moment,
            expires_at=moment + timedelta(seconds=ttl_seconds))
        self._enrolments[enrolment.token_hash] = enrolment
        return enrolment, raw_token

    def revoke(self, project_id: str, agent_label: str, *,
               now: Optional[datetime] = None) -> int:
        moment = now or _now()
        revoked = 0
        for enrolment in self._enrolments.values():
            if (enrolment.project_id == project_id
                    and enrolment.agent_label == agent_label
                    and enrolment.revoked_at is None):
                enrolment.revoked_at = moment
                revoked += 1
        return revoked

    # -- the chokepoint ---------------------------------------------------
    def authorise(self, raw_token: str, *, now: Optional[datetime] = None) -> Enrolment:
        enrolment = self._enrolments.get(_hash_token(raw_token or ""))
        if enrolment is None:
            # Unknown and revoked are reported identically on purpose: a caller
            # probing tokens must not be able to tell "wrong" from "used to be
            # right", which would confirm that a project has an agent at all.
            raise BridgeEnrolmentRevoked("This storage agent is not authorised.")
        if not enrolment.is_valid(now=now):
            raise BridgeEnrolmentRevoked(
                "The enrolment for %s has been revoked or has expired."
                % enrolment.agent_label)
        return enrolment

    def bridge_for(self, raw_token: str, *, now: Optional[datetime] = None) -> StorageBridge:
        """The ONLY way to reach a bridge. No project_id parameter exists."""
        enrolment = self.authorise(raw_token, now=now)
        bridge = self._bridges.get(enrolment.project_id)
        if bridge is None:
            bridge = StorageBridge(enrolment.project_id,
                                   stale_after_seconds=self._stale_after_seconds)
            self._bridges[enrolment.project_id] = bridge
        return bridge

    def knows_project(self, project_id: str) -> bool:
        """For assertions about state - deliberately returns no bridge."""
        return project_id in self._bridges
