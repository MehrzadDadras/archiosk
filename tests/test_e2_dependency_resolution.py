"""
E2 - the pinned dependency set must actually install, and must stay installable.

WHAT THIS CLOSES

`requirements.txt` pinned httpx==0.27.2 while google-genai==2.20.0 required
httpx>=0.28.1. `pip install -r requirements.txt` therefore returned
ResolutionImpossible: the file could not build an environment at all. Every
working environment had been assembled by hand, out of order, which is exactly
how production ended up on a combination the repository never described.

The consequence was not a missing feature. Production got httpx 0.28.x to
satisfy google-genai, and anthropic 0.34.2 raised

    TypeError: Client.__init__() got an unexpected keyword argument 'proxies'

when CONSTRUCTING the client - so every Anthropic-backed capability failed at
once, for a week, until one new feature happened to exercise the path. E1 made
that failure degrade honestly instead of returning 500. E2 removes the cause.

WHY METADATA IS NOT ENOUGH

anthropic 0.34.2 declares httpx<1,>=0.23.0, which INCLUDES 0.28.1. The
declaration was wider than the code: `proxies=` was passed to httpx
unconditionally, and httpx removed it in 0.28. A resolver cannot detect a
package that misdeclares its own range, and `pip check` stays silent. So the
floor is asserted here directly, with the evidence attached, rather than
trusted to metadata.

No test here reaches the network or installs anything.
"""
from __future__ import annotations

import importlib.metadata as importlib_metadata
import re
import unittest
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REQUIREMENTS = _REPO_ROOT / "requirements.txt"

# The first anthropic release whose code guards the argument instead of always
# passing it. Established by unpacking the wheels and reading _base_client.py:
# 0.34.2, 0.36.2, 0.37.1, 0.38.0 and 0.39.0 all construct the httpx client with
# a bare `proxies=proxies`; 0.40.0 constructs it with `**kwargs` populated only
# under `if proxies is not None`.
_ANTHROPIC_PROXIES_FIXED_AT = Version("0.40.0")

# The httpx release that removed the `proxies` argument.
_HTTPX_DROPPED_PROXIES_AT = Version("0.28")


def _pinned() -> dict:
    """Every `name==version` pin in requirements.txt, keyed by normalised name."""
    pins = {}
    for raw in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        req = Requirement(line)
        version = str(req.specifier).lstrip("=")
        pins[re.sub(r"[-_.]+", "-", req.name).lower()] = version
    return pins


class RequirementsAreInternallySatisfiableTests(unittest.TestCase):
    """The general guard: no pin may contradict another pin's declared needs."""

    def test_no_pin_violates_another_pinned_package_s_declared_range(self):
        pins = _pinned()
        violations = []
        for name, version in sorted(pins.items()):
            try:
                declared = importlib_metadata.requires(name) or []
            except importlib_metadata.PackageNotFoundError:
                # Not installed here. google-genai is legitimately optional -
                # see its own note in requirements.txt - so absence is not a
                # failure. What is checked is every pin we CAN see.
                continue
            for raw in declared:
                dep = Requirement(raw)
                if dep.marker is not None and not dep.marker.evaluate():
                    continue  # an extra or a platform we do not install
                dep_name = re.sub(r"[-_.]+", "-", dep.name).lower()
                if dep_name not in pins:
                    continue
                pinned_version = pins[dep_name]
                if not dep.specifier.contains(pinned_version, prereleases=True):
                    violations.append(
                        "%s==%s requires %s%s, but %s is pinned at %s"
                        % (name, version, dep.name, dep.specifier,
                           dep.name, pinned_version)
                    )
        self.assertEqual(
            violations, [],
            "requirements.txt cannot install as written:\n  " + "\n  ".join(violations),
        )


class AnthropicFloorTests(unittest.TestCase):
    """The specific guard metadata cannot express."""

    def test_anthropic_is_above_the_proxies_defect_whenever_httpx_is_0_28_or_newer(self):
        pins = _pinned()
        httpx_version = Version(pins["httpx"])
        anthropic_version = Version(pins["anthropic"])
        if httpx_version < _HTTPX_DROPPED_PROXIES_AT:
            self.skipTest("httpx pinned below 0.28; the defect cannot occur")
        self.assertGreaterEqual(
            anthropic_version, _ANTHROPIC_PROXIES_FIXED_AT,
            "anthropic %s passes `proxies=` to httpx unconditionally, and httpx "
            "%s has removed it. Client construction will raise TypeError and "
            "every AI capability will fail. anthropic>=%s is required alongside "
            "httpx>=%s." % (anthropic_version, httpx_version,
                            _ANTHROPIC_PROXIES_FIXED_AT, _HTTPX_DROPPED_PROXIES_AT),
        )

    def test_httpx_pin_satisfies_the_gemini_floor(self):
        """The exact pair that produced ResolutionImpossible, named directly so a
        regression reads as itself rather than as a generic resolver message."""
        pins = _pinned()
        self.assertIn("google-genai", pins)
        self.assertGreaterEqual(Version(pins["httpx"]), Version("0.28.1"))


class InstalledEnvironmentMatchesTheRepositoryTests(unittest.TestCase):
    """Parity. The repository must describe the environment that is running.

    The drift this closes was invisible precisely because the local venv was
    self-consistent WHILE INCOMPLETE - google-genai was absent, so nothing
    locally ever demanded httpx>=0.28.1 and the conflict stayed hidden until
    production hit it.
    """

    def test_installed_versions_match_the_pins_for_the_ai_dependencies(self):
        pins = _pinned()
        drift = []
        for name in ("anthropic", "httpx", "google-genai"):
            try:
                installed = importlib_metadata.version(name)
            except importlib_metadata.PackageNotFoundError:
                continue  # optional, or simply not installed in this environment
            if Version(installed) != Version(pins[name]):
                drift.append("%s: installed %s, pinned %s" % (name, installed, pins[name]))
        self.assertEqual(
            drift, [],
            "the running environment does not match requirements.txt:\n  "
            + "\n  ".join(drift),
        )


if __name__ == "__main__":
    unittest.main()
