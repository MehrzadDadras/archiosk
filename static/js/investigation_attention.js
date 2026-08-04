/*
 * CLAUDE-P40-VW7B - Foreground Project Vestibule and Four-Position
 * Investigation Attention Model.
 *
 * NOTE ON THE TAG: "CLAUDE-P40-VW7B" was already used once before, for
 * an unrelated, already-shipped stage ("generalize active-Display
 * projection; relocate a misplaced admin control" - see git log
 * a61a7b8/9a5c11b). This stage reuses the same tag because that is
 * what its own governing prompt specified; flagged here and in the
 * checkpoint entry so the collision is never silently ambiguous to a
 * future reader of this file's own history.
 *
 * Architecture, stated honestly: this is a full-page-reload application
 * (routes/workspace.py's own show_workspace) - "focused" Investigation
 * is not a separate concept this file tracks at all, it is simply
 * whichever Case the current URL's own ?case= already names (the SAME
 * "no new persisted state needed" reasoning templates/base.html's own
 * comment on the Foreground Project applies one level down, to
 * Investigations). What IS new and genuinely needs persistence is the
 * bounded ATTENTION SET - up to four Case ids held in attention,
 * independent of which one is currently focused - client-side only,
 * localStorage, keyed by username + Project id (matching
 * document_tabs.js's own established key shape and cross-account/
 * cross-Project leakage guard), revalidated on every load against
 * #workspace-visible-cases-data (the SAME authorized, privacy-filtered
 * list routes/workspace.py already computes - never a second,
 * separately-trusted source of truth, and never an arbitrarily chosen
 * "first Investigation in the Project" - Section 3's explicit
 * prohibition).
 *
 * Capacity enforcement (Section 9's "enforce at the governing
 * transition, not only through a disabled button... direct URLs,
 * refreshes... must not produce five contradictory active positions"):
 * deliberately NOT a pre-click interceptor on the Lists Investigations
 * branch (base.html already runs a separate, unrelated click-
 * interceptor there for Display-division routing - entangling a
 * second one with it would risk both). Instead, this file performs
 * POST-LOAD reconciliation on every workspace page render, the one
 * mechanism that uniformly covers every real entry path (an ordinary
 * click, a bookmark, Back/Forward, a refresh, or create_case's own
 * redirect into the just-created Investigation) rather than only the
 * common one - the governing transition Section 9 actually asks for.
 */
(function () {
    'use strict';

    var strip = document.getElementById('attention-strip');
    if (!strip) return;
    var list = document.getElementById('attention-strip-list');
    if (!list) return;

    var projectId = strip.getAttribute('data-project-id') || '';
    var activeCaseId = strip.getAttribute('data-active-case-id') || '';
    var baseUrl = strip.getAttribute('data-base-url') || window.location.pathname;

    var MAX_ATTENTION = 4;

    var usernameEl = document.querySelector('.workspace-user-name');
    var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
    var ATTENTION_KEY = 'beehive:attention:cases:' + username + ':' + projectId;

    function readVisibleCases() {
        var el = document.getElementById('workspace-visible-cases-data');
        if (!el) return [];
        try {
            var parsed = JSON.parse(el.textContent || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function loadAttention() {
        try {
            var raw = window.localStorage.getItem(ATTENTION_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function saveAttention(ids) {
        try { window.localStorage.setItem(ATTENTION_KEY, JSON.stringify(ids)); } catch (e) { /* ignore */ }
    }

    function navigateTo(caseId) {
        window.location.href = baseUrl + '?case=' + encodeURIComponent(caseId);
    }

    function navigateToEmpty() {
        window.location.href = baseUrl;
    }

    // -------- Reconciliation (Section 3/11: never an arbitrary guess,
    // never a stale/unauthorized/foreign-Project id) -----------------
    var visibleCases = readVisibleCases();
    var casesById = {};
    visibleCases.forEach(function (c) { casesById[c.id] = c; });

    var attention = loadAttention().filter(function (id) { return !!casesById[id]; });
    var attentionChanged = loadAttention().length !== attention.length;

    var capacityDialogNeeded = false;
    if (activeCaseId && casesById[activeCaseId]) {
        if (attention.indexOf(activeCaseId) === -1) {
            if (attention.length < MAX_ATTENTION) {
                attention.push(activeCaseId);
                attentionChanged = true;
            } else {
                capacityDialogNeeded = true;
            }
        }
    }
    if (attentionChanged) saveAttention(attention);

    // -------- Rendering ---------------------------------------------
    function render() {
        list.textContent = '';
        strip.hidden = attention.length === 0;
        attention.forEach(function (id) {
            var c = casesById[id];
            if (!c) return;
            list.appendChild(buildPositionEl(c));
        });
    }

    function buildPositionEl(c) {
        var isFocused = c.id === activeCaseId;
        var a = document.createElement('a');
        a.className = 'attention-position' + (isFocused ? ' attention-position-focused' : '');
        a.href = baseUrl + '?case=' + encodeURIComponent(c.id);
        a.setAttribute('role', 'tab');
        a.setAttribute('data-case-id', c.id);
        a.setAttribute('aria-selected', String(isFocused));
        a.setAttribute('tabindex', isFocused ? '0' : '-1');
        // Section 6: non-color state cue - "Focused" is real, visible
        // text on the focused position, not merely a background/border
        // color change (see main.css's own .attention-position-focused
        // for the accompanying, non-exclusive color treatment).
        var accessibleName = c.title + (isFocused ? ' (focused)' : ' (in attention)') +
            (c.status === 'archived' ? ', archived' : '');
        a.setAttribute('aria-label', accessibleName);

        var labelSpan = document.createElement('span');
        labelSpan.className = 'attention-position-label';
        labelSpan.textContent = c.title;
        a.appendChild(labelSpan);

        if (isFocused) {
            var focusedTag = document.createElement('span');
            focusedTag.className = 'attention-position-focused-tag';
            focusedTag.setAttribute('aria-hidden', 'true');
            focusedTag.textContent = 'Focused';
            a.appendChild(focusedTag);
        }
        if (c.status === 'archived') {
            var archivedTag = document.createElement('span');
            archivedTag.className = 'attention-position-archived-tag';
            archivedTag.setAttribute('aria-hidden', 'true');
            archivedTag.textContent = 'Archived';
            a.appendChild(archivedTag);
        }

        var releaseBtn = document.createElement('button');
        releaseBtn.type = 'button';
        releaseBtn.className = 'attention-position-release';
        releaseBtn.setAttribute('aria-label', 'Release ' + c.title + ' from attention');
        releaseBtn.textContent = '×';
        releaseBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            releaseFromAttention(c.id);
        });
        a.appendChild(releaseBtn);

        a.addEventListener('keydown', function (e) { onPositionKeydown(e, a); });
        return a;
    }

    // Section 8: "removing an Investigation from attention must not
    // delete, close, resolve, archive, or otherwise falsify its real
    // status" - a pure localStorage membership change, nothing else.
    // Never navigates - the currently-displayed content (whatever
    // ?case= or ?source= the URL already names) is untouched by a
    // release, even when the released position was the focused one.
    function releaseFromAttention(caseId) {
        var idx = attention.indexOf(caseId);
        if (idx === -1) return;
        attention.splice(idx, 1);
        saveAttention(attention);
        render();
    }

    // CLAUDE-P40-VW8 (Governed Display Tab System, Section 4's "mouse and
    // keyboard operation"): Space-key activation added - a real gap found
    // by this stage's own audit against document_tabs.js's onTabKeydown,
    // which already has this. Native <a href> elements activate on Enter
    // but NOT Space (that's a button/checkbox convention); document_tabs.js
    // already compensates with an explicit e.key === ' ' handler, this file
    // never did. Same fix, same reasoning, applied here for parity across
    // both of this app's real dynamic-record tab strips.
    function onPositionKeydown(e, el) {
        var positions = Array.prototype.slice.call(list.querySelectorAll('.attention-position'));
        var idx = positions.indexOf(el);
        if (idx === -1) return;
        function focusIndex(i) {
            positions.forEach(function (p) { p.setAttribute('tabindex', '-1'); });
            var next = positions[(i + positions.length) % positions.length];
            next.setAttribute('tabindex', '0');
            next.focus();
        }
        if (e.key === 'ArrowRight') { focusIndex(idx + 1); e.preventDefault(); }
        else if (e.key === 'ArrowLeft') { focusIndex(idx - 1); e.preventDefault(); }
        else if (e.key === 'Home') { focusIndex(0); e.preventDefault(); }
        else if (e.key === 'End') { focusIndex(positions.length - 1); e.preventDefault(); }
        else if (e.key === ' ') { e.preventDefault(); el.click(); }
    }

    render();

    // -------- Fifth-Investigation capacity dialog (Section 9) -------
    var dialog = document.getElementById('attention-capacity-dialog');
    if (capacityDialogNeeded && dialog) {
        openCapacityDialog();
    }

    function openCapacityDialog() {
        var targetNameEl = document.getElementById('attention-capacity-target-name');
        var positionsList = document.getElementById('attention-capacity-dialog-list');
        var cancelBtn = document.getElementById('attention-capacity-cancel');
        var concludeForm = document.getElementById('attention-capacity-conclude-form');
        var nextCaseInput = document.getElementById('attention-capacity-next-case');
        if (!targetNameEl || !positionsList || !cancelBtn || !concludeForm || !nextCaseInput) return;

        var targetCase = casesById[activeCaseId];
        targetNameEl.textContent = targetCase ? targetCase.title : '';
        positionsList.textContent = '';

        attention.forEach(function (id) {
            var c = casesById[id];
            if (!c) return;
            var li = document.createElement('li');
            li.className = 'attention-capacity-dialog-item';

            var name = document.createElement('span');
            name.className = 'attention-capacity-dialog-item-name';
            name.textContent = c.title;
            li.appendChild(name);

            var releaseBtn = document.createElement('button');
            releaseBtn.type = 'button';
            releaseBtn.className = 'btn btn-ghost';
            releaseBtn.textContent = 'Release';
            releaseBtn.setAttribute('aria-label', 'Release ' + c.title + ' to open ' + (targetCase ? targetCase.title : 'this Investigation'));
            releaseBtn.addEventListener('click', function () {
                releaseFromAttention(id);
                attention.push(activeCaseId);
                saveAttention(attention);
                render();
                closeCapacityDialog();
            });
            li.appendChild(releaseBtn);

            // Section 9: "conclude one only through its genuine
            // governed completion action" - the real, already-existing,
            // owner-or-admin-gated archive_case route (see routes/
            // workspace.py's own docstring on why this is the first UI
            // trigger it ever gets). No "move to a Waiting/Parked
            // state" option is offered here - grounded in this
            // repository's actual Case model (CASE_STATUS_OPEN/
            // CASE_STATUS_ARCHIVED only; no such state exists to move
            // anything into - see this stage's own checkpoint entry for
            // the full reasoning), not omitted by oversight.
            var concludeBtn = document.createElement('button');
            concludeBtn.type = 'button';
            concludeBtn.className = 'btn btn-ghost';
            concludeBtn.textContent = 'Conclude';
            concludeBtn.setAttribute('aria-label', 'Conclude ' + c.title + ' to open ' + (targetCase ? targetCase.title : 'this Investigation'));
            concludeBtn.addEventListener('click', function () {
                releaseFromAttention(id);
                concludeForm.action = baseUrl.replace(/\/workspace$/, '/workspace/cases/' + encodeURIComponent(id) + '/archive');
                nextCaseInput.value = activeCaseId;
                concludeForm.submit();
            });
            li.appendChild(concludeBtn);

            positionsList.appendChild(li);
        });

        dialog.hidden = false;
        cancelBtn.focus();

        function closeCapacityDialog() {
            dialog.hidden = true;
            document.removeEventListener('keydown', onKeydown);
        }
        function onKeydown(e) {
            if (e.key === 'Escape') { e.preventDefault(); navigateToEmpty(); }
        }
        document.addEventListener('keydown', onKeydown);

        // Section 9: "cancel opening the new Investigation" - this page
        // has ALREADY loaded showing the fifth Investigation's own
        // content (post-load reconciliation, not a pre-click
        // intercept - see this file's own header comment), so
        // cancelling means navigating away from it, back to a neutral
        // Overview state, not merely hiding the dialog in place.
        cancelBtn.addEventListener('click', function () { navigateToEmpty(); });
    }

    // Exposed for tests/future callers - a read-only lookup, never a
    // second write path for attention-set membership (mirrors
    // document_tabs.js's own window.ArchioskDocumentTabs.isPinned).
    //
    // CLAUDE-P40-VW8 (Governed Display Tab System, Section 4's "Closing
    // the active tab selects a deterministic neighboring or previously
    // active tab"): mostRecentAttended added so document_tabs.js's own
    // activateFallback can treat BOTH of this app's real dynamic-record
    // tab strips (Documents, Investigations) as one governed fallback
    // pool, rather than falling straight to the empty Display state when
    // no other Document tab exists but a perfectly good attended
    // Investigation does. Deliberately does NOT reach into Attention's
    // own "release" behavior (still never navigates - VW7B's own
    // explicit, accepted "removing an Investigation from attention must
    // not... otherwise falsify its real status" / "never navigates"
    // guarantee is untouched) - this is a read-only lookup consulted by
    // a DIFFERENT action (closing a Document tab), not a change to what
    // release itself does. attention has no per-entry recency timestamp
    // (unlike document_tabs.js's own pinned entries' lastActiveAt) - the
    // array's own insertion order (last pushed = most recently brought
    // into attention) is used as the defined, deterministic rule instead
    // of inventing new persisted state for a fallback path.
    window.ArchioskInvestigationAttention = {
        isAttended: function (caseId) { return attention.indexOf(caseId) !== -1; },
        mostRecentAttended: function (excludingId) {
            for (var i = attention.length - 1; i >= 0; i--) {
                var id = attention[i];
                if (id !== excludingId && casesById[id]) return id;
            }
            return null;
        }
    };
})();
