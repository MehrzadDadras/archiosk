// CLAUDE-CA1D-RECEPTION-FIX-01: password reveal/hide toggle for the
// sign-in form. External file, not inline - this app's real CSP
// (deploy/nginx.conf: default-src 'self', no 'unsafe-inline', no
// nonce) blocks inline <script> execution outright. A live-browser
// check against the deployed instance found an earlier inline-script
// version of this silently never ran (no console error either - CSP
// violations don't always surface as console.error) - confirmed via
// a direct securitypolicyviolation-style test before this file
// existed. Client-side display only; never touches the posted
// credential or services/auth.py's authentication logic.
//
// CLAUDE-SIGNIN-EYE-VISIBILITY-01: this used to also set showIcon.hidden/
// hideIcon.hidden directly, but `hidden` has no effect on SVG elements in
// Chromium (confirmed live: hasAttribute('hidden') was true yet computed
// display stayed "block" - Blink's SVG UA stylesheet doesn't define a
// [hidden] rule the way html.css does for HTML elements), so both icons
// were always visible at once, permanently superimposed - a live Product
// Owner report ("the toggle eyes are beside each other which is
// confusing") is exactly this. aria-pressed is now the single source of
// truth for which icon shows - static/css/main.css's own
// .password-toggle[aria-pressed=...] rule keys off it directly, so this
// function only needs to keep toggling that one attribute correctly.
(function () {
    var toggle = document.getElementById('password-toggle');
    var input = document.getElementById('password');
    if (!toggle || !input) return;
    toggle.addEventListener('click', function () {
        var revealed = input.type === 'text';
        input.type = revealed ? 'password' : 'text';
        toggle.setAttribute('aria-pressed', String(!revealed));
        toggle.setAttribute('aria-label', revealed ? 'Show password' : 'Hide password');
    });
})();
