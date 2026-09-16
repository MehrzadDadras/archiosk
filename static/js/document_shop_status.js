// CLAUDE-EXAMINATION-ACTIVITY-01 — advance the working indicator without a refresh.
//
// The page already renders the correct label server-side; this only keeps it
// current while the person watches. Everything here degrades to exactly the
// pre-existing behaviour if it does not run: the indicator still shows the
// state it was rendered with, and a manual refresh still works. That is why
// there is no error banner and no retry counter on screen - a polling failure
// is not the customer's problem to read about.
(function () {
    var panel = document.querySelector('[data-ui-ref="document-shop.result.working"]');
    if (!panel) { return; }
    var url = panel.getAttribute('data-status-url');
    var label = panel.querySelector('[data-ui-ref="document-shop.result.working-label"]');
    if (!url || !label) { return; }

    // 3s: fast enough that "Examining document" gives way to "Visual analysis"
    // while the person is still looking, slow enough that a minute of waiting
    // is twenty requests rather than a stream. The two stages together run
    // roughly 45-70s on a real survey.
    var INTERVAL_MS = 3000;
    // Stop long before a stuck examination turns a left-open tab into a
    // permanent poller. The page is still correct afterwards; it simply stops
    // updating itself, which is where it started.
    var MAX_POLLS = 200;
    var polls = 0;

    function tick() {
        if (polls++ >= MAX_POLLS) { return; }
        fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
            .then(function (response) {
                if (!response.ok) { throw new Error('status ' + response.status); }
                return response.json();
            })
            .then(function (data) {
                if (data.done) {
                    // The examination finished. Reload rather than patching the
                    // DOM: the finished page carries findings, a Survey
                    // Reference and a side-by-side that this script has no
                    // business assembling client-side.
                    window.location.reload();
                    return;
                }
                if (data.activity && data.activity !== label.textContent) {
                    label.textContent = data.activity;
                }
                window.setTimeout(tick, INTERVAL_MS);
            })
            .catch(function () {
                // Silent, and deliberately so: the server-rendered label is
                // still true, and a transient network blip is not news.
                window.setTimeout(tick, INTERVAL_MS);
            });
    }

    window.setTimeout(tick, INTERVAL_MS);
})();
