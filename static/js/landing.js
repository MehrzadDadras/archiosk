// CLAUDE-CA1D-PUBLIC-LANDING-01: the aqueous particle field, adapted
// from C:\Archiosk\holodeck\archive\archiosk_holodeck_v_3.html's own
// drawField/resize/buildPoints functions -- same dot-grid-with-cursor-
// push visual language, but with the fish-navigation state machine,
// environment-room switching, and contact-bubble logic all removed
// (those belonged to the deeper Holodeck environment, not this
// commercial front door -- see landing.css's own header comment).
(function () {
    var canvas = document.getElementById('landing-field-canvas');
    if (!canvas) return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
        // Product Owner's own explicit requirement: skip the animated
        // field entirely, not merely slow it down -- the static
        // gradient background in landing.css is the whole visual on
        // its own, no canvas needed.
        canvas.classList.add('is-static');
        return;
    }

    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var width = 1, height = 1, dpr = 1, points = [], raf = null;
    var mouse = { x: -9999, y: -9999 };

    function resize() {
        width = Math.max(1, window.innerWidth);
        height = Math.max(1, window.innerHeight);
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        buildPoints();
    }

    function buildPoints() {
        points = [];
        var spacing = width < 720 ? 30 : 36;
        for (var y = 0; y <= height; y += spacing) {
            for (var x = 0; x <= width; x += spacing) {
                points.push({ baseX: x, baseY: y, size: 1.3 + Math.random() * 1.1 });
            }
        }
    }

    function drawField() {
        ctx.clearRect(0, 0, width, height);
        var gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, 'rgba(8, 36, 44, 0.0)');
        gradient.addColorStop(1, 'rgba(3, 18, 24, 0.0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);

        for (var i = 0; i < points.length; i++) {
            var p = points[i];
            var dx = p.baseX - mouse.x;
            var dy = p.baseY - mouse.y;
            var distance = Math.sqrt(dx * dx + dy * dy);
            var influence = Math.max(0, 1 - distance / 190);
            var push = influence * 22;
            var angle = Math.atan2(dy, dx);
            var px = p.baseX + Math.cos(angle) * push;
            var py = p.baseY + Math.sin(angle) * push;
            ctx.beginPath();
            ctx.arc(px, py, p.size + influence * 1.1, 0, Math.PI * 2);
            // CLAUDE-CA1D-PUBLIC-LANDING-01 (background adjustment): opacity
            // range lowered alongside landing.css's own darker base -- the
            // same dot brightness read as much more prominent once the
            // background got darker; restrained depth, not visible flecks.
            ctx.fillStyle = 'rgba(184, 245, 239,' + (0.08 + influence * 0.24) + ')';
            ctx.fill();
        }
    }

    function tick() {
        drawField();
        raf = requestAnimationFrame(tick);
    }

    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', function (event) {
        mouse.x = event.clientX;
        mouse.y = event.clientY;
    });
    window.addEventListener('mouseleave', function () {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    resize();
    if (raf) cancelAnimationFrame(raf);
    tick();
})();

// CLAUDE-CA1D-PUBLIC-LANDING-01 (addendum): the decorative rotating
// line. Separate IIFE, independent of the canvas above -- naturally a
// no-op on /explore and /start-trial, neither of which has a
// #landing-rotator element. Both the outgoing and incoming line get
// .is-active toggled in the same tick, so their CSS opacity
// transitions run simultaneously -- a real cross-fade, not a
// hide-then-show.
(function () {
    var rotator = document.getElementById('landing-rotator');
    if (!rotator) return;
    var lines = Array.prototype.slice.call(rotator.querySelectorAll('.landing-rotator-line'));
    if (lines.length < 2) return;

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return; // stays on the first (markup-default .is-active) line only

    var index = 0;
    setInterval(function () {
        var nextIndex = (index + 1) % lines.length;
        lines[index].classList.remove('is-active');
        lines[nextIndex].classList.add('is-active');
        index = nextIndex;
    }, 4800);
})();

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

    function spawn(className, content, opts) {
        opts = opts || {};
        var el = document.createElement(content === null ? 'div' : 'span');
        el.className = 'kf-item ' + className;
        if (content !== null) el.textContent = content;
        el.style.left = randomBetween(2, 96) + 'vw';
        el.style.setProperty('--kf-drift', Math.round(randomBetween(-60, 60)) + 'px');
        var duration = randomBetween(opts.minDuration || 22, opts.maxDuration || 38);
        el.style.animationDuration = duration.toFixed(1) + 's';
        el.style.animationDelay = '-' + randomBetween(0, duration).toFixed(1) + 's'; // negative delay: mid-flight from first paint, not a synchronized wave
        if (opts.size) {
            el.style.width = opts.size + 'px';
            el.style.height = opts.size + 'px';
        }
        field.appendChild(el);
    }

    // Counts deliberately small -- "few rather than many" (bubbles) and
    // "sparse" (every text tier). Total field population stays well
    // under what would read as a screensaver.
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
// (CLASSIFIERS below) instead -- never a generative/LLM call, never a
// network request, never a durable record of any kind. This keeps the
// landing mic at Level 2 (Suggest) of the future Voice authority ladder
// (governance/specified-unbuilt/voice-conversational-presence.md,
// Section 6) at most -- it only ever proposes a real, existing link the
// visitor can choose to follow, exactly like the ordinary Explore/
// Request Trial Access/Sign In actions above it, never a silent
// navigation and never an answer beyond what Archiosk's real public
// pages already say.
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

    // Section 6: a small, honest, deterministic router -- never an
    // unconstrained chatbot. First matching pattern wins; falls back to
    // an honest "not sure" reply pointing at Explore rather than
    // inventing capability. hrefs are resolved once at load time from
    // real url_for()-rendered links already on this page (never
    // hardcoded paths), so this can never drift from the real routes.
    var EXPLORE_HREF = document.querySelector('[data-ui-ref="landing.explore"]').getAttribute('href');
    var TRIAL_HREF = document.querySelector('[data-ui-ref="landing.start-trial"]').getAttribute('href');
    var SIGNIN_HREF = document.querySelector('[data-ui-ref="landing.sign-in"]').getAttribute('href');
    var CLASSIFIERS = [
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
            pattern: /sign in|log ?in|my account/i,
            text: 'Here’s where to sign in to your existing Archiosk account.',
            href: SIGNIN_HREF, label: 'Sign In',
        },
        {
            pattern: /trial|try it|get access|get started/i,
            text: 'Self-service trial registration isn’t available yet, but you can request access.',
            href: TRIAL_HREF, label: 'Request Trial Access',
        },
        {
            pattern: /rfp|proposal|procurement|tender/i,
            text: 'It sounds like you’re working with an RFP or similar procurement document — that’s exactly what Archiosk is built for.',
            href: TRIAL_HREF, label: 'Request Trial Access',
        },
        {
            pattern: /explore|what can archiosk|what does archiosk|how do i start/i,
            text: 'Let’s take a look at what Archiosk does.',
            href: EXPLORE_HREF, label: 'Explore Archiosk',
        },
    ];
    var FALLBACK = {
        text: 'I’m not sure yet — here’s a quick look at what Archiosk does.',
        href: EXPLORE_HREF, label: 'Explore Archiosk',
    };

    function classify(transcript) {
        for (var i = 0; i < CLASSIFIERS.length; i += 1) {
            if (CLASSIFIERS[i].pattern.test(transcript)) return CLASSIFIERS[i];
        }
        return FALLBACK;
    }

    function showResult(transcript) {
        var match = classify(transcript);
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
                setStatus('', false);
                showResult(finalTranscript.trim());
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
