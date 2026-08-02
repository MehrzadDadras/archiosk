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
    // CLAUDE-P40-E3A: .case-workspace is retired - Toolbox and Chat moved
    // out to base.html's own shell-level grid, so .workspace-pane-display
    // (Display alone) is the root or this whole Workspace page has none.
    const root = document.querySelector('.workspace-pane-display');
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
        // CLAUDE-P40-E3A, Section 9: Chat is now a full-width row in the
        // application shell's own grid (base.html's .app-shell), not
        // nested inside a Workspace-local grid - --chat-height moves with
        // it to the new grid container.
        const grid = document.querySelector('.app-shell');
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

    // CLAUDE-P40-E3A, Section 7: Toolbox's own show/hide toggle is now the
    // Display|Toolbox panel-dividing line itself, wired in base.html's own
    // inline script (application-shell level) alongside the Lists divider
    // - both panels' dividers live in one place now, not split across two
    // files. Nothing left to wire here. The Display-Layout/Appearance/User
    // menus' click-outside-close also moved to base.html (those controls
    // themselves are shell-level now, present on every authenticated page,
    // not just this one).

    // CLAUDE-P40-E3A, Section 6: dynamic multi-division Display. Division
    // 0 is always whatever the server rendered (Investigation/Document/
    // Overview) - never closed, never client-side-repopulated, and stays
    // the one division Toolbox is bound to (the ordinary ?source=/?case=
    // query string - the only honest way a shared, server-rendered
    // Toolbox can follow "the active division"). Divisions 1-5 are
    // client-side-only slots: each loads its content from the SAME
    // authorized workspace.source_file route a normal ?source= view
    // already uses (workspace-active-sources-data's own file_url,
    // resolved server-side via url_for), so a division can never render a
    // Document this reviewer/Project isn't already authorized for, and
    // never a removed one (active_sources only). Multi-Display geometry
    // (orientation, quantity, which division holds which Document) is
    // reviewer/device presentation state only - localStorage/
    // sessionStorage, never a Project/Document/ownership/authorization/
    // evidence/conversation/governance-log write (Section 6's own
    // "presentation-state boundary").
    (function setUpDisplayLayout() {
        const divisionsRoot = document.getElementById('display-divisions');
        const dataScript = document.getElementById('workspace-active-sources-data');
        if (!divisionsRoot || !dataScript) return;

        // MAX_DISPLAY_DIVISIONS = 6 (division 0 + 5 more, all always
        // server-rendered - see case_workspace.html's own comment on
        // this exact number): a restrained, explained ceiling, not a
        // decorative round one. Past 6 simultaneous divisions a typical
        // 1280-1920px viewport gives each one under ~200px in the
        // vertical orientation - too narrow to usefully read an
        // architectural drawing or document.
        const MAX_DISPLAY_DIVISIONS = 6;
        const MIN_DISPLAY_DIVISIONS = 1;

        let sourcesById = {};
        try {
            JSON.parse(dataScript.textContent || '[]').forEach((s) => { sourcesById[s.id] = s; });
        } catch (e) { /* ignore */ }

        const layoutKey = `beehive:display:layout:${projectId}`;
        const openDivisionsKey = `beehive:display:open:${projectId}`;
        const targetKey = `beehive:display:target:${projectId}`;

        let quantity = 1;
        let orientation = 'vertical';
        let activeTarget = 0;

        function applyLayout(nextQuantity, nextOrientation, persist) {
            quantity = Math.max(MIN_DISPLAY_DIVISIONS, Math.min(MAX_DISPLAY_DIVISIONS, nextQuantity));
            orientation = nextOrientation === 'horizontal' ? 'horizontal' : 'vertical';
            divisionsRoot.dataset.count = String(quantity);
            divisionsRoot.dataset.orientation = orientation;
            if (activeTarget >= quantity) setActiveTarget(0);
            if (persist !== false) {
                try { window.localStorage.setItem(layoutKey, JSON.stringify({ quantity: quantity, orientation: orientation })); } catch (e) { /* ignore */ }
            }
        }

        function syncMenuControls(menuPrefix, pendingQuantity, pendingOrientation) {
            const valueEl = document.getElementById(`${menuPrefix}-quantity-value`);
            if (valueEl) valueEl.textContent = String(pendingQuantity);
            const vBtn = document.getElementById(`${menuPrefix}-orientation-vertical`) || document.querySelector(`[data-context-orientation="vertical"]`);
            const hBtn = document.getElementById(`${menuPrefix}-orientation-horizontal`) || document.querySelector(`[data-context-orientation="horizontal"]`);
            if (vBtn) vBtn.setAttribute('aria-pressed', String(pendingOrientation === 'vertical'));
            if (hBtn) hBtn.setAttribute('aria-pressed', String(pendingOrientation === 'horizontal'));
        }

        // ---------------- Top-bar Display-layout control (base.html) -----
        (function wireTopBarLayoutControl() {
            const decBtn = document.getElementById('display-quantity-decrement');
            const incBtn = document.getElementById('display-quantity-increment');
            const applyBtn = document.getElementById('display-layout-apply');
            const vBtn = document.getElementById('display-orientation-vertical');
            const hBtn = document.getElementById('display-orientation-horizontal');
            if (!decBtn || !incBtn || !applyBtn) return;

            let pendingQuantity = quantity;
            let pendingOrientation = orientation;
            syncMenuControls('display', pendingQuantity, pendingOrientation);

            decBtn.addEventListener('click', () => {
                pendingQuantity = Math.max(MIN_DISPLAY_DIVISIONS, pendingQuantity - 1);
                syncMenuControls('display', pendingQuantity, pendingOrientation);
            });
            incBtn.addEventListener('click', () => {
                pendingQuantity = Math.min(MAX_DISPLAY_DIVISIONS, pendingQuantity + 1);
                syncMenuControls('display', pendingQuantity, pendingOrientation);
            });
            if (vBtn) vBtn.addEventListener('click', () => { pendingOrientation = 'vertical'; syncMenuControls('display', pendingQuantity, pendingOrientation); });
            if (hBtn) hBtn.addEventListener('click', () => { pendingOrientation = 'horizontal'; syncMenuControls('display', pendingQuantity, pendingOrientation); });

            applyBtn.addEventListener('click', () => {
                applyLayout(pendingQuantity, pendingOrientation);
                const menu = document.getElementById('workspace-layout-menu');
                if (menu) menu.open = false;
            });
        })();

        function saveOpenDivisions() {
            const open = [];
            for (let i = 1; i < MAX_DISPLAY_DIVISIONS; i++) {
                const division = document.getElementById(`display-division-${i}`);
                if (division && division.dataset.sourceId) open.push(division.dataset.sourceId);
            }
            try { window.sessionStorage.setItem(openDivisionsKey, JSON.stringify(open)); } catch (e) { /* ignore */ }
        }

        function promoteDivision(sourceId) {
            // Division 0 is about to become this Document (a real
            // navigation - the only honest way for Toolbox to follow
            // "the active division" in a server-rendered page) -
            // preserve every OTHER currently-open division across it.
            const open = [];
            for (let i = 1; i < MAX_DISPLAY_DIVISIONS; i++) {
                const division = document.getElementById(`display-division-${i}`);
                if (division && division.dataset.sourceId && division.dataset.sourceId !== sourceId) {
                    open.push(division.dataset.sourceId);
                }
            }
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

            const nameEl = division.querySelector('.display-division-header-name');
            if (nameEl) nameEl.textContent = source.name;

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

        // ---------------- Close a Display: remaining Displays expand -----
        // (CLAUDE-P40-E3A, Section 6). Division 0 has no close button - it
        // is the always-present primary. At least one Display always
        // remains: quantity never drops below MIN_DISPLAY_DIVISIONS.
        document.querySelectorAll('[data-division-close]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.divisionClose, 10);
                clearDivision(idx);
                applyLayout(quantity - 1, orientation);
            });
        });

        // ---------------- Active target division (Section 6) -------------
        // "One Display is always the active target... clicking a Display
        // selects it... the next selected Document opens in that Display
        // only." Division 0 remains the default target (a real ?source=
        // navigation, unchanged); selecting a different Display makes
        // Lists route the next Document click there instead, client-side
        // (see base.html's own leaf-click handler, which calls
        // window.ArchioskDisplay.populateDivision below).
        function setActiveTarget(index) {
            activeTarget = index;
            divisionsRoot.querySelectorAll('.display-division').forEach((d) => {
                d.classList.toggle('active', parseInt(d.dataset.division, 10) === index);
            });
            try { window.sessionStorage.setItem(targetKey, String(index)); } catch (e) { /* ignore */ }
        }
        divisionsRoot.querySelectorAll('.display-division').forEach((division) => {
            division.addEventListener('click', () => {
                setActiveTarget(parseInt(division.dataset.division, 10));
            });
        });

        window.ArchioskDisplay = {
            getActiveTarget: () => activeTarget,
            populateDivision: (index, sourceId) => populateDivision(index, sourceId, true),
            clearDivision: (index) => clearDivision(index),
            getDivisionSource: (index) => {
                const division = document.getElementById(`display-division-${index}`);
                return division ? division.dataset.sourceId : undefined;
            },
        };

        // ---------------- Right-click context menu (Section 6) -----------
        // ONE shared menu, repositioned to whichever Display was
        // right-clicked - Close / Divide (direction + quantity + Apply)
        // only, the capabilities honestly implemented this stage. Closes
        // on outside click or Escape.
        (function setUpContextMenu() {
            const menu = document.getElementById('display-context-menu');
            const closeBtn = document.getElementById('display-context-close');
            const applyBtn = document.getElementById('display-context-apply');
            const decBtn = document.getElementById('display-context-decrement');
            const incBtn = document.getElementById('display-context-increment');
            const vBtn = document.getElementById('display-context-orientation-vertical');
            const hBtn = document.getElementById('display-context-orientation-horizontal');
            if (!menu) return;

            let menuDivisionIndex = null;
            let pendingQuantity = 2;
            let pendingOrientation = 'vertical';

            function openMenu(x, y, divisionIndex) {
                menuDivisionIndex = divisionIndex;
                pendingQuantity = 2;
                pendingOrientation = orientation;
                syncMenuControls('display-context', pendingQuantity, pendingOrientation);
                if (closeBtn) closeBtn.hidden = (divisionIndex === 0);
                menu.style.left = `${x}px`;
                menu.style.top = `${y}px`;
                menu.hidden = false;
            }
            function closeMenu() { menu.hidden = true; menuDivisionIndex = null; }

            divisionsRoot.querySelectorAll('.display-division').forEach((division) => {
                division.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    openMenu(e.clientX, e.clientY, parseInt(division.dataset.division, 10));
                });
            });
            document.addEventListener('click', (e) => {
                if (!menu.hidden && !menu.contains(e.target)) closeMenu();
            });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && !menu.hidden) closeMenu();
            });

            if (closeBtn) closeBtn.addEventListener('click', () => {
                if (menuDivisionIndex) {
                    clearDivision(menuDivisionIndex);
                    applyLayout(quantity - 1, orientation);
                }
                closeMenu();
            });
            if (decBtn) decBtn.addEventListener('click', () => { pendingQuantity = Math.max(2, pendingQuantity - 1); syncMenuControls('display-context', pendingQuantity, pendingOrientation); });
            if (incBtn) incBtn.addEventListener('click', () => { pendingQuantity = Math.min(MAX_DISPLAY_DIVISIONS, pendingQuantity + 1); syncMenuControls('display-context', pendingQuantity, pendingOrientation); });
            if (vBtn) vBtn.addEventListener('click', () => { pendingOrientation = 'vertical'; syncMenuControls('display-context', pendingQuantity, pendingOrientation); });
            if (hBtn) hBtn.addEventListener('click', () => { pendingOrientation = 'horizontal'; syncMenuControls('display-context', pendingQuantity, pendingOrientation); });
            if (applyBtn) applyBtn.addEventListener('click', () => {
                // "Divide this Display" - this stage's own honest scope:
                // applies the chosen direction/quantity to the WHOLE
                // Display (extending the existing dynamic-N mechanism),
                // not a true nested sub-grid within one division - a
                // fully independent per-division sub-split is not
                // implemented this stage (Section 6 asks only for the
                // presentation-state foundation, not every refinement).
                applyLayout(pendingQuantity, pendingOrientation);
                closeMenu();
            });
        })();

        // Division 0's own header name identifies the active division -
        // no separate click behavior needed (it's already division 0,
        // already the default target).
        const primaryNameEl = document.querySelector('#display-division-0 .display-division-header-name');
        if (primaryNameEl) {
            primaryNameEl.setAttribute('aria-label', `${primaryNameEl.textContent.trim()} (active division)`);
        }

        // Restore whatever was open before the last navigation - a
        // promotion (or any other navigation within this Project) must
        // not silently lose the rest of a split view someone was
        // actively using. Presentation state only (sessionStorage) -
        // never a Project/Document write (Section 6's boundary).
        let storedLayout = null;
        try { storedLayout = JSON.parse(window.localStorage.getItem(layoutKey) || 'null'); } catch (e) { /* ignore */ }
        applyLayout(storedLayout ? storedLayout.quantity : 1, storedLayout ? storedLayout.orientation : 'vertical', false);

        let storedTarget = null;
        try { storedTarget = parseInt(window.sessionStorage.getItem(targetKey), 10); } catch (e) { /* ignore */ }
        setActiveTarget(Number.isInteger(storedTarget) && storedTarget < quantity ? storedTarget : 0);

        let savedOpen = [];
        try { savedOpen = JSON.parse(window.sessionStorage.getItem(openDivisionsKey) || '[]'); } catch (e) { /* ignore */ }
        savedOpen.forEach((sourceId, idx) => {
            if (idx < MAX_DISPLAY_DIVISIONS - 1 && sourcesById[sourceId]) populateDivision(idx + 1, sourceId, false);
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
