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
    // when the handle is focused), and one size toggle as the keyboard-
    // friendly alternative Section C itself asks for. Height is a CSS
    // custom property (--chat-height, on .app-shell), read by the Chat
    // row's own height rule - one write point, so the drag handle and
    // the toggle never fight each other or drift out of sync.
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
        // CLAUDE-P40-E3A-QA, Section 10: the one size toggle's label names
        // the action it performs next, not a fixed preset name - "closer to
        // Expanded than Compact" (the arithmetic midpoint between the two
        // presets) is "already expanded", so the toggle offers to Compact
        // it, and vice versa. Applies regardless of whether the height got
        // there via drag, keyboard, or the toggle itself.
        const SIZE_MIDPOINT = (COMPACT_HEIGHT + EXPANDED_HEIGHT) / 2;
        const heightKey = `beehive:chat:height:${projectId}`;
        const sizeToggle = document.getElementById('conversation-size-toggle');

        function clamp(px) {
            return Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, px));
        }

        function syncSizeToggle(px) {
            if (!sizeToggle) return;
            const isExpanded = px > SIZE_MIDPOINT;
            sizeToggle.textContent = isExpanded ? 'Compact' : 'Expand';
            sizeToggle.setAttribute('aria-pressed', String(isExpanded));
            sizeToggle.setAttribute('aria-label', isExpanded ? 'Compact the conversation panel' : 'Expand the conversation panel');
        }

        function applyHeight(px, persist) {
            const clamped = clamp(px);
            grid.style.setProperty('--chat-height', `${clamped}px`);
            handle.setAttribute('aria-valuenow', String(clamped));
            syncSizeToggle(clamped);
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

        if (sizeToggle) {
            sizeToggle.addEventListener('click', () => {
                const current = parseInt(handle.getAttribute('aria-valuenow'), 10) || COMPACT_HEIGHT;
                const target = current > SIZE_MIDPOINT ? COMPACT_HEIGHT : EXPANDED_HEIGHT;
                applyHeight(target);
                handle.focus();
            });
        }
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

        // CLAUDE-P40-VW4: Vertical and Horizontal are two INDEPENDENT
        // numbers, not one quantity plus an either/or orientation choice
        // (the E3A/E3A-QA/VW1 model this replaces) - Vertical = side-by-
        // side columns, Horizontal = stacked rows, and the resulting
        // Display count is their PRODUCT (product owner's own worked
        // examples: 2x3 and 3x2 both total six, but are different
        // arrangements). `quantity` is retained as a plain derived value
        // (vertical * horizontal) so the rest of this function - active-
        // target bounds, saved-open-division restore - doesn't need to
        // change shape.
        let vertical = 1;
        let horizontal = 1;
        let quantity = 1;
        let activeTarget = 0;

        function applyLayout(nextVertical, nextHorizontal, persist) {
            const safeVertical = Number.isInteger(nextVertical) ? nextVertical : MIN_DISPLAY_DIVISIONS;
            const safeHorizontal = Number.isInteger(nextHorizontal) ? nextHorizontal : MIN_DISPLAY_DIVISIONS;
            let v = Math.max(MIN_DISPLAY_DIVISIONS, Math.min(MAX_DISPLAY_DIVISIONS, safeVertical));
            let h = Math.max(MIN_DISPLAY_DIVISIONS, Math.min(MAX_DISPLAY_DIVISIONS, safeHorizontal));
            // The six-Display ceiling applies to the PRODUCT, not either
            // axis alone (Requirement 5/7: never accept a partially-
            // applied or corrupted, >6 layout, even from a hand-edited or
            // stale localStorage value) - shrink whichever axis is
            // currently larger until the product fits, same deterministic
            // rule "Close this Display" below uses.
            while (v * h > MAX_DISPLAY_DIVISIONS) {
                if (h > MIN_DISPLAY_DIVISIONS && h >= v) h -= 1;
                else if (v > MIN_DISPLAY_DIVISIONS) v -= 1;
                else break;
            }
            vertical = v;
            horizontal = h;
            quantity = vertical * horizontal;
            divisionsRoot.dataset.count = String(quantity);
            divisionsRoot.dataset.vertical = String(vertical);
            divisionsRoot.dataset.horizontal = String(horizontal);
            // Read by the [900px breakpoint] grid-template rule in
            // main.css (repeat(var(--display-v), 1fr) / repeat(var(
            // --display-h), 1fr)) - a genuine two-axis grid can't be
            // expressed by the old finite [data-orientation][data-count]
            // attribute-selector table (14 valid V*H<=6 combinations,
            // not a linear 1-6 range), so the column/row counts are
            // handed to CSS as custom properties instead.
            divisionsRoot.style.setProperty('--display-v', String(vertical));
            divisionsRoot.style.setProperty('--display-h', String(horizontal));
            if (activeTarget >= quantity) setActiveTarget(0);
            if (persist !== false) {
                try { window.localStorage.setItem(layoutKey, JSON.stringify({ vertical: vertical, horizontal: horizontal })); } catch (e) { /* ignore */ }
            }
        }

        // CLAUDE-P40-VW4: backward compatibility for a `layoutKey` value
        // saved before this stage - {quantity, orientation} rather than
        // {vertical, horizontal}. Mapping is the one this stage's own
        // prompt specifies verbatim: an unsplit Display (quantity 1) is
        // Vertical 1 / Horizontal 1 regardless of its old orientation
        // (equivalent at quantity 1); a "vertical" quantity N was N
        // side-by-side columns, so becomes Vertical N / Horizontal 1; a
        // "horizontal" quantity N was N stacked rows, so becomes
        // Vertical 1 / Horizontal N. A value already in the new shape
        // (written by this stage's own code) passes through unchanged,
        // making the mapping idempotent on re-application - same
        // approach VW3's own Appearance-mode compatibility mapping used.
        function normalizeStoredLayout(stored) {
            if (stored && Number.isInteger(stored.vertical) && Number.isInteger(stored.horizontal)) {
                return { vertical: stored.vertical, horizontal: stored.horizontal };
            }
            if (stored && Number.isInteger(stored.quantity)) {
                return stored.orientation === 'horizontal'
                    ? { vertical: 1, horizontal: stored.quantity }
                    : { vertical: stored.quantity, horizontal: 1 };
            }
            return { vertical: 1, horizontal: 1 };
        }

        // CLAUDE-P40-VW4, Requirement 6: "provide a concise explanation
        // rather than silently changing the other number" - the relevant
        // increment button is actually disabled (not just refused on
        // click) the moment applying it would exceed the six-Display
        // ceiling, and the static helper text next to Apply (rendered in
        // both menus - see base.html/case_workspace.html) states the
        // rule up front rather than only reacting after the fact.
        function syncQuantityControls(prefix, pendingVertical, pendingHorizontal) {
            const vValueEl = document.getElementById(`${prefix}-vertical-value`);
            if (vValueEl) vValueEl.textContent = String(pendingVertical);
            const hValueEl = document.getElementById(`${prefix}-horizontal-value`);
            if (hValueEl) hValueEl.textContent = String(pendingHorizontal);
            const vDec = document.getElementById(`${prefix}-vertical-decrement`);
            const vInc = document.getElementById(`${prefix}-vertical-increment`);
            const hDec = document.getElementById(`${prefix}-horizontal-decrement`);
            const hInc = document.getElementById(`${prefix}-horizontal-increment`);
            if (vDec) vDec.disabled = pendingVertical <= MIN_DISPLAY_DIVISIONS;
            if (hDec) hDec.disabled = pendingHorizontal <= MIN_DISPLAY_DIVISIONS;
            if (vInc) vInc.disabled = (pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS;
            if (hInc) hInc.disabled = pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS;
        }

        // ---------------- Top-bar Display-layout control (base.html) -----
        (function wireTopBarLayoutControl() {
            const vDec = document.getElementById('display-vertical-decrement');
            const vInc = document.getElementById('display-vertical-increment');
            const hDec = document.getElementById('display-horizontal-decrement');
            const hInc = document.getElementById('display-horizontal-increment');
            const applyBtn = document.getElementById('display-layout-apply');
            const menuDetails = document.getElementById('workspace-layout-menu');
            if (!vDec || !vInc || !hDec || !hInc || !applyBtn) return;

            let pendingVertical = vertical;
            let pendingHorizontal = horizontal;
            syncQuantityControls('display', pendingVertical, pendingHorizontal);

            // Requirement 9: dismissing/reopening without Apply must not
            // show a stale unapplied edit next time - reset the pending
            // values to whatever is actually applied every time the
            // popover opens (native <details> "toggle" event fires on
            // both open and close; only re-seed on open).
            if (menuDetails) {
                menuDetails.addEventListener('toggle', () => {
                    if (!menuDetails.open) return;
                    pendingVertical = vertical;
                    pendingHorizontal = horizontal;
                    syncQuantityControls('display', pendingVertical, pendingHorizontal);
                });
            }

            vDec.addEventListener('click', () => {
                pendingVertical = Math.max(MIN_DISPLAY_DIVISIONS, pendingVertical - 1);
                syncQuantityControls('display', pendingVertical, pendingHorizontal);
            });
            vInc.addEventListener('click', () => {
                if ((pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS) return;
                pendingVertical += 1;
                syncQuantityControls('display', pendingVertical, pendingHorizontal);
            });
            hDec.addEventListener('click', () => {
                pendingHorizontal = Math.max(MIN_DISPLAY_DIVISIONS, pendingHorizontal - 1);
                syncQuantityControls('display', pendingVertical, pendingHorizontal);
            });
            hInc.addEventListener('click', () => {
                if (pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS) return;
                pendingHorizontal += 1;
                syncQuantityControls('display', pendingVertical, pendingHorizontal);
            });

            applyBtn.addEventListener('click', () => {
                applyLayout(pendingVertical, pendingHorizontal);
                if (menuDetails) menuDetails.open = false;
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

        // CLAUDE-P40-VW4: a true V x H rectangle can't shrink by exactly
        // one cell and stay a full rectangle (Requirement 7: never a
        // partially-applied or corrupted/ragged layout) - "close one
        // Display" shrinks whichever axis is currently larger by one
        // (ties favor shrinking Horizontal, keeping Vertical - listed
        // and asked-for first everywhere else in this UI - intact
        // longest), the smallest possible reduction that still yields a
        // full rectangle. Division 0/quantity-1 floor: unreachable in
        // practice, since the only caller-visible "close" controls are
        // already hidden whenever vertical*horizontal is already 1 (see
        // closeBtn.hidden below and data-division-close's own template
        // gating, division 0 never renders one).
        function shrinkLayoutByOne() {
            if (horizontal > 1 && horizontal >= vertical) {
                applyLayout(vertical, horizontal - 1);
            } else if (vertical > 1) {
                applyLayout(vertical - 1, horizontal);
            }
        }

        // ---------------- Close a Display: remaining Displays expand -----
        // (CLAUDE-P40-E3A, Section 6). Division 0 has no close button - it
        // is the always-present primary. At least one Display always
        // remains: quantity never drops below MIN_DISPLAY_DIVISIONS.
        document.querySelectorAll('[data-division-close]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.dataset.divisionClose, 10);
                clearDivision(idx);
                shrinkLayoutByOne();
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
            const vDec = document.getElementById('display-context-vertical-decrement');
            const vInc = document.getElementById('display-context-vertical-increment');
            const hDec = document.getElementById('display-context-horizontal-decrement');
            const hInc = document.getElementById('display-context-horizontal-increment');
            if (!menu) return;

            let menuDivisionIndex = null;
            let pendingVertical = vertical;
            let pendingHorizontal = horizontal;

            function openMenu(x, y, divisionIndex) {
                menuDivisionIndex = divisionIndex;
                // CLAUDE-P40-VW4: seed the pending values from the
                // CURRENTLY APPLIED layout (not a fixed preset) - matches
                // the top-bar control and satisfies Requirement 9
                // (dismissing without Apply must show the real state next
                // time, whichever control reopens it).
                pendingVertical = vertical;
                pendingHorizontal = horizontal;
                syncQuantityControls('display-context', pendingVertical, pendingHorizontal);
                if (closeBtn) closeBtn.hidden = (divisionIndex === 0);
                // CLAUDE-P40-E3A-QA, Section 6: "position within the usable
                // application surface" - a right-click near the right or
                // bottom edge must not push the menu partially off-screen.
                // Measured AFTER menu.hidden = false so offsetWidth/Height
                // reflect its real rendered size, then clamped.
                menu.hidden = false;
                const margin = 8;
                const maxLeft = window.innerWidth - menu.offsetWidth - margin;
                const maxTop = window.innerHeight - menu.offsetHeight - margin;
                menu.style.left = `${Math.max(margin, Math.min(x, maxLeft))}px`;
                menu.style.top = `${Math.max(margin, Math.min(y, maxTop))}px`;
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
                    shrinkLayoutByOne();
                }
                closeMenu();
            });
            if (vDec) vDec.addEventListener('click', () => { pendingVertical = Math.max(MIN_DISPLAY_DIVISIONS, pendingVertical - 1); syncQuantityControls('display-context', pendingVertical, pendingHorizontal); });
            if (vInc) vInc.addEventListener('click', () => { if ((pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS) return; pendingVertical += 1; syncQuantityControls('display-context', pendingVertical, pendingHorizontal); });
            if (hDec) hDec.addEventListener('click', () => { pendingHorizontal = Math.max(MIN_DISPLAY_DIVISIONS, pendingHorizontal - 1); syncQuantityControls('display-context', pendingVertical, pendingHorizontal); });
            if (hInc) hInc.addEventListener('click', () => { if (pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS) return; pendingHorizontal += 1; syncQuantityControls('display-context', pendingVertical, pendingHorizontal); });
            if (applyBtn) applyBtn.addEventListener('click', () => {
                // "Divide this Display" - this stage's own honest scope:
                // applies the chosen Vertical x Horizontal to the WHOLE
                // Display (extending the existing dynamic-grid mechanism),
                // not a true nested sub-grid within one division - a
                // fully independent per-division sub-split is not
                // implemented this stage (Section 6 asks only for the
                // presentation-state foundation, not every refinement).
                applyLayout(pendingVertical, pendingHorizontal);
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
        const normalizedLayout = normalizeStoredLayout(storedLayout);
        applyLayout(normalizedLayout.vertical, normalizedLayout.horizontal, false);

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

    // CLAUDE-P40-VW7: OneNote-style selection toolbar for Project
    // Conversation text -> Tags/Highlights/Tasks, plus the Lists Tasks/
    // Tags branches' live-update behaviour and navigate-to-source flash.
    // A bounded, project-scoped capability - see this stage's own
    // authorization comment in routes/workspace.py and
    // services/case_workspace.py. First use of fetch() in this file
    // (tools/dependency_fit.py checked clean beforehand) - used ONLY
    // for the specific cases Section 7/12 require to update without a
    // full page reload (Tag/Task creation, Tag removal); Task complete/
    // reopen stay classic form-POST + redirect, this app's normal
    // convention, and never touch this code path at all.
    (function setUpConversationTagsAndTasks() {
        const toolbar = document.getElementById('conv-selection-toolbar');
        const statusEl = document.getElementById('conv-selection-status');
        const tagDialog = document.getElementById('conv-tag-dialog');
        const taskDialog = document.getElementById('conv-task-dialog');
        if (!toolbar || !statusEl || !tagDialog || !taskDialog) return;

        const tagForm = document.getElementById('conv-tag-form');
        const taskForm = document.getElementById('conv-task-form');

        // Mirrors services/case_workspace.py's own BUILT_IN_TAG_* string
        // constants exactly - these three are fixed code-level identities
        // on the server (never stored per-project), so the client only
        // ever needs to know their literal ids, not fetch them.
        const BUILT_IN_TAG_IMPORTANT = 'built-in:important';
        const BUILT_IN_TAG_QUESTION = 'built-in:question';
        const BUILT_IN_TAG_HIGHLIGHT = 'built-in:highlight';

        let currentAnchor = null; // last computed anchor (or {ambiguous:true,...}), from the most recent meaningful selection
        let currentQuoteText = '';
        let pendingAnchor = null; // anchor captured at the moment a dialog opened - selection may already be gone by submit time
        let dialogTriggerEl = null;
        let statusHideTimer = null;
        let selectionDebounce = null;

        function csrfToken() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.content : '';
        }

        function postForm(url, fields) {
            const formData = new FormData();
            Object.keys(fields).forEach((key) => formData.append(key, fields[key]));
            return fetch(url, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrfToken() },
                credentials: 'same-origin',
            }).then((resp) => resp.json().then((data) => ({ ok: resp.ok, data: data })));
        }

        function showStatus(message, autoHide) {
            statusEl.textContent = message;
            statusEl.hidden = false;
            window.clearTimeout(statusHideTimer);
            if (autoHide) {
                statusHideTimer = window.setTimeout(() => { statusEl.hidden = true; }, 2500);
            }
        }
        function hideStatus() {
            window.clearTimeout(statusHideTimer);
            statusEl.hidden = true;
            statusEl.textContent = '';
        }

        function hideToolbar() {
            toolbar.hidden = true;
            hideStatus();
            currentAnchor = null;
            currentQuoteText = '';
        }

        function dialogOpen() {
            return !tagDialog.hidden || !taskDialog.hidden;
        }

        // -------- Anchor computation (Section 4: text-quote anchoring, --
        // -------- never fragile DOM coordinates) -------------------------
        function withinConversationDock(node) {
            const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
            return !!(el && el.closest('#conversation-dock'));
        }

        function resolveAnchorContainer(node) {
            const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
            if (!el) return null;
            return el.closest('[data-message-text]') || el.closest('#project-conversation-guidance');
        }

        // Range.toString() of "container start -> this boundary" gives the
        // exact rendered-text offset without a manual TreeWalker - simpler
        // and just as correct, since hotlinks() never changes text length.
        function offsetWithin(container, node, nodeOffset) {
            const r = document.createRange();
            r.selectNodeContents(container);
            try {
                r.setEnd(node, nodeOffset);
            } catch (e) {
                return container.textContent.length;
            }
            return r.toString().length;
        }

        function computeAnchorFromSelection(range, text) {
            const startContainer = resolveAnchorContainer(range.startContainer);
            const endContainer = resolveAnchorContainer(range.endContainer);
            // Cross-message/cross-source-block selections must not create
            // an ambiguous anchor (Section 3) - Copy stays available,
            // everything source-dependent gets disabled by the caller.
            if (!startContainer || !endContainer || startContainer !== endContainer) {
                return { ambiguous: true, quote: text };
            }
            const container = startContainer;
            const isGuidance = container.id === 'project-conversation-guidance';
            let scope; let caseId = null; let messageId = null; let guidanceKey = null;
            if (isGuidance) {
                scope = 'guidance';
                guidanceKey = container.dataset.guidanceKey || '';
            } else {
                const messageEl = container.closest('[data-message-id]');
                const scopeEl = container.closest('[data-anchor-scope]');
                if (!messageEl || !scopeEl) return { ambiguous: true, quote: text };
                messageId = messageEl.dataset.messageId;
                scope = scopeEl.dataset.anchorScope;
                if (scope === 'case') caseId = scopeEl.dataset.anchorCaseId;
            }
            const rawStart = offsetWithin(container, range.startContainer, range.startOffset);
            const rawEnd = offsetWithin(container, range.endContainer, range.endOffset);
            const startOffset = Math.min(rawStart, rawEnd);
            const endOffset = Math.max(rawStart, rawEnd);
            const fullText = container.textContent;
            const CONTEXT_LEN = 40;
            return {
                ambiguous: false,
                scope: scope,
                caseId: caseId,
                messageId: messageId,
                guidanceKey: guidanceKey,
                startOffset: startOffset,
                endOffset: endOffset,
                quote: text,
                prefix: fullText.slice(Math.max(0, startOffset - CONTEXT_LEN), startOffset),
                suffix: fullText.slice(endOffset, endOffset + CONTEXT_LEN),
            };
        }

        function anchorFormFields(anchor) {
            return {
                anchor_scope: anchor.scope || '',
                anchor_case_id: anchor.caseId || '',
                anchor_message_id: anchor.messageId || '',
                anchor_guidance_key: anchor.guidanceKey || '',
                anchor_start_offset: anchor.startOffset != null ? String(anchor.startOffset) : '',
                anchor_end_offset: anchor.endOffset != null ? String(anchor.endOffset) : '',
                anchor_quote: anchor.quote || '',
                anchor_prefix: anchor.prefix || '',
                anchor_suffix: anchor.suffix || '',
            };
        }

        // Mirrors routes/workspace.py's own _conversation_source_url -
        // the current page's own path IS the show_workspace URL whenever
        // this script runs (case_workspace.js loads on no other page),
        // so no project_id needs deriving separately.
        function buildSourceUrl(anchor) {
            const basePath = window.location.pathname;
            let query = '';
            let fragment;
            if (anchor.scope === 'case') {
                query = `?case=${encodeURIComponent(anchor.case_id)}`;
                fragment = `conv-source-${anchor.message_id}`;
            } else if (anchor.scope === 'guidance') {
                fragment = 'conv-source-guidance';
            } else {
                fragment = `conv-source-${anchor.message_id}`;
            }
            return `${basePath}${query}#${fragment}`;
        }

        // -------- Toolbar visibility + positioning (Section 3/10) --------
        function applyToolbarAvailability(anchor) {
            const sourceDependent = toolbar.querySelectorAll('[data-conv-action]:not([data-conv-action="copy"])');
            const usable = !!(anchor && !anchor.ambiguous);
            sourceDependent.forEach((btn) => {
                btn.disabled = !usable;
                btn.title = usable ? '' : 'Select text within a single message or the guidance note to use this action.';
            });
            if (!usable && anchor) {
                showStatus('Selection spans multiple messages \u2014 only Copy is available.', false);
            } else {
                hideStatus();
            }
        }

        function positionToolbar(rect) {
            toolbar.hidden = false;
            const margin = 8;
            let top = rect.top - toolbar.offsetHeight - margin;
            if (top < margin) top = rect.bottom + margin;
            if (top + toolbar.offsetHeight > window.innerHeight - margin) {
                top = Math.max(margin, window.innerHeight - toolbar.offsetHeight - margin);
            }
            let left = rect.left + (rect.width / 2) - (toolbar.offsetWidth / 2);
            left = Math.max(margin, Math.min(left, window.innerWidth - toolbar.offsetWidth - margin));
            toolbar.style.top = `${top}px`;
            toolbar.style.left = `${left}px`;
        }

        function handleSelectionMaybeChanged() {
            if (dialogOpen()) return;
            const active = document.activeElement;
            if (active && ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].indexOf(active.tagName) !== -1) {
                hideToolbar();
                return;
            }
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0 || sel.isCollapsed) { hideToolbar(); return; }
            const text = sel.toString();
            if (!text || !text.trim()) { hideToolbar(); return; }
            const range = sel.getRangeAt(0);
            if (!withinConversationDock(range.startContainer) && !withinConversationDock(range.endContainer)) {
                hideToolbar();
                return;
            }
            const anchor = computeAnchorFromSelection(range, text);
            currentAnchor = anchor;
            currentQuoteText = text;
            positionToolbar(range.getBoundingClientRect());
            applyToolbarAvailability(anchor);
        }

        document.addEventListener('selectionchange', () => {
            window.clearTimeout(selectionDebounce);
            selectionDebounce = window.setTimeout(handleSelectionMaybeChanged, 150);
        });

        // -------- Copy (Section 9) ----------------------------------------
        function fallbackCopy(text, cb) {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            let ok = false;
            try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
            document.body.removeChild(ta);
            cb(ok);
        }
        function doCopy(text) {
            function done(ok) { showStatus(ok ? 'Copied.' : 'Copy failed.', true); }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => done(true), () => fallbackCopy(text, done));
            } else {
                fallbackCopy(text, done);
            }
        }

        // -------- Truncation for Task titles / dialog quote preview ------
        function truncateForDisplay(text, maxLen) {
            const trimmed = text.trim().replace(/\s+/g, ' ');
            if (trimmed.length <= maxLen) return trimmed;
            let cut = trimmed.slice(0, maxLen);
            const lastSpace = cut.lastIndexOf(' ');
            if (lastSpace > maxLen * 0.6) cut = cut.slice(0, lastSpace);
            return `${cut}\u2026`;
        }

        // -------- Add Tag / Make Task dialogs (Section 5/6) ---------------
        function showDialogError(dialog, message) {
            const el = dialog.querySelector('[data-conv-dialog-error]');
            if (!el) return;
            el.textContent = message;
            el.hidden = false;
        }
        function clearDialogError(dialog) {
            const el = dialog.querySelector('[data-conv-dialog-error]');
            if (el) { el.hidden = true; el.textContent = ''; }
        }

        function injectAnchorHiddenFields(form, anchor) {
            form.querySelectorAll('[data-conv-anchor-field]').forEach((el) => el.remove());
            const fields = anchorFormFields(anchor);
            Object.keys(fields).forEach((name) => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = name;
                input.value = fields[name];
                input.setAttribute('data-conv-anchor-field', '');
                form.appendChild(input);
            });
        }

        function showDialog(dialog) {
            clearDialogError(dialog);
            dialog.hidden = false;
            const focusable = dialog.querySelector('input, select, textarea');
            if (focusable) focusable.focus();
        }
        function closeDialog(dialog) {
            dialog.hidden = true;
            pendingAnchor = null;
            const returnTarget = (dialogTriggerEl && document.body.contains(dialogTriggerEl)) ? dialogTriggerEl : null;
            if (returnTarget && typeof returnTarget.focus === 'function') returnTarget.focus();
            dialogTriggerEl = null;
        }

        function openTagDialog(anchor, quote, triggerEl) {
            pendingAnchor = anchor;
            dialogTriggerEl = triggerEl;
            hideToolbar();
            tagForm.reset();
            document.getElementById('conv-tag-dialog-quote').textContent = `\u201C${truncateForDisplay(quote, 140)}\u201D`;
            injectAnchorHiddenFields(tagForm, anchor);
            showDialog(tagDialog);
        }
        function openTaskDialog(anchor, quote, triggerEl) {
            pendingAnchor = anchor;
            dialogTriggerEl = triggerEl;
            hideToolbar();
            taskForm.reset();
            document.getElementById('conv-task-title').value = truncateForDisplay(quote, 200);
            injectAnchorHiddenFields(taskForm, anchor);
            showDialog(taskDialog);
        }

        document.querySelectorAll('[data-conv-dialog-cancel]').forEach((btn) => {
            btn.addEventListener('click', () => closeDialog(btn.closest('.conv-dialog')));
        });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (!tagDialog.hidden) { closeDialog(tagDialog); return; }
            if (!taskDialog.hidden) { closeDialog(taskDialog); return; }
            if (!toolbar.hidden) hideToolbar();
        });
        document.addEventListener('mousedown', (e) => {
            if (!tagDialog.hidden && !tagDialog.contains(e.target)) { closeDialog(tagDialog); return; }
            if (!taskDialog.hidden && !taskDialog.contains(e.target)) { closeDialog(taskDialog); return; }
            if (!toolbar.hidden && !toolbar.contains(e.target)) {
                const sel = window.getSelection();
                if (!sel || sel.isCollapsed || !sel.toString().trim()) hideToolbar();
            }
        });

        [tagForm, taskForm].forEach((form) => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                clearDialogError(form.closest('.conv-dialog'));
                const formData = new FormData(form);
                fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-CSRFToken': csrfToken() },
                    credentials: 'same-origin',
                }).then((resp) => resp.json()).then((data) => {
                    if (!data.ok) {
                        showDialogError(form.closest('.conv-dialog'), data.error || 'Something went wrong.');
                        return;
                    }
                    if (form === tagForm) {
                        patchTagsListOnAdd(data.occurrence, data.tag, data.counts);
                        showStatus(`Tagged as ${data.tag.name}.`, true);
                    } else {
                        patchTasksListOnCreate(data.task, data.counts);
                        showStatus('Task created.', true);
                    }
                    closeDialog(form.closest('.conv-dialog'));
                }).catch(() => showDialogError(form.closest('.conv-dialog'), 'Network error \u2014 please try again.'));
            });
        });

        // -------- Toolbar button handling ---------------------------------
        toolbar.addEventListener('mousedown', (e) => {
            // Preserve the live text selection through the click - a plain
            // browser default would shift focus to the button on mousedown
            // and collapse the selection before the click handler below
            // ever runs (Section 3's own "must not destroy selection before
            // an action captures it"). The click event itself still fires
            // normally afterwards; only the focus-shift side effect is
            // suppressed.
            e.preventDefault();
        });
        toolbar.addEventListener('keydown', (e) => {
            if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
            const buttons = Array.from(toolbar.querySelectorAll('[data-conv-action]:not([disabled])'));
            const idx = buttons.indexOf(document.activeElement);
            if (idx === -1) return;
            e.preventDefault();
            const next = e.key === 'ArrowRight' ? (idx + 1) % buttons.length : (idx - 1 + buttons.length) % buttons.length;
            buttons[next].focus();
        });
        toolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-conv-action]');
            if (!btn || btn.disabled) return;
            const action = btn.dataset.convAction;
            const anchor = currentAnchor;
            const quote = currentQuoteText;
            if (action === 'copy') { doCopy(quote); return; }
            if (!anchor || anchor.ambiguous) return; // defensive - button is already disabled in this state
            if (action === 'tag') { openTagDialog(anchor, quote, btn); return; }
            if (action === 'task') { openTaskDialog(anchor, quote, btn); return; }
            const builtIn = action === 'important' ? { id: BUILT_IN_TAG_IMPORTANT, name: 'Important' }
                : action === 'question' ? { id: BUILT_IN_TAG_QUESTION, name: 'Question' }
                : action === 'highlight' ? { id: BUILT_IN_TAG_HIGHLIGHT, name: 'Highlight' } : null;
            if (!builtIn) return;
            postForm(tagForm.action, Object.assign({ tag_id: builtIn.id }, anchorFormFields(anchor))).then(({ ok, data }) => {
                if (!ok || !data.ok) {
                    showStatus((data && data.error) || 'Could not apply tag.', true);
                    return;
                }
                patchTagsListOnAdd(data.occurrence, data.tag, data.counts);
                showStatus(`Tagged as ${builtIn.name}.`, true);
                hideToolbar();
            });
        });

        // -------- Live Lists DOM patching (Section 7) ---------------------
        function cssEscape(value) {
            return (window.CSS && CSS.escape) ? CSS.escape(value) : String(value).replace(/["\\]/g, '\\$&');
        }
        function buildEmptyRow(message) {
            const li = document.createElement('li');
            li.className = 'tree-node-empty';
            const span = document.createElement('span');
            span.className = 'pane-note';
            span.textContent = message;
            li.appendChild(span);
            return li;
        }
        function buildTagGroupElement(tag) {
            const li = document.createElement('li');
            li.className = 'tree-node-group';
            li.setAttribute('data-tag-group', tag.id);
            const p = document.createElement('p');
            p.className = 'launcher-subheading';
            const swatch = document.createElement('span');
            swatch.className = `launcher-tag-swatch conv-tag-color-${tag.color}`;
            swatch.setAttribute('aria-hidden', 'true');
            p.appendChild(swatch);
            p.appendChild(document.createTextNode(` ${tag.name} `));
            const countSpan = document.createElement('span');
            countSpan.className = 'launcher-count';
            countSpan.setAttribute('data-tag-group-count', '');
            countSpan.textContent = '0';
            p.appendChild(countSpan);
            li.appendChild(p);
            const ul = document.createElement('ul');
            ul.className = 'tree-children';
            ul.setAttribute('data-tree-open', '');
            li.appendChild(ul);
            return li;
        }
        function removeOccurrenceUrl(occurrenceId) {
            // Mirrors remove_tag_occurrence_route's own path. Built here
            // rather than copied from an existing row's action=, because
            // the very first Tag ever added to a Project has no existing
            // row to copy from.
            return `${window.location.pathname}/tags/${encodeURIComponent(occurrenceId)}/remove`;
        }
        function buildTagOccurrenceElement(occurrence) {
            const li = document.createElement('li');
            li.className = 'tree-node';
            li.setAttribute('data-tree-node', '');
            li.setAttribute('data-tag-occurrence-id', occurrence.id);
            const row = document.createElement('div');
            row.className = 'launcher-task-row';
            const a = document.createElement('a');
            a.className = 'tree-leaf launcher-link';
            a.href = buildSourceUrl(occurrence.source_anchor);
            a.textContent = `\u201C${truncateForDisplay(occurrence.quote, 60)}\u201D`;
            row.appendChild(a);
            const form = document.createElement('form');
            form.method = 'post';
            form.action = removeOccurrenceUrl(occurrence.id);
            form.setAttribute('data-tag-remove-form', '');
            form.setAttribute('data-occurrence-id', occurrence.id);
            const btn = document.createElement('button');
            btn.type = 'submit';
            btn.className = 'link-button';
            btn.textContent = 'Remove';
            form.appendChild(btn);
            row.appendChild(form);
            li.appendChild(row);
            return li;
        }
        function patchTagsListOnAdd(occurrence, tag, counts) {
            const countEl = document.getElementById('lists-tags-count');
            if (countEl) countEl.textContent = String(counts.total);
            const groupsRoot = document.getElementById('lists-tags-groups');
            if (!groupsRoot) return;
            const emptyRow = groupsRoot.querySelector('.tree-node-empty');
            if (emptyRow) emptyRow.remove();
            let group = groupsRoot.querySelector(`[data-tag-group="${cssEscape(tag.id)}"]`);
            if (!group) {
                group = buildTagGroupElement(tag);
                groupsRoot.appendChild(group);
            }
            const list = group.querySelector('ul.tree-children');
            list.appendChild(buildTagOccurrenceElement(occurrence));
            const groupCountEl = group.querySelector('[data-tag-group-count]');
            const known = counts.by_tag && counts.by_tag[tag.id] != null ? counts.by_tag[tag.id] : list.children.length;
            if (groupCountEl) groupCountEl.textContent = String(known);
        }

        function buildTaskElement(task, open) {
            const li = document.createElement('li');
            li.className = 'tree-node';
            li.setAttribute('data-tree-node', '');
            li.setAttribute('data-task-id', task.id);
            const row = document.createElement('div');
            row.className = 'launcher-task-row';
            const a = document.createElement('a');
            a.className = open ? 'tree-leaf launcher-link' : 'tree-leaf launcher-link launcher-task-completed';
            a.href = buildSourceUrl(task.source_anchor);
            a.textContent = task.title;
            row.appendChild(a);
            const form = document.createElement('form');
            form.method = 'post';
            form.action = `${window.location.pathname}/tasks/${encodeURIComponent(task.id)}/${open ? 'complete' : 'reopen'}`;
            const btn = document.createElement('button');
            btn.type = 'submit';
            btn.className = 'link-button';
            btn.textContent = open ? 'Mark complete' : 'Reopen';
            form.appendChild(btn);
            row.appendChild(form);
            li.appendChild(row);
            return li;
        }
        function patchTasksListOnCreate(task, counts) {
            const countEl = document.getElementById('lists-tasks-count');
            if (countEl) countEl.textContent = String(counts.total);
            const openCountEl = document.getElementById('lists-tasks-open-count');
            if (openCountEl) openCountEl.textContent = String(counts.open);
            const completedCountEl = document.getElementById('lists-tasks-completed-count');
            if (completedCountEl) completedCountEl.textContent = String(counts.completed);
            const openList = document.getElementById('lists-tasks-open-list');
            if (!openList) return;
            const emptyRow = openList.querySelector('.tree-node-empty');
            if (emptyRow) emptyRow.remove();
            openList.appendChild(buildTaskElement(task, true));
        }

        // Removal is wired via delegation so it uniformly covers both
        // server-rendered rows (present on page load) and rows this
        // script itself just inserted, without a second binding pass.
        document.addEventListener('submit', (e) => {
            const form = e.target.closest('[data-tag-remove-form]');
            if (!form) return;
            e.preventDefault();
            const row = form.closest('[data-tag-occurrence-id]');
            const group = form.closest('[data-tag-group]');
            postForm(form.action, {}).then(({ ok, data }) => {
                if (!ok || !data.ok) {
                    showStatus((data && data.error) || 'Could not remove tag.', true);
                    return;
                }
                if (row) row.remove();
                const countEl = document.getElementById('lists-tags-count');
                if (countEl) countEl.textContent = String(data.counts.total);
                if (group) {
                    const tagId = group.getAttribute('data-tag-group');
                    const remaining = data.counts.by_tag && data.counts.by_tag[tagId] != null ? data.counts.by_tag[tagId] : 0;
                    if (remaining <= 0) {
                        group.remove();
                        const groupsRoot = document.getElementById('lists-tags-groups');
                        if (groupsRoot && !groupsRoot.querySelector('[data-tag-group]')) {
                            groupsRoot.appendChild(buildEmptyRow('No Tags yet.'));
                        }
                    } else {
                        const groupCountEl = group.querySelector('[data-tag-group-count]');
                        if (groupCountEl) groupCountEl.textContent = String(remaining);
                    }
                }
            });
        });

        // -------- Navigate-to-source flash (Section 4) --------------------
        function navigateToConversationSource() {
            const hash = window.location.hash;
            if (!hash || hash.indexOf('#conv-source-') !== 0) return;
            const key = hash.slice('#conv-source-'.length);
            const target = key === 'guidance'
                ? document.getElementById('project-conversation-guidance')
                : document.getElementById(`message-${key}`);
            if (!target) return;
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            target.classList.add('conv-source-flash');
            window.setTimeout(() => target.classList.remove('conv-source-flash'), 2500);
        }
        navigateToConversationSource();
        window.addEventListener('hashchange', navigateToConversationSource);
    })();
});
