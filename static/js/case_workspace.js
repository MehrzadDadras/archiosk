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
    // class flip, same shape as nav-expanded in base.html. The badges
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
});
