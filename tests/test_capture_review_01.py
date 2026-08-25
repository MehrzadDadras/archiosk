"""
CLAUDE-CAPTURE-REVIEW-01 - look at the photo before it is attached.

Product Owner, from live phone use: the phone's own camera gives a review moment
- keep, crop, retake - and the Composer went straight from shutter to attached.

WHAT THE INVESTIGATION FOUND, AND WHY THE ORDER MATTERS MORE THAN THE UI

Discard and retake already existed. What was missing was a moment to LOOK, and -
less visibly but more importantly - the ORDER of operations:
ArchioskPrepareImage ran the instant a file was picked, so the only image that
ever existed to review had already been downscaled to MAX_EDGE and re-encoded. A
crop bolted on after that would have cropped into a re-encode, and for
construction review the detail that matters (a damper label, a drawing stamp, a
serial number) is exactly what that throws away.

So most of this file asserts SEQUENCE rather than appearance:

    original File held untouched
      -> preview from an object URL, nothing normalized
        -> crop computed against NATURAL pixels
          -> "Use photo"
            -> ArchioskPrepareImage runs, ONCE, on the chosen result
              -> field.value is finally set

THE BOUNDARY THAT KEEPS THIS BOUNDED

ArchioskPrepareImage is shared with Image Search (document_marks.js). Putting
review inside it would give Image Search a camera confirmation step it never
asked for. The helper is asserted BYTE-IDENTICAL to its committed form, and
Image Search is asserted to have gained nothing.

Rotate is DEFERRED by explicit Product Owner decision until the existing
EXIF/orientation behaviour is understood. Its absence is asserted, so a later
half-built rotate control cannot appear unnoticed.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ATTACH_JS = _REPO_ROOT / "static" / "js" / "composer_attach.js"
_MARKS_JS = _REPO_ROOT / "static" / "js" / "document_marks.js"
_MACROS = _REPO_ROOT / "templates" / "_macros.html"
_CSS = _REPO_ROOT / "static" / "css" / "main.css"

ATTACH_JS = _ATTACH_JS.read_text(encoding="utf-8")
MACROS = _MACROS.read_text(encoding="utf-8")
CSS = _CSS.read_text(encoding="utf-8")


def _strip_js_comments(source: str) -> str:
    source = re.sub(r"/\*[\s\S]*?\*/", "", source)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", source)


CODE = _strip_js_comments(ATTACH_JS)


class NothingIsAttachedUntilUsePhotoTests(unittest.TestCase):
    """field.value is the moment of commitment. It must arrive last."""

    def test_only_one_path_commits_a_value_to_the_field(self):
        """Every other write must CLEAR it.

        Counting writes was the wrong invariant - clear() and fail() both
        legitimately empty the field, and a third clearing path is harmless.
        What must stay singular is the path that puts a real value IN.
        """
        writes = re.findall(r"field\.value\s*=\s*([^;]+);", CODE)
        self.assertTrue(writes)
        commits = [w.strip() for w in writes if w.strip() not in ("''", '""')]
        self.assertEqual(commits, ["dataUrl"],
                         "something other than show() commits a value to the field")

    def test_show_is_reached_only_after_prepare_which_is_reached_only_from_use(self):
        use = CODE[CODE.index("reviewUse.addEventListener"):]
        use = use[:use.index("\n    function attach(")]
        self.assertIn("window.ArchioskPrepareImage(chosen", use)
        self.assertIn("show(name, dataUrl)", use)

    def test_opening_the_review_commits_nothing(self):
        open_review = CODE[CODE.index("function openReview(file)"):]
        open_review = open_review[:open_review.index("\n    }")]
        for token in ("field.value", "ArchioskPrepareImage", "show("):
            self.assertNotIn(token, open_review, token)

    def test_attach_opens_the_review_instead_of_preparing(self):
        attach = CODE[CODE.index("function attach(file)"):]
        attach = attach[:attach.index("\n    }")]
        self.assertIn("openReview(file)", attach)
        # The pre-review behaviour survives only as a fallback for a surface
        # that renders no review markup - guarded, never the Composer's path.
        self.assertIn("if (review && reviewImage)", attach)


class TheOriginalIsHeldUnchangedTests(unittest.TestCase):
    def test_the_file_itself_is_held_not_a_derived_copy(self):
        self.assertIn("pendingFile = file", CODE)

    def test_the_preview_is_an_object_url_not_a_normalized_data_url(self):
        # An object URL displays the ORIGINAL bytes with no decode/re-encode.
        self.assertIn("window.URL.createObjectURL(file)", CODE)

    def test_the_preview_url_is_released(self):
        self.assertIn("window.URL.revokeObjectURL", CODE)

    def test_an_uncropped_photo_is_passed_through_untouched(self):
        # No canvas round trip when nothing was cropped: re-encoding an
        # untouched photo would lose quality for nothing.
        resolve = CODE[CODE.index("function resolveChosenImage"):]
        head = resolve[:resolve.index("var image = new Image()")]
        self.assertIn("if (!cropRect)", head)
        self.assertIn("callback(pendingFile)", head)


class CropWorksOnTheOriginalPixelsTests(unittest.TestCase):
    """The whole reason the review had to come BEFORE normalization."""

    def test_the_crop_is_scaled_to_natural_dimensions(self):
        self.assertIn("reviewImage.naturalWidth / point.rect.width", CODE)
        self.assertIn("reviewImage.naturalHeight / point.rect.height", CODE)

    def test_the_crop_draws_from_the_original_preview(self):
        resolve = CODE[CODE.index("function resolveChosenImage"):]
        resolve = resolve[:resolve.index("\n    if (reviewUse)")]
        self.assertIn("image.src = pendingUrl", resolve)
        self.assertIn("cropRect.x, cropRect.y, cropRect.w, cropRect.h", resolve)

    def test_normalization_happens_after_the_crop_not_before(self):
        # The ordering defect this whole stage exists to fix.
        self.assertLess(CODE.index("function resolveChosenImage"),
                        CODE.index("window.ArchioskPrepareImage(chosen"))

    def test_a_tap_is_not_treated_as_a_crop(self):
        # Silently cropping to a few pixels is the worst possible reading of
        # someone simply touching the photo.
        self.assertIn("displayW < 12 || displayH < 12", CODE)
        tiny = CODE[CODE.index("displayW < 12"):]
        tiny = tiny[:tiny.index("return;")]
        self.assertIn("cropRect = null", tiny)

    def test_a_crop_can_be_undone_without_retaking(self):
        self.assertIn("reviewCropReset.addEventListener", CODE)
        undo = CODE[CODE.index("reviewCropReset.addEventListener"):]
        undo = undo[:undo.index("});")]
        self.assertIn("cropRect = null", undo)


class RetakeAndDiscardLeaveNothingBehindTests(unittest.TestCase):
    def test_both_close_the_review_and_clear_attachment_state(self):
        for name in ("reviewRetake", "reviewDiscard"):
            block = CODE[CODE.index(name + ".addEventListener"):]
            block = block[:block.index("});")]
            self.assertIn("closeReview()", block, name)
            self.assertIn("clear()", block, name)

    def test_retake_reopens_the_picker(self):
        retake = CODE[CODE.index("reviewRetake.addEventListener"):]
        retake = retake[:retake.index("});")]
        self.assertIn("input.click()", retake)

    def test_closing_releases_the_held_file_and_the_crop(self):
        close = CODE[CODE.index("function closeReview()"):]
        close = close[:close.index("\n    }")]
        self.assertIn("pendingFile = null", close)
        self.assertIn("cropRect = null", close)
        self.assertIn("releasePreview()", close)

    def test_clear_still_resets_the_input_so_the_same_file_can_be_picked_again(self):
        clear = CODE[CODE.index("function clear()"):]
        clear = clear[:clear.index("\n    }")]
        self.assertIn("input.value = ''", clear)
        self.assertIn("field.value = ''", clear)


class ImageSearchInheritsNothingTests(unittest.TestCase):
    """The shared helper is shared. It must not grow a camera UI."""

    def test_the_shared_helper_body_is_byte_identical_to_its_committed_form(self):
        committed = subprocess.run(
            ["git", "show", "HEAD:static/js/composer_attach.js"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
            check=True, encoding="utf-8",
        ).stdout

        def helper_body(source):
            start = source.index("window.ArchioskPrepareImage = function")
            return source[start:source.index("\n    };", start)]

        self.assertEqual(helper_body(committed), helper_body(ATTACH_JS))

    def test_image_search_gained_no_review_controls(self):
        marks = _MARKS_JS.read_text(encoding="utf-8")
        for token in ("capture-review", "openReview", "cropRect", "pendingFile"):
            self.assertNotIn(token, marks, token)

    def test_image_search_still_delegates_to_the_helper(self):
        marks = _MARKS_JS.read_text(encoding="utf-8")
        self.assertIn("window.ArchioskPrepareImage(file", marks)

    def test_the_review_markup_lives_only_in_the_composer(self):
        for path in (_REPO_ROOT / "templates").rglob("*.html"):
            if path.name == "_macros.html":
                continue
            self.assertNotIn("dock-capture-review", path.read_text(encoding="utf-8"), path.name)


class EveryPhotoInAQIsReviewedTests(unittest.TestCase):
    """Including the second and third, by construction rather than by wiring."""

    def test_there_is_one_capture_path_for_every_photo(self):
        # The file input's change handler is the only entry, and it calls
        # attach() - so a second or third photo added through multi-image Q
        # travels the identical path and gets the identical review.
        self.assertEqual(CODE.count("input.addEventListener('change'"), 1)
        change = CODE[CODE.index("input.addEventListener('change'"):]
        change = change[:change.index("});")]
        self.assertIn("attach(files[0])", change)

    def test_the_add_to_q_button_does_not_bypass_the_review(self):
        # Add to this Q sends a phrase; it never attaches an image itself.
        add = CODE[CODE.index("addToQ.addEventListener"):]
        add = add[:add.index("});")]
        for token in ("ArchioskPrepareImage", "field.value", "openReview"):
            self.assertNotIn(token, add, token)


class ItIsAConfirmationNotAnEditorTests(unittest.TestCase):
    def test_no_editing_controls_beyond_crop(self):
        # The markup's own comment lists what this deliberately is NOT, naming
        # these very words - so prose is stripped before asserting absence, or
        # the explanation of a prohibition satisfies the test for it.
        markup = re.sub(r"\{#[\s\S]*?#\}", "", MACROS)
        for token in ("brightness", "contrast", "filter", "saturation",
                      "annotate", "markup", "drawText", "fillText"):
            self.assertNotIn(token, CODE, token)
            self.assertNotIn(token, markup, token)

    def test_rotate_is_deferred_not_half_built(self):
        # Product Owner deferred rotate until EXIF/orientation is understood.
        # A stub would be worse than its absence.
        self.assertNotIn("rotate", CODE.lower())
        markup = re.sub(r"\{#[\s\S]*?#\}", "", MACROS)
        self.assertNotIn("capture-review-rotate", markup)

    def test_use_photo_is_the_first_and_primary_action(self):
        markup = re.sub(r"\{#[\s\S]*?#\}", "", MACROS)
        block = markup[markup.index('class="capture-review-actions"'):]
        block = block[:block.index("</div>")]
        order = [m for m in re.findall(r'id="dock-capture-review-([a-z-]+)"', block)]
        self.assertEqual(order[0], "use", "Use photo must come first")
        rule = re.search(r"\.capture-review-use\s*\{[^}]*\}", CSS)
        self.assertIsNotNone(rule)
        self.assertIn("flex: 1 1 auto", rule.group(0))

    def test_the_review_ships_hidden(self):
        block = re.search(r'<div class="capture-review"[^>]*>', MACROS, re.S)
        self.assertIsNotNone(block)
        self.assertIn("hidden", block.group(0))


class MobileTreatmentTests(unittest.TestCase):
    def test_the_photo_cannot_push_the_actions_off_screen(self):
        rules = re.findall(r"\.capture-review-image\s*\{[^}]*\}", CSS)
        self.assertTrue(rules)
        self.assertIn("max-height", rules[0])

    def test_dragging_on_the_photo_crops_rather_than_scrolls(self):
        rules = re.findall(r"\.capture-review-image\s*\{[^}]*\}", CSS)
        self.assertIn("touch-action: none", rules[0])

    def test_it_becomes_a_bottom_sheet_clearing_the_home_indicator(self):
        phone = CSS[CSS.index("CLAUDE-CAPTURE-REVIEW-01"):]
        phone = phone[phone.index("@media (max-width: 640px)"):]
        self.assertIn("position: fixed", phone)
        self.assertIn("safe-area-inset-bottom", phone)

    def test_the_actions_are_touch_sized(self):
        for selector in (".capture-review-use", ".capture-review-action"):
            rule = re.search(re.escape(selector) + r"\s*\{[^}]*\}", CSS)
            self.assertIsNotNone(rule, selector)
            height = re.search(r"min-height:\s*(\d+)px", rule.group(0))
            self.assertIsNotNone(height, selector)
            self.assertGreaterEqual(int(height.group(1)), 44, selector)


if __name__ == "__main__":
    unittest.main()
