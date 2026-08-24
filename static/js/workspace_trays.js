/* CLAUDE-MOBILE-FRAME-02 — the shared workspace-frame primitive.
 *
 * `governance/current/contracts/CIC-PANEL.md` has carried "There is no
 * common panel-state API" as a KNOWN LIMITATION since 2026-08-20, and
 * `panel-template-system.md`'s own audit summary named the same gap
 * ("a common panel-state API remain[s] future work"). This file is that
 * API. It is deliberately small, and it owns exactly three things that did
 * not exist before:
 *
 *   1. WHICH tray currently owns the work area  (`data-tray-focus`)
 *   2. WHETHER a layer is raised over it        (`data-tray-layer`)
 *   3. WHERE the work/Composer boundary sits on a phone (delegated)
 *
 * The Product Owner's mobile frame is three persistent zones:
 *
 *      TOP     fixed compact header - where am I, what am I working on
 *      MIDDLE  ONE active work tray - where the work happens
 *      BOTTOM  fixed Composer       - how I talk to GO
 *
 * Composer is deliberately NOT a tray. It is a zone. There is no
 * "switch to Composer" — it is always below the work, which is why the
 * future photo flow needs no "Open in Composer" handoff.
 *
 * What this does NOT re-implement, on purpose:
 *
 *   COLLAPSED  is still `html.launcher-hidden` / `html.toolbox-hidden`,
 *              driven by the panel dividers in templates/base.html's own
 *              setUpDivider(). Untouched.
 *   NORMAL     is still the plain LAY-5A flex composition in main.css.
 *              Untouched.
 *   SIZING     is still `window.__chatSplitter` in case_workspace.js —
 *              the ONE write point for `--chat-height` on `.app-shell`.
 *              The mobile grabber below calls into it rather than
 *              introducing a second height system that would drift out
 *              of sync with the desktop handle, the size toggle, and the
 *              linked Eye/Toolbox splitter.
 *   MAXIMIZE   `#eye-maximize-btn`/`#toolbox-maximize-btn` stay exactly
 *              as they are. Those are INTRA-column proportion controls
 *              (how Eye and Toolbox divide the right column between
 *              them). Focus is a workspace-level question (which tray
 *              gets the screen), so the two compose rather than compete.
 *
 * Focus state lives in one place: a `data-tray-focus` attribute on
 * <html>. An attribute holds exactly one value, so "only one active work
 * tray" is structurally true rather than something four booleans have to
 * be kept in agreement about.
 *
 * PRESENTATION STATE ONLY. Focusing, switching, or resizing a tray must
 * never change authorization, project context, selected evidence, or
 * anything a route would treat as project truth — nothing in this file
 * posts, fetches, or mutates. Non-focused trays keep their DOM (a
 * Composer draft, a scroll position, a selected Document all survive a
 * switch and a rotation); they surrender their box, never their content.
 */
(function () {
    'use strict';

    var html = document.documentElement;
    var ATTR = 'data-tray-focus';
    // Reviewer-wide, matching `beehive:panel:launcher` rather than the
    // per-Project `beehive:panel:toolbox:<id>`: which tray you want in
    // front of you is a working posture, not a fact about one project.
    var STORAGE_KEY = 'beehive:tray:focus';
    // The same 640px the launcher/right-column drawer rules in main.css
    // already use for "narrow". Reused rather than introducing a second,
    // slightly-different phone breakpoint that would drift from it.
    var NARROW = '(max-width: 640px)';

    // Tray key -> the element that becomes the work surface. Keys and
    // labels are the surface identities this application already uses
    // everywhere else (the Appearance menu's own Menu/Lists/Display/
    // Toolbox/Chat vocabulary, plus Eye) and the NPT identities from
    // panel-template-system.md: lists=NPT-002, display=NPT-003,
    // toolbox=NPT-006. (Eye, NPT-005, is a LAYER rather than a tray - see
    // LAYERS below.) No new functions are invented here — Documents, Spin,
    // Findings, Project Context and the photo tray are CONTENTS of these
    // surfaces already.
    var TRAYS = {
        lists: '#launcher-panel',
        display: '.app-main',
        toolbox: '#workspace-toolbox-panel'
    };

    // CLAUDE-MOBILE-Q-TRIAL-01, Section 4 - the foreground layer.
    //
    // "While working on the main panel, open a drawing/document/photo
    // directly from the current screen, bring it to the foreground, work with
    // it, then shovel it back to reveal the main panel exactly where it was."
    // A drawing sheet laid on a desk and slid off again.
    //
    // Eye is that sheet, and is deliberately NOT in TRAYS above. A tray
    // REPLACES what is in the work area; a layer COVERS it. That distinction
    // is what makes "exactly where it was" structural rather than a promise:
    // the base tray is never hidden while Eye is forward, so there is no
    // state to restore - no scroll to recapture, no selection to re-apply, no
    // draft to preserve, because nothing was ever taken away. Eye is also
    // already the drawing/photo surface (rotate, mirror, markers, crop, via
    // drawing_image_viewer.js), so this adds a POSITION for an existing pane
    // rather than a new surface, and adds no second control: the Eye entry in
    // the switcher raises and lowers it.
    var LAYERS = {
        eye: '#eye-pane'
    };
    var LAYER_ATTR = 'data-tray-layer';

    // Resting positions for the work/Composer boundary on a phone,
    // expressed as the share of the shell the COMPOSER takes. The tray
    // gets the rest, so one boundary reads both ways:
    //   tray HIGH    <-> composer at its floor  (focused work)
    //   tray WORKING <-> the ordinary split
    //   tray LOW     <-> composer large         (reading a long answer)
    // Fractions, not pixels: a 667px iPhone SE and an 932px Pro Max
    // should feel the same, which a fixed px preset cannot do.
    var SNAP = { high: 0.22, working: 0.42, low: 0.68 };
    var SNAP_ORDER = ['high', 'working', 'low'];
    // The composer's own controls (input row, send, voice) need a real
    // floor - Section 10's "do not allow Composer expansion to obscure
    // essential send/voice controls" read in the other direction: the
    // tray must not be able to squeeze them out either.
    var COMPOSER_FLOOR_PX = 132;

    function isNarrow() {
        return !!(window.matchMedia && window.matchMedia(NARROW).matches);
    }

    function element(key) {
        var selector = TRAYS[key] || LAYERS[key];
        return selector ? document.querySelector(selector) : null;
    }

    function isLayer(key) {
        return Object.prototype.hasOwnProperty.call(LAYERS, key);
    }

    function currentLayer() {
        return html.getAttribute(LAYER_ATTR) || null;
    }

    /* Raise or lower the foreground layer. Nothing underneath is touched -
       no tray is hidden, no scroll captured, no attribute on the base
       changed - so lowering it reveals the work exactly as it was left. */
    function setLayer(key) {
        if (key && !exists(key)) return false;
        if (key) html.setAttribute(LAYER_ATTR, key);
        else html.removeAttribute(LAYER_ATTR);
        syncControls();
        return true;
    }

    function exists(key) {
        return !!element(key);
    }

    function current() {
        return html.getAttribute(ATTR) || null;
    }

    /* ---------------------------------------------------------------
       Scroll and context survival (Section 17, and Section 14's own
       "returning from a landscape camera capture to portrait must not
       reset the workspace").

       The existing collapse mechanism can promise scroll survival for
       free because `display:none` on a panel later shown again in the
       SAME layout usually restores its scrollTop. That is not reliable
       enough to promise here — an element with no layout box has no
       scroll position to keep, and these trays are genuinely re-laid-out
       (fixed drawer -> full-bleed work surface) crossing in and out of
       focus, which is exactly the case where browsers drop it. So it is
       captured explicitly rather than assumed.
       --------------------------------------------------------------- */
    var scrollMemory = {};

    function rememberScroll() {
        Object.keys(TRAYS).forEach(function (key) {
            var root = element(key);
            if (!root) return;
            var entries = [];
            if (root.scrollTop > 0) entries.push([root, root.scrollTop]);
            var nodes = root.querySelectorAll('*');
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].scrollTop > 0) entries.push([nodes[i], nodes[i].scrollTop]);
            }
            if (entries.length) scrollMemory[key] = entries;
        });
    }

    function restoreScroll() {
        // After layout has actually happened, or the assignment is a
        // no-op against an element that is still zero-height.
        window.requestAnimationFrame(function () {
            Object.keys(scrollMemory).forEach(function (key) {
                var entries = scrollMemory[key];
                for (var i = 0; i < entries.length; i++) {
                    // An element the user legitimately scrolled back to 0
                    // is simply recaptured as 0 next time, so this never
                    // fights them.
                    entries[i][0].scrollTop = entries[i][1];
                }
            });
        });
    }

    function persist(key) {
        try {
            if (key) window.localStorage.setItem(STORAGE_KEY, key);
            else window.localStorage.removeItem(STORAGE_KEY);
        } catch (e) { /* private mode - state still applies, just is not remembered */ }
    }

    function labelFor(key) {
        var btn = document.querySelector('[data-tray-focus-btn="' + key + '"]');
        return (btn && btn.getAttribute('data-tray-label')) || key;
    }

    function syncControls() {
        var active = current();
        var buttons = document.querySelectorAll('[data-tray-focus-btn]');
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            var key = btn.getAttribute('data-tray-focus-btn');
            var on = isLayer(key) ? key === currentLayer() : key === active;
            btn.setAttribute('aria-pressed', String(on));
            var name = btn.getAttribute('data-tray-label') || key;
            // The label names what the next press DOES, the same
            // convention case_workspace.js's own syncSizeToggle() uses.
            if (isLayer(key)) {
                btn.setAttribute('aria-label', on
                    ? ('Send ' + name + ' back and return to the work below')
                    : ('Bring ' + name + ' to the front, over the current work'));
            } else {
                btn.setAttribute('aria-label', on && !isNarrow()
                    ? ('Restore the workspace from ' + name)
                    : ('Show ' + name));
            }
        }
        // Section 3: the header states what is being worked on.
        var readout = document.getElementById('tray-active-label');
        if (readout) readout.textContent = active ? labelFor(active) : 'Workspace';
    }

    function apply(key, options) {
        var opts = options || {};
        if (key && !exists(key)) return false;
        if (key === current() && !opts.force) return false;
        rememberScroll();
        if (key) html.setAttribute(ATTR, key);
        else html.removeAttribute(ATTR);
        if (opts.persist !== false) persist(key);
        syncControls();
        restoreScroll();
        return true;
    }

    function focus(key) {
        // A layer is raised and lowered, never swapped in as the work area -
        // see LAYERS above. Pressing it again shovels it back.
        if (isLayer(key)) return setLayer(key === currentLayer() ? null : key);
        // On a phone SOME tray always owns the work zone - pressing the
        // active one again would empty the middle of the frame, so a
        // repeat press is a no-op there. On desktop the same press is
        // the restore path back to the normal multi-tray composition
        // (Section 19), on the same control, with no separate "unfocus"
        // button to hunt for.
        if (key === current()) return isNarrow() ? false : apply(null);
        return apply(key);
    }

    function clear() {
        if (isNarrow()) return false;
        return apply(null);
    }

    /* ---------------------------------------------------------------
       The work/Composer boundary. One write point: the existing
       `window.__chatSplitter` from case_workspace.js, which owns
       `--chat-height` on `.app-shell` and already carries the clamps,
       the persistence, the aria-valuenow bookkeeping and the linked-
       splitter mirroring. Nothing here writes that property directly.
       --------------------------------------------------------------- */
    function shellHeight() {
        var shell = document.querySelector('.app-shell');
        return (shell && shell.clientHeight) || window.innerHeight || 0;
    }

    function composerPx() {
        if (window.__chatSplitter) return window.__chatSplitter.getValue();
        return 0;
    }

    function setComposerPx(px, persistIt) {
        if (!window.__chatSplitter) return false;
        var available = shellHeight();
        var ceiling = Math.max(COMPOSER_FLOOR_PX, available - 140); // always leave the tray a real strip
        var next = Math.max(COMPOSER_FLOOR_PX, Math.min(ceiling, Math.round(px)));
        window.__chatSplitter.setValue(next, persistIt !== false);
        return true;
    }

    function snap(state, persistIt) {
        var fraction = SNAP[state];
        if (fraction == null) return false;
        return setComposerPx(shellHeight() * fraction, persistIt);
    }

    /* Which rest position is the boundary nearest right now - used to
       label the grabber and to decide what the next cycle press does. */
    function splitState() {
        var available = shellHeight();
        if (!available || !window.__chatSplitter) return 'working';
        var fraction = composerPx() / available;
        var best = 'working';
        var bestDistance = Infinity;
        SNAP_ORDER.forEach(function (name) {
            var distance = Math.abs(SNAP[name] - fraction);
            if (distance < bestDistance) { bestDistance = distance; best = name; }
        });
        return best;
    }

    function syncGrabber() {
        var grabber = document.getElementById('tray-composer-grabber');
        if (!grabber) return;
        var state = splitState();
        // Named from the TRAY's point of view - the tray is the thing
        // the reviewer is sizing; the Composer is what it trades against.
        var trayState = state === 'high' ? 'expanded' : (state === 'low' ? 'collapsed' : 'working');
        grabber.setAttribute('data-tray-size', trayState);
        grabber.setAttribute('aria-valuetext', 'Work area ' + trayState);
        // Declared aria-valuemin/max on the element need a real valuenow
        // beside them, the same bookkeeping applyHeight() already does for
        // the desktop handle.
        if (window.__chatSplitter) {
            grabber.setAttribute('aria-valuenow', String(composerPx()));
        }
    }

    function cycleSize() {
        // A plain tap cycles the rest positions, so the boundary is
        // reachable without a drag at all (Section 22: avoid precision
        // targets; Section 23: keyboard access).
        var index = SNAP_ORDER.indexOf(splitState());
        var next = SNAP_ORDER[(index + 1) % SNAP_ORDER.length];
        snap(next);
        syncGrabber();
    }

    function wireGrabber() {
        var grabber = document.getElementById('tray-composer-grabber');
        if (!grabber) return;

        var dragging = false;
        var startY = 0;
        var startPx = 0;
        var moved = false;

        grabber.addEventListener('pointerdown', function (event) {
            if (!isNarrow()) return;
            dragging = true;
            moved = false;
            startY = event.clientY;
            startPx = composerPx();
            grabber.setPointerCapture(event.pointerId);
            grabber.classList.add('dragging');
        });

        grabber.addEventListener('pointermove', function (event) {
            if (!dragging) return;
            var delta = startY - event.clientY; // drag up = more Composer, less tray
            if (Math.abs(delta) > 4) moved = true;
            // Live, unpersisted - the resting value is written on release
            // so an abandoned drag never becomes the remembered posture.
            setComposerPx(startPx + delta, false);
            syncGrabber();
            event.preventDefault();
        });

        function endDrag(event) {
            if (!dragging) return;
            dragging = false;
            grabber.classList.remove('dragging');
            if (event && event.pointerId != null && grabber.hasPointerCapture(event.pointerId)) {
                grabber.releasePointerCapture(event.pointerId);
            }
            if (!moved) { cycleSize(); return; }
            // Settle onto the nearest rest position so the frame stays
            // predictable rather than landing anywhere at all.
            snap(splitState());
            syncGrabber();
        }

        grabber.addEventListener('pointerup', endDrag);
        grabber.addEventListener('pointercancel', endDrag);

        grabber.addEventListener('keydown', function (event) {
            var step = 32;
            if (event.key === 'ArrowUp') { setComposerPx(composerPx() + step); }
            else if (event.key === 'ArrowDown') { setComposerPx(composerPx() - step); }
            else if (event.key === 'Enter' || event.key === ' ') { cycleSize(); }
            else return;
            syncGrabber();
            event.preventDefault();
        });
    }

    /* ---------------------------------------------------------------
       The software keyboard (Section 15). iOS does not shrink the layout
       viewport when the keyboard opens, so a bottom-anchored Composer
       ends up underneath it. visualViewport reports the real visible
       area; the difference is published as `--kb-inset` and the Composer
       rides above it. No-op on platforms that resize properly.
       --------------------------------------------------------------- */
    function wireKeyboardInset() {
        var vv = window.visualViewport;
        if (!vv) return;
        function update() {
            var inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
            html.style.setProperty('--kb-inset', inset + 'px');
            html.classList.toggle('keyboard-open', inset > 80);
        }
        vv.addEventListener('resize', update);
        vv.addEventListener('scroll', update);
        update();
    }

    /* On a phone the normal LAY-5A composition is not a smaller version
     * of itself - it is three columns and a dock competing for 390px,
     * which is the condition this whole change exists to end. So at
     * narrow widths a tray is ALWAYS active: if the reviewer has not
     * chosen one, Display (the primary work surface, NPT-003, the one
     * panel the inventory marks "not closable") is it.
     *
     * The default is deliberately not persisted - persisting it would
     * make a single phone visit silently rewrite the desktop preference. */
    function narrowDefault() {
        if (!isNarrow() || current()) return;
        apply(exists('display') ? 'display' : 'lists', { persist: false });
    }

    function wireSwitcher() {
        var buttons = document.querySelectorAll('[data-tray-focus-btn]');
        for (var i = 0; i < buttons.length; i++) {
            (function (btn) {
                var key = btn.getAttribute('data-tray-focus-btn');
                if (!exists(key)) {
                    // A control for a tray this page does not have is a
                    // dead control - remove it rather than render a
                    // button that does nothing (a project-less page has
                    // no Eye or Toolbox at all).
                    btn.remove();
                    return;
                }
                btn.addEventListener('click', function () {
                    focus(key);
                    var target = element(key);
                    if (target && target.scrollIntoView) target.scrollIntoView({ block: 'nearest' });
                });
            })(buttons[i]);
        }
    }

    function wireLayerDismiss() {
        // The switcher entry raises and lowers the layer, but a reviewer whose
        // attention is on the drawing itself should not have to travel back up
        // to the header to put it down. Same action, reachable from where the
        // work is.
        var dismiss = document.getElementById('eye-layer-dismiss');
        if (!dismiss) return;
        dismiss.addEventListener('click', function () {
            setLayer(null);
            var btn = document.querySelector('[data-tray-focus-btn="eye"]');
            if (btn) btn.focus();
        });
    }

    function wireMobileNav() {
        var toggle = document.getElementById('mobile-nav-toggle');
        if (!toggle) return;
        function setOpen(open) {
            html.classList.toggle('mobile-nav-open', open);
            toggle.setAttribute('aria-expanded', String(open));
        }
        toggle.addEventListener('click', function () {
            setOpen(!html.classList.contains('mobile-nav-open'));
        });
        // Choosing anything inside the drawer closes it - a menu that
        // stays open over the work after you used it is its own problem.
        var menubar = document.querySelector('.workspace-menubar');
        if (menubar) {
            menubar.addEventListener('click', function (event) {
                var el = event.target;
                if (el && el.closest && el.closest('a, button:not(summary)')) setOpen(false);
            });
        }
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && html.classList.contains('mobile-nav-open')) {
                setOpen(false);
                toggle.focus();
            }
        });
        // A tap on the work behind the drawer dismisses it - the same
        // outside-click convention app_menu.js already applies to every
        // <details> popup in the topbar, which does not cover this
        // because the drawer is a class on <html>, not a popup.
        document.addEventListener('click', function (event) {
            if (!html.classList.contains('mobile-nav-open')) return;
            var el = event.target;
            if (el === toggle || (el && el.closest && (el.closest('#mobile-nav-toggle') || el.closest('.workspace-menubar')))) return;
            setOpen(false);
        });
    }

    function wire() {
        // The pre-paint script in base.html restores a stored key without
        // being able to check it - it runs in <head>, before the body it
        // would have to look in. A reviewer who last focused Eye and then
        // opened a project-less page would otherwise land on a frame whose
        // active tray is not on the page at all.
        var restored = current();
        // Also catches a preference stored while Eye was still a TRAY,
        // before Section 4 made it the foreground layer - TRAYS no longer
        // has that key, so exists() reports it through LAYERS and the
        // isLayer() check below retires it deliberately.
        if (restored && (!exists(restored) || isLayer(restored))) {
            html.removeAttribute(ATTR);
            persist(null);
        }
        wireSwitcher();
        wireLayerDismiss();
        wireMobileNav();
        wireGrabber();
        wireKeyboardInset();

        // Escape restores the normal composition on desktop. Never a trap
        // (Section 23) - but never at the cost of a real Escape either:
        // a menu, dialog, or text field the reviewer is actually inside
        // gets first refusal.
        document.addEventListener('keydown', function (event) {
            if (event.key !== 'Escape') return;
            var el = event.target;
            // A menu, dialog or text field the reviewer is actually inside
            // gets first refusal on a real Escape (Section 23).
            if (el && el.closest && el.closest('input, textarea, select, [contenteditable="true"], details[open]')) return;
            // Lower the foreground layer before touching the work beneath it -
            // top of the stack goes first, which is what Escape means.
            if (currentLayer()) { setLayer(null); return; }
            if (!current() || isNarrow()) return;
            clear();
        });

        // Crossing the narrow boundary in either direction - a rotation,
        // a resized desktop window - re-evaluates the default without
        // touching a preference the reviewer set deliberately. Section 14:
        // the active tray, its content and the Composer draft all survive,
        // because nothing here rebuilds any DOM.
        if (window.matchMedia) {
            var mq = window.matchMedia(NARROW);
            var onChange = function () {
                if (mq.matches) narrowDefault();
                syncControls();
                syncGrabber();
            };
            if (mq.addEventListener) mq.addEventListener('change', onChange);
            else if (mq.addListener) mq.addListener(onChange);
        }
        window.addEventListener('orientationchange', function () {
            window.requestAnimationFrame(function () { narrowDefault(); syncGrabber(); });
        });

        narrowDefault();
        syncControls();
        // __chatSplitter is published by case_workspace.js, which may load
        // after this file - settle the grabber once the frame is up.
        window.requestAnimationFrame(syncGrabber);
    }

    window.ArchioskTrays = {
        KEYS: Object.keys(TRAYS),
        LAYER_KEYS: Object.keys(LAYERS),
        SNAP: SNAP,
        focus: focus,
        clear: clear,
        current: current,
        currentLayer: currentLayer,
        setLayer: setLayer,
        exists: exists,
        isNarrow: isNarrow,
        snap: snap,
        splitState: splitState,
        STORAGE_KEY: STORAGE_KEY
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wire);
    } else {
        wire();
    }
})();
