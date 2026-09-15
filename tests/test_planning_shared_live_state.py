"""Independent worker processes exercise the actual shared filesystem handoff."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from services import planning_studies as studies
from services.case_workspace import CaseWorkspaceStore
from tests.test_planning_map_export import specimen


def worker(root, code):
    return subprocess.run([sys.executable, '-c',
        'from services.planning_studies import WorkingResults\n'
        'from services.case_workspace import CaseWorkspaceStore\n'
        'import sys,json\nroot=sys.argv[1]\n' + code, str(root)],
        text=True, capture_output=True, timeout=40,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))


def test_worker_a_exit_worker_b_saves_and_reopens_exact_bytes(tmp_path):
    CaseWorkspaceStore(tmp_path).get_or_create('p')
    original = specimen()
    (tmp_path / 'input.json').write_text(json.dumps(original))
    first = worker(tmp_path, "from pathlib import Path\nprint(WorkingResults(root).put('p','alice',json.loads((Path(root)/'input.json').read_text())))")
    assert first.returncode == 0, first.stderr
    key = first.stdout.strip()
    second = worker(tmp_path, f"from pathlib import Path\nrecord=WorkingResults(root).save_study(CaseWorkspaceStore(root),'{key}','p','alice',formats=['pdf','docx'])\n(Path(root)/'worker-result.json').write_text(json.dumps(record))")
    assert second.returncode == 0, second.stderr
    record = json.loads((tmp_path / 'worker-result.json').read_text())
    store = CaseWorkspaceStore(tmp_path)
    with patch('services.planning_live.run_live', side_effect=AssertionError('No retrieval')):
        assert studies.reopen(store, store.get('p'), key) == original
        again = studies.WorkingResults(tmp_path).save_study(store, key, 'p', 'alice', formats=['pdf','docx'])
        assert record == again
        assert len(store.get('p').planning_studies) == 1
        for name, digest in record['artifacts'].items():
            assert studies.maps.sha(studies.artifact(store, store.get('p'), key, name)) == digest


def test_expiry_identity_and_integrity_fail_without_reconstruction(tmp_path):
    cache = studies.WorkingResults(tmp_path)
    store = CaseWorkspaceStore(tmp_path); store.get_or_create('p'); store.get_or_create('q')
    key = cache.put('p', 'alice', specimen())
    for requested, project, actor, message in [
        ('../x', 'p','alice','Invalid planning run'),
        ('0'*32, 'p','alice','unavailable'),
        (key, 'q','alice','another project'),
        (key, 'p','bob','another user'),
        (key, 'p',None,'another user')]:
        with pytest.raises(ValueError, match=message):
            cache.save_study(store, requested, project, actor)
    item = json.loads(cache._path(key).read_bytes())
    with patch('services.planning_studies.time.time', return_value=item['expires_at']):
        with pytest.raises(ValueError, match='expired'):
            cache.save_study(store, key, 'p', 'alice')
    item['result']['tampered'] = True
    cache._path(key).write_text(json.dumps(item))
    with pytest.raises(ValueError, match='integrity'):
        cache.get(key, 'p', 'alice')
    assert not store.get('p').planning_studies


def test_concurrent_save_is_rejected_then_idempotent(tmp_path):
    cache = studies.WorkingResults(tmp_path)
    store = CaseWorkspaceStore(tmp_path); store.get_or_create('p')
    key = cache.put('p','alice',specimen())
    with cache._save_lock('p'):
        other = worker(tmp_path, f"WorkingResults(root).save_study(CaseWorkspaceStore(root),'{key}','p','alice')")
        assert other.returncode != 0
        assert 'already in progress' in other.stderr
        assert not store.get('p').planning_studies
    first = cache.save_study(store,key,'p','alice')
    assert studies.WorkingResults(tmp_path).save_study(store,key,'p','alice') == first
    assert len(store.get('p').planning_studies) == 1
    with pytest.raises(ValueError, match='different report selection'):
        cache.save_study(store,key,'p','alice',formats=['pdf'])


def test_crashed_lock_owner_does_not_strand_live_result(tmp_path):
    cache = studies.WorkingResults(tmp_path)
    key = cache.put('p','alice',specimen())
    store = CaseWorkspaceStore(tmp_path); store.get_or_create('p')
    crashed = worker(tmp_path, "import os\nwith WorkingResults(root)._save_lock('p'):\n os._exit(17)")
    assert crashed.returncode == 17
    assert cache.save_study(store,key,'p','alice')['id'] == key


def test_ttl_sweep_only_removes_expired_staging(tmp_path):
    cache = studies.WorkingResults(tmp_path)
    key = cache.put('p','alice',{'original': True})
    item = json.loads(cache._path(key).read_bytes())
    with patch('services.planning_studies.time.time', return_value=item['expires_at']):
        new = cache.put('p','alice',{'new': True})
    assert not cache._path(key).exists()
    assert cache.get(new,'p','alice') == {'new': True}
