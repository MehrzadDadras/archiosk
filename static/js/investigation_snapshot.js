/*
 * CLAUDE-POSTCAMEL-INVESTIGATION-AR1: the "Request Snapshot" widget for
 * the "Continue from Archive" chooser (case_workspace.html's own
 * show_continue_from_archive block). A plain, self-contained per-button
 * widget - same shape as static/js/document_structure_registration.js's
 * own mount(container) convention - not folded into case_workspace.js's
 * much larger multi-Display projection system, which this stage does
 * not touch.
 *
 * Read-only and ephemeral by design (Section 10 - "Snapshot assists
 * recall; it does not create authority"): this file only ever POSTs to
 * routes/workspace.py's snapshot_archived_case, renders the JSON result
 * into the row's own output element, and discards it on the next
 * request or page navigation - nothing here is written back to the
 * server, and no result is cached beyond the current page view.
 */
(function () {
    'use strict';

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function renderResult(outputEl, body) {
        outputEl.textContent = '';
        outputEl.hidden = false;

        if (!body || !body.ran) {
            var skipped = document.createElement('p');
            skipped.className = 'pane-note';
            skipped.textContent = 'Snapshot not available: ' + ((body && body.skipped_reason) || 'an error occurred.');
            outputEl.appendChild(skipped);
            return;
        }

        var label = document.createElement('p');
        label.className = 'pane-note';
        label.textContent = 'AI-generated orientation summary, grounded only in this Investigation’s own Findings and discussion — not itself verified evidence:';
        outputEl.appendChild(label);

        var summary = document.createElement('p');
        summary.textContent = body.summary || '';
        outputEl.appendChild(summary);

        if (body.grounded_in && body.grounded_in.length) {
            var groundedLabel = document.createElement('p');
            groundedLabel.className = 'pane-note';
            groundedLabel.textContent = 'Grounded in:';
            outputEl.appendChild(groundedLabel);
            var list = document.createElement('ul');
            list.className = 'source-list';
            body.grounded_in.forEach(function (item) {
                var li = document.createElement('li');
                li.className = 'source-item';
                li.textContent = item;
                list.appendChild(li);
            });
            outputEl.appendChild(list);
        }

        if (body.not_covered) {
            var notCovered = document.createElement('p');
            notCovered.className = 'pane-note';
            notCovered.textContent = 'Not covered: ' + body.not_covered;
            outputEl.appendChild(notCovered);
        }
    }

    function mount(button) {
        if (button.dataset.snapshotMounted === '1') return;
        button.dataset.snapshotMounted = '1';

        button.addEventListener('click', function () {
            var row = button.closest('[data-archive-case-id]');
            var outputEl = row ? row.querySelector('[data-snapshot-output]') : null;
            if (!outputEl) return;

            button.disabled = true;
            var originalText = button.textContent;
            button.textContent = 'Requesting Snapshot…';

            outputEl.hidden = false;
            outputEl.textContent = '';
            var pending = document.createElement('p');
            pending.className = 'pane-note';
            pending.textContent = 'Requesting Snapshot…';
            outputEl.appendChild(pending);

            fetch(button.getAttribute('data-snapshot-url'), {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrfToken() },
            }).then(function (resp) {
                return resp.json();
            }).then(function (body) {
                renderResult(outputEl, body);
            }).catch(function () {
                renderResult(outputEl, { ran: false, skipped_reason: 'A network error occurred.' });
            }).finally(function () {
                button.disabled = false;
                button.textContent = originalText;
            });
        });
    }

    function mountAll() {
        document.querySelectorAll('[data-snapshot-trigger]').forEach(mount);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', mountAll);
    } else {
        mountAll();
    }
})();
