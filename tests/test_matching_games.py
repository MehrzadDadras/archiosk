import hashlib
import pytest
from tests.test_survey_evaluation import web_app
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceStore
from services.runtime_observation import read


@pytest.mark.parametrize('case,expected', [
    ('matching:fit','FIT'), ('matching:partial','UNRESOLVED'), ('matching:mandatory-failure','NON_FIT'),
    ('matching:known-partial','PARTIAL'),
    ('matching:historical','UNRESOLVED'), ('matching:repeated-claim','FIT'),
    ('matching:missing-provenance','UNRESOLVED'), ('matching:composition','MATCH'), ('matching:brief','UNRESOLVED'),
])
def test_matching_games_use_real_ui_owners_without_creating_investor_truth(web_app, case, expected):
    client = web_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='reviewer', role='admin', developer_mode=True, survey_observe=True)
    response = client.post('/admin/survey-evaluation', data={'case':case})
    assert response.status_code == 302
    run_id = response.location.rsplit('/',1)[-1]
    path = evaluation.location(web_app, run_id)
    record = evaluation._read(path)
    store = CaseWorkspaceStore(path/'registry')
    workspace = store.get(record['project_id'])
    result = workspace.analyses[-1]['governed_result']
    assert (result['model']['state'] if case.endswith('composition') else result['model_label']) == expected
    assert result['state'] == 'UNRESOLVED' and result['evaluation_only'] and not result['canonical']
    assert all(source['evaluation_only'] for source in workspace.sources)
    assert all(claim['author_type'] == 'ai' and claim['adoption_state'] == 'proposed' for claim in workspace.claims)
    assert not workspace.reviewer_validations
    before = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    page = client.get(response.location, follow_redirects=True)
    assert page.status_code == 200 and b'EVALUATION_INPUT' in page.data and b'UNRESOLVED' in page.data
    assert before == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    owners = {event['owner'] for event in read(web_app,response.headers['X-ARCHIOSK-Observation'])['events'] if event['phase'] == 'INVOKED'}
    assert 'services.case_workspace.CaseWorkspaceStore.record_subject_proposition' in owners
    assert 'services.cross_modal_investigation.match_normalized_criteria' in owners
    if case.endswith('composition'):
        assert 'services.cross_modal_investigation.cover_requirements' in owners
    if case.endswith('brief'):
        assert 'services.case_workspace.CaseWorkspaceStore.render_professional_review' in owners
        assert workspace.work_products[-1]['state'] == 'draft'
    if case.endswith('repeated-claim'):
        assert len(result['unselected_claim_ids']) == 3
    with pytest.raises(ValueError, match='attention scope'):
        evaluation.action(web_app,run_id,'confirm','reviewer')
