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
