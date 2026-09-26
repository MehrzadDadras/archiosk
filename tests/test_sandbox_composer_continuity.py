"""The shared Composer remains reachable throughout a Sandbox conversation."""
import base64
import threading
from unittest.mock import patch

from services import llm_gateway
from services import sandbox as sb
from tests.test_liquid_sandbox_object_field_01 import _Field
from tests.test_sandbox_slice1_01 import MODEL_REPLY, _png_data_url


class ComposerContinuity(_Field):
    def test_repeated_interactions_leave_the_real_input_typable_and_sendable(self):
        self.continue_conversation(1280, 800)

    def test_phone_composer_continues_after_repeated_interactions(self):
        self.continue_conversation(390, 844)

    def continue_conversation(self, width, height):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw, patch.object(llm_gateway, 'call_llm_json', return_value=MODEL_REPLY), \
                patch('routes.portal._project_less_external_ai_allowed', return_value=True):
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': width, 'height': height})
            from werkzeug.serving import make_server
            server = make_server('127.0.0.1', 0, self.app, threaded=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            origin = 'http://127.0.0.1:' + str(server.server_port)
            cookie = self.boss.get_cookie(self.app.config['SESSION_COOKIE_NAME'])
            page.context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
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

