/*
 * CLAUDE-SPIN-01 - Spin's selected canonical container grammar.
 * CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 (Part I) - compact grammar
 * correction: no more per-row ON/OFF toggle or All-ON/All-OFF/Return-to-
 * Baseline button trio. Each row now carries a compact selection circle
 * (data-spin-selector) meaning "included in the next Spin" - purely local
 * selection state, changing it never by itself updates the status strip.
 * Only the single top SPIN button (data-spin-action="spin") commits the
 * current selection as the active/engaged set. An "All" row
 * (data-spin-all-toggle) is a convenience that selects/deselects every
 * discipline row at once - same "control that applies an existing state,
 * never a state of its own" idiom as base.html's own Appearance-menu "All"
 * row, kept in sync (checked only when every row already agrees).
 *
 * Findings boxes (data-spin-findings) are deliberately never written to
 * by this file - this prototype layer has no real investigation to
 * report, so fabricating "[N]"/"[0]" here would violate the "never show
 * what isn't real" rule. They stay in their honest, permanently-blank
 * "[ ]" state; a future layer that actually runs an investigation is the
 * only thing that should ever populate them.
 *
 * Pure client-side prototype state. No fetch/XHR anywhere in this file -
 * nothing here persists across a reload, nothing here calls a route,
 * nothing here touches real project data - see the template's own header
 * comment for the full scope boundary.
 */
(function () {
    'use strict';

    var statusStrip = document.querySelector('.spin-status-strip');
    if (!statusStrip) return;

    var root = statusStrip.closest('.workspace-pane') || document;
    var rows = Array.prototype.slice.call(root.querySelectorAll('[data-spin-id]'));
    var allToggle = root.querySelector('[data-spin-all-toggle]');
    var spinTrigger = root.querySelector('[data-spin-action="spin"]');
    var statusEl = root.querySelector('[data-spin-status]');
    var summaryEl = root.querySelector('[data-spin-summary]');
    var selectionOrder = []; // ordered list of data-spin-id values, in selection order - unsurfaced

    function isSelected(row) {
        return row.getAttribute('data-selected') === 'true';
    }

    function selectedRows() {
        return rows.filter(isSelected);
    }

    function setRowSelected(row, selected) {
        var selector = row.querySelector('[data-spin-selector]');
        selector.setAttribute('aria-pressed', selected ? 'true' : 'false');
        row.setAttribute('data-selected', selected ? 'true' : 'false');

        var id = row.getAttribute('data-spin-id');
        var pos = selectionOrder.indexOf(id);
        if (selected && pos === -1) {
            selectionOrder.push(id);
        } else if (!selected && pos !== -1) {
            selectionOrder.splice(pos, 1);
        }
    }

    function syncAllToggle() {
        if (!allToggle) return;
        var allSelected = rows.length > 0 && rows.every(isSelected);
        allToggle.setAttribute('aria-pressed', allSelected ? 'true' : 'false');
    }

    function wireDisclosure(toggleBtn, detail) {
        if (!toggleBtn || !detail) return;
        toggleBtn.addEventListener('click', function () {
            var expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            toggleBtn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
            toggleBtn.textContent = expanded ? '+' : '−';
            detail.hidden = expanded;
        });
    }

    rows.forEach(function (row) {
        var selector = row.querySelector('[data-spin-selector]');
        selector.addEventListener('click', function () {
            // Selecting/deselecting a row is local state only - never
            // updates the status strip and never runs anything; only the
            // SPIN button below commits a selection.
            setRowSelected(row, selector.getAttribute('aria-pressed') !== 'true');
            syncAllToggle();
        });
        wireDisclosure(row.querySelector('[data-spin-disclosure]'), row.nextElementSibling);
    });

    var allRow = root.querySelector('[data-spin-all-row]');
    if (allRow) {
        wireDisclosure(allRow.querySelector('[data-spin-disclosure]'), allRow.nextElementSibling);
    }

    if (allToggle) {
        allToggle.addEventListener('click', function () {
            var makeSelected = allToggle.getAttribute('aria-pressed') !== 'true';
            rows.forEach(function (row) { setRowSelected(row, makeSelected); });
            syncAllToggle();
        });
    }

    if (spinTrigger) {
        spinTrigger.addEventListener('click', function () {
            var selected = selectedRows();
            var active = selected.length > 0;

            if (statusEl) {
                statusEl.textContent = active ? 'Spin Active' : 'Baseline';
                statusEl.classList.toggle('review-state-baseline', !active);
                statusEl.classList.toggle('review-state-spin-active', active);
            }

            if (summaryEl) {
                summaryEl.textContent = active
                    ? selected.map(function (r) { return r.getAttribute('data-spin-name'); }).join(' + ')
                    : 'None engaged';
            }

            // Findings boxes are deliberately left untouched here - see
            // this file's own header comment.
        });
    }

    syncAllToggle();
})();
