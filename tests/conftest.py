"""
CLAUDE-TEST-REGISTRY-ISOLATION-01 - start every test session from an empty
test registry, so the suite stops degrading with use.

WHAT WAS WRONG

`TestingConfig` points the registry at a FIXED path (`instance/test_registry`)
rather than a per-process temp directory, deliberately - config.py's own note
says "so the artifacts stay inspectable after a failure", and that is a real
benefit worth keeping. What it never had was anything that empties it. Every
run left its Projects behind permanently, and they accumulated across runs
forever.

`services/project_code.py` issues each Project a 3-4 character acronym derived
from its name, and refuses to reuse one that is taken. The space is small: for
a given name stem it tries the initials, some truncations, then `stem + one of
"23456789"`, then `stem[:2] + 10..99` - on the order of a hundred variants.
Tests that ingest Projects use a FIXED name stem with a random suffix
(`"Collision " + uuid4().hex[:8]`), so they all compete for the same handful of
acronyms. Once enough have accumulated, `derive_code` exhausts the space and
raises.

The failure that produced this file: a full run reported 15 failures across
`test_write_collision_01.py` and `test_mobile_continuation_01.py`, every one of
them `ProjectCodeError: Could not derive a unique project acronym`. Nothing was
wrong with either feature. The store had reached 815 entries / 270 distinct
codes. Moving it aside and re-running made all 40 pass unchanged.

That is the worst shape a test failure can take: it appears in features
unrelated to the state that is actually accumulating, it appears only after
enough prior runs, and it reads exactly like a regression in whichever feature
happens to draw the short straw. One measured run leaves ~130 entries, so the
suite had roughly six or seven runs of headroom before going red on its own.

WHY CLEAR AT SESSION START RATHER THAN TEAR DOWN AFTER

Tearing down at the end of a session would destroy exactly what config.py
wanted kept - the artifacts of the run that just failed, at the moment somebody
wants to look at them. Clearing at the START gives both properties: the last
run's artifacts survive for as long as you are looking at them, and no run ever
inherits another's Projects.

Set ARCHIOSK_KEEP_TEST_REGISTRY=1 to skip the reset - for the case where you
are re-running one file against the store a full run just left behind, and want
that state preserved.

WHY THIS REFUSES TO DELETE ANYTHING IT IS NOT SURE ABOUT

One character wrong here deletes `instance/registry`, which is real development
data and is NOT recoverable from git. So `_is_disposable_store` is a positive
allowlist - under this repository's own `instance/`, and a directory name
starting with `test_` - and `_reset_test_stores` RAISES on a path that fails it
rather than skipping quietly. A silent skip would restore the accumulation
without anything saying so, which is the bug this file exists to end.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from config import BASE_DIR, TestingConfig

_INSTANCE_DIR = (BASE_DIR / "instance").resolve()

# Read from TestingConfig rather than restating the literals: if those paths
# ever move, this follows them instead of quietly cleaning nothing.
TEST_STORE_PATHS = (
    Path(TestingConfig.REGISTRY_STORE_PATH),
    Path(TestingConfig.PROJECT_ASSET_PATH),
)

KEEP_ENV_VAR = "ARCHIOSK_KEEP_TEST_REGISTRY"


def _is_disposable_store(path: Path) -> bool:
    """True only for a test-owned store directory under instance/.

    Positive allowlist, deliberately. `instance/registry` and
    `instance/project_assets` are the real development stores and both fail
    this: the first on the `test_` prefix, and any path outside `instance/`
    on the parent check.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return resolved.parent == _INSTANCE_DIR and resolved.name.startswith("test_")


def _reset_test_stores() -> list[Path]:
    """Remove the test stores. Returns what was actually removed."""
    removed = []
    for path in TEST_STORE_PATHS:
        if not _is_disposable_store(path):
            raise RuntimeError(
                "refusing to clear %s - not a test store under %s. "
                "TestingConfig's store paths changed; update tests/conftest.py "
                "rather than loosening this check." % (path, _INSTANCE_DIR)
            )
        if path.exists():
            # ignore_errors so a locked file (Windows, an editor holding a
            # handle) cannot fail the whole suite - but then SAY SO, because a
            # store that silently survived the reset resumes accumulating and
            # this file would be providing false assurance.
            shutil.rmtree(path, ignore_errors=True)
            if path.exists():
                print("\n[conftest] WARNING: %s survived the reset - it will "
                      "keep accumulating. Remove it by hand." % path)
            else:
                removed.append(path)
    return removed


def pytest_sessionstart(session):
    """Clear the test stores before collection imports a single test module.

    sessionstart rather than an autouse fixture: a fixture runs after
    collection, and a test module that builds a store at import time would
    already have written into the previous run's leftovers by then.
    """
    if os.environ.get(KEEP_ENV_VAR):
        return
    removed = _reset_test_stores()
    if removed:
        names = ", ".join(p.name for p in removed)
        print("\n[conftest] reset test stores: %s" % names)
