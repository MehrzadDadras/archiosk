/*
 * CLAUDE-P40-DTAB1 - Preview, Pinned, Colored, Renamed, and Hidden
 * Document Display Tabs.
 *
 * Architecture, stated honestly: this is a full-page-reload application
 * (routes/workspace.py's own show_workspace, no client-side router) -
 * activating a tab is therefore a REAL navigation (a plain <a href=
 * "?source=<id>">), never client-side routing invented for this stage.
 * Stable URLs, direct links, and browser Back/Forward all keep working
 * exactly as they already did, for free. Tab metadata (pinned/hidden/
 * alias/color) is a pure client-side workspace preference - localStorage
 * (pinned/hidden, survives reload) and sessionStorage (the one
 * replaceable preview tab, Section 4's own "not persisted across
 * sessions unless converted to pinned"), keyed by BOTH the current
 * username and the current Project id, so switching accounts or
 * Projects never exposes another workspace's tabs (Section 11's own
 * "must not leak tab names or Document identities to another account").
 * Every persisted entry is revalidated on every load against
 * #workspace-active-sources-data - the SAME authorized, Project-scoped
 * JSON island static/js/case_workspace.js's own populateDivision
 * already reads - so a stale, removed, or unauthorized Document can
 * never be exposed through restored tab metadata (Section 5's own
 * explicit requirement); nothing here calls fetch()/XMLHttpRequest.
 */
(function () {
    'use strict';

    var strip = document.getElementById('document-tab-strip');
    if (!strip) return;
    var list = document.getElementById('document-tab-list');
    var overflowDetails = document.getElementById('document-tabs-overflow');
    var overflowPanel = document.getElementById('document-tabs-overflow-panel');
    if (!list || !overflowDetails || !overflowPanel) return;

    var projectId = strip.getAttribute('data-project-id') || '';
    var selectedSourceId = strip.getAttribute('data-selected-source-id') || '';
    var baseUrl = strip.getAttribute('data-base-url') || window.location.pathname;

    // CLAUDE-P40-DTAB1, Section 11: username-scoped, not just Project-
    // scoped - localStorage is shared across every account that ever
    // signs into this browser profile; without this segment, Account
    // B would see Account A's own tab names/aliases the moment they
    // logged in, exactly the leakage Section 11 forbids. No real
    // username at all (shouldn't happen on an authenticated Workspace
    // page, but degrade honestly rather than throw) falls back to a
    // fixed anonymous bucket, matching this app's own "never crash on
    // a missing precondition" convention elsewhere.
    var usernameEl = document.querySelector('.workspace-user-name');
    var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
    var PINNED_KEY = 'beehive:tabs:pinned:' + username + ':' + projectId;
    var PREVIEW_KEY = 'beehive:tabs:preview:' + username + ':' + projectId;

    var COLORS = ['gold', 'turquoise', 'lapis', 'terracotta', 'green', 'purple'];

    function readActiveSources() {
        var el = document.getElementById('workspace-active-sources-data');
        if (!el) return [];
        try {
            var parsed = JSON.parse(el.textContent || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function loadPinned() {
        try {
            var raw = window.localStorage.getItem(PINNED_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function savePinned(entries) {
        try { window.localStorage.setItem(PINNED_KEY, JSON.stringify(entries)); } catch (e) { /* ignore */ }
    }

    function loadPreview() {
        try {
            var raw = window.sessionStorage.getItem(PREVIEW_KEY);
            var parsed = raw ? JSON.parse(raw) : null;
            return parsed && parsed.id ? parsed : null;
        } catch (e) {
            return null;
        }
    }

    function savePreview(id) {
        try {
            if (id) window.sessionStorage.setItem(PREVIEW_KEY, JSON.stringify({ id: id }));
            else window.sessionStorage.removeItem(PREVIEW_KEY);
        } catch (e) { /* ignore */ }
    }

    function navigateTo(sourceId) {
        window.location.href = baseUrl + '?source=' + encodeURIComponent(sourceId);
    }

    function navigateToEmpty() {
        window.location.href = baseUrl;
    }

    // -------- Reconciliation (Section 5, 11: revalidate on every load) --
    var activeSources = readActiveSources();
    var activeById = {};
    activeSources.forEach(function (s) { activeById[s.id] = s; });

    var pinned = loadPinned().filter(function (entry) { return !!activeById[entry.id]; });
    var pinnedDropped = loadPinned().length !== pinned.length;
    var preview = loadPreview();
    if (preview && !activeById[preview.id]) { preview = null; }

    function findPinned(sourceId) {
        for (var i = 0; i < pinned.length; i++) { if (pinned[i].id === sourceId) return pinned[i]; }
        return null;
    }

    // Section 4/5: a real ?source= selection reconciles into either the
    // existing pinned tab it matches (no preview change - "pinned tabs
    // are never replaced by preview navigation") or the ONE replaceable
    // preview slot (Section 4's own "selecting another unopened Document
    // by single click replaces the current preview tab").
    if (selectedSourceId && activeById[selectedSourceId]) {
        var existingPinned = findPinned(selectedSourceId);
        if (existingPinned) {
            existingPinned.lastActiveAt = Date.now();
        } else {
            preview = { id: selectedSourceId };
        }
    }
    savePreview(preview ? preview.id : null);
    if (pinnedDropped || (selectedSourceId && findPinned(selectedSourceId))) savePinned(pinned);

    // -------- Rendering --------------------------------------------------
    var activeMenu = null;
    function closeActiveMenu() {
        if (activeMenu && activeMenu.parentNode) activeMenu.parentNode.removeChild(activeMenu);
        activeMenu = null;
    }

    function labelFor(entry, source) {
        var alias = entry && entry.alias;
        return alias || source.name;
    }

    function buildTabEl(entry, source, isPreview) {
        var a = document.createElement('a');
        a.className = 'document-tab' + (isPreview ? ' document-tab-preview' : '');
        a.href = baseUrl + '?source=' + encodeURIComponent(source.id);
        a.setAttribute('role', 'tab');
        a.setAttribute('data-source-id', source.id);
        var isActive = source.id === selectedSourceId;
        a.setAttribute('aria-selected', String(isActive));
        a.setAttribute('tabindex', isActive ? '0' : '-1');
        if (entry && entry.color) a.setAttribute('data-tab-color', entry.color);
        var alias = entry && entry.alias;
        var displayName = labelFor(entry, source);
        var accessibleName = alias ? (alias + ', originally ' + source.name) : source.name;
        if (isPreview) accessibleName = accessibleName + ' (preview)';
        a.setAttribute('aria-label', accessibleName);
        if (alias) a.title = 'Original name: ' + source.name;

        var labelSpan = document.createElement('span');
        labelSpan.className = 'document-tab-label';
        labelSpan.textContent = displayName;
        labelSpan.setAttribute('aria-hidden', 'true');
        a.appendChild(labelSpan);

        var menuBtn = document.createElement('button');
        menuBtn.type = 'button';
        menuBtn.className = 'document-tab-menu-btn';
        menuBtn.setAttribute('aria-label', 'Tab options for ' + source.name);
        menuBtn.setAttribute('aria-haspopup', 'true');
        menuBtn.textContent = '⋯';
        menuBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openTabMenu(source, entry, isPreview, menuBtn);
        });
        a.appendChild(menuBtn);

        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'document-tab-close';
        closeBtn.setAttribute('aria-label', 'Close ' + source.name);
        closeBtn.textContent = '×';
        closeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            closeTab(source.id, isPreview);
        });
        a.appendChild(closeBtn);

        a.addEventListener('dblclick', function (e) {
            e.preventDefault();
            if (isPreview) pinTab(source.id);
        });
        a.addEventListener('click', function () { closeActiveMenu(); });
        a.addEventListener('keydown', function (e) { onTabKeydown(e, a); });

        return a;
    }

    function render() {
        closeActiveMenu();
        list.textContent = '';
        var visiblePinned = pinned.filter(function (e) { return !e.hidden; });
        var anyTabs = visiblePinned.length > 0 || !!preview;

        visiblePinned.forEach(function (entry) {
            var source = activeById[entry.id];
            if (!source) return;
            list.appendChild(buildTabEl(entry, source, false));
        });
        if (preview && !findPinned(preview.id)) {
            var previewSource = activeById[preview.id];
            if (previewSource) list.appendChild(buildTabEl(null, previewSource, true));
        }

        renderOverflowPanel();
        strip.hidden = !anyTabs;
        syncKeepOpenButtons();
    }

    // -------- ADDENDUM (DOCUMENT-ROW CONTROL ORDER / MARK VS KEEP): the
    // rail's own "Keep this document open" triangle - a direct per-row
    // path to the SAME pinTab()/findPinned() mechanism above (previously
    // reachable only from inside the tab strip itself, via double-click
    // or the "Keep Open" tab-menu item), not a second tab system. Synced
    // from render() itself so it can never drift from the real pinned
    // set regardless of which action last mutated it.
    var keepOpenButtons = document.querySelectorAll('.keep-open-btn');
    function syncKeepOpenButtons() {
        Array.prototype.forEach.call(keepOpenButtons, function (btn) {
            btn.setAttribute('aria-pressed', String(!!findPinned(btn.getAttribute('data-source-id'))));
        });
    }
    Array.prototype.forEach.call(keepOpenButtons, function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            pinTab(btn.getAttribute('data-source-id'));
        });
    });

    function renderOverflowPanel() {
        overflowPanel.textContent = '';
        var hiddenEntries = pinned.filter(function (e) { return e.hidden; });

        var closeOthersBtn = document.createElement('button');
        closeOthersBtn.type = 'button';
        closeOthersBtn.className = 'document-tab-menu-item';
        closeOthersBtn.textContent = 'Close All Tabs';
        closeOthersBtn.disabled = pinned.length === 0 && !preview;
        closeOthersBtn.addEventListener('click', function () {
            overflowDetails.open = false;
            closeAllTabs();
        });
        overflowPanel.appendChild(closeOthersBtn);

        if (hiddenEntries.length === 0) {
            var note = document.createElement('p');
            note.className = 'document-tabs-empty-note';
            note.textContent = 'No hidden tabs.';
            overflowPanel.appendChild(note);
            return;
        }

        var heading = document.createElement('p');
        heading.className = 'document-hidden-tabs-heading';
        heading.textContent = 'Hidden Tabs';
        overflowPanel.appendChild(heading);

        hiddenEntries.forEach(function (entry) {
            var source = activeById[entry.id];
            if (!source) return;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'document-hidden-tab-item';
            if (entry.color) {
                var swatch = document.createElement('span');
                swatch.className = 'document-tab-color-swatch';
                swatch.setAttribute('data-tab-color', entry.color);
                btn.appendChild(swatch);
            }
            var nameSpan = document.createElement('span');
            nameSpan.textContent = labelFor(entry, source);
            btn.appendChild(nameSpan);
            if (entry.alias) {
                var orig = document.createElement('span');
                orig.className = 'document-hidden-tab-item-original-name';
                orig.textContent = '(' + source.name + ')';
                btn.appendChild(orig);
            }
            btn.setAttribute('aria-label', 'Restore hidden tab ' + labelFor(entry, source));
            btn.addEventListener('click', function () {
                overflowDetails.open = false;
                unhideTab(source.id);
            });
            overflowPanel.appendChild(btn);
        });
    }

    // -------- Actions (Section 5/7/8/9/10) --------------------------------
    function pinTab(sourceId) {
        var entry = findPinned(sourceId);
        if (!entry) {
            entry = { id: sourceId, alias: null, color: null, hidden: false, pinnedAt: Date.now(), lastActiveAt: Date.now() };
            pinned.push(entry);
        } else {
            entry.hidden = false;
        }
        if (preview && preview.id === sourceId) { preview = null; savePreview(null); }
        savePinned(pinned);
        render();
    }

    function normalizedAlias(raw) {
        return (raw || '').trim();
    }

    function aliasInUse(alias, excludingId) {
        var lower = alias.toLowerCase();
        return pinned.some(function (e) {
            return e.id !== excludingId && e.alias && e.alias.trim().toLowerCase() === lower;
        });
    }

    // Returns an error message string, or null on success - Section 7's
    // own "empty or whitespace-only aliases are invalid" and "prevent or
    // clearly disambiguate duplicate aliases" are both real, rejecting
    // validation failures rather than silently coercing them.
    function renameTab(sourceId, rawAlias) {
        var alias = normalizedAlias(rawAlias);
        if (!alias) return 'A tab name cannot be empty.';
        if (aliasInUse(alias, sourceId)) return 'Another open tab already uses that name.';
        if (!findPinned(sourceId)) pinTab(sourceId);
        var entry = findPinned(sourceId);
        entry.alias = alias;
        savePinned(pinned);
        render();
        return null;
    }

    function restoreOriginalName(sourceId) {
        var entry = findPinned(sourceId);
        if (!entry) return;
        entry.alias = null;
        savePinned(pinned);
        render();
    }

    function setTabColor(sourceId, color) {
        if (!findPinned(sourceId)) pinTab(sourceId);
        var entry = findPinned(sourceId);
        entry.color = color || null;
        savePinned(pinned);
        render();
    }

    function mostRecentVisibleFallback(excludingId) {
        var candidates = pinned.filter(function (e) { return !e.hidden && e.id !== excludingId && activeById[e.id]; });
        candidates.sort(function (a, b) { return (b.lastActiveAt || 0) - (a.lastActiveAt || 0); });
        return candidates.length ? candidates[0].id : null;
    }

    // Section 9: "if the active tab is hidden, activate the most
    // recently used visible tab, otherwise a preview, otherwise a clear
    // empty Display state."
    //
    // CLAUDE-P40-VW8 (Governed Display Tab System, Section 4's "Closing
    // the active tab selects a deterministic neighboring or previously
    // active tab"): a fourth, final fallback added ahead of the empty
    // state - an attended Investigation, via investigation_attention.js's
    // own window.ArchioskInvestigationAttention.mostRecentAttended (see
    // that file's own comment on this exact addition). This app has TWO
    // real dynamic-record tab strips (Documents, Investigations); closing
    // the active Document tab with no other Document tab or preview open
    // used to go straight to the empty Display state even when a
    // perfectly good attended Investigation was sitting right there in
    // the Attention strip - this makes "closing the active tab" coherent
    // across the WHOLE governed system, not just within one strip.
    // Guarded (typeof check) since investigation_attention.js's own
    // early-return (no #attention-strip element - e.g. panel_only iframe
    // content) means window.ArchioskInvestigationAttention is not always
    // defined; degrades to the pre-existing empty-state behavior exactly
    // as before whenever that's the case, never throws.
    function activateFallback(excludingId) {
        var fallback = mostRecentVisibleFallback(excludingId);
        if (fallback) { navigateTo(fallback); return; }
        if (preview && preview.id !== excludingId && activeById[preview.id]) { navigateTo(preview.id); return; }
        if (window.ArchioskInvestigationAttention && typeof window.ArchioskInvestigationAttention.mostRecentAttended === 'function') {
            var attendedFallback = window.ArchioskInvestigationAttention.mostRecentAttended(null);
            if (attendedFallback) {
                window.location.href = baseUrl + '?case=' + encodeURIComponent(attendedFallback);
                return;
            }
        }
        navigateToEmpty();
    }

    function hideTab(sourceId) {
        var entry = findPinned(sourceId);
        if (!entry) return;
        entry.hidden = true;
        savePinned(pinned);
        if (sourceId === selectedSourceId) { activateFallback(sourceId); return; }
        render();
    }

    function unhideTab(sourceId) {
        var entry = findPinned(sourceId);
        if (!entry) return;
        entry.hidden = false;
        savePinned(pinned);
        navigateTo(sourceId);
    }

    // Section 10: closing removes only workspace tab state, never the
    // Document itself - no request is ever sent to the server for this.
    function closeTab(sourceId, isPreview) {
        var wasActive = sourceId === selectedSourceId;
        if (isPreview || (preview && preview.id === sourceId)) { preview = null; savePreview(null); }
        var idx = -1;
        for (var i = 0; i < pinned.length; i++) { if (pinned[i].id === sourceId) { idx = i; break; } }
        if (idx !== -1) { pinned.splice(idx, 1); savePinned(pinned); }
        if (wasActive) { activateFallback(sourceId); return; }
        render();
    }

    function closeOthers(sourceId) {
        var keep = findPinned(sourceId);
        pinned = keep ? [keep] : [];
        if (preview && preview.id !== sourceId) { preview = null; savePreview(null); }
        savePinned(pinned);
        if (selectedSourceId && selectedSourceId !== sourceId && !findPinned(selectedSourceId) && (!preview || preview.id !== selectedSourceId)) {
            activateFallback(selectedSourceId);
            return;
        }
        render();
    }

    function closeAllTabs() {
        var hadActive = !!(findPinned(selectedSourceId) || (preview && preview.id === selectedSourceId));
        pinned = [];
        preview = null;
        savePinned(pinned);
        savePreview(null);
        if (hadActive) { navigateToEmpty(); return; }
        render();
    }

    // -------- Rename input (Section 7) - a real inline <input>, never a
    // native browser input dialog, matching this app's own established
    // "no native browser dialogs for real input" convention (see e.g.
    // Eye's own openTextAnnotationInput). ---------------------------
    function openRenameInput(source, tabEl) {
        closeActiveMenu();
        var existing = tabEl.querySelector('.document-tab-rename-input');
        if (existing) return;
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'document-tab-rename-input';
        input.value = '';
        input.placeholder = source.name;
        input.setAttribute('aria-label', 'Rename tab for ' + source.name);
        var labelSpan = tabEl.querySelector('.document-tab-label');
        tabEl.insertBefore(input, labelSpan);
        input.focus();
        function commit() {
            var value = input.value;
            if (input.parentNode) input.parentNode.removeChild(input);
            if (value != null && value.trim()) {
                var err = renameTab(source.id, value);
                if (err) window.setTimeout(function () { window.alert(err); }, 0);
            }
        }
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); commit(); }
            else if (e.key === 'Escape') { e.preventDefault(); input.value = ''; if (input.parentNode) input.parentNode.removeChild(input); }
            e.stopPropagation();
        });
        input.addEventListener('blur', commit);
        input.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); });
    }

    // -------- Per-tab menu (Section 10) - only state-applicable actions -
    function openTabMenu(source, entry, isPreview, anchorEl) {
        closeActiveMenu();
        var menu = document.createElement('div');
        menu.className = 'document-tab-menu';
        menu.setAttribute('role', 'menu');
        menu.setAttribute('aria-label', 'Tab options for ' + source.name);

        function addItem(labelText, onClick) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'document-tab-menu-item';
            btn.setAttribute('role', 'menuitem');
            btn.textContent = labelText;
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                closeActiveMenu();
                onClick();
            });
            menu.appendChild(btn);
            return btn;
        }
        function addDivider() {
            var div = document.createElement('div');
            div.className = 'document-tab-menu-divider';
            menu.appendChild(div);
        }

        var tabEl = anchorEl.closest ? anchorEl.closest('.document-tab') : null;

        if (isPreview) {
            addItem('Keep Open', function () { pinTab(source.id); });
        }
        addItem('Rename Tab', function () { if (tabEl) openRenameInput(source, tabEl); });
        if (entry && entry.alias) {
            addItem('Restore Original Name', function () { restoreOriginalName(source.id); });
        }
        addItem('Show Original Document Name', function () { window.alert(source.name); });
        addDivider();

        COLORS.forEach(function (color) {
            var item = addItem(color.charAt(0).toUpperCase() + color.slice(1), function () { setTabColor(source.id, color); });
            item.classList.add('document-tab-color-option');
            var swatch = document.createElement('span');
            swatch.className = 'document-tab-color-swatch';
            swatch.setAttribute('data-tab-color', color);
            item.insertBefore(swatch, item.firstChild);
        });
        if (entry && entry.color) {
            addItem('Default Color', function () { setTabColor(source.id, null); });
        }
        addDivider();

        if (!isPreview) {
            addItem('Hide Tab', function () { hideTab(source.id); });
        }
        addItem('Close', function () { closeTab(source.id, isPreview); });
        if (pinned.length > 1 || (pinned.length >= 1 && preview)) {
            addItem('Close Others', function () { closeOthers(source.id); });
        }

        document.body.appendChild(menu);
        var rect = anchorEl.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.top = rect.bottom + 'px';
        menu.style.left = Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8) + 'px';
        activeMenu = menu;
    }

    document.addEventListener('mousedown', function (e) {
        if (activeMenu && !activeMenu.contains(e.target)) closeActiveMenu();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && activeMenu) closeActiveMenu();
    });

    // -------- Keyboard tab semantics (Section 12) - roving tabindex,
    // Left/Right/Home/End, Enter/Space activation (native <a> already
    // activates on Enter; Space is added explicitly since browsers don't
    // do that for anchors by default). --------------------------------
    function onTabKeydown(e, tabEl) {
        var tabs = Array.prototype.slice.call(list.querySelectorAll('.document-tab'));
        var idx = tabs.indexOf(tabEl);
        if (idx === -1) return;
        function focusIndex(i) {
            tabs.forEach(function (t) { t.setAttribute('tabindex', '-1'); });
            var next = tabs[(i + tabs.length) % tabs.length];
            next.setAttribute('tabindex', '0');
            next.focus();
        }
        if (e.key === 'ArrowRight') { focusIndex(idx + 1); e.preventDefault(); }
        else if (e.key === 'ArrowLeft') { focusIndex(idx - 1); e.preventDefault(); }
        else if (e.key === 'Home') { focusIndex(0); e.preventDefault(); }
        else if (e.key === 'End') { focusIndex(tabs.length - 1); e.preventDefault(); }
        else if (e.key === ' ') { e.preventDefault(); tabEl.click(); }
    }

    render();

    // Exposed for pdf_viewer.js (Section 6: per-tab viewer state) - a
    // read-only lookup, never a second write path for tab metadata.
    window.ArchioskDocumentTabs = {
        isPinned: function (sourceId) { return !!findPinned(sourceId); }
    };
})();
