import copy
import json
import uuid
from unittest.mock import patch

import pytest
from services.case_workspace import CaseWorkspaceStore
from services import planning_studies as studies
from services import planning_result_view as views
from tests.test_planning_map_export import specimen


def test_immutable_project_snapshot_and_reports(tmp_path):
    store=CaseWorkspaceStore(tmp_path);ws=store.get_or_create('project-a')
    result=specimen(); before=copy.deepcopy(result);key=uuid.uuid4().hex
    row=studies.save(store,ws,result,actor='planner',study_id=key,formats=['pdf','docx'])
    with patch('services.planning_live.run_live',side_effect=AssertionError('No retrieval on reopen')):
        reloaded=CaseWorkspaceStore(tmp_path).get('project-a')
        assert studies.reopen(store,reloaded,key)==before
        for name in row['artifacts']:assert studies.artifact(store,reloaded,key,name)
    assert result==before
    assert studies.save(store,reloaded,result,actor='planner',study_id=key)==row
    assert len(reloaded.planning_studies)==1
    changed=copy.deepcopy(result);changed['document']['result_status']='different'
    with pytest.raises(ValueError):studies.save(store,reloaded,changed,actor='planner',study_id=key)
    other=store.get_or_create('project-b')
    with pytest.raises(ValueError):studies.reopen(store,other,key)
    raw=store.binaries_path/'project-a'/key/'report.pdf'
    raw.write_bytes(b'tampered')
    with pytest.raises(ValueError):studies.artifact(store,reloaded,key,'report.pdf')


def test_working_buffer_is_scoped_and_expires(tmp_path):
    cache=studies.WorkingResults(tmp_path);key=cache.put('p','alice',{'a':1})
    assert cache.get(key,'p','alice')=={'a':1}
    for p,a in [('q','alice'),('p','bob')]:
        with pytest.raises(ValueError):cache.get(key,p,a)
    with patch('services.planning_studies.time.time',return_value=json.loads(cache._path(key).read_bytes())['expires_at']):
        with pytest.raises(ValueError):cache.get(key,'p','alice')


def test_cross_project_source_and_path_rejected(tmp_path):
    store=CaseWorkspaceStore(tmp_path);ws=store.get_or_create('p')
    with pytest.raises(ValueError):studies.save(store,ws,specimen(),actor='a',study_id=uuid.uuid4().hex,source_ids=['foreign'])
    with pytest.raises(ValueError):studies._directory(store,'../escape',uuid.uuid4().hex)


def test_explicit_save_and_reopen_routes(tmp_path):
    from flask import Flask
    from routes import planning_zoning as routes
    app=Flask(__name__,template_folder=str(__import__('pathlib').Path('templates').resolve()))
    app.secret_key='test-only'
    app.config['REGISTRY_STORE_PATH']=str(tmp_path)
    app.register_blueprint(routes.planning_bp)
    store=CaseWorkspaceStore(tmp_path);ws=store.get_or_create('p')
    with app.test_request_context('/'):
        from flask import session
        session['username']='alice'
        key=routes._working_studies().put('p','alice',specimen())
        assert not store.get('p').planning_studies
    with app.test_request_context('/',method='POST',data={'study_token':key,'formats':['pdf','docx']}):
        from flask import session
        session['username']='alice'
        with patch.object(routes,'_study_workspace',return_value=(None,store,ws)), patch('routes.workspace._require_export_allowed',return_value=None):
            response=routes.save_study.__wrapped__('p')
            assert response.status_code==302
    with app.test_request_context('/'):
        with patch.object(routes,'_study_workspace',return_value=(None,store,store.get('p'))), patch.object(routes,'render_template',side_effect=lambda name,**kw:kw), patch('services.planning_live.run_live',side_effect=AssertionError('retrieval')):
            context=routes.open_study.__wrapped__('p',key)
            assert context['saved_study']['id']==key and context['exportable'] is False
    with app.test_request_context('/',method='POST',data={'study_token':key}):
        from flask import session
        session['username']='bob'
        with patch.object(routes,'_study_workspace',return_value=(None,store,store.get('p'))):
            from werkzeug.exceptions import Conflict
            with pytest.raises(Conflict):routes.save_study.__wrapped__('p')


def test_old_workspace_loads_without_migration(tmp_path):
    store=CaseWorkspaceStore(tmp_path);store.get_or_create('p')
    path=tmp_path/'p.workspace.json'; data=json.loads(path.read_text());data.pop('planning_studies')
    path.write_text(json.dumps(data))
    assert store.get('p').planning_studies==[]


def test_saved_html_uses_only_saved_links(tmp_path):
    from flask import Flask
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from routes import planning_zoning as routes
    from pathlib import Path
    app=Flask(__name__);app.secret_key='test-only';app.register_blueprint(routes.planning_bp)
    app.jinja_loader=ChoiceLoader([DictLoader({'base.html':'{% block content %}{% endblock %}'}),FileSystemLoader(str(Path('templates').resolve()))])
    app.jinja_env.globals['csrf_token']=lambda:'test-only'
    store=CaseWorkspaceStore(tmp_path);ws=store.get_or_create('p');key=uuid.uuid4().hex
    studies.save(store,ws,specimen(),actor='a',study_id=key,formats=['pdf'])
    with app.test_request_context('/'):
        with patch.object(routes,'_study_workspace',return_value=(None,store,ws)),patch('services.planning_live.run_live',side_effect=AssertionError('no retrieval')):
            html=routes.open_study.__wrapped__('p',key)
            assert 'Download saved PDF' in html
            assert 'Official Zoning Evidence' in html and 'zoning-map.png' in html
            assert '/planning-zoning/export' not in html
            assert 'Nothing on this page is stored' not in html
            assert 'No municipal geometry was carried' not in html
