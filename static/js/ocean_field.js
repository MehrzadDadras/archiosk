// CLAUDE-CA1D-PUBLIC-LANDING-01: the aqueous particle field, adapted
// from C:\Archiosk\holodeck\archive\archiosk_holodeck_v_3.html's own
// drawField/resize/buildPoints functions -- same dot-grid-with-cursor-
// push visual language, but with the fish-navigation state machine,
// environment-room switching, and contact-bubble logic all removed
// (those belonged to the deeper Holodeck environment, not this
// commercial front door -- see landing.css's own header comment).
//
// CLAUDE-CA1D-SIGNIN-VISUAL-CONTINUITY-01: extracted out of landing.js
// into its own file so the sign-in family (auth_shell.html) can reuse
// the exact same background mechanism as /, /explore, /start-trial
// without also loading landing.js's other, landing-page-specific
// behaviors (the knowledge field, the spoken welcome greeting, the
// voice-input mic) -- none of which belong on an authentication page.
// landing_shell.html loads this file, then landing.js, in that order.
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
        // CLAUDE-MOBILE-SHELL-STABILITY-01: measured from the ELEMENT, never
        // from window.innerWidth.
        //
        // The previous form read window.innerWidth and wrote it back as an
        // explicit pixel style.width. That overrides the CSS `width: 100%`
        // with a fixed number - and on iOS window.innerWidth is the VISUAL
        // viewport, which inflates while the page is rubber-banding or
        // pinch-zoomed. The canvas could therefore become genuinely wider than
        // its container, which is the "starts moving sideways then springs
        // back" the Product Owner reported. .landing-page's own overflow-x
        // was hiding that rather than preventing it.
        //
        // Now: CSS owns the layout size (width/height 100%, already set), and
        // only the BACKING STORE is scaled for device pixel ratio. No pixel
        // width is written at all, so the canvas cannot exceed its container
        // by construction rather than by clamping.
        var rect = canvas.getBoundingClientRect();
        width = Math.max(1, Math.round(rect.width) || canvas.clientWidth || 1);
        height = Math.max(1, Math.round(rect.height) || canvas.clientHeight || 1);
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
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
