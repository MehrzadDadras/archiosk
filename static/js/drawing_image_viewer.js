/*
 * CLAUDE-MM4 (Drawing Intelligence and Orientation-Normalized Comparison):
 * a real, interactive viewer for a standalone raster drawing Source
 * (.png/.jpg/.jpeg, Source.kind == "drawing") - replacing what was
 * previously a bare, uncontrolled <img> (templates/case_workspace.html's
 * own prior comment: "a drawing (<img>)... has no page/zoom/rotation
 * concept for this adapter to drive" - true of static/js/pdf_viewer.js,
 * which is genuinely PDF-only; this file is the drawing-specific
 * counterpart that comment always implied was still needed).
 *
 * Deliberately NOT a page-scoped singleton IIFE the way pdf_viewer.js is
 * (that file binds to ONE top-menu #workspace-document-controls region
 * shared by the whole page). This module instead exports a per-element
 * mount(imgEl) that builds its OWN self-contained toolbar/state next to
 * the image it is given - so the SAME script mounts independently on
 * BOTH the primary document pane (division 0) AND any comparison
 * Display division showing a second drawing (case_workspace.js's own
 * populateDivision, extended to call this mount() after inserting a
 * drawing <img> into ANY division) - two mounted instances never share
 * rotation/mirror/zoom/pan state, which is exactly what Section 8's own
 * "independently rotate or mirror EITHER drawing" comparison requires.
 * Both mounts live in the SAME top-level page/script context (a 'source'-
 * kind Display division is a direct DOM insertion, not an <iframe> -
 * confirmed by reading case_workspace.js's own populateDivision before
 * writing this), so no cross-frame plumbing is needed for that
 * independence - closured per-call state alone is sufficient.
 *
 * Orientation transform composition is MIRROR-then-ROTATE (CSS `rotate()
 * scaleX() scaleY()` on the same element composes exactly that way -
 * scale/mirror applies first, rotate second, reading right-to-left) -
 * the SAME order services/drawing_intelligence.py's own transform_point_
 * to_display/transform_point_to_original functions define as canonical.
 * toDisplayPoint/toOriginalPoint below are a direct, deliberately small
 * reimplementation of that exact Python math (not imported - there is no
 * shared runtime between Flask and the browser), verified independently
 * by tests/test_mm4_drawing_intelligence.py on the Python side and by
 * live-browser verification here (create a region while mirrored/
 * rotated, reset, confirm it redisplays over the same real drawing
 * content).
 */
(function () {
    'use strict';

    var MIN_ZOOM = 0.25;
    var MAX_ZOOM = 4;

    function normalizeRotation(r) {
        return ((Math.round(r / 90) * 90) % 360 + 360) % 360;
    }

    function mirrorPoint(x, y, mirrorH, mirrorV) {
        return [mirrorH ? 1 - x : x, mirrorV ? 1 - y : y];
    }

    function toDisplayPoint(x, y, rotation, mirrorH, mirrorV) {
        var m = mirrorPoint(x, y, mirrorH, mirrorV);
        var mx = m[0], my = m[1];
        rotation = normalizeRotation(rotation);
        if (rotation === 0) return [mx, my];
        if (rotation === 90) return [1 - my, mx];
        if (rotation === 180) return [1 - mx, 1 - my];
        return [my, 1 - mx]; // 270
    }

    function toOriginalPoint(dx, dy, rotation, mirrorH, mirrorV) {
        rotation = normalizeRotation(rotation);
        var mx, my;
        if (rotation === 0) { mx = dx; my = dy; }
        else if (rotation === 90) { mx = dy; my = 1 - dx; }
        else if (rotation === 180) { mx = 1 - dx; my = 1 - dy; }
        else { mx = 1 - dy; my = dx; } // 270
        return mirrorPoint(mx, my, mirrorH, mirrorV);
    }

    function describeTransform(rotation, mirrorH, mirrorV) {
        var parts = [];
        rotation = normalizeRotation(rotation);
        if (rotation) parts.push('Rotated ' + rotation + '° clockwise');
        if (mirrorH) parts.push('mirrored horizontally');
        if (mirrorV) parts.push('mirrored vertically');
        if (!parts.length) return '';
        var text = parts.join(' and ');
        return text.charAt(0).toUpperCase() + text.slice(1) + ' — source unchanged';
    }

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    function mount(imgEl) {
        if (!imgEl || imgEl.dataset.drawingViewerMounted === '1') return;
        imgEl.dataset.drawingViewerMounted = '1';

        var sourceId = imgEl.dataset.sourceId;
        var stripEl = document.getElementById('document-tab-strip');
        var projectId = (stripEl && stripEl.getAttribute('data-project-id')) || imgEl.dataset.projectId || '';
        if (!sourceId || !projectId) return;

        var apiBase = '/api/v1/documents/' + encodeURIComponent(projectId);

        // -------- Build the surrounding DOM ---------------------------
        var host = document.createElement('div');
        host.className = 'drawing-viewer';

        var toolbar = document.createElement('div');
        toolbar.className = 'drawing-viewer-toolbar';
        toolbar.setAttribute('role', 'toolbar');
        toolbar.setAttribute('aria-label', 'Drawing controls');

        function makeBtn(label, title) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'doc-control-btn';
            btn.textContent = label;
            btn.title = title;
            btn.setAttribute('aria-label', title);
            toolbar.appendChild(btn);
            return btn;
        }

        var zoomOutBtn = makeBtn('−', 'Zoom out');
        var zoomLevelEl = document.createElement('span');
        zoomLevelEl.className = 'doc-zoom-level';
        zoomLevelEl.setAttribute('aria-live', 'polite');
        toolbar.appendChild(zoomLevelEl);
        var zoomInBtn = makeBtn('+', 'Zoom in');
        var fitBtn = makeBtn('Fit', 'Fit to view');
        var divider1 = document.createElement('span');
        divider1.className = 'doc-controls-divider';
        toolbar.appendChild(divider1);
        var rotateBtn = makeBtn('↻', 'Rotate 90°');
        var mirrorHBtn = makeBtn('↔', 'Mirror horizontally');
        var mirrorVBtn = makeBtn('↕', 'Mirror vertically');
        var resetBtn = makeBtn('↴', 'Reset orientation');
        var orientationStatusEl = document.createElement('span');
        orientationStatusEl.className = 'doc-orientation-status';
        orientationStatusEl.setAttribute('aria-live', 'polite');
        toolbar.appendChild(orientationStatusEl);
        var divider2 = document.createElement('span');
        divider2.className = 'doc-controls-divider';
        toolbar.appendChild(divider2);
        var regionBtn = makeBtn('▢', 'Select a drawing region');
        regionBtn.classList.add('doc-annotation-tool');
        regionBtn.setAttribute('aria-pressed', 'false');
        // CLAUDE-MM5 Section 13: the one bounded annotation type this
        // stage implements - a point marker with a required short note,
        // sharing the SAME one-active-tool-at-a-time group as the region
        // tool (never both active together).
        var markerBtn = makeBtn('📍', 'Add a marker');
        markerBtn.classList.add('doc-annotation-tool');
        markerBtn.setAttribute('aria-pressed', 'false');
        var regionStatusEl = document.createElement('span');
        regionStatusEl.className = 'doc-region-status';
        regionStatusEl.setAttribute('aria-live', 'polite');
        toolbar.appendChild(regionStatusEl);

        // CLAUDE-MM4 Section 10/11: sheet title-block metadata + the
        // required scale-reliability warning - rendered from whatever
        // register_drawing_sheet_structure actually extracted, each field
        // shown with its own honest reliability tag (never silently
        // promoted to fact). A standalone raster image has no text layer
        // to mine (Section 15: OCR deferred), so this panel will
        // typically show every field as "unavailable" - itself an honest,
        // useful signal, not hidden.
        var metadataPanel = document.createElement('div');
        metadataPanel.className = 'drawing-sheet-metadata';
        metadataPanel.hidden = true;

        // CLAUDE-MM6 Section 19: the bounded "river relationship viewer" -
        // a small panel, NOT a free-form graph canvas, opened for the most
        // recently created region/marker's own EvidenceItem (the one real
        // object a reviewer has an on-screen reference to right now - this
        // codebase has no "reopen an existing region" affordance yet, the
        // same limitation MM4/MM5's own checkpoint notes already record).
        var riverPanel = document.createElement('div');
        riverPanel.className = 'relationship-river-panel';
        riverPanel.hidden = true;

        var viewport = document.createElement('div');
        viewport.className = 'drawing-viewport';

        var panZoom = document.createElement('div');
        panZoom.className = 'drawing-pan-zoom';

        var overlay = document.createElement('div');
        overlay.className = 'drawing-region-overlay';

        var parent = imgEl.parentNode;
        parent.insertBefore(host, imgEl);
        host.appendChild(toolbar);
        host.appendChild(viewport);
        host.appendChild(metadataPanel);
        host.appendChild(riverPanel);
        viewport.appendChild(panZoom);
        panZoom.appendChild(imgEl);
        panZoom.appendChild(overlay);

        // -------- State --------------------------------------------------
        var zoom = 1;
        var panX = 0, panY = 0;
        var rotation = 0;
        var mirrorH = false, mirrorV = false;
        var regionToolActive = false;
        var markerToolActive = false;
        var sheetUnit = null;
        var isPanning = false;
        var panStart = null;
        var dragRect = null; // {x1,y1,x2,y2} in raw client pixels

        function applyImageTransform() {
            var scaleX = mirrorH ? -1 : 1;
            var scaleY = mirrorV ? -1 : 1;
            imgEl.style.transform = 'rotate(' + rotation + 'deg) scale(' + scaleX + ',' + scaleY + ')';
        }

        function applyPanZoomTransform() {
            panZoom.style.transform = 'translate(' + panX + 'px,' + panY + 'px) scale(' + zoom + ')';
        }

        function updateZoomLabel() {
            zoomLevelEl.textContent = Math.round(zoom * 100) + '%';
        }

        function updateOrientationStatus() {
            orientationStatusEl.textContent = describeTransform(rotation, mirrorH, mirrorV);
        }

        function setZoom(z) {
            zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));
            applyPanZoomTransform();
            updateZoomLabel();
        }

        function fitToView() {
            panX = 0; panY = 0;
            setZoom(1);
        }

        function rotateStep() {
            rotation = normalizeRotation(rotation + 90);
            applyImageTransform();
            updateOrientationStatus();
        }

        function mirrorHorizontal() {
            mirrorH = !mirrorH;
            applyImageTransform();
            updateOrientationStatus();
        }

        function mirrorVertical() {
            mirrorV = !mirrorV;
            applyImageTransform();
            updateOrientationStatus();
        }

        function resetOrientation() {
            rotation = 0; mirrorH = false; mirrorV = false;
            applyImageTransform();
            updateOrientationStatus();
        }

        // -------- Sheet StructuralUnit lookup (Section 4/6) --------------
        function ensureSheetUnit() {
            if (sheetUnit) return Promise.resolve(sheetUnit);
            regionStatusEl.textContent = 'Looking up this drawing’s sheet…';
            return fetch(apiBase + '/structural-units?source_id=' + encodeURIComponent(sourceId), {
                credentials: 'same-origin',
            }).then(function (resp) { return resp.json(); }).then(function (body) {
                var units = (body && body.structural_units) || [];
                // CLAUDE-MM5: this viewer is shared by MM4 drawing sheets
                // (unit_type="sheet") AND MM5 images (unit_type="image",
                // already registered automatically at "Save to project"
                // time - services/image_intelligence.py's own register_
                // eye_capture) - either is a valid governing unit for
                // region/marker anchoring here, so both are accepted
                // rather than forcing a redundant second registration
                // click for an Eye-saved photo that is already registered.
                var match = units.filter(function (u) { return u.unit_type === 'sheet' || u.unit_type === 'image'; })[0];
                if (!match) {
                    regionStatusEl.textContent = '';
                    var msg = document.createElement('span');
                    msg.textContent = 'This drawing is not registered yet. ';
                    regionStatusEl.appendChild(msg);
                    var registerBtn = document.createElement('button');
                    registerBtn.type = 'button';
                    registerBtn.className = 'doc-control-btn';
                    registerBtn.textContent = 'Register this drawing';
                    registerBtn.addEventListener('click', function () {
                        registerBtn.disabled = true;
                        fetch(apiBase + '/sources/' + encodeURIComponent(sourceId) + '/drawing-structure', {
                            method: 'POST', credentials: 'same-origin',
                        }).then(function () { sheetUnit = null; return ensureSheetUnit(); });
                    });
                    regionStatusEl.appendChild(registerBtn);
                    return null;
                }
                sheetUnit = match;
                regionStatusEl.textContent = 'Drag a rectangle on the drawing to create a region.';
                renderSheetMetadata(match);
                return match;
            }).catch(function () {
                regionStatusEl.textContent = 'Could not look up this drawing’s sheet.';
                return null;
            });
        }

        var FIELD_LABELS = {
            sheet_number: 'Sheet number', drawing_title: 'Drawing title', discipline: 'Discipline',
            consultant: 'Consultant / designer', issue_date: 'Issue date', revision: 'Revision', scale: 'Scale',
            project_name: 'Project name', project_number: 'Project number', project_address: 'Project address',
            owner_client: 'Owner / client',
        };

        function renderSheetMetadata(unit) {
            metadataPanel.textContent = '';
            var fields = (unit.modality_metadata && unit.modality_metadata.fields) || {};
            var list = document.createElement('dl');
            list.className = 'drawing-sheet-metadata-list';
            Object.keys(FIELD_LABELS).forEach(function (key) {
                var info = fields[key];
                var dt = document.createElement('dt');
                dt.textContent = FIELD_LABELS[key];
                var dd = document.createElement('dd');
                if (info && info.value) {
                    dd.textContent = info.value + ' (' + info.reliability.replace('_', ' ') + ')';
                } else {
                    dd.textContent = 'unavailable';
                    dd.className = 'drawing-sheet-metadata-unavailable';
                }
                list.appendChild(dt);
                list.appendChild(dd);
            });
            metadataPanel.appendChild(list);
            var warning = document.createElement('p');
            warning.className = 'drawing-scale-warning';
            warning.textContent = 'Measurements are not reliable: scale is recorded as extracted text only, ' +
                'not calibrated against this image. Do not take dimensions from this view.';
            metadataPanel.appendChild(warning);
            metadataPanel.hidden = false;
        }

        // -------- CLAUDE-MM6: bounded river relationship viewer ----------
        // Section 19's own required capabilities: see related objects,
        // their modality/direction/state, open either endpoint's citation,
        // create one relationship, confirm/dispute/reject one, see stale/
        // broken status - all against the real /relationships and
        // /evidence/<id>/trust routes, never a client-side mock.
        var RELATIONSHIP_TYPES = [
            'supports', 'contradicts', 'observes', 'deviates_from', 'requires_follow_up',
            'references', 'same_subject_as', 'compares_with', 'validates', 'invalidates',
        ];
        var ENDPOINT_OBJECT_TYPES = [
            'evidence_item', 'addressable_region', 'structural_unit', 'derived_observation',
            'source', 'task', 'finding',
        ];

        function statusBadge(status) {
            var span = document.createElement('span');
            span.className = 'relationship-status-badge relationship-status-' + status;
            span.textContent = status;
            return span;
        }

        function renderTrustSummary(evidenceItemId, container) {
            container.textContent = '';
            fetch(apiBase + '/evidence/' + encodeURIComponent(evidenceItemId) + '/trust', { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (trust) {
                    if (trust.status !== 'assembled') return;
                    var p = document.createElement('p');
                    p.className = 'relationship-trust-summary';
                    p.textContent = 'Why trust this: ' + String(trust.basis || 'unknown').replace(/_/g, ' ') +
                        (trust.has_contradictions ? ' — has contradicting evidence, see below' : '');
                    container.appendChild(p);
                })
                .catch(function () { /* trust summary is supplementary - a failed fetch leaves it absent, not broken */ });
        }

        function loadRelationships(evidenceItemId, listEl) {
            listEl.textContent = 'Loading…';
            fetch(
                apiBase + '/relationships?object_type=evidence_item&object_id=' + encodeURIComponent(evidenceItemId) + '&direction=both',
                { credentials: 'same-origin' },
            ).then(function (r) { return r.json(); }).then(function (body) {
                var relationships = (body && body.relationships) || [];
                listEl.textContent = '';
                if (!relationships.length) {
                    var empty = document.createElement('p');
                    empty.className = 'relationship-river-empty';
                    empty.textContent = 'No relationships recorded yet.';
                    listEl.appendChild(empty);
                    return;
                }
                relationships.forEach(function (rel) {
                    var row = document.createElement('div');
                    row.className = 'relationship-river-row';
                    var isFrom = rel.from_type === 'evidence_item' && rel.from_id === evidenceItemId;
                    var otherType = isFrom ? rel.to_type : rel.from_type;
                    var otherId = isFrom ? rel.to_id : rel.from_id;

                    var head = document.createElement('div');
                    head.className = 'relationship-river-row-head';
                    var summary = document.createElement('span');
                    summary.textContent = (isFrom ? '→ ' : '← ') + rel.relationship_type + ' ' + otherType +
                        ' (' + String(otherId).slice(0, 8) + '…)';
                    head.appendChild(summary);
                    row.appendChild(head);

                    if (rel.reason) {
                        var reasonEl = document.createElement('p');
                        reasonEl.className = 'relationship-river-reason';
                        reasonEl.textContent = rel.reason;
                        row.appendChild(reasonEl);
                    }

                    fetch(apiBase + '/relationships/' + encodeURIComponent(rel.id) + '/status', { credentials: 'same-origin' })
                        .then(function (r) { return r.json(); })
                        .then(function (statusResult) { head.appendChild(statusBadge(statusResult.status)); });

                    var actions = document.createElement('div');
                    actions.className = 'relationship-river-row-actions';
                    function actionButton(label, verb) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'doc-control-btn';
                        btn.textContent = label;
                        btn.addEventListener('click', function () {
                            btn.disabled = true;
                            fetch(apiBase + '/relationships/' + encodeURIComponent(rel.id) + '/' + verb, {
                                method: 'POST', credentials: 'same-origin',
                                headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
                            }).then(function () { loadRelationships(evidenceItemId, listEl); });
                        });
                        actions.appendChild(btn);
                    }
                    actionButton('Confirm', 'confirm');
                    actionButton('Dispute', 'dispute');
                    actionButton('Reject', 'reject');
                    row.appendChild(actions);

                    listEl.appendChild(row);
                });
            }).catch(function () {
                listEl.textContent = '';
                var errorEl = document.createElement('p');
                errorEl.className = 'relationship-river-empty';
                errorEl.textContent = 'Could not load relationships.';
                listEl.appendChild(errorEl);
            });
        }

        function buildCreateRelationshipForm(evidenceItemId, listEl) {
            var form = document.createElement('div');
            form.className = 'relationship-river-create';

            var typeSelect = document.createElement('select');
            typeSelect.setAttribute('aria-label', 'Target object type');
            ENDPOINT_OBJECT_TYPES.forEach(function (t) {
                var opt = document.createElement('option');
                opt.value = t; opt.textContent = t;
                typeSelect.appendChild(opt);
            });

            var idInput = document.createElement('input');
            idInput.type = 'text';
            idInput.placeholder = 'Target object id';
            idInput.setAttribute('aria-label', 'Target object id');

            var relTypeSelect = document.createElement('select');
            relTypeSelect.setAttribute('aria-label', 'Relationship type');
            RELATIONSHIP_TYPES.forEach(function (t) {
                var opt = document.createElement('option');
                opt.value = t; opt.textContent = t;
                relTypeSelect.appendChild(opt);
            });

            var reasonInput = document.createElement('input');
            reasonInput.type = 'text';
            reasonInput.placeholder = 'Reason (optional)';
            reasonInput.setAttribute('aria-label', 'Reason');

            var createBtn = document.createElement('button');
            createBtn.type = 'button';
            createBtn.className = 'doc-control-btn';
            createBtn.textContent = 'Create relationship';

            var statusEl = document.createElement('span');
            statusEl.className = 'relationship-river-create-status';
            statusEl.setAttribute('aria-live', 'polite');

            createBtn.addEventListener('click', function () {
                var targetId = idInput.value.trim();
                if (!targetId) { statusEl.textContent = 'Target object id is required.'; return; }
                createBtn.disabled = true;
                statusEl.textContent = '';
                fetch(apiBase + '/relationships', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        from_type: 'evidence_item', from_id: evidenceItemId,
                        to_type: typeSelect.value, to_id: targetId,
                        relationship_type: relTypeSelect.value, reason: reasonInput.value.trim() || null,
                    }),
                }).then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
                    .then(function (result) {
                        createBtn.disabled = false;
                        if (!result.ok) {
                            statusEl.textContent = result.body.message || 'Could not create that relationship.';
                            return;
                        }
                        statusEl.textContent = 'Relationship created.';
                        idInput.value = ''; reasonInput.value = '';
                        loadRelationships(evidenceItemId, listEl);
                    });
            });

            form.appendChild(typeSelect);
            form.appendChild(idInput);
            form.appendChild(relTypeSelect);
            form.appendChild(reasonInput);
            form.appendChild(createBtn);
            form.appendChild(statusEl);
            return form;
        }

        function openRelationshipRiver(evidenceItemId) {
            riverPanel.textContent = '';
            riverPanel.hidden = false;
            riverPanel.dataset.evidenceId = evidenceItemId;

            var heading = document.createElement('h4');
            heading.textContent = 'Related evidence';
            riverPanel.appendChild(heading);

            var trustEl = document.createElement('div');
            riverPanel.appendChild(trustEl);
            renderTrustSummary(evidenceItemId, trustEl);

            var listEl = document.createElement('div');
            listEl.className = 'relationship-river-list';
            riverPanel.appendChild(listEl);
            loadRelationships(evidenceItemId, listEl);

            riverPanel.appendChild(buildCreateRelationshipForm(evidenceItemId, listEl));
        }

        function addRelationshipsButton(statusContainer, evidenceItemId) {
            if (!evidenceItemId) return;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'doc-control-btn';
            btn.textContent = 'Relationships';
            btn.addEventListener('click', function () {
                if (!riverPanel.hidden && riverPanel.dataset.evidenceId === evidenceItemId) {
                    riverPanel.hidden = true;
                    return;
                }
                openRelationshipRiver(evidenceItemId);
            });
            statusContainer.appendChild(btn);
        }

        // -------- Region selection (Section 4/6/12) ----------------------
        function clearOverlay() { overlay.textContent = ''; }

        function drawOverlayRect(clientRectLike) {
            clearOverlay();
            var vpRect = viewport.getBoundingClientRect();
            var box = document.createElement('div');
            box.className = 'drawing-region-box';
            box.style.left = (clientRectLike.left - vpRect.left) + 'px';
            box.style.top = (clientRectLike.top - vpRect.top) + 'px';
            box.style.width = clientRectLike.width + 'px';
            box.style.height = clientRectLike.height + 'px';
            overlay.appendChild(box);
        }

        function commitRegion(x1, y1, x2, y2) {
            var imgRect = imgEl.getBoundingClientRect();
            if (imgRect.width <= 0 || imgRect.height <= 0) return;
            var relX1 = (x1 - imgRect.left) / imgRect.width, relY1 = (y1 - imgRect.top) / imgRect.height;
            var relX2 = (x2 - imgRect.left) / imgRect.width, relY2 = (y2 - imgRect.top) / imgRect.height;
            var o1 = toOriginalPoint(relX1, relY1, rotation, mirrorH, mirrorV);
            var o2 = toOriginalPoint(relX2, relY2, rotation, mirrorH, mirrorV);
            var nx = Math.max(0, Math.min(o1[0], o2[0]));
            var ny = Math.max(0, Math.min(o1[1], o2[1]));
            var nw = Math.min(1 - nx, Math.abs(o2[0] - o1[0]));
            var nh = Math.min(1 - ny, Math.abs(o2[1] - o1[1]));
            if (nw <= 0 || nh <= 0 || !sheetUnit) return;

            regionStatusEl.textContent = 'Saving region…';
            fetch(apiBase + '/sources/' + encodeURIComponent(sourceId) + '/drawing-regions', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ structural_unit_id: sheetUnit.id, x: nx, y: ny, width: nw, height: nh }),
            }).then(function (resp) { return resp.json().then(function (body) { return { ok: resp.ok, body: body }; }); })
                .then(function (result) {
                    clearOverlay();
                    regionStatusEl.textContent = '';
                    if (!result.ok) {
                        regionStatusEl.textContent = 'Could not save that region: ' + (result.body.message || 'unknown error');
                        return;
                    }
                    var label = result.body.citation && result.body.citation.label;
                    var regionIdCreated = result.body.region && result.body.region.id;
                    var span = document.createElement('span');
                    span.textContent = label ? ('Region created: ' + label + ' ') : 'Region created. ';
                    regionStatusEl.appendChild(span);
                    if (label && navigator.clipboard) {
                        var copyBtn = document.createElement('button');
                        copyBtn.type = 'button';
                        copyBtn.className = 'doc-control-btn';
                        copyBtn.textContent = 'Copy citation';
                        copyBtn.addEventListener('click', function () { navigator.clipboard.writeText(label); });
                        regionStatusEl.appendChild(copyBtn);
                    }
                    // CLAUDE-MM5 Section 12: "optionally export a derivative
                    // crop" - a real cropped PNG registered as its own
                    // Source, EXIF-free by construction (see services/
                    // image_intelligence.py's own extract_bounded_crop).
                    if (regionIdCreated) {
                        var exportBtn = document.createElement('button');
                        exportBtn.type = 'button';
                        exportBtn.className = 'doc-control-btn';
                        exportBtn.textContent = 'Export crop';
                        exportBtn.addEventListener('click', function () {
                            exportBtn.disabled = true;
                            fetch(apiBase + '/sources/' + encodeURIComponent(sourceId) + '/derivative-crop', {
                                method: 'POST', credentials: 'same-origin',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ region_id: regionIdCreated }),
                            }).then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
                                .then(function (exportResult) {
                                    exportBtn.disabled = false;
                                    if (!exportResult.ok) {
                                        regionStatusEl.appendChild(document.createTextNode(
                                            ' Could not export: ' + (exportResult.body.message || 'unknown error')));
                                        return;
                                    }
                                    regionStatusEl.appendChild(document.createTextNode(
                                        ' Derivative crop saved (checksum ' + exportResult.body.derivative_checksum.slice(0, 12) + '…).'));
                                });
                        });
                        regionStatusEl.appendChild(exportBtn);
                    }
                    var evidenceItemId = result.body.evidence_item && result.body.evidence_item.id;
                    addRelationshipsButton(regionStatusEl, evidenceItemId);
                });
        }

        function commitMarker(clientX, clientY) {
            var imgRect = imgEl.getBoundingClientRect();
            if (imgRect.width <= 0 || imgRect.height <= 0 || !sheetUnit) return;
            var relX = (clientX - imgRect.left) / imgRect.width, relY = (clientY - imgRect.top) / imgRect.height;
            var o = toOriginalPoint(relX, relY, rotation, mirrorH, mirrorV);

            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'drawing-marker-note-input';
            var vpRect = viewport.getBoundingClientRect();
            input.style.left = (clientX - vpRect.left) + 'px';
            input.style.top = (clientY - vpRect.top) + 'px';
            input.placeholder = 'Marker note';
            input.setAttribute('aria-label', 'Marker note');
            overlay.appendChild(input);
            input.focus();

            function commit() {
                var note = input.value.trim();
                if (input.parentNode) input.parentNode.removeChild(input);
                if (!note) return;
                regionStatusEl.textContent = 'Saving marker…';
                fetch(apiBase + '/sources/' + encodeURIComponent(sourceId) + '/markers', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ structural_unit_id: sheetUnit.id, x: o[0], y: o[1], note: note }),
                }).then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
                    .then(function (result) {
                        regionStatusEl.textContent = '';
                        if (!result.ok) {
                            regionStatusEl.textContent = 'Could not save that marker: ' + (result.body.message || 'unknown error');
                            return;
                        }
                        var label = result.body.citation && result.body.citation.label;
                        var span = document.createElement('span');
                        span.textContent = label ? ('Marker created: ' + label) : 'Marker created.';
                        regionStatusEl.appendChild(span);
                        var evidenceItemId = result.body.evidence_item && result.body.evidence_item.id;
                        addRelationshipsButton(regionStatusEl, evidenceItemId);
                    });
            }
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); commit(); }
                else if (e.key === 'Escape') { e.preventDefault(); input.value = ''; commit(); }
            });
            input.addEventListener('blur', commit);
        }

        // -------- Pointer handling: pan by default, region-drag when the
        // -------- region tool is active (never both at once). ------------
        viewport.addEventListener('pointerdown', function (e) {
            if (markerToolActive) {
                if (!sheetUnit) { ensureSheetUnit(); return; }
                commitMarker(e.clientX, e.clientY);
            } else if (regionToolActive) {
                if (!sheetUnit) { ensureSheetUnit(); return; }
                dragRect = { x1: e.clientX, y1: e.clientY, x2: e.clientX, y2: e.clientY };
                try { viewport.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            } else {
                isPanning = true;
                panStart = { x: e.clientX - panX, y: e.clientY - panY };
                try { viewport.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            }
        });
        viewport.addEventListener('pointermove', function (e) {
            if (dragRect) {
                dragRect.x2 = e.clientX; dragRect.y2 = e.clientY;
                drawOverlayRect({
                    left: Math.min(dragRect.x1, dragRect.x2), top: Math.min(dragRect.y1, dragRect.y2),
                    width: Math.abs(dragRect.x2 - dragRect.x1), height: Math.abs(dragRect.y2 - dragRect.y1),
                });
            } else if (isPanning && panStart) {
                panX = e.clientX - panStart.x;
                panY = e.clientY - panStart.y;
                applyPanZoomTransform();
            }
        });
        viewport.addEventListener('pointerup', function () {
            if (dragRect) {
                var drag = dragRect;
                dragRect = null;
                if (Math.abs(drag.x2 - drag.x1) > 3 || Math.abs(drag.y2 - drag.y1) > 3) {
                    commitRegion(drag.x1, drag.y1, drag.x2, drag.y2);
                } else {
                    clearOverlay();
                }
            }
            isPanning = false;
            panStart = null;
        });
        viewport.addEventListener('wheel', function (e) {
            e.preventDefault();
            setZoom(zoom + (e.deltaY < 0 ? 0.1 : -0.1));
        }, { passive: false });

        // -------- Event wiring --------------------------------------------
        zoomOutBtn.addEventListener('click', function () { setZoom(zoom - 0.1); });
        zoomInBtn.addEventListener('click', function () { setZoom(zoom + 0.1); });
        fitBtn.addEventListener('click', fitToView);
        rotateBtn.addEventListener('click', rotateStep);
        mirrorHBtn.addEventListener('click', mirrorHorizontal);
        mirrorVBtn.addEventListener('click', mirrorVertical);
        resetBtn.addEventListener('click', resetOrientation);
        regionBtn.addEventListener('click', function () {
            regionToolActive = !regionToolActive;
            if (regionToolActive) markerToolActive = false;
            regionBtn.setAttribute('aria-pressed', String(regionToolActive));
            markerBtn.setAttribute('aria-pressed', 'false');
            viewport.style.cursor = (regionToolActive || markerToolActive) ? 'crosshair' : 'grab';
            if (regionToolActive) {
                ensureSheetUnit();
            } else {
                regionStatusEl.textContent = '';
                clearOverlay();
            }
        });
        markerBtn.addEventListener('click', function () {
            markerToolActive = !markerToolActive;
            if (markerToolActive) regionToolActive = false;
            markerBtn.setAttribute('aria-pressed', String(markerToolActive));
            regionBtn.setAttribute('aria-pressed', 'false');
            viewport.style.cursor = (regionToolActive || markerToolActive) ? 'crosshair' : 'grab';
            if (markerToolActive) {
                ensureSheetUnit();
            } else {
                regionStatusEl.textContent = '';
                clearOverlay();
            }
        });

        viewport.style.cursor = 'grab';
        updateZoomLabel();
        applyImageTransform();
        applyPanZoomTransform();
        // Section 10: sheet metadata is shown proactively, not only once
        // the reviewer opts into the region tool - regionStatusEl's own
        // "not registered yet" / register affordance doubles as this
        // panel's own empty state when no sheet exists yet.
        ensureSheetUnit();
    }

    window.ArchioskDrawingImageViewer = {
        mount: mount,
        // Exposed for live-browser/manual verification only - not used by
        // any Python code (no shared runtime between Flask and the
        // browser; services/drawing_intelligence.py's own equivalent
        // functions are the ones tests/test_mm4_drawing_intelligence.py
        // actually exercises).
        _toDisplayPoint: toDisplayPoint,
        _toOriginalPoint: toOriginalPoint,
    };

    // -------- Auto-mount: every drawing <img> already on the page ---------
    document.querySelectorAll('.document-viewer-image[data-source-id]').forEach(mount);
})();
