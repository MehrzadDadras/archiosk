/* Shared Composer keyboard behavior.
   Enter submits the real form; Shift+Enter remains a newline; composition
   events (IME) never trigger an accidental submission.

   Named for the Developer Composer it was first extracted from, but it has
   never been developer-only - the Workspace chat dock has always used it too.
   CLAUDE-ESTABLISH-COMPOSER-ENTER-01 adds the project-creation help composer,
   which is why the send-button selector below is now declared by the form
   instead of hardcoded here.

   Why a form opts in at all, rather than relying on the browser: implicit
   submission clicks the form's DEFAULT button - the FIRST submit button in
   tree order - which is silent, positional, and has already produced one live
   Product Owner defect in this codebase (CLAUDE-CA1D-COMPOSER-ENTER-FIX-01,
   18cac57: Enter reached a "clear context" button that had been added ahead of
   Send). Binding an explicit target makes Enter mean the one thing it should
   mean, and keeps meaning it when a button is added later. */
(function () {
    function bindComposer(form) {
        if (!form || form.dataset.developerKeyboardBound === 'true') return;
        var input = form.querySelector('[data-developer-composer-input]');
        if (!input) return;
        form.dataset.developerKeyboardBound = 'true';
        var submitting = false;
        var composing = false;
        input.addEventListener('compositionstart', function () { composing = true; });
        input.addEventListener('compositionend', function () { composing = false; });
        input.addEventListener('keydown', function (event) {
            if (event.key !== 'Enter' || event.shiftKey || event.isComposing || composing) return;
            if (!input.value.trim() || submitting) {
                event.preventDefault();
                return;
            }
            // A form may name its own send control; the two original refs stay
            // the default so existing callers are untouched.
            var sendSelector = form.getAttribute('data-composer-send')
                || '[data-ui-ref="chat.composer.send"], [data-ui-ref="developer.home.composer.send"]';
            var send = form.querySelector(sendSelector);
            if (!send || send.disabled) return;
            event.preventDefault();
            submitting = true;
            if (typeof form.requestSubmit === 'function') form.requestSubmit(send);
            else send.click();
        });
        form.addEventListener('submit', function (event) {
            if (!input.value.trim() || (submitting && event.defaultPrevented)) {
                event.preventDefault();
                submitting = false;
                return;
            }
            if (submitting) return;
            submitting = true;
        });
    }

    function bindAll() {
        document.querySelectorAll('[data-developer-composer-form]').forEach(bindComposer);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindAll);
    else bindAll();
})();

/* CLAUDE-MOBILE-CONTINUATION-01: declare the surface the composer is being used
   on, so the server can offer a continuation instead of half-answering.

   Set at submit time rather than on load, because a laptop window narrowed to a
   phone width mid-session is genuinely a phone-sized surface, and a value
   captured at page load would be stale. The 640px query is the SAME breakpoint
   main.css already uses - one definition of "phone", not a second one drifting
   alongside it.

   Empty means "capable": if this script never runs, the server sees no surface
   and answers normally. The boundary can only ever be reached deliberately,
   never by a failure to report. */
(function () {
    var field = document.getElementById('dock-composer-surface');
    if (!field) return;
    var form = field.closest('form');
    if (!form) return;
    form.addEventListener('submit', function () {
        var narrow = window.matchMedia && window.matchMedia('(max-width: 640px)').matches;
        field.value = narrow ? 'mobile' : '';
    });
})();
