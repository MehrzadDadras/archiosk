"""Non-destructive UI transforms use existing owners and never upgrade geometry."""
import copy
import hashlib
import io

import pytest
from PIL import Image

from tests.test_kernel_mapping import project
from services import image_intake, derived_view
from services.capability_registry import VIEW_ACTIONS, resolve_view_action


@pytest.mark.parametrize('action', [key for key, spec in VIEW_ACTIONS.items() if key not in ('CROP', 'FIT') and not spec.get('requires_premises')])
def test_typed_transform_preserves_original_and_qualification(action):
    image = Image.new('RGB', (30, 20), 'white')
    image.putpixel((1, 2), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    raw = buffer.getvalue()
    before = hashlib.sha256(raw).hexdigest()
    preview, transform = image_intake.transform_document_preview(raw, 'original.png', action)
    assert hashlib.sha256(raw).hexdigest() == before
    assert transform['authority'] == 'NOT_ESTABLISHED'
    assert transform['text_rendering'] == 'ORIGINAL_PIXELS_TRANSFORMED'
    assert transform['matrix'] and preview != raw
    assert not derived_view.may_measure({'view_transform': transform, 'scale_state': 'QUANTITATIVE'})[0]
    with pytest.raises(ValueError):
        derived_view.to_view_coordinates({'view_transform': transform}, 1, 2)


def test_real_ui_transform_lineage_original_unchanged_and_reload(project):
    app, store, workspace, evidence, client = project
    source = workspace.sources[0]
    path = store.store_path / 'original.png'
    Image.new('RGB', (30, 20), 'white').save(path)
    source.update(file_path=str(path), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    store.save(workspace)
    original = path.read_bytes()
    prior = copy.deepcopy((workspace.sources, workspace.evidence_items))
    url = f"/projects/project/sources/{source['id']}/review"
    response = client.post(url, data={'action': 'view_transform', 'view_instruction': 'rotate 180 degrees',
                                     'reason': 'Inspect reading orientation'})
    assert response.status_code == 302
    saved = store.get('project')
    assert len(saved.derived_views) == 1
    view = saved.derived_views[0]
    assert view['view_transform']['source_sha256'] == hashlib.sha256(original).hexdigest()
    assert (saved.sources, saved.evidence_items) == prior
    assert path.read_bytes() == original
    persisted = store._path_for('project').read_bytes()
    assert client.get(url).status_code == 200
    image_url = f"/projects/project/sources/{source['id']}/working-view/{view['id']}"
    assert client.get(image_url).status_code == 200
    assert store._path_for('project').read_bytes() == persisted
    assert client.get(image_url.replace(source['id'], 'foreign')).status_code == 404
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase'] == 'INVOKED' and e['owner'].endswith('.transform_document_preview') for e in trace['events'])


def test_ambiguous_viewpoint_and_north_never_guessed():
    assert resolve_view_action('turn this around') == 'ROTATE_180'
    assert resolve_view_action('show the opposite side') == 'OPPOSITE_SIDE'
    assert resolve_view_action('put north up') == 'NORTH_UP'
    assert resolve_view_action('align these two details') == 'ALIGN'


def test_crop_and_fit_record_exact_sampling_premises():
    buffer = io.BytesIO()
    Image.new('RGB', (100, 80), 'white').save(buffer, 'PNG')
    raw = buffer.getvalue()
    _, transform = image_intake.transform_document_preview(raw, 'source.png', 'CROP', {'box': [.1,.1,.9,.9]})
    assert transform['parameters']['pixel_box'] == [10,8,90,72]
    assert transform['output_size'] == [80,64]
    _, fitted = image_intake.transform_document_preview(raw, 'source.png', 'FIT', {'max_edge': 50})
    assert fitted['output_size'] == [50,40]
    with pytest.raises(ValueError):
        image_intake.transform_document_preview(raw, 'source.png', 'CROP', {'box': [0,0,0,0]})
