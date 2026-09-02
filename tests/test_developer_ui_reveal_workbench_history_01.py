"""Focused coverage for the bounded Developer identity/workbench/chat slice."""
from pathlib import Path
import shutil
import tempfile
import unittest


class DeveloperUiRevealWorkbenchHistoryTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_dev_workbench_"))
        self.app = app_module.create_app("testing")
        self.app.config.update(REGISTRY_STORE_PATH=str(self.tmp), TESTING=True)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess.update({"user_id": 1, "username": "admin", "role": "admin", "developer_mode": True})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reveal_is_server_session_gated_and_maps_inventory_identity(self):
        response = self.client.get("/admin/developer-tools")
        self.assertNotIn(b"TPL-012", response.data)
        self.client.post("/developer-mode/ui-reveal")
        response = self.client.get("/admin/developer-tools")
        self.assertIn(b"TPL-012 \xc2\xb7 Developer Tools", response.data)
        self.assertIn(b"Reveal Template IDs" if False else b"Hide Template IDs", response.data)

    def test_client_cannot_fabricate_template_context(self):
        response = self.client.post("/developer-composer/context", data={
            "object_type": "template_surface", "object_id": "TPL-999", "label": "TPL-999 · Fake",
        })
        self.assertEqual(response.status_code, 400)

    def test_workbench_has_one_composer_and_history_controls(self):
        """CLAUDE-ONE-COMPOSER-01: asserted by ROUTE, not by button wording.

        This previously required the literal strings "New Chat" and "Delete
        Chat". Those words were the accidental history, not the intent - the
        product names the same act "New" on the project side
        (chat.dock.new-conversation), and inventing a second vocabulary for it
        was part of what made this read as a separate chat system.

        The intent - exactly one composer, and the history controls genuinely
        present - is unchanged and now checked against the endpoints they post
        to, which is stronger: a renamed button still passes, a removed
        capability does not.
        """
        response = self.client.get("/admin/developer-tools")
        self.assertEqual(response.data.count(b'data-ui-ref="developer.home.composer.form"'), 1)
        self.assertIn(b'data-developer-workbench', response.data)
        self.assertIn(b"/developer-composer/new-chat", response.data)
        self.client.post("/developer-composer", data={"message": "Inspect the home page"})
        response = self.client.get("/admin/developer-tools")
        self.assertIn(b"Inspect the home page", response.data)
        self.assertIn(b"/developer-composer/delete-chat", response.data)

    def test_new_chat_preserves_old_chat_and_delete_requires_confirmation(self):
        self.client.post("/developer-composer", data={"message": "First chat"})
        self.client.post("/developer-composer/new-chat")
        with self.client.session_transaction() as sess:
            self.assertGreaterEqual(len(sess["developer_home_chats"]), 2)
            current = sess["developer_home_current_chat_id"]
        self.assertEqual(self.client.post("/developer-composer/delete-chat", data={"chat_id": current}).status_code, 400)
