// CLAUDE-CA1D-SIGNIN-VISUAL-CONTINUITY-01: the aqueous canvas particle
// field that used to live here (drawField/resize/buildPoints) moved to
// static/js/ocean_field.js, loaded by landing_shell.html immediately
// before this file, so auth_shell.html can reuse the exact same
// background mechanism without also loading this file's own landing-
// page-specific behaviors below (knowledge field, spoken welcome, voice
// input) -- none of which belong on a sign-in page.

// CLAUDE-CA1D-PUBLIC-LANDING-01 consolidated addendum, Sections B3/C1-C3:
// the ambient knowledge field. Three tiers of sparse, slow-rising
// elements (plus plain bubbles) generated once at load and appended to
// #landing-knowledge-field (landing.css's own .kf-* rules own the
// visual treatment/animation; this only decides count, content,
// placement and per-element timing). Naturally a no-op on /explore and
// /start-trial (neither has the container). Skipped entirely under
// prefers-reduced-motion -- consistent with the canvas particle field
// above, not merely slowed.
(function () {
    var field = document.getElementById('landing-knowledge-field');
    if (!field) return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return; // container stays empty -- CSS also hides it outright as a second guard

    // Tier C1: small knowledge particles -- numbers, plain letters, and
    // real mathematical/musical notation (never invented symbols).
    var PARTICLES = ['7', '42', 'x', 'y', 'e', 'i', 'Q', 'π', '∫', '√', '∞',
        'Δ', '♪', '♫', '♭', '♯', '½', '×', '÷', '∑'];

    // Tier C2: real writing-system fragments a human reader of that
    // script would recognize as an actual word -- never a faux/invented
    // script. Kept to simple, common words meaning "knowledge" (or a
    // very close near-synonym) in each language, so the field stays
    // thematically coherent rather than random foreign text -- see
    // Section C2's own "their meaning is: human knowledge has travelled
    // through many languages" framing. One entry per listed writing
    // system (Latin, Greek, Arabic/Persian, Hebrew, Devanagari, Chinese,
    // Japanese, Korean, Cyrillic), plus a couple of real, standard
    // mathematical/musical symbols already covered above are not
    // repeated here.
    var SCRIPTS = [
        'scientia',      // Latin - "knowledge"
        'γνώση',            // Greek - gnosi, "knowledge"
        'معرفة',            // Arabic - ma'rifa, "knowledge"
        'דעת',                         // Hebrew - da'at, "knowledge"
        'ज्ञान',             // Devanagari - jnana, "knowledge"
        '知识',                                // Chinese - zhishi, "knowledge"
        '知恵',                                // Japanese kanji - chie, "wisdom"
        '지식',                                // Korean Hangul - jisik, "knowledge"
        'знание',       // Cyrillic (Russian) - znaniye, "knowledge"
    ];

    // Tier C3: occasional larger GO domain-intelligence signals -- exact
    // set from the Product Owner's own list. Not links/buttons (no href,
    // no click handler, the whole container is pointer-events: none).
    var TERMS = ['RFP', 'REQUIREMENTS', 'EVIDENCE', 'ADDENDA', 'DRAWINGS', 'RISKS', 'RFI', 'DECISIONS'];

    function randomBetween(min, max) { return min + Math.random() * (max - min); }

    // CLAUDE-CA1D-PUBLIC-LANDING-04: depth + upward-convection model.
    // A visual metaphor only (Section 1's own "not a literal scientific
    // simulation") -- two named lower-field regions an upward current
    // seems to originate from, inferred purely through motion (tighter
    // spawn spread + faster rise), never rendered as a graphic of any
    // kind. Kept as a small, named, reusable structure (not inlined
    // magic numbers) specifically so a future tranche could parameterize
    // VENTS with a "strength" driven by a live question/interaction
    // (Section 8's own "do not build that now, but do not prevent it")
    // without this tranche building that interaction itself.
    // CLAUDE-CA1D-LANDING-BALANCE-01, Section B3: moved further toward
    // the true edges (was 12/88) and probability lowered (was .42) --
    // a live report found the previous, tighter/more-frequent vent
    // cluster reading as an over-dense "hot spot" right at those two
    // x-positions specifically, on top of (not blended with) the
    // ambient population's own edge density, making the far left/right
    // look "programmatically dumped" rather than organic.
    var VENTS = [{ xVw: 7 }, { xVw: 93 }];
    var IN_CURRENT_PROBABILITY = 0.3;

    // CLAUDE-CA1D-PUBLIC-LANDING-05, Section 4: "calm center / active
    // surrounding ocean" -- a quiet horizontal reading column reserved
    // for ARCHIOSK/the tagline/CTAs/the mic control, kept clear of base
    // spawn positions AND of how far an item's own drift can carry it
    // (below), rather than only avoiding the center at spawn time and
    // letting later movement wander back through it. A soft, viewport-
    // percentage heuristic (Section 4/5's own "should not pass through
    // or visually compete," not a literal collision system) -- items
    // still occasionally graze the edge at maximum wander, which reads
    // as organic rather than a rigid force field.
    var CENTER_MIN_VW = 30;
    var CENTER_MAX_VW = 70;
    function clampOutsideCenter(xVw) {
        if (xVw > CENTER_MIN_VW && xVw < CENTER_MAX_VW) {
            return (xVw - (CENTER_MIN_VW + CENTER_MAX_VW) / 2) < 0 ? CENTER_MIN_VW : CENTER_MAX_VW;
        }
        return xVw;
    }

    // CLAUDE-CA1D-LANDING-BALANCE-01, Sections B1/B3: three named
    // left-side sub-bands (outer edge / mid-field / approaching-center),
    // each getting an EQUAL share of the ambient population rather than
    // one wide uniform range. A single uniform [2, CENTER_MIN_VW-4] band
    // is mathematically even everywhere, but with only ~16 ambient items
    // split across two sides, pure chance under-populates the innermost
    // quarter often enough to read as "center too empty" -- a live
    // report's own words. Explicit equal-thirds guarantees a genuine,
    // reliably visible "some approaching the central region" population
    // (Section B1) without ever entering the protected CENTER_MIN_VW/
    // CENTER_MAX_VW column itself.
    var AMBIENT_BANDS_LEFT = [
        [2, 13],                          // outer edge
        [13, 21],                         // mid-field
        [21, CENTER_MIN_VW - 2],          // approaching center (21-28)
    ];
    function pickAmbientLeftVw() {
        var band = AMBIENT_BANDS_LEFT[Math.floor(Math.random() * AMBIENT_BANDS_LEFT.length)];
        return randomBetween(band[0], band[1]);
    }

    // Section 3/4: three perceptual depth layers, weighted so mid-field
    // stays "the principal readable knowledge layer" (Section 3) --
    // most items land there; near/far are the minority accents.
    // scaleRange governs apparent size, peakOpacity governs brightness/
    // contrast, durationMult scales the rise duration set per spawn()
    // call (near = shorter = more apparent movement; far = longer =
    // barely moving, Section 4's own "near = faster... far = slower").
    var DEPTH_CONFIG = {
        near: { weight: .18, scaleRange: [1.25, 1.5], peakOpacity: 1, durationMult: .62, className: 'kf-depth-near' },
        mid: { weight: .54, scaleRange: [.92, 1.05], peakOpacity: .82, durationMult: 1, className: 'kf-depth-mid' },
        far: { weight: .28, scaleRange: [.6, .8], peakOpacity: .5, durationMult: 1.65, className: 'kf-depth-far' },
    };
    function pickDepth() {
        var r = Math.random();
        if (r < DEPTH_CONFIG.near.weight) return 'near';
        if (r < DEPTH_CONFIG.near.weight + DEPTH_CONFIG.mid.weight) return 'mid';
        return 'far';
    }

    function spawn(className, content, opts) {
        opts = opts || {};
        var el = document.createElement(content === null ? 'div' : 'span');
        var depth = pickDepth();
        var depthConfig = DEPTH_CONFIG[depth];
        var inCurrent = Math.random() < IN_CURRENT_PROBABILITY;

        el.className = 'kf-item ' + className + ' ' + depthConfig.className;
        if (content !== null) el.textContent = content;

        if (inCurrent) {
            // Tight spread around one named vent -- "presence should be
            // inferred mainly from motion" (Section 2), never a visible
            // marker at that position. Both VENTS already sit well
            // outside the quiet center column; clampOutsideCenter is a
            // safety net, not the primary mechanism.
            var vent = VENTS[Math.floor(Math.random() * VENTS.length)];
            el.style.left = clampOutsideCenter(Math.min(96, Math.max(2, vent.xVw + randomBetween(-8, 8)))) + 'vw';
        } else {
            // Section 4/5/B1: ambient (non-current) items pick a side,
            // then an equal-thirds sub-band on that side (edge/mid-field/
            // approaching-center, mirrored via 100-x for the right side)
            // -- never inside the quiet center column, but no longer
            // left to pure uniform-range chance to populate the region
            // nearest it either.
            var leftBand = Math.random() < 0.5;
            var leftVw = pickAmbientLeftVw();
            el.style.left = (leftBand ? leftVw : 100 - leftVw) + 'vw';
        }

        // Three independently-randomized drift stops (Section 2's own
        // "may widen or gently meander as it rises... drift sideways or
        // spiral slightly as they leave the strongest part of the
        // current") -- a current member starts tight and widens toward
        // the top of its rise; an ambient item wanders gently and evenly
        // throughout, never a rigid vertical column either way. Ranges
        // tightened from the LANDING-04 baseline (Section 4/5's own
        // "should not pass through... the central zone") so drift alone
        // rarely carries a peripheral spawn back into the quiet center.
        var wander = inCurrent ? [8, 14, 20] : [5, 7, 9];
        el.style.setProperty('--kf-drift-1', Math.round(randomBetween(-wander[0], wander[0])) + 'px');
        el.style.setProperty('--kf-drift-2', Math.round(randomBetween(-wander[1], wander[1])) + 'px');
        el.style.setProperty('--kf-drift-3', Math.round(randomBetween(-wander[2], wander[2])) + 'px');

        el.style.setProperty('--kf-scale', randomBetween(depthConfig.scaleRange[0], depthConfig.scaleRange[1]).toFixed(2));
        el.style.setProperty('--kf-peak-opacity', depthConfig.peakOpacity);

        // A current accelerates its own members (Section 2: "particles
        // accelerate slightly upward" within a vent) on top of the
        // depth-driven speed difference (Section 4).
        var currentMult = inCurrent ? .78 : 1;
        var baseMin = (opts.minDuration || 22) * depthConfig.durationMult * currentMult;
        var baseMax = (opts.maxDuration || 38) * depthConfig.durationMult * currentMult;
        var duration = randomBetween(baseMin, baseMax);
        el.style.animationDuration = duration.toFixed(1) + 's';
        el.style.animationDelay = '-' + randomBetween(0, duration).toFixed(1) + 's'; // negative delay: mid-flight from first paint, not a synchronized wave

        if (opts.size) {
            el.style.width = opts.size + 'px';
            el.style.height = opts.size + 'px';
        }
        field.appendChild(el);
    }

    // Counts deliberately unchanged from the previous tranche -- "few
    // rather than many" (bubbles), "sparse" (every text tier), and
    // Section 10's own "prefer a small number of well-behaved objects
    // over hundreds of decorative elements." Depth/current membership
    // is decided per-item inside spawn() above, not by adding more
    // items. Bubbles now run through the exact same spawn() as every
    // other tier (Section 7: "should not feel like an unrelated
    // decorative overlay... integrate them into the same circulation
    // logic") rather than a separate code path.
    for (var b = 0; b < 7; b++) {
        spawn('kf-bubble', null, { size: Math.round(randomBetween(6, 16)), minDuration: 26, maxDuration: 46 });
    }
    for (var p = 0; p < 8; p++) {
        spawn('kf-particle', PARTICLES[Math.floor(Math.random() * PARTICLES.length)], { minDuration: 20, maxDuration: 34 });
    }
    for (var s = 0; s < 8; s++) {
        spawn('kf-script', SCRIPTS[Math.floor(Math.random() * SCRIPTS.length)], { minDuration: 24, maxDuration: 40 });
    }
    for (var t = 0; t < 5; t++) {
        spawn('kf-term', TERMS[Math.floor(Math.random() * TERMS.length)], { minDuration: 30, maxDuration: 48 });
    }
})();

// CLAUDE-CA1D-PUBLIC-LANDING-05, Sections 2/3: the spoken welcome --
// carries the same philosophy the visible rotating line used to carry
// (now removed outright, Section 2's own "do not replace them with
// another visual text carousel"). Browser-native SpeechSynthesis --
// no vendor, no API key, no network request, no dependency, exactly
// the same "browser-native needs no new Product Owner decision"
// reasoning already established for the mic's own SpeechRecognition
// (CLAUDE-POSTCAMEL-VOICE1-PRE). Section 3's own explicit browser-
// autoplay caveat: this makes ONE best-effort attempt shortly after
// load (works today in most desktop Chrome profiles without a gesture),
// and ALSO arms a one-time fallback on the very first real user
// interaction (pointerdown/keydown/touchstart) -- whichever fires
// first wins, `spoken` makes the two paths mutually exclusive, so a
// browser that blocks the immediate attempt still greets the visitor
// at the first meaningful interaction rather than staying silent
// forever. sessionStorage (not localStorage) -- "do not repeatedly
// replay it on every navigation or refresh without reason": silent for
// the rest of THIS tab's session once spoken, but a fresh tab/window
// (a genuinely new visit) is greeted again. Gated off entirely under
// prefers-reduced-motion -- this codebase's own established convention
// treats that preference as "skip non-essential ambient effects
// outright," and the same meaning remains available in text on
// /explore.
(function setUpSpokenWelcome() {
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    var STORAGE_KEY = 'archiosk-welcome-spoken';
    var GREETING = 'Welcome to Archiosk. We learn together. From many questions, understanding. From many minds, connected knowledge.';
    var spoken = false;

    function speakGreeting() {
        if (spoken) return;
        try {
            if (sessionStorage.getItem(STORAGE_KEY)) { spoken = true; return; }
            sessionStorage.setItem(STORAGE_KEY, '1');
        } catch (err) {
            // Private-browsing/storage-denied environments: fall through
            // and speak once for this page load anyway rather than
            // silently failing the whole feature over a storage quirk.
        }
        spoken = true;
        var utterance = new SpeechSynthesisUtterance(GREETING);
        utterance.rate = 0.95;
        utterance.pitch = 1;
        window.speechSynthesis.speak(utterance);
    }

    window.setTimeout(speakGreeting, 900);

    ['pointerdown', 'keydown', 'touchstart'].forEach(function (evt) {
        document.addEventListener(evt, speakGreeting, { once: true, passive: true });
    });
})();

// CLAUDE-CA1D-PUBLIC-LANDING-03, Sections 3-8: "Speak to Archiosk" --
// the landing page's own bounded voice-entry path. Deliberately mirrors
// static/js/case_workspace.js's own setUpVoiceInput (CLAUDE-POSTCAMEL-
// VOICE1-PRE) as closely as possible -- same browser-native
// SpeechRecognition mechanism (no vendor, no API key, no server round
// trip, no audio blob ever handled by this code), same push-to-talk
// model, same hidden-until-feature-detected default, same
// ERROR_MESSAGES vocabulary, same voice-input-listening state class.
// The one real difference: there is no existing draft/composer field on
// this public, unauthenticated page to fill, so a final transcript is
// run through a small, deterministic, client-side-only keyword lookup
// instead -- never a generative/LLM call, never a network request,
// never a durable record of any kind. CLAUDE-CA1D-PUBLIC-LANDING-05,
// Sections 9/10: a clear, safe, local navigation command (DIRECT_NAV
// below -- Sign In/Explore/Request Trial Access only) executes directly,
// no second click and no response card duplicating a button already on
// the page; anything less direct still gets the small informational
// response card (INFORMATIONAL below) rather than guessing. This keeps
// the landing mic at Level 2/3 (Suggest / reversible local navigation)
// of the future Voice authority ladder (governance/specified-unbuilt/
// voice-conversational-presence.md, Section 6) at most -- never Level
// 4/5, never anything destructive/authenticated/consequential.
(function setUpLandingVoiceInput() {
    var micButton = document.getElementById('landing-voice-button');
    var statusEl = document.getElementById('landing-voice-status');
    var resultEl = document.getElementById('landing-voice-result');
    if (!micButton || !resultEl) return;

    var SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
        // Graceful degradation (Section 5): unsupported browser -- the
        // button stays hidden (its own default state); the real Explore/
        // Request Trial Access/Sign In actions above remain the fully
        // equivalent path. Nothing to show here.
        return;
    }

    micButton.hidden = false;

    function setStatus(message, isError) {
        if (!statusEl) return;
        statusEl.textContent = message || '';
        if (isError) statusEl.setAttribute('data-state', 'error');
        else statusEl.removeAttribute('data-state');
    }

    var ERROR_MESSAGES = {
        'not-allowed': 'Microphone permission denied',
        'service-not-allowed': 'Microphone permission denied',
        'permission-denied': 'Microphone permission denied',
        'audio-capture': 'No microphone available',
        'no-speech': 'No speech detected',
        'network': 'Speech recognition unavailable in this browser',
        'language-not-supported': 'Speech recognition unavailable in this browser',
    };

    // hrefs are resolved once at load time from real url_for()-rendered
    // links already on this page (never hardcoded paths), so this can
    // never drift from the real routes.
    var EXPLORE_HREF = document.querySelector('[data-ui-ref="landing.explore"]').getAttribute('href');
    var TRIAL_HREF = document.querySelector('[data-ui-ref="landing.start-trial"]').getAttribute('href');
    var SIGNIN_HREF = document.querySelector('[data-ui-ref="landing.sign-in"]').getAttribute('href');

    // CLAUDE-CA1D-PUBLIC-LANDING-05, Sections 9/10: clear, reversible,
    // local navigation commands execute DIRECTLY -- no second click, no
    // response card repeating a button already on this page. Checked
    // BEFORE the informational classifiers below; matches the Product
    // Owner's own three named examples exactly (the same patterns that,
    // before this tranche, matched an informational card pointing at
    // these same three destinations -- Section 9 only changes WHAT
    // happens on a match, not which utterances are recognized).
    // Deliberately NOT generalized beyond these three safe, local,
    // reversible destinations (Section 9's own explicit boundary) --
    // nothing here ever creates, changes, or sends anything.
    var DIRECT_NAV = [
        { pattern: /sign in|log ?in|my account|sign me in/i, href: SIGNIN_HREF, confirmText: 'Opening Sign In…' },
        { pattern: /trial|try it|get access|get started/i, href: TRIAL_HREF, confirmText: 'Opening Request Trial Access…' },
        { pattern: /explore|what can archiosk|what does archiosk|how do i start/i, href: EXPLORE_HREF, confirmText: 'Opening Explore…' },
    ];

    // Section 6/10: genuinely informational asks (not a "go there"
    // command) still get a small, honest, deterministic response card
    // -- never an unconstrained chatbot, never a generative/LLM call.
    var INFORMATIONAL = [
        {
            pattern: /learning holodeck|holodeck/i,
            text: 'The Learning Holodeck is a future initiative and isn’t available yet. Right now, Archiosk turns your project documents into governed, evidence-backed answers.',
            href: EXPLORE_HREF, label: 'See what Archiosk does today',
        },
        {
            pattern: /without an account|no account/i,
            text: 'Yes — Explore doesn’t require an account or any commitment.',
            href: EXPLORE_HREF, label: 'Explore Archiosk',
        },
        {
            pattern: /rfp|proposal|procurement|tender/i,
            text: 'It sounds like you’re working with an RFP or similar procurement document — that’s exactly what Archiosk is built for.',
            href: TRIAL_HREF, label: 'Request Trial Access',
        },
    ];
    var FALLBACK = {
        text: 'I’m not sure yet — here’s a quick look at what Archiosk does.',
        href: EXPLORE_HREF, label: 'Explore Archiosk',
    };

    // Section 9's own "ambiguous commands should clarify rather than
    // guess": a transcript only ever executes direct navigation on an
    // actual pattern match here -- everything else, including anything
    // ambiguous, falls through to the informational path (a real
    // response, never a silent/guessed navigation).
    function classifyDirectNav(transcript) {
        for (var i = 0; i < DIRECT_NAV.length; i += 1) {
            if (DIRECT_NAV[i].pattern.test(transcript)) return DIRECT_NAV[i];
        }
        return null;
    }

    function classifyInformational(transcript) {
        for (var i = 0; i < INFORMATIONAL.length; i += 1) {
            if (INFORMATIONAL[i].pattern.test(transcript)) return INFORMATIONAL[i];
        }
        return FALLBACK;
    }

    function showResult(transcript) {
        var match = classifyInformational(transcript);
        resultEl.innerHTML = '';
        var transcriptLine = document.createElement('span');
        transcriptLine.className = 'landing-voice-transcript';
        transcriptLine.textContent = '“' + transcript + '”';
        var responseLine = document.createElement('p');
        responseLine.style.margin = '0 0 10px';
        responseLine.textContent = match.text;
        var link = document.createElement('a');
        link.href = match.href;
        link.textContent = match.label;
        resultEl.appendChild(transcriptLine);
        resultEl.appendChild(responseLine);
        resultEl.appendChild(link);
        resultEl.hidden = false;
    }

    var recognition = null;
    var listening = false;
    var userInitiatedStop = false;
    var gotFinalResult = false;
    var finalTranscript = '';

    function stopListening() {
        listening = false;
        micButton.classList.remove('voice-input-listening');
        micButton.setAttribute('aria-pressed', 'false');
    }

    var hasOnDeviceApi = typeof SpeechRecognitionCtor.available === 'function'
        && typeof SpeechRecognitionCtor.install === 'function';

    async function ensureOnDeviceReady(lang) {
        if (!hasOnDeviceApi) return false;
        var state;
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

        recognition.addEventListener('speechstart', function () {
            setStatus('Transcribing…', false);
        });

        recognition.addEventListener('result', function (event) {
            var transcript = '';
            for (var i = 0; i < event.results.length; i += 1) {
                transcript += event.results[i][0].transcript;
                if (event.results[i].isFinal) gotFinalResult = true;
            }
            finalTranscript = transcript;
            setStatus('Transcribing…', false);
        });

        recognition.addEventListener('error', function (event) {
            if (event.error === 'aborted' && userInitiatedStop) {
                setStatus('Recognition stopped', false);
            } else {
                setStatus(ERROR_MESSAGES[event.error] || 'Speech recognition unavailable in this browser', true);
            }
            stopListening();
        });

        recognition.addEventListener('end', function () {
            stopListening();
            if (gotFinalResult && finalTranscript.trim()) {
                var transcript = finalTranscript.trim();
                var navMatch = classifyDirectNav(transcript);
                if (navMatch) {
                    // Section 9/10: execute directly, no response card
                    // duplicating a button already on this page -- the
                    // brief confirmText (reusing the existing status
                    // live region) is the only feedback before the real
                    // navigation happens, so the visitor still perceives
                    // cause and effect rather than an instant jump.
                    setStatus(navMatch.confirmText, false);
                    window.setTimeout(function () { window.location.href = navMatch.href; }, 350);
                } else {
                    setStatus('', false);
                    showResult(transcript);
                }
            } else if (!statusEl || !statusEl.getAttribute('data-state')) {
                setStatus(userInitiatedStop ? 'Recognition stopped' : 'No speech detected', !userInitiatedStop);
            }
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

    micButton.addEventListener('click', async function () {
        if (listening) {
            // Push-to-Talk, not push-to-toggle-forever (Section 5's own
            // "provide an obvious cancel/stop control").
            userInitiatedStop = true;
            if (recognition) recognition.stop();
            stopListening();
            return;
        }

        userInitiatedStop = false;
        gotFinalResult = false;
        finalTranscript = '';
        resultEl.hidden = true;
        setStatus('Listening…', false);

        var lang = document.documentElement.lang || 'en-US';
        var useOnDevice = await ensureOnDeviceReady(lang);
        if (userInitiatedStop) return;
        beginListening(useOnDevice);
    });
})();
