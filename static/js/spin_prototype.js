/*
 * CLAUDE-SPIN-01 - Spin's selected canonical container grammar.
 *
 * Pure client-side prototype state. No fetch/XHR anywhere in this file -
 * every toggle and "All ON"/"All OFF"/"Return to Baseline" only ever
 * mutates the DOM already rendered by templates/_spin_prototype.html.
 * Nothing here persists across a reload, nothing here calls a route,
 * nothing here touches real project data - see that template's own header
 * comment for the full scope boundary.
 *
 * CLAUDE-SPIN-00A built three comparison alternatives with a dev-only
 * switcher; the Product Owner selected Alternative A (+ one incorporated
 * pairing from B - see the template's own header comment). This file was
 * simplified accordingly: no more variant switching, no more Engaged/
 * Not-Engaged row regrouping (Alternative B, not adopted), no more visible
 * per-row sequence index or "Sequence" summary (Alternative C, not
 * adopted). `engagedOrder` itself is kept - harmless, never rendered - per
 * the Product Owner's own explicit instruction to preserve the latent
 * engagement-order data without surfacing it in the UI.
 */
(function () {
    'use strict';

    var statusStrip = document.querySelector('.spin-status-strip');
    if (!statusStrip) return;

    var root = statusStrip.closest('.workspace-pane') || document;
    var rows = Array.prototype.slice.call(root.querySelectorAll('[data-spin-toggle]')).map(function (btn) {
        return btn.closest('[data-spin-id]');
    });
    var statusEl = root.querySelector('[data-spin-status]');
    var summaryEl = root.querySelector('[data-spin-summary]');
    var engagedOrder = []; // ordered list of data-spin-id values, in engagement order - unsurfaced

    function isEngaged(row) {
        return row.getAttribute('data-engaged') === 'true'
            || row.querySelector('[data-spin-toggle]').getAttribute('aria-pressed') === 'true';
    }

    function engagedRows() {
        return rows.filter(isEngaged);
    }

    function setRowState(row, engaged) {
        var toggle = row.querySelector('[data-spin-toggle]');
        toggle.setAttribute('aria-pressed', engaged ? 'true' : 'false');
        toggle.textContent = engaged ? 'ON' : 'OFF';
        row.setAttribute('data-engaged', engaged ? 'true' : 'false');

        var id = row.getAttribute('data-spin-id');
        var pos = engagedOrder.indexOf(id);
        if (engaged && pos === -1) {
            engagedOrder.push(id);
        } else if (!engaged && pos !== -1) {
            engagedOrder.splice(pos, 1);
        }
    }

    function render() {
        var engaged = engagedRows();
        var active = engaged.length > 0;

        if (statusEl) {
            statusEl.textContent = active ? 'Spin Active' : 'Baseline';
            statusEl.classList.toggle('review-state-baseline', !active);
            statusEl.classList.toggle('review-state-spin-active', active);
        }

        if (summaryEl) {
            summaryEl.textContent = active
                ? engaged.map(function (r) { return r.getAttribute('data-spin-name'); }).join(' + ')
                : 'None engaged';
        }
    }

    rows.forEach(function (row) {
        var toggle = row.querySelector('[data-spin-toggle]');
        toggle.addEventListener('click', function () {
            setRowState(row, toggle.getAttribute('aria-pressed') !== 'true');
            render();
        });
    });

    root.querySelectorAll('[data-spin-action]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var action = btn.getAttribute('data-spin-action');
            if (action === 'all-on') {
                rows.forEach(function (row) { setRowState(row, true); });
            } else {
                // "all-off" and "reset" (Return to Baseline) both fully
                // disengage every discipline - kept as two separate,
                // separately-labeled controls per the original comparison
                // brief even though they currently do the same thing.
                rows.forEach(function (row) { setRowState(row, false); });
                engagedOrder.length = 0;
            }
            render();
        });
    });

    render();
})();
