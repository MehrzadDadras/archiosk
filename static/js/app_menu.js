/*
 * CLAUDE-APP-MENU-01: the application menu bar (Archiosk | File | Edit |
 * View | Document | Tools | Window | Help) - very top-left, above the
 * working surfaces (templates/base.html's own new .workspace-menubar).
 *
 * Deliberately NOT a second implementation of any command: every item is
 * either a real <a href> to an existing route, or a plain button that
 * either (a) clicks an existing control by id (data-reuse-control) so it
 * inherits that control's own enabled/disabled state and click behavior
 * verbatim, or (b) performs one of a small, named set of real actions
 * (data-action) that open/scroll to an existing panel or call an already-
 * exposed function on another module's own public object
 * (window.ArchioskDocumentTabs, etc.). No parallel state machine.
 *
 * Also supplies the one generic behavior none of the pre-existing topbar
 * <details> popups (Display Layout/Appearance/Account/Project Context)
 * had before this stage - native <details> does neither on its own:
 * Escape closes the deepest open menu, opening one closes every other
 * one that isn't its own ancestor, and an outside click closes whatever
 * is open. Scoped to .workspace-topbar so Toolbox's own unrelated
 * <details> accordions are never touched.
 */
(function () {
    'use strict';

    var topbar = document.querySelector('.workspace-topbar');
    if (!topbar) return;

    // -------- Generic popup-menu behavior (Section 14) -------------------
    function allMenus() {
        return Array.prototype.slice.call(topbar.querySelectorAll('details'));
    }

    function closeOthers(current) {
        allMenus().forEach(function (d) {
            if (d === current) return;
            if (d.contains(current) || current.contains(d)) return;
            d.open = false;
        });
    }

    topbar.addEventListener('toggle', function (e) {
        var target = e.target;
        if (!target || target.tagName !== 'DETAILS') return;
        if (target.open) closeOthers(target);
        // CLAUDE-MENU-DEBOXING-01: native <details>/<summary> never sets
        // aria-expanded on its own - .workspace-topbar-btn[aria-expanded=
        // "true"] (main.css) was dead CSS, matching nothing, so "this
        // menu is currently open" had no real visual signal at all
        // beyond a fleeting :hover. Setting it here, on every toggle
        // (including the programmatic ones closeOthers() triggers, which
        // themselves dispatch a real 'toggle' event) makes that state
        // genuine rather than decorative-only.
        var summary = target.querySelector(':scope > summary');
        if (summary) summary.setAttribute('aria-expanded', String(target.open));
    }, true);

    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        var open = allMenus().filter(function (d) { return d.open; });
        if (!open.length) return;
        // Back out one level at a time - close the DEEPEST open menu
        // first (a real desktop-menu convention), never everything at
        // once.
        var deepest = open[0];
        open.forEach(function (d) { if (deepest.contains(d)) deepest = d; });
        deepest.open = false;
        var summary = deepest.querySelector(':scope > summary');
        if (summary) summary.focus();
    });

    document.addEventListener('click', function (e) {
        allMenus().forEach(function (d) {
            if (d.open && !d.contains(e.target)) d.open = false;
        });
    });

    // -------- Context-sensitive availability (Icon Intelligence / menu
    // intelligence, Section 13) - re-derived from the real underlying
    // control every time any topbar menu opens, never a second flag that
    // could drift out of sync with it. --------------------------------
    function syncMenuState() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-reuse-control]'), function (item) {
            var real = document.getElementById(item.getAttribute('data-reuse-control'));
            var available = !!real && !real.disabled && real.offsetParent !== null;
            item.disabled = !available;
            if (real && real.hasAttribute('aria-pressed')) {
                item.setAttribute('aria-pressed', real.getAttribute('aria-pressed'));
            }
        });

        var closeDocBtn = document.querySelector('[data-action="close-active-tab"]');
        if (closeDocBtn) {
            closeDocBtn.disabled = !document.querySelector('.document-tab[aria-selected="true"]');
        }
        var closeAllBtn = document.querySelector('[data-action="close-all-tabs"]');
        if (closeAllBtn) {
            closeAllBtn.disabled = !(window.ArchioskDocumentTabs && window.ArchioskDocumentTabs.hasAnyTabs && window.ArchioskDocumentTabs.hasAnyTabs());
        }
        var hiddenTabsBtn = document.querySelector('[data-action="open-hidden-tabs"]');
        if (hiddenTabsBtn) {
            hiddenTabsBtn.disabled = !document.getElementById('document-tabs-overflow');
        }
    }

    topbar.addEventListener('toggle', function (e) {
        if (e.target && e.target.tagName === 'DETAILS' && e.target.open) syncMenuState();
    }, true);
    syncMenuState();

    // -------- data-reuse-control: click the real control -----------------
    Array.prototype.forEach.call(document.querySelectorAll('[data-reuse-control]'), function (item) {
        item.addEventListener('click', function () {
            var real = document.getElementById(item.getAttribute('data-reuse-control'));
            if (real && !real.disabled) real.click();
        });
    });

    // -------- data-action: named real actions -----------------------------
    function byRef(ref) { return document.querySelector('[data-ui-ref="' + ref + '"]'); }

    function openAndScroll(el) {
        if (!el) return;
        if (el.tagName === 'DETAILS') el.open = true;
        else if (el.hasAttribute('hidden')) el.hidden = false;
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        if (typeof el.focus === 'function') el.focus({ preventScroll: true });
    }

    var actions = {
        // CLAUDE-WINDOW-MENU-01: Window > Panels > Search. A data-action rather
        // than a data-reuse-control because that mechanism calls real.click(),
        // and clicking a text input does not reliably move focus - the menu
        // item would appear to work and visibly do nothing. openAndScroll()
        // focuses, which is the behaviour this item promises.
        'focus-document-search': function () {
            openAndScroll(document.getElementById('doc-search-input'));
        },

        'close-active-tab': function () {
            var activeTab = document.querySelector('.document-tab[aria-selected="true"]');
            var closeBtn = activeTab && activeTab.querySelector('.document-tab-close');
            if (closeBtn) closeBtn.click();
        },
        'open-publish-panel': function () { openAndScroll(byRef('toolbox.project-admin.publish')); },
        'open-document-context': function () { openAndScroll(byRef('display.document.context')); },
        'open-admin-document-understanding': function () { openAndScroll(byRef('display.document.admin-qac')); },
        'open-hidden-tabs': function () { openAndScroll(document.getElementById('document-tabs-overflow')); },
        'close-all-tabs': function () {
            if (window.ArchioskDocumentTabs && window.ArchioskDocumentTabs.closeAllTabs) {
                window.ArchioskDocumentTabs.closeAllTabs();
            }
        },
        'toggle-fullscreen': function () {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else if (document.documentElement.requestFullscreen) {
                document.documentElement.requestFullscreen();
            }
        },
        'open-keyboard-shortcuts': function () {
            var panel = document.getElementById('app-menu-keyboard-shortcuts');
            if (panel) openAndScroll(panel);
        }
    };

    Array.prototype.forEach.call(document.querySelectorAll('[data-action]'), function (item) {
        item.addEventListener('click', function () {
            var fn = actions[item.getAttribute('data-action')];
            if (fn) fn();
        });
    });

    // Fullscreen's own checked state - re-derived from the real browser
    // event, never inferred from the click alone (Escape/F11 can exit
    // fullscreen outside this control entirely).
    document.addEventListener('fullscreenchange', function () {
        var btn = document.querySelector('[data-action="toggle-fullscreen"]');
        if (btn) btn.setAttribute('aria-pressed', String(!!document.fullscreenElement));
    });

    // -------- Departure (Exit / Sign out): the closest truthful "close
    // the application" this browser architecture supports is ending the
    // authenticated session - the SAME /logout route both menu.archiosk.
    // exit and menu.account.sign-out point at (see each link's own
    // unchanged href), never two logout implementations. CLAUDE-UI-
    // ACTION-REDUNDANCY-REVIEW-01, Disposition 4: these were previously
    // two routes to the identical action with INCONSISTENT unsaved-work
    // protection (only Exit was guarded) - guardDeparture() below is now
    // the one canonical safe-departure mechanism, wired to every menu
    // location that remains justified, so which link a reviewer happens
    // to click never changes the safety behavior. Guards with a plain
    // native confirm() ONLY when a real, detectable in-progress edit
    // exists - there is no server-side draft object here for a governed
    // dialog to protect, since this app writes on submit, not on a
    // "Save" verb. -----------------------------
    function hasUnsavedInput() {
        var composer = document.getElementById('dock-composer-input');
        if (composer && composer.value && composer.value.trim()) return true;
        if (document.querySelector('.document-tab-rename-input')) return true;
        var activeTool = document.querySelector('.doc-annotation-tool[aria-pressed="true"]');
        if (activeTool && activeTool.id !== 'doc-annotate-select') return true;
        return false;
    }

    function guardDeparture(link) {
        if (!link) return;
        link.addEventListener('click', function (e) {
            if (hasUnsavedInput() && !window.confirm(
                'You have unsaved input (a message being typed, a tab rename in progress, or an active drawing tool). '
                + 'Exit ARCHIOSK and discard it?'
            )) {
                e.preventDefault();
            }
        });
    }

    // -------- Open Project: plain client-side text filter over the
    // already-authorized, already-rendered rows only (CLAUDE-POST-SIGNIN-
    // GATEWAY-SIMPLIFICATION-01, Addendum G) - never a second fetch/
    // authorization check, and never touches which rows exist, only
    // which are hidden. ---------------------------------------------
    var openProjectSearch = document.querySelector('.workspace-open-project-search');
    if (openProjectSearch) {
        openProjectSearch.addEventListener('input', function () {
            var needle = openProjectSearch.value.trim().toLowerCase();
            Array.prototype.forEach.call(document.querySelectorAll('.workspace-open-project-item'), function (item) {
                var visible = !needle || item.textContent.toLowerCase().indexOf(needle) !== -1;
                item.closest('li').hidden = !visible;
            });
        });
    }

    guardDeparture(byRef('menu.archiosk.exit'));
    guardDeparture(byRef('menu.account.sign-out'));
    // Gateway's own separate Account-menu Sign out (templates/
    // gateway_shell.html, gateway.account.sign-out - a different ref
    // namespace, same reason gateway.account itself already differs
    // from menu.account: a genuinely different template/shell). Harmless
    // no-op on any page without this ref; on Gateway itself
    // hasUnsavedInput() always reads false (no Composer/tab-rename/
    // annotation DOM exists there), so this never surfaces a spurious
    // confirm() - it exists purely for consistency, so which departure
    // link a reviewer clicks never matters.
    guardDeparture(byRef('gateway.account.sign-out'));
})();
