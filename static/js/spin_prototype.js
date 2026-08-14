/*
 * CLAUDE-SPIN-00A - Spin container comparison prototype.
 *
 * Pure client-side prototype state. No fetch/XHR anywhere in this file -
 * every toggle, "All ON"/"All OFF"/"Return to Baseline", and the dev-only
 * A/B/C switcher only ever mutates the DOM already rendered by
 * templates/_spin_prototype.html. Nothing here persists across a reload,
 * nothing here calls a route, nothing here touches real project data -
 * see that template's own header comment for the full scope boundary.
 *
 * Each of the three .spin-variant containers gets its own independent
 * state (initSpinVariant, called once per container) - they are NOT
 * synchronized with each other, since the Product Owner compares them
 * one at a time via the dev switcher below, not simultaneously.
 */
(function () {
    'use strict';

    var switcher = document.querySelector('.spin-variant-switcher');
    if (!switcher) return;

    var variants = document.querySelectorAll('.spin-variant');

    // -- dev-only A/B/C switcher (removable wholesale with this file) ----
    var switchButtons = switcher.querySelectorAll('[data-spin-switch]');
    switchButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var target = btn.getAttribute('data-spin-switch');
            switchButtons.forEach(function (b) {
                b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
            });
            variants.forEach(function (variantEl) {
                variantEl.hidden = variantEl.getAttribute('data-spin-variant') !== target;
            });
        });
    });

    // -- per-variant prototype state --------------------------------------
    function initSpinVariant(root) {
        var variant = root.getAttribute('data-spin-variant');
        var rows = Array.prototype.slice.call(root.querySelectorAll('[data-spin-toggle]')).map(function (btn) {
            return btn.closest('[data-spin-id]');
        });
        var statusEl = root.querySelector('[data-spin-status]');
        var summaryEl = root.querySelector('[data-spin-summary]');
        var sequenceEl = root.querySelector('[data-spin-sequence]');
        var engagedOrder = []; // ordered list of data-spin-id values, in engagement order

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

            if (sequenceEl) {
                var ordered = engagedOrder
                    .map(function (id) { return rows.filter(function (r) { return r.getAttribute('data-spin-id') === id; })[0]; })
                    .filter(function (r) { return r && isEngaged(r); });
                sequenceEl.textContent = ordered.length
                    ? ordered.map(function (r) { return r.getAttribute('data-spin-name'); }).join(' → ')
                    : 'None engaged';
            }

            // Variant C: per-row sequence index (blank until engaged, then
            // its 1-based position in engagedOrder).
            if (variant === 'c') {
                rows.forEach(function (row) {
                    var indexEl = row.querySelector('[data-spin-index]');
                    if (!indexEl) return;
                    var id = row.getAttribute('data-spin-id');
                    var pos = engagedOrder.indexOf(id);
                    indexEl.textContent = pos === -1 ? '–' : String(pos + 1);
                });
            }

            // Variant B: rows physically move between the Engaged / Not
            // Engaged sub-lists, rather than only being recolored in place -
            // the grouping itself is the point of this alternative.
            if (variant === 'b') {
                var engagedList = root.querySelector('[data-spin-list="engaged"]');
                var disengagedList = root.querySelector('[data-spin-list="disengaged"]');
                var emptyNote = engagedList ? engagedList.querySelector('[data-spin-empty-note]') : null;
                if (engagedList && disengagedList) {
                    rows.forEach(function (row) {
                        var destination = isEngaged(row) ? engagedList : disengagedList;
                        if (row.parentElement !== destination) destination.appendChild(row);
                    });
                    if (emptyNote) emptyNote.hidden = engaged.length > 0;
                }
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
                    // separately-labeled controls per the comparison brief
                    // even though they currently do the same thing, since
                    // the Product Owner is evaluating both as distinct
                    // affordances, not just their effect.
                    rows.forEach(function (row) { setRowState(row, false); });
                    engagedOrder.length = 0;
                }
                render();
            });
        });

        render();
    }

    variants.forEach(initSpinVariant);
})();
