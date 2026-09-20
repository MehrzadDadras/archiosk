"""Natural-language proposals choose capabilities; real owners retain control."""
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from tests.test_document_shop_deletion import env
from tests.test_document_shop_bulk import image_case
from services.conversational_turn import sanitize_typed_action
from services.capability_registry import ACTION_REGISTRY


@pytest.mark.parametrize('proposal', [
    {'action_id': 'DELETE_ITEMS', 'parameters': {}, 'user_requested': True},
    {'action_id': 'ROTATE_VIEW', 'parameters': {'degrees': 90.0}, 'user_requested': True},
    {'action_id': 'MIRROR_VIEW', 'parameters': {'axis': 'horizontal', 'source_id': 'foreign'}, 'user_requested': True},
    {'action_id': 'MIRROR_VIEW', 'parameters': {}, 'user_requested': True},
    {'action_id': 'FIT_VIEW', 'parameters': {}, 'user_requested': 'true'},
    {'action_id': 'FIT_VIEW', 'parameters': {}, 'user_requested': True, 'actor': 'admin'},
])
def test_model_cannot_supply_authority_selectors_or_ambiguous_parameters(proposal):
    assert sanitize_typed_action(proposal, ACTION_REGISTRY) is None


def test_ask_go_executes_real_view_and_reload_does_not_repeat_it(env):
    app, client, store, registry, root = env
    app.instance_path = str(root)
    app.config['ANTHROPIC_API_KEY'] = 'test-no-network'
    workspace = image_case(env)
    document = registry.get(workspace.project_id)
    document.filename = 'original.png'
    registry.save(document)
    source = workspace.sources[0]
    original_bytes = Path(source['file_path']).read_bytes()
    original_records = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.analyses))
    with client.session_transaction() as session:
        session.update(developer_mode=True, survey_observe=True)
    proposal = dict(action_id='ROTATE_VIEW', parameters={'degrees': 180}, user_requested=True)
    outcome = SimpleNamespace(ran=True, parsed={'answer': 'Requested a reversed working view.', 'command': proposal})
    with patch('services.llm_gateway.call_llm_json', return_value=outcome) as provider:
        response = client.post('/document-shop/jobs/' + workspace.project_id,
            data={'question': 'Please give this page a half turn.'})
    assert response.status_code == 302
    assert 'ROTATE_VIEW' in provider.call_args.kwargs['system_prompt']
    assert 'image_base64' not in provider.call_args.kwargs
    saved = store.get(workspace.project_id)
    assert len(saved.derived_views) == 1
    view = saved.derived_views[0]
    assert view['view_transform']['type'] == 'ROTATE_180'
    assert view['view_transform']['source_sha256'] == hashlib.sha256(original_bytes).hexdigest()
    assert (saved.sources, saved.evidence_items, saved.analyses) == original_records
    assert Path(source['file_path']).read_bytes() == original_bytes
    persisted = store._path_for(workspace.project_id).read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'ROTATE_180' in page.data
    assert str(root).encode() not in page.data
    assert store._path_for(workspace.project_id).read_bytes() == persisted
    image = client.get(f'/document-shop/jobs/{workspace.project_id}/working-view/{view["id"]}')
    assert image.status_code == 200 and image.mimetype == 'image/png'
    from services.runtime_observation import read
    owners = {e['owner'] for e in read(app, response.headers['X-ARCHIOSK-Observation'])['events'] if e['phase'] == 'INVOKED'}
    assert 'services.conversation_interpreter.execute_document_action' in owners
    assert 'services.document_examination.create_working_view' in owners


def test_executor_reloads_authorization_and_foreign_view_cannot_be_opened(env):
    _, client, store, _, _ = env
    workspace = image_case(env)
    from services.conversation_interpreter import execute_document_action
    from services.case_workspace import CaseWorkspaceError
    proposal = dict(action_id='FIT_VIEW', parameters={}, user_requested=True)
    current = store.get(workspace.project_id)
    current.owner = 'someone-else'
    store.save(current)
    with pytest.raises(CaseWorkspaceError):
        execute_document_action(store, workspace, workspace.sources[0]['id'], proposal, 'owner')
    assert not store.get(workspace.project_id).derived_views
    current.owner = 'owner'
    store.save(current)
    result = execute_document_action(store, current, current.sources[0]['id'], proposal, 'owner')
    foreign = image_case(env)
    assert client.get(f'/document-shop/jobs/{foreign.project_id}/working-view/{result["view_id"]}').status_code == 404
    store.move_document_shop_case(store.get(workspace.project_id), 'owner', 'trash')
    assert client.get(f'/document-shop/jobs/{workspace.project_id}/working-view/{result["view_id"]}').status_code == 404


@pytest.mark.parametrize('case', ['native_vector', 'embedded_raster', 'multiple_pages', 'stale_measurement'])
def test_north_up_uses_actual_measured_pdf_direction_and_preserves_original(env, case):
    import json
    import math
    import pymupdf
    from tests.test_document_shop_deletion import shell
    from services import survey_north, visual_examination
    from services.visual_classification import _pdf_page_raster
    from services.document_examination import create_working_view, working_view_bytes
    app, _, store, _, root = env
    workspace, _ = shell(env, 'EVALUATION_INPUT north-up.pdf')
    path = root / 'north.pdf'
    def rotated(points):
        cosine, sine = math.cos(math.radians(30)), math.sin(math.radians(30))
        return [(100 + cosine*(x-100)-sine*(y-100), 100 + sine*(x-100)+cosine*(y-100)) for x,y in points]
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=200)
        page.draw_polyline(rotated([(100,20),(65,80),(135,80)]), closePath=True, color=(0,0,0), fill=(0,0,0))
        page.draw_polyline(rotated([(94,75),(106,75),(106,170),(94,170)]), closePath=True, color=(0,0,0), fill=(0,0,0))
        if case == 'embedded_raster':
            from PIL import Image
            import io
            image = io.BytesIO()
            Image.new('RGB', (10, 10), 'white').save(image, format='PNG')
            page.insert_image(pymupdf.Rect(180, 180, 190, 190), stream=image.getvalue())
        if case == 'multiple_pages':
            pdf.new_page(width=200, height=200)
        pdf.save(path)
    original = path.read_bytes()
    source = store.add_source(workspace, kind='drawing', name='EVALUATION_INPUT north.pdf',
        file_path=str(path), file_hash=hashlib.sha256(original).hexdigest(), actor='owner')
    workspace.sources[0]['evaluation_only'] = True
    store.save(workspace)
    measured = survey_north.measure_north(_pdf_page_raster(original), dict(x=0,y=0,w=1,h=1))
    assert measured['ok']
    candidate = survey_north.normalise_candidates([dict(id='north', source_type='survey_arrow',
        reference_type='TRUE_NORTH', reference_text='Explicit EVALUATION_INPUT True North',
        provenance='Measured from the retained PDF raster; reference type is an evaluation premise',
        applicability='THIS_VIEW', degrees=measured['degrees'], read_certainty='RECOVERED',
        bind_certainty='RECOVERED', bind_basis='declared', source_region=dict(x=0,y=0,w=1,h=1))])[0]
    candidate.update(measured_degrees=measured['degrees'], measured_ok=True, measured_reason=measured['reason'],
                     measure_version=survey_north.MEASURE_VERSION)
    if case == 'stale_measurement':
        # A previously coherent reading belongs to a different orientation.
        # Repeated resolver success cannot bind it to today's retained bytes.
        candidate.update(degrees=(measured['degrees'] + 30) % 360,
                         measured_degrees=(measured['degrees'] + 30) % 360)
    store.register_evidence_item(workspace, source['id'], 'ai_generated_proposal',
        json.dumps(dict(graph=dict(north_candidates=[candidate]))), visual_examination.VISUAL_CONTENT_TYPE)
    original_records = copy.deepcopy((workspace.sources, workspace.evidence_items))
    if case != 'native_vector':
        before = store._path_for(workspace.project_id).read_bytes()
        reasons = {'embedded_raster': 'embedded raster', 'multiple_pages': 'explicit page',
                   'stale_measurement': 'does not corroborate'}
        with app.app_context(), pytest.raises(ValueError, match=reasons[case]):
            create_working_view(store, workspace, source['id'], 'ALIGN_NORTH_UP',
                'Try the retained direction without inventing premises', 'owner')
        assert store._path_for(workspace.project_id).read_bytes() == before
        assert Path(source['file_path']).read_bytes() == original
        assert not workspace.derived_views
        return
    with app.app_context():
        view = create_working_view(store, workspace, source['id'], 'ALIGN_NORTH_UP',
            'Align the established evaluation direction in a derived view', 'owner')
    raw, _ = working_view_bytes(store, workspace, view)
    aligned = survey_north.measure_north(raw, dict(x=0,y=0,w=1,h=1))
    assert aligned['ok'] and survey_north.angular_delta(aligned['degrees'], 0) < 2
    assert view['view_transform']['north_premise']['state'] == 'ESTABLISHED'
    assert view['view_transform']['rendering']['source_sha256'] == hashlib.sha256(original).hexdigest()
    assert view['view_transform']['evaluation_only']
    assert Path(source['file_path']).read_bytes() == original
    assert (workspace.sources, workspace.evidence_items) == original_records


def test_north_up_refuses_unrectified_image_without_inventing_a_frame(env):
    from services.document_examination import create_working_view
    app, _, store, _, _ = env
    workspace = image_case(env)
    before = store._path_for(workspace.project_id).read_bytes()
    with app.app_context(), pytest.raises(ValueError, match='unresolved'):
        create_working_view(store, workspace, workspace.sources[0]['id'], 'ALIGN_NORTH_UP', 'Put north up', 'owner')
    assert store._path_for(workspace.project_id).read_bytes() == before
