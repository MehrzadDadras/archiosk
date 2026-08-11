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
