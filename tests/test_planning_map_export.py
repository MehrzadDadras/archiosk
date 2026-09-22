import copy
import io
import json
import zipfile

import pytest
from PIL import Image
from services import planning_map_export as maps
from services import planning_result_view as views
from services import deterministic_spatial as spatial


def specimen():
    def poly(x,y,s):
        return {"type":"Polygon","coordinates":[[[x,y],[x,y+s],[x+s,y+s],[x+s,y],[x,y]]]}
    parcel=poly(10,10,10); zone=poly(0,0,100)
    p={"geometry":parcel,"geometry_id":spatial.geometry_hash(parcel),"spatial_reference":"EPSG:3857",
       "parcel_identifier":"SYNTHETIC-PARCEL","source":"City fixture","layer":"Property Boundary"}
    z={"geometry":zone,"geometry_id":spatial.geometry_hash(zone),"source_crs":"EPSG:3857",
       "feature_identifier":"SYNTHETIC-ZONE","source":"City fixture","layer":"Zoning Area",
       "zone_label":"R (x8)","zone_code":"R","url":"https://example.invalid/fixture", "qualified":True,
       "exception_identifier":8,"exception_status":"EXCEPTION_TEXT_UNRESOLVED","spatial_relation":"INSIDE"}
    return {"document":{"subject":{"normalized_address":"Synthetic test site","parcel_identifier":"SYNTHETIC-PARCEL"},
            "result_status":"UNRESOLVED","statements":[{"statement_id":"zone","kind":"AUTHORITY_SAYS","topic":"ZONING_DESIGNATION","text":"The parcel lies within R (x8)."},
            {"statement_id":"exception","kind":"AUTHORITY_SAYS","topic":"SITE_SPECIFIC_EXCEPTION","text":"Exception 8 text is unresolved."}]},
            "spatial_tokens":{"zoning_area":spatial.relate({"crs":"EPSG:3857","geometry":parcel},{"crs":"EPSG:3857","geometry":zone})},
            "retrieval":{"retrieved_at":"2026-09-14T00:00:00Z","zone_features_examined":True,"zone_features":[z],
            "exception":{"acquired":False},"zoning_attributes":{"ZN_STRING":"R (x8)","ZN_ZONE":"R","ZN_EXCPTN":"Y","ZN_EXCPTN_NO":8},
            "visual_geometry":{"parcel":p,"zoning":dict(z,spatial_reference="EPSG:3857")}}}


def test_saved_report_images_and_hashes(tmp_path):
    r=specimen(); before=copy.deepcopy(r); view=views.build_view(r)
    maps.save_package(tmp_path,r,view,address="Synthetic test site",generated_at="test")
    assert r==before
    m=json.loads((tmp_path/'export-manifest.json').read_text())
    assert all(maps.sha((tmp_path/n).read_bytes())==h for n,h in m['files'].items())
    with Image.open(tmp_path/'evidence/zoning-map.png') as im: im.verify()
    with zipfile.ZipFile(next(tmp_path.glob('*.docx'))) as z:
        assert any(n.startswith('word/media/') for n in z.namelist())
    import fitz
    with fitz.open(next(tmp_path.glob('*.pdf'))) as doc:
        assert any(p.get_images() for p in doc)
        assert 'Official Zoning Evidence' in ''.join(p.get_text() for p in doc)
    with pytest.raises(FileExistsError):maps.save_package(tmp_path,r,view,address="Synthetic test site",generated_at="test")


@pytest.mark.parametrize('mutation', ['prose','geometry','crs','feature','split'])
def test_fail_closed(mutation):
    r=specimen()
    if mutation=='prose':r['document']['statements'][0]['text']='The parcel lies within WRONG.'
    if mutation=='geometry':r['retrieval']['zone_features'][0]['geometry']['coordinates'][0][0][0]=99
    if mutation=='crs':r['retrieval']['zone_features'][0]['source_crs']='EPSG:4326'
    if mutation=='feature':r['retrieval']['zone_features'][0].pop('feature_identifier')
    if mutation=='split':r['retrieval']['zone_features_examined']=False
    with pytest.raises(ValueError):maps.build(r,address='Synthetic test site')


def test_no_project_creation(tmp_path):
    r=specimen()
    with pytest.raises(ValueError):maps.save_package(tmp_path/'invented-project',r,views.build_view(r),address='Synthetic test site',generated_at='test')
    assert not (tmp_path/'invented-project').exists()


def test_report_prose_cannot_drift(tmp_path):
    r=specimen(); v=views.build_view(r);v['conclusion']='Different unsupported conclusion'
    with pytest.raises(ValueError):maps.save_package(tmp_path,r,v,address='Synthetic test site',generated_at='test')


def test_all_split_zone_geometries_retained():
    r=specimen(); z=r['retrieval']['zone_features'][0]
    other=copy.deepcopy(z);other['feature_identifier']='SECOND';other['zone_label']='R2';other['zone_code']='R2'
    for p in z['geometry']['coordinates'][0]:
        if p[0]==100:p[0]=15
    for p in other['geometry']['coordinates'][0]:
        if p[0]==0:p[0]=15
    for f in [z,other]:
        f['geometry_id']=spatial.geometry_hash(f['geometry']);f['spatial_relation']='INTERSECTS'
    r['retrieval']['zone_features'].append(other)
    r['retrieval']['visual_geometry']['zoning']=dict(z,spatial_reference='EPSG:3857')
    r['spatial_tokens']['zoning_area']['spatial_relation']='INTERSECTS'
    r['document']['statements'][0]['text']='The parcel intersects multiple zones: R (x8) and R2.'
    asset=maps.build(r,address='Synthetic test site')
    assert len(asset['zones'])==2
    assert 'R2' in asset['svg']


def test_polygon_hole_is_retained():
    r=specimen();z=r['retrieval']['zone_features'][0]
    z['geometry']['coordinates'].append([[50,50],[60,50],[60,60],[50,60],[50,50]])
    z['geometry_id']=spatial.geometry_hash(z['geometry'])
    r['retrieval']['visual_geometry']['zoning']=dict(z,spatial_reference='EPSG:3857')
    asset=maps.build(r,address='Synthetic test site')
    assert len(asset['zones'][0]['geometry']['coordinates'])==2
    assert 'fill-rule="evenodd"' in asset['svg']
