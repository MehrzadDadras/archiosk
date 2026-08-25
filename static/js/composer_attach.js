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
 * CLAUDE-GO-COMPOSER-CAPTURE-02 — Product Owner, from an actual site photo:
 * "I took a photo by my phone and the message is: That photo is too large
 * (5MB limit)."
 *
 * Correct, and refusing was the wrong answer. A current phone camera produces
 * 3-12MB per frame as a matter of course, so the first real photo taken with
 * this feature hit the ceiling - which made the entry point to the application
 * fail on its own primary input.
 *
 * The ceiling itself is not ours to raise: 5MB is the vision API's own limit.
 * So the photo is resized before it is ever sent, which is what every
 * messaging application on the same phone does. This costs nothing in answer
 * quality - the vision model downsamples to roughly 1568px on the long edge
 * anyway, so anything beyond that is bytes spent to be thrown away, and
 * sending less also means a faster upload on site signal.
 */
(function () {
    'use strict';

    var input = document.getElementById('dock-composer-image');
    var field = document.getElementById('dock-composer-image-data');

    var chip = document.getElementById('dock-composer-image-chip');
    var thumb = document.getElementById('dock-composer-image-thumb');
    var nameEl = document.getElementById('dock-composer-image-name');
    var clearBtn = document.getElementById('dock-composer-image-clear');
    var form = field ? field.form : null;
    // CLAUDE-GO-COMPOSER-CAPTURE-03: the next step, made visible.
    var nextStep = document.getElementById('dock-composer-image-next');
    var makeQ = document.getElementById('dock-composer-make-q');
    // CLAUDE-MULTI-IMAGE-Q-01. Absent outside an open Q, deliberately.
    var addToQ = document.getElementById('dock-composer-add-to-q');
    var messageBox = document.getElementById('dock-composer-input');
    var originalPlaceholder = messageBox ? messageBox.getAttribute('placeholder') : null;
    var ATTACHED_PLACEHOLDER = 'Ask about this photo, or tap Make a new Q';

    // The route enforces this independently; this copy exists so a photo is
    // brought UNDER the limit here rather than rejected there.
    var MAX_BYTES = 5 * 1024 * 1024;
    // What the vision model actually uses. Larger buys no accuracy.
    var MAX_EDGE = 1568;
    // Tried in order until one fits. Even the first step usually lands a phone
    // photo around a few hundred KB, so the later ones are a safety net for
    // unusually large or unusually noisy frames rather than the normal path.
    var QUALITY_STEPS = [0.85, 0.7, 0.55, 0.4];

    function clear() {
        field.value = '';
        input.value = '';
        if (thumb) thumb.removeAttribute('src');
        if (nameEl) nameEl.textContent = '';
        if (chip) chip.hidden = true;
        if (nextStep) nextStep.hidden = true;
        // Restored the moment the photo goes, so the box never describes an
        // attachment that is no longer there.
        if (messageBox && originalPlaceholder !== null) {
            messageBox.setAttribute('placeholder', originalPlaceholder);
        }
    }

    function show(name, dataUrl) {
        field.value = dataUrl;
        if (thumb) thumb.src = dataUrl;
        if (nameEl) nameEl.textContent = name;
        if (chip) chip.hidden = false;
        if (nextStep) nextStep.hidden = false;
        if (messageBox) messageBox.setAttribute('placeholder', ATTACHED_PLACEHOLDER);
    }

    function fail(message) {
        field.value = '';
        if (nextStep) nextStep.hidden = true;
        if (thumb) thumb.removeAttribute('src');
        if (nameEl) nameEl.textContent = message;
        if (chip) chip.hidden = false;
    }

    function approximateBytes(dataUrl) {
        var comma = dataUrl.indexOf(',');
        if (comma < 0) return dataUrl.length;
        // base64 carries 3 bytes in every 4 characters.
        return Math.floor((dataUrl.length - comma - 1) * 3 / 4);
    }

    function attach(file) {
        window.ArchioskPrepareImage(file, function (name, dataUrl) {
            show(name, dataUrl);
        }, fail);
    }

    // Shared with Document Search's phone/gallery path.  Both doors into the
    // same vision capability must apply the same byte/edge boundary before a
    // request reaches the server; otherwise a camera photo succeeds or fails
    // solely because of which Composer surface happened to receive it.
    window.ArchioskPrepareImage = function (file, onReady, onFail) {
        if (!file) return;
        var reader = new FileReader();
        reader.onerror = function () {
            if (onFail) onFail('That photo could not be read.');
        };
        reader.onload = function () {
            var original = String(reader.result || '');
            var image = new Image();
            image.onerror = function () {
                if (onFail) onFail('That photo is in a format this browser cannot open.');
            };
            image.onload = function () {
                if (approximateBytes(original) <= MAX_BYTES
                    && Math.max(image.width, image.height) <= MAX_EDGE) {
                    if (onReady) onReady(file.name || 'Photo', original);
                    return;
                }
                var scale = Math.min(1, MAX_EDGE / Math.max(image.width, image.height));
                var canvas = document.createElement('canvas');
                canvas.width = Math.max(1, Math.round(image.width * scale));
                canvas.height = Math.max(1, Math.round(image.height * scale));
                var context = canvas.getContext('2d');
                if (!context) {
                    if (onFail) onFail('This browser could not prepare that photo.');
                    return;
                }
                context.drawImage(image, 0, 0, canvas.width, canvas.height);
                for (var i = 0; i < QUALITY_STEPS.length; i++) {
                    try {
                        var candidate = canvas.toDataURL('image/jpeg', QUALITY_STEPS[i]);
                        if (approximateBytes(candidate) <= MAX_BYTES) {
                            if (onReady) onReady(file.name || 'Photo', candidate);
                            return;
                        }
                    } catch (err) {
                        if (onFail) onFail('This browser could not prepare that photo.');
                        return;
                    }
                }
                if (onFail) onFail('That photo could not be reduced enough to send.');
            };
            image.src = original;
        };
        reader.readAsDataURL(file);
    };

    // The shared preparation helper is useful to other authenticated image
    // surfaces even when this page does not render the Composer attachment
    // control.  Only the Composer-specific wiring below requires its markup.
    if (!input || !field) return;

    input.addEventListener('change', function () {
        var files = input.files;
        if (files && files.length) attach(files[0]);
    });

    if (clearBtn) clearBtn.addEventListener('click', clear);

    function sendAs(phrase) {
        // Written into the box rather than posted behind the reviewer's back:
        // the phrase then appears in the conversation as their own message,
        // which is how they find out they could have typed it - and that they
        // may type something else instead.
        messageBox.value = phrase;
        if (form.requestSubmit) form.requestSubmit();
        else form.submit();
    }

    if (makeQ && form && messageBox) {
        makeQ.addEventListener('click', function () { sendAs('Make a new Q'); });
    }

    // CLAUDE-MULTI-IMAGE-Q-01: the second photo into the SAME Q. The phrase
    // matches routes/workspace.py's own _ADD_TO_Q_PHRASES, so the button and a
    // reviewer typing it by hand travel the identical path - the button is a
    // shortcut to words, never a second mechanism.
    if (addToQ && form && messageBox) {
        addToQ.addEventListener('click', function () { sendAs('Add this to this Q'); });
    }

    if (form) {
        // Cleared on submit, not on response: a photo that has already been
        // sent must never ride along silently with the next message. The
        // field is read synchronously by the form post before this fires.
        form.addEventListener('submit', function () {
            window.setTimeout(clear, 0);
        });
    }
})();
