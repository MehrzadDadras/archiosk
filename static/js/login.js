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
(function () {
    var toggle = document.getElementById('password-toggle');
    var input = document.getElementById('password');
    if (!toggle || !input) return;
    var showIcon = toggle.querySelector('.password-toggle-icon-show');
    var hideIcon = toggle.querySelector('.password-toggle-icon-hide');
    toggle.addEventListener('click', function () {
        var revealed = input.type === 'text';
        input.type = revealed ? 'password' : 'text';
        toggle.setAttribute('aria-pressed', String(!revealed));
        toggle.setAttribute('aria-label', revealed ? 'Show password' : 'Hide password');
        showIcon.hidden = !revealed;
        hideIcon.hidden = revealed;
    });
})();
