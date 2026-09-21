"""Real local browser proof; --public-live checks only public production copy.

No production identity is created. Local mutations use isolated evaluation cases.
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--public-live', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    proof = dict(environment='PUBLIC_LIVE' if args.public_live else 'LOCAL_ISOLATED_RUNTIME', errors=[])
    server = None
    temporary = None
    if args.public_live:
        base = 'https://archiosk.com'
    else:
        from app import create_app
        from models import db, User, ROLE_ADMIN
        from werkzeug.security import generate_password_hash
        from werkzeug.serving import make_server
        temporary = tempfile.TemporaryDirectory(prefix='go-workspace-ui-')
        app = create_app('testing')
        app.instance_path = temporary.name
        app.config.update(SECRET_KEY='local-browser-only', WTF_CSRF_ENABLED=True,
                          REGISTRY_STORE_PATH=str(Path(temporary.name) / 'registry'))
        with app.app_context():
            db.create_all()
            user = User(username='workspace-ui-test', role=ROLE_ADMIN)
            user.password_hash = generate_password_hash('Local-UI-Only-2026!')
            db.session.add(user)
            db.session.commit()
        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:' + str(server.server_port)
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            page.on('pageerror', lambda error: proof['errors'].append(str(error)))
            for width in (1440, 390, 320):
                page.set_viewport_size(dict(width=width, height=1000))
                page.goto(base + '/explore')
                assert page.get_by_role('heading', name='What Archiosk does').is_visible()
                assert page.locator('.landing-doc-section').count() == 7
                assert 'Project-document investigation' not in page.inner_text('body')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                for label, suffix in [('Request Trial Access', '/start-trial'), ('Sign In', '/login')]:
                    link = page.get_by_role('link', name=label, exact=True)
                    assert link.get_attribute('href').endswith(suffix)
                    link.click()
                    assert urlparse(page.url).path == suffix
                    page.go_back()
                page.screenshot(path=str(output / ('explore-' + str(width) + '.png')), full_page=True)
            proof['copy_desktop_mobile_buttons'] = True
            if args.public_live:
                response = page.goto(base + '/admin/survey-evaluation')
                assert response.ok and '/login' in page.url
                proof['workspace_authentication_boundary'] = True
            else:
                page.set_viewport_size(dict(width=1440, height=1000))
                page.goto(base + '/login')
                page.fill('#username', 'workspace-ui-test')
                page.fill('#password', 'Local-UI-Only-2026!')
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.wait_for_load_state()
                csrf = page.locator('meta[name="csrf-token"]').get_attribute('content')
                assert page.request.post(base + '/developer-mode/toggle', form={'csrf_token': csrf}, headers={'Referer': base + '/'}).ok
                page.goto(base + '/admin/survey-evaluation')
                page.locator('#review-technical > summary').click()
                page.get_by_role('button', name='Observe my real requests', exact=True).click()
                page.locator('#review-examples > summary').click()
                page.select_option('#case', 'matching:fit')
                page.get_by_role('button', name='Run isolated evaluation', exact=True).click()
                page.wait_for_url(lambda url: '/attention?analysis=' in url, wait_until='domcontentloaded')
                entry = page.url
                run_id = urlparse(entry).path.split('/')[-2]
                from services import survey_evaluation as evaluation
                from services.case_workspace import CaseWorkspaceStore
                from services.runtime_observation import read
                location = evaluation.location(app, run_id)
                store = CaseWorkspaceStore(location / 'registry')
                project_id = evaluation._read(location)['project_id']
                before = store.get(project_id)
                original_evidence = json.dumps(before.evidence_items, sort_keys=True)
                original_sources = json.dumps(before.sources, sort_keys=True)
                page.goto(base + '/admin/survey-evaluation')
                for width in (1440, 390):
                    page.set_viewport_size(dict(width=width, height=1000))
                    assert page.get_by_role('heading', name='GO Review Workspace', exact=True).is_visible()
                    assert page.locator('#review-entry input[type=radio]').count() == 6
                    assert not page.get_by_role('heading', name='Same muscle across domains').is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(output / ('workspace-' + str(width) + '.png')), full_page=True)
                page.check('[name=review_task][value=capital]')
                page.select_option('#review-target', '/admin/survey-evaluation/' + run_id + '/attention')
                page.fill('#review-objective', 'Review investor capital sector geography equity debt opportunity evidence')
                page.evaluate("""() => document.addEventListener('submit', e => {
                  if (e.target.querySelector('[name=plan_id]')) sessionStorage.setItem('shown-plan', document.querySelector('#go-work-plans').innerText);
                }, true)""")
                with page.expect_navigation():
                    page.get_by_role('button', name='Start review', exact=True).click()
                seen = page.evaluate("sessionStorage.getItem('shown-plan')")
                assert all(label in seen for label in ('Scope:', 'Stop conditions:', 'Evidence:', 'Expected output:'))
                assert 'task=capital' in page.url
                assert page.get_by_text('Evidence scope prepared.', exact=False).is_visible()
                assert page.locator('#attention-report pre:visible').count() == 0
                page.get_by_role('navigation', name='Review tasks').get_by_role('link', name='Evaluate capital alignment').click()
                assert page.locator('#requirement-matching').is_visible()
                form = page.locator('#requirement-matching form').first
                assert form.is_visible()
                form.locator('[name=context_key]').select_option('investment')
                form.locator('[name=require_currentness]').select_option('no')
                required = form.locator('[name=criterion_0_required] option').nth(1).get_attribute('value')
                form.locator('[name=criterion_0_required]').select_option(required)
                form.locator('[name=reason]').fill('Expose missing candidate evidence; do not invent a mandate.')
                with page.expect_navigation():
                    form.get_by_role('button', name='Run requirement matching', exact=True).click()
                assert page.locator('#attention-report').is_visible()
                assert 'UNRESOLVED' in page.locator('#attention-report').inner_text()
                state = store.get(project_id)
                executions = [run for run in state.analyses if (run.get('governed_result') or {}).get('kind') == 'requirement_matching']
                trace = read(app, executions[-1]['runtime_trace_id'])
                assert any(e['owner'].endswith('.run_requirement_matching') and e['phase'] == 'INVOKED' for e in trace['events'])
                assert json.dumps(state.evidence_items, sort_keys=True) == original_evidence
                assert json.dumps(state.sources, sort_keys=True) == original_sources
                committed = store._path_for(project_id).read_bytes()
                page.get_by_role('link', name='Reload', exact=True).click()
                assert store._path_for(project_id).read_bytes() == committed
                page.set_viewport_size(dict(width=1440, height=1000))
                page.screenshot(path=str(output / 'result.png'), full_page=True)
                proof.update(plan_displayed_before_execution=True, task_entry_invoked_existing_attention=True,
                             matching_invoked=True, missing_evidence_unresolved=True, reload_read_only=True,
                             sources_evidence_unchanged=True, trace_id=trace['id'])
            assert not proof['errors']
            browser.close()
        (output / 'proof.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    finally:
        if server:
            server.shutdown()
        if temporary:
            temporary.cleanup()


if __name__ == '__main__':
    main()
