/* CLAUDE-COMPOSER-DRAFT-ASSIST-01 — the pen beside the Composer.
 *
 * Product Owner: "I want to write naturally first, then let GO help sharpen the
 * language without changing my meaning or taking control away from me...
 * Do not silently overwrite the user's draft."
 *
 * THE ONE RULE THIS FILE EXISTS TO KEEP
 *
 * A proposal NEVER reaches the textarea on its own. It renders into its own
 * element beside the original, and exactly two lines in this file write to the
 * draft — both inside a click handler on a button the reviewer pressed. Search
 * for `box.value =` and you will find them; there are no others, and a test
 * asserts that count.
 *
 * WHY A COMPARISON RATHER THAN AN INLINE REWRITE
 *
 * The Product Owner asked to "compare the original with the proposed revision
 * before accepting anything". That is not a preference about layout — for RFI
 * and site-observation text it is the whole safety mechanism. A model that
 * quietly drops a qualification, or firms up a tentative observation, produces
 * prose that reads better and says something different. You can only catch that
 * by seeing both.
 *
 * CHECK AMBIGUITY IS NOT A REWRITE. The server marks such actions
 * `rewrites: false` and Replace is hidden entirely — pasting observations over
 * the draft would be nonsense, and offering the button would invite it.
 */
(function () {
    'use strict';

    var pen = document.getElementById('dock-composer-pen');
    var box = document.getElementById('dock-composer-input');
    if (!pen || !box) return;

    var sheet = document.getElementById('dock-composer-pen-sheet');
    var actions = document.getElementById('dock-composer-pen-actions');
    var status = document.getElementById('dock-composer-pen-status');
    var compare = document.getElementById('dock-composer-pen-compare');
    var originalEl = document.getElementById('dock-composer-pen-original');
    var proposalEl = document.getElementById('dock-composer-pen-proposal');
    var proposalTitle = document.getElementById('dock-composer-pen-proposal-title');
    var noteEl = document.getElementById('dock-composer-pen-note');
    var replaceBtn = document.getElementById('dock-composer-pen-replace');
    var insertBtn = document.getElementById('dock-composer-pen-insert');
    var discardBtn = document.getElementById('dock-composer-pen-discard');
    if (!sheet || !actions || !compare) return;

    var current = null;   // the proposal in view, or null
    var busy = false;

    // ── The pen appears and disappears with the draft ───────────────────────
    // Same discipline as the photo actions: a control with nothing to act on is
    // clutter, and on a phone it is clutter in the one band that matters.
    function syncPen() {
        var hasText = box.value.trim().length > 0;
        pen.hidden = !hasText;
        if (!hasText) closeSheet();
    }

    box.addEventListener('input', syncPen);
    syncPen();

    function closeSheet() {
        sheet.hidden = true;
        pen.setAttribute('aria-expanded', 'false');
        clearProposal();
    }

    function clearProposal() {
        current = null;
        compare.hidden = true;
        proposalEl.textContent = '';
        originalEl.textContent = '';
        noteEl.textContent = '';
        noteEl.hidden = true;
        status.textContent = '';
    }

    pen.addEventListener('click', function () {
        if (sheet.hidden) {
            sheet.hidden = false;
            pen.setAttribute('aria-expanded', 'true');
        } else {
            closeSheet();
        }
    });

    // ── Asking ──────────────────────────────────────────────────────────────
    actions.addEventListener('click', function (event) {
        var button = event.target.closest('[data-assist-action]');
        if (!button || busy) return;

        var draft = box.value.trim();
        if (!draft) return;

        busy = true;
        clearProposal();
        status.textContent = 'Working on ' + button.textContent.toLowerCase() + '…';

        var body = new URLSearchParams();
        body.set('draft', draft);
        body.set('action', button.getAttribute('data-assist-action'));

        var headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
        var token = document.querySelector('meta[name="csrf-token"]');
        if (token) headers['X-CSRFToken'] = token.getAttribute('content');

        fetch(pen.getAttribute('data-assist-url'), {
            method: 'POST', headers: headers, body: body.toString(),
            credentials: 'same-origin',
        }).then(function (response) {
            return response.json();
        }).then(function (data) {
            busy = false;
            if (!data || !data.ok) {
                // Always says the draft is untouched, because that is the thing
                // a reviewer will worry about when something goes wrong.
                status.textContent = (data && data.reason) || 'That did not work. Your draft is untouched.';
                return;
            }
            status.textContent = '';
            current = data;

            // The reviewer's own words, captured at the moment of asking, so the
            // comparison stays honest even if they keep typing afterwards.
            originalEl.textContent = draft;
            proposalEl.textContent = data.proposal;
            proposalTitle.textContent = data.rewrites ? 'Proposed' : data.label;

            if (data.note) {
                noteEl.textContent = data.note;
                noteEl.hidden = false;
            }

            // No Replace for an action that reports rather than revises.
            replaceBtn.hidden = !data.rewrites;
            insertBtn.hidden = false;
            compare.hidden = false;
        }).catch(function () {
            busy = false;
            status.textContent = 'That did not work. Your draft is untouched.';
        });
    });

    // ── Deciding — the only two places anything is written to the draft ─────
    replaceBtn.addEventListener('click', function () {
        if (!current || !current.rewrites) return;
        box.value = current.proposal;
        afterDecision();
    });

    insertBtn.addEventListener('click', function () {
        if (!current) return;
        // Appended below the reviewer's own text, never merged into it - so the
        // original survives verbatim and they can see both while editing.
        box.value = box.value.replace(/\s*$/, '') + '\n\n' + current.proposal;
        afterDecision();
    });

    discardBtn.addEventListener('click', function () {
        clearProposal();
    });

    function afterDecision() {
        closeSheet();
        syncPen();
        // The draft store listens for `input`; without this the change would not
        // survive a navigation, which would be a quiet way to lose accepted work.
        box.dispatchEvent(new Event('input', { bubbles: true }));
        box.focus();
    }

    // Escape closes the sheet and keeps the draft exactly as it was.
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !sheet.hidden) closeSheet();
    });
})();
