/* UNIVERSAL COMPOSER INVARIANT: the behaviour of the ONE canonical GO Composer
 * (templates/_macros.html conversation_dock, rendered once by base.html on every
 * signed-in page). One owner for each behaviour:
 *
 * - draft preservation, submit status and thread scroll memory, and push-to-talk
 *   voice: MOVED VERBATIM from static/js/case_workspace.js, which only loaded on
 *   workspace/planning pages - the Composer now exists everywhere;
 * - once-only submit: replaces the retired Document Shop composer's own
 *   double-submit guard (a second tap must not ask - and charge - twice);
 * - APPLICATION scope, staff (data-go-reply="json"): the orientation reply and
 *   navigation the retired Projects / New Project composers performed against
 *   portal.gateway_orientation, unchanged;
 * - APPLICATION scope, My Documents (data-go-selection): the selected document ids
 *   travel with the request as Composer context, to the existing selection
 *   action - the same ids the desk's own selection controls hold;
 * - paste: a pasted screenshot enters the Composer's EXISTING attachment
 *   pipeline (composer_attach.js), as the retired developer composer allowed.
 *
 * Enter-to-send stays with static/js/developer_composer_input.js, which already
 * binds every [data-developer-composer-form], this Composer included.
 */
document.addEventListener('DOMContentLoaded', () => {
    const goForm = document.querySelector('form[data-ui-ref="chat.composer"]');
    if (!goForm) return;
    const goInput = document.getElementById('dock-composer-input');
    const goSend = goForm.querySelector('[data-ui-ref="chat.composer.send"]');
    const goReply = document.getElementById('dock-go-reply');

    function showGoReply(text) {
        if (!goReply) return;
        goReply.textContent = text || '';
        goReply.hidden = !text;
    }

    // Selection context: attach the desk's selected ids; nothing selected -> say so, send nothing.
    const selectionFormId = goForm.getAttribute('data-go-selection');
    if (selectionFormId) {
        goForm.addEventListener('submit', (e) => {
            goForm.querySelectorAll('input[data-go-selected]').forEach((el) => el.remove());
            const selected = document.querySelectorAll(
                'input[form="' + selectionFormId + '"][name="project_id"]:checked');
            if (!selected.length) {
                e.preventDefault();
                e.stopImmediatePropagation();
                showGoReply('Select one or more documents first.');
                // Nothing was sent: release the keyboard for the next attempt.
                goForm.dispatchEvent(new Event('composer:settled'));
                return;
            }
            selected.forEach((box) => {
                const hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = 'project_id';
                hidden.value = box.value;
                hidden.setAttribute('data-go-selected', '');
                goForm.appendChild(hidden);
            });
        });
    }

    // Once-only submit for a full-page post (the JSON mode below manages its own state).
    if (goForm.getAttribute('data-go-reply') !== 'json') {
        let goSent = false;
        goForm.addEventListener('submit', (e) => {
            if (e.defaultPrevented) return;
            if (goSent) { e.preventDefault(); return; }
            if (goInput && !goInput.value.trim() && !document.getElementById('dock-composer-image-data')?.value) return;
            goSent = true;
        });
    }

    // APPLICATION (staff): orientation reply in place, navigation when GO names a page.
    // The submit stops here: the handlers after it assume a page load, which
    // this mode never does. So it says itself when the question is over
    // (composer:settled) - once only while in flight, free again afterwards.
    if (goForm.getAttribute('data-go-reply') === 'json') {
        let goInFlight = false;
        const settle = () => goForm.dispatchEvent(new Event('composer:settled'));
        goForm.addEventListener('submit', (e) => {
            e.preventDefault();
            e.stopImmediatePropagation();
            if (goInFlight) return;
            const message = goInput ? goInput.value.trim() : '';
            if (!message) { settle(); return; }
            goInFlight = true;
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (goSend) goSend.disabled = true;
            fetch(goForm.action, {
                method: 'POST',
                body: new FormData(goForm),
                headers: { 'X-CSRFToken': meta ? meta.content : '' },
                credentials: 'same-origin',
            }).then((resp) => {
                if (!resp.ok) throw new Error('request failed');
                return resp.json();
            }).then((data) => {
                showGoReply(data.text || '');
                if (data.kind === 'navigate' && data.url) {
                    window.setTimeout(() => { window.location.href = data.url; }, 350);
                }
            }).catch(() => {
                showGoReply('Something went wrong - try again.');
            }).finally(() => {
                goInFlight = false;
                if (goSend) goSend.disabled = false;
                settle();
            });
        }, true);
    }

    // Paste a screenshot into the Composer's existing attachment pipeline.
    const goImage = document.getElementById('dock-composer-image');
    if (goInput && goImage && typeof DataTransfer === 'function') {
        goInput.addEventListener('paste', (e) => {
            const items = (e.clipboardData && e.clipboardData.items) || [];
            const item = Array.prototype.find.call(items, (i) => i.kind === 'file' && /^image\//.test(i.type));
            if (!item) return;
            const file = item.getAsFile();
            if (!file) return;
            e.preventDefault();
            const dt = new DataTransfer();
            dt.items.add(file);
            goImage.files = dt.files;
            goImage.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

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
        draftInput.closest('form').addEventListener('submit', (e) => {
            window.sessionStorage.removeItem(draftKey);
            if (conversationScopeForDraft) {
                window.sessionStorage.setItem(`beehive:conversation:justSent:${conversationScopeForDraft}`, '1');
            }
            // CLAUDE-CA1D-INSTRUMENT-RAIL-01: composer-adjacent execution
            // strip proof (Plan-Mode report, Section D.3/K.4) - this is a
            // classic, un-intercepted form submit (no preventDefault
            // anywhere on this form), so the browser keeps the current DOM
            // rendered exactly as-is for the real duration of the server
            // round trip, then replaces it wholesale once the response
            // arrives. Setting the status text and disabling Send here is
            // therefore both real (visible for the actual wait) and
            // self-clearing (the next page load has neither, since this is
            // never persisted anywhere) - no fetch/AJAX, no new backend
            // endpoint, no async infrastructure added.
            const executionStatus = document.getElementById('dock-composer-execution-status');
            if (executionStatus) executionStatus.textContent = 'Working on your request…';
            // CLAUDE-ARCHIOSK-IDENTITY-ACTIVITY-INDICATOR-01: the SAME real
            // signal that already sets executionStatus's text above also
            // drives the top-left three-dot working indicator - one
            // handler, one truthful moment, never a second "GO is working"
            // mechanism. Self-clearing for the identical reason
            // executionStatus is: this is a classic, un-intercepted submit,
            // so the current DOM (including this [hidden] removal and
            // .working class) survives only for the real duration of the
            // server round trip, then the whole page is replaced.
            const appActivity = document.getElementById('workspace-app-activity');
            if (appActivity) {
                appActivity.hidden = false;
                appActivity.classList.add('working');
                appActivity.title = 'GO working';
                appActivity.setAttribute('aria-label', 'GO working');
            }
            // CLAUDE-CA1D-COMPOSER-ENTER-FIX-01: was `e.target.querySelector
            // ('button[type="submit"]')`, which returns the FIRST submit
            // button in DOM order - since CLAUDE-CA1D-COMPOSER-CONTEXT-
            // LABEL-01 this form can also contain the "Clear work context"
            // button (composer-context-clear, also type="submit", rendered
            // BEFORE this one whenever current_context is set), so this was
            // disabling the wrong button. The real Send button has its own
            // stable data-ui-ref - use that instead of positional order.
            const sendBtn = e.target.querySelector('[data-ui-ref="chat.composer.send"]');
            if (sendBtn) sendBtn.disabled = true;
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

    // CLAUDE-POSTCAMEL-VOICE1-PRE, CLAUDE-VOICE-CONSISTENCY-01: Push-to-
    // Talk voice input - "the microphone is merely another door into
    // ARCHIOSK Go." The actual SpeechRecognition wiring/status-messaging/
    // Push-to-Talk engine now lives in static/js/voice_input.js
    // (window.ArchioskVoiceInput), shared with the Project Gateway and
    // Sign-In pages' own mic controls rather than duplicated - see that
    // file's own header comment for the full behavior/provider-choice
    // reasoning, unchanged by this extraction. This call site only wires
    // the existing composer's own element ids and its "fill the input,
    // never auto-submit" behavior (Section 6, review-before-send) - every
    // existing hidden field (anchor/current_view/selected_source_id) on
    // the same <form> is still submitted unchanged, so voice still
    // inherits the exact same Project context/selection/permission path
    // text already has.
    (function () {
        const composerInput = document.getElementById('dock-composer-input');
        if (!composerInput) return;
        window.ArchioskVoiceInput({
            buttonId: 'dock-composer-voice',
            statusId: 'dock-composer-voice-status',
            onTranscript: (transcript) => { composerInput.value = transcript; },
            onEnd: () => composerInput.focus(),
        });
    })();
});
