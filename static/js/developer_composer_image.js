/* CLAUDE-DEVELOPER-COMPOSER-IMAGE-01: screenshots into the Developer Composer.

   Two doors, because the Product Owner reached for the one that did not exist:
   a real Ctrl/Cmd+V paste (what a screenshot workflow actually is), and the +
   picker (what a phone offers). Both end at the same hidden field, so the
   server sees one wire format either way.

   DELIBERATELY NOT composer_attach.js. That module is 533 lines bound to the
   workspace Composer's own ids and carries Make-Q, Add-to-Q and the capture
   crop/review flow - project-evidence machinery that has no meaning here, since
   Developer Mode has no project and files nothing. Generalizing it would have
   meant reworking a load-bearing path for a surface that needs a fraction of
   it.

   What IS shared is the part that must be: window.ArchioskPrepareImage, the one
   place the byte/edge boundary is applied. Its own comment says both doors into
   the same vision capability must normalize identically "otherwise a camera
   photo succeeds or fails solely because of which Composer surface happened to
   receive it" - and that now includes this one. It is defined on every page
   (before composer_attach.js's own early return), so nothing new is loaded to
   get it. */
(function () {
    var input = document.getElementById('developer-home-composer-image');
    var field = document.getElementById('developer-home-composer-image-data');
    var chip = document.getElementById('developer-home-composer-image-chip');
    var thumb = document.getElementById('developer-home-composer-image-thumb');
    var nameEl = document.getElementById('developer-home-composer-image-name');
    var clearBtn = document.getElementById('developer-home-composer-image-clear');
    var messageBox = document.querySelector('.developer-home-composer-form [data-developer-composer-input]');
    if (!input || !field) return;

    var form = field.closest('form');

    function show(name, dataUrl) {
        field.value = dataUrl;
        if (thumb) thumb.src = dataUrl;
        if (nameEl) nameEl.textContent = name || 'Screenshot';
        if (chip) chip.hidden = false;
    }

    function clear() {
        field.value = '';
        if (thumb) thumb.removeAttribute('src');
        if (nameEl) nameEl.textContent = '';
        if (chip) chip.hidden = true;
        try { input.value = ''; } catch (e) { /* older browsers */ }
    }

    function fail(message) {
        clear();
        // Said where the person is looking, not in a console they will never
        // open. Silently dropping a screenshot is the worst outcome here - it
        // looks like the paste worked.
        if (nameEl) {
            nameEl.textContent = message || 'That image could not be attached.';
            if (chip) chip.hidden = false;
        }
    }

    function accept(file) {
        if (!file) return;
        if (!window.ArchioskPrepareImage) {
            fail('Image support did not load - try reloading the page.');
            return;
        }
        window.ArchioskPrepareImage(file, show, fail);
    }

    input.addEventListener('change', function () {
        accept(input.files && input.files[0]);
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', function () { clear(); });
    }

    // The paste path. Bound to the textarea rather than the document so a paste
    // meant for some other field on Home can never be swallowed by the
    // Composer. Only ever preventDefault when an image is genuinely taken -
    // pasting ordinary text must keep working exactly as before.
    if (messageBox) {
        messageBox.addEventListener('paste', function (event) {
            var data = event.clipboardData;
            if (!data) return;
            var items = data.items || [];
            for (var i = 0; i < items.length; i += 1) {
                if (items[i].kind === 'file' && String(items[i].type).indexOf('image/') === 0) {
                    var file = items[i].getAsFile();
                    if (file) {
                        event.preventDefault();
                        accept(file);
                        return;
                    }
                }
            }
        });
    }

    // A screenshot is a complete turn on its own, so the shared keyboard
    // primitive's "no text means do not submit" rule would strand it. Enter is
    // allowed through whenever an image is attached; the server supplies a
    // neutral question when the message is empty.
    if (form && messageBox) {
        messageBox.addEventListener('keydown', function (event) {
            if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
            if (messageBox.value.trim() || !field.value) return;
            event.preventDefault();
            if (typeof form.requestSubmit === 'function') form.requestSubmit();
            else form.submit();
        }, true);

        // Never resend the same screenshot with the next question.
        form.addEventListener('submit', function () {
            window.setTimeout(clear, 0);
        });
    }
})();
