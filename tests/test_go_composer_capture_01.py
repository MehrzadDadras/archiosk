"""CLAUDE-GO-COMPOSER-CAPTURE-01 / -LIFECYCLE-01 - the entry point.

Product Owner: "add a '+' beside the Composer so I can add an image by my phone
camera and then tell Make a new 'Q' and he give it a name and save it as new
investigation and respond to my questions about it. That is a priority as that
is the entry point to the application." And: "I must be able to start a new
conversation and delete an old one."

The photo already had a way in, but it landed in Image Search and its only
onward move was an "Open in Composer" handoff. With a persistent Composer
already sitting below the work, that handoff is exactly the step that should
not exist - so the photo now attaches to the message itself and travels on the
same submit, through the same route, with the same context envelope.

Hermetic: `call_llm_json` is always patched. No Anthropic call is made.
"""
from __future__ import annotations

import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services import case_workspace as cw
from services.requirements_registry import RequirementsRegistry

MACROS = (Path(__file__).resolve().parents[1] / "templates" / "_macros.html").read_text(encoding="utf-8")
ATTACH_JS = (Path(__file__).resolve().parents[1] / "static" / "js" / "composer_attach.js").read_text(encoding="utf-8")
CSS = (Path(__file__).resolve().parents[1] / "static" / "css" / "main.css").read_text(encoding="utf-8")


def _png_data_url() -> str:
    """A real, decodable 2x2 PNG - register_eye_capture sniffs content, so a
    fake byte string would be rejected for the wrong reason and the test would
    pass while proving nothing."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (2, 2), (120, 120, 120)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class TheControlExistsWhereTheWorkIsTests(unittest.TestCase):
    def test_the_plus_sits_on_the_composer_form_itself(self):
        self.assertIn('for="dock-composer-image"', MACROS)
        self.assertIn('id="dock-composer-image"', MACROS)
        self.assertIn('name="image_data_url"', MACROS)

    def test_it_asks_a_phone_for_the_rear_camera(self):
        block = MACROS[MACROS.index('id="dock-composer-image"'):]
        block = block[: block.index(">")]
        self.assertIn('accept="image/*"', block)
        self.assertIn('capture="environment"', block)

    def test_the_photo_rides_the_same_submit_as_the_text(self):
        """One action, not three - no second upload route, no handoff."""
        for forbidden in ("fetch(", "XMLHttpRequest", "FormData", "action="):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, ATTACH_JS)
        self.assertIn("readAsDataURL", ATTACH_JS)

    def test_an_already_sent_photo_cannot_ride_along_with_the_next_message(self):
        self.assertIn("'submit'", ATTACH_JS)
        self.assertIn("clear", ATTACH_JS)

    def test_the_reviewer_can_see_and_remove_it_before_sending(self):
        self.assertIn('id="dock-composer-image-chip"', MACROS)
        self.assertIn('id="dock-composer-image-clear"', MACROS)

    def test_the_plus_is_a_real_touch_target(self):
        rule = CSS[CSS.index(".composer-attach {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("min-width: 44px", rule)
        self.assertIn("min-height: 44px", rule)


class _RouteBase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_composer_capture_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "proj-cap"

        with self.flask_app.app_context():
            db.session.add(User(
                username="cap", password_hash=generate_password_hash("x"), role="admin",
            ))
            db.session.commit()

        # `_load_workspace_or_404` resolves a project through the registry, so
        # a CaseWorkspaceStore entry alone is invisible to every route.
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx",
            ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[RequirementItem(
                id="i1", text="The system shall do a thing.",
                category="other", confidence=0.6, source_line=1,
            )],
        ))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "cap"
            sess["role"] = "admin"

        self.store = cw.CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)

    def _reload(self):
        return self.store.get_or_create(self.project_id)

    def _vision(self, reply="A steel sill support, corroded at the bearing.",
                names=("Corroded sill support", "Sill bearing corrosion")):
        outcome = type("O", (), {
            "ran": True,
            "parsed": {"reply": reply, "proposed_names": list(names)},
            "provider": "x", "model": "y", "requested_at": "z",
            "skipped_reason": None,
        })()
        return patch("services.llm_gateway.call_llm_json", return_value=outcome)


class MakeANewQTests(_RouteBase):
    def test_a_photo_plus_make_a_new_q_creates_a_named_investigation(self):
        before = len(self._reload().cases)
        with self._vision():
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "make a new Q for this", "image_data_url": _png_data_url()},
                follow_redirects=False,
            )
        cases = self._reload().cases
        self.assertEqual(len(cases), before + 1)
        # Named from what the photo shows, not from the reviewer's typing.
        self.assertEqual(cases[-1]["title"], "Corroded sill support")

    def test_the_photo_is_saved_into_that_investigation(self):
        with self._vision():
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "start an investigation", "image_data_url": _png_data_url()},
            )
        ws = self._reload()
        case = ws.cases[-1]
        self.assertTrue(case["source_ids"], "the photo was not attached to the new Q")

    def test_go_answers_about_it_in_the_new_investigation(self):
        with self._vision(reply="A steel sill support, corroded at the bearing."):
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "make a new Q", "image_data_url": _png_data_url()},
            )
        case = self._reload().cases[-1]
        replies = [m["text"] for m in case["conversation"] if m["role"] == "ai"]
        self.assertTrue(replies)
        self.assertIn("corroded at the bearing", replies[0])

    def test_the_name_is_offered_as_a_label_not_a_conclusion(self):
        """Content proposes the name; the reviewer owns it."""
        with self._vision():
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "make a new Q", "image_data_url": _png_data_url()},
            )
        case = self._reload().cases[-1]
        reply = [m["text"] for m in case["conversation"] if m["role"] == "ai"][0]
        self.assertIn("Rename it", reply)
        self.assertIn("not a conclusion", reply)


class APhotoWithoutAskingForAQTests(_RouteBase):
    def test_it_is_answered_without_creating_anything(self):
        """Saving is a governed act and stays something the reviewer asks for."""
        before = len(self._reload().cases)
        with self._vision(reply="Looks like a duct penetration."):
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "what is this?", "image_data_url": _png_data_url()},
            )
        ws = self._reload()
        self.assertEqual(len(ws.cases), before, "an unrequested Investigation was created")
        replies = [m["text"] for m in ws.project_conversation if m["role"] == "ai"]
        self.assertTrue(any("duct penetration" in r for r in replies))

    def test_a_photo_with_no_words_is_still_a_complete_act(self):
        """The old empty-text guard would have refused this. Taking a photo and
        sending it is a whole thought on a phone."""
        with self._vision(reply="A cable tray."):
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "", "image_data_url": _png_data_url()},
            )
        replies = [m["text"] for m in self._reload().project_conversation if m["role"] == "ai"]
        self.assertTrue(any("cable tray" in r for r in replies))


class BoundariesTests(_RouteBase):
    def test_a_message_with_no_photo_is_completely_unaffected(self):
        from routes import workspace as wr

        handled, new_case = wr._composer_photo_turn(
            self.project_id, self.store, self.workspace, None, "just text", None,
        )
        self.assertFalse(handled)
        self.assertIsNone(new_case)

    def test_the_new_q_phrases_read_the_reviewers_own_words(self):
        """Deterministic, not a model decision - creating a governed object
        must not hinge on a classification."""
        from routes import workspace as wr

        self.assertTrue(wr._asked_for_a_new_investigation("make a new Q for this"))
        self.assertTrue(wr._asked_for_a_new_investigation("start an investigation"))
        self.assertFalse(wr._asked_for_a_new_investigation("what is this?"))
        self.assertFalse(wr._asked_for_a_new_investigation(""))

    def test_persistence_goes_through_the_governed_capture_pathway(self):
        """register_eye_capture is the EXIF-stripping, GPS-presence-only route.
        This file must never write an image to disk itself."""
        source = (Path(__file__).resolve().parents[1] / "routes" / "workspace.py").read_text(encoding="utf-8")
        helper = source[source.index("def _composer_photo_turn"):]
        helper = helper[: helper.index("@workspace_bp.route")]
        self.assertIn("register_eye_capture", helper)
        self.assertNotIn("write_bytes", helper)
        self.assertNotIn("open(", helper)


class ConversationLifecycleTests(_RouteBase):
    def test_new_conversation_creates_one_and_lands_in_it(self):
        before = len(self._reload().cases)
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/conversations/new",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        cases = self._reload().cases
        self.assertEqual(len(cases), before + 1)
        self.assertIn(cases[-1]["id"], response.headers["Location"])

    def test_both_controls_render_in_the_dock(self):
        self.assertIn('data-ui-ref="chat.dock.new-conversation"', MACROS)
        self.assertIn('data-ui-ref="chat.dock.archive-conversation"', MACROS)

    def test_ending_a_conversation_reuses_the_existing_governed_path(self):
        """Not a second, weaker removal beside a Composer button - the same
        confirm page, authority check and terminal semantics already in force."""
        self.assertIn("confirm_archive_case", MACROS)
        self.assertNotIn("delete_case", MACROS)

    def test_the_archive_control_is_absent_where_there_is_nothing_to_archive(self):
        """The project-level conversation has no single Investigation behind
        it, so the guard must render no control rather than a dead one."""
        block = MACROS[MACROS.index('data-ui-ref="chat.dock.archive-conversation"') - 400:]
        block = block[: block.index("</a>")]
        self.assertIn("{% if case_id", block)


if __name__ == "__main__":
    unittest.main()
