import copy
import pytest

from tests.test_kernel_mapping import project
from tests.test_role_composition import composition_inputs
from services.cross_modal_investigation import cover_requirements, evaluate_requirement_coverage


def requirement(key='capital', classification='MANDATORY', divisible=False, basis=None):
    return dict(id=key, normalization=dict(kind='NUMBER', value='100', unit='CAD',
        property_key=key, scope_key='opportunity', qualifiers=[]),
        policy=dict(classification=classification, divisible=divisible, combination_basis=basis))


def candidate(state='MATCH', amount='100', **changes):
    return dict(dict(state=state, evidence_refs=['retained-claim'], operator='AT_LEAST',
        normalization=dict(kind='NUMBER', value=amount, unit='CAD', property_key='capital', scope_key='opportunity', qualifiers=[])), **changes)


@pytest.mark.parametrize('rows,policy,expected', [
    ({'a':candidate()}, requirement(), 'INDIVIDUAL_CONFIGURATION_FEASIBLE'),
    ({'a':candidate('NON_MATCH', '50')}, requirement(divisible=True), 'PARTIAL_CONFIGURATION'),
    ({'a':candidate('UNRESOLVED', evidence_refs=[])}, requirement(), 'CONFIGURATION_UNRESOLVED'),
    ({'a':candidate('NON_MATCH')}, requirement(classification='HARD_EXCLUSION'), 'CONFIGURATION_NON_FIT'),
    ({'a':candidate('NON_MATCH','50'),'b':candidate('NON_MATCH','50')}, requirement(divisible=True), 'CONFIGURATION_UNRESOLVED'),
    ({'a':candidate('NON_MATCH','50'),'b':candidate('NON_MATCH','50')},
     requirement(divisible=True,basis={'evidence_refs':['combination-claim']}), 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED'),
])
def test_requirement_precedence_and_supported_divisibility(rows, policy, expected):
    original = copy.deepcopy(rows)
    result = evaluate_requirement_coverage([policy], {k:{'capital':v} for k,v in rows.items()}, list(rows))
    assert result['state'] == expected
    assert result['factual_state'] == 'UNRESOLVED' and not result['canonical']
    assert rows == original


def test_optional_fit_cannot_repair_unknown_mandatory_or_positive_conflict():
    policies = [requirement(),requirement('optional','OPTIONAL')]
    rows = {'a':{'capital':candidate('UNRESOLVED',evidence_refs=[]),'optional':candidate()}}
    assert evaluate_requirement_coverage(policies,rows,['a'])['state']=='CONFIGURATION_UNRESOLVED'
    policies[0]['policy']['classification']='HARD_EXCLUSION'
    rows['a']['capital']=candidate('NON_MATCH')
    assert evaluate_requirement_coverage(policies,rows,['a'])['state']=='CONFIGURATION_NON_FIT'


def test_shared_solver_preserves_all_minima_and_failed_smaller_sets():
    policies=[requirement('equity'),requirement('debt'),requirement('operator')]
    rows={party:{role:candidate('MATCH' if role==covered else 'NON_MATCH') for role in ('equity','debt','operator')}
          for party,covered in [('a','equity'),('b','debt'),('c','operator'),('d','operator')]}
    result=cover_requirements(['equity','debt','operator'],dict.fromkeys(rows,[]),
        configuration_evaluator=lambda parties:evaluate_requirement_coverage(policies,rows,parties))
    assert result['minimum_count']==3
    assert result['configurations']==[['a','b','c'],['a','b','d']]
    assert all(not t['result']['coverage_complete'] for t in result['tested_configurations'] if len(t['participant_ids'])<3)
    assert all(t['result']['state']=='PARTNERSHIP_COMPATIBILITY_UNRESOLVED' for t in result['tested_configurations'] if t['result']['coverage_complete'])


def test_real_route_retains_coverage_assignments_and_history_without_mutation(project):
    app,store,_,_,client=project
    attention,parties,claims,runs=composition_inputs(project,mandatory=True)
    workspace=store.get('project')
    old=copy.deepcopy((workspace.sources,workspace.evidence_items,workspace.claims,workspace.analyses))
    form=dict(action='role_composition',coverage_mode='requirements',analysis_id=attention['id'],
        matching_id=[r['id'] for r in runs],required_role_id=[c['id'] for c in claims[:2]],reason='Collective role requirements.')
    response=client.post('/projects/project/attention',data=form)
    assert response.status_code==303
    workspace=store.get('project')
    result=workspace.analyses[-1]['governed_result']
    assert result['configuration_set_state']=='MINIMAL_CONFIGURATION_SET'
    assert result['model']['minimum_count']==2
    minimum=result['minimum_configurations'][0]
    assert minimum['result']['state']=='PARTNERSHIP_COMPATIBILITY_UNRESOLVED'
    assert all(a['coverage_state']=='COVERED' and a['evidence_refs'] for a in minimum['result']['assignments'])
    assert all(not r['remaining']['coverage_complete'] for r in minimum['removal_checks'])
    assert (workspace.sources,workspace.evidence_items,workspace.claims,workspace.analyses[:-1])==old
    before=store._path_for('project').read_bytes()
    assert client.get(response.location).status_code==200
    assert store._path_for('project').read_bytes()==before
    from services.runtime_observation import read
    trace=read(app,response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase']=='INVOKED' and e['owner'].endswith('.evaluate_requirement_coverage') for e in trace['events'])


def test_coverage_without_evidence_never_closes_requirement():
    result=evaluate_requirement_coverage([requirement()],{'a':{'capital':candidate(evidence_refs=[])}},['a'])
    assert result['state']=='CONFIGURATION_UNRESOLVED'
    assert not result['coverage_complete']


@pytest.mark.parametrize('case,count,configurations', [
    ('coverage-one',1,1),('coverage-two',2,1),('coverage-three',3,1),
    ('coverage-alternatives',2,2),('additive-capital',2,1),('additive-unresolved',None,0),
])
def test_real_evaluation_games_use_the_shared_persisted_composition(project,case,count,configurations):
    app,normal_store,workspace,_,client=project
    from services import survey_evaluation as evaluation
    from services.case_workspace import CaseWorkspaceStore
    from services.runtime_observation import read
    untouched=normal_store._path_for(workspace.project_id).read_bytes()
    response=client.post('/admin/survey-evaluation',data={'case':'matching:'+case})
    assert response.status_code==302
    location=evaluation.location(app,response.location.rsplit('/',1)[-1])
    record=evaluation._read(location)
    store=CaseWorkspaceStore(location/'registry')
    retained=store.get(record['project_id'])
    result=retained.analyses[-1]['governed_result']
    assert result['model'].get('minimum_count')==count
    assert len(result['minimum_configurations'])==configurations
    assert result['state']=='UNRESOLVED' and result['evaluation_only']
    url=response.location+'/attention?analysis='+record['attention_id']
    before=store._path_for(retained.project_id).read_bytes()
    page=client.get(url)
    assert page.status_code==200 and b'Governed factual status' in page.data
    assert store._path_for(retained.project_id).read_bytes()==before
    assert normal_store._path_for(workspace.project_id).read_bytes()==untouched
    trace=read(app,response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase']=='INVOKED' and e['owner'].endswith('.cover_requirements') for e in trace['events'])
