"""Evaluation inputs invoke ordinary owners; Reload only consumes persisted runs."""
import hashlib
import pytest
from tests.test_survey_evaluation import web_app
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceStore
from services.runtime_observation import read


@pytest.mark.parametrize('case', evaluation.REVIEW_GAMES)
def test_game_ui_invokes_shared_owners_and_preserves_evaluation_boundary(web_app, case):
    client = web_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='reviewer', role='admin', developer_mode=True, survey_observe=True)
    response = client.post('/admin/survey-evaluation', data={'case': case})
    assert response.status_code == 302
    run_id = response.location.rsplit('/', 1)[-1]
    path = evaluation.location(web_app, run_id)
    record = evaluation._read(path)
    store = CaseWorkspaceStore(path/'registry')
    workspace = store.get(record['project_id'])
    result = workspace.analyses[-1]['governed_result']
    assert result['evaluation_only'] and not result['canonical']
    assert all(source['evaluation_only'] for source in workspace.sources)
    assert all(row['authority'] == 'NOT_ESTABLISHED' for row in result['admissions'])
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    page = client.get(response.location, follow_redirects=True)
    assert page.status_code == 200 and b'EVALUATION_INPUT' in page.data
    assert record['attention_id'].encode() in page.data
    assert client.get(page.request.path+'?analysis='+record['attention_id']).status_code == 200
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    owners = {e['owner'] for e in read(web_app, response.headers['X-ARCHIOSK-Observation'])['events'] if e['phase'] == 'INVOKED'}
    assert 'services.case_workspace.CaseWorkspaceStore.record_go_attention' in owners
    if 'constraints' in evaluation.REVIEW_GAMES[case]:
        assert 'services.quantitative_investigation.probe_interval_constraints' in owners
        expected = 'NO_COMMON_ADMISSIBLE_CONDITION' if case.endswith('constraint-conflict') else 'CONSISTENT_WITH_TOLERANCE'
        assert result['model']['state'] == expected
        assert result['breakpoint']['state'] == ('UNRESOLVED' if case.endswith('constraint-conflict') else 'BOUNDARY_FOUND')
        if case.endswith('breakpoint'):
            assert result['breakpoint']['margin_to_failure'] == '5'
    else:
        assert 'services.cross_modal_investigation.inspect_continuum_participation' in owners
        assert 'services.drawing_conditions.review_representation_coverage' in owners
        if case in ('review:orphan', 'review:specification-gap', 'review:drawing-support-gap'):
            assert result['continuum']['state'] == 'ORPHANED_INFORMATION'
        if case == 'review:independent':
            assert result['continuum']['state'] == 'PARTICIPATION_NOT_REQUIRED'
        if case in ('review:section-gap', 'review:physical-path-gap'):
            assert result['coverage']['conditions'][0]['section_state'] == 'SECTION_COVERAGE_GAP'
        if case in ('review:essential', 'review:typical'):
            assert result['coverage']['minimum_sections_for_known_conditions']['minimum_count'] == 1
            assert all(row['section_state'] == 'QUALIFIED_COVERAGE' for row in result['coverage']['conditions'])
        if case == 'review:discipline-gap':
            assert any(row['state'] == 'DISCIPLINE_COVERAGE_GAP' for row in result['coverage']['conditions'][0]['disciplines'])
        if case == 'review:physical-path-gap':
            assert not result['coverage']['conditions'][0]['physical_control']['performance_established']
    assert client.post(response.location, data={'action':'confirm'}).status_code == 405
    with pytest.raises(ValueError, match='attention scope'):
        evaluation.action(web_app, run_id, 'confirm', 'reviewer')


def test_failed_fixture_does_not_publish_a_navigable_incomplete_game(web_app, monkeypatch):
    def unavailable(*args, **kwargs):
        raise ValueError('Controlled resolver unavailable')
    monkeypatch.setattr(CaseWorkspaceStore, 'run_professional_review', unavailable)
    with pytest.raises(ValueError, match='unavailable'):
        evaluation.create(web_app, 'review:orphan', 'reviewer')
    assert evaluation.recent(web_app) == []
