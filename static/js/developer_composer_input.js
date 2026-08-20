/* Shared Developer Composer keyboard behavior for Home and Workspace.
   Enter submits the real form; Shift+Enter remains a newline; composition
   events (IME) never trigger an accidental submission. */
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
            var send = form.querySelector('[data-ui-ref="chat.composer.send"], [data-ui-ref="developer.home.composer.send"]');
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
