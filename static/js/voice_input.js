// CLAUDE-POSTCAMEL-VOICE1-PRE (extracted), CLAUDE-VOICE-CONSISTENCY-01:
// shared Push-to-Talk voice input, factored out of case_workspace.js so
// the Project Gateway and Sign-In pages can reuse the exact same
// SpeechRecognition wiring/behavior/status messaging rather than a second,
// copy-pasted implementation - "the microphone is merely another door
// into ARCHIOSK Go," now true consistently everywhere the door exists,
// not just inside an open Project. Deliberately uses the browser's own
// built-in SpeechRecognition (Web Speech API), never a hosted
// transcription provider - see case_workspace.js's own former copy of
// this comment (git history) for the full provider-audit reasoning,
// unchanged by this extraction.
//
// Deliberately minimal: no manual getUserMedia/MediaRecorder/audio-blob
// handling anywhere in this file - SpeechRecognition captures and
// discards its own internal audio entirely inside the browser and only
// ever hands this code a text transcript. There is no audio blob here to
// accidentally persist.
//
// Generalized via `onTranscript`/`onFinalTranscript` callbacks instead of
// a hardcoded "fill the composer input" behavior: the in-project Chat
// composer and the Gateway orientation composer both still want that
// exact behavior (fill an editable text field, never auto-submit - the
// reviewer/user still reviews/sends themselves), but Sign-In's use is
// different in kind (match a small fixed navigation intent, never fill
// any credential field) - one shared recognition/status/Push-to-Talk
// engine underneath, not a second one.
//
// Exposes ONE global, `window.ArchioskVoiceInput(options)`, since none of
// these pages use ES modules/a bundler (plain <script> includes,
// consistent with every other file in static/js/).
(function () {
    // CLAUDE-MOBILE-Q-TRIAL-01, Section 6: mic discoverability, without a
    // sound. The automatic spoken welcome that used to introduce ARCHIOSK is
    // retired (see static/js/landing.js) because it mispronounced the brand
    // and "wrong pronunciation creates distrust" - but the Product Owner still
    // could not tell the mic was there. So the mic says so itself, silently,
    // once.
    //
    // Four things this must not become, all of them explicit requirements:
    //   - it must never look like active listening. LISTENING is a solid
    //     --attention-amber FILL that persists while the key is held; this is
    //     a thin --machine-blue ring that expands, fades, and extinguishes
    //     itself. Different colour, different mechanism, different lifetime -
    //     and main.css cancels this ring outright while listening, so the two
    //     can never be on screen together.
    //   - it must not request microphone permission. Nothing here touches
    //     getUserMedia or SpeechRecognition; it is a class name and a CSS
    //     keyframe.
    //   - it must respect reduced motion, this codebase's established
    //     convention being to skip non-essential ambient effects outright.
    //   - it must be ONCE. Reviewer-wide, not per page load.
    var CUE_SEEN_KEY = 'beehive:voice-cue-seen';

    function announceAvailabilityOnce(button) {
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        if (button.classList.contains('voice-input-listening')) return;

        var seen = false;
        try {
            seen = !!window.localStorage.getItem(CUE_SEEN_KEY);
        } catch (err) {
            // Private browsing / storage denied: show it for this load rather
            // than failing the whole affordance over a storage quirk. The
            // cost of being wrong here is one extra silent ripple.
            seen = false;
        }
        if (seen) return;

        button.classList.add('voice-input-available-cue');

        function spend() {
            button.classList.remove('voice-input-available-cue');
            try { window.localStorage.setItem(CUE_SEEN_KEY, '1'); } catch (err) { /* nothing to remember it with */ }
        }
        // Whichever comes first: the ripple finishes, or the reviewer presses
        // the mic - a cue that has done its job should not keep animating.
        button.addEventListener('animationend', spend, { once: true });
        button.addEventListener('pointerdown', spend, { once: true });
    }

    function setUpVoiceInput(options) {
        const micButton = document.getElementById(options.buttonId);
        const statusEl = options.statusId ? document.getElementById(options.statusId) : null;
        if (!micButton) return null;

        const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognitionCtor) {
            // Graceful degradation: unsupported browser - the button
            // stays hidden (its own default state), typing/clicking
            // remains the only, fully-equivalent input path.
            return null;
        }

        micButton.hidden = false;
        announceAvailabilityOnce(micButton);

        function setStatus(message, isError) {
            if (!statusEl) return;
            statusEl.textContent = message || '';
            if (isError) statusEl.setAttribute('data-state', 'error');
            else statusEl.removeAttribute('data-state');
        }

        // event.error values a real SpeechRecognition implementation uses
        // (https://wicg.github.io/speech-api/#speechreco-error). "aborted"
        // is deliberately NOT in this map - it fires on our OWN
        // recognition.stop() call below (the Push-to-Talk release), which
        // is normal operation, not a failure to report as one.
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

        const hasOnDeviceApi = typeof SpeechRecognitionCtor.available === 'function'
            && typeof SpeechRecognitionCtor.install === 'function';

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

            recognition.addEventListener('speechstart', () => {
                setStatus('Transcribing…', false);
            });

            recognition.addEventListener('result', (event) => {
                let transcript = '';
                let isFinal = false;
                for (let i = 0; i < event.results.length; i += 1) {
                    transcript += event.results[i][0].transcript;
                    if (event.results[i].isFinal) isFinal = true;
                }
                if (isFinal) gotFinalResult = true;
                if (options.onTranscript) options.onTranscript(transcript, isFinal);
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
                if (!gotFinalResult && (!statusEl || !statusEl.getAttribute('data-state'))) {
                    setStatus(userInitiatedStop ? 'Recognition stopped' : 'No speech detected', !userInitiatedStop);
                } else if (gotFinalResult) {
                    setStatus('', false);
                }
                if (options.onEnd) options.onEnd();
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
                // Push-to-Talk, not push-to-toggle-forever: a second press
                // stops listening early, same as releasing a physical
                // push-to-talk button - not a failure, so "aborted" (fired
                // by this same .stop() call, below) must not be reported
                // as one.
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
            if (userInitiatedStop) return;
            beginListening(useOnDevice);
        });

        return { stopListening };
    }

    window.ArchioskVoiceInput = setUpVoiceInput;
})();
