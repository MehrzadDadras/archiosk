"""Focused browser contract for the New Project acronym slots."""
from __future__ import annotations

import unittest

from werkzeug.security import generate_password_hash

try:
    from playwright.sync_api import sync_playwright
    _BROWSER_AVAILABLE = True
except ImportError:
    _BROWSER_AVAILABLE = False


def _rendered_page() -> str:
    import app as app_module
    from models import User, db

    flask_app = app_module.create_app("testing")
    with flask_app.app_context():
        db.session.add(User(username="acronym_slots",
                            password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    client = flask_app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "acronym_slots"
        session["role"] = "admin"
    return client.get("/upload").get_data(as_text=True)


class AcronymSlotMarkupTests(unittest.TestCase):
    def test_four_slots_map_to_one_submitted_value(self):
        body = _rendered_page()
        self.assertEqual(body.count("data-project-code-slot="), 4)
        self.assertEqual(body.count('name="project_code"'), 1)
        self.assertNotIn("3&ndash;4 letters", body)
        self.assertNotIn("ABCD-T014", body)


@unittest.skipUnless(_BROWSER_AVAILABLE, "Playwright is not installed")
class AcronymSlotBrowserTests(unittest.TestCase):
    def test_typing_backspace_and_paste(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(_rendered_page())
            slots = page.locator("[data-project-code-slot]")

            slots.nth(0).fill("p")
            slots.nth(1).fill("n")
            slots.nth(2).fill("s")
            self.assertEqual(page.locator("#upload-project-code").input_value(), "PNS")
            self.assertTrue(slots.nth(0).evaluate("el => el.checkValidity()"))

            slots.nth(3).focus()
            slots.nth(3).press("Backspace")
            self.assertEqual(page.locator("#upload-project-code").input_value(), "PN")
            self.assertFalse(slots.nth(0).evaluate("el => el.checkValidity()"))

            page.eval_on_selector("[data-project-code-slot]", """el => {
                const data = new DataTransfer(); data.setData('text', 'ABCD');
                el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true}));
            }""")
            self.assertEqual(page.locator("#upload-project-code").input_value(), "ABCD")
            self.assertTrue(slots.nth(0).evaluate("el => el.checkValidity()"))

            page.eval_on_selector("[data-project-code-slot]", """el => {
                const data = new DataTransfer(); data.setData('text', 'NORTH');
                el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true}));
            }""")
            self.assertFalse(slots.nth(0).evaluate("el => el.checkValidity()"))
            browser.close()
