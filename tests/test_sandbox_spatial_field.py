"""Spatial presentation shares object identity, selection and revision authority."""
import copy
from urllib.parse import urlsplit

from services import sandbox as sb
from tests.test_liquid_sandbox_object_field_01 import _Field


class SpatialField(_Field):
    def move(self, obj, x=140, y=180, token=None):
        store = sb.SandboxStore(str(self.tmp), self.media)
        return self.boss.post('/sandbox/move', json={
            'object_id': obj, 'x': x, 'y': y,
            'sandbox_base': token if token is not None else store.token('cover_boss')})

    def test_move_changes_only_position_and_revision(self):
        note, image, _, _ = self.seeded()
        before = self.record()
        governed = self.governed_state()
        media = self.boss.get('/sandbox/media/' + image['id']).data
        for obj in (note, image):
            response = self.move(obj['id'])
            self.assertEqual(response.status_code, 200)
            self.assertIn('sandbox_base', response.json)
        after = self.record()
        self.assertEqual(after.pop('revision'), before.pop('revision') + 2)
        for obj in after['objects'][:2]:
            self.assertEqual(obj.pop('position'), {'x': 140, 'y': 180})
        self.assertEqual(after, before)
        self.assertEqual(self.governed_state(), governed)
        self.assertEqual(self.boss.get('/sandbox/media/' + image['id']).data, media)
        selected, ignored = sb.resolve_selection(self.record(), [note['id'], image['id'], 'foreign'])
        self.assertEqual(ignored, 1)
        context = self.selection_block(sb.selection_prompt(selected))
        self.assertEqual([o['modality'] for o in context], ['text', 'image'])

    def test_stale_foreign_invalid_and_missing_tokens_do_not_write(self):
        note, _, _, _ = self.seeded()
        token = sb.SandboxStore(str(self.tmp)).token('cover_boss')
        self.assertEqual(self.move(note['id'], token=token).status_code, 200)
        before = self.record()
        self.assertEqual(self.move(note['id'], token=token).status_code, 409)
        self.assertEqual(self.move(note['id'], token='').status_code, 409)
        self.assertEqual(self.move('foreign').status_code, 400)
        for invalid in (-1, 10001, True, '2', None, float('nan'), float('inf')):
            self.assertEqual(self.move(note['id'], x=invalid).status_code, 400)
        self.assertEqual(self.record(), before)

    def test_move_requires_login_and_csrf(self):
        note, _, _, _ = self.seeded()
        before = self.record()
        with self.app.test_client() as anonymous:
            self.assertIn(anonymous.post('/sandbox/move', json={}).status_code, (302, 401))
        self.app.config['WTF_CSRF_ENABLED'] = True
        try:
            self.assertEqual(self.move(note['id']).status_code, 400)
        finally:
            self.app.config['WTF_CSRF_ENABLED'] = False
        self.assertEqual(self.record(), before)
        foreign = sb.SandboxStore(str(self.tmp), self.media).start('another_owner')
        foreign = sb.SandboxStore(str(self.tmp), self.media).add_turn('another_owner', foreign['id'], 'Private', {})
        self.assertEqual(self.move(foreign['objects'][0]['id']).status_code, 400)
        self.assertEqual(self.record(), before)

    def test_pointer_keyboard_reload_and_shared_selection_under_csp(self):
        from playwright.sync_api import sync_playwright, expect
        note, image, _, _ = self.seeded()
        before = copy.deepcopy(self.record()['objects'])
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 1000})
            def serve(route):
                request = route.request
                path = urlsplit(request.url).path
                response = self.boss.open(path, method=request.method, data=request.post_data,
                    content_type=request.headers.get('content-type'),
                    headers={'X-CSRFToken': request.headers.get('x-csrftoken', '')})
                route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)
            page.route('http://sandbox.test/**', serve)
            page.goto('http://sandbox.test/sandbox')
            card = page.locator('[data-field-object="' + note['id'] + '"]')
            expect(card).to_have_count(1)
            expect(page.locator('[data-field-object="' + image['id'] + '"] img')).to_have_js_property('naturalWidth', 24)
            card.locator('.sandbox-field-select').click()
            expect(page.locator('#sandbox-object-' + note['id'])).to_be_checked()
            page.locator('#sandbox-object-' + image['id']).check()
            expect(page.locator('[data-field-object="' + image['id'] + '"] .sandbox-field-select')).to_have_attribute('aria-pressed', 'true')
            expect(page.locator('[data-go-selection-count="sandbox-selection"]')).to_contain_text('2 objects selected')
            handle = card.locator('.sandbox-move')
            handle.scroll_into_view_if_needed()
            box = handle.bounding_box()
            page.mouse.move(box['x'] + 20, box['y'] + 20)
            page.mouse.down()
            page.mouse.move(box['x'] + 120, box['y'] + 80, steps=8)
            page.mouse.up()
            expect(page.locator('.sandbox-move-status')).to_have_text('Position saved.')
            self.assertEqual(self.record()['objects'][0]['position'], {'x': 124, 'y': 84})
            handle.press('ArrowRight')
            expect(card).to_have_attribute('data-x', '144')
            expect(page.locator('.sandbox-move-status')).to_have_text('Position saved.')
            page.reload()
            expect(card).to_have_attribute('data-x', '144')
            expect(card).to_have_attribute('data-y', '84')
            self.assertEqual(len(self.record()['objects']), len(before))
            for old, new in zip(before, self.record()['objects']):
                new.pop('position', None)
                self.assertEqual(old, new)
            expect(page.locator('#sandbox-latest')).to_contain_text('Your objective')
            expect(page.locator('#dock-composer-input')).to_be_enabled()
            page.set_viewport_size({'width': 390, 'height': 844})
            self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth + 1'))
            browser.close()
