"""Task entry forwards to existing scoped persistence and plan execution."""
from tests.test_kernel_mapping import project
from services.runtime_observation import read


def test_task_entry_declares_then_executes_existing_owner(project):
    app, store, workspace, evidence, client = project
    before = store._path_for('project').read_bytes()
    page = client.get('/admin/survey-evaluation')
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for label in ('GO Review Workspace', 'Review a project', 'Compare sources',
                  'Evaluate capital alignment', 'Review participant composition',
                  'Review transaction status', 'Run professional review', 'What do you want GO to evaluate?'):
        assert label in html
    assert '<details id="review-technical" >' in html
    assert store._path_for('project').read_bytes() == before
    payload = dict(review_target='/projects/project/attention', review_task='capital',
                   objective='What capital evidence is missing?', declare_work_plan='yes')
    declared = client.post('/admin/survey-evaluation', data=payload, follow_redirects=True)
    assert declared.status_code == 200
    assert not store.get('project').analyses
    assert all(label in declared.json['html'] for label in ('Scope:', 'Evidence:', 'Stop conditions:', 'Expected output:'))
    payload.pop('declare_work_plan')
    payload['plan_id'] = declared.json['plan']['plan_id']
    executed = client.post('/admin/survey-evaluation', data=payload)
    assert executed.status_code == 303 and '&task=capital' in executed.location
    state = store.get('project')
    assert len(state.analyses) == 1
    assert state.analyses[0]['objective'] == payload['objective']
    assert state.evidence_items == workspace.evidence_items
    trace = read(app, executed.headers['X-ARCHIOSK-Observation'])
    assert any(e['owner'].endswith('.record_go_attention') and e['phase'] == 'INVOKED' for e in trace['events'])
    committed = store._path_for('project').read_bytes()
    for _ in range(2):
        result = client.get(executed.location)
        assert result.status_code == 200
        text = result.get_data(as_text=True)
        for title in ('What matters', 'What changed', 'What remains unresolved', 'Supporting evidence', 'Technical details'):
            assert title in text
        assert 'has not yet reached a domain decision' in text
    assert store._path_for('project').read_bytes() == committed


def test_entry_rejects_external_or_unknown_targets(project):
    _, store, _, _, client = project
    before = store._path_for('project').read_bytes()
    for target in ('https://evil.example', '/projects/missing/attention', '/admin/users'):
        assert client.post('/admin/survey-evaluation', data=dict(review_target=target, objective='Review')).status_code == 400
    assert store._path_for('project').read_bytes() == before
