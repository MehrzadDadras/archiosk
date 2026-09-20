import copy
import importlib

import pytest

from tests.test_kernel_mapping import project
from services import runtime_observation
from services.capability_registry import MUSCLE_CONTRACTS


@pytest.mark.parametrize('owner,contract', MUSCLE_CONTRACTS.items())
def test_contracts_name_real_instrumented_owners(owner, contract):
    parts = owner.split('.')
    target = importlib.import_module('.'.join(parts[:2]))
    for name in parts[2:]:
        target = getattr(target, name)
    assert callable(target) and hasattr(target, '__wrapped__')
    for field in ('inputs', 'outputs', 'allowed_transitions', 'refusal_states',
                  'authority_rule', 'provenance_requirements', 'runtime_hooks'):
        assert contract[field]


def test_return_or_catalogue_does_not_manufacture_invocation_and_trace_is_unchanged():
    owner = 'services.quantitative_investigation.compare_scalar_values'
    record = dict(id='a'*32, truncated=True, events=[dict(owner=owner, phase='RETURNED',
        sequence=1, result=dict(state='UNRESOLVED')), dict(owner='flask', phase='SURFACED', http_status=200)])
    original = copy.deepcopy(record)
    exposed = runtime_observation.muscle_exposure(record)
    row = next(r for r in exposed['muscles'] if r['owner'] == owner)
    assert row['invocation_state'] == 'NOT_OBSERVED' and row['return_count'] == 1
    assert exposed['truncated'] and row['events'][0]['result']['state'] == 'UNRESOLVED'
    assert record == original
    assert all(r['invocation_state'] == 'NOT_OBSERVED' for r in runtime_observation.muscle_exposure(None)['muscles'])


def test_real_action_links_committed_analysis_to_observed_execution_and_inspector_is_read_only(project, monkeypatch):
    app, store, workspace, evidence, client = project
    response = client.post('/projects/project/attention', data=dict(objective='Inspect this source', included_id=evidence['id']))
    assert response.status_code == 303
    trace_id = response.headers['X-ARCHIOSK-Observation']
    saved = store.get('project')
    analysis = saved.analyses[-1]
    assert analysis['runtime_trace_id'] == trace_id
    assert saved.evidence_items == workspace.evidence_items
    trace_path = runtime_observation.directory(app)/(trace_id+'.json')
    original_trace = trace_path.read_bytes()
    original_workspace = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert ('observation='+trace_id).encode() in page.data
    assert b'Inspect muscles for this execution' in page.data
    def forbidden(*args, **kwargs):
        pytest.fail('The observational inspector invoked a domain producer')
    monkeypatch.setattr(type(store), 'record_go_attention', forbidden)
    monkeypatch.setattr(type(store), 'admit_proposition', forbidden)
    page = client.get('/admin/survey-evaluation?observation='+trace_id)
    assert page.status_code == 200
    assert b'GO muscle inspector' in page.data and b'ATTENTION' in page.data
    assert b'data-invocation="INVOKED"' in page.data
    assert b'NOT_OBSERVED' in page.data and b'SOURCE_REFERENCE' in page.data
    assert b'Invocation does not prove correctness' in page.data
    assert store._path_for('project').read_bytes() == original_workspace
    assert trace_path.read_bytes() == original_trace


def test_observation_disabled_does_not_invent_a_trace_or_rerun_analysis(project):
    _, store, _, evidence, client = project
    with client.session_transaction() as session:
        session['survey_observe'] = False
    response = client.post('/projects/project/attention', data=dict(objective='Unobserved review', included_id=evidence['id']))
    assert 'X-ARCHIOSK-Observation' not in response.headers
    assert store.get('project').analyses[-1]['runtime_trace_id'] is None
    page = client.get(response.location)
    assert b'No runtime observation retained' in page.data
    assert b'Inspect muscles for this execution' not in page.data


def test_missing_and_retired_trace_cannot_reappear_as_another_execution(project):
    _, store, workspace, evidence, client = project
    assert client.get('/admin/survey-evaluation?observation='+'f'*32).status_code == 404
    response = client.post('/projects/project/attention', data=dict(objective='Recorded scope', included_id=evidence['id']))
    saved = store.get('project')
    saved.container_state = 'black_box'
    saved.document_desk_state = 'trash'
    store.save(saved)
    assert client.get('/admin/survey-evaluation?observation='+response.headers['X-ARCHIOSK-Observation']).status_code == 404
