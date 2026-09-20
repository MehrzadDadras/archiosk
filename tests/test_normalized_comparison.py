import copy
import pytest
from tests.test_kernel_mapping import project
from services.cross_modal_investigation import compare_normalized_information
from services.quantitative_investigation import compare_scalar_values
from services.case_workspace import CaseWorkspaceError


def premise(value='100', **changes):
    return dict(dict(subject_key='source:one', property_key='width', scope_key='interface-1',
        kind='NUMBER', basis='Explicit analytical premise, not an established reading.', premise_ids=['e1'],
        qualifiers=[], view_basis='VIEW_INVARIANT', view_id=None, value=value, unit='mm', vocabulary=''), **changes)


@pytest.mark.parametrize('operator,required,candidate,state', [
    ('EQUAL','100.0','1e2','MATCH'), ('EQUAL','100','101','NON_MATCH'),
    ('AT_LEAST','100','101','MATCH'), ('AT_MOST','100','101','NON_MATCH'),
    ('EQUAL',None,'100','UNRESOLVED'), ('EQUAL',True,'1','UNRESOLVED'),
    ('EQUAL','NaN','100','UNRESOLVED'), ('EQUAL','1e10000','100','UNRESOLVED'),
    ('SIMILAR','100','100','REFUSED')])
def test_shared_scalar_predicates_are_bounded(operator, required, candidate, state):
    assert compare_scalar_values(required, candidate, operator)['state'] == state


@pytest.mark.parametrize('change,state', [
    ({'scope_key':'other-interface'},'INCOMPARABLE'), ({'property_key':'height'},'INCOMPARABLE'),
    ({'unit':'in'},'INCOMPARABLE'), ({'qualifiers':None},'UNRESOLVED'),
    ({'qualifiers':['approximate']},'PARTIAL'), ({'view_basis':'UNRESOLVED'},'UNRESOLVED'),
    ({'view_basis':'NORMALIZED_VIEW','view_id':None},'UNRESOLVED'),
    ({'kind':'PROSE'},'INCOMPARABLE'), ({'authority':'ESTABLISHED'},'REFUSED'),
    ({'premise_ids':[]},'UNRESOLVED')])
def test_scope_units_qualifiers_viewpoint_and_authority_cannot_be_laundered(change, state):
    result = compare_normalized_information(premise(), premise(**change))
    assert result['state'] == state
    assert result['factual_consistency'] == 'UNRESOLVED' and not result['canonical']
    assert result['authority'] == 'UNCHANGED'


def test_token_sets_require_explicit_common_vocabulary_and_do_not_match_prose():
    left = premise(['CERT_A','REGION_ON'], kind='TOKEN_SET', vocabulary='declared-catalogue', unit='')
    right = premise(['CERT_A','REGION_ON','CERT_B'], kind='TOKEN_SET', vocabulary='declared-catalogue', unit='')
    assert compare_normalized_information(left, right, operator='CONTAINS_ALL')['state'] == 'MATCH'
    right['value'] = ['CERT_A']
    assert compare_normalized_information(left, right, operator='CONTAINS_ALL')['predicate']['missing'] == ['REGION_ON']
    right['vocabulary'] = 'unmapped-other-catalogue'
    assert compare_normalized_information(left, right)['state'] == 'INCOMPARABLE'
    assert compare_normalized_information(premise(kind='PROSE'), premise(kind='PROSE'))['state'] == 'UNRESOLVED'


def test_participant_uses_existing_graph_identity_without_granting_authority(project):
    _, store, workspace, evidence, client = project
    party = store.record_participant(workspace, 'Example company', 'proponent', 'reviewer')
    edge = store.record_evidence_relationship(workspace, 'participant', party['id'], 'evidence_item', evidence['id'],
        'references', reason='Company reference is not a proven capability', created_by='reviewer')
    store.confirm_relationship(workspace, edge['id'], 'reviewer')
    assert store.resolve_relationship_status(workspace, edge['id'])['status'] == 'confirmed'
    assert store.admit_proposition(workspace, evidence['id'])['authority'] == 'NOT_ESTABLISHED'
    page = client.get('/projects/project/kernel?item=participants:'+party['id'])
    assert page.status_code == 200 and party['id'].encode() in page.data and b'Entity' in page.data
    foreign = store.get_or_create('foreign')
    assert store._resolve_mm6_endpoint(foreign, 'participant', party['id']) is None


def test_comparison_route_invokes_shared_owner_and_reload_preserves_source_records(project):
    app, store, workspace, evidence, client = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Compare explicit width hypotheses', [evidence['id']])
    original = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.relationships))
    form = dict(action='information_comparison', analysis_id=attention['id'], kind='NUMBER', property_key='width',
        operator='EQUAL', reason='Explicit view-invariant scalar hypotheses; not source-extracted measurements.')
    for side in ('left','right'):
        form.update({side+'_subject':'source:'+evidence['source_id'], side+'_evidence':evidence['id'],
            side+'_scope':'interface-1', side+'_value':'100', side+'_unit':'mm', side+'_qualifiers':'[]', side+'_view':'VIEW_INVARIANT'})
    response = client.post('/projects/project/attention', data=form)
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['comparison']['state'] == 'MATCH'
    assert result['state'] == 'EVALUATION_INPUT' and result['evaluation_only'] and not result['canonical']
    assert result['comparison']['factual_consistency'] == 'UNRESOLVED'
    assert (saved.sources, saved.evidence_items, saved.relationships) == original
    persisted = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'model MATCH' in page.data and b'not corrected machine readings' in page.data
    assert store._path_for('project').read_bytes() == persisted
    from services.runtime_observation import read
    owners = {event['owner'] for event in read(app, response.headers['X-ARCHIOSK-Observation'])['events'] if event['phase'] == 'INVOKED'}
    assert 'services.cross_modal_investigation.compare_normalized_information' in owners
    assert 'services.quantitative_investigation.compare_scalar_values' in owners
    left = premise(subject_key='source:'+evidence['source_id'], premise_ids=[evidence['id']])
    with pytest.raises(CaseWorkspaceError, match='unavailable'):
        store.run_information_comparison(saved, 'reviewer', attention['id'], left,
            dict(left, subject_key='participant:foreign'), 'EQUAL', 'No cross-project identities')
    assert store._path_for('project').read_bytes() == persisted


def test_retained_view_chain_is_verified_and_never_grants_factual_consistency(project):
    import hashlib
    from PIL import Image
    from services.document_examination import create_working_view
    _, store, workspace, evidence, _ = project
    source = workspace.sources[0]
    path = store.store_path/'original.png'
    Image.new('RGB', (30,20), 'white').save(path)
    source.update(file_path=str(path), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    store.save(workspace)
    original = path.read_bytes()
    view = create_working_view(store, workspace, source['id'], 'MIRROR_HORIZONTAL', 'Declared opposite viewing hypothesis', 'reviewer')
    attention = store.record_go_attention(workspace, 'reviewer', 'Compare declared values after a retained transform', [evidence['id']])
    left = premise(subject_key='source:'+source['id'], premise_ids=[evidence['id']], view_basis='NORMALIZED_VIEW', view_id=view['id'])
    right = premise(subject_key='source:'+source['id'], premise_ids=[evidence['id']])
    result = store.run_information_comparison(workspace, 'reviewer', attention['id'], left, right, 'EQUAL', 'Explicit hypotheses')['governed_result']
    assert result['views'][0]['transform']['type'] == 'MIRROR_HORIZONTAL'
    assert 'file_path' not in result['views'][0]['transform']
    assert result['comparison']['factual_consistency'] == 'UNRESOLVED'
    assert path.read_bytes() == original
    persisted = store._path_for('project').read_bytes()
    with pytest.raises(CaseWorkspaceError, match='referenced source'):
        store.run_information_comparison(workspace, 'reviewer', attention['id'], dict(left, view_id='foreign'), right, 'EQUAL', 'Invalid view')
    path.write_bytes(b'TAMPERED TEST INPUT')
    with pytest.raises(ValueError, match='recorded hash'):
        store.run_information_comparison(workspace, 'reviewer', attention['id'], left, right, 'EQUAL', 'Reject changed original')
    assert store._path_for('project').read_bytes() == persisted


def test_stale_attention_cannot_recreate_missing_evidence_or_activate_archived_case(project):
    _, store, workspace, evidence, _ = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Bounded model', [evidence['id']])
    left = premise(subject_key='source:'+evidence['source_id'], premise_ids=[evidence['id']])
    workspace.document_desk_state = 'archive'
    with pytest.raises(CaseWorkspaceError, match='active document'):
        store.run_information_comparison(workspace, 'reviewer', attention['id'], left, left, 'EQUAL', 'Do not activate archive')
    workspace.document_desk_state = 'active'
    workspace.evidence_items.clear()
    with pytest.raises(CaseWorkspaceError, match='no longer available'):
        store.run_information_comparison(workspace, 'reviewer', attention['id'], left, left, 'EQUAL', 'Do not reconstruct missing evidence')
