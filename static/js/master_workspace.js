/* MASTERUI: the one behaviour the Master Menu needs that static/js/app_menu.js
 * does not already give it - on a phone, the Menu button opens the same 19
 * families as a fixed grid. Order and names are the server's; this only shows
 * or hides them. Like the classic phone drawer it replaced, it closes on
 * Escape and on a tap outside it, so opening it can never trap the page.
 * Self-guards on pages without the Master shell. */
(function () {
    'use strict';
    // VIEW > Work / Inspect Density: set ?density on the page's own URL and
    // reload - the same effect as the classic density control, with nothing
    // from the request echoed by the server.
    Array.prototype.forEach.call(document.querySelectorAll('[data-action^="set-density-"]'), function (item) {
        item.addEventListener('click', function () {
            var url = new URL(window.location.href);
            url.searchParams.set('density', item.getAttribute('data-action').replace('set-density-', ''));
            window.location.assign(url.toString());
        });
    });
    var toggle = document.querySelector('.master-families-toggle');
    var families = document.getElementById('master-families');
    if (!toggle || !families) return;
    function setOpen(open) {
        if (open) families.setAttribute('data-open', ''); else families.removeAttribute('data-open');
        toggle.setAttribute('aria-expanded', String(open));
    }
    toggle.addEventListener('click', function () {
        setOpen(!families.hasAttribute('data-open'));
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && families.hasAttribute('data-open')) setOpen(false);
    });
    document.addEventListener('click', function (event) {
        if (!families.hasAttribute('data-open')) return;
        var el = event.target;
        if (el === toggle || (el && el.closest && (el.closest('.master-families-toggle') || el.closest('#master-families')))) return;
        setOpen(false);
    });
})();
