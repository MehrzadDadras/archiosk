"""Validate operational receipts; test fixtures below are not deployment proof."""
import json
from pathlib import Path
from types import SimpleNamespace

from services import runtime_observation as runtime


def test_qualification_requires_receipt_success_actual_tests_and_unchanged_tree(tmp_path):
    from tools.qualify_go_runtime import deployment_implementation_hashes
    implementation=tmp_path/'source.py'
    implementation.write_text('value = 1\n',encoding='utf-8')
    tooling=tmp_path/'agent-settings.json'
    tooling.write_text('{}',encoding='utf-8')
    hashes=deployment_implementation_hashes({'source.py':implementation,'.claude/settings.json':tooling})
    tooling.unlink()  # The normal deployment does not include local agent tooling.
    app=SimpleNamespace(root_path=str(tmp_path),instance_path=str(tmp_path/'instance'),extensions={},
        config={'REGISTRY_STORE_PATH':str(tmp_path/'registry'),'GO_TESTS_PASSED':True})
    assert not runtime.applicable_test_qualification(app)['established']
    folder=runtime.directory(app)
    identifier='a'*32
    record=dict(id=identifier,actor='qualification_runner',request=dict(endpoint='tools.qualify_go_runtime'),events=[],
        qualification=dict(suite='authoritative_full_gate',exit_code=0,executed_tests=1,frozen_tree_unchanged=True,
            implementation_hashes=hashes))
    runtime._retain(app,record)
    (folder/'_qualification-current.json').write_text(json.dumps({'trace_id':identifier}),encoding='utf-8')
    assert runtime.applicable_test_qualification(app)['established']
    for key,value in [('exit_code',1),('executed_tests',0),('frozen_tree_unchanged',False),('suite','focused')]:
        original=record['qualification'][key]
        record['qualification'][key]=value
        runtime._retain(app,record)
        assert not runtime.applicable_test_qualification(app)['established']
        record['qualification'][key]=original
    runtime._retain(app,record)
    implementation.write_text('value = 200\n',encoding='utf-8')
    assert not runtime.applicable_test_qualification(app)['established']


def test_qualification_fingerprint_normalizes_only_text_checkout_line_endings(tmp_path):
    first,second=tmp_path/'first',tmp_path/'second'
    first.write_bytes(b'a\r\nb\r\n')
    second.write_bytes(b'a\nb\n')
    assert runtime.qualification_file_hash(first)==runtime.qualification_file_hash(second)
    first.write_bytes(b'\x00a\r\nb')
    second.write_bytes(b'\x00a\nb')
    assert runtime.qualification_file_hash(first)!=runtime.qualification_file_hash(second)
