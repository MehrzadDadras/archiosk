"""Run an isolated bounded precheck or one full gate; preserve tree hashes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = Path(r"C:\Users\info\AppData\Local\Temp\archiosk-planning-composer-01")
SOURCE = OUT.parents[2]
mode = sys.argv[1]
assert mode in ("targeted", "full")
setup = json.loads((OUT / "isolated-setup.json").read_text())
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.update(PYTHONDONTWRITEBYTECODE="1", FLASK_SECRET_KEY="repair-closeout-test-only",
                  AI_CALLS_DISABLED="1", PYTHONPATH=str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def snapshot():
    names = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT / "static/nipigon").rglob("*") if p.is_file()]
    return {n: sha(ROOT / n) for n in sorted(set(names)) if (ROOT / n).is_file()}


def shared_repair():
    return {n: sha(SOURCE / n) for n in setup["repair_owned"]}


# Do not run over somebody else's test process. Our own launcher is excluded.
ps = subprocess.check_output(["powershell", "-NoProfile", "-Command",
    "Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python|pytest'} | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"], text=True)
processes = json.loads(ps) if ps.strip() else []
if isinstance(processes, dict): processes = [processes]
others = [p for p in processes if "run_qualification.py" not in (p.get("CommandLine") or "")]
(OUT / f"{mode}-process-preflight.json").write_text(json.dumps(processes, indent=2), encoding="utf-8")
if others:
    print("GATE_NOT_STARTED: other Python process active", json.dumps(others))
    sys.exit(3)

before = snapshot()
head = git("rev-parse", "HEAD")
state = git("status", "--short")
repair_before = shared_repair()
assert repair_before == setup["repair_owned"]
assert all(before[n] == h for n, h in setup["candidate_hashes"].items())
freeze = {"head": head, "state": state, "files": before, "repair_hashes": repair_before,
          "tree_sha256": hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
(OUT / f"{mode}-freeze.json").write_text(json.dumps(freeze, indent=2), encoding="utf-8")

args = ["-m", "not legacy_route_diagnostic", "-q", "-p", "no:cacheprovider", "--ignore-glob=docs/records/*/*.source.py"]
if mode == "targeted":
    args += ["tests/test_planning_composer.py", "tests/test_planning_word_export_405.py", "tests/test_planning_studies.py", "tests/test_planning_shared_live_state.py",
             "tests/test_planning_map_export.py", "tests/test_planning_live_route_01.py",
             "tests/test_planning_workspace_02a.py", "tests/test_planning_zoning_door_01.py",
             "tests/test_planning_visual_acceptance_01.py"]
    from tools.tier0 import tier0_files
    args += ["tests/test_ca1d_composer_spine_stage2_context_envelope.py", "tests/test_composer_evidence_join_01.py", "tests/test_go_document_export_01.py"]
    args += [f for f in tier0_files() if f not in args]
else:
    args += ["-n", "8", "--dist", "loadfile", "--durations=10"]

import pytest
started = time.perf_counter()
timing = {}
counts = {}


class Record:
    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):
        timing.setdefault("worker_collection", {})[node.gateway.id] = {"seconds": time.perf_counter() - started, "items": len(ids)}

    def pytest_runtest_logstart(self, nodeid, location):
        timing.setdefault("first_test_seconds", time.perf_counter() - started)

    def pytest_terminal_summary(self, terminalreporter):
        counts.update({k: len(v) for k, v in terminalreporter.stats.items()})


rc = pytest.main(args, plugins=[Record()])
after = snapshot()
repair_after = shared_repair()
result = {"command": [sys.executable, "-m", "pytest", *args], "PYTEST_EXIT": int(rc),
          "counts": counts, "runtime_seconds": time.perf_counter() - started, "timing": timing,
          "head_before": head, "head_after": git("rev-parse", "HEAD"),
          "state_before": state, "state_after": git("status", "--short"),
          "files_unchanged": before == after,
          "changed_files": [n for n in set(before) | set(after) if before.get(n) != after.get(n)],
          "repair_pre_hashes": repair_before, "repair_post_hashes": repair_after,
          "repair_unchanged": repair_before == repair_after,
          "test_environment": {"FLASK_SECRET_KEY": "test-only supplied", "AI_CALLS_DISABLED": "1"},
          "model_calls": 0}
result["clean"] = bool(rc == 0 and before == after and repair_before == repair_after
                       and result["head_before"] == result["head_after"] and state == result["state_after"])
(OUT / f"{mode}-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
(OUT / f"{mode}-post-hashes.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
print("PYTEST_EXIT=" + str(rc), flush=True)
print("CLEAN=" + str(result["clean"]), flush=True)
sys.exit(int(rc) if result["clean"] else (int(rc) or 2))
