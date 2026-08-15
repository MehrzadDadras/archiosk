/*
 * CLAUDE-DOCUMENT-RAIL-PROBE-EYE-TOOL-01, Part 3/4: PM Mark - a
 * lightweight, per-reviewer "this document interests me, keep it on my
 * review shortlist" flag, client-side only (localStorage, the SAME
 * username+Project scoping document_tabs.js's own PINNED_KEY already
 * establishes, for the identical cross-account-leakage reason - see
 * that file's own comment). It does not mean open in Main, open in
 * Eye, create a tab, archive, remove, or mutate project evidence -
 * marking many Documents while continuing to probe others must stay
 * cheap, reversible, and independent of every other row control.
 *
 * The Marked filter (Part 4) is a pure client-side row show/hide - no
 * navigation, no server round-trip, no separate panel - so it can sit
 * beside RAIL-SEARCH-01's own upcoming search field without either
 * needing to know about the other's internals.
 */
(function () {
    'use strict';

    var checkboxes = document.querySelectorAll('.pm-mark-checkbox');
    var filterBtn = document.getElementById('documents-marked-filter-btn');
    if (!checkboxes.length && !filterBtn) return;

    var stripEl = document.getElementById('document-tab-strip');
    var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
    var usernameEl = document.querySelector('.workspace-user-name');
    var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
    var MARKS_KEY = 'beehive:marks:' + username + ':' + projectId;
    var FILTER_KEY = 'beehive:marks-filter-active:' + username + ':' + projectId;

    // The SAME authorized, Project-scoped JSON island document_tabs.js's
    // own reconciliation already reads - never a second, separately-
    // trusted source of truth about which Sources currently exist.
    function activeSourceIds() {
        var el = document.getElementById('workspace-active-sources-data');
        if (!el) return null;
        try {
            var parsed = JSON.parse(el.textContent || '[]');
            var ids = {};
            (Array.isArray(parsed) ? parsed : []).forEach(function (s) { ids[s.id] = true; });
            return ids;
        } catch (e) {
            return null;
        }
    }

    function loadMarks() {
        try {
            var raw = window.localStorage.getItem(MARKS_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function saveMarks(ids) {
        try { window.localStorage.setItem(MARKS_KEY, JSON.stringify(ids)); } catch (e) { /* ignore */ }
    }

    // Same "revalidate on every load" precedent as document_tabs.js's
    // own pinned-tab reconciliation - a mark on a removed/foreign Source
    // can never silently persist past this load.
    var known = activeSourceIds();
    var marks = loadMarks();
    if (known) {
        var reconciled = marks.filter(function (id) { return known[id]; });
        if (reconciled.length !== marks.length) {
            marks = reconciled;
            saveMarks(marks);
        }
    }
    var markedSet = {};
    marks.forEach(function (id) { markedSet[id] = true; });

    function isMarked(id) { return !!markedSet[id]; }

    function setMarked(id, next) {
        if (next) { markedSet[id] = true; } else { delete markedSet[id]; }
        saveMarks(Object.keys(markedSet));
    }

    function syncCheckboxes() {
        Array.prototype.forEach.call(checkboxes, function (cb) {
            cb.checked = isMarked(cb.getAttribute('data-source-id'));
        });
    }
    syncCheckboxes();

    // -------- Marked filter (Part 4) -------------------------------------
    var filterActive = false;
    try { filterActive = window.localStorage.getItem(FILTER_KEY) === 'true'; } catch (e) { filterActive = false; }

    function applyFilter() {
        Array.prototype.forEach.call(checkboxes, function (cb) {
            var row = cb.closest('.tree-node-document');
            if (!row) return;
            row.hidden = filterActive && !isMarked(cb.getAttribute('data-source-id'));
        });
    }

    function setFilterActive(next) {
        filterActive = next;
        try { window.localStorage.setItem(FILTER_KEY, next ? 'true' : 'false'); } catch (e) { /* ignore */ }
        if (filterBtn) filterBtn.setAttribute('aria-pressed', String(next));
        applyFilter();
    }

    Array.prototype.forEach.call(checkboxes, function (cb) {
        // Never let a checkbox click bubble into the row's own name-
        // link/eye/tool controls - marking is deliberately independent
        // of every other row action.
        cb.addEventListener('click', function (e) { e.stopPropagation(); });
        cb.addEventListener('change', function () {
            setMarked(cb.getAttribute('data-source-id'), cb.checked);
            applyFilter();
        });
    });

    if (filterBtn) {
        filterBtn.setAttribute('aria-pressed', String(filterActive));
        filterBtn.addEventListener('click', function () { setFilterActive(!filterActive); });
    }
    applyFilter();

    // Exposed for RAIL-SEARCH-01's own upcoming "Marked + search
    // coexist" requirement - a read-only lookup, never a second write
    // path for mark state.
    window.ArchioskDocumentMarks = { isMarked: isMarked, isFilterActive: function () { return filterActive; } };
})();
