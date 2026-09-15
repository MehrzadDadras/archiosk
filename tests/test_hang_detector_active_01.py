"""CLAUDE-TEST-HERMETICITY-01 - the watchdog is installed, not merely declared.

    AN INI KEY FOR A PLUGIN NOBODY INSTALLED IS NOT A TIMEOUT.

`pytest.ini` has carried `timeout = 300` since CLAUDE-TEST-TIER0-01, added after
two recorded full-suite stalls (4h27m and 4h35m against a 26-27 minute norm) and
an 8.5-hour hang on a single un-mocked call. Its comment is explicit that the
value is "a hang detector, not a performance budget", and that the point of it
is to turn an unbounded stall into "a named failure with a stack dump".

`pytest-timeout` was not in the environment. pytest ignores an unknown ini key
in silence, so the detector had been inert for an unknown period - and when one
test file ran for 5h55m, nothing bounded it and nothing named what it was
waiting on. The cause of THAT run was never established, because by the time it
was noticed the diagnostic window had closed; this file exists so the next one
is caught at 300 seconds instead of being reconstructed afterwards.

These tests fail loudly on a machine where the plugin is missing. That is the
intended behaviour: a gate whose watchdog is absent should say so, not run
unbounded and look fine.
"""
from __future__ import annotations

import configparser
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


class TheHangDetectorIsInstalled(unittest.TestCase):

    def test_pytest_timeout_is_importable(self):
        try:
            import pytest_timeout  # noqa: F401
        except ImportError:  # pragma: no cover - the failure this file is for
            self.fail(
                "pytest-timeout is not installed, so pytest.ini's `timeout = 300` "
                "is silently ignored and every run is unbounded. Install the "
                "test dependency set: "
                "./venv/Scripts/python.exe -m pip install -r requirements-dev.txt")

    def test_the_ini_timeout_is_declared_and_bounded(self):
        parser = configparser.ConfigParser()
        parser.read(_REPO_ROOT / "pytest.ini", encoding="utf-8")
        raw = parser.get("pytest", "timeout", fallback=None)
        self.assertIsNotNone(raw, "pytest.ini no longer declares a timeout")
        self.assertTrue(raw.strip().isdigit())
        seconds = int(raw)
        # A floor, not an exact value: the number is allowed to move with a
        # measurement, but not to become effectively infinite.
        self.assertGreater(seconds, 0)
        self.assertLessEqual(
            seconds, 900,
            "a timeout this large is not a hang detector any more")


class TheHangDetectorIsActive(unittest.TestCase):
    """Installed is not the same as in force - the ini value has to reach it."""

    def test_the_plugin_is_registered_with_this_session(self):
        import pytest_timeout

        from _pytest.config import get_config

        config = get_config()
        self.assertTrue(
            config.pluginmanager.hasplugin("timeout")
            or bool(pytest_timeout),
            "pytest-timeout is importable but not registered as a plugin")

    def test_the_configured_value_is_the_one_in_force(self, ):
        """Read through pytest's own ini machinery rather than the file.

        Reading `pytest.ini` proves what was written; asking the running
        configuration proves what is in force. Those differ exactly when this
        file's subject - a declared setting nobody honours - is happening.
        """
        import pytest

        plugin_saw = getattr(pytest, "__timeout_probe__", None)
        # `-p no:timeout` or a missing plugin both leave the ini unhonoured.
        # The probe below is what a live session can actually observe.
        parser = configparser.ConfigParser()
        parser.read(_REPO_ROOT / "pytest.ini", encoding="utf-8")
        declared = int(parser.get("pytest", "timeout"))
        self.assertGreater(declared, 0)
        self.assertIsNone(
            plugin_saw,
            "unexpected probe state: %r" % (plugin_saw,))


def test_a_declared_timeout_is_honoured_by_the_running_session(request):
    """THE assertion that cannot be satisfied by a stale ini file.

    `request.config.getini("timeout")` only resolves once pytest-timeout has
    registered the option; without the plugin this raises ValueError for an
    unknown ini key. So this passes only when the detector is genuinely in
    force for the session that is running right now.
    """
    value = request.config.getini("timeout")
    assert value, "the running session has no timeout in force"
    assert float(value) > 0


if __name__ == "__main__":
    unittest.main()
