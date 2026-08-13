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

// CLAUDE-VOICE-CONSISTENCY-01: pre-authentication voice - Level 2/3 of
// the future Voice authority ladder only (governance/specified-unbuilt/
// voice-conversational-presence.md, Section 6: Suggest / Reversible
// local action), mirroring static/js/landing.js's own DIRECT_NAV
// pattern exactly (same authority ceiling, same "client-side keyword
// match, no server round trip, no LLM" approach) - the smallest safe
// pre-auth surface, not a new one. There is no composer/draft field on
// this page the way the in-project Chat has, so a final transcript is
// matched against a small, fixed command list instead of filling a
// field for review - but exactly like the composer's own voice input,
// it NEVER auto-submits the form itself; the human still clicks Sign In.
// Never targets the password field for dictation and never reads back
// or exposes any field's value (nothing here performs text-to-speech
// in either direction) - satisfies "must not speak stored passwords /
// expose credential values" by construction, not by convention.
(function () {
    if (!window.ArchioskVoiceInput) return;
    var usernameInput = document.getElementById('username');
    var passwordInput = document.getElementById('password');
    var signInButton = document.querySelector('[data-ui-ref="auth.signin.submit"]');
    var forgotLink = document.getElementById('forgot-password-link');
    var statusEl = document.getElementById('signin-voice-status');

    var COMMANDS = [
        { pattern: /forgot|reset (my )?password/i, run: function () {
            if (forgotLink) window.location.href = forgotLink.getAttribute('href');
        } },
        { pattern: /sign in|log ?in/i, run: function () {
            // Level 3 "change visible focus" only - never submits. If a
            // field is still empty, focus it instead so the human's next
            // keystroke lands somewhere useful either way.
            if (usernameInput && !usernameInput.value) usernameInput.focus();
            else if (passwordInput && !passwordInput.value) passwordInput.focus();
            else if (signInButton) signInButton.focus();
        } },
    ];

    // ArchioskVoiceInput's onTranscript fires on every partial result;
    // a command should only run once, on the final transcript (a
    // "deliberate completion signal before interpreting any command" -
    // same principle static/js/landing.js's own voice input already
    // established) - tracked here and matched in onEnd, not per partial
    // result.
    var lastTranscript = '';

    window.ArchioskVoiceInput({
        buttonId: 'signin-voice',
        statusId: 'signin-voice-status',
        onTranscript: function (transcript) { lastTranscript = transcript; },
        onEnd: function () {
            var transcript = lastTranscript.trim();
            lastTranscript = '';
            if (!transcript) return;
            for (var i = 0; i < COMMANDS.length; i += 1) {
                if (COMMANDS[i].pattern.test(transcript)) {
                    COMMANDS[i].run();
                    return;
                }
            }
            if (statusEl) statusEl.textContent = "Try: “forgot password” or “sign in”";
        },
    });
})();
