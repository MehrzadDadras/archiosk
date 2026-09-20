"""Narrative configuration cannot supply authority or substitute scale for proof."""
import pytest
from tests.test_kernel_mapping import project

from services.cross_modal_investigation import (
    PROFESSIONAL_NARRATIVES, assess_review_resolution, expected_next_information,
)


def test_six_lenses_share_one_configuration_contract():
    assert len(PROFESSIONAL_NARRATIVES) >= 6
    for key, narrative in PROFESSIONAL_NARRATIVES.items():
        assert narrative.key == key and narrative.professional_lens
        assert narrative.review_objective and narrative.information_sequence
        assert narrative.resolution_questions and narrative.affected_disciplines
        assert narrative.governing_evidence_requirements and narrative.sufficiency_criteria
        assert 'Uncertainty and refusals' in narrative.presentation_structure


def test_finer_resolution_answers_a_missing_question_not_an_authority_upgrade():
    narrative = PROFESSIONAL_NARRATIVES['building_science']
    result = assess_review_resolution(narrative, 'OVERALL', 'LOCAL_TIE_IN', premise_ids=['source-region'])
    assert result['state'] == 'INSUFFICIENT_SCALE'
    assert 'overlap' in result['next_question']
    assert result['authority'] == 'UNCHANGED'
    assert assess_review_resolution(narrative, 'LOCAL_TIE_IN', 'LOCAL_TIE_IN', premise_ids=['region'])['state'] == 'QUALIFIED'
    assert assess_review_resolution(narrative, '1:5', 'LOCAL_TIE_IN', premise_ids=['region'])['state'] == 'UNRESOLVED'
    assert assess_review_resolution(narrative, 'LOCAL_TIE_IN', 'LOCAL_TIE_IN')['state'] == 'UNRESOLVED'


@pytest.mark.parametrize('key', PROFESSIONAL_NARRATIVES)
def test_expected_next_uses_classes_and_requires_context(key):
    narrative = PROFESSIONAL_NARRATIVES[key]
    current, expected = narrative.information_sequence[:2]
    args = dict(subject='subject-1', project_phase='design-review', discipline=narrative.affected_disciplines[0], evidence_state='QUALIFIED')
    assert expected_next_information(narrative, current, [expected], **args)['state'] == 'EXPECTED'
    assert expected_next_information(narrative, current, ['A101', 'A102'], **args)['state'] == 'MISSING'
    assert expected_next_information(narrative, current, [expected])['state'] == 'UNRESOLVED'
    assert expected_next_information(narrative, narrative.information_sequence[-1], [], **args)['state'] == 'UNRESOLVED'


def test_real_review_route_persists_results_and_reload_never_recomputes(project):
    import copy
    app, store, workspace, evidence, client = project
    analysis = store.record_go_attention(workspace, 'reviewer', 'Inspect envelope tie-in', [evidence['id']])
    original = copy.deepcopy((workspace.sources, workspace.evidence_items))
    response = client.post('/projects/project/attention', data=dict(action='professional_review',
        analysis_id=analysis['id'], narrative='building_science', focus_id=evidence['id'],
        subject='envelope corner', representation_class='PLAN', current_resolution='OVERALL',
        required_resolution='LOCAL_TIE_IN', project_phase='design-review', discipline='architectural',
        reason='Reviewing the overall representation for an exact seal termination'))
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['state'] == 'INSUFFICIENT_SCALE'
    assert result['admissions'][0]['authority'] == 'NOT_ESTABLISHED'
    assert not result['canonical']
    assert (saved.sources, saved.evidence_items) == original
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'INSUFFICIENT_SCALE' in page.data
    assert store._path_for('project').read_bytes() == before
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    owners = {e['owner'] for e in trace['events'] if e['phase'] == 'INVOKED'}
    assert 'services.cross_modal_investigation.assess_review_resolution' in owners
    assert 'services.cross_modal_investigation.expected_next_information' in owners
    assert 'services.cross_modal_investigation.trace_governing_root' in owners
    presentation = client.post('/projects/project/attention', data=dict(action='professional_presentation',
        review_id=saved.analyses[-1]['id']))
    assert presentation.status_code == 303
    rendered = store.get('project')
    assert rendered.analyses == saved.analyses
    product = rendered.work_products[-1]
    assert len(product['sections']) == 11
    from services.work_product_export import export_work_product
    import docx
    buffer, _ = export_work_product(product, 'docx')
    text = '\n'.join(p.text for p in docx.Document(buffer).paragraphs)
    assert 'INSUFFICIENT_SCALE' in text and 'UNRESOLVED' in text
    assert saved.analyses[-1]['id'] in text
    assert 'Representation classifications are explicit review assumptions' in text
    assert (rendered.sources, rendered.evidence_items) == original


def test_root_trace_follows_only_governing_dependencies_and_returns_without_laundering(project):
    from services.cross_modal_investigation import trace_governing_root
    _, store, workspace, target, _ = project
    parent = store.register_evidence_item(workspace, target['source_id'], 'direct_source_evidence', 'Controlling prose', 'text')
    peripheral = store.register_evidence_item(workspace, target['source_id'], 'direct_source_evidence', 'Nearby but unrelated', 'text')
    edge = store.record_relationship(workspace, 'evidence_item', target['id'], 'evidence_item', parent['id'], 'based_on')
    store.confirm_relationship(workspace, edge['id'], 'reviewer')
    store.record_relationship(workspace, 'evidence_item', target['id'], 'evidence_item', peripheral['id'], 'references')
    result = trace_governing_root(store, workspace, target['id'])
    assert [node['evidence_item_id'] for node in result['trace']] == [target['id'], parent['id']]
    assert result['state'] == 'UNRESOLVED' and result['root'] is None
    assert result['return_target'] == target['id']
    cycle = store.record_relationship(workspace, 'evidence_item', parent['id'], 'evidence_item', target['id'], 'based_on')
    store.confirm_relationship(workspace, cycle['id'], 'reviewer')
    assert trace_governing_root(store, workspace, target['id'])['state'] == 'REFUSED'
    assert trace_governing_root(store, workspace, 'foreign')['state'] == 'REFUSED'


def test_coverage_requires_review_and_reuses_one_representation_without_strengthening(project):
    import copy
    from services.drawing_conditions import review_representation_coverage
    _, store, workspace, original, client = project
    unit = store.create_structural_unit(workspace, original['source_id'], 'page', 0)
    region = store.create_addressable_region(workspace, unit['id'], 'rectangle', {'x': 0, 'y': 0, 'width': 100, 'height': 100})
    evidence = store.register_evidence_item(workspace, original['source_id'], 'direct_source_evidence',
        'Typical section applies to both recorded conditions', 'text', region_id=region['id'])
    attention = store.record_go_attention(workspace, 'reviewer', 'Review conditions', [evidence['id']])
    originals = copy.deepcopy((workspace.sources, workspace.evidence_items))
    conditions = []
    for meaning in ('Parapet', 'Recessed parapet'):
        response = client.post('/projects/project/attention', data=dict(action='record_condition',
            analysis_id=attention['id'], evidence_id=evidence['id'], meaning=meaning,
            affected_disciplines='structural, mechanical', required_resolution='ASSEMBLY_LAYERS',
            requires_section='yes', reason='Distinct condition explicitly located in this region'))
        assert response.status_code == 303
        workspace = store.get('project')
        condition = workspace.drawing_conditions[-1]
        conditions.append(condition)
        store.review_coverage_record(workspace, 'reviewer', attention['id'], condition['id'],
            'confirm_condition', 'Reviewed the located condition')
        representation = store.record_review_representation(workspace, 'reviewer', attention['id'], condition['id'],
            evidence['id'], 'structural', 'WALL_SECTION', 'ASSEMBLY_LAYERS', 'Explicitly applies to this condition')
        before = review_representation_coverage(store, workspace, [original['source_id']], PROFESSIONAL_NARRATIVES['building_science'])
        assert before['conditions'][-1]['section_state'] == 'SECTION_COVERAGE_GAP'
        store.review_coverage_record(workspace, 'reviewer', attention['id'], representation['id'],
            'resolve_representation', 'Reviewed scope and exceptions for this condition')
    result = review_representation_coverage(store, workspace, [original['source_id']], PROFESSIONAL_NARRATIVES['building_science'])
    assert result['inventory_completeness'] == 'UNRESOLVED'
    assert result['minimum_sections_for_known_conditions']['minimum_count'] == 1
    assert all(r['section_state'] == 'QUALIFIED_COVERAGE' for r in result['conditions'])
    for row in result['conditions']:
        assert {r['discipline']: r['state'] for r in row['disciplines']} == {
            'structural': 'QUALIFIED_COVERAGE', 'mechanical': 'DISCIPLINE_COVERAGE_GAP'}
        assert row['representations'][0]['admission']['authority'] == 'NOT_ESTABLISHED'
    assert (workspace.sources, workspace.evidence_items) == originals
    store.decide_drawing_observation(workspace, conditions[0]['id'], 'overridden', 'reviewer',
        meaning='Parapet with a materially different return', note='New condition scope')
    changed = review_representation_coverage(store, workspace, [original['source_id']], PROFESSIONAL_NARRATIVES['building_science'])
    assert changed['conditions'][0]['section_state'] == 'SECTION_COVERAGE_GAP'
    assert 'changed after applicability review' in changed['conditions'][0]['representations'][0]['reasons'][0]
    page = client.get('/projects/project/attention?analysis=' + attention['id'])
    assert b'Applicability review required' in page.data
    store.review_coverage_record(workspace, 'reviewer', attention['id'], workspace.discipline_assumptions[0]['id'],
        'resolve_representation', 'Reviewed the changed return and its applicability')
    restored = review_representation_coverage(store, workspace, [original['source_id']], PROFESSIONAL_NARRATIVES['building_science'])
    assert restored['conditions'][0]['section_state'] == 'QUALIFIED_COVERAGE'
    assert len(workspace.discipline_assumptions[0]['resolution_history']) == 2
    workspace.discipline_assumptions[0]['resolution_class'] = 'OVERALL'
    low = review_representation_coverage(store, workspace, [original['source_id']], PROFESSIONAL_NARRATIVES['building_science'])
    assert low['conditions'][0]['section_state'] == 'SECTION_COVERAGE_GAP'
    assert low['conditions'][0]['representations'][0]['resolution']['state'] == 'INSUFFICIENT_SCALE'


def test_composition_is_coverage_not_ranking_and_refuses_unbounded_search():
    from services.cross_modal_investigation import cover_requirements
    result = cover_requirements(['a', 'b'], {'one': ['a', 'b'], 'two': ['a'], 'three': ['b']})
    assert result['state'] == 'MATCH' and result['minimum_count'] == 1
    assert cover_requirements(['a', 'b'], {'one': ['a']})['state'] == 'PARTIAL'
    assert cover_requirements([], {})['state'] == 'UNRESOLVED'
    assert cover_requirements(['a'], {str(i): ['a'] for i in range(17)})['state'] == 'REFUSED'


@pytest.mark.parametrize('admission,currentness,expected', [
    ('SOURCE_REFERENCE', 'current', 'EXPECTED'), ('CONTESTED', 'current', 'CONTRADICTORY'),
    ('UNRESOLVED', 'current', 'UNRESOLVED'), ('SOURCE_REFERENCE', 'superseded', 'SUPERSEDED'),
    ('SOURCE_REFERENCE', 'removed', 'UNRESOLVED')])
def test_expected_next_carries_existing_admission_and_currentness(admission, currentness, expected):
    result = expected_next_information(PROFESSIONAL_NARRATIVES['building_science'], 'PLAN', ['ENLARGED_PLAN'],
        subject='envelope', project_phase='review', discipline='architectural', evidence_state='SOURCE_REFERENCE',
        next_evidence_state=admission, next_currentness=currentness)
    assert result['state'] == expected


def test_necessity_requires_unique_coverage_and_never_treats_overlap_as_agreement():
    from services.cross_modal_investigation import inspect_representation_necessity
    result = inspect_representation_necessity(['wall', 'roof', 'opening'],
        {'typical': ['wall', 'roof'], 'copy': ['wall', 'roof'], 'unique': ['opening']})
    rows = {r['representation_id']: r for r in result['representations']}
    assert rows['unique']['necessity_class'] == 'ESSENTIAL'
    assert rows['unique']['removal_state'] == 'COVERAGE_GAP'
    assert rows['typical']['necessity_class'] == 'REPRESENTATIVE'
    assert rows['typical']['duplicate_consistency'] == 'UNRESOLVED'
    assert rows['typical']['overlapping_representations'] == ['copy']
    assert not any(r['safe_to_remove'] for r in rows.values())
    assert result['minimum_sufficient_set']['minimum_count'] == 2


def test_physical_function_label_does_not_establish_continuity_or_capacity(project):
    from services.drawing_conditions import functional_layer_continuity
    narrative = PROFESSIONAL_NARRATIVES['physical_control']
    assert narrative.information_sequence == ('PHYSICAL_PHENOMENON', 'CONTROL_FUNCTION',
        'MATERIAL_ASSEMBLY', 'CONNECTION', 'CONTINUITY', 'FAILURE_PATH')
    result = functional_layer_continuity({'functional_layers': [
        {'function': 'air_control', 'intended': True, 'continues': True},
        {'function': 'water_control', 'intended': True, 'continues': False}]})
    assert all(row['state'] == 'review_needed' for row in result)
    assert not any(row['repair_proposed'] for row in result)


def test_continuum_is_expected_participation_not_connectivity_authority(project):
    from services.cross_modal_investigation import inspect_continuum_participation
    _, store, workspace, target, _ = project
    assert inspect_continuum_participation(store, workspace, target['id'])['state'] == 'CONTINUUM_PARTICIPATION_UNRESOLVED'
    assert inspect_continuum_participation(store, workspace, target['id'], 'independent')['state'] == 'PARTICIPATION_NOT_REQUIRED'
    assert inspect_continuum_participation(store, workspace, target['id'], 'upstream')['state'] == 'ORPHANED_INFORMATION'
    parent = store.register_evidence_item(workspace, target['source_id'], 'direct_source_evidence', 'Upstream source', 'text')
    edge = store.record_relationship(workspace, 'evidence_item', target['id'], 'evidence_item', parent['id'], 'based_on')
    assert inspect_continuum_participation(store, workspace, target['id'], 'upstream')['state'] == 'COORDINATION_GAP'
    store.confirm_relationship(workspace, edge['id'], 'reviewer')
    result = inspect_continuum_participation(store, workspace, target['id'], 'upstream')
    assert result['state'] == 'PARTICIPATION_PARTIAL'
    assert result['admission']['authority'] == 'NOT_ESTABLISHED'
    assert result['connections'][0]['role'] == 'upstream'
    assert inspect_continuum_participation(store, workspace, parent['id'], 'downstream')['state'] == 'PARTICIPATION_PARTIAL'
    assert inspect_continuum_participation(store, workspace, target['id'], 'both')['missing'] == ['downstream']
