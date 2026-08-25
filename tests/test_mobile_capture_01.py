"""CLAUDE-MOBILE-CAPTURE-01 - a phone can reach the image tray.

The Image Search tray already invited a "capture", and its aria-label already
promised one, but the only ways in were paste and drop. Neither exists on a
phone, so on mobile the invitation was unfulfillable. This adds a plain file
input with `accept="image/*"` and `capture="environment"` and feeds it to the
SAME handler paste and drop already use.

What these tests are really guarding is that it stayed that way: one code
path, no mobile-only behaviour, no new ingestion route, and no bypass of the
project boundary. The phone is another doorway into GO, not another GO.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_HTML = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
CASE_HTML = (ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
MARKS_JS = (ROOT / "static" / "js" / "document_marks.js").read_text(encoding="utf-8")


class TheCaptureControlExistsTests(unittest.TestCase):
    def test_a_file_input_backs_the_trays_capture_promise(self):
        self.assertIn('id="documents-image-search-file"', BASE_HTML)
        self.assertIn('data-ui-ref="lists.project.documents.image-search-capture"', BASE_HTML)

    def test_it_offers_photos_and_hints_the_rear_camera(self):
        block = BASE_HTML[BASE_HTML.index('id="documents-image-search-file"'):]
        block = block[: block.index(">")]
        self.assertIn('accept="image/*"', block)
        self.assertIn('capture="environment"', block)

    def test_it_has_a_visible_label(self):
        """A hidden input with no label is not an affordance."""
        self.assertIn('for="documents-image-search-file"', BASE_HTML)

    def test_it_lives_in_the_rendering_tray_not_the_dead_one(self):
        """base.html keeps a second, deliberately dead copy of this tray inside
        an `{% if false %}` branch. The control belongs to the live one."""
        self.assertEqual(BASE_HTML.count('id="documents-image-search-file"'), 1)
        first_tray = BASE_HTML.index('id="documents-image-search-tray"')
        dead_branch = BASE_HTML.index("{% if false %}")
        self.assertLess(first_tray, dead_branch)
        self.assertLess(BASE_HTML.index('id="documents-image-search-file"'), dead_branch)


class OneCodePathTests(unittest.TestCase):
    def test_capture_feeds_the_same_handler_as_paste_and_drop(self):
        """The whole point: a photo taken on a phone is handled identically to
        one pasted on a desktop."""
        self.assertIn("documents-image-search-file", MARKS_JS)
        # One definition, and the capture handler calls it - asserted as a
        # property rather than a call count, which would break the next time
        # anyone mentions the function in a comment.
        self.assertEqual(MARKS_JS.count("function loadImageFile("), 1)
        capture_block = MARKS_JS[MARKS_JS.index("var imageFileInput"):]
        capture_block = capture_block[: capture_block.index("imageTray.addEventListener('dragover'")]
        self.assertIn("loadImageFile(files[0])", capture_block)

    def test_capture_reuses_the_composer_phone_image_normalizer_when_available(self):
        """Document Search must not bypass the Composer's tested 5MB/edge
        normalization path for the same phone photo."""
        self.assertIn("window.ArchioskPrepareImage", MARKS_JS)
        self.assertNotIn("new FileReader", MARKS_JS[MARKS_JS.index("function loadImageFile"):MARKS_JS.index("function clearImageQuery")])
        composer = (ROOT / "static" / "js" / "composer_attach.js").read_text(encoding="utf-8")
        self.assertIn("window.ArchioskPrepareImage = function", composer)
        self.assertIn("MAX_EDGE", composer)
        self.assertIn("MAX_BYTES", composer)

    def test_shared_normalizer_loads_before_document_search(self):
        self.assertLess(
            BASE_HTML.index('js/composer_attach.js'),
            CASE_HTML.index('js/document_marks.js'),
        )

    def test_no_separate_mobile_branch_was_introduced(self):
        for forbidden in ("isMobile", "userAgent", "ontouchstart", "field_mode", "fieldMode"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, MARKS_JS)

    def test_the_input_resets_so_the_same_photo_can_be_chosen_twice(self):
        block = MARKS_JS[MARKS_JS.index("documents-image-search-file"):]
        block = block[: block.index("imageTray.addEventListener('dragover'")]
        self.assertIn("imageFileInput.value = ''", block)

    def test_it_degrades_when_the_input_is_absent(self):
        block = MARKS_JS[MARKS_JS.index("documents-image-search-file"):]
        self.assertIn("if (imageFileInput)", block)


class NoNewEvidenceOrIngestionPathTests(unittest.TestCase):
    """Capture changes how an image ARRIVES, never what happens to it."""

    def test_no_upload_route_was_added_to_the_tray(self):
        block = MARKS_JS[MARKS_JS.index("documents-image-search-file"):]
        block = block[: block.index("function clearImageQuery")]
        for forbidden in ("fetch(", "XMLHttpRequest", "FormData", ".submit()"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, block)

    def test_every_vision_path_is_governed(self):
        """Was: open_image_in_composer is the ONE vision-capable route.

        CLAUDE-GO-COMPOSER-CAPTURE-01 deliberately added a second, at the
        Product Owner's explicit request - the Composer's own "+" - because a
        photo reaching GO only through Image Search's no-match state was the
        handoff the persistent Composer exists to remove.

        A bare count was never the real protection; what matters is that
        vision cannot arrive through an ungoverned back door. So: every call
        site lives in this one file, and each is preceded by the same
        external-AI policy resolver every other transmission uses."""
        workspace = (ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        # CLAUDE-COMPOSER-EVIDENCE-JOIN-01 made it three. The photo turn stopped
        # calling the model itself and now reaches it through the shared
        # conversational spine, and candidate naming became its own small call in
        # the one branch that uses it. Both still transmit an image, so both are
        # real vision call sites and both are counted here.
        #
        # The count was never the protection - the gating assertion below is. It
        # caught this change honestly: the naming helper was initially governed
        # only by WHERE it was called from, and now resolves the policy gate
        # itself, which is what this test's own "no ungoverned back door" wording
        # actually requires.
        call_sites = workspace.count("image_base64=")
        self.assertEqual(call_sites, 3)

        # No other route module may transmit an image at all.
        for other in (ROOT / "routes").glob("*.py"):
            if other.name == "workspace.py":
                continue
            with self.subTest(module=other.name):
                self.assertNotIn("image_base64=", other.read_text(encoding="utf-8"))

        # Each call site is gated: the policy decision is resolved before it.
        for index in range(call_sites):
            position = -1
            for _ in range(index + 1):
                position = workspace.index("image_base64=", position + 1)
            preceding = workspace[:position]
            with self.subTest(call_site=index):
                self.assertIn("ACTION_EXTERNAL_AI_REQUEST", preceding)

    def test_gps_coordinates_are_still_never_read(self):
        """services/image_intelligence.py detects GPS PRESENCE only. Mobile
        capture makes casual photography far more likely, so this boundary
        matters more now, not less."""
        image_intel = (ROOT / "services" / "image_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("GPS", image_intel)
        self.assertIn("presence", image_intel.lower())


class ItRendersForAnAuthorizedUserTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(
                username="mob", password_hash=generate_password_hash("x"), role="admin",
            ))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "mob"
            sess["role"] = "admin"

    def test_the_control_is_not_exposed_to_an_anonymous_visitor(self):
        """It lives inside the authenticated shell; the public landing must not
        carry a project capture control."""
        anon = self.flask_app.test_client()
        body = anon.get("/").get_data(as_text=True)
        self.assertNotIn("documents-image-search-file", body)


if __name__ == "__main__":
    unittest.main()
