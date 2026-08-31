/*
 * CLAUDE-CHUNKED-UPLOAD-01 - slice a large document and send it in pieces.
 *
 * PROGRESSIVE ENHANCEMENT, DELIBERATELY
 *
 * The Add Documents form works without this file. Small files keep posting the
 * ordinary way through workspace.add_document_source, exactly as before, and if
 * this script fails to load, is blocked, or throws, the browser submits the form
 * normally. Chunking is an upgrade applied only where the ordinary path would
 * actually fail - which is what keeps a routine 2 MB upload on the code path
 * that has been working all along instead of routing it through new machinery
 * for no benefit.
 *
 * WHY NO CLIENT-SIDE DIGEST
 *
 * crypto.subtle.digest has no streaming API: hashing a 400 MB file in the
 * browser means holding all 400 MB in memory, which is the exact problem
 * chunking exists to avoid. The server computes SHA-256 while streaming the
 * chunks to disk, so the digest covers precisely the bytes that landed. The
 * endpoint still accepts an optional `sha256` field for callers that can supply
 * one cheaply; this one honestly cannot, so it does not pretend to.
 */
(function () {
    'use strict';

    // Under Flask's MAX_CONTENT_LENGTH (25 MB) with room to spare, and large
    // enough that a 400 MB set is ~80 requests rather than thousands.
    var CHUNK_BYTES = 5 * 1024 * 1024;
    // Files at or below this go the ordinary single-request route untouched.
    var CHUNK_THRESHOLD_BYTES = 5 * 1024 * 1024;
    var MAX_RETRIES = 3;
    var RETRY_BASE_MS = 500;

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function jsonHeaders() {
        // Accept is what tells services.auth.wants_json_response() that a
        // script is asking, so an expired session comes back as 401 JSON
        // rather than a 302 to an HTML login page. X-CSRFToken alone already
        // satisfies that helper, but stating Accept makes the intent explicit
        // at the call site instead of relying on a side effect of CSRF.
        return {
            'X-CSRFToken': csrfToken(),
            'Accept': 'application/json'
        };
    }

    /* An expired session mid-upload is a routine timeout, not an error to
     * report as one. Without this the 401 would surface as "Upload failed:
     * HTTP 401" and the reviewer would be left on a page whose every control
     * is now dead, with no indication that signing in again is the fix. */
    function redirectIfSessionExpired(response, payload) {
        if (response.status !== 401) { return false; }
        var target = (payload && payload.redirect) ||
            ('/login?next=' + encodeURIComponent(window.location.pathname));
        window.location.href = target;
        return true;
    }

    function delay(ms) {
        return new Promise(function (resolve) { setTimeout(resolve, ms); });
    }

    function humanSize(bytes) {
        if (bytes < 1024) { return bytes + ' B'; }
        if (bytes < 1024 * 1024) { return (bytes / 1024).toFixed(0) + ' KB'; }
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function uploadId() {
        // 32 lowercase hex, matching the server's _UPLOAD_ID_RE exactly. Any
        // other shape is refused there, which is the point of validating it.
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID().replace(/-/g, '');
        }
        var out = '';
        for (var i = 0; i < 32; i += 1) {
            out += Math.floor(Math.random() * 16).toString(16);
        }
        return out;
    }

    function Status(form) {
        var node = document.createElement('p');
        node.className = 'mono pane-note';
        node.setAttribute('data-ui-ref', 'pdm.add-documents.progress');
        node.setAttribute('role', 'status');
        node.setAttribute('aria-live', 'polite');
        form.appendChild(node);
        this.node = node;
    }
    Status.prototype.say = function (text) { this.node.textContent = text; };

    /* One chunk, with bounded retry. Transient failures are the normal case on
     * a long upload - a retry that gives up after the first blip would make
     * chunking less reliable than the single request it replaced. */
    function sendChunk(url, body, index, total, status) {
        var attempt = 0;

        function tryOnce() {
            attempt += 1;
            return fetch(url, {
                method: 'POST',
                headers: jsonHeaders(),
                body: body,
                credentials: 'same-origin'
            }).then(function (response) {
                if (response.ok) { return response.json(); }
                // 4xx is a refusal - a malformed chunk, an unsupported format,
                // an expired session. Retrying cannot change the answer, and
                // retrying an authorization failure three times is worse than
                // reporting it once.
                if (response.status >= 400 && response.status < 500) {
                    return response.json().catch(function () { return {}; })
                        .then(function (payload) {
                            if (redirectIfSessionExpired(response, payload)) {
                                // Navigation is underway. Reject with a marker
                                // the retry loop will not swallow, so no chunk
                                // is re-sent into a session that is gone.
                                throw new Error('SESSION_EXPIRED');
                            }
                            var message = payload.message || ('Refused (HTTP ' + response.status + ')');
                            throw new Error(message);
                        });
                }
                throw new Error('HTTP ' + response.status);
            }).catch(function (error) {
                if (attempt > MAX_RETRIES || error.message === 'SESSION_EXPIRED' ||
                        /Refused|Unsupported|match|range|large|empty/i.test(error.message)) {
                    throw error;
                }
                status.say('Chunk ' + (index + 1) + '/' + total +
                           ' failed (' + error.message + ') - retry ' +
                           attempt + ' of ' + MAX_RETRIES + '...');
                return delay(RETRY_BASE_MS * attempt).then(tryOnce);
            });
        }
        return tryOnce();
    }

    function chunkedUpload(form, file, status) {
        var chunkUrl = form.getAttribute('data-chunk-url');
        var completeUrl = form.getAttribute('data-complete-url');
        var id = uploadId();
        var total = Math.max(1, Math.ceil(file.size / CHUNK_BYTES));
        var index = 0;

        function next() {
            if (index >= total) {
                status.say('Assembling & verifying digest...');
                var done = new FormData();
                done.append('upload_id', id);
                done.append('filename', file.name);
                done.append('total_chunks', String(total));
                return fetch(completeUrl, {
                    method: 'POST',
                    headers: jsonHeaders(),
                    body: done,
                    credentials: 'same-origin'
                }).then(function (response) {
                    return response.json().catch(function () { return {}; })
                        .then(function (payload) {
                            if (redirectIfSessionExpired(response, payload)) {
                                throw new Error('SESSION_EXPIRED');
                            }
                            if (!response.ok) {
                                throw new Error(payload.message || ('HTTP ' + response.status));
                            }
                            return payload;
                        });
                }).then(function (payload) {
                    status.say('Complete - ' + payload.name + ' (' +
                               humanSize(payload.size_bytes) + ', sha256 ' +
                               payload.sha256.slice(0, 12) + '...). Reloading...');
                    // Reload rather than patching the DOM: the flash message,
                    // the Source list and the archive list are all rendered
                    // server-side, and reproducing them here would be a second
                    // source of truth for what the page already knows.
                    window.location.assign(payload.redirect || window.location.href);
                });
            }

            var start = index * CHUNK_BYTES;
            var blob = file.slice(start, Math.min(start + CHUNK_BYTES, file.size));
            var body = new FormData();
            body.append('chunk', blob, file.name);
            body.append('upload_id', id);
            body.append('chunk_index', String(index));
            body.append('total_chunks', String(total));
            body.append('filename', file.name);

            var percent = Math.round((index / total) * 100);
            status.say('Uploading chunk ' + (index + 1) + '/' + total +
                       ' (' + percent + '%)');

            return sendChunk(chunkUrl, body, index, total, status).then(function () {
                index += 1;
                return next();
            });
        }

        return next();
    }

    function init() {
        var forms = document.querySelectorAll('form[data-chunk-url][data-complete-url]');
        Array.prototype.forEach.call(forms, function (form) {
            var input = form.querySelector('input[type="file"]');
            if (!input) { return; }

            form.addEventListener('submit', function (event) {
                var file = input.files && input.files[0];
                if (!file) { return; }                       // let the form complain
                if (file.size <= CHUNK_THRESHOLD_BYTES) { return; }  // ordinary path

                event.preventDefault();
                var submit = form.querySelector('button[type="submit"]');
                if (submit) { submit.disabled = true; }
                input.disabled = true;

                var status = new Status(form);
                status.say('Preparing ' + file.name + ' (' + humanSize(file.size) + ')...');

                chunkedUpload(form, file, status).catch(function (error) {
                    if (error.message === 'SESSION_EXPIRED') {
                        // redirectIfSessionExpired already navigated. Saying
                        // "upload failed" here would blame the upload for an
                        // expired session and flash it as the page unloads.
                        status.say('Your session expired. Redirecting to sign in...');
                        return;
                    }
                    // Re-enable so the reviewer can retry or pick another file;
                    // a dead form after a failed upload is its own defect.
                    status.say('Upload failed: ' + error.message +
                               '. Nothing was added. You can try again.');
                    if (submit) { submit.disabled = false; }
                    input.disabled = false;
                });
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
