/* CLAUDE-LANDING-SONIC-01 — the ARCHIOSK startup cue.
 *
 * EXPERIMENTAL. Not brand governance. Nothing is promoted until the Product
 * Owner has heard it on a physical phone and accepted it.
 *
 * Product Owner: "a brief, original ARCHIOSK sonic identity that feels
 * intelligent; anticipatory; architectural/technical; energetic but controlled;
 * like a system becoming ready... a very short startup cue / sonic logo, not
 * music... low/grounded opening pulse; upward or opening tonal movement; clean
 * bright resolution."
 *
 * ── WHAT ALREADY EXISTED, AND WHAT THIS DELIBERATELY DOES NOT REUSE ─────────
 *
 * static/js/voice_input.js is the only audio code in this application, and it
 * is INPUT only — the browser's own SpeechRecognition, which captures and
 * discards its audio internally and hands back a text transcript. There is no
 * playback path anywhere to reuse, and no <audio> element in any template.
 *
 * There WAS an output path: CLAUDE-RECEPTION-VOICE-01's automatic spoken
 * welcome, removed in aec1b04 on an explicit Product Owner instruction — "Do
 * not play an automatic welcome sound. Do not automatically speak ARCHIOSK...
 * wrong pronunciation creates distrust. Voice must remain opt-in."
 *
 * That instruction is worth stating plainly rather than quietly stepping past,
 * because this file plays a sound on the landing page and that is the surface
 * the instruction was about. What was rejected was a SPOKEN greeting that
 * mispronounced the brand; this mission explicitly opens with "this is not a
 * spoken welcome." So this file must never be able to become one — it does not
 * touch speechSynthesis, touches no utterance, says no word, and requests no
 * microphone permission. It is three oscillators. If the Product Owner does not
 * accept it, deleting this file and its two lines of wiring removes it
 * completely, exactly as the greeting's removal did.
 *
 * ── WHY SYNTHESIS AND NOT AN AUDIO FILE ────────────────────────────────────
 *
 * "Keep the sound asset small and performant." Taken literally, the smallest
 * possible asset is no asset: this is generated from oscillators at play time,
 * so there is no file to fetch, no codec to decode, no cache entry, and nothing
 * the service worker has to reason about. It also keeps the sonic identity
 * reviewable in a diff — the cue's character is the numbers below, which can be
 * argued with, rather than an opaque binary.
 *
 * ── THE SOUND, AND HOW IT MAPS TO THE MARK ─────────────────────────────────
 *
 * The landing mark is a closed base with two arms rising out of it and a bright
 * accent at the waist. The cue is that shape in time:
 *
 *   GROUND    110 Hz sine, fast attack, gone in half a second.
 *             The closed base. Low and brief — grounded, not a drone.
 *   RISE      a glide from 196 Hz to 587 Hz behind an opening low-pass filter.
 *             The arms. This is the "forward motion", and the filter opening
 *             with it is what makes it read as ARRIVING rather than merely
 *             getting higher.
 *   ARRIVAL   880 Hz and 1318.5 Hz together — an open fifth — with a short
 *             bell decay. The waist accent. An open fifth resolves cleanly
 *             without committing to major or minor, which is what keeps it from
 *             sounding triumphant; a major third here would be a fanfare, and a
 *             fanfare is the "theatrical" the mission rules out.
 *
 * ORIGINALITY: this is a filtered glide into a bare fifth, not a melody. It
 * imitates nothing — deliberately no rising four-note motif, no orchestral
 * swell, no bloom-and-sustain chord. Total length ~1.4s.
 *
 * Peak amplitude is held low on purpose. A startup cue that is loud once is a
 * cue people disable forever.
 */
(function () {
    'use strict';

    var MUTED_KEY = 'archiosk:sonic-cue-muted';
    var PLAYED_KEY = 'archiosk:sonic-cue-played';

    var AudioCtx = window.AudioContext || window.webkitAudioContext;

    function storage(kind) {
        // Private mode and locked-down browsers throw on access, not on use.
        try { return window[kind]; } catch (error) { return null; }
    }

    function isMuted() {
        var store = storage('localStorage');
        if (!store) return false;
        try { return store.getItem(MUTED_KEY) === '1'; } catch (error) { return false; }
    }

    function setMuted(muted) {
        var store = storage('localStorage');
        if (!store) return;
        try {
            if (muted) store.setItem(MUTED_KEY, '1');
            else store.removeItem(MUTED_KEY);
        } catch (error) { /* preference simply does not persist */ }
    }

    function alreadyPlayedThisSession() {
        var store = storage('sessionStorage');
        if (!store) return false;
        try { return store.getItem(PLAYED_KEY) === '1'; } catch (error) { return false; }
    }

    function markPlayed() {
        var store = storage('sessionStorage');
        if (!store) return;
        try { store.setItem(PLAYED_KEY, '1'); } catch (error) { /* replays next nav */ }
    }

    /* Session storage, not local: "do not replay on every internal navigation"
     * needs a flag that survives navigation within one visit, and "play once on
     * a deliberate app/landing launch" needs one that does NOT survive closing
     * the app. That is exactly sessionStorage's lifetime, so a cold launch of
     * an installed PWA plays and a tap back to the landing page does not. */

    function synthesise(ctx) {
        var t = ctx.currentTime + 0.02;

        var master = ctx.createGain();
        master.gain.value = 0.5;
        master.connect(ctx.destination);

        // Every envelope below starts and ends at 0.0001 rather than 0:
        // exponentialRampToValueAtTime cannot touch zero, and a linear ramp to
        // zero is what produces the click that makes a cue sound cheap.
        function envelope(peak, attack, release, start) {
            var gain = ctx.createGain();
            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(peak, start + attack);
            gain.gain.exponentialRampToValueAtTime(0.0001, start + release);
            gain.connect(master);
            return gain;
        }

        // GROUND — the closed base.
        var ground = ctx.createOscillator();
        ground.type = 'sine';
        ground.frequency.setValueAtTime(110, t);
        var groundGain = envelope(0.16, 0.012, 0.55, t);
        ground.connect(groundGain);
        ground.start(t);
        ground.stop(t + 0.6);

        // RISE — the arms, behind a filter that opens with them.
        var riseStart = t + 0.09;
        var rise = ctx.createOscillator();
        rise.type = 'triangle';
        rise.frequency.setValueAtTime(196, riseStart);
        rise.frequency.exponentialRampToValueAtTime(587, riseStart + 0.42);
        var riseFilter = ctx.createBiquadFilter();
        riseFilter.type = 'lowpass';
        riseFilter.Q.value = 0.7;
        riseFilter.frequency.setValueAtTime(700, riseStart);
        riseFilter.frequency.exponentialRampToValueAtTime(4200, riseStart + 0.45);
        var riseGain = envelope(0.10, 0.06, 0.55, riseStart);
        rise.connect(riseFilter);
        riseFilter.connect(riseGain);
        rise.start(riseStart);
        rise.stop(riseStart + 0.6);

        // ARRIVAL — an open fifth, short bell decay. No third: a third would
        // pick major or minor and turn a signal into a fanfare.
        var arrival = t + 0.50;
        [[880, 0.085, 0.85], [1318.5, 0.05, 0.75], [2637, 0.012, 0.55]].forEach(function (voice) {
            var osc = ctx.createOscillator();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(voice[0], arrival);
            var gain = envelope(voice[1], 0.008, voice[2], arrival);
            osc.connect(gain);
            osc.start(arrival);
            osc.stop(arrival + voice[2] + 0.05);
        });

        // Release the hardware once the cue is finished. Holding an open
        // AudioContext for the life of the page is what makes a phone show a
        // persistent audio indicator for a sound that lasted a second.
        window.setTimeout(function () {
            if (ctx.close) ctx.close();
        }, 2000);
    }

    var context = null;
    var pending = false;

    function play() {
        if (!AudioCtx || isMuted() || alreadyPlayedThisSession()) return false;
        try {
            if (!context) context = new AudioCtx();
        } catch (error) {
            return false;
        }
        if (context.state === 'suspended') return false;
        markPlayed();
        try {
            synthesise(context);
        } catch (error) {
            return false;
        }
        return true;
    }

    /* ── PLATFORM REALITY ───────────────────────────────────────────────────
     *
     * Checked before writing this rather than assumed, because the mission asks
     * for it honestly:
     *
     * iOS (Safari, and every other iOS browser — they all use WKWebView):
     *   an AudioContext is created SUSPENDED and can only be resumed from
     *   inside a real user-gesture handler. Installing to the home screen and
     *   running standalone does NOT lift this. A cold launch therefore CANNOT
     *   make a sound on iPhone, and no amount of engineering changes that.
     *   Separately, the hardware silent switch mutes Web Audio in Safari, so
     *   even a correctly gesture-triggered cue is silent on a phone set to
     *   silent — which will look like a bug and is not one.
     *
     * Android/Chrome:
     *   audible autoplay is gated by the Media Engagement Index, and an
     *   installed PWA is one of the documented conditions that satisfies it.
     *   So an installed ARCHIOSK on Android plausibly CAN sound on launch,
     *   while the same page in a browser tab on a first visit will not.
     *
     * Desktop Firefox/Safari: blocked by default without prior interaction.
     *
     * So the design is: TRY, and if the platform says no, ARM — play at the
     * first real gesture instead. On iPhone that gesture is normally the tap on
     * Explore / Request Trial Access / Sign In, which means the cue sounds at
     * the moment of entering rather than the moment of arriving. That is a
     * worse moment, and it is the honest one; the alternative is a silent-audio
     * unlock trick, which is precisely the "workaround that violates expected
     * browser behavior" the mission rules out.
     */
    var GESTURES = ['pointerdown', 'keydown', 'touchend'];

    function disarm() {
        GESTURES.forEach(function (name) {
            document.removeEventListener(name, onGesture, true);
        });
        pending = false;
    }

    function onGesture() {
        if (!pending) return;
        disarm();
        if (!AudioCtx || isMuted() || alreadyPlayedThisSession()) return;
        try {
            if (!context) context = new AudioCtx();
        } catch (error) {
            return;
        }
        var resumed = context.resume ? context.resume() : null;
        if (resumed && resumed.then) resumed.then(play, function () { /* platform said no */ });
        else play();
    }

    function arm() {
        if (pending || !AudioCtx || isMuted() || alreadyPlayedThisSession()) return;
        pending = true;
        GESTURES.forEach(function (name) {
            // Capture phase, so a tap on a link still triggers the cue before
            // the navigation begins.
            document.addEventListener(name, onGesture, true);
        });
    }

    function start() {
        // Reduced motion is this codebase's established signal for "skip the
        // ambient, non-essential layer" (the canvas field, the knowledge field
        // and the mic ring all already honour it). An unrequested sound is the
        // same category of thing, so it honours it too. Nothing the application
        // MEANS is carried by this cue — it is decoration, and silence costs
        // the user nothing.
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        if (!play()) arm();
    }

    // ── The mute control ────────────────────────────────────────────────────
    // Revealed rather than rendered, matching the mic button's own established
    // "hidden until feature-detected" pattern: a browser with no Web Audio
    // would otherwise show a control for a sound it can never make.
    function wireToggle() {
        var button = document.getElementById('landing-sound-toggle');
        if (!button || !AudioCtx) return;
        button.hidden = false;

        function render() {
            var muted = isMuted();
            button.setAttribute('aria-pressed', muted ? 'true' : 'false');
            button.setAttribute(
                'aria-label',
                muted ? 'Startup sound off — turn it on' : 'Startup sound on — turn it off'
            );
            button.title = muted ? 'Startup sound off' : 'Startup sound on';
            button.textContent = muted ? '🔇' : '🔈';
        }

        button.addEventListener('click', function () {
            var muted = !isMuted();
            setMuted(muted);
            render();
            if (muted) {
                disarm();
            } else {
                // Turning it back on is itself a gesture, so this is the one
                // moment a preview is both possible and warranted - otherwise
                // the control gives no evidence it did anything.
                var store = storage('sessionStorage');
                try { if (store) store.removeItem(PLAYED_KEY); } catch (error) { /* no-op */ }
                onGesturePreview();
            }
        });

        render();
    }

    function onGesturePreview() {
        if (!AudioCtx) return;
        try {
            if (!context) context = new AudioCtx();
        } catch (error) {
            return;
        }
        var resumed = context.resume ? context.resume() : null;
        if (resumed && resumed.then) resumed.then(play, function () { /* platform said no */ });
        else play();
    }

    window.ArchioskSonicCue = {
        play: play,
        arm: arm,
        isMuted: isMuted,
        setMuted: setMuted,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { wireToggle(); start(); });
    } else {
        wireToggle();
        start();
    }
})();
