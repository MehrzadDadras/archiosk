#!/usr/bin/env python3
"""
CLAUDE-STORAGE-BRIDGE-04 - the private-network half of the storage bridge.

Runs on any machine that can already see the storage: the NAS itself, a mini PC
beside it, a workstation with the share mounted. It reaches OUT to ARCHIOSK over
HTTPS and nothing ever reaches in, so no port is opened, no firewall rule
changes, and SMB stays exactly where it is - on the LAN.

    python3 tools/storage_bridge_agent.py \\
        --root /mnt/ex4100/ProjectSmokeDetector \\
        --server https://archiosk.com \\
        --token-file ~/.archiosk/agent.token

ZERO DEPENDENCIES, ON PURPOSE

Standard library only. A NAS or an office box should not need a venv, pip, or a
build toolchain to run this - the moment it does, it stops being something a
person can drop onto the machine that already has the share mounted, and starts
being a deployment project. That is also why this file imports nothing from
`services/`: that package pulls in Flask and the whole application, which cannot
be assumed present on the private side.

THE COST OF THAT, AND HOW IT IS PAID

Manifest building and root containment are therefore implemented twice - here,
and in services/storage_bridge.py. Two implementations of one rule is exactly
the drift this repository warns about, so tests/test_storage_bridge_agent_04.py
asserts the two produce IDENTICAL output for the same directory, including the
manifest digest. If they ever disagree, that test fails rather than a NAS
quietly reporting a corpus ARCHIOSK reads differently.

THE TOKEN IS NEVER AN ARGUMENT

--token-file or ARCHIOSK_BRIDGE_TOKEN, never --token. Command-line arguments are
visible to every user on the machine through `ps`, and they land in shell
history. The file should be chmod 600 and owned by whoever runs the agent.

WHAT THIS AGENT WILL NOT DO

It sends a manifest and, when asked, the bytes of a file inside the configured
root. It never accepts a path from ARCHIOSK that resolves outside that root -
checked AFTER resolution, so `..` and symlinks anywhere in the chain are both
caught. It never sends anything ARCHIOSK did not ask for by name, and it never
deletes, moves or writes to the storage. It has no code that could.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

USER_AGENT = "ARCHIOSK-StorageBridgeAgent/1.0"
DEFAULT_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 900


# ---------------------------------------------------------------------------
# manifest - must stay identical to services/storage_bridge.py
# ---------------------------------------------------------------------------

def normalize_relative_reference(relative_path: str) -> str:
    """Mirror of the server-side rule. Kept deliberately strict."""
    text = str(relative_path).replace("\\", "/").strip()
    if not text:
        raise ValueError("An empty reference is not a file.")
    pure = PurePosixPath(text)
    if pure.is_absolute():
        pure = PurePosixPath(*pure.parts[1:])
    parts = [p for p in pure.parts if p not in (".", "")]
    if any(p == ".." for p in parts):
        raise ValueError("An external source reference cannot traverse upward.")
    if not parts:
        raise ValueError("An empty reference is not a file.")
    return "/".join(parts)


def resolve_within_root(root: str, relative_path: str) -> Path:
    """Containment checked AFTER resolution.

    A prefix test on the raw string passes for a path that resolves outside, so
    the check has to happen once the filesystem has had its say - which is also
    what catches a symlink planted anywhere in the chain.
    """
    reference = normalize_relative_reference(relative_path)
    root_path = Path(root).expanduser().resolve()
    candidate = (root_path / reference).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError:
        raise ValueError("Resolved outside the configured storage root: %s" % relative_path)
    return candidate


def build_manifest(root: str) -> list:
    """Walk the storage and describe it. Contents never leave this function."""
    root_path = Path(root).expanduser().resolve()
    if not root_path.is_dir():
        raise FileNotFoundError("The storage root is not reachable: %s" % root)
    entries = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, PermissionError) as exc:
            print("  skipped %s (%s)" % (path, exc), file=sys.stderr)
            continue
        entries.append({
            "relative_path": normalize_relative_reference(
                str(path.relative_to(root_path))),
            "size_bytes": stat.st_size,
            "mtime_iso": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": digest,
        })
    return entries


def manifest_digest(entries) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(entries, key=lambda e: e["relative_path"]):
        hasher.update(("%s\x00%d\x00%s\x00%s\x1e" % (
            entry["relative_path"], entry["size_bytes"],
            entry["mtime_iso"], entry["sha256"])).encode())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------

class BridgeResponse:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}


class UrllibTransport:
    """The real one. Kept behind a seam so tests can drive the agent without a
    listening socket - the alternative is an agent that can only be tested by
    standing up a server, which means it mostly is not tested."""

    def __init__(self, server: str, timeout: int = 120):
        self.server = server.rstrip("/")
        self.timeout = timeout

    def send(self, method, path, *, token, body=None, headers=None, json_body=None):
        url = self.server + path
        data = body
        request_headers = {"User-Agent": USER_AGENT,
                           "Authorization": "Bearer %s" % token}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        elif body is not None:
            request_headers["Content-Type"] = "application/octet-stream"
        request_headers.update(headers or {})
        request = urllib.request.Request(url, data=data, method=method,
                                         headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return BridgeResponse(response.status, response.read())
        except urllib.error.HTTPError as exc:
            return BridgeResponse(exc.code, exc.read())
        except (urllib.error.URLError, OSError) as exc:
            # A dropped link is not a protocol answer. 0 means "no answer at
            # all", which the backoff treats exactly like a 503.
            return BridgeResponse(0, str(exc).encode())


class AgentStopped(Exception):
    """Raised when the agent must not continue - a revoked credential."""


class StorageBridgeAgent:
    def __init__(self, root, transport, token, *, interval=DEFAULT_INTERVAL_SECONDS,
                 log=print):
        self.root = str(Path(root).expanduser().resolve())
        self.transport = transport
        self.token = token
        self.interval = interval
        self.log = log
        self.last_digest = None
        self.backoff = 0

    # -- one full cycle ----------------------------------------------------
    def sync_manifest(self, *, force=False):
        """Post the manifest, but only when something actually changed.

        Re-uploading an identical manifest every 30 seconds would be pure noise
        on a domestic uplink, and it is the digest's whole purpose to make that
        comparison cheap.
        """
        entries = build_manifest(self.root)
        digest = manifest_digest(entries)
        if digest == self.last_digest and not force:
            return None
        response = self.transport.send(
            "POST", "/api/bridge/manifest", token=self.token,
            json_body={"entries": entries})
        self._raise_if_unauthorised(response)
        if response.status == 200:
            self.last_digest = digest
            self.log("manifest: %d entries, digest %s" % (len(entries), digest[:12]))
        return response

    def serve_pending(self):
        """Collect the shelf and answer it. Each file is read, sent, released."""
        response = self.transport.send("GET", "/api/bridge/pending", token=self.token)
        self._raise_if_unauthorised(response)
        if response.status != 200:
            return response
        delivered = 0
        for item in response.json().get("requests", []):
            if self._deliver(item):
                delivered += 1
        if delivered:
            self.log("delivered %d file(s)" % delivered)
        return response

    def _deliver(self, item):
        reference = item.get("relative_path", "")
        try:
            # Containment BEFORE opening. ARCHIOSK is not trusted to have sent a
            # safe path, even though it only ever echoes back one the agent
            # itself advertised.
            path = resolve_within_root(self.root, reference)
            payload = path.read_bytes()
        except (ValueError, OSError) as exc:
            self.log("refusing %r: %s" % (reference, exc))
            return False
        response = self.transport.send(
            "POST", "/api/bridge/deliver", token=self.token, body=payload,
            headers={"X-Bridge-Request-Id": item.get("id", "")})
        self._raise_if_unauthorised(response)
        if response.status != 200:
            self.log("delivery of %s refused: HTTP %s %s"
                     % (reference, response.status, response.json().get("message", "")))
            return False
        return True

    @staticmethod
    def _raise_if_unauthorised(response):
        if response.status == 401:
            raise AgentStopped(
                "This agent's enrolment is not authorised. It has been revoked, "
                "has expired, or the token is wrong. Re-enrol in ARCHIOSK and "
                "replace the token file; retrying will not help.")

    # -- the loop ----------------------------------------------------------
    def run_once(self):
        manifest = self.sync_manifest()
        pending = self.serve_pending()
        statuses = [r.status for r in (manifest, pending) if r is not None]
        if any(s in (0, 502, 503, 504) for s in statuses):
            self._back_off(pending)
            return False
        self.backoff = 0
        return True

    def _back_off(self, response):
        """Exponential with jitter, honouring Retry-After when offered.

        Jitter matters with more than one agent: identical backoff makes every
        agent retry in the same instant, turning a brief restart into a
        thundering herd against a server that has only just come back.
        """
        suggested = 0
        if response is not None:
            try:
                suggested = int((response.json() or {}).get("retry_after", 0))
            except (TypeError, ValueError):
                suggested = 0
        self.backoff = min(max(self.interval, self.backoff * 2, suggested),
                           MAX_BACKOFF_SECONDS)
        self.log("server unavailable; retrying in ~%ds" % self.backoff)

    def sleep_seconds(self):
        base = self.backoff or self.interval
        return base + random.uniform(0, base * 0.2)

    def run_forever(self, sleeper=time.sleep):
        self.log("agent started: root=%s interval=%ds" % (self.root, self.interval))
        while True:
            try:
                self.run_once()
            except AgentStopped as exc:
                self.log("STOPPING: %s" % exc)
                return 2
            except FileNotFoundError as exc:
                # The share is unmounted. That is not fatal and not a reason to
                # exit - the NAS may simply be asleep, and the agent should be
                # there when it wakes.
                self.log("storage not reachable: %s" % exc)
                self.backoff = min(max(self.interval, self.backoff * 2),
                                   MAX_BACKOFF_SECONDS)
            sleeper(self.sleep_seconds())


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def read_token(args) -> str:
    if args.token_file:
        token = Path(args.token_file).expanduser().read_text(encoding="utf-8").strip()
        if token:
            return token
    token = os.environ.get("ARCHIOSK_BRIDGE_TOKEN", "").strip()
    if token:
        return token
    raise SystemExit(
        "No token. Provide --token-file (chmod 600) or ARCHIOSK_BRIDGE_TOKEN.\n"
        "There is deliberately no --token argument: command-line arguments are "
        "visible to every user on this machine via `ps` and land in shell history.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="ARCHIOSK private-storage bridge agent (outbound only).")
    parser.add_argument("--root", required=True,
                        help="Directory to advertise. Nothing outside it is ever read.")
    parser.add_argument("--server", default="https://archiosk.com",
                        help="ARCHIOSK base URL.")
    parser.add_argument("--token-file", help="File containing the enrolment token.")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS,
                        help="Seconds between polls (default %d)." % DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true",
                        help="Run a single cycle and exit. Use this first.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build the manifest and print it. Contacts nothing.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.dry_run:
        entries = build_manifest(args.root)
        print(json.dumps({"entries": entries,
                          "manifest_digest": manifest_digest(entries)}, indent=2))
        return 0

    if not args.server.startswith("https://") and "localhost" not in args.server:
        print("Refusing to send a bearer token over plain HTTP.", file=sys.stderr)
        return 2

    agent = StorageBridgeAgent(args.root, UrllibTransport(args.server),
                               read_token(args), interval=args.interval)
    if args.once:
        try:
            agent.run_once()
        except AgentStopped as exc:
            print(exc, file=sys.stderr)
            return 2
        return 0
    return agent.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
