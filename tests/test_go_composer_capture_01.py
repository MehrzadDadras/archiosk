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
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services import case_workspace as cw
from services.requirements_registry import RequirementsRegistry

MACROS = (Path(__file__).resolve().parents[1] / "templates" / "_macros.html").read_text(encoding="utf-8")
ROOT_DIR = Path(__file__).resolve().parents[1]
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
        """Hermetic double for both model calls the photo path can make.

        CLAUDE-COMPOSER-EVIDENCE-JOIN-01: the photo turn reasons through the
        shared conversational spine now, so the reply must be patched at
        `services.conversational_turn.call_llm_json` - the BOUND name in the
        module that calls it. That module binds the symbol at import, so the old
        `services.llm_gateway` patch no longer intercepted it and this test would
        have gone silently un-hermetic; an un-mocked call on this path once cost
        this repository an 8.5-hour run.

        Naming keeps the llm_gateway patch: `_propose_capture_names` imports
        inside the function, so it resolves at call time.
        """
        def _outcome(parsed):
            return type("O", (), {
                "ran": True, "parsed": parsed,
                "provider": "x", "model": "y", "requested_at": "z",
                "skipped_reason": None,
            })()

        turn = _outcome({
            "reply_text": reply,
            "intent_class": "general_answer",
            "candidate_referents": [],
        })
        naming = _outcome({"proposed_names": list(names)})

        from contextlib import ExitStack

        class _Both:
            def __enter__(self_inner):
                self_inner.stack = ExitStack()
                self_inner.stack.enter_context(
                    patch("services.conversational_turn.call_llm_json", return_value=turn))
                self_inner.stack.enter_context(
                    patch("services.llm_gateway.call_llm_json", return_value=naming))
                return self_inner

            def __exit__(self_inner, *exc):
                return self_inner.stack.__exit__(*exc)

        return _Both()


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

    def test_new_renders_in_the_dock(self):
        self.assertIn('data-ui-ref="chat.dock.new-conversation"', MACROS)

    def test_archive_is_not_offered_from_the_composer(self):
        """Product Owner, explicit: "Remove 'Archive this conversation' or
        anything in that regard." Removed in full - markup, styling, registry
        row and these assertions - rather than hidden, because a control that
        renders nowhere but still has CSS and a registry row misleads whoever
        reads this next."""
        self.assertNotIn("chat.dock.archive-conversation", MACROS)
        self.assertNotIn("conversation-lifecycle-archive", MACROS)
        self.assertNotIn("conversation-lifecycle-archive", CSS)

    def test_the_capability_itself_is_untouched(self):
        """Removing the Composer control is not withdrawing the ability to
        archive an Investigation - that still lives in the Toolbox list, with
        its own confirmation page and authority check."""
        workspace_template = (
            Path(__file__).resolve().parents[1] / "templates" / "case_workspace.html"
        ).read_text(encoding="utf-8")
        self.assertIn("confirm_archive_case", workspace_template)
        self.assertIn("toolbox.investigations.leaf.archive", workspace_template)

    def test_no_destructive_alternative_was_introduced_in_its_place(self):
        self.assertNotIn("delete_case", MACROS)


class APhoneSizedPhotoMustNotBeRefusedTests(unittest.TestCase):
    """CLAUDE-GO-COMPOSER-CAPTURE-02. Product Owner, from an actual site photo:
    "I took a photo by my phone and the message is: That photo is too large
    (5MB limit)."

    A current phone camera produces 3-12MB per frame as a matter of course, so
    the FIRST real photo taken with this feature hit the ceiling - the entry
    point to the application failing on its own primary input. Refusing was the
    wrong answer; the ceiling is the vision API's own and not ours to raise, so
    the photo is brought under it before it is ever sent.
    """

    def test_the_photo_is_resized_rather_than_refused(self):
        self.assertIn("canvas", ATTACH_JS)
        self.assertIn("drawImage", ATTACH_JS)
        self.assertIn("toDataURL", ATTACH_JS)

    def test_it_targets_the_size_the_vision_model_actually_uses(self):
        """Anything beyond roughly 1568px on the long edge is bytes spent to be
        downsampled away - and a slower upload on site signal."""
        self.assertIn("MAX_EDGE = 1568", ATTACH_JS)

    def test_quality_steps_down_until_it_fits(self):
        block = ATTACH_JS[ATTACH_JS.index("QUALITY_STEPS"):]
        block = block[: block.index("]")]
        self.assertIn("0.85", block)
        self.assertIn("0.4", block)

    def test_a_photo_that_already_fits_is_left_alone(self):
        """An image under both limits keeps its original bytes and format -
        re-encoding it would only lose quality for nothing.

        The preparation logic moved into window.ArchioskPrepareImage when image
        normalization was unified across the Composer and Image Search, so this
        follows it there. The property is unchanged and is what is asserted: on
        the fits-already path the ORIGINAL data URL is handed back untouched and
        the function returns before any canvas work.
        """
        block = ATTACH_JS[ATTACH_JS.index("window.ArchioskPrepareImage = function"):]
        block = block[: block.index("var scale = Math.min")]
        self.assertIn("<= MAX_BYTES", block)
        self.assertIn("<= MAX_EDGE", block)
        # The original, not a re-encoded copy.
        self.assertIn("onReady(file.name || 'Photo', original)", block)
        self.assertNotIn("canvas", block)

    def test_the_old_bare_refusal_is_gone(self):
        """The exact message the Product Owner was shown must not survive as
        BEHAVIOUR. Scanned against code rather than prose - this file's own
        comment quotes that message verbatim to explain why it was removed,
        and a naive substring check is satisfied by the explanation."""
        code = re.sub(r"/\*.*?\*/", "", ATTACH_JS, flags=re.S)
        code = re.sub(r"(?<![:\w])//.*$", "", code, flags=re.M)
        self.assertNotIn("That photo is too large", code)

    def test_undecodable_formats_are_reported_honestly(self):
        """HEIC the browser cannot open is the realistic case - iOS usually
        hands a JPEG to a file input, but not always. Saying so beats a silent
        failure or a misleading size complaint."""
        self.assertIn("image.onerror", ATTACH_JS)
        self.assertIn("cannot open", ATTACH_JS)

    def test_the_server_ceiling_is_still_enforced_independently(self):
        """Client-side shrinking is a convenience, never the boundary."""
        route = (ROOT_DIR / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertIn("_MAX_IMAGE_BYTES", route)
        self.assertGreaterEqual(route.count("> _MAX_IMAGE_BYTES"), 2)


class TheNextStepIsVisibleTests(unittest.TestCase):
    """CLAUDE-GO-COMPOSER-CAPTURE-03. Product Owner: "I took the picture and
    chose use it then the next step is not clear?"

    Fair. "Make a new Q" was a phrase invented in conversation and written
    nowhere in the product, so the one action this entry point exists for was
    discoverable only by having been told it.
    """

    def test_the_action_is_offered_with_the_photo(self):
        self.assertIn('data-ui-ref="chat.composer.attach.make-q"', MACROS)
        self.assertIn("Make a new Q", MACROS)

    def test_it_appears_and_disappears_with_the_photo(self):
        """Never a control with nothing to act on."""
        self.assertIn('id="dock-composer-image-next" hidden', MACROS)
        self.assertIn("nextStep.hidden = false", ATTACH_JS)
        self.assertIn("nextStep.hidden = true", ATTACH_JS)

    def test_a_failed_attachment_withdraws_the_offer(self):
        code = ATTACH_JS[ATTACH_JS.index("function fail("):]
        code = code[: code.index("function approximateBytes")]
        self.assertIn("nextStep.hidden = true", code)

    def test_the_phrase_is_written_into_the_box_not_posted_behind_them(self):
        """It lands in the conversation as the reviewer's own message, which is
        how they learn they could have typed it - and that they may type
        something else instead."""
        # CLAUDE-MULTI-IMAGE-Q-01 factored the two phrase buttons ("Make a new Q"
        # and "Add to this Q") onto one sendAs helper, so the write to the box
        # lives there now. The property is unchanged and is asserted in both
        # halves: the button carries the exact phrase, and the helper puts it in
        # the box rather than posting it.
        code = ATTACH_JS[ATTACH_JS.index("makeQ.addEventListener"):]
        self.assertIn("sendAs('Make a new Q')", code)
        helper = ATTACH_JS[ATTACH_JS.index("function sendAs("):]
        helper = helper[: helper.index("\n    }")]
        self.assertIn("messageBox.value = phrase", helper)

    def test_it_is_the_same_submit_and_not_a_second_route(self):
        helper = ATTACH_JS[ATTACH_JS.index("function sendAs("):]
        helper = helper[: helper.index("\n    }")]
        self.assertIn("form.requestSubmit", helper)
        # Checked across the whole file, not just the send path: a second route
        # introduced anywhere in this file would defeat the point.
        for forbidden in ("fetch(", "XMLHttpRequest", "action ="):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, ATTACH_JS)

    def test_both_phrase_buttons_share_one_submit_path(self):
        """Two buttons, one mechanism - so neither can drift into its own."""
        self.assertEqual(ATTACH_JS.count("function sendAs("), 1)
        self.assertIn("sendAs('Make a new Q')", ATTACH_JS)
        self.assertIn("sendAs('Add this to this Q')", ATTACH_JS)

    def test_the_message_box_says_what_it_is_for_while_a_photo_waits(self):
        self.assertIn("Ask about this photo", ATTACH_JS)

    def test_the_original_placeholder_returns_when_the_photo_goes(self):
        """The box must never describe an attachment that is no longer there."""
        code = ATTACH_JS[ATTACH_JS.index("function clear("):]
        code = code[: code.index("function show(")]
        self.assertIn("originalPlaceholder", code)

    def test_the_button_is_not_presented_as_the_only_option(self):
        self.assertIn("or just ask about it", MACROS)


if __name__ == "__main__":
    unittest.main()
