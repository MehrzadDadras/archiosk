"""
CLAUDE-STORAGE-BRIDGE-01, reduced by -07 to what is genuinely shared.

WHAT THIS FILE IS NOW

services/storage_bridge.py used to hold an in-memory StorageBridge and
BridgeRegistry as well as the manifest vocabulary. Phase 2 proved the in-memory
half could not survive fifteen gunicorn workers, so it was DELETED and replaced
by durable state - the manifest on ProjectWorkspace, the queue on the filesystem,
the credential in the database.

Its properties did not disappear with it; they moved to
test_storage_bridge_durable_05.py and test_storage_bridge_trust_02.py, where they
are asserted against the implementation that actually runs. What is left here is
the part that was always shared and never process-local: the manifest
vocabulary, the digest both halves must agree on, and the private-side walk.

THE OUTBOUND-ONLY GUARD STAYS HERE

It is a property of the MODULE, not of any object, so deleting the classes did
not weaken it. ARCHIOSK cannot dial out because nothing in this module imports
anything capable of it - asserted by AST, because a promise is worth less than an
absence.

tests/fixtures/wd_nas_bridge/oracle/ remains unread and untracked.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import shutil
import tempfile
import unittest
from pathlib import Path

from services.external_source import ExternalSourceError, ExternalSourceUnavailable
from services.storage_bridge import (
    ManifestEntry, build_manifest, manifest_digest, read_manifest_file,
)

_FILES = {
    "drawings/A-101.pdf": b"%PDF-1.4 issued floor plan bytes",
    "schedules/Door_Schedule.csv": b"Mark,Rating\nD-101,45 MIN\nD-105,45 MIN\n",
    "specs/Section_08.md": b"# Doors\n\nRated assemblies at service rooms.\n",
}


class _PrivateStorage(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="bridge-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.root = self.base / "ex4100_share"
        for reference, payload in _FILES.items():
            path = self.root / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)


class ArchiosxCannotInitiate(unittest.TestCase):
    """A property of the module, unaffected by the classes that were removed."""

    def test_the_module_imports_nothing_that_can_dial_out(self):
        """AST, not substring matching.

        An earlier version looked for "requests." in the source and failed on a
        `self._requests.get(...)` identifier of its own, in a module importing no
        network library at all. A substring pass answers a question about text;
        the question here is about imports, so it is asked of the parse tree -
        and that is the stronger claim anyway, since a module cannot open a
        connection without importing something that can.
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
        import services.storage_bridge as module

        called = set()
        for node in ast.walk(ast.parse(inspect.getsource(module))):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    called.add(func.attr)
                elif isinstance(func, ast.Name):
                    called.add(func.id)
        for primitive in ("urlopen", "connect", "create_connection", "getaddrinfo",
                          "sendall", "recv", "Popen", "system", "__import__"):
            self.assertNotIn(primitive, called)

    def test_the_in_memory_implementation_is_gone_not_deprecated(self):
        # Two implementations of one protocol is the duplication this work has
        # already had to converge away from once.
        import services.storage_bridge as module

        for dead in ("StorageBridge", "BridgeRegistry", "ByteRequest", "Enrolment"):
            self.assertFalse(hasattr(module, dead), "%s survived deletion" % dead)


class TheManifestDescribesWithoutRevealing(_PrivateStorage):
    def test_it_carries_path_size_mtime_and_digest(self):
        entries = {e.relative_path: e for e in build_manifest(str(self.root))}
        entry = entries["schedules/Door_Schedule.csv"]
        payload = _FILES["schedules/Door_Schedule.csv"]
        self.assertEqual(entry.size_bytes, len(payload))
        self.assertEqual(entry.sha256, hashlib.sha256(payload).hexdigest())
        self.assertTrue(entry.mtime_iso)

    def test_it_never_carries_content(self):
        for entry in build_manifest(str(self.root)):
            rendered = str(entry.as_dict())
            for payload in _FILES.values():
                self.assertNotIn(payload.decode("utf-8", "ignore"), rendered)

    def test_every_file_is_described(self):
        self.assertEqual(
            sorted(e.relative_path for e in build_manifest(str(self.root))),
            sorted(_FILES))

    def test_a_manifest_survives_a_round_trip_through_plain_data(self):
        # It has to cross a wire as JSON; the shape must not depend on Python.
        entries = build_manifest(str(self.root))
        rebuilt = [ManifestEntry.from_dict(e.as_dict()) for e in entries]
        self.assertEqual(rebuilt, entries)
        self.assertEqual(manifest_digest(rebuilt), manifest_digest(entries))


class TheDigestChangesOnlyWhenTheCorpusDoes(_PrivateStorage):
    def test_an_identical_walk_produces_an_identical_digest(self):
        self.assertEqual(manifest_digest(build_manifest(str(self.root))),
                         manifest_digest(build_manifest(str(self.root))))

    def test_a_content_change_moves_it(self):
        before = manifest_digest(build_manifest(str(self.root)))
        (self.root / "specs" / "Section_08.md").write_bytes(b"# Doors\n\nRevised.\n")
        self.assertNotEqual(manifest_digest(build_manifest(str(self.root))), before)

    def test_a_rename_moves_it_too(self):
        before = manifest_digest(build_manifest(str(self.root)))
        (self.root / "specs" / "Section_08.md").rename(
            self.root / "specs" / "Section_08_Rev1.md")
        self.assertNotEqual(manifest_digest(build_manifest(str(self.root))), before)

    def test_it_does_not_depend_on_walk_order(self):
        entries = build_manifest(str(self.root))
        self.assertEqual(manifest_digest(list(reversed(entries))),
                         manifest_digest(entries))


class TheAgentSideWalksTheFilesystemAndArchiosxNever(_PrivateStorage):
    def test_build_manifest_reports_an_unreachable_root_honestly(self):
        shutil.rmtree(self.root)
        with self.assertRaises(ExternalSourceUnavailable):
            build_manifest(str(self.root))

    def test_reading_reuses_containment_rather_than_reimplementing_it(self):
        with self.assertRaises(ExternalSourceError):
            read_manifest_file(str(self.root), "../ex4100_share/../../escape.txt")

    def test_a_real_file_reads_back_byte_for_byte(self):
        for reference, payload in _FILES.items():
            self.assertEqual(read_manifest_file(str(self.root), reference), payload)


if __name__ == "__main__":
    unittest.main()
