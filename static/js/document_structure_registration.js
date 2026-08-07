/*
 * CLAUDE-MM9 (Whole-System Integration): a real, click-driven UI trigger
 * for MM2 (PDF page/paragraph structure) and MM3 (spreadsheet worksheet/
 * row structure) registration - closing a genuine integration gap this
 * stage's own repository-grounded investigation found: MM2's `/pdf-
 * structure` and MM3's `/spreadsheet-structure` API routes existed,
 * were fully tested, and were reachable by direct API call - but had
 * ZERO template/JS reference anywhere in the running application. A
 * first-time user who added a PDF or .xlsx as a Project Source through
 * the real "Add Documents" form had no way to ever turn it into citable
 * page/paragraph or worksheet/row evidence - the entire MM2/MM3
 * evidence layer was invisible, even though it was real and governed
 * underneath. MM4's drawing_image_viewer.js already solved exactly this
 * problem for drawings (its own ensureSheetUnit()'s lazy "Register this
 * drawing" button, calling POST .../drawing-structure) - this module
 * applies the SAME lazy-registration pattern to PDF and spreadsheet
 * sources, reusing the existing, unmodified `/pdf-structure` and
 * `/spreadsheet-structure` routes exactly as they already are. No new
 * backend route, no new domain object - UI wiring only.
 *
 * Mounts on every `[data-document-structure-registration]` element
 * present at load (one per PDF/.xlsx Source detail pane) - a plain,
 * self-contained per-element widget, the same shape drawing_image_
 * viewer.js's own mount(el) already established, so this file behaves
 * consistently with the rest of this app's viewer-mounting convention.
 */
(function () {
    'use strict';

    function mount(container) {
        var projectId = container.getAttribute('data-project-id');
        var sourceId = container.getAttribute('data-source-id');
        var kind = container.getAttribute('data-structure-kind'); // "pdf" | "spreadsheet"
        var apiBase = '/api/v1/documents/' + encodeURIComponent(projectId);
        var registerPath = kind === 'spreadsheet' ? '/spreadsheet-structure' : '/pdf-structure';
        var unitTypes = kind === 'spreadsheet' ? ['worksheet'] : ['page'];
        var noun = kind === 'spreadsheet' ? 'workbook' : 'document';

        function render() {
            container.textContent = '';
            var status = document.createElement('span');
            status.className = 'pane-note';
            status.textContent = 'Checking whether this ' + noun + ' has been registered for citation…';
            container.appendChild(status);

            fetch(apiBase + '/structural-units?source_id=' + encodeURIComponent(sourceId), {
                credentials: 'same-origin',
            }).then(function (resp) { return resp.json(); }).then(function (body) {
                var units = (body && body.structural_units) || [];
                var matches = units.filter(function (u) { return unitTypes.indexOf(u.unit_type) !== -1; });
                if (matches.length) {
                    return fetch(apiBase + '/evidence?source_id=' + encodeURIComponent(sourceId), {
                        credentials: 'same-origin',
                    }).then(function (resp) { return resp.json(); }).then(function (evBody) {
                        var evidence = (evBody && evBody.evidence_items) || [];
                        container.textContent = '';
                        var summary = document.createElement('span');
                        summary.className = 'pane-note';
                        var unitNoun = kind === 'spreadsheet' ? 'worksheet' : 'page';
                        var evidenceNoun = kind === 'spreadsheet' ? 'citable row' : 'citable paragraph';
                        summary.textContent = 'Registered for citation: ' + matches.length + ' ' + unitNoun +
                            (matches.length === 1 ? '' : 's') + ', ' + evidence.length + ' ' + evidenceNoun +
                            (evidence.length === 1 ? '' : 's') + '. Individual ' + evidenceNoun +
                            's are reachable today through the diagnostic evidence API, not yet a full in-app browser.';
                        container.appendChild(summary);
                    });
                }
                container.textContent = '';
                var msg = document.createElement('span');
                msg.className = 'pane-note';
                msg.textContent = 'This ' + noun + ' is not registered for citation yet. ';
                container.appendChild(msg);
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'doc-control-btn';
                btn.textContent = kind === 'spreadsheet' ? 'Register this workbook' : 'Register this document';
                btn.addEventListener('click', function () {
                    btn.disabled = true;
                    btn.textContent = 'Registering…';
                    fetch(apiBase + '/sources/' + encodeURIComponent(sourceId) + registerPath, {
                        method: 'POST', credentials: 'same-origin',
                    }).then(function (resp) {
                        if (!resp.ok) { throw new Error('registration failed'); }
                        return render();
                    }).catch(function () {
                        btn.disabled = false;
                        btn.textContent = kind === 'spreadsheet' ? 'Register this workbook' : 'Register this document';
                        var err = document.createElement('span');
                        err.className = 'pane-note';
                        err.style.color = 'var(--failure-red, #c0392b)';
                        err.textContent = ' Could not register this ' + noun + '.';
                        container.appendChild(err);
                    });
                });
                container.appendChild(btn);
            }).catch(function () {
                container.textContent = '';
                var errStatus = document.createElement('span');
                errStatus.className = 'pane-note';
                errStatus.textContent = 'Could not check this ' + noun + '’s citation-registration status.';
                container.appendChild(errStatus);
            });
        }

        render();
    }

    document.addEventListener('DOMContentLoaded', function () {
        var containers = document.querySelectorAll('[data-document-structure-registration]');
        for (var i = 0; i < containers.length; i++) {
            mount(containers[i]);
        }
    });
})();
