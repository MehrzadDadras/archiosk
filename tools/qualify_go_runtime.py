"""Run the frozen-tree full pytest gate and retain its actual operational receipt.

No existing log or caller-supplied PASS is accepted. The subprocess is the proof
producer. Receipts use runtime_observation, never project evidence persistence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def deployment_implementation_hashes(files):
    """Associate proof with deployed code, not deployment-excluded agent tooling.

    The full-tree freeze below still includes every tooling file. Only receipt
    applicability follows deploy/DEPLOYMENT.md's established .claude exclusion.
    """
    from services.runtime_observation import qualification_file_hash
    return {name: qualification_file_hash(path) for name, path in files.items()
            if not name.startswith('.claude/')}


def main():
    from services.runtime_observation import _retain, directory
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Existing workspace-local artifact directory.')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT/'instance'):
        raise SystemExit('Qualification artifacts must be inside this workspace instance directory.')
    output.mkdir(parents=True, exist_ok=True)
    listed = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    names = sorted({value.decode('utf-8') for value in listed.split(b'\0') if value})
    files = {name: ROOT/name for name in names if (ROOT/name).is_file()}
    before = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
    logical = deployment_implementation_hashes(files)
    (output/'freeze.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    identifier = uuid.uuid4().hex
    started = datetime.now(timezone.utc).isoformat()
    xml_path = output/'pytest.xml'
    # Long fixture names plus atomic-write suffixes can exceed Windows MAX_PATH.
    # Reserve a short, unique directory; retain it for failure inspection.
    base_temp = tempfile.mkdtemp(prefix='ag-')
    command = [sys.executable, '-m', 'pytest', '-q', '-x', '--tb=short', '-rs', '-n', '8', '--dist', 'loadfile',
               '--junitxml='+str(xml_path), '--basetemp='+base_temp]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    env.pop('PYTEST_ADDOPTS', None)  # A developer's local filter must not narrow the full gate.
    env.setdefault('FLASK_SECRET_KEY', 'local-qualification-only')
    with (output/'pytest.log').open('w', encoding='utf-8') as log:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    unchanged = all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == before[name] for name, path in files.items())
    current_names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    unchanged = unchanged and listed == current_names
    executed = 0
    if xml_path.exists():
        tree = ET.parse(xml_path)
        executed = sum(case.find('skipped') is None for case in tree.iter('testcase'))
    receipt = dict(id=identifier, actor='qualification_runner', started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        request=dict(method='QUALIFICATION', path='authoritative-full-gate', endpoint='tools.qualify_go_runtime', arguments={}),
        events=[dict(owner='pytest', phase='RETURNED', exit_code=completed.returncode)],
        qualification=dict(suite='authoritative_full_gate', exit_code=completed.returncode, executed_tests=executed,
            frozen_tree_unchanged=unchanged, implementation_hashes=logical, command=command,
            excluded_tooling_hashes={name: before[name] for name in files if name not in logical},
            full_tree_freeze_sha256=hashlib.sha256((output/'freeze.json').read_bytes()).hexdigest(),
            log_sha256=hashlib.sha256((output/'pytest.log').read_bytes()).hexdigest(),
            junit_sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest() if xml_path.exists() else None))
    app = SimpleNamespace(instance_path=str(ROOT/'instance'), config={'REGISTRY_STORE_PATH':str(ROOT/'instance/registry')})
    _retain(app, receipt)
    if completed.returncode == 0 and unchanged and executed:
        pointer = directory(app)/'_qualification-current.json'
        pending = pointer.with_suffix('.tmp')
        pending.write_text(json.dumps(dict(trace_id=identifier)), encoding='utf-8')
        pending.replace(pointer)
    print(json.dumps(dict(trace_id=identifier, exit_code=completed.returncode, executed_tests=executed, frozen_tree_unchanged=unchanged)))
    raise SystemExit(completed.returncode or (0 if unchanged and executed else 1))


if __name__ == '__main__':
    main()
