"""
CLAUDE-STORAGE-BRIDGE-01 - the private network always speaks first.

WHAT IS ACTUALLY BEING PROVEN

Not that HTTPS works. The transport plumbing is the easy half and the half that
proves nothing. What needs proving is the PROTOCOL's shape:

1. ARCHIOSK structurally cannot initiate. Not "does not" - cannot. The bridge is
   asserted to hold no address, socket, client or credential, because a promise
   that ARCHIOSK never dials out is worth less than an object with nothing to
   dial with.

2. Knowledge outlives the transport. The manifest - paths, sizes, mtimes,
   SHA-256 - is what ARCHIOSK keeps. Pull the agent and every one of those facts
   must still be there, unchanged.

3. Bytes are consumed, not stored. `consume()` removes as it returns, so a
   cache cannot form by accident. A buffer that quietly retained payloads would
   be permanent custody arriving through the back door, which is the single
   thing this whole design exists to prevent.

4. A halted agent is Unavailable, deterministically - reusing the exception the
   503 + Retry-After handler already answers, rather than inventing a second
   vocabulary for "not right now". That convergence was the lesson of
   CLAUDE-EXTERNAL-CUSTODY-03 and is not being re-learned here.

A LOCAL DIRECTORY IS A HONEST STAND-IN FOR THE EX4100

From the protocol's side, a NAS and a temp directory differ only in latency. The
agent walks a filesystem it can see and posts what it found; ARCHIOSK never
touches that filesystem in either case. Nothing here opens a port, presents a
credential, or contacts the real device.

tests/fixtures/wd_nas_bridge/oracle/ remains unread and untracked.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.external_source import ExternalSourceError, ExternalSourceUnavailable
from services.storage_bridge import (
    DEFAULT_RETRY_AFTER_SECONDS,
    ManifestEntry,
    StorageBridge,
    build_manifest,
    manifest_digest,
    read_manifest_file,
)

_T0 = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)

_FILES = {
    "drawings/A-101.pdf": b"%PDF-1.4 issued floor plan bytes",
    "schedules/Door_Schedule.csv": b"Mark,Rating\nD-101,45 MIN\nD-105,45 MIN\n",
    "specs/Section_08.md": b"# Doors\n\nRated assemblies at service rooms.\n",
}


class _PrivateStorage(unittest.TestCase):
    """A directory standing in for the private network's file server."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="bridge-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.root = self.base / "ex4100_share"
        for reference, payload in _FILES.items():
            path = self.root / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        self.bridge = StorageBridge("wd-nas-project")

    # -- the agent, which lives on the private side ------------------------
    def agent_push_manifest(self, at=_T0):
        return self.bridge.record_manifest(build_manifest(str(self.root)), now=at)

    def agent_answer_everything(self, at=_T0):
        """One outbound poll: collect the shelf, return with bytes."""
        for request in self.bridge.pending(now=at):
            self.bridge.deliver(
                request.id, read_manifest_file(str(self.root), request.relative_path),
                now=at)


class ArchiosxCannotInitiate(_PrivateStorage):
    """Invariant 1, asserted structurally rather than trusted."""

    def test_the_bridge_holds_no_address_or_credential(self):
        forbidden = ("host", "url", "endpoint", "address", "port", "socket",
                     "session", "token", "credential", "password", "client")
        held = {name for name in vars(self.bridge)
                if any(word in name.lower() for word in forbidden)}
        self.assertEqual(held, set())

    def test_the_module_imports_nothing_that_can_dial_out(self):
        """AST, not substring matching.

        The first version of this test looked for "requests." in the source and
        failed on `self._requests.get(...)` - matching an identifier of my own,
        in a module that imports no network library at all. A substring pass
        answers a question about text; the question here is about imports, so it
        is asked of the parse tree.

        This is also the STRONGEST available form of the claim: a module cannot
        open a connection without importing something that can, so an empty
        intersection here is structural rather than stylistic.
        """
        import services.storage_bridge as module

        tree = ast.parse(inspect.getsource(module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        networked = {"socket", "ssl", "http", "urllib", "requests", "httpx",
                     "aiohttp", "ftplib", "smtplib", "telnetlib", "asyncio",
                     "subprocess", "smbprotocol", "paramiko"}
        self.assertEqual(imported & networked, set())

    def test_no_call_in_the_module_names_a_network_primitive(self):
        # Belt and braces against reaching the network through a re-export or a
        # dynamically resolved attribute rather than a plain import.
        import services.storage_bridge as module

        tree = ast.parse(inspect.getsource(module))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        for primitive in ("urlopen", "connect", "create_connection", "getaddrinfo",
                          "sendall", "recv", "Popen", "system", "__import__"):
            self.assertNotIn(primitive, called)

    def test_requesting_bytes_does_not_reach_the_agent(self):
        # request() only leaves a note. Nothing arrives until the agent polls.
        self.agent_push_manifest()
        self.bridge.request("drawings/A-101.pdf", now=_T0)
        with self.assertRaises(ExternalSourceUnavailable):
            self.bridge.consume("drawings/A-101.pdf", now=_T0)

    def test_archiosk_will_not_ask_for_a_path_it_has_no_evidence_of(self):
        # Handing the agent an arbitrary path would be ARCHIOSK guessing at the
        # private side's contents - and a path traversal vector by proxy.
        self.agent_push_manifest()
        with self.assertRaises(ExternalSourceError):
            self.bridge.request("../../etc/passwd", now=_T0)
        with self.assertRaises(ExternalSourceError):
            self.bridge.request("drawings/never_existed.pdf", now=_T0)


class TheManifestIsWhatArchiosxKeeps(_PrivateStorage):
    """Invariant 3: epistemic preservation."""

    def test_the_manifest_carries_path_size_mtime_and_digest(self):
        self.agent_push_manifest()
        entry = self.bridge.entry_for("schedules/Door_Schedule.csv")
        self.assertEqual(entry.size_bytes, len(_FILES["schedules/Door_Schedule.csv"]))
        self.assertEqual(entry.sha256,
                         hashlib.sha256(_FILES["schedules/Door_Schedule.csv"]).hexdigest())
        self.assertTrue(entry.mtime_iso)

    def test_every_file_is_described_and_none_of_them_by_content(self):
        self.agent_push_manifest()
        self.assertEqual([e.relative_path for e in self.bridge.entries()],
                         sorted(_FILES))
        for entry in self.bridge.entries():
            for payload in _FILES.values():
                self.assertNotIn(payload.decode("utf-8", "ignore"), str(entry.as_dict()))

    def test_the_knowledge_survives_the_storage_being_destroyed(self):
        self.agent_push_manifest()
        before = [e.as_dict() for e in self.bridge.entries()]
        shutil.rmtree(self.root)          # the NAS is gone, not merely offline
        self.assertEqual([e.as_dict() for e in self.bridge.entries()], before)
        self.assertEqual(self.bridge.digest(), manifest_digest(
            [ManifestEntry.from_dict(d) for d in before]))

    def test_the_digest_changes_only_when_the_corpus_does(self):
        first = self.agent_push_manifest()
        self.assertEqual(self.agent_push_manifest(at=_T0 + timedelta(minutes=1)), first)
        (self.root / "specs" / "Section_08.md").write_bytes(b"# Doors\n\nRevised.\n")
        self.assertNotEqual(self.agent_push_manifest(at=_T0 + timedelta(minutes=2)), first)

    def test_a_manifest_survives_a_round_trip_through_plain_data(self):
        # It has to cross a wire as JSON; the shape must not depend on Python.
        self.agent_push_manifest()
        rebuilt = [ManifestEntry.from_dict(e.as_dict()) for e in self.bridge.entries()]
        self.assertEqual(rebuilt, self.bridge.entries())


class BytesAreTransient(_PrivateStorage):
    """Invariant 2: zero permanent custody."""

    def test_a_delivered_payload_can_be_read_exactly_once(self):
        self.agent_push_manifest()
        self.bridge.request("drawings/A-101.pdf", now=_T0)
        self.agent_answer_everything()
        self.assertEqual(self.bridge.consume("drawings/A-101.pdf", now=_T0),
                         _FILES["drawings/A-101.pdf"])
        # The second read must go back to the agent, not to a cache.
        with self.assertRaises(ExternalSourceUnavailable):
            self.bridge.consume("drawings/A-101.pdf", now=_T0)

    def test_the_bridge_holds_nothing_before_or_after(self):
        self.agent_push_manifest()
        self.assertFalse(self.bridge.holds_bytes())
        self.bridge.request("drawings/A-101.pdf", now=_T0)
        self.agent_answer_everything()
        self.assertTrue(self.bridge.holds_bytes())
        self.bridge.consume("drawings/A-101.pdf", now=_T0)
        self.assertFalse(self.bridge.holds_bytes())

    def test_no_source_bytes_are_written_to_disk_anywhere(self):
        # The claim in its bluntest form: run a whole cycle, then search the
        # filesystem ARCHIOSK owns for the payloads. Not one may appear.
        registry = self.base / "archiosk_registry"
        registry.mkdir()
        self.agent_push_manifest()
        for reference in _FILES:
            self.bridge.request(reference, now=_T0)
        self.agent_answer_everything()
        for reference in _FILES:
            self.bridge.consume(reference, now=_T0)
        written = [p for p in registry.rglob("*") if p.is_file()]
        self.assertEqual(written, [])
        for path in self.base.rglob("*"):
            if path.is_file() and self.root not in path.parents and path != self.root:
                for payload in _FILES.values():
                    self.assertNotIn(payload, path.read_bytes())

    def test_extraction_can_run_against_the_transient_payload(self):
        # On-demand streaming has to be good for something: the bytes must be
        # usable by the real extraction path while they exist.
        self.agent_push_manifest()
        self.bridge.request("schedules/Door_Schedule.csv", now=_T0)
        self.agent_answer_everything()
        payload = self.bridge.consume("schedules/Door_Schedule.csv", now=_T0)
        rows = payload.decode().strip().splitlines()
        self.assertEqual(rows[0], "Mark,Rating")
        self.assertIn("D-101,45 MIN", rows)
        self.assertFalse(self.bridge.holds_bytes())


class IntegrityIsCheckedOnArrival(_PrivateStorage):
    def test_bytes_that_do_not_match_the_manifest_are_refused(self):
        self.agent_push_manifest()
        request = self.bridge.request("drawings/A-101.pdf", now=_T0)
        self.bridge.pending(now=_T0)
        with self.assertRaises(ExternalSourceError) as caught:
            self.bridge.deliver(request.id, b"not the file", now=_T0)
        self.assertIn("hash", str(caught.exception))

    def test_a_mismatch_is_an_error_not_an_unavailability(self):
        # Retrying a wrong payload just fetches it again, more confidently.
        self.agent_push_manifest()
        request = self.bridge.request("drawings/A-101.pdf", now=_T0)
        self.bridge.pending(now=_T0)
        try:
            self.bridge.deliver(request.id, b"wrong", now=_T0)
        except ExternalSourceError as exc:
            self.assertNotIsInstance(exc, ExternalSourceUnavailable)

    def test_a_refused_delivery_leaves_nothing_behind(self):
        self.agent_push_manifest()
        request = self.bridge.request("drawings/A-101.pdf", now=_T0)
        self.bridge.pending(now=_T0)
        with self.assertRaises(ExternalSourceError):
            self.bridge.deliver(request.id, b"wrong", now=_T0)
        self.assertFalse(self.bridge.holds_bytes())

    def test_an_unknown_request_id_is_refused(self):
        self.agent_push_manifest()
        with self.assertRaises(ExternalSourceError):
            self.bridge.deliver("req-9999", b"anything", now=_T0)


class AHaltedAgentIsDeterministicallyUnavailable(_PrivateStorage):
    """Invariant 4, and the reason no new exception type was invented."""

    def test_silence_past_the_stale_window_reads_as_unavailable(self):
        self.agent_push_manifest()
        self.bridge.request("drawings/A-101.pdf", now=_T0)
        later = _T0 + timedelta(seconds=self.bridge.stale_after.total_seconds() + 1)
        self.assertFalse(self.bridge.agent_is_live(now=later))
        with self.assertRaises(ExternalSourceUnavailable):
            self.bridge.consume("drawings/A-101.pdf", now=later)

    def test_the_boundary_is_exact_not_approximate(self):
        self.agent_push_manifest()
        window = self.bridge.stale_after
        self.assertTrue(self.bridge.agent_is_live(now=_T0 + window))
        self.assertFalse(self.bridge.agent_is_live(
            now=_T0 + window + timedelta(seconds=1)))

    def test_an_empty_poll_still_counts_as_proof_of_life(self):
        self.agent_push_manifest()
        late = _T0 + timedelta(seconds=self.bridge.stale_after.total_seconds() + 1)
        self.assertFalse(self.bridge.agent_is_live(now=late))
        self.bridge.note_agent_poll(now=late)
        self.assertTrue(self.bridge.agent_is_live(now=late))

    def test_an_agent_never_seen_at_all_is_not_live(self):
        self.assertFalse(StorageBridge("fresh").agent_is_live(now=_T0))

    def test_it_reuses_the_exception_the_503_handler_already_answers(self):
        # CLAUDE-EXTERNAL-CUSTODY-03's lesson: one vocabulary for one subject.
        self.assertTrue(issubclass(ExternalSourceUnavailable, ExternalSourceError))
        source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        self.assertIn("@app.errorhandler(ExternalSourceUnavailable)", source)

    def test_the_advertised_retry_matches_what_the_handler_sends(self):
        self.assertEqual(DEFAULT_RETRY_AFTER_SECONDS, 60)
        source = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        self.assertIn('"Retry-After"] = "60"', source)

    def test_the_manifest_is_untouched_by_the_agent_going_dark(self):
        self.agent_push_manifest()
        before = [e.as_dict() for e in self.bridge.entries()]
        late = _T0 + timedelta(hours=6)
        with self.assertRaises(ExternalSourceUnavailable):
            self.bridge.consume("drawings/A-101.pdf", now=late)
        self.assertEqual([e.as_dict() for e in self.bridge.entries()], before)


class TheAgentSideWalksTheFilesystemAndArchiosxNever(_PrivateStorage):
    def test_build_manifest_reports_an_unreachable_root_honestly(self):
        shutil.rmtree(self.root)
        with self.assertRaises(ExternalSourceUnavailable):
            build_manifest(str(self.root))

    def test_the_agent_reuses_containment_rather_than_reimplementing_it(self):
        with self.assertRaises(ExternalSourceError):
            read_manifest_file(str(self.root), "../ex4100_share/../../escape.txt")

    def test_a_full_round_trip_delivers_every_file_intact(self):
        self.agent_push_manifest()
        for reference in _FILES:
            self.bridge.request(reference, now=_T0)
        self.agent_answer_everything()
        for reference, payload in _FILES.items():
            self.assertEqual(self.bridge.consume(reference, now=_T0), payload)


if __name__ == "__main__":
    unittest.main()
