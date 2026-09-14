/* CLAUDE-DOCUMENT-UPLOAD-PUBLIC-UX-01 - ARCHIOSK owns the visible upload state.
 *
 *   Choose files   No file chosen        <- the browser's wording, not ours
 *   [ Choose files ]                     <- ours, and it says what we mean
 *
 * A native file input renders its own status text beside itself, and that text
 * is the browser's: "No file chosen" on Chrome, "No files selected" on Firefox,
 * nothing at all on some mobile shells. It cannot be styled, cannot be worded,
 * and on an empty form it is the loudest thing on the page - telling a person
 * what they have NOT done before they have had a chance to do it.
 *
 * THIS IS NOT A NEW PATTERN. `templates/upload.html` already does exactly this
 * for project creation: the real input carries `class="visually-hidden"`, a real
 * <button> opens it, and an ARCHIOSK-owned list renders the selection. That
 * implementation also carries founding-document logic specific to that page, so
 * this file is the same pattern made reusable rather than a second invention -
 * driven entirely by data attributes, with no knowledge of any one page.
 *
 * `visually-hidden` AND NOT `hidden`, WHICH IS THE WHOLE ACCESSIBILITY POINT.
 * `hidden` and `display: none` remove the input from the accessibility tree and
 * from the tab order, so a keyboard or screen-reader user loses the control
 * entirely and `.click()` becomes the only way in. `.visually-hidden` clips it
 * to a 1px box while leaving it focusable, labelled and activatable, so the
 * native picker - including a phone's camera and photo picker - still opens by
 * the browser's own semantics. A `<label for>` pointing at it keeps working; so
 * does drag-and-drop, which targets the input rather than the button.
 *
 * WHAT IT NEVER DOES: it never reads, renames, reorders or rewrites a file. The
 * FileList belongs to the browser and is submitted unchanged, so provenance,
 * hashes and the original filenames are untouched by anything here. It is a
 * label for a state the input already has.
 */
(function () {
    'use strict';

    function fileWord(count) {
        return count === 1 ? '1 file selected' : count + ' files selected';
    }

    function wire(root) {
        var input = root.querySelector('[data-upload-input]');
        var button = root.querySelector('[data-upload-choose]');
        var status = root.querySelector('[data-upload-status]');
        var names = root.querySelector('[data-upload-names]');
        if (!input || !button || !status) {
            return;
        }

        // The button is a convenience, not the control. If script never runs,
        // the input is still there and still works - it is only visually
        // clipped, and the label remains associated with it.
        button.addEventListener('click', function () {
            input.click();
        });

        // Focus is forwarded so the visible button shows the focus ring the
        // clipped input would otherwise be showing off-screen.
        input.addEventListener('focus', function () {
            button.classList.add('upload-choose-focused');
        });
        input.addEventListener('blur', function () {
            button.classList.remove('upload-choose-focused');
        });

        function paint() {
            var files = input.files ? Array.prototype.slice.call(input.files) : [];
            if (!files.length) {
                // The EMPTY state says nothing, deliberately. "No file chosen"
                // is the wording being removed; replacing it with our own
                // version of the same sentence would miss the point.
                status.textContent = '';
                status.hidden = true;
                if (names) {
                    names.textContent = '';
                    names.hidden = true;
                }
                return;
            }
            status.textContent = fileWord(files.length);
            status.hidden = false;
            if (names) {
                // ORIGINAL FILENAMES, EXACTLY AS THE BROWSER REPORTS THEM.
                // `textContent` rather than any markup path, so a filename
                // containing < or & is shown rather than interpreted - a
                // filename is attacker-supplied text on this surface.
                names.textContent = files.map(function (file) {
                    return file.name;
                }).join(', ');
                names.hidden = false;
            }
        }

        input.addEventListener('change', paint);
        paint();
    }

    function init() {
        var roots = document.querySelectorAll('[data-upload-control]');
        Array.prototype.forEach.call(roots, wire);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
