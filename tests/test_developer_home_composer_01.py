"""Focused proof for the application-level Developer Composer on Home."""
from pathlib import Path
import shutil
import tempfile
import unittest


class DeveloperHomeComposerTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_home_ccn_"))
        self.app = app_module.create_app("testing")
        self.app.config.update(REGISTRY_STORE_PATH=str(self.tmp), TESTING=True)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess.update({"user_id": 1, "username": "admin", "role": "admin"})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _developer(self, enabled=True):
        with self.client.session_transaction() as sess:
            sess["developer_mode"] = enabled

    def test_normal_home_keeps_orientation_without_developer_composer(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'data-ui-ref="developer.home.composer"', response.data)

    def test_home_ccn_is_application_scoped_and_lifecycle_works(self):
        self._developer()
        response = self.client.get("/")
        self.assertIn(b'data-ui-ref="developer.home.composer"', response.data)

        response = self.client.post("/developer-composer", data={"message": "/CCN inspect the project list"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["developer_ccn"]["id"])
            self.assertEqual(sess["developer_ccn"].get("project_id"), None)

        for command in ("/CCN status", "/CCN show"):
            self.client.post("/developer-composer", data={"message": command})
        response = self.client.get("/")
        self.assertIn(b"CCN:", response.data)
        self.assertIn(b"CCN status", response.data)

        self.client.post("/developer-composer", data={"message": "/CCN cancel"})
        response = self.client.get("/")
        self.assertNotIn(b'data-ui-ref="developer.ccn.active"', response.data)

    def test_inline_ccn_intent_accepts_space_and_colon_forms(self):
        self._developer()
        for command, expected in (
            ("/CCN Make the Developer Mode badge bold", "Make the Developer Mode badge bold"),
            ("/CCN: Move project selection into one interface", "Move project selection into one interface"),
        ):
            self.client.post("/developer-composer", data={"message": "/CCN cancel"})
            self.client.post("/developer-composer", data={"message": command})
            with self.client.session_transaction() as sess:
                self.assertEqual(sess["developer_ccn"]["intent"], expected)

    def test_ordinary_developer_question_is_answered_without_ccn(self):
        self._developer()
        response = self.client.post(
            "/developer-composer", data={"message": "How can we change the font for this icon: DEVELOPER MODE to make it bold?"}
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            reply = sess["developer_home_messages"][-1]["text"]
        self.assertIn("templates/_app_menu.html", reply)
        self.assertIn("font-weight: 700", reply)
        self.assertNotIn("Select an ARCHIOSK surface or use /CCN", reply)

    def test_ordinary_question_keeps_active_ccn_as_a_lens(self):
        self._developer()
        self.client.post("/developer-composer", data={"message": "/CCN: Make the badge bold"})
        self.client.post("/developer-composer", data={"message": "How is the Developer Mode badge implemented?"})
        with self.client.session_transaction() as sess:
            reply = sess["developer_home_messages"][-1]["text"]
        self.assertIn("templates/_app_menu.html", reply)
        self.assertIn("active CCN", reply)

    def test_home_selection_attaches_application_object_without_authorizing_mutation(self):
        self._developer()
        response = self.client.post(
            "/developer-composer/context",
            data={"object_type": "application_surface", "object_id": "project-list", "label": "Project list"},
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess["developer_application_selection"]["project_id"])
        self.client.post("/developer-composer", data={"message": "/CCN inspect this"})
        with self.client.session_transaction() as sess:
            elements = sess["developer_ccn"]["selected_elements"]
            self.assertEqual(elements[0]["object_id"], "project-list")
            self.assertIsNone(elements[0]["project_id"])
            self.assertEqual(elements[0]["classification"], "INVESTIGATE")

    def test_project_binding_is_rejected_and_non_admin_cannot_use_client_state(self):
        self._developer()
        self.assertEqual(
            self.client.post("/developer-composer", data={"message": "/CCN", "project_id": "project-a"}).status_code,
            400,
        )
        with self.client.session_transaction() as sess:
            sess.update({"role": "member", "developer_mode": True})
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotIn(b'data-ui-ref="developer.home.composer"', self.client.get("/").data)
        self.assertEqual(self.client.post("/developer-composer", data={"message": "/CCN"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
