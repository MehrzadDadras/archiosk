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
    // CLAUDE-CAPTURE-REVIEW-01: the confirmation step. Absent on surfaces that
    // render no Composer attachment control, which is why every use below is
    // guarded rather than assumed.
    var review = document.getElementById('dock-capture-review');
    var reviewImage = document.getElementById('dock-capture-review-image');
    var reviewCropBox = document.getElementById('dock-capture-review-crop');
    var reviewHint = document.getElementById('dock-capture-review-hint');
    var reviewUse = document.getElementById('dock-capture-review-use');
    var reviewCropReset = document.getElementById('dock-capture-review-crop-reset');
    var reviewRetake = document.getElementById('dock-capture-review-retake');
    var reviewDiscard = document.getElementById('dock-capture-review-discard');
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

    /* ── CLAUDE-CAPTURE-REVIEW-01 ────────────────────────────────────────────
     *
     * Product Owner, from live phone use: the phone's own camera gives a review
     * moment - keep, crop, retake - and the Composer went straight from shutter
     * to attached. Discard and retake already existed here; what was missing was
     * a moment to LOOK before committing.
     *
     * THE ORDERING IS THE POINT, NOT THE UI
     *
     * Before this, ArchioskPrepareImage ran the instant a file was picked, so the
     * only image that ever existed to review was already downscaled to MAX_EDGE
     * and re-encoded. A crop added after that would have cropped into a
     * re-encode - and for construction review the detail that matters (a damper
     * label, a drawing stamp, a serial number) is exactly what that throws away.
     *
     * So the original File is held untouched, cropping works from the ORIGINAL
     * pixels, and normalization runs ONCE, at the end, on whatever the reviewer
     * actually chose. field.value stays empty until then: nothing is attached
     * until "Use photo".
     *
     * DELIBERATELY NOT INSIDE ArchioskPrepareImage. That helper is shared with
     * Image Search (document_marks.js); putting review there would give Image
     * Search a camera confirmation step it never asked for. The review lives in
     * the Composer's own attach path, and the helper is unchanged.
     *
     * A mobile capture confirmation, not an editor: crop only. Rotate is
     * DEFERRED by explicit Product Owner decision until the existing
     * EXIF/orientation behaviour is understood - absent rather than stubbed.
     */
    var pendingFile = null;     // the original, held unchanged
    var pendingUrl = null;      // object URL for the working preview
    var cropRect = null;        // {x, y, w, h} in natural pixels, or null

    function releasePreview() {
        if (pendingUrl) {
            window.URL.revokeObjectURL(pendingUrl);
            pendingUrl = null;
        }
    }

    function closeReview() {
        if (review) review.hidden = true;
        releasePreview();
        pendingFile = null;
        cropRect = null;
        if (reviewCropBox) reviewCropBox.hidden = true;
        if (reviewCropReset) reviewCropReset.hidden = true;
    }

    function openReview(file) {
        pendingFile = file;
        cropRect = null;
        releasePreview();
        pendingUrl = window.URL.createObjectURL(file);
        if (reviewImage) reviewImage.src = pendingUrl;
        if (reviewCropBox) reviewCropBox.hidden = true;
        if (reviewCropReset) reviewCropReset.hidden = true;
        if (reviewHint) reviewHint.textContent = 'Drag on the photo to crop.';
        if (review) review.hidden = false;
    }

    /* Crop by dragging a rectangle over the preview. Pointer events cover
     * touch, pen and mouse in one path rather than three. */
    function wireCrop() {
        if (!reviewImage || !reviewCropBox) return;
        var dragging = false;
        var startX = 0, startY = 0;

        function localPoint(event) {
            var rect = reviewImage.getBoundingClientRect();
            return {
                x: Math.min(Math.max(event.clientX - rect.left, 0), rect.width),
                y: Math.min(Math.max(event.clientY - rect.top, 0), rect.height),
                rect: rect,
            };
        }

        reviewImage.addEventListener('pointerdown', function (event) {
            dragging = true;
            var point = localPoint(event);
            startX = point.x;
            startY = point.y;
            reviewCropBox.hidden = false;
            reviewCropBox.style.left = startX + 'px';
            reviewCropBox.style.top = startY + 'px';
            reviewCropBox.style.width = '0px';
            reviewCropBox.style.height = '0px';
            event.preventDefault();
        });

        reviewImage.addEventListener('pointermove', function (event) {
            if (!dragging) return;
            var point = localPoint(event);
            reviewCropBox.style.left = Math.min(startX, point.x) + 'px';
            reviewCropBox.style.top = Math.min(startY, point.y) + 'px';
            reviewCropBox.style.width = Math.abs(point.x - startX) + 'px';
            reviewCropBox.style.height = Math.abs(point.y - startY) + 'px';
        });

        reviewImage.addEventListener('pointerup', function (event) {
            if (!dragging) return;
            dragging = false;
            var point = localPoint(event);
            var displayW = Math.abs(point.x - startX);
            var displayH = Math.abs(point.y - startY);

            // A tap is not a crop. Below this the reviewer was almost certainly
            // just touching the photo, and silently cropping to a few pixels
            // would be the worst possible reading of that.
            if (displayW < 12 || displayH < 12) {
                cropRect = null;
                reviewCropBox.hidden = true;
                if (reviewCropReset) reviewCropReset.hidden = true;
                return;
            }

            // Display coordinates -> natural pixels, so the crop applies to the
            // ORIGINAL resolution rather than to whatever size it happens to be
            // shown at on this screen.
            var scaleX = reviewImage.naturalWidth / point.rect.width;
            var scaleY = reviewImage.naturalHeight / point.rect.height;
            cropRect = {
                x: Math.round(Math.min(startX, point.x) * scaleX),
                y: Math.round(Math.min(startY, point.y) * scaleY),
                w: Math.round(displayW * scaleX),
                h: Math.round(displayH * scaleY),
            };
            if (reviewCropReset) reviewCropReset.hidden = false;
            if (reviewHint) reviewHint.textContent = 'Cropped. Use photo, or undo the crop.';
        });
    }
    wireCrop();

    if (reviewCropReset) {
        reviewCropReset.addEventListener('click', function () {
            cropRect = null;
            if (reviewCropBox) reviewCropBox.hidden = true;
            reviewCropReset.hidden = true;
            if (reviewHint) reviewHint.textContent = 'Drag on the photo to crop.';
        });
    }

    // Retake reopens the picker; Discard simply stops. Both leave NOTHING
    // behind - no field value, no chip, no held file, no input value - which is
    // what makes a second attempt a clean one.
    if (reviewRetake) {
        reviewRetake.addEventListener('click', function () {
            closeReview();
            clear();
            if (input) input.click();
        });
    }
    if (reviewDiscard) {
        reviewDiscard.addEventListener('click', function () {
            closeReview();
            clear();
        });
    }

    /* Produce the bytes to attach: the cropped region of the ORIGINAL, or the
     * original file itself when nothing was cropped.
     *
     * Uncropped is deliberately a pass-through of the File rather than a canvas
     * round trip - re-encoding an untouched photo would lose quality for
     * nothing, and ArchioskPrepareImage already leaves a small-enough image
     * completely alone. */
    function resolveChosenImage(callback, onFail) {
        if (!pendingFile) return;
        if (!cropRect) {
            callback(pendingFile);
            return;
        }
        var image = new Image();
        image.onerror = function () { onFail('That photo could not be cropped.'); };
        image.onload = function () {
            var canvas = document.createElement('canvas');
            canvas.width = Math.max(1, cropRect.w);
            canvas.height = Math.max(1, cropRect.h);
            var context = canvas.getContext('2d');
            context.drawImage(
                image, cropRect.x, cropRect.y, cropRect.w, cropRect.h,
                0, 0, canvas.width, canvas.height
            );
            canvas.toBlob(function (blob) {
                if (!blob) {
                    onFail('That photo could not be cropped.');
                    return;
                }
                // Named from the original so provenance in the conversation
                // still reads as the reviewer's own photo.
                var name = (pendingFile.name || 'Photo');
                callback(new File([blob], name, { type: blob.type || 'image/jpeg' }));
            }, 'image/jpeg', 0.92);
        };
        image.src = pendingUrl;
    }

    if (reviewUse) {
        reviewUse.addEventListener('click', function () {
            resolveChosenImage(function (chosen) {
                // ONLY NOW does normalization run, and only now is anything
                // attached. Everything before this point was a preview.
                window.ArchioskPrepareImage(chosen, function (name, dataUrl) {
                    closeReview();
                    show(name, dataUrl);
                }, function (message) {
                    closeReview();
                    fail(message);
                });
            }, function (message) {
                closeReview();
                fail(message);
            });
        });
    }

    function attach(file) {
        // The review step owns the Composer's capture path now. Where its
        // markup is absent (a surface with no review element), behaviour falls
        // back to what it was - prepare immediately - so nothing that reused
        // this file loses its attachment path.
        if (review && reviewImage) {
            openReview(file);
            return;
        }
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
