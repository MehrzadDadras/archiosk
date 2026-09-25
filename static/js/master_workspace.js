/* MASTERUI-PREVIEW: the one behaviour the Master Menu needs that
 * static/js/app_menu.js does not already give it - on a phone, the Menu
 * button opens the same 19 families as a fixed grid. Order and names are
 * the server's; this only shows or hides them. Self-guards on pages without
 * the Master shell. */
(function () {
    'use strict';
    var toggle = document.querySelector('.master-families-toggle');
    var families = document.getElementById('master-families');
    if (!toggle || !families) return;
    toggle.addEventListener('click', function () {
        var open = families.hasAttribute('data-open');
        if (open) families.removeAttribute('data-open'); else families.setAttribute('data-open', '');
        toggle.setAttribute('aria-expanded', String(!open));
    });
})();
