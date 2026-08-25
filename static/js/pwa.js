/* CLAUDE-MOBILE-PWA-01 — registration and the update notice.
 *
 * Product Owner: "users should not need to reinstall to receive updates;
 * deployed application updates must flow normally to installed users;
 * service-worker/cache behavior must not freeze users on old shells; a safe,
 * unobtrusive update/reload notice may be shown when required."
 *
 * Two jobs, both small:
 *   1. register the worker;
 *   2. when a NEW worker takes over, offer a reload - never perform one.
 *
 * A page that reloads itself is the worst possible behaviour here: it can
 * discard a half-typed Composer message, and on a phone the reviewer may be
 * standing on site with one hand. The notice is an offer, dismissible, and
 * the work underneath it is untouched until they choose.
 */
(function () {
    'use strict';

    if (!('serviceWorker' in navigator)) return;

    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {
        // Registration failure must never break the page. ARCHIOSK is a normal
        // web application first and an installable one second - everything
        // works without a worker, which is also why an install failure is not
        // worth telling the reviewer about.
    });

    function offerReload() {
        if (document.getElementById('archiosk-update-notice')) return;

        var notice = document.createElement('div');
        notice.id = 'archiosk-update-notice';
        notice.className = 'update-notice';
        notice.setAttribute('role', 'status');

        var text = document.createElement('span');
        text.className = 'update-notice-text';
        text.textContent = 'A new version of ARCHIOSK is ready.';

        var reload = document.createElement('button');
        reload.type = 'button';
        reload.className = 'update-notice-action';
        reload.textContent = 'Reload';
        reload.addEventListener('click', function () {
            window.location.reload();
        });

        var dismiss = document.createElement('button');
        dismiss.type = 'button';
        dismiss.className = 'update-notice-dismiss';
        dismiss.setAttribute('aria-label', 'Dismiss');
        dismiss.textContent = '×';
        dismiss.addEventListener('click', function () {
            notice.remove();
        });

        notice.appendChild(text);
        notice.appendChild(reload);
        notice.appendChild(dismiss);
        document.body.appendChild(notice);
    }

    // The worker posts this from its own activate handler, which only runs when
    // a genuinely new version has taken over.
    navigator.serviceWorker.addEventListener('message', function (event) {
        if (event.data && event.data.type === 'archiosk:updated') offerReload();
    });

    // A controller change means a new worker is now driving this page. On the
    // very first registration there was no previous controller, and that is not
    // an update - offering a reload there would greet a first-time visitor with
    // a notice about a version they never had.
    var hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener('controllerchange', function () {
        if (hadController) offerReload();
        hadController = true;
    });
})();
