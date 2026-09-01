"""
CLAUDE-TEST-TIER0-01 - the Tier 0 fast-feedback lane's own guard.

`tools/tier0.py` DERIVES its file set from two mechanical rules rather than
carrying a hand-maintained list, because a list of 49 paths goes stale in
silence: a new source-scan test simply never joins the lane and nothing says
so. The cost of deriving is that a careless edit to the rules can quietly
shrink the lane toward nothing while every run still reports green. That is
what this file exists to prevent.

Nothing here asserts the lane is FAST - wall-clock is environment-dependent and
this repository has already recorded the same suite taking 27:57 and 59:47 hours
apart. It asserts the lane is the right SHAPE.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_tier0():
    """Load tools/tier0.py by path - there is no tools/__init__.py, and this is
    the idiom tests/test_nginx_crit_monitor_01.py already uses for a tool."""
    spec = importlib.util.spec_from_file_location(
        "archiosk_tier0_tool", _REPO_ROOT / "tools" / "tier0.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TIER0 = _load_tier0()


class LaneSelectionTests(unittest.TestCase):
    def setUp(self):
        self.files = _TIER0.tier0_files()

    def test_the_lane_is_not_empty_or_near_empty(self):
        """49 files at the time of writing. The floor is deliberately well
        below that so ordinary churn does not fail this, and well above zero so
        a broken rule does."""
        self.assertGreaterEqual(len(self.files), 40, self.files)

    def test_every_selected_file_actually_exists(self):
        for relative in self.files:
            with self.subTest(file=relative):
                self.assertTrue((_REPO_ROOT / relative).is_file(), relative)

    def test_no_selected_file_needs_the_flask_app(self):
        """The rules are re-applied to their own output. If a marker is ever
        removed from NEEDS_APP, this fails on the file it let through."""
        for relative in self.files:
            text = (_REPO_ROOT / relative).read_text(encoding="utf-8", errors="replace")
            for marker in _TIER0.NEEDS_APP:
                with self.subTest(file=relative, marker=marker):
                    self.assertNotIn(marker, text)

    def test_no_selected_file_is_heavyweight(self):
        for relative in self.files:
            text = (_REPO_ROOT / relative).read_text(encoding="utf-8", errors="replace")
            for marker in _TIER0.HEAVY:
                with self.subTest(file=relative, marker=marker):
                    self.assertNotIn(marker, text)

    def test_every_selected_file_really_is_a_source_scan(self):
        for relative in self.files:
            text = (_REPO_ROOT / relative).read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=relative):
                self.assertIn(_TIER0.SOURCE_SCAN, text)

    def test_the_known_heavyweight_files_are_excluded(self):
        """Named individually because these are the files whose exclusion is the
        entire reason the HEAVY rule exists - the four-process bridge-claim race
        and the real-Chromium geometry tests. Both are valuable and both belong
        in the full suite; neither belongs in a lane that promises seconds."""
        for name in ("test_storage_bridge_durable_05.py",
                     "test_p40vw7b_qa3_header_topbar_stacking_fix.py",
                     "test_view_state_isolation_01.py"):
            with self.subTest(excluded=name):
                self.assertNotIn(f"tests/{name}", self.files)

    def test_this_file_is_itself_in_the_lane(self):
        """A real trap, guarded rather than commented.

        The selection rules search test files for literal marker strings. A test
        ABOUT those rules that spelled them out inline would match its own
        exclusion rule and silently drop out of the lane it guards - so this
        file references _TIER0.NEEDS_APP/_TIER0.HEAVY rather than writing those
        strings. If someone later inlines one for readability, this fails.
        """
        self.assertIn("tests/test_tier0_lane_01.py", self.files)


class TimeoutBoundaryTests(unittest.TestCase):
    """CLAUDE-TEST-TIER0-01's other half: no test may wait forever."""

    def setUp(self):
        self.pytest_ini = (_REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")

    def test_a_global_timeout_is_configured_at_all(self):
        self.assertIn("timeout =", self.pytest_ini)

    def test_the_global_timeout_clears_the_slowest_real_test_by_a_wide_margin(self):
        """The slowest measured test in this repository is a real headless
        Chromium geometry check at 5.46s. A global bound that a genuine test
        could reach would convert a slow machine into a red suite, which is how
        a timeout stops being trusted and starts being raised reflexively."""
        line = next(l for l in self.pytest_ini.splitlines()
                    if l.strip().startswith("timeout ="))
        configured = int(line.split("=", 1)[1].strip())
        self.assertGreaterEqual(configured, 60, "too tight to be a hang detector")
        self.assertLessEqual(configured, 900, "too loose to catch a hang usefully")

    def test_tier0_is_bounded_more_tightly_than_the_global_default(self):
        line = next(l for l in self.pytest_ini.splitlines()
                    if l.strip().startswith("timeout ="))
        self.assertLess(_TIER0.TIMEOUT_SECONDS, int(line.split("=", 1)[1].strip()))


if __name__ == "__main__":
    unittest.main()
