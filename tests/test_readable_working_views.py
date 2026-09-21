"""A readable view is a retained display projection, never replacement evidence."""
import copy
import hashlib

import pytest
from PIL import Image

from tests.test_kernel_mapping import project
from services import document_examination as dx


def native_source(project):
    import pymupdf
    from services.positioned_text import _native_positioned_lines
    _, store, workspace, _, _ = project
    source = workspace.sources[0]
    path = store.store_path/'native-labels.pdf'
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=250)
        page.insert_text((35, 75), 'DIMENSION 144.12 - retained original annotation', fontsize=12)
        document.save(path)
        text = page.get_text()
    source.update(file_path=str(path), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    store.save(workspace)
    store.register_pdf_page_structure(workspace, source['id'], [text])
    page = next(u for u in workspace.structural_units if u['source_id']==source['id'] and u['unit_type']=='page')
    positioned = _native_positioned_lines(path.read_bytes(), 0)
    store.register_positioned_text_regions(workspace, source['id'], page['id'], positioned['lines'],
        frame=positioned['frame'], extractor_version='pymupdf-native', actor='reviewer')
    return store, workspace, source, path


def test_mirror_renders_native_text_separately_and_preserves_original_and_readonly_reload(project):
    app, _, _, _, client = project
    store, workspace, source, path = native_source(project)
    original = path.read_bytes()
    evidence = copy.deepcopy(workspace.evidence_items)
    url = f'/projects/project/sources/{source["id"]}/review'
    response = client.post(url, data=dict(action='view_transform', view_action='MIRROR_HORIZONTAL', reason='Inspect opposite display viewpoint.'))
    assert response.status_code == 302
    saved = store.get('project')
    view = saved.derived_views[-1]
    annotations = view['view_transform']['readable_annotations']
    assert annotations['state'] == 'QUALIFIED'
    item = annotations['items'][0]
    assert item['placement_state'] == 'QUALIFIED_DISPLAY'
    assert item['box']['x'] == pytest.approx(1-item['anchor']['address']['x']-item['anchor']['address']['width'])
    assert item['text'] == 'DIMENSION 144.12 - retained original annotation'
    assert view['view_transform']['authority'] == 'NOT_ESTABLISHED'
    assert saved.evidence_items == evidence and path.read_bytes() == original
    before = store._path_for('project').read_bytes()
    page = client.get(url)
    assert page.status_code == 200 and b'TEXT RE-ORIENTED' in page.data
    assert b'not original source imagery' in page.data
    assert b'<text ' in page.data
    assert store._path_for('project').read_bytes() == before
    assert dx.working_view_bytes(store, saved, view)[0]


def test_child_view_transforms_retained_annotation_not_the_original_read(project):
    store, workspace, source, path = native_source(project)
    original = path.read_bytes()
    first = dx.create_working_view(store, workspace, source['id'], 'MIRROR_HORIZONTAL', 'First mirror.', 'reviewer')
    second = dx.create_working_view(store, workspace, source['id'], 'MIRROR_HORIZONTAL', 'Reverse the view only.', 'reviewer', parent_view_id=first['id'])
    item = second['view_transform']['readable_annotations']['items'][0]
    assert item['box']['x'] == pytest.approx(item['anchor']['address']['x'])
    assert item['source_text_sha256'] == first['view_transform']['readable_annotations']['items'][0]['source_text_sha256']
    assert path.read_bytes() == original


def test_unknown_raster_frame_keeps_readable_text_but_refuses_fabricated_position(project):
    _, store, workspace, _, client = project
    source = workspace.sources[0]
    path = store.store_path/'raster.png'
    Image.new('RGB', (100, 80), 'white').save(path)
    source.update(file_path=str(path), file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    store.save(workspace)
    unit = store.create_structural_unit(workspace, source['id'], 'image', 0)
    store.register_positioned_text_regions(workspace, source['id'], unit['id'],
        [dict(text='<script>not executable</script>', x=.1,y=.1,width=.4,height=.1)],
        frame=dict(coordinate_space='fraction_of_normalised_frame', normalised_size=[100,80]),
        extractor_version='controlled-existing-read', actor='reviewer')
    view = dx.create_working_view(store, workspace, source['id'], 'MIRROR_HORIZONTAL', 'Unknown processing frame.', 'reviewer')
    annotations = view['view_transform']['readable_annotations']
    assert annotations['state'] == 'PARTIAL' and annotations['items'][0]['box'] is None
    assert annotations['items'][0]['placement_state'] == 'UNRESOLVED'
    page = client.get(f'/projects/project/sources/{source["id"]}/review')
    assert page.status_code == 200 and b'<script>not executable</script>' not in page.data
    assert b'&lt;script&gt;not executable&lt;/script&gt;' in page.data
