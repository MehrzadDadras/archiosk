"""CLAUDE-TEST-HERMETICITY-01 - the guard holds against APPLICATION code.

    STUBBING THE FUNCTION YOU REMEMBERED IS NOT THE SAME AS CLOSING THE DOOR.

Every other hermeticity measure in this repository replaces a NAMED function:
`BHiveParser.parse` in one file, `llm_gateway.call_llm_json` in another. Those
are necessary and they are not sufficient - they close the paths somebody
thought of, and say nothing about a path added later that reaches the network
another way: a bespoke client, an SDK retry, a second provider, a raw socket.

So these tests do not stub anything. They let real application code genuinely
try to call out, and assert that it is refused at the socket - which is the
only claim that survives someone adding a new provider tomorrow.

WHAT THIS IS EVIDENCE OF, STATED HONESTLY. A socket-level audit of the full
suite recorded ZERO non-loopback connections across 9,055 tests, so this guard
closes a door that is already shut. It is a structural guarantee about the
NEXT path, not a response to a leak. That distinction is worth keeping in the
file, because a 5h55m run was briefly and wrongly attributed to a live provider
call before anyone measured; the measurement disproved it, and the cause of
that run remains unestablished.

The companion is `tests/test_hang_detector_active_01.py`: this file proves a
test cannot reach a provider, that one proves a test cannot run forever.
"""
from __future__ import annotations

import os
import socket
import unittest

import pytest

from tests.conftest import (
    EXTERNAL_OPT_IN_ENV,
    EXTERNAL_PROVIDER_MARKER,
    ExternalEgressDenied,
    external_calls_permitted,
)


class ARawSocketIsRefused(unittest.TestCase):
    """The floor: nothing gets out, however it asks."""

    def test_a_direct_connection_to_a_provider_is_denied(self):
        with self.assertRaises(ExternalEgressDenied) as caught:
            socket.create_connection(("api.anthropic.com", 443), timeout=5)
        message = str(caught.exception)
        self.assertIn("api.anthropic.com", message)
        self.assertIn(EXTERNAL_PROVIDER_MARKER, message,
                      "the refusal does not say how to opt in legitimately")
        self.assertIn(EXTERNAL_OPT_IN_ENV, message)

    def test_every_named_provider_is_refused_not_just_anthropic(self):
        for host in ("api.anthropic.com", "generativelanguage.googleapis.com",
                     "api.openai.com", "example.com"):
            with self.subTest(host):
                with self.assertRaises(ExternalEgressDenied):
                    socket.create_connection((host, 443), timeout=5)

    def test_the_socket_method_is_guarded_as_well_as_the_helper(self):
        """`socket.create_connection` is the convenience; `socket.connect` is
        the primitive underneath it, and an SDK may use either."""
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(ExternalEgressDenied):
                probe.connect(("api.anthropic.com", 443))
        finally:
            probe.close()

    def test_loopback_is_not_blocked(self):
        """The Flask test client and SQLite never leave the process, and a
        route test that could not reach localhost would fail for a reason that
        has nothing to do with what it is testing."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=5):
                pass
        except ExternalEgressDenied:  # pragma: no cover - the bug this forbids
            self.fail("loopback was blocked; every route test would break")
        finally:
            listener.close()


class ApplicationCodeCannotEscapeTheGuard(unittest.TestCase):
    """THE point of this file. Real call sites, no stubs, genuinely trying."""

    def test_the_llm_gateway_cannot_reach_anthropic(self):
        """`call_llm_json` never raises by contract - it returns an outcome
        with `ran=False`. So the assertion is that it did NOT run, and the
        proof that it was the socket that stopped it is that no HTTP status
        came back."""
        from services import llm_gateway

        outcome = llm_gateway.call_llm_json(
            user_prompt="probe", api_key="sk-ant-probe-not-a-real-key",
            model="claude-sonnet-4-6", timeout=5.0,
            log_label="egress guard probe")
        self.assertFalse(outcome.ran,
                         "the gateway completed a call from an ordinary test")
        self.assertTrue(outcome.skipped_reason)

    def test_a_vision_call_cannot_reach_a_provider(self):
        """The Survey Reference path specifically - the newest caller, and the
        one whose payload is a customer's document."""
        import io

        from PIL import Image

        from services import visual_examination as vx

        class Allow:
            decision = "allow"
            controlling_layer = "baseline"
            baseline_version_id = None
            exception_id = None

        buffer = io.BytesIO()
        Image.new("RGB", (60, 40), (250, 250, 246)).save(buffer, "JPEG")

        result = vx.examine(buffer.getvalue(), "probe.jpg", decision=Allow(),
                            api_key="sk-ant-probe-not-a-real-key")
        self.assertFalse(result.ran,
                         "a customer image was transmitted from an ordinary test")
        self.assertEqual(result.audit.outcome, "failed")

    def test_a_raising_transport_does_not_crash_the_caller(self):
        """The guard raises AssertionError, and application code catches broad
        exceptions around provider calls by design. This asserts the two
        compose: a denied call degrades, it does not propagate a test-harness
        error out of a service."""
        from services import llm_gateway

        outcome = llm_gateway.call_llm_json(
            user_prompt="probe", api_key="sk-ant-probe-not-a-real-key",
            timeout=5.0, log_label="egress guard degradation probe")
        self.assertFalse(outcome.ran)


class TheGateRequiresBothKeys(unittest.TestCase):
    """Either gate alone is too easy to acquire by accident."""

    def test_the_marker_alone_does_not_open_the_gate(self):
        node = _FakeNode(marked=True)
        previous = os.environ.pop(EXTERNAL_OPT_IN_ENV, None)
        try:
            self.assertFalse(external_calls_permitted(node),
                             "a marker alone enabled live calls - a rebase into "
                             "the default lane would start making them")
        finally:
            if previous is not None:
                os.environ[EXTERNAL_OPT_IN_ENV] = previous

    def test_the_env_flag_alone_does_not_open_the_gate(self):
        node = _FakeNode(marked=False)
        previous = os.environ.get(EXTERNAL_OPT_IN_ENV)
        os.environ[EXTERNAL_OPT_IN_ENV] = "1"
        try:
            self.assertFalse(external_calls_permitted(node),
                             "one exported variable enabled live calls for every "
                             "test in the suite")
        finally:
            if previous is None:
                os.environ.pop(EXTERNAL_OPT_IN_ENV, None)
            else:
                os.environ[EXTERNAL_OPT_IN_ENV] = previous

    def test_both_together_open_it(self):
        node = _FakeNode(marked=True)
        previous = os.environ.get(EXTERNAL_OPT_IN_ENV)
        os.environ[EXTERNAL_OPT_IN_ENV] = "1"
        try:
            self.assertTrue(external_calls_permitted(node))
        finally:
            if previous is None:
                os.environ.pop(EXTERNAL_OPT_IN_ENV, None)
            else:
                os.environ[EXTERNAL_OPT_IN_ENV] = previous


class _FakeNode:
    """The two attributes `external_calls_permitted` reads, and nothing else."""

    def __init__(self, marked: bool):
        self._marked = marked

    def get_closest_marker(self, name):
        return object() if (self._marked and name == EXTERNAL_PROVIDER_MARKER) else None


@pytest.mark.external_provider
def test_the_marked_lane_is_reachable_but_still_gated():
    """A marked test in an ordinary run is STILL denied, because the operator
    did not opt in. This is the only test in the default gate that carries the
    marker, and it proves the marker is inert on its own."""
    if os.getenv(EXTERNAL_OPT_IN_ENV, "").strip() == "1":
        pytest.skip("running in the authorized external lane")
    with pytest.raises(ExternalEgressDenied):
        socket.create_connection(("api.anthropic.com", 443), timeout=5)


if __name__ == "__main__":
    unittest.main()
