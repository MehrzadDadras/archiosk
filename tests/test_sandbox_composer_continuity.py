"""The shared Composer remains reachable throughout a Sandbox conversation."""
import base64
import threading
from unittest.mock import patch

from services import llm_gateway
from services import sandbox as sb
from tests.test_liquid_sandbox_object_field_01 import _Field
from tests.test_sandbox_slice1_01 import MODEL_REPLY, _png_data_url


class ComposerContinuity(_Field):
    def browser_page(self, pw, width, height):
        from werkzeug.serving import make_server
        server = make_server('127.0.0.1', 0, self.app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': height})
        origin = 'http://127.0.0.1:' + str(server.server_port)
        cookie = self.boss.get_cookie(self.app.config['SESSION_COOKIE_NAME'])
        page.context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
        return browser, page, origin

    def test_repeated_interactions_leave_the_real_input_typable_and_sendable(self):
        self.continue_conversation(1280, 800)

    def test_phone_composer_continues_after_repeated_interactions(self):
        self.continue_conversation(390, 844)

    def test_file_open_restores_saved_objects_in_a_fresh_session_and_supports_work(self):
        from playwright.sync_api import sync_playwright, expect
        note, image, _, _ = self.seeded()
        before = self.record()
        self.boss = self.client('cover_boss')  # Authenticated, with no Sandbox pointer.
        with sync_playwright() as pw, patch.object(llm_gateway, 'call_llm_json', return_value=MODEL_REPLY), \
                patch('routes.portal._project_less_external_ai_allowed', return_value=True):
            browser, page, origin = self.browser_page(pw, 1280, 900)
            page.context.clear_cookies()
            page.goto(origin + '/login')
            page.locator('#username').fill('cover_boss')
            page.locator('#password').fill(self.PW)
            with page.expect_navigation():
                page.locator('[data-ui-ref="auth.signin.submit"]').click()
            expect(page).to_have_url(origin + '/sandbox')
            expect(page.locator('[data-field-object="' + note['id'] + '"]')).to_be_in_viewport()
            self.assertEqual(self.record(), before)
            page.goto(origin + '/projects')
            page.locator('[data-family="file"] > summary').click()
            with page.expect_navigation():
                page.locator('[data-command="file.open_sandbox"] a').click()
            expect(page).to_have_url(origin + '/sandbox')
            card = page.locator('[data-field-object="' + note['id'] + '"]')
            expect(card).to_be_in_viewport()
            expect(page.locator('[data-field-object="' + image['id'] + '"] img')).to_have_js_property('naturalWidth', 24)
            self.assertEqual(self.record(), before)  # Opening/rendering has no store write.
            handle = card.locator('.sandbox-move').bounding_box()
            page.mouse.move(handle['x'] + 20, handle['y'] + 20)
            page.mouse.down()
            page.mouse.move(handle['x'] + 100, handle['y'] + 60, steps=8)
            page.mouse.up()
            expect(page.locator('.sandbox-move-status')).to_have_text('Position saved.')
            page.reload()
            expect(card).to_have_attribute('data-x', '104')
            expect(card).to_have_attribute('data-y', '64')
            card.locator('.sandbox-move').hover()  # Raise the exposed part of an overlapping card.
            card.locator('.sandbox-field-select').click()
            composer = page.locator('#dock-composer-input')
            composer.click()
            composer.press_sequentially('Continue after reopening and moving')
            with page.expect_navigation():
                composer.press('Enter')
            self.assertEqual(self.record()['turns'][-1]['selected'], [note['id']])
            expect(composer).to_be_enabled()
            page.locator('[data-family="file"] > summary').click()
            with page.expect_navigation():
                page.locator('[data-command="file.new_sandbox"] a').click()
            expect(page.locator('.sandbox-field-empty')).to_be_in_viewport()
            expect(page.locator('[data-field-object]')).to_have_count(0)
            with page.expect_navigation():
                page.get_by_role('link', name='Open your saved Sandbox').click()
            expect(card).to_have_attribute('data-x', '104')
            browser.close()

    def test_open_is_owner_scoped_and_keeps_the_customer_boundary(self):
        self.seeded()
        before = self.record()
        store = sb.SandboxStore(str(self.tmp), self.media)
        foreign = store.start('another_owner')
        foreign = store.add_turn('another_owner', foreign['id'], 'Private note', {})
        fresh = self.client('cover_boss')
        self.assertEqual(fresh.get('/sandbox?resume=1&owner=another_owner').status_code, 302)
        html = fresh.get('/sandbox').get_data(as_text=True)
        self.assertIn(before['objects'][0]['id'], html)
        self.assertNotIn(foreign['objects'][0]['id'], html)
        self.assertEqual(self.client('cover_cust').get('/sandbox?resume=1').status_code, 404)
        self.assertEqual(self.record(), before)

    def continue_conversation(self, width, height):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw, patch.object(llm_gateway, 'call_llm_json', return_value=MODEL_REPLY), \
                patch('routes.portal._project_less_external_ai_allowed', return_value=True):
            browser, page, origin = self.browser_page(pw, width, height)
            page.goto(origin + '/sandbox')
            composer = page.locator('#dock-composer-input')
            def send(text):
                self.assertTrue(composer.evaluate('''input => {
                    const r = input.getBoundingClientRect();
                    const p = input.closest('.conversation-dock-panel').getBoundingClientRect();
                    return r.top >= p.top && r.bottom <= Math.min(p.bottom, innerHeight);
                }'''), 'Composer must be reachable without programmatically scrolling a clipped panel')
                composer.click()
                composer.press_sequentially(text)
                expect(composer).to_have_value(text)
                with page.expect_navigation():
                    composer.press('Enter')
                expect(composer).to_be_enabled()
            for index in range(6):
                send('Continue discussing the design ' + str(index))
                self.assertEqual(len(self.record()['turns']), index + 1)
                expect(page.locator('#sandbox-latest')).to_contain_text('Your objective')
                box = page.locator('[name="object_id"][type="checkbox"]').first
                box.check()
                box.uncheck()
            page.locator('#dock-composer-image').set_input_files({
                'name': 'photo.png', 'mimeType': 'image/png',
                'buffer': base64.b64decode(_png_data_url().split(',')[1])})
            page.locator('#dock-capture-review-use').click()
            expect(page.locator('#dock-composer-image-data')).not_to_have_value('')
            page.locator('#dock-composer-image-clear').click()
            send('Continue after removing the image')
            page.locator('#dock-composer-image').set_input_files({
                'name': 'photo.png', 'mimeType': 'image/png',
                'buffer': base64.b64decode(_png_data_url().split(',')[1])})
            page.locator('#dock-capture-review-use').click()
            expect(page.locator('#dock-composer-image-data')).not_to_have_value('')
            send('Send the image with this message')
            self.assertEqual(len(self.objects('image')), 1)
            page.locator('[name="object_id"][type="checkbox"]').first.check()
            send('Continue using the selected object')
            self.assertEqual(len(self.record()['turns'][-1]['selected']), 1)
            page.reload()
            send('Continue after reloading')
            # Another tab changes the same owner store after this page was drawn.
            store = sb.SandboxStore(str(self.tmp), self.media)
            record = self.record()
            store.add_turn('cover_boss', record['id'], 'A concurrent turn', record['turns'][-1]['reply'],
                           expected=store.token('cover_boss'))
            count = len(self.record()['turns'])
            send('This stale request must be refused')
            self.assertEqual(len(self.record()['turns']), count)
            send('Continue after stale-state recovery')
            self.assertEqual(len(self.record()['turns']), count + 1)
            browser.close()
