"""Exercise real browser forms locally or with a human-issued live verification URL.

Default: isolated testing app, in-memory test identity, no production connection.
--live: ARCHIOSK_VERIFICATION_URL must already exist; never issues credentials.
Writes no credential/session material to its proof output. All mutations use
the EVALUATION_INPUT UI; real project inspection is read-only.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    output=Path(args.output); output.mkdir(parents=True, exist_ok=True)
    server=None; temporary=None
    if args.live:
        access=os.environ.pop('ARCHIOSK_VERIFICATION_URL','')
        parsed=urlparse(access)
        if parsed.scheme!='https' or parsed.hostname not in ('archiosk.com','www.archiosk.com') or not parsed.path.startswith('/verification-access/'):
            raise SystemExit('A human-issued verification URL is required.')
        base=parsed.scheme+'://'+parsed.netloc
    else:
        from app import create_app
        from models import db, User, ROLE_ADMIN
        from werkzeug.security import generate_password_hash
        from werkzeug.serving import make_server
        temporary=tempfile.TemporaryDirectory(prefix='archiosk-source-review-')
        app=create_app('testing')
        app.instance_path=temporary.name
        app.config.update(SECRET_KEY='local-browser-test-only', WTF_CSRF_ENABLED=True,
            REGISTRY_STORE_PATH=str(Path(temporary.name)/'registry'))
        with app.app_context():
            db.create_all()
            user=User(username='local-review-test', role=ROLE_ADMIN)
            user.password_hash=generate_password_hash('Local-Test-Only-2026!')
            db.session.add(user); db.session.commit()
        server=make_server('127.0.0.1',0,app,threaded=True)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
    from playwright.sync_api import sync_playwright
    proof=dict(environment='LIVE' if args.live else 'LOCAL_ISOLATED_RUNTIME', traces=[], browser_errors=[])
    try:
        with sync_playwright() as driver:
            browser=driver.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.set_default_timeout(120000)
            page.on('pageerror',lambda error:proof['browser_errors'].append(str(error)))
            def capture(response):
                if response and response.headers.get('x-archiosk-observation'):
                    proof['traces'].append(dict(method=response.request.method,path=urlparse(response.url).path,
                        trace=response.headers['x-archiosk-observation'],status=response.status))
            page.on('response',capture)
            page.goto(base+'/login')
            if args.live:
                page.goto(access); access=''
            else:
                page.fill('#username','local-review-test'); page.fill('#password','Local-Test-Only-2026!')
                page.get_by_role('button',name='Sign in',exact=True).click()
                page.wait_for_load_state('domcontentloaded')
            csrf=page.locator('meta[name="csrf-token"]').get_attribute('content')
            assert page.request.post(base+'/developer-mode/toggle',form={'csrf_token':csrf},headers={'Referer':base+'/'}).ok
            page.goto(base+'/admin/survey-evaluation')
            page.get_by_role('button',name='Observe my real requests',exact=True).click()
            page.select_option('#case','source-review')
            page.get_by_role('button',name='Run isolated evaluation',exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            proof['evaluation_path']=urlparse(page.url).path
            page.get_by_role('link',name='Review source frame, anchored machine readings and unresolved stages').click()
            page.wait_for_load_state('domcontentloaded')
            proof['review_path']=urlparse(page.url).path
            page.get_by_role('button',name='Select four corners on original').click()
            image=page.locator('#review-original')
            box=image.bounding_box()
            for x,y in ((.05,.05),(.95,.08),(.9,.95),(.1,.9)):
                image.click(position={'x':box['width']*x,'y':box['height']*y})
            assert len(json.loads(page.input_value('#corners')))==4
            page.fill('#frame-reason','EVALUATION_INPUT: supplied document control quadrilateral; display aspect only.')
            page.get_by_role('button',name='Create qualified rectified view',exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            assert page.get_by_alt_text('Qualified rectified document preview').count()==1
            options=page.locator('#review-field option').evaluate_all('nodes => nodes.map(n => ({value:n.value,text:n.textContent}))')
            field=next(row['value'] for row in options if 'A-2O3' in row['text'])
            page.select_option('#review-field',field)
            page.fill('#after','Sheet: A-203'); page.fill('#text-reason','Controlled source title block visibly reads A-203.')
            page.get_by_role('button',name='Propose correction',exact=True).click()
            page.get_by_role('button',name='Accept reviewed correction',exact=True).click()
            page.get_by_role('button',name='Re-evaluate reviewed source',exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            assert 'Regulatory frontage / front lot line' in page.locator('.survey-evaluation').inner_text()
            before=page.locator('.survey-evaluation').inner_text()
            if not args.live:
                from services import survey_evaluation as evaluation
                from services.case_workspace import CaseWorkspaceStore
                run=proof['evaluation_path'].rsplit('/',1)[1]
                location=evaluation.location(app,run)
                store=CaseWorkspaceStore(str(location/'registry'))
                state_path=store._path_for(evaluation._read(location)['project_id'])
                persisted_before=state_path.read_bytes()
            page.screenshot(path=str(output/'source-review.png'),full_page=True)
            page.get_by_role('button',name='Reload view',exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            after=page.locator('.survey-evaluation').inner_text()
            assert before==after
            if not args.live:
                assert state_path.read_bytes()==persisted_before
                proof['reload_persisted_bytes_unchanged']=True
            page.get_by_role('button',name='Revert correction',exact=True).click()
            assert 'RE-EVALUATION REQUIRED' in page.locator('.survey-evaluation').inner_text()
            page.get_by_role('button',name='Re-evaluate reviewed source',exact=True).click()
            proof['reload_preserves_visible_state']=True
            proof['accept_explicit_reevaluate_revert']=True
            if args.live:
                page.goto(base+'/projects/9c00eeec-4e65-4bde-bcea-de8b09c8beb1/sources/c590314b-f7b7-491a-addc-e2217ec92da9/review')
                assert page.get_by_role('heading',name='Source review:',exact=False).count()==1
                page.screenshot(path=str(output/'castille-review.png'),full_page=True)
            assert not proof['browser_errors']
            if not args.live:
                from services.runtime_observation import read
                records=[read(app, item['trace']) for item in proof['traces']]
                (output/'runtime-traces.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
                owners={event['owner'] for record in records if record for event in record['events'] if event['phase']=='INVOKED'}
                for owner in ('services.image_intake.rectify_document_preview',
                    'services.document_examination.propose_text_correction',
                    'services.document_examination.review_text_correction',
                    'services.document_examination.reevaluate_source_review'):
                    assert owner in owners, owner
                proof['invoked_owners']=sorted(owners)
            (output/'proof.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
            browser.close()
    finally:
        if server: server.shutdown()
        if temporary: temporary.cleanup()
    print(json.dumps(proof,indent=2))


if __name__=='__main__': main()
