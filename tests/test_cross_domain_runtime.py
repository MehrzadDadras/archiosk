"""One actual shared matcher, four retained domain contexts, read-only exposure."""
from urllib.parse import urlencode

import pytest

from tests.test_kernel_mapping import project
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceStore


def execute_domains(project):
    app, _, _, _, client = project
    identifiers, files = [], []
    for case in ('matching:construction', 'matching:rfp', 'matching:fit', 'matching:asset'):
        response = client.post('/admin/survey-evaluation', data={'case':case})
        assert response.status_code == 302
        identifier = response.location.rsplit('/',1)[-1]
        path = evaluation.location(app, identifier)
        record = evaluation._read(path)
        store = CaseWorkspaceStore(path/'registry')
        workspace = store.get(record['project_id'])
        assert workspace.analyses[-1]['governed_result']['state'] == 'UNRESOLVED'
        assert workspace.analyses[-1]['governed_result']['evaluation_only']
        files.append(store._path_for(workspace.project_id))
        identifiers.append(identifier)
    return identifiers, files


def test_real_domains_share_invoked_owner_and_comparison_get_preserves_every_record(project):
    app, store, workspace, _, client = project
    untouched = store._path_for(workspace.project_id).read_bytes()
    identifiers, files = execute_domains(project)
    before = [p.read_bytes() for p in files]
    url = '/admin/survey-evaluation?' + urlencode([('compare_run', i) for i in identifiers])
    page = client.get(url)
    assert page.status_code == 200
    assert b'data-shared-owner="services.cross_modal_investigation.match_normalized_criteria"' in page.data
    comparison = evaluation.compare_runtime_domains(app, identifiers)
    owner = next(m for m in comparison['muscles'] if m['owner'].endswith('.match_normalized_criteria'))
    assert {e['execution']['domain'] for e in owner['executions']} == {'construction','rfp','investment','asset'}
    assert all(e['invoked_count'] and e['return_count'] for e in owner['executions'])
    assert all(e['execution']['consumer_events'] for e in owner['executions'])
    assert client.get(url).status_code == 200
    assert [p.read_bytes() for p in files] == before
    assert store._path_for(workspace.project_id).read_bytes() == untouched
    from services.runtime_observation import read
    trace = read(app, page.headers['X-ARCHIOSK-Observation'])
    invoked = [e['owner'] for e in trace['events'] if e['phase']=='INVOKED']
    assert not any(o.endswith(('.run_requirement_matching','.compare_normalized_information','.record_analysis')) for o in invoked)
    assert any(e['phase']=='CONSUMED' and e['owner']=='components/cross_domain_runtime.html' for e in trace['events'])


def test_missing_trace_does_not_manufacture_invocation(project, monkeypatch):
    app, _, _, _, _ = project
    identifiers, _ = execute_domains(project)
    from services import runtime_observation
    monkeypatch.setattr(runtime_observation, 'read', lambda *args:None)
    result = evaluation.compare_runtime_domains(app, identifiers)
    assert not result['muscles']
    assert all(not e['trace_available'] for e in result['executions'])


@pytest.mark.parametrize('identifiers', [['bad'], ['a'*32]*2, ['a'*32 for _ in range(9)]])
def test_unknown_duplicate_and_unbounded_comparison_refused(project, identifiers):
    app, _, _, _, client = project
    assert client.get('/admin/survey-evaluation?' + urlencode([('compare_run', i) for i in identifiers])).status_code == 400


def test_comparison_requires_existing_admin_developer_gate(project):
    _, _, _, _, client = project
    with client.session_transaction() as session:
        session.update(developer_mode=False)
    assert client.get('/admin/survey-evaluation').status_code == 403
