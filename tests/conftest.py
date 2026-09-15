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

import csv
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


# ---------------------------------------------------------------------------
# CLAUDE-XDIST-STORE-SWEEP-01 - stale per-worker stores.
# ---------------------------------------------------------------------------

WORKER_ENV_VAR = "PYTEST_XDIST_WORKER"

# The suffixed stores TestingConfig hands each xdist worker
# (instance/test_registry_gw0, ...). Anchored to the same two stems this file
# already resets, so a future third store follows automatically rather than
# being silently missed.
_WORKER_STORE_GLOBS = ("test_registry_*", "test_project_assets_*")


def _stale_worker_stores() -> list[Path]:
    """Per-worker stores left behind by a previous run.

    Every candidate is re-checked through _is_disposable_store rather than
    trusted because it matched a glob - the glob is a search, the allowlist is
    the authority, and that ordering is what keeps instance/registry
    unreachable from here.
    """
    return [
        path for pattern in _WORKER_STORE_GLOBS
        for path in sorted(_INSTANCE_DIR.glob(pattern))
        if path.is_dir() and _is_disposable_store(path)
    ]


def pytest_configure(config):
    """Remove worker stores orphaned by a run with a different -n.

    THE PROBLEM. Each worker clears only its OWN store, so `-n 8` followed by
    `-n 2` leaves test_registry_gw2..gw7 untouched forever. That is the same
    slow-accumulation shape this file's own header describes: a store nobody
    empties, failing much later in whichever feature draws the short straw.

    WHY pytest_configure AND NOT pytest_sessionstart. xdist spawns its workers
    during the controller's session start, so a sweep there races store
    creation and could delete a LIVE worker's directory mid-run. configure runs
    before any worker exists.

    WHY THE WORKER GUARD. configure also runs inside each worker. Without this,
    worker gw3 would delete gw5's store - the precise failure this exists to
    prevent, caused by the fix for it. Absent in a serial run too, which is
    correct: with no workers, every gw* directory is stale by definition.

    KNOWN LIMITATION, recorded rather than solved: two pytest runs started
    concurrently on one machine would have the second sweep the first's worker
    stores. That is already true of the shared instance/test_registry today, so
    it is pre-existing rather than introduced, and locking for a scenario
    nobody has would be machinery this repository does not need.
    """
    if os.environ.get(WORKER_ENV_VAR):
        return

    # Orphan guard first: an orphaned chain starves the run that is about to
    # start, and it holds handles under instance/ that can make the sweep
    # below fail on Windows. Deliberately NOT gated on KEEP_ENV_VAR - that
    # flag means "preserve a previous run's store", which says nothing about
    # whether a stale dev server should keep starving this one.
    if not os.environ.get(ALLOW_ORPHAN_ENV_VAR):
        killed = _terminate_orphan_app_processes()
        if killed:
            print("\n[conftest] terminated %d orphaned app.py chain(s) (root "
                  "PID %s, tree-killed). These starve the suite of I/O - one "
                  "measured run went from 5.6%% to ~79%% CPU the moment such a "
                  "chain was removed. Set %s=1 to keep them."
                  % (len(killed), ", ".join(str(p) for p in killed),
                     ALLOW_ORPHAN_ENV_VAR))

    if os.environ.get(KEEP_ENV_VAR):
        return
    removed = []
    for path in _stale_worker_stores():
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            removed.append(path)
        else:
            print("\n[conftest] WARNING: %s survived the sweep - remove it by "
                  "hand, or it will keep accumulating." % path)
    if removed:
        print("\n[conftest] swept %d stale worker store(s): %s"
              % (len(removed), ", ".join(p.name for p in removed)))


# ---------------------------------------------------------------------------
# CLAUDE-ORPHAN-APP-GUARD-01 - orphaned dev-server chains starve the suite.
# ---------------------------------------------------------------------------
#
# WHAT THIS IS FOR
#
# A five-deep Werkzeug reloader chain (each `python app.py` restart nesting a
# new child under the previous one), oldest process 47 hours old, was found
# mid-gate starving the suite at 5.6% CPU. The run took 7:00:57 against the
# same suite's 2:43:33 hours earlier. Killing the chain recovered CPU to ~79%
# immediately - roughly a 10x recovery, mid-run.
#
# CLAUDE.md's Watchdog Protocol records the manual check. This automates it,
# because a protocol that depends on remembering to run `tasklist` is a
# protocol that gets skipped on exactly the run where it mattered.
#
# THE SUITE IS NOT WHAT CREATES THESE. Audited before writing this: tests/ has
# ZERO subprocess.Popen, and all six subprocess.run() call sites are
# synchronous and cannot orphan. These processes come from a human or an agent
# running `python app.py` outside the harness, which the standing live-only,
# no-localhost policy says should not happen at all.
#
# WHY TWO STAGES
#
# Cost, measured on this machine. psutil is not installed and wmic no longer
# exists on Windows 11 26200, so the only stdlib route to a command line is
# PowerShell CIM at ~944ms. Paying that on every pytest invocation would be a
# 13% tax on a 7-second single-file run.
#
#   ctypes CreateToolhelp32Snapshot   20.7 ms   pid + PARENT pid + exe name
#   tasklist                         295.7 ms   names only, no cmdline
#   PowerShell CIM                   943.5 ms   full command lines
#
# So stage 1 (always, ~20ms) uses the snapshot's parent-pid data to find any
# python.exe OUTSIDE our own process tree, and stage 2 (~944ms, only when
# stage 1 finds something) confirms what it actually is. A clean machine pays
# 20ms; the expensive call happens only when there is something to identify.
#
# WHY STAGE 2 IS MANDATORY BEFORE ANY KILL
#
# Stage 1 cannot see command lines, so all it can say is "a python.exe that is
# not ours". That is equally true of a Jupyter kernel, a language server, or
# another project's process. Terminating on stage 1 alone would be wrong, so
# the allowlist below is positive and every condition must hold - the same
# shape as _is_disposable_store above, and for the same reason.

ALLOW_ORPHAN_ENV_VAR = "ARCHIOSK_ALLOW_ORPHAN_APP"

_TH32CS_SNAPPROCESS = 0x00000002
_APP_ENTRYPOINT = "app.py"


def _windows_process_snapshot():
    """[(pid, ppid, exe_name)] for every process, or [] off Windows.

    ctypes rather than a subprocess: 20.7ms against 295.7ms for tasklist and
    943.5ms for PowerShell, and unlike tasklist it yields the PARENT pid,
    which is what makes "outside our own tree" computable without ever
    reading a command line.
    """
    if sys.platform != "win32":
        return []
    import ctypes
    import ctypes.wintypes as wintypes

    class _PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if handle == -1:
        return []
    processes = []
    entry = _PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
    try:
        if kernel32.Process32First(handle, ctypes.byref(entry)):
            while True:
                processes.append((
                    int(entry.th32ProcessID),
                    int(entry.th32ParentProcessID),
                    entry.szExeFile.decode("utf-8", "replace"),
                ))
                if not kernel32.Process32Next(handle, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(handle)
    return processes


def _our_process_tree(processes):
    """Every pid this pytest run is responsible for - us, our ancestors, our
    descendants.

    Ancestors matter because the shell that launched pytest is often itself a
    python.exe. Descendants matter because xdist workers and the six
    subprocess.run() children are ours and must never be candidates.
    """
    parent_of = {pid: ppid for pid, ppid, _ in processes}
    children = {}
    for pid, ppid, _ in processes:
        children.setdefault(ppid, []).append(pid)

    ours = {os.getpid()}
    walker = os.getpid()
    seen = set()
    while walker in parent_of:
        if walker in seen:
            break                       # a cycle from a reused pid
        seen.add(walker)
        walker = parent_of[walker]
        if walker == 0 or walker in seen:
            break
        ours.add(walker)

    stack = [os.getpid()]
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            if child not in ours:
                ours.add(child)
                stack.append(child)
    return ours


def _confirm_app_command_lines(pids):
    """{pid: command_line} for pids whose command line genuinely runs THIS
    repository's app.py.

    Stage 2. Only reached when stage 1 already found a foreign python.exe, so
    the ~944ms is paid on the rare path rather than every run. Fails CLOSED:
    any error returns nothing, and nothing is terminated.
    """
    if not pids:
        return {}
    query = (
        "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Csv -NoTypeInformation"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if completed.returncode != 0:
        return {}

    confirmed = {}
    base = str(BASE_DIR).replace("/", "\\").lower()
    for row in csv.reader(io.StringIO(completed.stdout)):
        if len(row) < 2 or not row[0].isdigit():
            continue
        pid, command = int(row[0]), (row[1] or "")
        lowered = command.replace("/", "\\").lower()
        # Positive allowlist - EVERY condition must hold. Anything that fails
        # even one of them is left alone rather than guessed about.
        if (pid in pids
                and _APP_ENTRYPOINT in lowered
                and base in lowered
                and "pytest" not in lowered):
            confirmed[pid] = command
    return confirmed


def _chain_root(pid, parent_of, confirmed):
    """The topmost process of a reloader chain that is still one of ours to
    kill.

    Walks up only while the parent is ALSO a confirmed app.py process, so the
    shell that started the chain is never a candidate. Killing this pid with
    /T takes the nested children with it; killing a leaf would leave the
    reloader parent free to spawn a replacement.
    """
    seen = set()
    while pid in parent_of and pid not in seen:
        seen.add(pid)
        parent = parent_of[pid]
        if parent in confirmed and parent not in seen:
            pid = parent
        else:
            break
    return pid


def _terminate_orphan_app_processes():
    """Detect and tree-kill orphaned app.py chains. Returns what was killed."""
    processes = _windows_process_snapshot()
    if not processes:
        return []

    ours = _our_process_tree(processes)
    foreign = {
        pid for pid, _ppid, exe in processes
        if exe.lower() == "python.exe" and pid not in ours
    }
    if not foreign:
        return []                       # the common path: ~20ms, nothing more

    confirmed = _confirm_app_command_lines(foreign)
    if not confirmed:
        return []

    parent_of = {pid: ppid for pid, ppid, _ in processes}
    roots = {_chain_root(pid, parent_of, confirmed) for pid in confirmed}

    killed = []
    for root in sorted(roots):
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(root), "/T", "/F"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            killed.append(root)
        else:
            print("\n[conftest] WARNING: could not terminate orphaned app.py "
                  "chain rooted at PID %d - remove it by hand, or the suite "
                  "will run starved: %s" % (root, completed.stdout.strip()))
    return killed


# -- CLAUDE-TEST-HERMETICITY-01: external egress is DENY BY DEFAULT -----------
#
#     A TEST THAT CAN REACH A PROVIDER WILL EVENTUALLY REACH ONE.
#
# Hermeticity here has been maintained by remembering to stub the right
# function - `BHiveParser.parse` in one file, `llm_gateway.call_llm_json` in
# another. That is necessary and NOT sufficient: it closes the paths somebody
# thought of, and says nothing about a path added later that reaches the
# network another way - a bespoke client, an SDK retry, a second provider, a
# raw socket.
#
# So the boundary moves to the SOCKET, where all of those converge, and the
# default becomes refusal.
#
# WHAT THIS IS AND IS NOT EVIDENCE OF. A full-suite audit at this same layer
# recorded ZERO non-loopback connections across 9,055 tests, so this guard
# closes a door that is currently shut. It is a structural guarantee against
# the next path, not a response to a leak - and the distinction matters,
# because a 5h55m run was briefly and wrongly attributed to a live provider
# call before the measurement was taken. The cause of that run remains
# unestablished; this file makes the question answerable next time instead of
# reconstructible afterwards.
#
# LOOPBACK IS UNTOUCHED. The Flask test client and SQLite never leave the
# process; a localhost connection is not egress, and blocking it would break
# every route test for nothing.
#
# A test that legitimately needs a provider must say so TWICE - a marker in the
# code and a flag in the environment - because either alone is too easy to
# acquire by accident. A marker alone survives a rebase into the default lane;
# an env var alone enables live calls for the whole suite from one export.
#
#     @pytest.mark.external_provider          # declared by the test
#     ARCHIOSK_ALLOW_EXTERNAL_CALLS=1         # declared by the operator
#
# Without BOTH, the connection fails at connect() - before any request is
# constructed, before any byte leaves - and the failure names the test and the
# host it reached for.

EXTERNAL_PROVIDER_MARKER = "external_provider"
EXTERNAL_OPT_IN_ENV = "ARCHIOSK_ALLOW_EXTERNAL_CALLS"

#: Loopback only. "No host at all" - a unix socket, an empty address - is
#: handled separately BECAUSE AN EMPTY PREFIX MATCHES EVERY STRING: with "" in
#: this tuple, `"api.anthropic.com".startswith("")` is True and the guard
#: silently permits everything. The first run of
#: `tests/test_external_egress_guard_01.py` caught exactly that, which is the
#: whole argument for writing the regression before trusting the guard.
_LOCAL_HOST_PREFIXES = ("127.", "::1", "localhost", "0.0.0.0")


class ExternalEgressDenied(AssertionError):
    """A test reached for the network without being doubly opted in.

    AssertionError rather than a custom base, so it reads as a test failure
    rather than an application error - the thing that went wrong is the test's
    isolation, not the code under test.
    """


def _host_is_local(host) -> bool:
    """Loopback, or no host at all. Never a wildcard.

    An absent host is treated as local because it cannot be egress - there is
    nowhere for it to go - but it is tested explicitly rather than expressed as
    an empty prefix, which would match every hostname in existence.
    """
    text = str(host or "")
    if not text:
        return True
    return any(text.startswith(prefix) for prefix in _LOCAL_HOST_PREFIXES)


def _split_address(address):
    if isinstance(address, tuple) and address:
        return address[0], (address[1] if len(address) > 1 else None)
    return address, None


def external_calls_permitted(node) -> bool:
    """Both gates, evaluated together. Exposed so a test can assert on it."""
    marked = node.get_closest_marker(EXTERNAL_PROVIDER_MARKER) is not None
    opted_in = os.getenv(EXTERNAL_OPT_IN_ENV, "").strip() == "1"
    return marked and opted_in


@pytest.fixture(autouse=True)
def deny_external_egress(request):
    """Refuse every non-loopback connection unless doubly opted in."""
    import socket

    if external_calls_permitted(request.node):
        # An authorized external-integration test, running in its own lane.
        # This is the ONLY way a connection leaves this process.
        yield
        return

    original_connect = socket.socket.connect
    original_create = socket.create_connection

    def _refuse(host, port):
        raise ExternalEgressDenied(
            "external egress denied: %s tried to connect to %s:%s. "
            "Tests are hermetic by default. If this call is deliberate, mark it "
            "@pytest.mark.%s AND run the integration lane with %s=1; otherwise "
            "stub the boundary (see CLAUDE.md on hermetic tests)."
            % (request.node.nodeid, host, port,
               EXTERNAL_PROVIDER_MARKER, EXTERNAL_OPT_IN_ENV))

    def guarded_connect(self, address, *args, **kwargs):
        host, port = _split_address(address)
        if not _host_is_local(host):
            _refuse(host, port)
        return original_connect(self, address, *args, **kwargs)

    def guarded_create(address, *args, **kwargs):
        host, port = _split_address(address)
        if not _host_is_local(host):
            _refuse(host, port)
        return original_create(address, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.create_connection = guarded_create
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create
