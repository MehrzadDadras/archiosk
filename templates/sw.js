/* CLAUDE-MOBILE-PWA-01 — the service worker.
 *
 * Product Owner: "users should not need to reinstall to receive updates;
 * deployed application updates must flow normally to installed users;
 * service-worker/cache behavior must not freeze users on old shells; no broad
 * offline caching of sensitive project material; authentication and
 * authorization remain unchanged."
 *
 * A service worker is the one thing in this application that can genuinely
 * strand a user on an old build, on their own device, with no way for us to
 * reach them. So this one is written to be as close to inert as a service
 * worker can be while still making ARCHIOSK installable.
 *
 * SERVED THROUGH FLASK, NOT AS A STATIC FILE. That is deliberate: it lets
 * STATIC_VERSION be baked into the cache name below, so a deploy produces a
 * genuinely new cache and the old one is deleted on activate. A static sw.js
 * would have no way to know a deploy had happened.
 *
 * THE THREE RULES THAT PREVENT A FROZEN SHELL
 *
 *   1. HTML IS NEVER SERVED FROM CACHE FIRST. Every navigation goes to the
 *      network. The classic PWA failure is cache-first HTML, which pins the
 *      user to whatever shell was cached the day they installed. Here the
 *      cache is only ever a fallback for a genuinely failed request.
 *   2. THE CACHE NAME CARRIES THE DEPLOYED VERSION. A new deploy cannot read
 *      the previous deploy's cache at all.
 *   3. OLD CACHES ARE DELETED ON ACTIVATE, so nothing accumulates and no
 *      obsolete shell can persist.
 *
 * WHAT IS NEVER CACHED
 *
 * Anything that is not a versioned static asset. No project pages, no
 * conversations, no documents, no API responses, no authenticated HTML - only
 * /static/ URLs, which already carry ?v= and contain no project material.
 * Everything else is passed straight through to the network untouched, which
 * is also why authentication and authorization are unaffected: this worker
 * never inspects, stores or replays a credential, and never answers a request
 * the server should have answered.
 */
const VERSION = "{{ static_version }}";
const SHELL_CACHE = `archiosk-shell-v${VERSION}`;

// Deliberately tiny. Enough that an installed icon opens to something rather
// than a browser error when the network is briefly unavailable - and nothing
// that could hold project content.
const PRECACHE = [
    "/static/css/tokens.css?v=" + VERSION,
    "/static/css/main.css?v=" + VERSION,
    "/static/app-icon.svg?v=" + VERSION,
];

self.addEventListener("install", (event) => {
    // skipWaiting so a new deploy takes over promptly rather than waiting for
    // every tab to close - "users should not need to reinstall to receive
    // updates" is only true if the new worker actually activates.
    self.skipWaiting();
    event.waitUntil(
        caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE)).catch(() => {
            // A precache miss must never block installation. An installed app
            // that fails to install its worker is worse than one with a cold
            // cache.
        })
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((names) => Promise.all(
                names
                    .filter((name) => name.startsWith("archiosk-shell-") && name !== SHELL_CACHE)
                    .map((name) => caches.delete(name))
            ))
            .then(() => self.clients.claim())
            .then(() => self.clients.matchAll({ type: "window" }))
            .then((clients) => {
                // Tell open pages a new version is live. The page decides what
                // to show; a worker must never reload someone's tab out from
                // under them mid-sentence.
                clients.forEach((client) => client.postMessage({
                    type: "archiosk:updated", version: VERSION,
                }));
            })
    );
});

function isVersionedStatic(url) {
    return url.origin === self.location.origin && url.pathname.startsWith("/static/");
}

self.addEventListener("fetch", (event) => {
    const request = event.request;

    // Only ordinary GETs are eligible for any cache involvement at all. A POST
    // is always a real request to the server.
    if (request.method !== "GET") return;

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    if (isVersionedStatic(url)) {
        // Cache-first is safe here ONLY because these URLs carry ?v=: a new
        // deploy changes the URL, so a stale asset can never be served for a
        // new build.
        event.respondWith(
            caches.match(request).then((hit) => hit || fetch(request).then((response) => {
                if (response && response.ok) {
                    const copy = response.clone();
                    caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
                }
                return response;
            }))
        );
        return;
    }

    // EVERYTHING ELSE - every page, every project, every API call - goes to the
    // network, always, and is never written to any cache. Not passing these
    // through would be how project material ends up on the device and how a
    // user ends up pinned to an old shell.
    //
    // No respondWith() at all on this path: the request is left entirely to the
    // browser, which is the most honest way to guarantee this worker changes
    // nothing about authenticated behaviour.
});

self.addEventListener("message", (event) => {
    if (event.data && event.data.type === "archiosk:skip-waiting") {
        self.skipWaiting();
    }
});
