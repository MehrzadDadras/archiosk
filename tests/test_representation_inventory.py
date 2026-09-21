"""Scoped representation redundancy consumes the actual reviewed Claim owner."""
import copy

import pytest

from tests.test_kernel_mapping import project
from tests.test_scoped_proposition_review import prepared
from tests.test_transaction_identity import admit
from tests.test_normalized_comparison import premise
from services.cross_modal_investigation import inspect_representation_necessity


def inventories(project, *, mismatch=False, review_inventory=True, incomplete=False):
    store, workspace, first, _, _, proposal, _ = prepared(project)
    unit = store.create_structural_unit(workspace, first['source_id'], 'page', 0)
    region = store.create_addressable_region(workspace, unit['id'], 'rectangle', {'x':0,'y':0,'width':100,'height':100})
    first = store.register_evidence_item(workspace, first['source_id'], 'direct_source_evidence', first['content'], 'text', region_id=region['id'])
    region = store.create_addressable_region(workspace, unit['id'], 'rectangle', {'x':0,'y':100,'width':100,'height':100})
    second = store.register_evidence_item(workspace, first['source_id'], 'direct_source_evidence', first['content'], 'text', region_id=region['id'])
    attention = store.record_go_attention(workspace, 'reviewer', 'Review duplicate representations', [first['id'], second['id']])
    subject = 'participant:' + workspace.participants[-1]['id']
    claims = []
    for index, evidence in enumerate((first, second)):
        def append(value, key, kind='NUMBER', vocabulary='', reviewed=True):
            normalized = premise(value, subject_key=subject, property_key=key, scope_key='known-envelope-condition',
                kind=kind, unit='mm' if kind == 'NUMBER' else '', vocabulary=vocabulary, premise_ids=[evidence['id']])
            claim = store.record_subject_proposition(workspace, 'reviewer', attention['id'], normalized,
                'PROJECT_DOCUMENT', 'DATED_REQUIREMENT', evidence['content'], 'Controlled fixture interpretation.',
                as_of='2024-01-01', valid_until='2024-12-31', attribution='agent_assessment')
            if reviewed:
                admit(store, workspace, claim, proposal)
            return claim
        value = append('80' if mismatch and index else '100', 'clearance')
        claims.append(value)
        if not incomplete or index == 0:
            append([value['id']], 'complete_representation_inventory', 'TOKEN_SET',
                'representation:' + evidence['id'], reviewed=review_inventory)
    coverage = {row['id']: ['wall:structural'] for row in (first, second)}
    return store, workspace, attention, first, coverage, claims


@pytest.mark.parametrize('options,expected', [
    ({}, 'REDUNDANT_CONSISTENT'),
    ({'mismatch':True}, 'REDUNDANT_CONFLICTING'),
    ({'review_inventory':False}, 'NECESSITY_UNRESOLVED'),
    ({'incomplete':True}, 'NECESSITY_UNRESOLVED'),
])
def test_reviewed_complete_inventory_is_required_for_scoped_redundancy(project, options, expected):
    store, workspace, _, _, coverage, _ = inventories(project, **options)
    before = store._path_for('project').read_bytes()
    result = inspect_representation_necessity(['wall:structural'], coverage,
        store=store, workspace=workspace, query_date='2024-06-01')
    assert {r['necessity_class'] for r in result['representations']} == {expected}
    assert not any(r['safe_to_remove'] for r in result['representations'])
    assert store._path_for('project').read_bytes() == before
    stale = inspect_representation_necessity(['wall:structural'], coverage,
        store=store, workspace=workspace, query_date='2025-06-01')
    assert all(r['duplicate_consistency'] == 'UNRESOLVED' for r in stale['representations'])


def test_real_professional_review_retains_comparison_and_reload_does_not_recompute(project):
    app, _, _, _, client = project
    store, workspace, attention, first, coverage, _ = inventories(project, mismatch=True)
    condition = store.record_review_condition(workspace, 'reviewer', attention['id'], first['id'],
        'Controlled envelope condition', ['structural'], 'ASSEMBLY_LAYERS', True, 'Test scope')
    store.review_coverage_record(workspace, 'reviewer', attention['id'], condition['id'], 'confirm_condition', 'Test review')
    for identifier in coverage:
        representation = store.record_review_representation(workspace, 'reviewer', attention['id'], condition['id'],
            identifier, 'structural', 'WALL_SECTION', 'ASSEMBLY_LAYERS', 'Applies to controlled condition')
        store.review_coverage_record(workspace, 'reviewer', attention['id'], representation['id'], 'resolve_representation', 'Test review')
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    response = client.post('/projects/project/attention', data=dict(action='professional_review',
        analysis_id=attention['id'], narrative='building_science', focus_id=first['id'], subject='Envelope',
        representation_class='WALL_SECTION', current_resolution='ASSEMBLY_LAYERS', required_resolution='ASSEMBLY_LAYERS',
        project_phase='review', discipline='structural', reason='Inspect scoped representations', query_date='2024-06-01'))
    assert response.status_code == 303
    saved = store.get('project')
    rows = saved.analyses[-1]['governed_result']['coverage']['representation_necessity']['representations']
    assert {r['necessity_class'] for r in rows} == {'REDUNDANT_CONFLICTING'}
    assert rows[0]['comparison_proof'][0]['comparisons'][0]['result']['state'] == 'NON_MATCH'
    assert (saved.sources, saved.evidence_items, saved.claims) == before
    persisted = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'REDUNDANT_CONFLICTING' in page.data
    assert store._path_for('project').read_bytes() == persisted
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase'] == 'INVOKED' and e['owner'].endswith('.inspect_representation_necessity') for e in trace['events'])
