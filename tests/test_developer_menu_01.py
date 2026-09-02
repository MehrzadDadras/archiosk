"""
CLAUDE-DEVELOPER-MENU-01 - Developer Mode is named in the Archiosk menu.

Product Owner, live: "there is no visible Developer Mode control."

They were right, and the interesting part is HOW they were right. The control
rendered, their session was authorized, and the route worked. It sat at the
bottom of the Admin submenu behind a separator - two closed disclosures deep,
where the only visible word was "Admin", which does not say Developer Mode is
inside.

So this is not a permissions fix and not a new capability. It moves where the
capability is NAMED. The gate, the route and the authorization are untouched,
and tests below assert that they are.

WHAT THIS FILE PROTECTS

The property that failed is discoverability: reachable in one visible step from
a menu that says what it contains. Markup assertions alone would not have caught
the original problem - the markup was fine. So the tests here are written
against the disclosure PATH, not just the presence of an element.
"""
from __future__ import annotations

import io
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

_MENU = (Path(__file__).resolve().parent.parent / "templates" / "_app_menu.html").read_text(
    encoding="utf-8")


class _MenuCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="menu_admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="menu_reader",
                                password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def _client(self, username, role, uid):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["username"] = username
            sess["role"] = role
        return client

    def _home(self, client):
        return client.get("/", follow_redirects=True).get_data(as_text=True)


class ItIsNamedWhereItCanBeSeen(_MenuCase):
    def test_the_archiosk_menu_names_developer_mode(self):
        body = self._home(self._client("menu_admin", "admin", 1))
        self.assertIn('data-ui-ref="menu.archiosk.developer"', body)
        # The word itself must appear as the submenu's own label - "Admin" did
        # not say Developer Mode was inside it, which is the whole defect.
        i = body.index('data-ui-ref="menu.archiosk.developer"')
        summary = body[i:body.index("</summary>", i)]
        self.assertIn("Developer Mode", summary)

    def test_it_is_a_sibling_of_admin_not_buried_inside_it(self):
        # One visible step from the Archiosk menu, not two.
        admin_at = _MENU.index('data-ui-ref="menu.archiosk.admin"')
        admin_closes = _MENU.index("</details>", admin_at)
        developer_at = _MENU.index('data-ui-ref="menu.archiosk.developer"')
        self.assertGreater(developer_at, admin_closes,
                           "Developer Mode is still nested inside the Admin submenu")

    def test_the_toggle_lives_in_the_new_submenu(self):
        body = self._home(self._client("menu_admin", "admin", 1))
        start = body.index('data-ui-ref="menu.archiosk.developer"')
        end = body.index("</details>", start)
        self.assertIn('data-ui-ref="menu.archiosk.developer.mode-toggle"', body[start:end])

    def test_the_label_says_what_happens_next(self):
        body = self._home(self._client("menu_admin", "admin", 1))
        self.assertIn("Enter Developer Mode", body)
        self.assertNotIn("Exit Developer Mode", body)

    def test_it_says_exit_once_developer_mode_is_on(self):
        client = self._client("menu_admin", "admin", 1)
        with client.session_transaction() as sess:
            sess["developer_mode"] = True
        body = self._home(client)
        self.assertIn("Exit Developer Mode", body)


class TheOldLocationIsGoneNotDuplicated(_MenuCase):
    """A governed toggle appearing twice is two things to keep in agreement."""

    def test_the_toggle_appears_exactly_once(self):
        body = self._home(self._client("menu_admin", "admin", 1))
        self.assertEqual(body.count('data-ui-ref="menu.archiosk.developer.mode-toggle"'), 1)

    def test_no_developer_control_remains_under_admin(self):
        for stale in ["menu.archiosk.admin.developer-mode-toggle",
                      "menu.archiosk.admin.ui-reveal-toggle",
                      "menu.archiosk.admin.developer-tools"]:
            with self.subTest(ref=stale):
                self.assertNotIn(stale, _MENU)

    def test_the_admin_submenu_still_holds_its_own_items(self):
        # Moving Developer Mode out must not have taken anything with it.
        body = self._home(self._client("menu_admin", "admin", 1))
        for kept in ["menu.archiosk.admin.security", "menu.archiosk.admin.operations",
                     "menu.archiosk.admin.diagnostics",
                     "menu.archiosk.admin.project-data-management"]:
            with self.subTest(ref=kept):
                self.assertIn(kept, body)


class AuthorizationIsUnchanged(_MenuCase):
    """This moved a name. It must not have moved a boundary."""

    def test_a_non_admin_sees_no_developer_submenu_at_all(self):
        body = self._home(self._client("menu_reader", "read_only", 2))
        self.assertNotIn('data-ui-ref="menu.archiosk.developer"', body)
        self.assertNotIn('data-ui-ref="menu.archiosk.developer.mode-toggle"', body)
        self.assertNotIn("Enter Developer Mode", body)

    def test_the_route_still_rejects_a_non_admin(self):
        # The real boundary was never the menu - a hidden control is not a
        # security mechanism, and surfacing it must not become one either.
        resp = self._client("menu_reader", "read_only", 2).post("/developer-mode/toggle")
        self.assertEqual(resp.status_code, 403)

    def test_the_submenu_is_inside_the_is_admin_gate(self):
        gate = _MENU.index("{% if is_admin %}")
        developer = _MENU.index('data-ui-ref="menu.archiosk.developer"')
        closing = _MENU.index("{% endif %}", developer)
        self.assertLess(gate, developer)
        self.assertLess(developer, closing)

    def test_the_toggle_is_still_a_form_post_not_a_link(self):
        # A GET link would put a state change in browser history and make it
        # reachable by typing a URL.
        start = _MENU.index('data-ui-ref="menu.archiosk.developer"')
        block = _MENU[start:_MENU.index("</details>", start)]
        self.assertIn('<form method="post"', block)
        self.assertIn("toggle_developer_mode", block)
        self.assertNotIn('<a class="workspace-menubar-item" data-ui-ref="menu.archiosk.developer.mode-toggle"',
                         block)


class TheBadgeCarriesItsOwnExit(_MenuCase):
    """A mode you can see you are in but cannot leave from where you see it is
    the same defect as one you cannot find your way into."""

    def _dev_client(self):
        client = self._client("menu_admin", "admin", 1)
        with client.session_transaction() as sess:
            sess["developer_mode"] = True
        return client

    def test_the_badge_shows_when_developer_mode_is_on(self):
        body = self._home(self._dev_client())
        self.assertIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertIn("DEVELOPER MODE", body)

    def test_the_badge_carries_an_exit_control(self):
        body = self._home(self._dev_client())
        self.assertIn('data-ui-ref="menu.developer-mode-badge.exit"', body)

    def test_the_exit_is_labelled_for_screen_readers(self):
        # "×" alone announces as nothing useful.
        body = self._home(self._dev_client())
        i = body.index('data-ui-ref="menu.developer-mode-badge.exit"')
        tag = body[body.rindex("<button", 0, i):body.index(">", i) + 1]
        self.assertIn('aria-label="Exit Developer Mode"', tag)

    def test_the_exit_actually_leaves_developer_mode(self):
        client = self._dev_client()
        resp = client.post("/developer-mode/toggle")
        self.assertEqual(resp.status_code, 302)
        body = self._home(client)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)

    def test_neither_badge_nor_exit_appears_when_the_mode_is_off(self):
        body = self._home(self._client("menu_admin", "admin", 1))
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge.exit"', body)

    def test_a_non_admin_never_sees_the_exit(self):
        # Defence in depth: the flag cannot be set for a non-admin, but if it
        # somehow were, the control must still not render for them.
        client = self._client("menu_reader", "read_only", 2)
        with client.session_transaction() as sess:
            sess["developer_mode"] = True
        body = self._home(client)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge.exit"', body)

    def test_the_exit_is_a_post_not_a_get_link(self):
        # A GET would put a session state change in browser history.
        start = _MENU.index('data-ui-ref="menu.developer-mode-badge"')
        block = _MENU[start:start + 1400]
        self.assertIn('<form method="post"', block)
        self.assertNotIn('<a class="workspace-developer-mode-exit"', block)

    def test_the_indicator_itself_is_still_an_indicator(self):
        # The original decision - badge as operational boundary indicator, not a
        # casual mode-switch button - is narrowed, not discarded: the status
        # text keeps role="status" and gains no handler of its own.
        body = self._home(self._dev_client())
        i = body.index('data-ui-ref="menu.developer-mode-badge"')
        tag = body[body.rindex("<span", 0, i):body.index(">", i) + 1]
        self.assertIn('role="status"', tag)
        self.assertNotIn("onclick", tag)


class ItActuallyWorksEndToEnd(_MenuCase):
    def test_entering_developer_mode_reveals_the_developer_composer(self):
        # The point of finding the control is what it unlocks - and as of
        # CLAUDE-DEVELOPER-COMPOSER-IMAGE-01 that Composer accepts screenshots.
        client = self._client("menu_admin", "admin", 1)
        self.assertNotIn('data-ui-ref="developer.home.composer.form"', self._home(client))
        resp = client.post("/developer-mode/toggle")
        self.assertEqual(resp.status_code, 302)
        root = client.get("/")
        self.assertEqual(root.status_code, 302)
        self.assertEqual(root.headers["Location"], "/projects")
        body = client.get("/admin/developer-tools").get_data(as_text=True)
        self.assertIn('data-ui-ref="developer.home.composer.form"', body)
        self.assertIn('data-ui-ref="developer.home.composer.attach"', body)

    def test_leaving_developer_mode_puts_it_back(self):
        client = self._client("menu_admin", "admin", 1)
        client.post("/developer-mode/toggle")
        client.post("/developer-mode/toggle")
        self.assertNotIn('data-ui-ref="developer.home.composer.form"', self._home(client))


if __name__ == "__main__":
    unittest.main()
