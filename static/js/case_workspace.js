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
            // CLAUDE-P40-VW7A-QA2, Section 6: "active accent only while
            // dragging" - :hover alone isn't enough, since a drag
            // legitimately continues (via the document-level listeners
            // above) even once the pointer strays off this handle's own
            // thin hit target; an explicit class is what keeps the accent
            // lit for the whole drag regardless of exact pointer position.
            handle.classList.remove('dragging');
            document.removeEventListener('pointermove', onPointerMove);
            document.removeEventListener('pointerup', onPointerUp);
        }
        handle.addEventListener('pointerdown', (e) => {
            dragStartY = e.clientY;
            dragStartHeight = parseInt(getComputedStyle(grid).getPropertyValue('--chat-height'), 10) || COMPACT_HEIGHT;
            handle.classList.add('dragging');
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

        // CLAUDE-P40-VW7B: {kind, id, displayName} per open division, not
        // a bare source id - generalized once Investigations/Overview
        // joined Documents as projectable record kinds (see
        // populateDivision below). Backward-compatible: a plain string
        // entry from a session saved before this stage is treated as
        // {kind:'source', id: <string>} on restore, the same "honest
        // mapping, no reinterpretation" pattern VW4's own
        // normalizeStoredLayout already established for a different
        // stored shape.
        function saveOpenDivisions() {
            const open = [];
            for (let i = 1; i < MAX_DISPLAY_DIVISIONS; i++) {
                const division = document.getElementById(`display-division-${i}`);
                if (division && division.dataset.kind) {
                    open.push({
                        kind: division.dataset.kind,
                        id: division.dataset.recordId || '',
                        displayName: division.dataset.displayName || '',
                    });
                }
            }
            try { window.sessionStorage.setItem(openDivisionsKey, JSON.stringify(open)); } catch (e) { /* ignore */ }
        }

        // CLAUDE-P40-VW7B: which Lists leaves this function itself most
        // recently marked .active for a non-zero division's content -
        // tracked separately so clearing/repopulating a division can
        // safely remove exactly those, never a leaf's own server-
        // rendered .active state (division 0's real selection, from the
        // page's own navigation - untouched here under any
        // circumstance). Section 7: "Lists active-state communication
        // must remain understandable when several Displays show
        // different items" - every leaf whose record is CURRENTLY SHOWN
        // in ANY division (0 through 5) reads as active, not only the
        // one division 0 or the active target happens to hold.
        function cssEscapeValue(value) {
            return (window.CSS && CSS.escape) ? CSS.escape(value) : String(value).replace(/["\\]/g, '\\$&');
        }

        // CLAUDE-P40-VW8-QA1 (Governed Display Tab System sufficiency
        // review): the single registration point for every "singleton"
        // kind - a Project-level record with no real file of its own,
        // embedded via the &panel=1 iframe route (buildPanelUrl) rather
        // than a plain <img>/<iframe src=file_url> the way a Document
        // ('source') is. Before this stage, buildPanelUrl, populateDivision,
        // and syncListsActiveState each had their own independent kind ===
        // 'case' / 'overview' / 'new-case' chain - three places that had to
        // be kept in sync by hand, and syncListsActiveState's own final
        // fallback (`: 'a[data-view="overview"]'`) applied to ANY
        // unrecognized kind, not only 'overview' - a real latent bug
        // (an unknown future kind would have silently marked Overview's
        // own Lists leaf active instead of nothing). This table is what
        // those three functions now share - proven for real by
        // CLAUDE-P40-VW9's own 'files' entry below (see routes/
        // workspace.py's matching STABLE_DIRECTORY_KINDS registration):
        // one new entry here, not three independently-maintained
        // branches.
        const PANEL_KINDS = {
            case: {
                buildQuery: (url, id) => { url.searchParams.set('case', id); },
                listsSelector: (id) => `a[data-case-id="${cssEscapeValue(id)}"]`,
            },
            overview: {
                buildQuery: (url) => { url.searchParams.set('view', 'overview'); },
                listsSelector: () => 'a[data-view="overview"]',
            },
            // CLAUDE-P40-VW8-QA (New Investigation Action in Lists): same
            // vocabulary, same route, same &panel=1 mechanism -
            // routes/workspace.py's own show_new_case_form reads this
            // exact ?view=new-case value.
            'new-case': {
                buildQuery: (url) => { url.searchParams.set('view', 'new-case'); },
                listsSelector: () => 'a[data-new-case]',
            },
            // CLAUDE-P40-VW9 (Governed Files Display and Project File
            // Architecture): the first real second stable-surface kind
            // registered here since VW8-QA1 built this table - exactly
            // the extension point it was built for. Same shape as
            // 'overview' (a Project-level singleton, no per-instance id).
            files: {
                buildQuery: (url) => { url.searchParams.set('view', 'files'); },
                listsSelector: () => 'a[data-view="files"]',
            },
        };

        let clientManagedActiveLeaves = [];
        function syncListsActiveState() {
            const listsRoot = document.querySelector('[data-tree-root]');
            if (!listsRoot) return;
            clientManagedActiveLeaves.forEach((el) => el.classList.remove('active'));
            clientManagedActiveLeaves = [];
            for (let i = 1; i < MAX_DISPLAY_DIVISIONS; i++) {
                const division = document.getElementById(`display-division-${i}`);
                if (!division || !division.dataset.kind) continue;
                const kind = division.dataset.kind;
                const id = division.dataset.recordId || '';
                const panelKind = PANEL_KINDS[kind];
                const selector = kind === 'source' ? `a[data-source-id="${cssEscapeValue(id)}"]`
                    : panelKind ? panelKind.listsSelector(id)
                    : null;
                if (!selector) continue;
                listsRoot.querySelectorAll(selector).forEach((el) => {
                    if (!el.classList.contains('active')) {
                        el.classList.add('active');
                        clientManagedActiveLeaves.push(el);
                    }
                });
            }
        }

        function clearDivision(divisionIndex) {
            const division = document.getElementById(`display-division-${divisionIndex}`);
            if (!division) return;
            division.classList.remove('display-division-populated', 'active');
            delete division.dataset.kind;
            delete division.dataset.recordId;
            delete division.dataset.displayName;
            const contentEl = division.querySelector('.display-division-content');
            if (contentEl) { contentEl.innerHTML = ''; contentEl.hidden = true; }
            const picker = division.querySelector('.display-division-picker');
            if (picker) picker.value = '';
            saveOpenDivisions();
            syncListsActiveState();
        }

        // Mirrors routes/workspace.py's own ?case=/?view=overview
        // vocabulary exactly - &panel=1 is the one addition (see that
        // route's own panel_only comment and templates/panel_shell.html).
        function buildPanelUrl(kind, id) {
            const url = new URL(window.location.href);
            url.search = '';
            const panelKind = PANEL_KINDS[kind];
            if (panelKind) panelKind.buildQuery(url, id);
            url.searchParams.set('panel', '1');
            return url.toString();
        }

        // CLAUDE-P40-VW7B: generalized from Documents-only to also
        // project Investigations/Overview - a Document is a real file
        // (embedded via a plain <img>/<iframe src=file_url>, unchanged
        // below); an Investigation/Overview is not, so its content is
        // instead embedded via an <iframe> pointing back at this same
        // Workspace route with &panel=1, rendering the exact same
        // Division-0 content this page already knows how to show, just
        // wrapped in panel_shell.html instead of the full application
        // shell (see routes/workspace.py's panel_only comment).
        // CLAUDE-P40-VW8 (Governed Display Tab System - distinct from the
        // earlier, already-shipped "CLAUDE-P40-VW8"/"CLAUDE-P40-VW8-QA"
        // stage this same file's own comments above reference; the tag is
        // reused because that is what this stage's own governing prompt
        // specifies, flagged here per this repo's own established
        // discipline for tag collisions - see git log a61a7b8/9a5c11b and
        // investigation_attention.js's own header comment for the prior
        // "CLAUDE-P40-VW7B" collision this exact pattern already covers).
        // Section 9's reserved extension point: 'kind' here is this app's
        // real, governing tab-identity vocabulary - 'source' (Document,
        // embedded as a real file below) and whatever is registered in
        // PANEL_KINDS above (Investigation, Overview, New Investigation,
        // and - as of CLAUDE-P40-VW9 - Files) are the only REAL kinds
        // implemented. Files itself has no picker entry (it is not a
        // Documents-shaped per-instance list) - it registers exactly one
        // PANEL_KINDS entry, same as Overview, and is reachable from
        // Lists/multi-Display the identical way Overview already was.
        // The two Files roots (Data Room/Design-Builder Workspace) are
        // NOT separate 'kind' values - they are both rendered inside the
        // one 'files' surface's own content (see case_workspace.html's
        // own `directory_view == 'files'` branch), the same way Overview's
        // many internal sections all live under the one 'overview' kind.
        function populateDivision(divisionIndex, kind, id, displayName, persist) {
            const division = document.getElementById(`display-division-${divisionIndex}`);
            if (!division) return;
            const nameEl = division.querySelector('.display-division-header-name');
            const contentEl = division.querySelector('.display-division-content');
            if (!contentEl) return;

            if (kind === 'source') {
                const source = sourcesById[id];
                if (!source) return;
                displayName = source.name;
                contentEl.textContent = '';
                if (source.kind === 'drawing') {
                    // CLAUDE-MM4 Section 8: a comparison Display division
                    // is a direct DOM insertion into THIS SAME page (never
                    // an <iframe> - unlike the PANEL_KINDS branch below) -
                    // so mounting static/js/drawing_image_viewer.js on
                    // this specific <img> gives this division its OWN
                    // independent rotate/mirror/zoom/pan/region state,
                    // exactly like the primary document pane's own
                    // instance, never sharing state with it.
                    const img = document.createElement('img');
                    img.className = 'document-viewer-image';
                    img.src = source.file_url;
                    img.alt = source.name;
                    img.dataset.sourceId = source.id;
                    img.dataset.projectId = projectId;
                    contentEl.appendChild(img);
                    if (window.ArchioskDrawingImageViewer) window.ArchioskDrawingImageViewer.mount(img);
                } else {
                    const frame = document.createElement('iframe');
                    frame.src = source.file_url;
                    frame.title = source.name;
                    contentEl.appendChild(frame);
                }
            } else if (PANEL_KINDS[kind]) {
                contentEl.textContent = '';
                const frame = document.createElement('iframe');
                frame.src = buildPanelUrl(kind, id);
                frame.title = displayName || (kind === 'overview' ? 'Overview' : '');
                contentEl.appendChild(frame);
            } else {
                return;
            }

            if (nameEl) nameEl.textContent = displayName || '';
            contentEl.hidden = false;
            division.classList.add('display-division-populated');
            division.dataset.kind = kind;
            division.dataset.recordId = id || '';
            division.dataset.displayName = displayName || '';
            if (persist !== false) saveOpenDivisions();
            syncListsActiveState();
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
            // CLAUDE-P40-VW7B: generalized from (index, sourceId) to
            // (index, kind, id, displayName) - kind is 'source'
            // (Documents, unchanged real-file embedding) or 'case'/
            // 'overview' (Investigations/Overview, embedded via the new
            // &panel=1 iframe route - see populateDivision's own
            // comment above).
            populateDivision: (index, kind, id, displayName) => populateDivision(index, kind, id, displayName, true),
            clearDivision: (index) => clearDivision(index),
            getDivisionRecord: (index) => {
                const division = document.getElementById(`display-division-${index}`);
                if (!division || !division.dataset.kind) return undefined;
                return { kind: division.dataset.kind, id: division.dataset.recordId || '' };
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

        // Restore whatever was open before the last navigation or
        // refresh (Section 6.7/6.8 - "restore the same projection") -
        // any real navigation within this Project must not silently
        // lose the rest of a split view someone was actively using.
        // Presentation state only (sessionStorage) - never a Project/
        // Document write (Section 6's boundary).
        let storedLayout = null;
        try { storedLayout = JSON.parse(window.localStorage.getItem(layoutKey) || 'null'); } catch (e) { /* ignore */ }
        const normalizedLayout = normalizeStoredLayout(storedLayout);
        applyLayout(normalizedLayout.vertical, normalizedLayout.horizontal, false);

        let storedTarget = null;
        try { storedTarget = parseInt(window.sessionStorage.getItem(targetKey), 10); } catch (e) { /* ignore */ }
        setActiveTarget(Number.isInteger(storedTarget) && storedTarget < quantity ? storedTarget : 0);

        let savedOpen = [];
        try { savedOpen = JSON.parse(window.sessionStorage.getItem(openDivisionsKey) || '[]'); } catch (e) { /* ignore */ }
        savedOpen.forEach((entry, idx) => {
            if (idx >= MAX_DISPLAY_DIVISIONS - 1) return;
            // Backward compatibility: a plain string entry, saved by a
            // session from before CLAUDE-P40-VW7B generalized this
            // beyond Documents, is a bare source id - same "honest
            // mapping, no reinterpretation" pattern VW4's own
            // normalizeStoredLayout already established for a
            // different stored shape.
            const normalized = typeof entry === 'string' ? { kind: 'source', id: entry, displayName: '' } : entry;
            if (!normalized || !normalized.kind) return;
            if (normalized.kind === 'source') {
                if (sourcesById[normalized.id]) populateDivision(idx + 1, 'source', normalized.id, sourcesById[normalized.id].name, false);
            } else if (PANEL_KINDS[normalized.kind]) {
                populateDivision(idx + 1, normalized.kind, normalized.id, normalized.displayName, false);
            }
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
    const conversationScopeForDraft = draftInput ? draftInput.dataset.conversationDraft : null;
    if (draftInput) {
        const draftKey = `beehive:conversation:draft:${conversationScopeForDraft}`;
        const savedDraft = window.sessionStorage.getItem(draftKey);
        if (savedDraft) draftInput.value = savedDraft;
        draftInput.addEventListener('input', () => {
            if (draftInput.value) window.sessionStorage.setItem(draftKey, draftInput.value);
            else window.sessionStorage.removeItem(draftKey);
        });
        // CLAUDE-CA1C-UX-FIX-01: mark this scope "just sent" right before the
        // full-page-reload POST fires, so the very next DOMContentLoaded
        // (this same code, on the reloaded page) knows to land on the newest
        // exchange rather than restore whatever mid-history scroll position
        // happened to be saved from before this send - "after the user
        // themselves sends a new message, return them to the newest
        // exchange" is a real product requirement, not the general
        // navigation-preserving case this sessionStorage restore mechanism
        // otherwise exists for (see the scroll-restore block below).
        draftInput.closest('form').addEventListener('submit', () => {
            window.sessionStorage.removeItem(draftKey);
            if (conversationScopeForDraft) {
                window.sessionStorage.setItem(`beehive:conversation:justSent:${conversationScopeForDraft}`, '1');
            }
        });
    }

    // CLAUDE-CA1C-UX-FIX-01: root cause of the live-reported "conversation
    // starts too high, scrolls down, stops short of the newest exchange"
    // defect - routes/workspace.py used to redirect back here with a
    // "#conversation-dock" fragment, which triggered the BROWSER'S OWN
    // native anchor-scroll (targeting this sticky, bottom-pinned panel's
    // own top edge - not the newest message) racing against this exact
    // block's own scrollTop assignment, on a container with `scroll-
    // behavior: smooth` (main.css) - two competing smooth-scrolls settling
    // wherever the last one happened to finish. That fragment is gone now
    // (it was already vestigial - the hash-driven "open the collapsed
    // ancestor" logic above only matches `details.accordion-section`, and
    // this dock has been a plain, always-open <div> since P40-E2B). This
    // block is now the SOLE owner of this container's scroll position.
    const conversationThread = document.querySelector('.conversation-thread[data-conversation-scope]');
    if (conversationThread) {
        const scope = conversationThread.dataset.conversationScope;
        const scrollKey = `beehive:conversation:scroll:${scope}`;
        const justSentKey = `beehive:conversation:justSent:${scope}`;
        // How close to the bottom (in px) counts as "the reviewer was
        // already following the newest messages" - a decision threshold
        // for CHOOSING to auto-follow, not a scroll destination in itself,
        // so this isn't the "arbitrary hard-coded pixel offset" the fix
        // needs to avoid (the actual destination is always computed from
        // the live scrollHeight/clientHeight below, never a fixed number).
        const NEAR_BOTTOM_TOLERANCE_PX = 48;

        const justSent = window.sessionStorage.getItem(justSentKey) === '1';
        window.sessionStorage.removeItem(justSentKey);

        const applyScrollPosition = () => {
            if (justSent) {
                conversationThread.scrollTop = conversationThread.scrollHeight;
                return;
            }
            const saved = window.sessionStorage.getItem(scrollKey);
            if (!saved) {
                // First-ever view of this scope this session - show the
                // newest exchange, not the (empty) top of history.
                conversationThread.scrollTop = conversationThread.scrollHeight;
                return;
            }
            let distanceFromBottom = null;
            try {
                const parsed = JSON.parse(saved);
                distanceFromBottom = typeof parsed.distanceFromBottom === 'number' ? parsed.distanceFromBottom : null;
            } catch (err) {
                // Pre-fix sessions stored a bare scrollTop number, not JSON -
                // fall through to the legacy-format branch below.
            }
            if (distanceFromBottom !== null) {
                if (distanceFromBottom <= NEAR_BOTTOM_TOLERANCE_PX) {
                    // Was already following along near the bottom - keep
                    // following the (now possibly taller) newest content,
                    // exactly like a reviewer watching a live thread would
                    // expect, rather than freezing at a stale offset.
                    conversationThread.scrollTop = conversationThread.scrollHeight;
                } else {
                    // A deliberate mid-history read - restore it relative to
                    // the CURRENT scrollHeight, so genuine navigation (not a
                    // send) preserves where they actually were.
                    conversationThread.scrollTop = Math.max(
                        0,
                        conversationThread.scrollHeight - conversationThread.clientHeight - distanceFromBottom
                    );
                }
            } else {
                conversationThread.scrollTop = parseInt(saved, 10) || conversationThread.scrollHeight;
            }
        };

        // Scroll only once this reload's layout has actually settled (text
        // wrapping/fonts) - a double rAF waits for the next two painted
        // frames rather than guessing a fixed delay, so this never races
        // layout regardless of how long it takes to finish.
        window.requestAnimationFrame(() => window.requestAnimationFrame(applyScrollPosition));

        conversationThread.addEventListener('scroll', () => {
            const distanceFromBottom = conversationThread.scrollHeight - conversationThread.scrollTop - conversationThread.clientHeight;
            window.sessionStorage.setItem(scrollKey, JSON.stringify({ distanceFromBottom }));
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

    // CLAUDE-POSTCAMEL-VOICE1-PRE: Push-to-Talk voice input - "the
    // microphone is merely another door into ARCHIOSK Go." Deliberately
    // uses the browser's own built-in SpeechRecognition (Web Speech
    // API) rather than a hosted transcription provider: this stage's
    // own governing prompt required either a real Product Owner
    // decision (vendor, API key, cost) or a path that needs none - the
    // browser-native API is the only option that needs neither, so it
    // is what VOICE1-PRE actually implements (see the governance record
    // for the full provider audit and the adapter boundary this choice
    // preserves for a future hosted-provider swap).
    //
    // Deliberately minimal: no manual getUserMedia/MediaRecorder/audio-
    // blob handling anywhere in this file - SpeechRecognition captures
    // and discards its own internal audio entirely inside the browser
    // and only ever hands this code a text transcript. There is no
    // audio blob here to accidentally persist (Section 5's own
    // "transient audio, discard after transcription" requirement is
    // satisfied by construction, not by remembering to delete a file).
    //
    // Never auto-submits: the transcript only ever fills the existing
    // #dock-composer-input field, exactly as if the reviewer had typed
    // it - the PM still reviews/edits and clicks the real Send button
    // themselves (Section 6, review-before-send). Every existing hidden
    // field (anchor/current_view/selected_source_id) on the same <form>
    // is submitted unchanged, so voice inherits the exact same Project
    // context, selection, and permission path text already has - never
    // a second conversational system.
    (function setUpVoiceInput() {
        const micButton = document.getElementById('dock-composer-voice');
        const composerInput = document.getElementById('dock-composer-input');
        const statusEl = document.getElementById('dock-composer-voice-status');
        if (!micButton || !composerInput) return;

        const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognitionCtor) {
            // Graceful degradation (Section 8): unsupported browser -
            // the button stays hidden (its own default state), typing
            // remains the only, fully-equivalent input path. Nothing to
            // show here - there is no button to press in the first place.
            return;
        }

        micButton.hidden = false;

        // CLAUDE-VOICE1-LIVE-FIX-01: a real Product Owner pressed the mic
        // in their own browser and saw NOTHING - not an error, not a
        // "listening" indicator, nothing - because the previous version of
        // this code (see git history) swallowed every outcome into a bare
        // stopListening() with no visible trace. "Silent failure is
        // unacceptable" (this stage's own governing instruction). Every
        // reachable outcome now sets one line of real, specific text via
        // setStatus - never left to the reviewer to guess at.
        function setStatus(message, isError) {
            if (!statusEl) return;
            statusEl.textContent = message || '';
            if (isError) statusEl.setAttribute('data-state', 'error');
            else statusEl.removeAttribute('data-state');
        }

        // event.error values a real SpeechRecognition implementation uses
        // (https://wicg.github.io/speech-api/#speechreco-error) - mapped to
        // the specific, actionable wording this stage's governing prompt
        // requires, not a generic "something went wrong". "aborted" is
        // deliberately NOT in this map - it fires on our OWN recognition.stop()
        // call below (the Push-to-Talk release), which is normal operation,
        // not a failure to report as one.
        const ERROR_MESSAGES = {
            'not-allowed': 'Microphone permission denied',
            'service-not-allowed': 'Microphone permission denied',
            'permission-denied': 'Microphone permission denied',
            'audio-capture': 'No microphone available',
            'no-speech': 'No speech detected',
            'network': 'Speech recognition unavailable in this browser',
            'language-not-supported': 'Speech recognition unavailable in this browser',
        };

        let recognition = null;
        let listening = false;
        let userInitiatedStop = false;
        let gotFinalResult = false;

        function stopListening() {
            listening = false;
            micButton.classList.remove('voice-input-listening');
            micButton.setAttribute('aria-pressed', 'false');
        }

        // CLAUDE-VOICE1-LIVE-FIX-02: this build's own SpeechRecognition
        // exposes the real, standardized on-device extension - confirmed
        // live (available() genuinely resolves "downloadable" for en-US
        // here, install() genuinely exists and genuinely enforces its own
        // spec-required user-gesture check, not stubs). processLocally
        // means audio never leaves the device at all - strictly MORE
        // private than the previous implicit default (which this build,
        // like most Chrome installs, resolves to a server-based
        // recognizer unless explicitly told otherwise), and doesn't
        // depend on whatever network path was the leading suspect behind
        // "detects speech, returns nothing" (this stage's own prior
        // finding). Feature-detected, not assumed - a browser without
        // this extension (any non-Chromium engine, or an older Chrome)
        // takes the `hasOnDeviceApi` false branch below and behaves
        // exactly as before this stage.
        const hasOnDeviceApi = typeof SpeechRecognitionCtor.available === 'function'
            && typeof SpeechRecognitionCtor.install === 'function';

        // Resolves true if the caller should proceed with
        // `recognition.processLocally = true`, false to fall back to this
        // engine's own implicit default (never blocks the mic entirely on
        // a capability-detection failure - Section 8's own graceful-
        // degradation ethos). Must be called synchronously from within
        // the real click handler's own call stack up to its first
        // `await` - install() enforces "handling a user gesture" itself
        // (confirmed live: it throws NotAllowedError without one), so
        // this cannot be deferred or pre-fetched earlier.
        async function ensureOnDeviceReady(lang) {
            if (!hasOnDeviceApi) return false;
            let state;
            try {
                state = await SpeechRecognitionCtor.available({ langs: [lang], processLocally: true });
            } catch (err) {
                return false;
            }
            if (state === 'available') return true;
            if (state === 'unavailable') return false;
            // "downloadable" or "downloading" - install() is idempotent
            // for an already-in-progress download per its own spec.
            setStatus('Downloading speech model…', false);
            try {
                return await SpeechRecognitionCtor.install({ langs: [lang] });
            } catch (err) {
                return false;
            }
        }

        function beginListening(useOnDevice) {
            recognition = new SpeechRecognitionCtor();
            recognition.lang = document.documentElement.lang || 'en-US';
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;
            if (useOnDevice) recognition.processLocally = true;

            // onstart/onaudiostart confirm the browser actually opened the
            // microphone (distinct from onspeechstart, which needs a real
            // voice-shaped signal, not just an open mic) - kept as a single
            // "Listening…" message rather than three near-identical ones,
            // since the reviewer only needs to know capture has begun.
            recognition.addEventListener('speechstart', () => {
                setStatus('Transcribing…', false);
            });

            recognition.addEventListener('result', (event) => {
                let transcript = '';
                for (let i = 0; i < event.results.length; i += 1) {
                    transcript += event.results[i][0].transcript;
                    if (event.results[i].isFinal) gotFinalResult = true;
                }
                composerInput.value = transcript;
                setStatus('Transcribing…', false);
            });

            recognition.addEventListener('error', (event) => {
                if (event.error === 'aborted' && userInitiatedStop) {
                    setStatus('Recognition stopped', false);
                } else {
                    setStatus(ERROR_MESSAGES[event.error] || 'Speech recognition unavailable in this browser', true);
                }
                stopListening();
            });

            recognition.addEventListener('end', () => {
                stopListening();
                // A clean end with no error already shown and no speech
                // ever recognized (the exact "detects sound but transcribes
                // nothing" case this stage's own diagnosis reproduced) is
                // still a real, reportable outcome - not silence.
                if (!gotFinalResult && (!statusEl || !statusEl.getAttribute('data-state'))) {
                    setStatus(userInitiatedStop ? 'Recognition stopped' : 'No speech detected', !userInitiatedStop);
                } else if (gotFinalResult) {
                    setStatus('', false);
                }
                composerInput.focus();
            });

            try {
                recognition.start();
                listening = true;
                micButton.classList.add('voice-input-listening');
                micButton.setAttribute('aria-pressed', 'true');
                setStatus('Listening…', false);
            } catch (err) {
                stopListening();
                setStatus('Speech recognition unavailable in this browser', true);
            }
        }

        micButton.addEventListener('click', async () => {
            if (listening) {
                // Push-to-Talk, not push-to-toggle-forever: a second
                // press stops listening early, same as releasing a
                // physical push-to-talk button - not a failure, so
                // "aborted" (fired by this same .stop() call, below) must
                // not be reported as one.
                userInitiatedStop = true;
                if (recognition) recognition.stop();
                stopListening();
                return;
            }

            userInitiatedStop = false;
            gotFinalResult = false;
            setStatus('Listening…', false);

            const lang = document.documentElement.lang || 'en-US';
            const useOnDevice = await ensureOnDeviceReady(lang);
            // A press-and-release before the (usually near-instant, but
            // occasionally slow on first-ever install) availability check
            // resolves must not start a session the reviewer already
            // abandoned - `listening` only flips true inside
            // beginListening() itself, so a stop click that arrived during
            // this await already reset the button/status and this simply
            // no-ops instead of starting late.
            if (userInitiatedStop) return;
            beginListening(useOnDevice);
        });
    })();

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
    //
    // CLAUDE-P40-VW8-QA (native-popup-overlap correction): a browser or
    // OS text-selection popup (most identifiably Microsoft Edge's own
    // "mini menu on text selection" - edge://settings/appearance's
    // "Show mini menu when I select text" toggle, or the
    // QuickSearchShowMiniMenu enterprise policy in a managed
    // deployment) is NOT something this page creates, can detect
    // reliably, or can resize/reposition/merge/restyle - the browser
    // owns its size and placement, and no web-page API exposes either.
    // This code deliberately does not attempt browser sniffing or a
    // "disable the native popup" preference (both explicitly rejected
    // by the product owner - the first is unreliable, the second would
    // be misleading, since a page can't actually make that promise).
    // The only thing on this side of the boundary Archiosk can and does
    // control: (1) never suppressing the native context menu for text
    // selection - no contextmenu listener exists anywhere in this
    // toolbar's own setup, unlike the unrelated Display-division one
    // elsewhere in this file; (2) positioning ITS OWN menu on the
    // opposite side of the selection from where that popup
    // conventionally appears (positionToolbar below now prefers BELOW
    // the selection, not above); (3) making its own Copy action fully
    // self-sufficient (doCopy below copies the complete captured
    // selection text, not a partial value) so a reviewer never NEEDS
    // the native popup for ordinary copying. Any remaining overlap in a
    // specific browser/profile is a native-UI placement decision that
    // only that browser's own setting can change - not a defect in this
    // page.
    (function setUpConversationTagsAndTasks() {
        const toolbar = document.getElementById('conv-selection-toolbar');
        const statusEl = document.getElementById('conv-selection-status');
        const tagDialog = document.getElementById('conv-tag-dialog');
        const taskDialog = document.getElementById('conv-task-dialog');
        const removeTagDialog = document.getElementById('conv-remove-tag-dialog');
        const removeTagList = document.getElementById('conv-remove-tag-list');
        const undoBtn = document.getElementById('conv-selection-undo');
        if (!toolbar || !statusEl || !tagDialog || !taskDialog) return;

        const tagForm = document.getElementById('conv-tag-form');
        const taskForm = document.getElementById('conv-task-form');
        const removeTagBtn = toolbar.querySelector('[data-conv-action="remove-tag"]');
        const highlightBtn = toolbar.querySelector('[data-conv-action="highlight"]');
        const importantBtn = toolbar.querySelector('[data-conv-action="important"]');
        const questionBtn = toolbar.querySelector('[data-conv-action="question"]');

        // Mirrors services/case_workspace.py's own BUILT_IN_TAG_* string
        // constants exactly - these three are fixed code-level identities
        // on the server (never stored per-project), so the client only
        // ever needs to know their literal ids, not fetch them.
        const BUILT_IN_TAG_IMPORTANT = 'built-in:important';
        const BUILT_IN_TAG_QUESTION = 'built-in:question';
        const BUILT_IN_TAG_HIGHLIGHT = 'built-in:highlight';

        // CLAUDE-CA1D-RIVER-03 (Make the River Visible): a real Product
        // Owner could not discover this whole toolbar through ordinary
        // use, despite it being fully implemented (CA1D-RIVER-01's own
        // audit) - macros.operational_action_offers renders a server-
        // hidden #conv-selection-hint next to a genuinely actionable
        // answer (never a permanent toolbar - only appears where the
        // fourth beat itself already appears). Revealed here, once,
        // whenever this browser has never actually used the toolbar
        // before; hidden for good - and the localStorage flag set - the
        // very first time a real selection actually opens it (below,
        // inside handleSelectionMaybeChanged) - "once learned, quiet
        // again," never re-coaching an experienced reviewer. A single
        // global flag (not per-project): the mechanism itself is not
        // project-specific, so neither is having learned it.
        const SELECTION_HINT_SEEN_KEY = 'beehive:selectionHintSeen';
        function markSelectionHintLearned() {
            try { window.localStorage.setItem(SELECTION_HINT_SEEN_KEY, '1'); } catch (e) { /* ignore */ }
            document.querySelectorAll('.conv-selection-hint').forEach((el) => { el.hidden = true; });
        }
        (function revealSelectionHintIfNeverLearned() {
            let alreadyLearned = false;
            try { alreadyLearned = window.localStorage.getItem(SELECTION_HINT_SEEN_KEY) === '1'; } catch (e) { alreadyLearned = false; }
            if (alreadyLearned) return;
            document.querySelectorAll('.conv-selection-hint').forEach((el) => { el.hidden = false; });
        })();

        let currentAnchor = null; // last computed anchor (or {ambiguous:true,...}), from the most recent meaningful selection
        let currentQuoteText = '';
        let pendingAnchor = null; // anchor captured at the moment a dialog opened - selection may already be gone by submit time
        let dialogTriggerEl = null;
        let statusHideTimer = null;
        let selectionDebounce = null;
        // CLAUDE-P40-VW8-QA (reversibility correction): every Tag
        // occurrence currently overlapping the selection that produced
        // currentAnchor (built-in or custom) - the read side of
        // routes/workspace.py's own tag_occurrences_for_selection_route,
        // refreshed on every meaningful selection change. appliedFetchToken
        // guards against a slow/late response from an OLD selection
        // overwriting state after the reviewer has already moved on to a
        // new one (a plain "last response wins" race without it).
        let currentAppliedTags = [];
        let appliedFetchToken = 0;
        let undoHideTimer = null;
        let pendingUndo = null; // { anchorFields, label } captured at removal time

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
            currentAppliedTags = [];
            // Undo is deliberately NOT hidden here - a reviewer who
            // clicks away immediately after a removal (a very ordinary
            // thing to do) should still get the full Undo window; it
            // times out on its own (see showUndoableStatus).
        }

        function dialogOpen() {
            return !tagDialog.hidden || !taskDialog.hidden || (removeTagDialog && !removeTagDialog.hidden);
        }

        // -------- Reversibility (CLAUDE-P40-VW8-QA correction) ------------
        // "Anything the user can tag, classify, or highlight must have a
        // clear way to remove that application later." Highlight/
        // Important/Question are themselves just built-in Tags (see
        // BUILT_IN_TAG_* above and services/case_workspace.py's own
        // BUILT_IN_TAGS) - one removal mechanism (the existing /tags/
        // <occurrence_id>/remove route, already used by the Lists Tags
        // branch's own "Remove" button) covers all of them. Nothing here
        // is a second Tag/Highlight/Important/Question system.

        function undoUrl() { return tagForm.action; } // POST .../workspace/tags - same endpoint Add Tag already uses

        function appliedTagsUrl(anchor) {
            const params = new URLSearchParams(anchorFormFields(anchor));
            return `${window.location.pathname.replace(/\/$/, '')}/tags/for-selection?${params.toString()}`;
        }

        // Refetches which Tags currently overlap `anchor` and updates the
        // toolbar's own button states (Remove Tag count, Highlight/
        // Important/Question -> their "remove" state) - called after
        // every meaningful selection change AND after every successful
        // add/remove so the toolbar never shows a stale applied state.
        function refreshAppliedTagState(anchor) {
            if (!anchor || anchor.ambiguous) { applyAppliedTagState([]); return; }
            const token = ++appliedFetchToken;
            fetch(appliedTagsUrl(anchor), { credentials: 'same-origin' })
                .then((resp) => resp.json())
                .then((data) => {
                    if (token !== appliedFetchToken) return; // a newer selection/refresh has already superseded this request
                    applyAppliedTagState((data && data.ok && data.applied) || []);
                })
                .catch(() => { /* leave whatever state was last known - a failed background refresh must not make the toolbar flicker or lie */ });
        }

        function applyAppliedTagState(applied) {
            currentAppliedTags = applied;
            const byTagId = {};
            applied.forEach((item) => { byTagId[item.tag_id] = item; });

            function setBuiltinButtonState(btn, tagId, addLabel, addRef, removeLabel, removeRef, removeAction) {
                if (!btn) return;
                const item = byTagId[tagId];
                if (item) {
                    btn.dataset.convAction = removeAction;
                    btn.setAttribute('data-ui-ref', removeRef);
                    btn.textContent = removeLabel;
                    btn.dataset.occurrenceId = item.occurrence_id;
                } else {
                    btn.dataset.convAction = addLabel.action;
                    btn.setAttribute('data-ui-ref', addRef);
                    btn.textContent = addLabel.text;
                    delete btn.dataset.occurrenceId;
                }
            }
            setBuiltinButtonState(highlightBtn, BUILT_IN_TAG_HIGHLIGHT,
                { action: 'highlight', text: 'Highlight' }, 'chat.selection-toolbar.highlight',
                'Remove Highlight', 'chat.selection-toolbar.remove-highlight', 'remove-highlight');
            setBuiltinButtonState(importantBtn, BUILT_IN_TAG_IMPORTANT,
                { action: 'important', text: 'Important' }, 'chat.selection-toolbar.important',
                'Unmark Important', 'chat.selection-toolbar.unmark-important', 'unmark-important');
            setBuiltinButtonState(questionBtn, BUILT_IN_TAG_QUESTION,
                { action: 'question', text: 'Question' }, 'chat.selection-toolbar.question',
                'Unmark Question', 'chat.selection-toolbar.unmark-question', 'unmark-question');

            const customTags = applied.filter((item) => item.tag_id !== BUILT_IN_TAG_HIGHLIGHT
                && item.tag_id !== BUILT_IN_TAG_IMPORTANT && item.tag_id !== BUILT_IN_TAG_QUESTION);
            if (removeTagBtn) {
                if (customTags.length > 0) {
                    removeTagBtn.hidden = false;
                    // Text alone (not color) identifies the applied count -
                    // "Do not rely on color alone" for state identification.
                    removeTagBtn.textContent = customTags.length === 1 ? 'Remove Tag' : `Remove Tag (${customTags.length})`;
                } else {
                    removeTagBtn.hidden = true;
                }
            }
        }

        // Finds the rendered <mark> for an occurrence, if this exact
        // occurrence happens to be the one app.py's own hotlinks filter
        // chose to draw (Section 11's "first-starting wins" overlap
        // resolution means it might not be - a no-op in that case, never
        // an error, since the underlying text is untouched either way).
        function unwrapTagMark(occurrenceId) {
            const mark = document.querySelector(`mark.tag-highlight-inline[data-tag-occurrence-id="${cssEscapeLocal(occurrenceId)}"]`);
            if (mark && mark.parentNode) mark.replaceWith(document.createTextNode(mark.textContent));
        }
        function cssEscapeLocal(value) {
            return (window.CSS && CSS.escape) ? CSS.escape(value) : String(value).replace(/["\\]/g, '\\$&');
        }

        function showUndoableStatus(message, undo) {
            showStatus(message, false);
            window.clearTimeout(undoHideTimer);
            if (undo && undoBtn) {
                pendingUndo = undo;
                undoBtn.hidden = false;
                undoHideTimer = window.setTimeout(() => { undoBtn.hidden = true; pendingUndo = null; }, 8000);
            } else if (undoBtn) {
                undoBtn.hidden = true;
                pendingUndo = null;
            }
            window.clearTimeout(statusHideTimer);
            statusHideTimer = window.setTimeout(hideStatus, 8000);
        }

        if (undoBtn) {
            undoBtn.addEventListener('click', () => {
                if (!pendingUndo) return;
                const undo = pendingUndo;
                pendingUndo = null;
                undoBtn.hidden = true;
                undoBtn.disabled = true;
                postForm(undoUrl(), undo.fields).then(({ ok, data }) => {
                    undoBtn.disabled = false;
                    if (!ok || !data.ok) {
                        showStatus((data && data.error) || 'Could not undo.', true);
                        return;
                    }
                    patchTagsListOnAdd(data.occurrence, data.tag, data.counts);
                    showStatus(`Restored ${undo.label}.`, true);
                    if (currentAnchor) refreshAppliedTagState(currentAnchor);
                });
            });
        }

        // The one place a Tag/Highlight/Important/Question occurrence is
        // ever removed from - the Lists "Remove" form submit handler
        // (further below) and every selection-toolbar removal action
        // both route through this, exactly the same "single place a
        // state is ever applied" discipline setSurfaceMode established
        // for Appearance. Guards against duplicate requests via the
        // caller-supplied button's own [disabled] state.
        let removalInFlight = false;
        function removeOccurrenceWithUndo(btn, occurrenceId, tagId, tagName, anchorForUndo) {
            if (removalInFlight) return; // "Prevent duplicate removal requests"
            removalInFlight = true;
            if (btn) btn.disabled = true;
            postForm(removeOccurrenceUrl(occurrenceId), {}).then(({ ok, data }) => {
                removalInFlight = false;
                if (btn) btn.disabled = false;
                if (!ok || !data.ok) {
                    showStatus((data && data.error) || 'Could not remove.', true);
                    return;
                }
                unwrapTagMark(occurrenceId);
                patchTagsListOnRemove(occurrenceId, tagId, data.counts);
                const undoFields = anchorForUndo
                    ? Object.assign({ tag_id: tagId }, anchorFormFields(anchorForUndo))
                    : null;
                showUndoableStatus(`Removed ${tagName}.`, undoFields ? { fields: undoFields, label: tagName } : null);
                if (currentAnchor) refreshAppliedTagState(currentAnchor);
                const row = removeTagList && removeTagList.querySelector(`[data-occurrence-id="${cssEscapeLocal(occurrenceId)}"]`);
                if (row) row.remove();
                if (removeTagList && !removeTagList.children.length && removeTagDialog && !removeTagDialog.hidden) {
                    closeDialog(removeTagDialog);
                }
            }).catch(() => {
                removalInFlight = false;
                if (btn) btn.disabled = false;
                showStatus('Network error \u2014 please try again.', true);
            });
        }

        function populateRemoveTagDialog(anchor) {
            if (!removeTagList) return;
            removeTagList.textContent = '';
            const customTags = currentAppliedTags.filter((item) => item.tag_id !== BUILT_IN_TAG_HIGHLIGHT
                && item.tag_id !== BUILT_IN_TAG_IMPORTANT && item.tag_id !== BUILT_IN_TAG_QUESTION);
            customTags.forEach((item) => {
                const li = document.createElement('li');
                li.className = 'conv-remove-tag-row';
                li.setAttribute('data-occurrence-id', item.occurrence_id);
                const swatch = document.createElement('span');
                swatch.className = `launcher-tag-swatch conv-tag-color-${item.tag_color}`;
                swatch.setAttribute('aria-hidden', 'true');
                li.appendChild(swatch);
                const name = document.createElement('span');
                name.className = 'conv-remove-tag-name';
                name.textContent = item.tag_name; // text, not color alone, identifies which Tag this row removes
                li.appendChild(name);
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'link-button';
                removeBtn.textContent = 'Remove';
                removeBtn.addEventListener('click', () => {
                    removeOccurrenceWithUndo(removeBtn, item.occurrence_id, item.tag_id, item.tag_name, anchor);
                });
                li.appendChild(removeBtn);
                removeTagList.appendChild(li);
            });
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
            // Prefer BELOW the selection first, not above. The browser/
            // OS-owned selection popup (e.g. Edge's "mini menu on text
            // selection") conventionally appears above/beside the
            // selection start - defaulting Archiosk's own menu to the
            // opposite side keeps the two from contesting the same space
            // instead of visually overlapping (CLAUDE-P40-VW8-QA, native-
            // popup-overlap correction). Falls back to above, then to a
            // viewport-clamped position, exactly as before - only the
            // preferred side changed.
            let top = rect.bottom + margin;
            if (top + toolbar.offsetHeight > window.innerHeight - margin) {
                top = rect.top - toolbar.offsetHeight - margin;
            }
            if (top < margin) {
                top = Math.max(margin, window.innerHeight - toolbar.offsetHeight - margin);
            }
            let left = rect.left + (rect.width / 2) - (toolbar.offsetWidth / 2);
            left = Math.max(margin, Math.min(left, window.innerWidth - toolbar.offsetWidth - margin));
            toolbar.style.top = `${top}px`;
            toolbar.style.left = `${left}px`;
        }

        // A scroll or resize of any containing panel (the conversation
        // thread, <main>, or the window itself) leaves a fixed-position
        // toolbar stale at its old coordinates unless recomputed here -
        // it never had its own listener before this correction. Reuses
        // the LIVE selection's own rect rather than caching one, and
        // hides cleanly if the selection is gone by the time this runs.
        function repositionOrHideOnViewportChange() {
            if (toolbar.hidden) return;
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0 || sel.isCollapsed) { hideToolbar(); return; }
            const text = sel.toString();
            if (!text || !text.trim()) { hideToolbar(); return; }
            positionToolbar(sel.getRangeAt(0).getBoundingClientRect());
        }
        // capture:true - 'scroll' does not bubble, but IS dispatched
        // during the capture phase, so this is the only way a window-
        // level listener ever sees a scroll on an internal panel like
        // .conversation-thread or <main>.
        window.addEventListener('scroll', repositionOrHideOnViewportChange, true);
        window.addEventListener('resize', repositionOrHideOnViewportChange);

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
            refreshAppliedTagState(anchor);
            // CLAUDE-CA1D-RIVER-03: the toolbar genuinely opened for a
            // real selection - the reviewer has now demonstrably learned
            // this mechanism, whether or not they ever saw the hint text
            // (e.g. it wasn't rendered on this particular message).
            markSelectionHintLearned();
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
        // CLAUDE-P40-VW8-QA (reversibility correction): the toolbar stays
        // visible behind this dialog (unlike Add Tag/Make Task above,
        // which hide it) - removing a second, then a third Tag from the
        // same selection without the toolbar's own state having to be
        // rebuilt is a real, ordinary use of "remove one or more
        // individually," and closeDialog below already restores focus to
        // whichever button opened it.
        function openRemoveTagDialog(anchor, triggerEl) {
            dialogTriggerEl = triggerEl;
            populateRemoveTagDialog(anchor);
            showDialog(removeTagDialog);
        }

        document.querySelectorAll('[data-conv-dialog-cancel]').forEach((btn) => {
            btn.addEventListener('click', () => closeDialog(btn.closest('.conv-dialog')));
        });
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            if (!tagDialog.hidden) { closeDialog(tagDialog); return; }
            if (!taskDialog.hidden) { closeDialog(taskDialog); return; }
            if (removeTagDialog && !removeTagDialog.hidden) { closeDialog(removeTagDialog); return; }
            if (!toolbar.hidden) hideToolbar();
        });
        document.addEventListener('mousedown', (e) => {
            if (!tagDialog.hidden && !tagDialog.contains(e.target)) { closeDialog(tagDialog); return; }
            if (!taskDialog.hidden && !taskDialog.contains(e.target)) { closeDialog(taskDialog); return; }
            if (removeTagDialog && !removeTagDialog.hidden && !removeTagDialog.contains(e.target) && !toolbar.contains(e.target)) {
                closeDialog(removeTagDialog);
                return;
            }
            if (!toolbar.hidden && !toolbar.contains(e.target) && (!removeTagDialog || removeTagDialog.hidden)) {
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

        // CLAUDE-CA1D-RIVER-01 (the "fourth beat"): server-rendered
        // .conv-operational-action-form elements (macros.operational_
        // action_offers) post to these EXACT same create_task_route/
        // add_tag_occurrence_route endpoints, which only ever answer
        // JSON - a plain, un-intercepted form submission would navigate
        // the whole page to a bare JSON response. Delegated (not bound
        // by id) because a fresh one of these can render on every new
        // evidence-grounded answer, same reasoning as the Tag-removal
        // buttons' own delegated handler elsewhere in this file.
        //
        // CLAUDE-CA1D-RIVER-PO-02 (Eye/status-surface correction): this
        // used to ALSO call showStatus(...) - #conv-selection-status's
        // own CSS is `position: fixed; bottom: 1rem; right: 1rem`
        // (designed to sit near a live text selection's OWN toolbar,
        // which is what it was actually built for), not anywhere near
        // wherever THIS button happens to be clicked. In this app's own
        // 6-panel shell, that fixed viewport corner visually coincides
        // with the Eye pane's own screen region - a real Product Owner
        // report of "task-created feedback flashing in the Eye panel"
        // was this exact toast rendering on top of it, not any code
        // actually touching Eye. Eye is for seeing; Tasks are for doing -
        // feedback for a fourth-beat action now lives ONLY on the
        // button that was actually clicked (its own label changes, right
        // where the reviewer is already looking), never a floating
        // toast anchored to an unrelated part of the screen.
        document.addEventListener('submit', (e) => {
            const form = e.target.closest('.conv-operational-action-form');
            if (!form) return;
            e.preventDefault();
            const btn = form.querySelector('button[type="submit"]');
            const originalLabel = btn ? btn.textContent : '';
            if (btn) { btn.disabled = true; }
            const isTag = form.action.indexOf('/tags') !== -1;
            postForm(form.action, Object.fromEntries(new FormData(form))).then(({ ok, data }) => {
                if (!ok || !data.ok) {
                    if (btn) {
                        btn.disabled = false;
                        btn.title = (data && data.error) || 'Something went wrong.';
                        const previousLabel = btn.textContent;
                        btn.textContent = 'Error — try again';
                        window.setTimeout(() => { btn.textContent = previousLabel; }, 2500);
                    }
                    return;
                }
                if (isTag) {
                    patchTagsListOnAdd(data.occurrence, data.tag, data.counts);
                } else {
                    patchTasksListOnCreate(data.task, data.counts);
                }
                if (btn) { btn.textContent = isTag ? 'Tagged' : 'Task created'; }
            }).catch(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.title = 'Network error \u2014 please try again.';
                    btn.textContent = 'Error \u2014 try again';
                    window.setTimeout(() => { btn.textContent = originalLabel; }, 2500);
                }
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
            if (action === 'remove-tag') { openRemoveTagDialog(anchor, btn); return; }
            if (action === 'task') { openTaskDialog(anchor, quote, btn); return; }
            const removeBuiltIn = action === 'remove-highlight' ? { id: BUILT_IN_TAG_HIGHLIGHT, name: 'Highlight' }
                : action === 'unmark-important' ? { id: BUILT_IN_TAG_IMPORTANT, name: 'Important' }
                : action === 'unmark-question' ? { id: BUILT_IN_TAG_QUESTION, name: 'Question' } : null;
            if (removeBuiltIn) {
                const occurrenceId = btn.dataset.occurrenceId;
                if (!occurrenceId) return; // defensive - button only shows this action once an occurrence id is known
                removeOccurrenceWithUndo(btn, occurrenceId, removeBuiltIn.id, removeBuiltIn.name, anchor);
                return;
            }
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

        // CLAUDE-P40-VW8-QA (reversibility correction): the ONE place
        // Lists' own Tags branch gets patched after a removal - both the
        // Lists "Remove" form below AND the selection-toolbar's own
        // Remove Tag/Remove Highlight/Unmark Important/Unmark Question
        // actions (removeOccurrenceWithUndo, above) route through this,
        // rather than two divergent DOM-patching code paths.
        function patchTagsListOnRemove(occurrenceId, tagId, counts) {
            const countEl = document.getElementById('lists-tags-count');
            if (countEl) countEl.textContent = String(counts.total);
            const row = document.querySelector(`[data-tag-occurrence-id="${cssEscape(occurrenceId)}"]`);
            const group = (row && row.closest('[data-tag-group]')) || document.querySelector(`[data-tag-group="${cssEscape(tagId)}"]`);
            if (row) row.remove();
            if (group) {
                const remaining = counts.by_tag && counts.by_tag[tagId] != null ? counts.by_tag[tagId] : 0;
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
        }

        // Removal is wired via delegation so it uniformly covers both
        // server-rendered rows (present on page load) and rows this
        // script itself just inserted, without a second binding pass.
        document.addEventListener('submit', (e) => {
            const form = e.target.closest('[data-tag-remove-form]');
            if (!form) return;
            e.preventDefault();
            const occurrenceId = form.getAttribute('data-occurrence-id');
            const group = form.closest('[data-tag-group]');
            const tagId = group ? group.getAttribute('data-tag-group') : null;
            postForm(form.action, {}).then(({ ok, data }) => {
                if (!ok || !data.ok) {
                    showStatus((data && data.error) || 'Could not remove tag.', true);
                    return;
                }
                patchTagsListOnRemove(occurrenceId, tagId, data.counts);
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

    // -------- Work Product "Add a section" field grouping (CLAUDE-POSTCAMEL-P01) --------
    // Progressive enhancement only: every field group stays present and
    // POST-able with JavaScript disabled (templates/case_workspace.html's
    // own comment on this form explains why) - this purely hides the
    // groups that don't match the currently-selected section_type, so a
    // JS-enabled reviewer isn't shown risk/team-member/narrative fields
    // all at once and can't fill in a group that would otherwise be
    // silently discarded on save.
    document.querySelectorAll('[data-work-product-section-form]').forEach((form) => {
        const select = form.querySelector('[data-section-type-select]');
        const groups = form.querySelectorAll('[data-section-type-group]');
        if (!select || !groups.length) return;
        function applyVisibility() {
            groups.forEach((group) => {
                group.style.display = (group.getAttribute('data-section-type-group') === select.value) ? '' : 'none';
            });
        }
        select.addEventListener('change', applyVisibility);
        applyVisibility();
    });
});
