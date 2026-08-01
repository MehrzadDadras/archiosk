/*
 * Case Workspace accordion/focus behavior.
 *
 * Purely presentational: no domain logic, no server calls. Major sections
 * within each column (marked <details class="accordion-section"
 * data-accordion-group="..." data-accordion-id="...">) remember their last
 * open/closed state per project in localStorage, and opening one section
 * collapses its siblings within the same group so the active content stays
 * near the top of the column.
 */
document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('.case-workspace');
    if (!root) return;

    const projectId = root.dataset.projectId || 'default';
    const storageKey = (id) => `beehive:accordion:${projectId}:${id}`;

    const sections = Array.from(document.querySelectorAll('details.accordion-section'));

    // Restore remembered state first, before any listeners are attached,
    // so restoring one section's state can never trigger the sibling-
    // collapse logic below.
    sections.forEach((el) => {
        const id = el.dataset.accordionId;
        if (!id) return;
        const stored = window.localStorage.getItem(storageKey(id));
        if (stored === 'open') el.open = true;
        else if (stored === 'closed') el.open = false;
        // No stored preference yet -> leave the server-rendered default.
    });

    // A same-page anchor (e.g. "#governed-requirements") may target
    // content nested inside a collapsed section - open the whole
    // ancestor chain so the link actually reveals what it points to.
    if (window.location.hash) {
        const target = document.getElementById(window.location.hash.slice(1));
        if (target) {
            let ancestor = target.closest('details.accordion-section');
            while (ancestor) {
                ancestor.open = true;
                const id = ancestor.dataset.accordionId;
                if (id) window.localStorage.setItem(storageKey(id), 'open');
                ancestor = ancestor.parentElement ? ancestor.parentElement.closest('details.accordion-section') : null;
            }
            if (target.tagName === 'DETAILS') target.open = true;
        }
    }

    function setOpen(el, open) {
        el.open = open;
        const id = el.dataset.accordionId;
        if (id) window.localStorage.setItem(storageKey(id), open ? 'open' : 'closed');
    }

    sections.forEach((el) => {
        el.addEventListener('toggle', () => {
            const id = el.dataset.accordionId;
            const group = el.dataset.accordionGroup;
            if (id) window.localStorage.setItem(storageKey(id), el.open ? 'open' : 'closed');
            if (el.open && group) {
                sections.forEach((sibling) => {
                    if (sibling !== el && sibling.dataset.accordionGroup === group && sibling.open) {
                        setOpen(sibling, false);
                    }
                });
            }
        });
    });

    const collapseAllBtn = document.getElementById('collapse-all-btn');
    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', () => {
            sections.forEach((el) => setOpen(el, false));
        });
    }

    // CLAUDE-P13: navigation-membrane layer toggle - purely a client-side
    // class flip, same shape as launcher-hidden in base.html. The badges
    // themselves are already server-rendered (or absent, when there's
    // nothing to show); this only ever shows/hides what's already there.
    const riskLayerToggle = document.getElementById('layer-risk-toggle');
    if (riskLayerToggle) {
        const layerKey = 'beehive:layer:risk';
        const stored = window.localStorage.getItem(layerKey);
        if (stored === 'on') {
            document.documentElement.classList.add('layer-risk-active');
            riskLayerToggle.checked = true;
        }
        riskLayerToggle.addEventListener('change', () => {
            document.documentElement.classList.toggle('layer-risk-active', riskLayerToggle.checked);
            window.localStorage.setItem(layerKey, riskLayerToggle.checked ? 'on' : 'off');
        });
    }

    // CLAUDE-P38 (OBS-12): History summary/full toggle - identical
    // shape to the risk layer toggle above, own separate localStorage
    // key and CSS class so the two are independent.
    const historyFullToggle = document.getElementById('history-full-toggle');
    if (historyFullToggle) {
        const historyKey = 'beehive:history:full';
        const stored = window.localStorage.getItem(historyKey);
        if (stored === 'on') {
            document.documentElement.classList.add('history-full-active');
            historyFullToggle.checked = true;
        }
        historyFullToggle.addEventListener('change', () => {
            document.documentElement.classList.toggle('history-full-active', historyFullToggle.checked);
            window.localStorage.setItem(historyKey, historyFullToggle.checked ? 'on' : 'off');
        });
    }

    // CLAUDE-P40-E2B, Section C: Chat's continuous resize replaces the
    // old binary "show full history" checkbox entirely - a drag handle
    // (pointer events), keyboard resize (ArrowUp/ArrowDown/Home/End
    // when the handle is focused), and two discrete Compact/Expanded
    // presets as the keyboard-friendly alternative Section C itself
    // asks for. Height is a CSS custom property on .case-workspace
    // (--chat-height), read by grid-template-rows - one write point,
    // so the drag handle and the preset buttons never fight each other
    // or drift out of sync.
    (function setUpChatResize() {
        const grid = document.querySelector('.case-workspace');
        const handle = document.getElementById('conversation-dock-resize-handle');
        if (!grid || !handle) return;

        const MIN_HEIGHT = 120;
        const MAX_HEIGHT = 640;
        const COMPACT_HEIGHT = 220;
        const EXPANDED_HEIGHT = 520;
        const heightKey = `beehive:chat:height:${projectId}`;

        function clamp(px) {
            return Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, px));
        }

        function applyHeight(px, persist) {
            const clamped = clamp(px);
            grid.style.setProperty('--chat-height', `${clamped}px`);
            handle.setAttribute('aria-valuenow', String(clamped));
            if (persist !== false) {
                try { window.localStorage.setItem(heightKey, String(clamped)); } catch (e) { /* ignore */ }
            }
            return clamped;
        }

        // Restore a reviewer-specific height (never a Project-record
        // write - Section B's own "local/user preference state, not
        // ProjectWorkspace structural persistence" applies equally to
        // Chat's height) before anything else, so there is no flash of
        // the default size on a page that already has a saved one.
        let stored = null;
        try { stored = window.localStorage.getItem(heightKey); } catch (e) { /* ignore */ }
        applyHeight(stored ? parseInt(stored, 10) : COMPACT_HEIGHT, false);

        let dragStartY = null;
        let dragStartHeight = null;
        function onPointerMove(e) {
            if (dragStartY === null) return;
            // Dragging the handle UP grows Chat (moving the boundary
            // toward Display); dragging DOWN shrinks it - the delta is
            // inverted relative to plain pointer Y movement.
            applyHeight(dragStartHeight + (dragStartY - e.clientY));
        }
        function onPointerUp() {
            dragStartY = null;
            dragStartHeight = null;
            document.removeEventListener('pointermove', onPointerMove);
            document.removeEventListener('pointerup', onPointerUp);
        }
        handle.addEventListener('pointerdown', (e) => {
            dragStartY = e.clientY;
            dragStartHeight = parseInt(getComputedStyle(grid).getPropertyValue('--chat-height'), 10) || COMPACT_HEIGHT;
            document.addEventListener('pointermove', onPointerMove);
            document.addEventListener('pointerup', onPointerUp);
            e.preventDefault();
        });

        const KEY_STEP = 24;
        handle.addEventListener('keydown', (e) => {
            const current = parseInt(handle.getAttribute('aria-valuenow'), 10) || COMPACT_HEIGHT;
            if (e.key === 'ArrowUp') { applyHeight(current + KEY_STEP); e.preventDefault(); }
            else if (e.key === 'ArrowDown') { applyHeight(current - KEY_STEP); e.preventDefault(); }
            else if (e.key === 'Home') { applyHeight(MIN_HEIGHT); e.preventDefault(); }
            else if (e.key === 'End') { applyHeight(MAX_HEIGHT); e.preventDefault(); }
        });

        document.querySelectorAll('.conversation-preset-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const target = btn.dataset.conversationPreset === 'expanded' ? EXPANDED_HEIGHT : COMPACT_HEIGHT;
                const applied = applyHeight(target);
                document.querySelectorAll('.conversation-preset-btn').forEach((other) => {
                    other.setAttribute('aria-pressed', String(other === btn));
                });
                handle.focus();
            });
        });
    })();

    // CLAUDE-P40-E2B1: Toolbox hides/shows independently via a plain
    // class toggle on .case-workspace - never DOM removal, so every
    // form/draft/scroll position inside a hidden panel survives
    // untouched, and reopening needs no re-fetch. State is a
    // reviewer-specific, per-Project localStorage preference (never a
    // ProjectWorkspace write - collapsing a panel is pure viewing, not
    // a governed action), applied before first paint via the inline
    // script in case_workspace.html's own extra_head block. The
    // Launcher panel's own equivalent toggle now lives in base.html
    // (application-shell level, reviewer-wide not per-project) since
    // the panel itself moved there - see that template's own script.
    (function setUpPanelToggles() {
        const grid = document.querySelector('.case-workspace');
        if (!grid) return;
        const html = document.documentElement;

        [
            { key: 'toolbox', btnId: 'toolbox-toggle-btn', panelId: 'workspace-toolbox-panel', hiddenClass: 'toolbox-hidden', labelShow: 'Show Toolbox', labelHide: 'Hide Toolbox' },
        ].forEach((cfg) => {
            const btn = document.getElementById(cfg.btnId);
            const panel = document.getElementById(cfg.panelId);
            if (!btn || !panel) return;
            const prefKey = `beehive:panel:${cfg.key}:${projectId}`;

            function setHidden(hidden, persist) {
                html.classList.toggle(cfg.hiddenClass, hidden);
                btn.setAttribute('aria-expanded', String(!hidden));
                btn.setAttribute('aria-label', hidden ? cfg.labelShow : cfg.labelHide);
                if (persist !== false) {
                    try { window.localStorage.setItem(prefKey, hidden ? 'hidden' : 'shown'); } catch (e) { /* ignore */ }
                }
            }

            btn.setAttribute('aria-controls', cfg.panelId);
            // The inline before-paint script (case_workspace.html's own
            // extra_head block) already applied the stored preference
            // as a class on <html> (avoids a flash) - this just syncs
            // the button's own ARIA state to match what's already
            // rendered, without writing anything back.
            setHidden(html.classList.contains(cfg.hiddenClass), false);

            btn.addEventListener('click', () => {
                setHidden(!html.classList.contains(cfg.hiddenClass));
            });
        });

        // CLAUDE-P40-E2B1, Section G: on narrow screens Toolbox renders
        // as an overlay drawer (main.css's own max-width: 640px rules) -
        // Escape closes it if open. The Launcher panel's own equivalent
        // drawer/Escape handling now lives in base.html (it moved there
        // along with the panel itself).
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (window.matchMedia('(min-width: 641px)').matches) return;
            if (!html.classList.contains('toolbox-hidden')) {
                document.getElementById('toolbox-toggle-btn') && document.getElementById('toolbox-toggle-btn').click();
            }
        });
    })();

    // CLAUDE-P40-E2B, Section A: the Display Layout and overflow menus
    // are plain <details>/<summary> (native keyboard operability/focus
    // management for free) - the only thing added here is closing one
    // when a click lands outside it, the one behavior <details> does
    // not provide natively.
    document.querySelectorAll('.workspace-layout-menu, .workspace-topbar-overflow').forEach((menu) => {
        document.addEventListener('click', (e) => {
            if (menu.open && !menu.contains(e.target)) menu.open = false;
        });
    });

    // CLAUDE-P40-E2B, Section D: Display Layout + multi-division
    // viewing. Division 0 is always whatever the server rendered
    // (Investigation/Document/Project Home) - never closed, never
    // client-side-repopulated - and stays the one division Toolbox is
    // bound to (the ordinary ?source=/?case= query string). Divisions
    // 1-3 are client-side-only "also open alongside it" slots: each
    // loads its content from the SAME authorized workspace.source_file
    // route a normal ?source= view already uses (see
    // workspace-active-sources-data's own file_url, resolved server-
    // side via url_for), so a division can never render a Document
    // this reviewer/Project isn't already authorized for, and never a
    // removed one (active_sources only). "Opening several Documents"
    // is simultaneous viewing only - nothing here performs or implies
    // cross-document analysis.
    (function setUpDisplayLayout() {
        const divisionsRoot = document.getElementById('display-divisions');
        const dataScript = document.getElementById('workspace-active-sources-data');
        if (!divisionsRoot || !dataScript) return;

        let sourcesById = {};
        try {
            JSON.parse(dataScript.textContent || '[]').forEach((s) => { sourcesById[s.id] = s; });
        } catch (e) { /* ignore */ }

        const layoutKey = `beehive:display:layout:${projectId}`;
        const openDivisionsKey = `beehive:display:open:${projectId}`;

        function applyLayout(layout, persist) {
            divisionsRoot.dataset.layout = layout;
            document.querySelectorAll('.workspace-layout-option').forEach((btn) => {
                btn.setAttribute('aria-pressed', String(btn.dataset.displayLayout === layout));
            });
            if (persist !== false) {
                try { window.localStorage.setItem(layoutKey, layout); } catch (e) { /* ignore */ }
            }
        }

        let storedLayout = null;
        try { storedLayout = window.localStorage.getItem(layoutKey); } catch (e) { /* ignore */ }
        applyLayout(storedLayout || 'single', false);

        document.querySelectorAll('.workspace-layout-option').forEach((btn) => {
            btn.addEventListener('click', () => {
                applyLayout(btn.dataset.displayLayout);
                const menu = document.getElementById('workspace-layout-menu');
                if (menu) menu.open = false;
            });
        });

        function saveOpenDivisions() {
            const open = [];
            [1, 2, 3].forEach((i) => {
                const division = document.getElementById(`display-division-${i}`);
                if (division && division.dataset.sourceId) open.push(division.dataset.sourceId);
            });
            try { window.sessionStorage.setItem(openDivisionsKey, JSON.stringify(open)); } catch (e) { /* ignore */ }
        }

        function promoteDivision(sourceId) {
            // Division 0 is about to become this Document (a real
            // navigation - the only honest way for Toolbox to follow
            // "the active division" in a server-rendered page) -
            // preserve every OTHER currently-open division across it.
            const open = [];
            [1, 2, 3].forEach((i) => {
                const division = document.getElementById(`display-division-${i}`);
                if (division && division.dataset.sourceId && division.dataset.sourceId !== sourceId) {
                    open.push(division.dataset.sourceId);
                }
            });
            try { window.sessionStorage.setItem(openDivisionsKey, JSON.stringify(open)); } catch (e) { /* ignore */ }
            const url = new URL(window.location.href);
            url.searchParams.set('source', sourceId);
            url.searchParams.delete('case');
            window.location.href = url.toString();
        }

        function clearDivision(divisionIndex) {
            const division = document.getElementById(`display-division-${divisionIndex}`);
            if (!division) return;
            division.classList.remove('display-division-populated', 'active');
            delete division.dataset.sourceId;
            const header = division.querySelector('.display-division-header');
            if (header) header.remove();
            const contentEl = division.querySelector('.display-division-content');
            if (contentEl) { contentEl.innerHTML = ''; contentEl.hidden = true; }
            const picker = division.querySelector('.display-division-picker');
            if (picker) picker.value = '';
            saveOpenDivisions();
        }

        function populateDivision(divisionIndex, sourceId, persist) {
            const division = document.getElementById(`display-division-${divisionIndex}`);
            const source = sourcesById[sourceId];
            if (!division || !source) return;

            let header = division.querySelector('.display-division-header');
            if (!header) {
                header = document.createElement('div');
                header.className = 'display-division-header';
                division.insertBefore(header, division.firstChild);
            }
            header.textContent = '';

            const nameEl = document.createElement('span');
            nameEl.className = 'display-division-header-name';
            nameEl.textContent = source.name;
            nameEl.tabIndex = 0;
            nameEl.setAttribute('role', 'button');
            nameEl.setAttribute('aria-label', `Make ${source.name} the active division`);
            nameEl.addEventListener('click', (e) => { e.stopPropagation(); promoteDivision(sourceId); });
            nameEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); promoteDivision(sourceId); }
            });

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'display-division-close';
            closeBtn.textContent = 'Close';
            closeBtn.setAttribute('aria-label', `Close ${source.name} - does not delete the Document`);
            closeBtn.addEventListener('click', (e) => { e.stopPropagation(); clearDivision(divisionIndex); });

            header.appendChild(nameEl);
            header.appendChild(closeBtn);

            const contentEl = division.querySelector('.display-division-content');
            contentEl.textContent = '';
            contentEl.hidden = false;
            if (source.kind === 'drawing') {
                const img = document.createElement('img');
                img.src = source.file_url;
                img.alt = source.name;
                contentEl.appendChild(img);
            } else {
                const frame = document.createElement('iframe');
                frame.src = source.file_url;
                frame.title = source.name;
                contentEl.appendChild(frame);
            }
            division.classList.add('display-division-populated');
            division.dataset.sourceId = sourceId;
            if (persist !== false) saveOpenDivisions();
        }

        document.querySelectorAll('.display-division-picker').forEach((picker) => {
            picker.addEventListener('change', () => {
                if (!picker.value) return;
                populateDivision(picker.dataset.divisionPicker, picker.value);
            });
        });

        // Division 0's own header name is also clickable/keyboard-
        // operable - it's already active, but still needs to identify
        // itself and accept focus like every other division's header.
        const primaryNameEl = document.querySelector('#display-division-0 .display-division-header-name');
        if (primaryNameEl) {
            primaryNameEl.tabIndex = 0;
            primaryNameEl.setAttribute('role', 'button');
            primaryNameEl.setAttribute('aria-label', `${primaryNameEl.textContent.trim()} (active division)`);
        }

        // "allow selection as the active division" (a plain visual
        // highlight for divisions 1-3 that aren't yet promoted; 0 is
        // always .active already) - separate from promoteDivision,
        // which is the only thing that actually changes what Toolbox
        // is bound to.
        divisionsRoot.querySelectorAll('.display-division').forEach((division) => {
            division.addEventListener('click', () => {
                divisionsRoot.querySelectorAll('.display-division').forEach((d) => d.classList.remove('active'));
                division.classList.add('active');
            });
        });

        // Restore whatever was open in divisions 1-3 before the last
        // navigation - a promotion (or any other navigation within
        // this Project) must not silently lose the rest of a split
        // view someone was actively using.
        let savedOpen = [];
        try { savedOpen = JSON.parse(window.sessionStorage.getItem(openDivisionsKey) || '[]'); } catch (e) { /* ignore */ }
        savedOpen.forEach((sourceId, idx) => {
            if (idx < 3 && sourcesById[sourceId]) populateDivision(idx + 1, sourceId, false);
        });
    })();

    // CLAUDE-P40-E, Section E: preserve an unfinished conversation-dock
    // draft (and the message list's own scroll position) across a
    // document/Case navigation - this app is server-rendered, not an
    // SPA, so every navigation is a full page load and nothing survives
    // it without deliberately saving/restoring client-side state.
    // sessionStorage (not localStorage) - a draft belongs to the
    // current browsing session, not forever, and clears itself once
    // the tab closes. Keyed by project_id (data-conversation-draft),
    // not by which of the two mutually exclusive composers is on
    // screen, so a draft started while a Case was open is still there
    // after navigating back to Project Home, and vice versa - "does not
    // change or close the document currently displayed" (Section F #1)
    // and "preserve chat draft and position" (Section G) both hinge on
    // this same continuity.
    const draftInput = document.querySelector('[data-conversation-draft]');
    if (draftInput) {
        const draftKey = `beehive:conversation:draft:${draftInput.dataset.conversationDraft}`;
        const savedDraft = window.sessionStorage.getItem(draftKey);
        if (savedDraft) draftInput.value = savedDraft;
        draftInput.addEventListener('input', () => {
            if (draftInput.value) window.sessionStorage.setItem(draftKey, draftInput.value);
            else window.sessionStorage.removeItem(draftKey);
        });
        draftInput.closest('form').addEventListener('submit', () => {
            window.sessionStorage.removeItem(draftKey);
        });
    }

    const conversationThread = document.querySelector('.conversation-thread[data-conversation-scope]');
    if (conversationThread) {
        const scrollKey = `beehive:conversation:scroll:${conversationThread.dataset.conversationScope}`;
        const savedScroll = window.sessionStorage.getItem(scrollKey);
        if (savedScroll) conversationThread.scrollTop = parseInt(savedScroll, 10) || 0;
        else conversationThread.scrollTop = conversationThread.scrollHeight;
        conversationThread.addEventListener('scroll', () => {
            window.sessionStorage.setItem(scrollKey, String(conversationThread.scrollTop));
        });
    }

    // CLAUDE-P40-E1: "Discuss this X" (macros.aperture) no longer
    // renders its own composer - it attaches an anchor to the ONE
    // dock composer instead. Only ever wired when that composer is
    // actually on screen (no active Case - the aperture macro is only
    // called from Project-Home-scoped content today); a Case-open page
    // simply has no aperture buttons to wire, not a broken feature.
    document.querySelectorAll('.aperture-link').forEach((button) => {
        button.addEventListener('click', () => {
            const anchorTypeField = document.getElementById('dock-composer-anchor-type');
            const anchorIdField = document.getElementById('dock-composer-anchor-id');
            const anchorDescriptionField = document.getElementById('dock-composer-anchor-description');
            const anchorLabel = document.getElementById('dock-composer-anchor-label');
            const composerInput = document.getElementById('dock-composer-input');
            if (!anchorTypeField || !anchorIdField || !composerInput) return;

            anchorTypeField.value = button.dataset.apertureAnchorType || '';
            anchorIdField.value = button.dataset.apertureAnchorId || '';
            anchorDescriptionField.value = button.dataset.apertureAnchorDescription || '';
            if (anchorLabel) {
                anchorLabel.textContent = `Re: ${button.dataset.apertureAnchorLabel || 'this'}`;
                anchorLabel.hidden = false;
            }
            composerInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
            composerInput.focus();
        });
    });
});
