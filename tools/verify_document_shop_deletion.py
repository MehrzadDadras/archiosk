"""Real browser deletion proof in isolated storage; --live checks Castille read-only.

Live mode requires an existing human-issued ARCHIOSK_VERIFICATION_URL. This tool
never issues production credentials or deletes production data.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    temporary = server = None
    pid = '9c00eeec-4e65-4bde-bcea-de8b09c8beb1'
    proof = dict(environment='LIVE' if args.live else 'LOCAL_ISOLATED_RUNTIME', responses=[], errors=[])
    if args.live:
        access = os.environ.pop('ARCHIOSK_VERIFICATION_URL', '')
        parsed = urlparse(access)
        if parsed.scheme != 'https' or parsed.hostname != 'archiosk.com' or not parsed.path.startswith('/verification-access/'):
            raise SystemExit('An existing human-issued verification URL is required.')
        base = 'https://archiosk.com'
    else:
        from app import create_app
        from models import db, User, ROLE_ADMIN
        from werkzeug.security import generate_password_hash
        from werkzeug.serving import make_server
        from services.bhive_parser import ParsedDocument
        from services.case_workspace import CaseWorkspaceStore, CONTAINER_STATE_BLACK_BOX
        from services.requirements_registry import RequirementsRegistry
        temporary = tempfile.TemporaryDirectory(prefix='archiosk-deletion-')
        app = create_app('testing')
        captured = []
        @app.after_request
        def capture_execution(response):
            from flask import g
            record = getattr(g, 'survey_observation', None)
            if record:
                captured.append({k: v for k, v in record.items() if k != 'started'})
            return response
        app.instance_path = temporary.name
        app.config.update(SECRET_KEY='local-deletion-test-only', WTF_CSRF_ENABLED=True,
                          REGISTRY_STORE_PATH=str(Path(temporary.name) / 'registry'))
        with app.app_context():
            db.create_all()
            user = User(username='local-delete-test', role=ROLE_ADMIN)
            user.password_hash = generate_password_hash('Local-Delete-Only-2026!')
            db.session.add(user)
            db.session.commit()
        pid = str(uuid.uuid4())
        root = app.config['REGISTRY_STORE_PATH']
        registry = RequirementsRegistry(root)
        registry.save(ParsedDocument(project_id=pid, filename='Failed empty Castille browser case',
                                    ingested_at='2026-09-15T00:00:00Z'))
        store = CaseWorkspaceStore(root)
        workspace = store.get_or_create(pid)
        workspace.owner = 'local-delete-test'
        workspace.container_state = CONTAINER_STATE_BLACK_BOX
        store.save(workspace)
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:' + str(server.server_port)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            page = browser.new_page()
            page.on('pageerror', lambda e: proof['errors'].append(str(e)))
            page.on('response', lambda r: proof['responses'].append(dict(path=urlparse(r.url).path,
                method=r.request.method, status=r.status, trace=r.headers.get('x-archiosk-observation')))
                if urlparse(r.url).path.startswith('/document-shop') else None)
            page.goto(base + '/login')
            if args.live:
                page.goto(access)
                access = ''
            else:
                page.fill('#username', 'local-delete-test')
                page.fill('#password', 'Local-Delete-Only-2026!')
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.wait_for_load_state('domcontentloaded')
                csrf = page.locator('meta[name="csrf-token"]').get_attribute('content')
                assert page.request.post(base + '/developer-mode/toggle', form={'csrf_token': csrf},
                                         headers={'Referer': base + '/'}).ok
                page.goto(base + '/admin/survey-evaluation')
                page.get_by_role('button', name='Observe my real requests', exact=True).click()
                page.goto(base + '/document-shop/jobs')
                assert 'Could not complete' in page.inner_text('main')
                page.locator('[data-ui-ref="document-shop.jobs.delete"]').click()
                page.locator('[data-ui-ref="document-shop.job-delete.confirm"]').click()
                page.wait_for_url('**/document-shop/jobs')
                assert pid not in page.content()
                assert store.get(pid).document_desk_state == 'trash'
            for route in ('/document-shop/jobs', '/projects', '/projects/choose',
                          '/search?q=Castille', '/removed-projects'):
                response = page.goto(base + route)
                assert response.status == 200 and '/login' not in page.url, route
                assert pid not in page.content(), route
            page.goto(base + '/document-shop/jobs')
            page.get_by_role('link', name='Reload', exact=True).click()
            assert pid not in page.content()
            page.screenshot(path=str(output / 'after-reload.png'), full_page=True)
            response = page.goto(base + '/document-shop/jobs/' + pid)
            assert response.status == 404
            proof.update(project_id=pid, reload_absent=True, direct_url_status=response.status)
            if not args.live:
                from services.runtime_observation import read
                records = captured
                (output / 'runtime-traces.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
                owner = 'services.case_workspace.CaseWorkspaceStore.move_document_shop_case'
                assert any(e['owner'] == owner and e['phase'] == 'RETURNED' for r in records if r for e in r['events'])
                proof['real_owner_invoked'] = owner
            assert not proof['errors']
            (output / 'proof.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
            browser.close()
    finally:
        if server:
            server.shutdown()
        if temporary:
            temporary.cleanup()
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
