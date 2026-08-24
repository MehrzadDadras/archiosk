/* CLAUDE-GO-COMPOSER-CAPTURE-01 — the Composer's "+" attachment.
 *
 * Product Owner: "add a '+' beside the Composer so I can add an image by my
 * phone camera and then tell Make a new 'Q'... That is the entry point to the
 * application."
 *
 * Deliberately tiny, and deliberately NOT a second upload path. The photo
 * rides the composer's ordinary form submit as a data URL in a hidden field,
 * so the text and the image arrive together, through the route that already
 * carries the anchor / current_view / selected_source_id envelope. That is
 * what lets "make a new Q" be one action rather than three, and it is why the
 * old "Open in Composer" handoff stops being necessary.
 *
 * Reuses the FileReader/data-URL idiom static/js/document_marks.js already
 * established for Image Search, rather than inventing a second one.
 */
(function () {
    'use strict';

    var input = document.getElementById('dock-composer-image');
    var field = document.getElementById('dock-composer-image-data');
    if (!input || !field) return;

    var chip = document.getElementById('dock-composer-image-chip');
    var thumb = document.getElementById('dock-composer-image-thumb');
    var nameEl = document.getElementById('dock-composer-image-name');
    var clearBtn = document.getElementById('dock-composer-image-clear');
    var form = field.form;

    // The route enforces this too - a client-side check only exists so the
    // reviewer finds out before waiting for an upload, never instead of the
    // server's own ceiling.
    var MAX_BYTES = 5 * 1024 * 1024;

    function clear() {
        field.value = '';
        input.value = '';
        if (thumb) thumb.removeAttribute('src');
        if (nameEl) nameEl.textContent = '';
        if (chip) chip.hidden = true;
    }

    function attach(file) {
        if (!file) return;
        if (file.size > MAX_BYTES) {
            if (nameEl) nameEl.textContent = 'That photo is too large (5MB limit).';
            if (chip) chip.hidden = false;
            field.value = '';
            return;
        }
        var reader = new FileReader();
        reader.onload = function () {
            field.value = String(reader.result || '');
            if (thumb) thumb.src = field.value;
            if (nameEl) nameEl.textContent = file.name || 'Photo';
            if (chip) chip.hidden = false;
        };
        reader.readAsDataURL(file);
    }

    input.addEventListener('change', function () {
        var files = input.files;
        if (files && files.length) attach(files[0]);
    });

    if (clearBtn) clearBtn.addEventListener('click', clear);

    if (form) {
        // Cleared on submit, not on response: a photo that has already been
        // sent must never ride along silently with the NEXT message. The
        // field is read synchronously by the form post before this fires.
        form.addEventListener('submit', function () {
            window.setTimeout(clear, 0);
        });
    }
})();
