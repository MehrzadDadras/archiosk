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

This module holds no address, no socket, no client and no credential, and has no
function that reaches anything. It cannot contact the agent because there is
nothing in it capable of contacting anything - the same discipline
services/external_source.py uses for custody, where `file_path is None` IS the
claim rather than describing it. A test asserts the absence by AST, because a
promise that ARCHIOSK never dials out is worth less than a module that cannot.

What ARCHIOSK does instead is leave requests on a shelf. The agent, running
inside the private network, polls outbound over HTTPS, takes what is on the
shelf, and comes back with bytes. If the agent stops polling, requests simply
sit there - which is exactly the honest failure.

CLAUDE-STORAGE-BRIDGE-07 REMOVED THE IN-MEMORY HALF

An earlier version of this module carried StorageBridge/BridgeRegistry/Enrolment
- a per-process shelf and credential registry. Phase 2 proved in production why
that could not stand: fifteen gunicorn workers, so a manifest recorded in one was
invisible to the other fourteen. They are deleted rather than deprecated, because
two implementations of one protocol is the duplication this work has already had
to converge away from once. The shelf is now services/bridge_queue.py, the
credential is models.StorageAgentEnrolment, and the manifest lives on the project
record. What remains here is what was always genuinely shared: the manifest
vocabulary and the digest both sides must agree on.

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


