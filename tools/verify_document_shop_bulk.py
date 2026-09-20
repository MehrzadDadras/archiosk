"""Browser proof for the document desk. Live access must be human-issued."""
import argparse
import io
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
    parser.add_argument('--commands', action='store_true', help='Also exercise Ask GO typed working-view commands.')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    captured, errors, identifiers = [], [], []
    temp, server = None, None
    if args.live:
        access = os.environ.pop('ARCHIOSK_VERIFICATION_URL', '')
        parsed = urlparse(access)
        if parsed.scheme != 'https' or parsed.hostname != 'archiosk.com' or not parsed.path.startswith('/verification-access/'):
            raise SystemExit('Existing human-issued verification URL required.')
        base = 'https://archiosk.com'
    else:
        from app import create_app
        from models import db, User, ROLE_ADMIN
        from werkzeug.security import generate_password_hash
        from werkzeug.serving import make_server
        temp = tempfile.TemporaryDirectory(prefix='archiosk-bulk-proof-')
        app = create_app('testing')
        app.instance_path = temp.name
        app.config.update(WTF_CSRF_ENABLED=True, SECRET_KEY='local-bulk-proof-only',
                          REGISTRY_STORE_PATH=str(Path(temp.name) / 'registry'))
        @app.after_request
        def capture(response):
            from flask import g
            record = getattr(g, 'survey_observation', None)
            if record:
                captured.append({k:v for k,v in record.items() if k != 'started'})
            return response
        with app.app_context():
            db.create_all()
            user = User(username='bulk-proof', role=ROLE_ADMIN)
            user.password_hash = generate_password_hash('Local-Bulk-Proof-Only!')
            db.session.add(user)
            db.session.commit()
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:' + str(server.server_port)
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image, ImageDraw
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            page = browser.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            if args.live:
                page.goto(access)
                access = ''
            else:
                page.goto(base + '/login')
                page.fill('#username', 'bulk-proof')
                page.fill('#password', 'Local-Bulk-Proof-Only!')
                page.get_by_role('button', name='Sign in', exact=True).click()
            assert '/login' not in page.url
            csrf = page.locator('meta[name="csrf-token"]').get_attribute('content')
            assert page.request.post(base + '/developer-mode/toggle', form={'csrf_token':csrf}, headers={'Referer':base + '/'}).ok
            page.goto(base + '/admin/survey-evaluation')
            observe = page.get_by_role('button', name='Observe my real requests', exact=True)
            if observe.count():
                observe.click()
            for index in range(2):
                picture = Image.new('RGB', (640, 240), 'white')
                ImageDraw.Draw(picture).text((30, 60), 'EVALUATION_INPUT - disposable desk verification ' + str(index), fill='black')
                raw = io.BytesIO()
                picture.save(raw, format='PNG')
                page.goto(base + '/document-shop')
                page.locator('input[name="name"]').fill('EVALUATION_INPUT desk ' + uuid.uuid4().hex[:10])
                page.locator('input[type="file"]').set_input_files(dict(name='EVALUATION_INPUT.png', mimeType='image/png', buffer=raw.getvalue()))
                page.locator('form.upload-form button[type="submit"]').click()
                page.wait_for_url('**/document-shop/jobs/*')
                identifiers.append(urlparse(page.url).path.rsplit('/', 1)[-1])
            if args.commands:
                from contextlib import nullcontext
                if not args.live:
                    from unittest.mock import patch
                    from types import SimpleNamespace
                    app.config['ANTHROPIC_API_KEY'] = 'controlled-local-intent-response'
                    intent_context = patch('services.llm_gateway.call_llm_json', return_value=SimpleNamespace(
                        ran=True, parsed={'answer':'Requesting a half-turn working view.',
                            'command':dict(action_id='ROTATE_VIEW', parameters={'degrees':180}, user_requested=True)}))
                else:
                    intent_context = nullcontext()
                page.goto(base + '/document-shop/jobs/' + identifiers[0])
                with intent_context:
                    page.locator('textarea[name="question"]').fill('Please turn this document view upside down by 180 degrees.')
                    page.get_by_role('button', name='Ask', exact=True).click()
                    page.wait_for_url('**#conversation')
                    assert 'ROTATE_180' in page.inner_text('main')
                if not args.live:
                    app.config.pop('ANTHROPIC_API_KEY', None)
                views_before = page.locator('img[src*="/working-view/"]').count()
                assert views_before == 1
                page.reload()
                assert page.locator('img[src*="/working-view/"]').count() == views_before
                page.screenshot(path=str(output / 'typed-command-view.png'), full_page=True)
            page.goto(base + '/document-shop/jobs')
            def select_all_owned_cases():
                page.get_by_role('button', name='Clear selection', exact=True).click()
                for pid in identifiers:
                    page.locator('input[name="project_id"][value="' + pid + '"]').check()
            page.locator('input[name="project_id"][value="' + identifiers[0] + '"]').check()
            assert page.locator('#document-selected-count').inner_text() == '1 selected'
            page.get_by_role('button', name='Select all', exact=True).click()
            assert page.locator('input[name="project_id"]:checked').count() >= 2
            select_all_owned_cases()
            page.get_by_role('link', name='Reload', exact=True).click()
            assert page.locator('#document-selected-count').inner_text() == '2 selected'
            page.get_by_role('button', name='Compare', exact=True).click()
            assert 'Analytical, non-canonical' in page.inner_text('main')
            for pid in identifiers:
                assert pid in page.inner_text('main')
            page.get_by_role('link', name='Back to My documents', exact=True).click()
            assert page.locator('#document-selected-count').inner_text() == '2 selected'
            page.get_by_role('button', name='Archive', exact=True).click()
            for pid in identifiers:
                assert pid not in page.content()
            page.get_by_role('link', name='Reload', exact=True).click()
            for pid in identifiers:
                assert pid not in page.content()
            page.goto(base + '/document-shop/jobs?view=archive')
            select_all_owned_cases()
            page.get_by_role('button', name='Restore', exact=True).click()
            select_all_owned_cases()
            page.get_by_role('button', name='Re-analyze', exact=True).click()
            assert '2 documents queued for re-analysis' in page.inner_text('main')
            select_all_owned_cases()
            page.locator('#document-bulk-actions button[value="delete"]').click()
            assert '7 days' in page.inner_text('main')
            page.get_by_role('button', name='Move to Recently Deleted', exact=True).click()
            page.get_by_role('link', name='Reload', exact=True).click()
            for pid in identifiers:
                assert pid not in page.content()
                assert page.request.get(base + '/document-shop/jobs/' + pid).status == 404
            page.goto(base + '/document-shop/jobs?view=trash')
            select_all_owned_cases()
            page.get_by_role('button', name='Restore', exact=True).click()
            select_all_owned_cases()
            page.locator('#document-bulk-actions button[value="delete"]').click()
            page.get_by_role('button', name='Move to Recently Deleted', exact=True).click()
            page.screenshot(path=str(output / 'clean-desk.png'), full_page=True)
            assert not errors, errors
            proof = dict(environment='LIVE' if args.live else 'LOCAL_ISOLATED_RUNTIME', project_ids=identifiers,
                archive_restore=True, trash_restore=True, reload_preserves_selection=True,
                compare_invoked=True, reanalysis_queued=True, old_urls_404=True, errors=errors)
            if args.commands:
                proof.update(typed_command_invoked=True, reload_does_not_repeat_command=True,
                    intent_provider='LIVE_PROVIDER' if args.live else 'CONTROLLED_RESPONSE_NOT_LIVE_NL_PROOF')
                if not args.live:
                    owners = {e['owner'] for record in captured for e in record['events'] if e['phase'] == 'INVOKED'}
                    assert 'services.conversation_interpreter.execute_document_action' in owners
                    assert 'services.document_examination.create_working_view' in owners
            (output / 'proof.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
            if captured:
                (output / 'runtime-traces.json').write_text(json.dumps(captured, indent=2), encoding='utf-8')
            browser.close()
    finally:
        if server:
            server.shutdown()
        if temp:
            temp.cleanup()
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
