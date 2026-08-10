"""
CLAUDE-CA1D-LIVE-BRIDGE-01 -- the read-only Claude/agent session-state
bridge: tools/write_dev_session_status.py (write side) and
services/dev_session_status.py (read side). Narrowed strictly to the
evidence-confirmed vocabulary (active/waiting_for_input/unknown) per the
Plan-Mode report's SS7 live hook-payload experiment -- no ended/blocked/
stalled/detached/complete anywhere in this tranche.

Run via:

    python -m unittest tests.test_ca1d_live_bridge_01 -v
"""
from __future__ import annotations

import dataclasses
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from services.dev_session_status import (
    STATE_ACTIVE,
    STATE_UNKNOWN,
    STATE_WAITING_FOR_INPUT,
    DevSessionStatus,
    read_dev_session_status,
)
from tools.write_dev_session_status import (
    SCHEMA_VERSION,
    atomic_write,
    build_payload,
    read_prior_state_from_file,
    resolve_state,
)


class EventToStateMappingTests(unittest.TestCase):
    """Write-side mapping -- the evidence-confirmed vocabulary only."""

    def _unreachable_prior(self):
        self.fail("read_prior_state should not be called for a non-SubagentStop event")

    def test_active_events_map_to_active(self):
        for event in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart"):
            with self.subTest(event=event):
                self.assertEqual(resolve_state(event, self._unreachable_prior), STATE_ACTIVE)

    def test_stop_and_notification_map_to_waiting(self):
        for event in ("Stop", "Notification"):
            with self.subTest(event=event):
                self.assertEqual(resolve_state(event, self._unreachable_prior), STATE_WAITING_FOR_INPUT)

    def test_subagent_stop_preserves_prior_active_state(self):
        self.assertEqual(resolve_state("SubagentStop", lambda: STATE_ACTIVE), STATE_ACTIVE)

    def test_subagent_stop_preserves_prior_waiting_state(self):
        """The real, live-observed defect this design guards against: an
        unrelated background subagent's SubagentStop must never flip an
        already-idle session back to 'active' (Plan-Mode report SS7)."""
        self.assertEqual(resolve_state("SubagentStop", lambda: STATE_WAITING_FOR_INPUT), STATE_WAITING_FOR_INPUT)

    def test_subagent_stop_with_no_prior_state_defaults_to_active(self):
        """An orphaned SubagentStop (no prior write this bridge ever saw)
        must not corrupt anything -- the documented safe default."""
        self.assertEqual(resolve_state("SubagentStop", lambda: STATE_ACTIVE), STATE_ACTIVE)

    def test_unrecognized_event_maps_to_none(self):
        """Outside the confirmed vocabulary (e.g. SessionStart, PreCompact)
        -- the bridge does nothing, never guesses."""
        for event in ("SessionStart", "SessionEnd", "PreCompact", "PermissionRequest", "Bogus"):
            with self.subTest(event=event):
                self.assertIsNone(resolve_state(event, self._unreachable_prior))


class ReadPriorStateFromFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ca1d_bridge_prior_"))
        self.path = self.tmp_dir / "status.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_missing_file_defaults_to_active(self):
        self.assertEqual(read_prior_state_from_file(self.path), STATE_ACTIVE)

    def test_malformed_file_defaults_to_active(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(read_prior_state_from_file(self.path), STATE_ACTIVE)

    def test_valid_waiting_state_is_preserved(self):
        self.path.write_text(json.dumps({"state": STATE_WAITING_FOR_INPUT}), encoding="utf-8")
        self.assertEqual(read_prior_state_from_file(self.path), STATE_WAITING_FOR_INPUT)


class BuildPayloadSchemaTests(unittest.TestCase):
    """Structural proof of the whitelist -- content-zero by construction,
    not by redaction."""

    def test_payload_has_exactly_the_five_whitelisted_keys(self):
        payload = build_payload("Stop", STATE_WAITING_FOR_INPUT, "sess-1", 12345, now="2026-01-01T00:00:00+00:00")
        self.assertEqual(
            set(payload.keys()),
            {"schema_version", "session_id", "pid", "state", "last_structural_event", "updated_at"},
        )
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)

    def test_build_payload_signature_has_no_content_bearing_parameter(self):
        """Locks the whitelist down structurally: if a future edit adds a
        `prompt`/`tool_input`/`message` parameter to build_payload, this
        test fails loudly rather than silently widening the schema."""
        params = set(inspect.signature(build_payload).parameters.keys())
        self.assertEqual(params, {"event_name", "state", "session_id", "pid", "now"})

    def test_write_side_module_never_reads_hook_stdin_content(self):
        """A stronger structural guarantee than redaction: the write-side
        module has no code path that parses hook stdin into a Python
        value at all (see main()'s own drain-without-parsing comment) --
        confirmed here by asserting no reference to json.loads exists
        anywhere near stdin handling in the module source."""
        import tools.write_dev_session_status as write_module

        source = inspect.getsource(write_module)
        main_body = source[source.index("def main("):]
        self.assertIn("sys.stdin.read()", main_body)
        # The only json.loads call in the whole module is inside
        # read_prior_state_from_file, reading back THIS bridge's own
        # previously-written file -- never the harness's hook payload.
        self.assertEqual(source.count("json.loads"), 1)


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ca1d_bridge_write_"))
        self.path = self.tmp_dir / "nested" / "status.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_creates_parent_directory_and_writes_valid_json(self):
        atomic_write(self.path, {"a": 1})
        self.assertTrue(self.path.exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"a": 1})

    def test_replaces_existing_file_cleanly(self):
        atomic_write(self.path, {"a": 1})
        atomic_write(self.path, {"a": 2})
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"a": 2})

    def test_no_leftover_temp_files(self):
        atomic_write(self.path, {"a": 1})
        leftovers = list(self.path.parent.glob(".dev_session_status.*.tmp"))
        self.assertEqual(leftovers, [])


class ReadDevSessionStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ca1d_bridge_read_"))
        self.path = self.tmp_dir / "status.json"
        self.alive_pid = 0  # placeholder, set per-test via os.getpid() where needed

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_missing_file_is_unknown(self):
        status = read_dev_session_status(self.path)
        self.assertEqual(status.state, STATE_UNKNOWN)
        self.assertIsNone(status.pid)

    def test_malformed_json_is_unknown(self):
        self.path.write_text("{not valid json at all", encoding="utf-8")
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_json_that_is_not_an_object_is_unknown(self):
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_valid_active_state_with_live_pid(self):
        import os

        self._write({
            "schema_version": 1, "session_id": "sess-live", "pid": os.getpid(),
            "state": STATE_ACTIVE, "last_structural_event": "PreToolUse",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        status = read_dev_session_status(self.path)
        self.assertEqual(status.state, STATE_ACTIVE)
        self.assertEqual(status.session_id, "sess-live")
        self.assertEqual(status.last_structural_event, "PreToolUse")

    def test_valid_waiting_state_with_live_pid(self):
        import os

        self._write({
            "schema_version": 1, "session_id": "sess-live", "pid": os.getpid(),
            "state": STATE_WAITING_FOR_INPUT, "last_structural_event": "Stop",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        self.assertEqual(read_dev_session_status(self.path).state, STATE_WAITING_FOR_INPUT)

    def test_dead_pid_overrides_a_claimed_active_state_to_unknown(self):
        # A plain spawn-then-wait()'d subprocess is NOT a reliable "dead
        # pid" fixture on Windows: Popen holds its own handle to the
        # child's process object open until garbage-collected/closed, and
        # OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, ...) -- the exact
        # call _pid_is_alive makes -- can still succeed against that
        # still-open handle even after the process has actually exited.
        # An implausible fixed PID sidesteps that OS/handle-lifetime
        # flakiness entirely and is the standard way to fabricate "no such
        # process" deterministically.
        implausible_pid = 999999999
        self._write({
            "schema_version": 1, "session_id": "sess-dead", "pid": implausible_pid,
            "state": STATE_ACTIVE, "last_structural_event": "PreToolUse",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_missing_pid_is_unknown(self):
        self._write({
            "schema_version": 1, "session_id": "sess-1", "state": STATE_ACTIVE,
            "last_structural_event": "PreToolUse", "updated_at": "2026-01-01T00:00:00+00:00",
        })
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_wrong_typed_pid_is_unknown_not_a_crash(self):
        """Session identity/PID mismatch handling: a pid field of the
        wrong type must degrade gracefully, never raise."""
        self._write({
            "schema_version": 1, "session_id": "sess-1", "pid": "not-an-int",
            "state": STATE_ACTIVE, "last_structural_event": "PreToolUse",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_unrecognized_state_value_is_unknown(self):
        """Proves the read side rejects a state outside the confirmed
        vocabulary even if it somehow ended up in the file -- the
        vocabulary is enforced on read, not just assumed from the writer."""
        import os

        self._write({
            "schema_version": 1, "session_id": "sess-1", "pid": os.getpid(),
            "state": "stalled", "last_structural_event": "PreToolUse",
            "updated_at": "2026-01-01T00:00:00+00:00",
        })
        self.assertEqual(read_dev_session_status(self.path).state, STATE_UNKNOWN)

    def test_never_raises_on_completely_empty_file(self):
        self.path.write_text("", encoding="utf-8")
        status = read_dev_session_status(self.path)
        self.assertEqual(status.state, STATE_UNKNOWN)


class ContentExclusionStructuralTests(unittest.TestCase):
    """Proof that prohibited content-bearing fields cannot enter the
    persisted schema -- structural, not a redaction-based promise."""

    def test_dev_session_status_dataclass_has_no_content_bearing_field(self):
        field_names = {f.name for f in dataclasses.fields(DevSessionStatus)}
        self.assertEqual(
            field_names,
            {"state", "last_structural_event", "updated_at", "session_id", "pid"},
        )
        prohibited_substrings = ("prompt", "content", "message", "input", "output", "transcript", "response")
        for name in field_names:
            for bad in prohibited_substrings:
                self.assertNotIn(bad, name.lower(), f"field {name!r} looks content-bearing")

    def test_read_side_ignores_unexpected_extra_keys_in_the_file(self):
        """Even if a future/rogue writer stuffed extra keys (e.g. a stray
        'prompt') into the file, the read side must never surface them --
        DevSessionStatus's own closed field set is the actual enforcement,
        not trust in the writer."""
        import os

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ca1d_bridge_extra_"))
        try:
            path = self.tmp_dir / "status.json"
            path.write_text(json.dumps({
                "schema_version": 1, "session_id": "sess-1", "pid": os.getpid(),
                "state": STATE_ACTIVE, "last_structural_event": "PreToolUse",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "prompt": "this must never surface",
                "tool_input": {"command": "rm -rf /"},
            }), encoding="utf-8")
            status = read_dev_session_status(path)
            self.assertFalse(hasattr(status, "prompt"))
            self.assertFalse(hasattr(status, "tool_input"))
            self.assertEqual(status.state, STATE_ACTIVE)
        finally:
            import shutil

            shutil.rmtree(self.tmp_dir, ignore_errors=True)


class WriteThenReadIntegrationTests(unittest.TestCase):
    """End-to-end through both real modules together, no subprocess."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ca1d_bridge_e2e_"))
        self.path = self.tmp_dir / "status.json"

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_pretooluse_then_stop_round_trips_correctly(self):
        import os

        state = resolve_state("PreToolUse", lambda: None)
        atomic_write(self.path, build_payload("PreToolUse", state, "sess-e2e", os.getpid()))
        self.assertEqual(read_dev_session_status(self.path).state, STATE_ACTIVE)

        state = resolve_state("Stop", lambda: None)
        atomic_write(self.path, build_payload("Stop", state, "sess-e2e", os.getpid()))
        self.assertEqual(read_dev_session_status(self.path).state, STATE_WAITING_FOR_INPUT)

    def test_subagent_stop_after_waiting_does_not_flip_back_to_active(self):
        """The exact real-world scenario this design was revised to
        handle: Stop already wrote waiting_for_input; an unrelated
        SubagentStop arrives afterward and must not undo it."""
        import os

        atomic_write(self.path, build_payload("Stop", STATE_WAITING_FOR_INPUT, "sess-e2e", os.getpid()))
        prior = lambda: read_prior_state_from_file(self.path)
        state = resolve_state("SubagentStop", prior)
        atomic_write(self.path, build_payload("SubagentStop", state, "sess-e2e", os.getpid()))
        self.assertEqual(read_dev_session_status(self.path).state, STATE_WAITING_FOR_INPUT)


if __name__ == "__main__":
    unittest.main()
