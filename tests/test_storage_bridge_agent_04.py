"""
CLAUDE-STORAGE-BRIDGE-04 - the agent, driven against the real Flask app.

THE TEST THAT MATTERS MOST IS THE EQUIVALENCE ONE

tools/storage_bridge_agent.py implements manifest building and root containment a
SECOND time, because it must run on a NAS with no venv and cannot import
`services` without dragging in Flask and the whole application. Two
implementations of one rule is precisely the drift this repository warns about,
so TheTwoHalvesAgree asserts they produce identical entries and an identical
digest for the same directory. If they ever diverge, that fails here rather than
a NAS quietly advertising a corpus ARCHIOSK reads differently.

WHY A TRANSPORT SEAM RATHER THAN A LIVE SERVER

The agent talks through a transport object. In production that is urllib; here it
is the Flask test client. The alternative - an agent testable only by standing up
a listening socket - is an agent that in practice does not get tested, and this
one carries a credential and reads files off private storage.

Nothing here opens a port or contacts the real EX4100.

tests/fixtures/wd_nas_bridge/oracle/ remains unread and untracked.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from services.storage_agent_access import (
    enrol_agent, reset_bridges_for_testing, revoke_agent,
)

_ROOT = Path(__file__).resolve().parent.parent


def _load_agent_module():
    """Loaded by path: tools/ is not an importable package, and the agent must
    stay runnable as a bare file on a machine that has only this one script."""
    spec = importlib.util.spec_from_file_location(
        "storage_bridge_agent", _ROOT / "tools" / "storage_bridge_agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_module = _load_agent_module()

_FILES = {
    "drawings/A-101.pdf": b"%PDF-1.4 floor plan bytes",
    "schedules/Door_Schedule.csv": b"Mark,Rating\nD-101,45 MIN\n",
    "specs/Section_08.md": b"# Doors\n",
}


class _TestClientTransport:
    """Speaks the same shape as UrllibTransport, over the Flask test client."""

    def __init__(self, client):
        self.client = client
        self.calls = []

    def send(self, method, path, *, token, body=None, headers=None, json_body=None):
        request_headers = {"Authorization": "Bearer %s" % token}
        request_headers.update(headers or {})
        self.calls.append((method, path))
        if method == "GET":
            response = self.client.get(path, headers=request_headers)
        elif json_body is not None:
            response = self.client.post(path, json=json_body, headers=request_headers)
        else:
            response = self.client.post(path, data=body or b"", headers=request_headers)
        return agent_module.BridgeResponse(response.status_code, response.get_data())


class _AgentAgainstApp(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import db

        self.base = Path(tempfile.mkdtemp(prefix="agent-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.root = self.base / "ex4100_share"
        for reference, payload in _FILES.items():
            path = self.root / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        self.app = app_module.create_app("testing")
        self.addCleanup(reset_bridges_for_testing)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        db.create_all()
        _, self.token = enrol_agent("wd-project", "ex4100-office", actor="architect")

        self.transport = _TestClientTransport(self.app.test_client())
        self.logged = []
        self.agent = agent_module.StorageBridgeAgent(
            str(self.root), self.transport, self.token,
            log=self.logged.append)


class TheTwoHalvesAgree(unittest.TestCase):
    """The drift guard. Server-side and agent-side must be indistinguishable."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="equiv-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.root = self.base / "share"
        for reference, payload in _FILES.items():
            path = self.root / reference
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

    def test_the_manifests_are_identical(self):
        from services.storage_bridge import build_manifest as server_build

        server = [e.as_dict() for e in server_build(str(self.root))]
        agent = agent_module.build_manifest(str(self.root))
        self.assertEqual(agent, server)

    def test_the_digests_are_identical(self):
        from services.storage_bridge import (
            build_manifest as server_build, manifest_digest as server_digest,
        )
        from services.storage_bridge import ManifestEntry

        server = server_digest(server_build(str(self.root)))
        agent = agent_module.manifest_digest(agent_module.build_manifest(str(self.root)))
        self.assertEqual(agent, server)
        # And the server can re-digest the agent's own JSON to the same value.
        rebuilt = [ManifestEntry.from_dict(e)
                   for e in agent_module.build_manifest(str(self.root))]
        self.assertEqual(server_digest(rebuilt), server)

    def test_normalisation_agrees_on_the_awkward_cases(self):
        from services.external_source import normalize_relative_reference as server_norm

        for reference in ("a/b.pdf", "./a/b.pdf", "a\\b.pdf", "/a/b.pdf", "a//b.pdf"):
            with self.subTest(reference=reference):
                self.assertEqual(agent_module.normalize_relative_reference(reference),
                                 server_norm(reference))

    def test_both_refuse_upward_traversal(self):
        from services.external_source import (
            ExternalSourceError, normalize_relative_reference as server_norm,
        )

        with self.assertRaises(ValueError):
            agent_module.normalize_relative_reference("../secrets")
        with self.assertRaises(ExternalSourceError):
            server_norm("../secrets")


class TheAgentCompletesARealExchange(_AgentAgainstApp):
    def test_one_cycle_posts_a_manifest_and_finds_nothing_pending(self):
        self.assertTrue(self.agent.run_once())
        self.assertIn("/api/bridge/manifest", [p for _m, p in self.transport.calls])
        self.assertIn("/api/bridge/pending", [p for _m, p in self.transport.calls])
        self.assertTrue(any("manifest: 3 entries" in line for line in self.logged))

    def test_an_unchanged_manifest_is_not_re_uploaded(self):
        self.agent.run_once()
        before = self.transport.calls.count(("POST", "/api/bridge/manifest"))
        self.agent.run_once()
        self.assertEqual(self.transport.calls.count(("POST", "/api/bridge/manifest")),
                         before)

    def test_a_changed_file_causes_exactly_one_new_upload(self):
        self.agent.run_once()
        (self.root / "specs" / "Section_08.md").write_bytes(b"# Doors\n\nRevised.\n")
        self.agent.run_once()
        self.assertEqual(self.transport.calls.count(("POST", "/api/bridge/manifest")), 2)

    def test_it_streams_the_bytes_archiosk_asks_for(self):
        from services.storage_agent_access import bridge_for_token

        self.agent.run_once()
        bridge_for_token(self.token).request("drawings/A-101.pdf")
        self.agent.run_once()
        self.assertEqual(bridge_for_token(self.token).consume("drawings/A-101.pdf"),
                         _FILES["drawings/A-101.pdf"])

    def test_it_delivers_several_requests_in_one_cycle(self):
        from services.storage_agent_access import bridge_for_token

        self.agent.run_once()
        bridge = bridge_for_token(self.token)
        for reference in _FILES:
            bridge.request(reference)
        self.agent.run_once()
        for reference, payload in _FILES.items():
            self.assertEqual(bridge.consume(reference), payload)


class RevocationStopsTheAgentDead(_AgentAgainstApp):
    def test_a_401_raises_agent_stopped(self):
        self.agent.run_once()
        revoke_agent("wd-project", "ex4100-office", actor="architect")
        (self.root / "specs" / "Section_08.md").write_bytes(b"changed")
        with self.assertRaises(agent_module.AgentStopped):
            self.agent.run_once()

    def test_the_loop_exits_rather_than_retrying_forever(self):
        revoke_agent("wd-project", "ex4100-office", actor="architect")
        slept = []
        code = self.agent.run_forever(sleeper=slept.append)
        self.assertEqual(code, 2)
        self.assertEqual(slept, [])          # it must not sleep-and-retry

    def test_the_message_says_retrying_will_not_help(self):
        revoke_agent("wd-project", "ex4100-office", actor="architect")
        self.agent.run_forever(sleeper=lambda _s: None)
        self.assertTrue(any("will not help" in line for line in self.logged))


class ServerOutagesAreRiddenOut(_AgentAgainstApp):
    class _Down:
        def __init__(self, status):
            self.status = status
            self.calls = 0

        def send(self, *args, **kwargs):
            self.calls += 1
            return agent_module.BridgeResponse(self.status, b'{"retry_after": 0}')

    def _agent_against(self, status):
        return agent_module.StorageBridgeAgent(
            str(self.root), self._Down(status), self.token, interval=30,
            log=self.logged.append)

    def test_a_503_backs_off_instead_of_hammering(self):
        agent = self._agent_against(503)
        self.assertFalse(agent.run_once())
        self.assertGreaterEqual(agent.backoff, 30)

    def test_backoff_grows_and_is_capped(self):
        agent = self._agent_against(503)
        for _ in range(12):
            agent.run_once()
        self.assertLessEqual(agent.backoff, agent_module.MAX_BACKOFF_SECONDS)
        self.assertGreater(agent.backoff, 30)

    def test_a_dropped_connection_is_treated_like_a_503(self):
        agent = self._agent_against(0)       # transport returns status 0
        self.assertFalse(agent.run_once())
        self.assertGreaterEqual(agent.backoff, 30)

    def test_a_recovered_server_clears_the_backoff(self):
        self.agent.backoff = 240
        self.assertTrue(self.agent.run_once())
        self.assertEqual(self.agent.backoff, 0)

    def test_sleep_is_jittered_so_agents_do_not_synchronise(self):
        # Identical backoff turns a brief restart into a thundering herd.
        agent = self._agent_against(503)
        agent.run_once()
        waits = {round(agent.sleep_seconds(), 6) for _ in range(20)}
        self.assertGreater(len(waits), 1)

    def test_an_unmounted_share_is_survivable_not_fatal(self):
        shutil.rmtree(self.root)
        slept = []

        def stop_after_one(_seconds):
            slept.append(_seconds)
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.agent.run_forever(sleeper=stop_after_one)
        self.assertTrue(any("not reachable" in line for line in self.logged))
        self.assertEqual(len(slept), 1)      # it waited rather than exiting


class TheAgentGuardsItsOwnRoot(_AgentAgainstApp):
    def test_it_refuses_a_path_that_escapes_the_root(self):
        outside = self.base / "outside.txt"
        outside.write_bytes(b"not project data")
        sent = self.agent._deliver({"id": "req-0001", "relative_path": "../outside.txt"})
        self.assertFalse(sent)
        self.assertTrue(any("refusing" in line for line in self.logged))

    def test_it_refuses_an_absolute_path(self):
        self.assertFalse(
            self.agent._deliver({"id": "req-0001", "relative_path": "/etc/passwd"}))

    def test_a_symlink_out_of_the_root_is_refused(self):
        outside = self.base / "outside_secret.md"
        outside.write_bytes(b"secret")
        link = self.root / "escape.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted in this environment")
        self.assertFalse(
            self.agent._deliver({"id": "req-0001", "relative_path": "escape.md"}))

    def test_a_missing_file_is_refused_without_crashing_the_loop(self):
        self.assertFalse(
            self.agent._deliver({"id": "req-0001", "relative_path": "drawings/gone.pdf"}))


class TheCommandLineRefusesUnsafeUsage(unittest.TestCase):
    def test_there_is_no_token_argument(self):
        parser = agent_module.build_parser()
        options = {action.dest for action in parser._actions}
        self.assertIn("token_file", options)
        self.assertNotIn("token", options)

    def test_plain_http_is_refused(self):
        code = agent_module.main(["--root", ".", "--server", "http://archiosk.com"])
        self.assertEqual(code, 2)

    def test_dry_run_contacts_nothing_and_prints_a_manifest(self):
        import io
        from contextlib import redirect_stdout

        base = Path(tempfile.mkdtemp(prefix="dry-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        (base / "a.md").write_bytes(b"hello")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = agent_module.main(["--root", str(base), "--dry-run"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["entries"][0]["relative_path"], "a.md")
        self.assertEqual(len(payload["manifest_digest"]), 64)

    def test_the_agent_uses_only_the_standard_library(self):
        # It must run on a NAS with no venv, no pip and no build toolchain.
        import ast

        source = (_ROOT / "tools" / "storage_bridge_agent.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported & {"flask", "requests", "services", "models",
                                     "sqlalchemy", "werkzeug"}, set())


if __name__ == "__main__":
    unittest.main()
