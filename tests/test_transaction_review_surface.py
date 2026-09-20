"""The real Flask dispatcher persists and surfaces the shared transaction resolver."""
from services.runtime_observation import read
import pytest
from services import survey_evaluation as evaluation
from tests.test_kernel_mapping import project
from tests.test_transaction_propositions import source_case, event_data, record
from tests.test_survey_evaluation import evaluation_app


@pytest.mark.parametrize('case', evaluation.TRANSACTION_GAMES)
def test_transaction_evaluation_roundtrip_never_fabricates_geometry_or_human_authority(evaluation_app, case):
    from pathlib import Path
    from services.case_workspace import CaseWorkspaceStore
    identifier = evaluation.create(evaluation_app, case, 'evaluation reviewer')
    location = evaluation.location(evaluation_app, identifier)
    record = evaluation._read(location)
    store = CaseWorkspaceStore(location/'registry')
    workspace = store.get(record['project_id'])
    result = workspace.analyses[-1]['governed_result']
    assert record['origin'] == 'EVALUATION_INPUT'
    assert result['kind'] == 'transaction_review' and result['state'] == 'UNRESOLVED'
    assert result['transaction']['history'] and workspace.evidence_items
    assert all(claim['event_proposition']['evaluation_only'] for claim in workspace.claims)
    assert not workspace.applies and not workspace.reviewer_validations
    before = store._path_for(workspace.project_id).read_bytes()
    rows = store.inspect_transaction_reviews(workspace, 'evaluation reviewer', record['attention_id'])
    assert len(rows) == 1
    assert store._path_for(workspace.project_id).read_bytes() == before
    assert not Path(evaluation_app.config['REGISTRY_STORE_PATH']).exists()


def test_real_route_invocation_persistence_and_read_only_reload(project):
    app, _, _, _, client = project
    store, workspace, evidence, attention, party = source_case(project)
    root = record(store, workspace, evidence, attention, event_data(party))
    record(store, workspace, evidence, attention, event_data(party, root['id'], 'SIGNED'))
    response = client.post('/projects/project/attention', data=dict(action='transaction_review',
        analysis_id=attention['id'], transaction_claim_id=root['id'], query_date='2024-06-01',
        reason='Inspect the retained event without manufacturing authority.'))
    assert response.status_code == 303
    persisted = store.get('project')
    result = persisted.analyses[-1]['governed_result']
    assert result['kind'] == 'transaction_review' and result['state'] == 'UNRESOLVED'
    assert result['transaction']['events']['SIGNED']['state'] == 'UNRESOLVED'
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    invoked = {row['owner'] for row in trace['events'] if row['phase'] == 'INVOKED'}
    assert 'services.case_workspace.CaseWorkspaceStore.run_transaction_review' in invoked
    assert 'services.cross_modal_investigation.investigate_transaction_history' in invoked
    assert 'services.cross_modal_investigation.resolve_transaction_identity' in invoked
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Governed factual status:' in html and 'Transaction history' in html
    assert 'Record a source-anchored identity or event' in html
    reload_trace = read(app, page.headers['X-ARCHIOSK-Observation'])
    assert not any(row['phase'] == 'INVOKED' and row['owner'].endswith('investigate_transaction_history') for row in reload_trace['events'])
    assert store._path_for('project').read_bytes() == before
    assert store.inspect_transaction_reviews(persisted, 'reviewer', attention['id'])[0]['consumption_state'] == 'RETAINED_EXECUTION'
    store.register_evidence_item(persisted, evidence['source_id'], 'direct_source_evidence', 'A newly discovered contradiction', 'text')
    assert store.inspect_transaction_reviews(store.get('project'), 'reviewer', attention['id'])[0]['consumption_state'] == 'REVIEW_REQUIRED'
    changed = client.get(response.location).get_data(as_text=True)
    assert 'Current applicability unresolved:' in changed
    assert 'Factual status at earlier execution' in changed


def test_source_interpretation_form_uses_existing_claim_owner(project):
    _, _, _, _, client = project
    store, workspace, evidence, attention, party = source_case(project)
    data = event_data(party)
    form = dict(action='transaction_proposition', analysis_id=attention['id'], party_id=party['id'],
        evidence_id=evidence['id'], source_class='PROJECT_DOCUMENT', evidence_tier='3',
        original_quote=evidence['content'], reason='Source interpretation only.', attribution='agent_assessment')
    form.update({'project_'+k:v for k,v in data['identity']['project'].items()})
    form.update({'party_'+party['id']+'_'+k:v for k,v in data['identity']['participants'][0].items() if k != 'participant_id'})
    form.update({k:v for k,v in data['identity'].items() if k not in ('project','participants')})
    form.update({k:data[k] for k in ('asserted_state','occurred_at','effective_from','effective_until','discovered_at','component_scope','component_key','continuity')})
    response = client.post('/projects/project/attention', data=form)
    assert response.status_code == 303
    saved = store.get('project')
    assert len(saved.claims) == 1
    assert saved.claims[0]['event_proposition']['data']['identity'] == data['identity']
    assert not saved.applies and not saved.findings


def test_private_case_prevents_transaction_route_execution(project):
    _, _, _, _, client = project
    store, workspace, evidence, attention, party = source_case(project)
    root = record(store, workspace, evidence, attention, event_data(party))
    store.create_case(workspace, 'Private transaction', 'Private scope', 'someone-else')
    before = store._path_for('project').read_bytes()
    response = client.post('/projects/project/attention', data=dict(action='transaction_review',
        analysis_id=attention['id'], transaction_claim_id=root['id'], query_date='2024-06-01', reason='Inspect'))
    assert response.status_code == 403
    assert store._path_for('project').read_bytes() == before
