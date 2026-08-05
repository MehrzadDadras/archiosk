/*
 * CLAUDE-P40-VW9A (Files Cockpit Close-Out, Part A1) - the Design-
 * Builder Workspace's per-folder-row "..." action menus
 * (.files-folder-actions, templates/case_workspace.html) as an
 * exclusive group with click-outside and Escape dismissal.
 *
 * Deliberately NOT a rebuild of document_tabs.js's own JS-built,
 * body-appended .document-tab-menu (that menu holds only plain
 * <button>s; these hold real <form>s posting to rename/move/delete -
 * reconstructing them as synthetic body-level nodes would mean
 * reimplementing form submission semantics for no reason). Each menu
 * stays exactly what it already is - a native <details>/<summary> -
 * so keyboard activation (Enter/Space on the summary), native
 * open/close, and screen-reader semantics are the browser's own, never
 * degraded. Only two behaviors are ADDED, adapting document_tabs.js's
 * own document-level "mousedown outside closes the open menu" /
 * "Escape closes the open menu" pattern (see that file's own listeners
 * near its end) from its synthetic menu to these native ones:
 * exclusivity (opening one closes any other) and outside-dismissal.
 *
 * Full-page-reload architecture (document_tabs.js's own opening
 * comment): folder rows are fixed at page-load time, so a single
 * querySelectorAll here is correct - no MutationObserver needed.
 */
(function () {
    'use strict';

    var menus = Array.prototype.slice.call(document.querySelectorAll('.files-folder-actions'));
    if (!menus.length) return;

    menus.forEach(function (menu) {
        menu.addEventListener('toggle', function () {
            if (!menu.open) return;
            menus.forEach(function (other) {
                if (other !== menu && other.open) other.open = false;
            });
        });
    });

    document.addEventListener('mousedown', function (e) {
        menus.forEach(function (menu) {
            if (menu.open && !menu.contains(e.target)) menu.open = false;
        });
    });

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        menus.forEach(function (menu) {
            if (!menu.open) return;
            menu.open = false;
            var summary = menu.querySelector('summary');
            if (summary) summary.focus();
        });
    });
})();
