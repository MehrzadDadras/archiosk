/*
 * CLAUDE-P40-VW7A-QA (Move Document Controls into the Top Application
 * Menu) - a thin adapter around vendored PDF.js (static/js/vendor/
 * pdfjs/, see that directory's own README for what was vendored and
 * why) driving a plain <canvas> directly, NOT PDF.js's own bundled
 * pdf_viewer.mjs UI - the whole point of this stage is that Archiosk's
 * OWN top-menu controls (templates/base.html's own
 * #workspace-document-controls) drive the rendering, not a second
 * toolbar. Every function below is called by a real button/input in
 * that region; nothing here is scaffolding for a control that doesn't
 * exist yet.
 *
 * Scope, stated honestly: PDF only. A drawing (<img>) or DOCX/TXT
 * (plain <iframe>) Source has no page/zoom/rotation concept for this
 * adapter to drive, and this stage does not build a renderer for
 * those formats - templates/case_workspace.html's own branch only
 * calls mount() for a Source whose stored file_path ends in .pdf.
 *
 * No client-side build step (tools/dependency_fit.py's own
 * no-client-build check) - vendored PDF.js ships as plain ES modules,
 * loaded here via a dynamic import() from this ordinary (non-module)
 * script, same as every other static/js/*.js file in this app.
 *
 * CLAUDE-P40-VW7A-QA2 additions (Complete the PDF Viewer Controls,
 * Thumbnails and Collapsible Panel Geometry): lazy per-page thumbnail
 * rendering into templates/base.html's own #thumbnails-list, and a
 * real, client-side-only PDF annotation overlay (text/highlight/ink,
 * select+delete, undo/redo) - see each section's own comment below for
 * the reasoning, including the disclosed no-Save/Export scope boundary.
 *
 * CLAUDE-P40-LTH1 addition (Persistent Left Lists and Page-Thumbnails
 * Split): the Page Thumbnails pane is now a permanent structural
 * surface (templates/base.html's own comment on .lists-pane) rather
 * than something this file showed/hid via a cross-script API - see
 * "Remembered Document context" below for the one genuinely new piece
 * of behavior, a client-side-only memory of the last-viewed PDF Source
 * per Project+reviewer, used ONLY to populate thumbnails on a page
 * with no Document of its own selected (an Investigation, Chat, or
 * Overview) - never a new backend endpoint, never a database change.
 *
 * CLAUDE-DUAL-DOCUMENT-FOCUS-01 (this stage's own restructuring): the
 * entire single-document engine above is now a reusable factory,
 * createPdfSurface(name, ...), so Main Display and Eye can each hold a
 * genuinely independent PDF instance (own pdfDoc/canvas/page/zoom/
 * rotation/thumbnails) at the same time. There is still exactly ONE
 * physical top toolbar (#workspace-document-controls - "do not
 * duplicate two permanent full toolbars" is the Product Owner's own
 * explicit constraint) - its buttons now dispatch to whichever surface
 * currently has FOCUS (window.__activeDocumentSurface, 'main' or
 * 'eye', set by clicking/mousedown-ing inside Display vs Eye), and its
 * own displayed fields (page/zoom/search/etc) are re-synced from that
 * surface's own state every time focus changes. Annotation and drawing-
 * region tools stay bound to Main only, disabled outright while Eye is
 * focused, rather than fabricating region/structural-unit support for
 * a comparison surface that has none - Eye's own genuinely-supported
 * controls (page nav, zoom, fit, rotate, mirror, search, download,
 * print) are the ones that follow focus; this is a disclosed, narrower
 * scope than a literal reading of "markup... operate on Eye only"
 * would suggest, chosen because building real persisted-region support
 * for a second, non-canonical surface is a materially larger, separate
 * change this stage does not make silently.
 */
(function () {
    'use strict';

    var container = document.getElementById('workspace-document-controls');

    var prevBtn = document.getElementById('doc-prev-page');
    var nextBtn = document.getElementById('doc-next-page');
    var pageInput = document.getElementById('doc-page-input');
    var pageTotal = document.getElementById('doc-page-total');
    var zoomOutBtn = document.getElementById('doc-zoom-out');
    var zoomInBtn = document.getElementById('doc-zoom-in');
    var zoomLevel = document.getElementById('doc-zoom-level');
    var fitWidthBtn = document.getElementById('doc-fit-width');
    var fitPageBtn = document.getElementById('doc-fit-page');
    var rotateBtn = document.getElementById('doc-rotate');
    var searchInput = document.getElementById('doc-search-input');
    var searchPrevBtn = document.getElementById('doc-search-prev');
    var searchNextBtn = document.getElementById('doc-search-next');
    var searchCount = document.getElementById('doc-search-count');
    var downloadLink = document.getElementById('doc-download');
    var printBtn = document.getElementById('doc-print');
    var snapshotBtn = document.getElementById('doc-snapshot');
    var snapshotStatusEl = document.getElementById('doc-snapshot-status');
    var overflowDetails = document.getElementById('doc-controls-overflow');
    var overflowPanel = document.getElementById('doc-controls-overflow-panel');
    var secondaryGroup = document.getElementById('doc-controls-secondary');
    // CLAUDE-MM4: orientation (mirror/reset) and drawing-region controls -
    // additive to VW7A-QA2's own rotate/annotate controls, absent (null)
    // on any page whose markup predates this stage without breaking
    // anything below (every use is null-guarded the same way the
    // existing optional annotation buttons already are).
    var mirrorHBtn = document.getElementById('doc-mirror-h');
    var mirrorVBtn = document.getElementById('doc-mirror-v');
    var resetOrientationBtn = document.getElementById('doc-reset-orientation');
    var orientationStatusEl = document.getElementById('doc-orientation-status');
    var regionStatusEl = document.getElementById('doc-region-status');
    // CLAUDE-CANVAS-STEP1-01: the container lookup above and these six
    // controls used to be two hard gates that returned out of the WHOLE
    // module, so a chrome-less render produced no viewer and - more
    // importantly - no window.ArchioskPdfViewer for anything else to drive.
    // The engine never needed them: no chrome element appears in the render
    // pipeline, the viewport lifecycle or the geometry math (the canvas
    // arrives as a mount() parameter). Their absence therefore means "this
    // page has no shared toolbar", not "there is no viewer". Every chrome
    // write below goes through ownsToolbar(), and the toolbar wiring binds
    // only when the control actually exists - this file's own existing
    // `if (btn) btn.addEventListener(...)` idiom for optional controls,
    // extended to the six that used to be mandatory.
    var hasChrome = !!(container && prevBtn && nextBtn && pageInput && zoomOutBtn && zoomInBtn && searchInput);

    // -------- Responsive: move secondary controls into the overflow --
    // -------- panel below 900px (this file's own matchMedia listener, -
    // -------- matching the 900px breakpoint already used elsewhere in -
    // -------- static/css/main.css) - moves the SAME DOM node (real
    // -------- re-parenting via appendChild/insertBefore), never a
    // -------- cloned duplicate, so every control keeps exactly one
    // -------- physical identity regardless of viewport width. --------
    var secondaryHomeParent = secondaryGroup ? secondaryGroup.parentNode : null;
    var secondaryHomeNextSibling = secondaryGroup ? secondaryGroup.nextSibling : null;
    var narrowQuery = window.matchMedia('(max-width: 900px)');
    function applyResponsiveState(isNarrow) {
        if (!secondaryGroup || !overflowPanel || !overflowDetails) return;
        if (isNarrow) {
            overflowPanel.appendChild(secondaryGroup);
            overflowDetails.classList.add('doc-controls-overflow-active');
        } else {
            overflowDetails.classList.remove('doc-controls-overflow-active');
            overflowDetails.open = false;
            if (secondaryHomeParent) {
                secondaryHomeParent.insertBefore(secondaryGroup, secondaryHomeNextSibling);
            }
        }
    }
    applyResponsiveState(narrowQuery.matches);
    if (narrowQuery.addEventListener) {
        narrowQuery.addEventListener('change', function (e) { applyResponsiveState(e.matches); });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overflowDetails && overflowDetails.open) overflowDetails.open = false;
    });
    document.addEventListener('mousedown', function (e) {
        if (overflowDetails && overflowDetails.open && !overflowDetails.contains(e.target)) overflowDetails.open = false;
    });

    // -------- PDF.js module load (shared - one real fetch/import, both
    // -------- surfaces reuse the same cached module reference). -------
    var pdfjsLib = null;
    function loadPdfJs() {
        if (pdfjsLib) return Promise.resolve(pdfjsLib);
        return import('/static/js/vendor/pdfjs/pdf.min.mjs').then(function (mod) {
            pdfjsLib = mod;
            pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/js/vendor/pdfjs/pdf.worker.min.mjs';
            return pdfjsLib;
        });
    }

    // -------- Per-tab viewer state persistence (CLAUDE-P40-DTAB1,
    // Section 6) - shared helpers (no per-surface state of their own -
    // keyed by username+Project+source id, same as before this stage). ---
    function viewStateKey(sourceId) {
        var usernameEl = document.querySelector('.workspace-user-name');
        var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
        var stripEl = document.getElementById('document-tab-strip');
        var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
        return 'beehive:docview:' + username + ':' + projectId + ':' + sourceId;
    }

    function loadViewState(sourceId) {
        if (!sourceId) return null;
        try {
            var raw = window.localStorage.getItem(viewStateKey(sourceId));
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    // -------- Remembered Document context (CLAUDE-P40-LTH1, Section 3) --
    // Main-surface-only concept (see mountRememberedThumbnailsIfAny inside
    // the factory below, invoked only for the 'main' instance) - shared
    // helpers here, no per-surface state of their own.
    function lastPdfSourceKey() {
        var usernameEl = document.querySelector('.workspace-user-name');
        var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
        var stripEl = document.getElementById('document-tab-strip');
        var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
        return 'beehive:panel:last-pdf-source:' + username + ':' + projectId;
    }

    function rememberLastPdfSource(sourceId) {
        if (!sourceId) return;
        try { window.localStorage.setItem(lastPdfSourceKey(), sourceId); } catch (e) { /* ignore */ }
    }

    // The SAME authorized, Project-scoped JSON island every other
    // client-side feature in this shell already trusts (document_tabs.js,
    // case_workspace.js's populateDivision) - never a second, separately-
    // trusted source of truth about which Sources exist, are removed, or
    // belong to this Project.
    function activeSourcesFromJson() {
        var el = document.getElementById('workspace-active-sources-data');
        if (!el) return [];
        try {
            var parsed = JSON.parse(el.textContent);
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function apiDocumentsBase() {
        var stripEl = document.getElementById('document-tab-strip');
        var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
        return '/api/v1/documents/' + encodeURIComponent(projectId || '');
    }

    function showLoadError(canvasContainer, err) {
        canvasContainer.textContent = '';
        var msg = document.createElement('p');
        msg.className = 'document-viewer-load-error';
        msg.textContent = 'This PDF could not be opened in the viewer' + (err && err.message ? ': ' + err.message : '.');
        canvasContainer.appendChild(msg);
        if (window.console) console.error('PDF viewer failed to load', err);
    }

    // -------- CLAUDE-DUAL-DOCUMENT-FOCUS-01: focus/toolbar-ownership ----
    // window.__activeDocumentSurface ('main' | 'eye') decides which
    // surface's own state the ONE physical toolbar currently reads/
    // writes. Global (not module-local) because eye_pane.js's own Pop
    // Out / detached-window work (same lineage) also needs to read it.
    if (!window.__activeDocumentSurface) window.__activeDocumentSurface = 'main';
    var surfaces = {};

    var annotationToolButtons = [];
    ['doc-annotate-text', 'doc-annotate-highlight', 'doc-annotate-ink', 'doc-annotate-select', 'doc-region-select'].forEach(function (id) {
        var btn = document.getElementById(id);
        if (btn) annotationToolButtons.push(btn);
    });
    var deleteBtn = document.getElementById('doc-annotate-delete');
    var undoBtn = document.getElementById('doc-annotate-undo');
    var redoBtn = document.getElementById('doc-annotate-redo');
    var annotationStatusEl = document.getElementById('doc-annotation-status');

    function getFocused() { return surfaces[window.__activeDocumentSurface]; }

    // Annotation/region tools remain Main-only (see header comment) -
    // disabled outright, not merely inert, while Eye owns the toolbar,
    // so there is never a control that looks live but silently does
    // nothing (this app's own "no dead controls" discipline).
    function applyFocusIndication() {
        var isMain = window.__activeDocumentSurface === 'main';
        var displayEl = document.getElementById('workspace-display-panel');
        var eyePaneEl = document.getElementById('eye-pane');
        if (displayEl) displayEl.classList.toggle('surface-focused', isMain);
        if (eyePaneEl) eyePaneEl.classList.toggle('surface-focused', !isMain);
        annotationToolButtons.forEach(function (btn) { btn.disabled = !isMain; });
        if (deleteBtn) deleteBtn.disabled = !isMain;
        if (undoBtn) undoBtn.disabled = !isMain;
        if (redoBtn) redoBtn.disabled = !isMain;
        if (!isMain && regionStatusEl) regionStatusEl.textContent = '';
    }

    function setFocus(name) {
        if (!surfaces[name] || window.__activeDocumentSurface === name) return;
        window.__activeDocumentSurface = name;
        applyFocusIndication();
        surfaces[name].refreshToolbar();
    }
    applyFocusIndication();

    var displayFocusEl = document.getElementById('workspace-display-panel');
    if (displayFocusEl) displayFocusEl.addEventListener('mousedown', function () { setFocus('main'); });
    var eyeFocusEl = document.getElementById('eye-pane');
    if (eyeFocusEl) eyeFocusEl.addEventListener('mousedown', function () { setFocus('eye'); });

    // ---------------------------------------------------------------------
    // -------- The surface factory -----------------------------------------
    // One call per independent PDF instance (Main; Eye, from eye_pane.js
    // via window.ArchioskPdfViewer.createSurface). Everything below this
    // point used to be flat module state - it is unchanged LOGIC, just
    // closure-scoped per instance instead of shared, plus the focus-gating
    // noted inline where a function writes to the ONE shared toolbar.
    // ---------------------------------------------------------------------
    function createPdfSurface(name, thumbnailsList, thumbnailsEmptyState) {
        var pdfDoc = null;
        var canvas = null;
        var currentPage = 1;
        var currentZoom = 1.0;
        var currentRotation = 0;
        var mirrorH = false;
        var mirrorV = false;
        var renderTask = null;
        var pageTextCache = {};
        var searchMatches = [];
        var searchMatchIndex = -1;
        var searchDebounce = null;
        var overlayCanvas = null;
        var pageWrap = null;
        var currentViewport = null;
        var currentSourceId = null;
        var currentCanvasContainer = null;
        var currentUrl = null;
        var currentDownloadFilename = null;
        // CLAUDE-CANVAS-STEP1-01: the search query is SURFACE state, not DOM
        // state. It used to be read back out of #doc-search-input at save
        // time, which meant an unfocused surface persisted '' and silently
        // blanked its own remembered query on the pagehide flush.
        var currentSearchQuery = '';
        var drawingCapabilityPanel = null;
        var drawingCapabilityEvidenceId = null;
        var viewStateSaveTimer = null;
        var thumbnailsOnlyMode = false;
        var thumbnailRows = [];
        var thumbnailObserver = null;
        var THUMBNAIL_WIDTH = 140;
        var currentSheetUnit = null;
        var annotationsByPage = {};
        var annotationIdCounter = 1;
        var undoStack = [];
        var redoStack = [];
        var activeTool = null;
        var selectedAnnotation = null;
        var inkDrawing = null;
        var highlightDrag = null;
        var activeTextBox = null;
        var regionDrag = null;

        function hasSheetEvidence(units) {
            return Array.isArray(units) && units.some(function (unit) {
                return unit && unit.unit_type === 'sheet';
            });
        }

        var DRAWING_RELATIONSHIP_TYPES = [
            'supports', 'contradicts', 'observes', 'deviates_from', 'requires_follow_up',
            'references', 'same_subject_as', 'compares_with', 'validates', 'invalidates',
        ];
        var DRAWING_ENDPOINT_TYPES = [
            'evidence_item', 'addressable_region', 'structural_unit', 'derived_observation',
            'source', 'task', 'finding',
        ];

        function drawingStatusBadge(status) {
            var badge = document.createElement('span');
            badge.className = 'relationship-status-badge relationship-status-' + status;
            badge.textContent = status;
            return badge;
        }

        function loadPdfRelationships(evidenceId, listEl) {
            listEl.textContent = 'Loading relationships…';
            fetch(apiDocumentsBase() + '/relationships?object_type=evidence_item&object_id=' + encodeURIComponent(evidenceId) + '&direction=both', { credentials: 'same-origin' })
                .then(function (response) { return response.json(); })
                .then(function (body) {
                    listEl.textContent = '';
                    var relationships = (body && body.relationships) || [];
                    if (!relationships.length) { listEl.textContent = 'No relationships recorded yet.'; return; }
                    relationships.forEach(function (rel) {
                        var row = document.createElement('div');
                        row.className = 'relationship-river-row';
                        var from = rel.from_type === 'evidence_item' && rel.from_id === evidenceId;
                        var otherType = from ? rel.to_type : rel.from_type;
                        var otherId = from ? rel.to_id : rel.from_id;
                        var head = document.createElement('div');
                        head.className = 'relationship-river-row-head';
                        head.textContent = (from ? '→ ' : '← ') + rel.relationship_type + ' ' + otherType + ' (' + String(otherId).slice(0, 8) + '…) ';
                        row.appendChild(head);
                        fetch(apiDocumentsBase() + '/relationships/' + encodeURIComponent(rel.id) + '/status', { credentials: 'same-origin' })
                            .then(function (response) { return response.json(); })
                            .then(function (status) { head.appendChild(drawingStatusBadge(status.status)); });
                        if (rel.reason) { var reason = document.createElement('p'); reason.textContent = rel.reason; row.appendChild(reason); }
                        var actions = document.createElement('div');
                        ['confirm', 'dispute', 'reject'].forEach(function (verb) {
                            var action = document.createElement('button'); action.type = 'button'; action.className = 'doc-control-btn';
                            action.textContent = verb.charAt(0).toUpperCase() + verb.slice(1);
                            action.addEventListener('click', function () {
                                action.disabled = true;
                                fetch(apiDocumentsBase() + '/relationships/' + encodeURIComponent(rel.id) + '/' + verb, {
                                    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
                                }).then(function () { loadPdfRelationships(evidenceId, listEl); });
                            });
                            actions.appendChild(action);
                        });
                        row.appendChild(actions); listEl.appendChild(row);
                    });
                })
                .catch(function () { listEl.textContent = 'Could not load relationships.'; });
        }

        function buildPdfRelationshipForm(evidenceId, listEl) {
            var form = document.createElement('div'); form.className = 'relationship-river-create';
            var targetType = document.createElement('select'); targetType.setAttribute('aria-label', 'Target object type');
            DRAWING_ENDPOINT_TYPES.forEach(function (type) { var option = document.createElement('option'); option.value = type; option.textContent = type; targetType.appendChild(option); });
            var targetId = document.createElement('input'); targetId.type = 'text'; targetId.placeholder = 'Target object id'; targetId.setAttribute('aria-label', 'Target object id');
            var relationshipType = document.createElement('select'); relationshipType.setAttribute('aria-label', 'Relationship type');
            DRAWING_RELATIONSHIP_TYPES.forEach(function (type) { var option = document.createElement('option'); option.value = type; option.textContent = type; relationshipType.appendChild(option); });
            var reason = document.createElement('input'); reason.type = 'text'; reason.placeholder = 'Reason (optional)'; reason.setAttribute('aria-label', 'Relationship reason');
            var create = document.createElement('button'); create.type = 'button'; create.className = 'doc-control-btn'; create.textContent = 'Create relationship';
            var status = document.createElement('span'); status.setAttribute('aria-live', 'polite');
            create.addEventListener('click', function () {
                if (!targetId.value.trim()) { status.textContent = 'Target object id is required.'; return; }
                create.disabled = true;
                fetch(apiDocumentsBase() + '/relationships', {
                    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ from_type: 'evidence_item', from_id: evidenceId, to_type: targetType.value, to_id: targetId.value.trim(), relationship_type: relationshipType.value, reason: reason.value.trim() || null }),
                }).then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
                    .then(function (result) { create.disabled = false; status.textContent = result.ok ? 'Relationship created.' : (result.body.message || 'Could not create that relationship.'); if (result.ok) { targetId.value = ''; reason.value = ''; loadPdfRelationships(evidenceId, listEl); } });
            });
            [targetType, targetId, relationshipType, reason, create, status].forEach(function (element) { form.appendChild(element); });
            return form;
        }

        function buildPdfInvestigationForm(evidenceId, resultEl) {
            var form = document.createElement('div'); form.className = 'relationship-river-create';
            var caseId = document.createElement('input'); caseId.type = 'text'; caseId.placeholder = 'Case id'; caseId.setAttribute('aria-label', 'Case id');
            var question = document.createElement('input'); question.type = 'text'; question.placeholder = 'Investigation question'; question.setAttribute('aria-label', 'Investigation question');
            var run = document.createElement('button'); run.type = 'button'; run.className = 'doc-control-btn'; run.textContent = 'Investigate';
            var status = document.createElement('span'); status.setAttribute('aria-live', 'polite');
            run.addEventListener('click', function () {
                if (!caseId.value.trim() || !question.value.trim()) { status.textContent = 'Case id and a question are both required.'; return; }
                run.disabled = true; status.textContent = 'Investigating…';
                fetch(apiDocumentsBase() + '/investigations', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: question.value.trim(), case_id: caseId.value.trim(), anchor_object_type: 'evidence_item', anchor_object_id: evidenceId }) })
                    .then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
                    .then(function (result) {
                        run.disabled = false;
                        if (!result.ok) { status.textContent = result.body.message || 'Could not run that investigation.'; return; }
                        status.textContent = '';
                        fetch(apiDocumentsBase() + '/investigations/' + encodeURIComponent(result.body.investigation_step.id) + '/answer', { credentials: 'same-origin' })
                            .then(function (response) { return response.json(); }).then(function (answer) { resultEl.textContent = answer.status === 'assembled' ? ('Question: ' + answer.question + ((answer.claims || []).length ? ' Claims: ' + answer.claims.length : '')) : 'Investigation not available.'; });
                    });
            });
            [caseId, question, run, status].forEach(function (element) { form.appendChild(element); });
            return form;
        }

        function renderDrawingCapability(units) {
            if (name !== 'main' || !currentCanvasContainer) return;
            var available = hasSheetEvidence(units);
            if (!available) {
                if (drawingCapabilityPanel && drawingCapabilityPanel.parentNode) drawingCapabilityPanel.parentNode.removeChild(drawingCapabilityPanel);
                drawingCapabilityPanel = null; drawingCapabilityEvidenceId = null; return;
            }
            if (!drawingCapabilityPanel) { drawingCapabilityPanel = document.createElement('section'); drawingCapabilityPanel.className = 'pdf-drawing-capabilities'; drawingCapabilityPanel.setAttribute('aria-label', 'Drawing capabilities'); currentCanvasContainer.appendChild(drawingCapabilityPanel); }
            drawingCapabilityPanel.textContent = '';
            var heading = document.createElement('h4'); heading.textContent = 'Drawing capabilities'; drawingCapabilityPanel.appendChild(heading);
            var note = document.createElement('p'); note.textContent = drawingCapabilityEvidenceId ? 'Governed sheet evidence is available for Relationships and Investigation.' : 'Governed sheet structure is registered. Create a region to unlock evidence-linked capabilities.'; drawingCapabilityPanel.appendChild(note);
            if (!drawingCapabilityEvidenceId) return;
            var relationships = document.createElement('div'); relationships.className = 'pdf-drawing-relationships';
            var relHeading = document.createElement('h5'); relHeading.textContent = 'Relationships'; relationships.appendChild(relHeading);
            var relList = document.createElement('div'); relationships.appendChild(relList); relationships.appendChild(buildPdfRelationshipForm(drawingCapabilityEvidenceId, relList));
            var refresh = document.createElement('button'); refresh.type = 'button'; refresh.className = 'doc-control-btn'; refresh.textContent = 'Refresh relationships'; refresh.addEventListener('click', function () { loadPdfRelationships(drawingCapabilityEvidenceId, relList); }); relationships.appendChild(refresh); drawingCapabilityPanel.appendChild(relationships); loadPdfRelationships(drawingCapabilityEvidenceId, relList);
            var investigation = document.createElement('div'); investigation.className = 'pdf-drawing-investigation'; var invHeading = document.createElement('h5'); invHeading.textContent = 'Investigation'; investigation.appendChild(invHeading); var invResult = document.createElement('div'); investigation.appendChild(buildPdfInvestigationForm(drawingCapabilityEvidenceId, invResult)); investigation.appendChild(invResult); drawingCapabilityPanel.appendChild(investigation);
        }

        function isFocused() { return window.__activeDocumentSurface === name; }

        // A chrome write requires BOTH that this surface owns the one shared
        // toolbar AND that the toolbar physically exists on this page.
        function ownsToolbar() { return hasChrome && isFocused(); }

        // -------- Adapter contract (CLAUDE-CANVAS-STEP1-01) --------------
        // The surface owns its state and publishes it; a consumer renders
        // it. The shared toolbar is now just one such consumer, and a
        // canvas-native or headless consumer needs no #doc-* element at all.
        var stateListeners = [];

        function snapshot() {
            return {
                surface: name,
                hasDoc: !!pdfDoc,
                page: currentPage,
                pageCount: pdfDoc ? pdfDoc.numPages : 0,
                canPrev: !!pdfDoc && currentPage > 1,
                canNext: !!pdfDoc && currentPage < pdfDoc.numPages,
                zoom: currentZoom,
                rotation: currentRotation,
                mirrorH: mirrorH,
                mirrorV: mirrorV,
                searchQuery: currentSearchQuery,
                matchIndex: searchMatchIndex,
                matchCount: searchMatches.length,
                sourceId: currentSourceId,
                downloadUrl: currentUrl,
                downloadFilename: currentDownloadFilename
            };
        }

        function subscribe(listener) {
            if (typeof listener !== 'function') return function () {};
            stateListeners.push(listener);
            // Replay current state immediately so a consumer that subscribes
            // after mount() is not blank until the next change.
            try { listener('subscribe', snapshot()); } catch (e) { /* see emit */ }
            return function unsubscribe() {
                var i = stateListeners.indexOf(listener);
                if (i !== -1) stateListeners.splice(i, 1);
            };
        }

        function emit(event, data) {
            if (!stateListeners.length) return;
            var payload = data || snapshot();
            // A consumer must never be able to break the viewer.
            for (var i = 0; i < stateListeners.length; i++) {
                try { stateListeners[i](event, payload); } catch (e) { /* ignore */ }
            }
        }

        function saveViewStateNow() {
            if (!currentSourceId) return;
            var state = {
                page: currentPage,
                zoom: currentZoom,
                rotation: currentRotation,
                mirrorH: mirrorH,
                mirrorV: mirrorV,
                scrollLeft: currentCanvasContainer ? currentCanvasContainer.scrollLeft : 0,
                scrollTop: currentCanvasContainer ? currentCanvasContainer.scrollTop : 0,
                searchQuery: currentSearchQuery
            };
            try { window.localStorage.setItem(viewStateKey(currentSourceId), JSON.stringify(state)); } catch (e) { /* ignore */ }
        }

        function saveViewStateSoon() {
            window.clearTimeout(viewStateSaveTimer);
            viewStateSaveTimer = window.setTimeout(saveViewStateNow, 400);
        }

        // Only ever called for the 'main' surface (see auto-mount at the
        // bottom of this file) - never overrides an actually-active
        // Document's own thumbnails, and never picks a Document on its
        // own - only the literal last-viewed one, revalidated fresh.
        function mountRememberedThumbnailsIfAny() {
            var remembered = null;
            try { remembered = window.localStorage.getItem(lastPdfSourceKey()); } catch (e) { remembered = null; }
            if (!remembered) return;
            var sources = activeSourcesFromJson();
            var match = null;
            for (var i = 0; i < sources.length; i++) {
                if (sources[i].id === remembered && sources[i].is_pdf) { match = sources[i]; break; }
            }
            if (!match) {
                try { window.localStorage.removeItem(lastPdfSourceKey()); } catch (e) { /* ignore */ }
                return;
            }
            thumbnailsOnlyMode = true;
            loadPdfJs().then(function () {
                return pdfjsLib.getDocument({ url: match.file_url }).promise;
            }).then(function (doc) {
                pdfDoc = doc;
                currentSourceId = match.id;
                var saved = loadViewState(match.id);
                currentPage = (saved && typeof saved.page === 'number' && saved.page >= 1 && saved.page <= doc.numPages) ? saved.page : 1;
                buildThumbnails();
            }).catch(function () {
                thumbnailsOnlyMode = false;
                pdfDoc = null;
            });
        }

        function navigateToDocumentPage(n) {
            if (!currentSourceId) return;
            var stripEl = document.getElementById('document-tab-strip');
            var baseUrl = stripEl ? stripEl.getAttribute('data-base-url') : null;
            if (!baseUrl) return;
            var existing = loadViewState(currentSourceId) || {};
            existing.page = n;
            try { window.localStorage.setItem(viewStateKey(currentSourceId), JSON.stringify(existing)); } catch (e) { /* ignore */ }
            window.location.href = baseUrl + '?source=' + encodeURIComponent(currentSourceId);
        }

        // Only actually shows/hides the ONE shared toolbar when THIS
        // surface currently owns it - a non-focused surface mounting or
        // clearing a document must never steal or blank the toolbar the
        // reviewer is actively looking at.
        function showControls() { if (ownsToolbar()) container.hidden = false; }
        function hideControls() { if (ownsToolbar()) container.hidden = true; }

        function updateNavState() {
            updateThumbnailCurrent();
            if (!ownsToolbar()) return;
            pageInput.value = String(currentPage);
            prevBtn.disabled = currentPage <= 1;
            nextBtn.disabled = !pdfDoc || currentPage >= pdfDoc.numPages;
            zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
        }

        // -------- Thumbnails ---------------------------------------------
        function renderThumbnail(n) {
            var row = thumbnailRows[n - 1];
            if (!row || row.dataset.rendered === '1' || !pdfDoc) return;
            row.dataset.rendered = '1';
            pdfDoc.getPage(n).then(function (page) {
                var unscaled = page.getViewport({ scale: 1 });
                var thumbViewport = page.getViewport({ scale: THUMBNAIL_WIDTH / unscaled.width });
                var thumbCanvas = row.querySelector('canvas');
                if (!thumbCanvas) return;
                thumbCanvas.width = thumbViewport.width;
                thumbCanvas.height = thumbViewport.height;
                return page.render({ canvasContext: thumbCanvas.getContext('2d'), viewport: thumbViewport }).promise;
            });
        }

        function clearThumbnails() {
            if (thumbnailObserver) { thumbnailObserver.disconnect(); thumbnailObserver = null; }
            thumbnailRows = [];
            if (thumbnailsList) thumbnailsList.textContent = '';
            if (thumbnailsEmptyState) thumbnailsEmptyState.hidden = false;
        }

        function buildThumbnails() {
            clearThumbnails();
            if (!thumbnailsList || !pdfDoc) return;
            if (thumbnailsEmptyState) thumbnailsEmptyState.hidden = true;
            var supportsObserver = typeof window.IntersectionObserver === 'function';
            if (supportsObserver) {
                thumbnailObserver = new window.IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) renderThumbnail(parseInt(entry.target.dataset.page, 10));
                    });
                }, { root: thumbnailsList, rootMargin: '200px 0px' });
            }
            for (var n = 1; n <= pdfDoc.numPages; n++) {
                var row = document.createElement('button');
                row.type = 'button';
                row.className = 'thumbnail-row';
                row.dataset.page = String(n);
                row.setAttribute('role', 'listitem');
                row.setAttribute('aria-label', 'Go to page ' + n);
                row.setAttribute('aria-current', n === currentPage ? 'true' : 'false');
                row.appendChild(document.createElement('canvas'));
                var label = document.createElement('span');
                label.className = 'thumbnail-row-label';
                label.textContent = String(n);
                row.appendChild(label);
                row.addEventListener('click', function () {
                    var n = parseInt(this.dataset.page, 10);
                    if (thumbnailsOnlyMode) { navigateToDocumentPage(n); } else { goToPage(n); }
                });
                thumbnailsList.appendChild(row);
                thumbnailRows.push(row);
                if (thumbnailObserver) thumbnailObserver.observe(row);
                else renderThumbnail(n);
            }
            if (thumbnailsPanelVisibility) thumbnailsPanelVisibility();
        }

        function updateThumbnailCurrent() {
            thumbnailRows.forEach(function (row, idx) {
                var isCurrent = (idx + 1) === currentPage;
                row.setAttribute('aria-current', isCurrent ? 'true' : 'false');
                if (isCurrent) {
                    renderThumbnail(idx + 1);
                    if (row.scrollIntoView) row.scrollIntoView({ block: 'nearest' });
                }
            });
        }

        function renderPage() {
            if (!pdfDoc || !canvas) return Promise.resolve();
            return pdfDoc.getPage(currentPage).then(function (page) {
                var viewport = page.getViewport({ scale: currentZoom, rotation: currentRotation });
                canvas.width = viewport.width;
                canvas.height = viewport.height;
                if (overlayCanvas) { overlayCanvas.width = viewport.width; overlayCanvas.height = viewport.height; }
                currentViewport = viewport;
                var ctx = canvas.getContext('2d');
                if (renderTask) { try { renderTask.cancel(); } catch (e) { /* ignore - a newer render superseded it */ } }
                renderTask = page.render({ canvasContext: ctx, viewport: viewport });
                return renderTask.promise.then(function () { updateNavState(); redrawAnnotations(); emit('render'); });
            });
        }

        function goToPage(n) {
            if (!pdfDoc) return;
            n = Math.max(1, Math.min(pdfDoc.numPages, n));
            if (n === currentPage) { updateNavState(); return; }
            currentPage = n;
            selectedAnnotation = null;
            updateAnnotationUi();
            renderPage();
            saveViewStateSoon();
            emit('page');
        }

        function setZoom(z) {
            currentZoom = Math.max(0.25, Math.min(4, z));
            renderPage();
            saveViewStateSoon();
            emit('zoom');
        }

        function fitWidth() {
            if (!pdfDoc || !canvas || !canvas.parentElement) return;
            var containerWidth = canvas.parentElement.clientWidth;
            pdfDoc.getPage(currentPage).then(function (page) {
                var unscaled = page.getViewport({ scale: 1, rotation: currentRotation });
                setZoom(containerWidth / unscaled.width);
            });
        }

        function fitPage() {
            if (!pdfDoc || !canvas || !canvas.parentElement) return;
            var el = canvas.parentElement;
            pdfDoc.getPage(currentPage).then(function (page) {
                var unscaled = page.getViewport({ scale: 1, rotation: currentRotation });
                var scaleW = el.clientWidth / unscaled.width;
                var scaleH = el.clientHeight / unscaled.height;
                setZoom(Math.min(scaleW, scaleH));
            });
        }

        function rotate() {
            currentRotation = (currentRotation + 90) % 360;
            renderPage();
            updateOrientationStatus();
            saveViewStateSoon();
            emit('rotation');
        }

        function applyMirrorTransform() {
            if (!pageWrap) return;
            var scaleX = mirrorH ? -1 : 1;
            var scaleY = mirrorV ? -1 : 1;
            pageWrap.style.transform = (scaleX !== 1 || scaleY !== 1) ? ('scale(' + scaleX + ',' + scaleY + ')') : '';
        }

        function updateOrientationStatus() {
            if (!ownsToolbar() || !orientationStatusEl) return;
            var parts = [];
            if (currentRotation % 360) parts.push('Rotated ' + currentRotation + '° clockwise');
            if (mirrorH) parts.push('mirrored horizontally');
            if (mirrorV) parts.push('mirrored vertically');
            if (!parts.length) { orientationStatusEl.textContent = ''; return; }
            var text = parts.join(' and ');
            orientationStatusEl.textContent = text.charAt(0).toUpperCase() + text.slice(1) + ' — source unchanged';
        }

        function mirrorHorizontal() {
            mirrorH = !mirrorH;
            applyMirrorTransform();
            updateOrientationStatus();
            saveViewStateSoon();
            emit('rotation');
        }

        function mirrorVertical() {
            mirrorV = !mirrorV;
            applyMirrorTransform();
            updateOrientationStatus();
            saveViewStateSoon();
            emit('rotation');
        }

        function resetOrientation() {
            currentRotation = 0;
            mirrorH = false;
            mirrorV = false;
            applyMirrorTransform();
            renderPage();
            updateOrientationStatus();
            saveViewStateSoon();
            emit('rotation');
        }

        function flippedCanvasPoint(pt) {
            return {
                x: mirrorH && canvas ? (canvas.width - pt.x) : pt.x,
                y: mirrorV && canvas ? (canvas.height - pt.y) : pt.y,
            };
        }

        // -------- Search ----------------------------------------------------
        function ensurePageText(n) {
            if (pageTextCache[n] != null) return Promise.resolve(pageTextCache[n]);
            return pdfDoc.getPage(n).then(function (page) {
                return page.getTextContent();
            }).then(function (textContent) {
                var text = textContent.items.map(function (it) { return it.str; }).join(' ').toLowerCase();
                pageTextCache[n] = text;
                return text;
            });
        }

        function updateSearchUi() {
            if (!ownsToolbar()) return;
            searchPrevBtn.disabled = searchMatches.length === 0;
            searchNextBtn.disabled = searchMatches.length === 0;
            if (searchMatches.length) {
                searchCount.textContent = (searchMatchIndex + 1) + ' / ' + searchMatches.length;
            } else {
                searchCount.textContent = currentSearchQuery.trim() ? 'No matches' : '';
            }
        }

        function runSearch(query) {
            query = (query || '').trim().toLowerCase();
            searchMatches = [];
            searchMatchIndex = -1;
            if (!pdfDoc || !query) { updateSearchUi(); return Promise.resolve(); }
            var pages = [];
            for (var p = 1; p <= pdfDoc.numPages; p++) pages.push(p);
            return pages.reduce(function (chain, p) {
                return chain.then(function () {
                    return ensurePageText(p).then(function (text) {
                        var idx = 0;
                        while (true) {
                            var found = text.indexOf(query, idx);
                            if (found === -1) break;
                            searchMatches.push({ page: p });
                            idx = found + query.length;
                        }
                    });
                });
            }, Promise.resolve()).then(function () {
                if (searchMatches.length) {
                    searchMatchIndex = 0;
                    goToPage(searchMatches[0].page);
                }
                updateSearchUi();
                saveViewStateSoon();
            });
        }

        function searchStep(delta) {
            if (!searchMatches.length) return;
            searchMatchIndex = (searchMatchIndex + delta + searchMatches.length) % searchMatches.length;
            goToPage(searchMatches[searchMatchIndex].page);
            updateSearchUi();
        }

        // -------- Annotations (Main-only - see header comment) --------------
        function uid() { return name + 'a' + (annotationIdCounter++); }

        function getPageAnnotations(n) {
            return annotationsByPage[n] || (annotationsByPage[n] = []);
        }

        function hasAnyAnnotations() {
            return Object.keys(annotationsByPage).some(function (k) { return annotationsByPage[k].length > 0; });
        }

        function updateAnnotationUi() {
            if (name !== 'main') return;
            if (deleteBtn) deleteBtn.disabled = !selectedAnnotation;
            if (undoBtn) undoBtn.disabled = undoStack.length === 0;
            if (redoBtn) redoBtn.disabled = redoStack.length === 0;
            if (annotationStatusEl) {
                annotationStatusEl.textContent = hasAnyAnnotations()
                    ? 'Unsaved annotations (draft only - not saved to the Document)'
                    : '';
            }
        }

        function pushUndo(entry) {
            undoStack.push(entry);
            redoStack = [];
            updateAnnotationUi();
        }

        function addAnnotation(pageNum, annotation) {
            getPageAnnotations(pageNum).push(annotation);
            pushUndo({ op: 'add', pageNum: pageNum, annotation: annotation });
            redrawAnnotations();
        }

        function removeAnnotation(pageNum, id) {
            var list = getPageAnnotations(pageNum);
            var idx = -1;
            for (var i = 0; i < list.length; i++) { if (list[i].id === id) { idx = i; break; } }
            if (idx === -1) return;
            var removed = list.splice(idx, 1)[0];
            pushUndo({ op: 'delete', pageNum: pageNum, annotation: removed });
            if (selectedAnnotation && selectedAnnotation.id === id) selectedAnnotation = null;
            redrawAnnotations();
        }

        function undo() {
            var entry = undoStack.pop();
            if (!entry) return;
            var list = getPageAnnotations(entry.pageNum);
            if (entry.op === 'add') {
                for (var i = 0; i < list.length; i++) { if (list[i].id === entry.annotation.id) { list.splice(i, 1); break; } }
            } else if (entry.op === 'delete') {
                list.push(entry.annotation);
            }
            redoStack.push(entry);
            if (entry.pageNum === currentPage) redrawAnnotations();
            updateAnnotationUi();
        }

        function redo() {
            var entry = redoStack.pop();
            if (!entry) return;
            var list = getPageAnnotations(entry.pageNum);
            if (entry.op === 'add') {
                list.push(entry.annotation);
            } else if (entry.op === 'delete') {
                for (var i = 0; i < list.length; i++) { if (list[i].id === entry.annotation.id) { list.splice(i, 1); break; } }
            }
            undoStack.push(entry);
            if (entry.pageNum === currentPage) redrawAnnotations();
            updateAnnotationUi();
        }

        function hitTestAnnotation(pdfX, pdfY) {
            var list = getPageAnnotations(currentPage);
            for (var i = list.length - 1; i >= 0; i--) {
                var a = list[i];
                if (a.type === 'highlight') {
                    var minX = Math.min(a.x1, a.x2), maxX = Math.max(a.x1, a.x2);
                    var minY = Math.min(a.y1, a.y2), maxY = Math.max(a.y1, a.y2);
                    if (pdfX >= minX && pdfX <= maxX && pdfY >= minY && pdfY <= maxY) return a;
                } else if (a.type === 'text') {
                    if (Math.abs(pdfX - a.x) < 40 && Math.abs(pdfY - a.y) < 12) return a;
                } else if (a.type === 'ink') {
                    for (var j = 0; j < a.points.length; j++) {
                        if (Math.abs(pdfX - a.points[j].x) < 8 && Math.abs(pdfY - a.points[j].y) < 8) return a;
                    }
                }
            }
            return null;
        }

        function drawOneAnnotation(ctx, a, isSelected) {
            ctx.save();
            if (a.type === 'ink') {
                ctx.strokeStyle = isSelected ? '#ff6b35' : '#e0b800';
                ctx.lineWidth = isSelected ? 3 : 2;
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';
                ctx.beginPath();
                a.points.forEach(function (p, i) {
                    var v = currentViewport.convertToViewportPoint(p.x, p.y);
                    if (i === 0) ctx.moveTo(v[0], v[1]); else ctx.lineTo(v[0], v[1]);
                });
                ctx.stroke();
            } else if (a.type === 'highlight') {
                var p1 = currentViewport.convertToViewportPoint(a.x1, a.y1);
                var p2 = currentViewport.convertToViewportPoint(a.x2, a.y2);
                var rx = Math.min(p1[0], p2[0]), ry = Math.min(p1[1], p2[1]);
                var rw = Math.abs(p2[0] - p1[0]), rh = Math.abs(p2[1] - p1[1]);
                ctx.fillStyle = isSelected ? 'rgba(255,107,53,0.35)' : 'rgba(255,224,0,0.35)';
                ctx.fillRect(rx, ry, rw, rh);
                if (isSelected) { ctx.strokeStyle = '#ff6b35'; ctx.lineWidth = 1.5; ctx.strokeRect(rx, ry, rw, rh); }
            } else if (a.type === 'text') {
                var v = currentViewport.convertToViewportPoint(a.x, a.y);
                ctx.font = '13px sans-serif';
                ctx.textBaseline = 'top';
                var textW = ctx.measureText(a.text).width;
                ctx.fillStyle = isSelected ? 'rgba(255,200,170,0.95)' : 'rgba(255,247,200,0.95)';
                ctx.fillRect(v[0] - 2, v[1] - 2, textW + 4, 18);
                if (isSelected) { ctx.strokeStyle = '#ff6b35'; ctx.lineWidth = 1.5; ctx.strokeRect(v[0] - 2, v[1] - 2, textW + 4, 18); }
                ctx.fillStyle = '#1a1a1a';
                ctx.fillText(a.text, v[0], v[1]);
            }
            ctx.restore();
        }

        function redrawAnnotations() {
            if (!overlayCanvas || !currentViewport) return;
            var ctx = overlayCanvas.getContext('2d');
            ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            getPageAnnotations(currentPage).forEach(function (a) {
                drawOneAnnotation(ctx, a, !!(selectedAnnotation && selectedAnnotation.id === a.id));
            });
        }

        function drawLivePreview() {
            redrawAnnotations();
            var ctx = overlayCanvas.getContext('2d');
            if (inkDrawing) {
                drawOneAnnotation(ctx, { type: 'ink', points: inkDrawing.points }, false);
            } else if (highlightDrag) {
                drawOneAnnotation(ctx, { type: 'highlight', x1: highlightDrag.x1, y1: highlightDrag.y1, x2: highlightDrag.x2, y2: highlightDrag.y2 }, false);
            } else if (regionDrag) {
                var p1 = currentViewport.convertToViewportPoint(regionDrag.x1, regionDrag.y1);
                var p2 = currentViewport.convertToViewportPoint(regionDrag.x2, regionDrag.y2);
                var rx = Math.min(p1[0], p2[0]), ry = Math.min(p1[1], p2[1]);
                var rw = Math.abs(p2[0] - p1[0]), rh = Math.abs(p2[1] - p1[1]);
                ctx.save();
                ctx.strokeStyle = '#4fa9a2';
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 4]);
                ctx.strokeRect(rx, ry, rw, rh);
                ctx.restore();
            }
        }

        function setActiveTool(tool) {
            if (name !== 'main') return;
            activeTool = (activeTool === tool) ? null : tool;
            annotationToolButtons.forEach(function (btn) {
                btn.setAttribute('aria-pressed', String(btn.dataset.tool === activeTool));
            });
            selectedAnnotation = null;
            updateAnnotationUi();
            redrawAnnotations();
            if (overlayCanvas) overlayCanvas.style.cursor = activeTool ? 'crosshair' : 'default';
            if (activeTool === 'region') {
                ensureSheetUnitForCurrentPage();
            } else if (regionStatusEl) {
                regionStatusEl.textContent = '';
            }
        }

        function canvasPointFromEvent(e) {
            var rect = overlayCanvas.getBoundingClientRect();
            return { x: e.clientX - rect.left, y: e.clientY - rect.top };
        }

        function openTextAnnotationInput(pt, pdfPt) {
            if (activeTextBox) { activeTextBox.remove(); activeTextBox = null; }
            var input = document.createElement('input');
            input.type = 'text';
            input.className = 'document-viewer-annotation-text-input';
            input.style.left = pt.x + 'px';
            input.style.top = pt.y + 'px';
            input.placeholder = 'Annotation text';
            input.setAttribute('aria-label', 'Annotation text');
            pageWrap.appendChild(input);
            activeTextBox = input;
            input.focus();
            function commit() {
                var text = input.value.trim();
                if (input.parentNode) input.parentNode.removeChild(input);
                activeTextBox = null;
                if (text) addAnnotation(currentPage, { id: uid(), type: 'text', x: pdfPt[0], y: pdfPt[1], text: text });
            }
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') { e.preventDefault(); commit(); }
                else if (e.key === 'Escape') { e.preventDefault(); input.value = ''; commit(); }
            });
            input.addEventListener('blur', commit);
        }

        function onOverlayPointerDown(e) {
            if (!activeTool || !currentViewport) return;
            var pt = flippedCanvasPoint(canvasPointFromEvent(e));
            var pdfPt = currentViewport.convertToPdfPoint(pt.x, pt.y);
            if (activeTool === 'ink') {
                inkDrawing = { points: [{ x: pdfPt[0], y: pdfPt[1] }] };
                try { overlayCanvas.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            } else if (activeTool === 'highlight') {
                highlightDrag = { x1: pdfPt[0], y1: pdfPt[1], x2: pdfPt[0], y2: pdfPt[1] };
                try { overlayCanvas.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            } else if (activeTool === 'region') {
                if (!currentSheetUnit || currentSheetUnit.order_index !== (currentPage - 1)) {
                    ensureSheetUnitForCurrentPage();
                    return;
                }
                regionDrag = { x1: pdfPt[0], y1: pdfPt[1], x2: pdfPt[0], y2: pdfPt[1] };
                try { overlayCanvas.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
            } else if (activeTool === 'text') {
                openTextAnnotationInput(pt, pdfPt);
            } else if (activeTool === 'select') {
                var hit = hitTestAnnotation(pdfPt[0], pdfPt[1]);
                selectedAnnotation = hit ? { pageNum: currentPage, id: hit.id } : null;
                updateAnnotationUi();
                redrawAnnotations();
            }
        }

        function onOverlayPointerMove(e) {
            if (!currentViewport || (!inkDrawing && !highlightDrag && !regionDrag)) return;
            var pt = flippedCanvasPoint(canvasPointFromEvent(e));
            var pdfPt = currentViewport.convertToPdfPoint(pt.x, pt.y);
            if (inkDrawing) {
                inkDrawing.points.push({ x: pdfPt[0], y: pdfPt[1] });
            } else if (highlightDrag) {
                highlightDrag.x2 = pdfPt[0];
                highlightDrag.y2 = pdfPt[1];
            } else if (regionDrag) {
                regionDrag.x2 = pdfPt[0];
                regionDrag.y2 = pdfPt[1];
            }
            drawLivePreview();
        }

        function onOverlayPointerUp() {
            if (inkDrawing) {
                if (inkDrawing.points.length > 1) {
                    addAnnotation(currentPage, { id: uid(), type: 'ink', points: inkDrawing.points });
                }
                inkDrawing = null;
            }
            if (highlightDrag) {
                if (Math.abs(highlightDrag.x2 - highlightDrag.x1) > 2 || Math.abs(highlightDrag.y2 - highlightDrag.y1) > 2) {
                    addAnnotation(currentPage, { id: uid(), type: 'highlight', x1: highlightDrag.x1, y1: highlightDrag.y1, x2: highlightDrag.x2, y2: highlightDrag.y2 });
                }
                highlightDrag = null;
            }
            if (regionDrag) {
                var drag = regionDrag;
                regionDrag = null;
                if (Math.abs(drag.x2 - drag.x1) > 2 || Math.abs(drag.y2 - drag.y1) > 2) {
                    commitRegionSelection(drag);
                }
            }
            redrawAnnotations();
        }

        // -------- Drawing regions (Main-only) --------------------------------
        function ensureSheetUnitForCurrentPage() {
            if (name !== 'main' || !regionStatusEl || !currentSourceId) return Promise.resolve(null);
            if (currentSheetUnit && currentSheetUnit.order_index === (currentPage - 1)) {
                return Promise.resolve(currentSheetUnit);
            }
            regionStatusEl.textContent = 'Looking up this sheet…';
            return fetch(apiDocumentsBase() + '/structural-units?source_id=' + encodeURIComponent(currentSourceId), {
                credentials: 'same-origin',
            }).then(function (resp) { return resp.json(); }).then(function (body) {
                var units = (body && body.structural_units) || [];
                renderDrawingCapability(units);
                var match = units.filter(function (u) {
                    return u.unit_type === 'sheet' && u.order_index === (currentPage - 1);
                })[0];
                if (!match) {
                    regionStatusEl.textContent = "This drawing's sheets are not registered yet.";
                    offerRegisterSheets();
                    currentSheetUnit = null;
                    return null;
                }
                currentSheetUnit = match;
                regionStatusEl.textContent = 'Drag a rectangle to create a region.';
                return match;
            }).catch(function () {
                regionStatusEl.textContent = 'Could not look up this sheet.';
                return null;
            });
        }

        function offerRegisterSheets() {
            if (!regionStatusEl) return;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'doc-control-btn';
            btn.textContent = 'Register this drawing';
            btn.addEventListener('click', function () {
                btn.disabled = true;
                fetch(apiDocumentsBase() + '/sources/' + encodeURIComponent(currentSourceId) + '/drawing-structure', {
                    method: 'POST', credentials: 'same-origin',
                }).then(function () {
                    currentSheetUnit = null;
                    return ensureSheetUnitForCurrentPage();
                });
            });
            regionStatusEl.appendChild(document.createTextNode(' '));
            regionStatusEl.appendChild(btn);
        }

        function pdfPointToNormalized(px, py) {
            var meta = currentSheetUnit.modality_metadata || {};
            var w = meta.width || 1;
            var h = meta.height || 1;
            return { x: px / w, y: 1 - (py / h) };
        }

        function commitRegionSelection(drag) {
            if (!currentSheetUnit) return;
            var n1 = pdfPointToNormalized(drag.x1, drag.y1);
            var n2 = pdfPointToNormalized(drag.x2, drag.y2);
            var x = Math.max(0, Math.min(n1.x, n2.x));
            var y = Math.max(0, Math.min(n1.y, n2.y));
            var width = Math.min(1 - x, Math.abs(n2.x - n1.x));
            var height = Math.min(1 - y, Math.abs(n2.y - n1.y));
            if (regionStatusEl) regionStatusEl.textContent = 'Saving region…';
            fetch(apiDocumentsBase() + '/sources/' + encodeURIComponent(currentSourceId) + '/drawing-regions', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ structural_unit_id: currentSheetUnit.id, x: x, y: y, width: width, height: height }),
            }).then(function (resp) { return resp.json().then(function (body) { return { ok: resp.ok, body: body }; }); })
                .then(function (result) {
                    if (!regionStatusEl) return;
                    if (!result.ok) {
                        regionStatusEl.textContent = 'Could not save that region: ' + (result.body.message || 'unknown error');
                        return;
                    }
                    var label = result.body.citation && result.body.citation.label;
                    var evidenceId = result.body.evidence_item && result.body.evidence_item.id;
                    if (evidenceId) drawingCapabilityEvidenceId = evidenceId;
                    regionStatusEl.textContent = '';
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
                    if (drawingCapabilityEvidenceId) {
                        fetch(apiDocumentsBase() + '/structural-units?source_id=' + encodeURIComponent(currentSourceId), { credentials: 'same-origin' })
                            .then(function (response) { return response.json(); })
                            .then(function (body) { renderDrawingCapability((body && body.structural_units) || []); });
                    }
                });
        }

        function resetAnnotationState() {
            annotationsByPage = {};
            undoStack = [];
            redoStack = [];
            selectedAnnotation = null;
            activeTool = null;
            inkDrawing = null;
            highlightDrag = null;
            if (activeTextBox) { if (activeTextBox.parentNode) activeTextBox.parentNode.removeChild(activeTextBox); activeTextBox = null; }
            if (name === 'main') {
                annotationToolButtons.forEach(function (btn) { btn.setAttribute('aria-pressed', 'false'); });
            }
            updateAnnotationUi();
        }

        // -------- Mount / unmount -------------------------------------------
        function mount(url, canvasContainer, downloadFilename, sourceId) {
            currentSourceId = sourceId || null;
            currentCanvasContainer = canvasContainer;
            currentUrl = url;
            currentDownloadFilename = downloadFilename || null;
            return loadPdfJs().then(function () {
                canvas = document.createElement('canvas');
                canvas.className = 'document-viewer-canvas';
                pageWrap = document.createElement('div');
                pageWrap.className = 'document-viewer-page-wrap';
                pageWrap.appendChild(canvas);
                overlayCanvas = document.createElement('canvas');
                overlayCanvas.className = 'document-viewer-annotation-layer';
                overlayCanvas.setAttribute('aria-hidden', 'true');
                pageWrap.appendChild(overlayCanvas);
                overlayCanvas.addEventListener('pointerdown', onOverlayPointerDown);
                overlayCanvas.addEventListener('pointermove', onOverlayPointerMove);
                overlayCanvas.addEventListener('pointerup', onOverlayPointerUp);
                canvasContainer.textContent = '';
                canvasContainer.appendChild(pageWrap);
                canvasContainer.addEventListener('scroll', saveViewStateSoon);
                return pdfjsLib.getDocument({ url: url }).promise;
            }).then(function (doc) {
                pdfDoc = doc;
                thumbnailsOnlyMode = false;
                if (name === 'main') rememberLastPdfSource(currentSourceId);
                var saved = loadViewState(currentSourceId);
                var hasSavedPage = saved && typeof saved.page === 'number' && saved.page >= 1 && saved.page <= doc.numPages;
                currentPage = hasSavedPage ? saved.page : 1;
                currentRotation = (saved && typeof saved.rotation === 'number') ? saved.rotation : 0;
                mirrorH = !!(saved && saved.mirrorH);
                mirrorV = !!(saved && saved.mirrorV);
                currentSheetUnit = null;
                drawingCapabilityEvidenceId = null;
                drawingCapabilityPanel = null;
                if (ownsToolbar() && regionStatusEl) regionStatusEl.textContent = '';
                applyMirrorTransform();
                updateOrientationStatus();
                pageTextCache = {};
                searchMatches = [];
                searchMatchIndex = -1;
                currentSearchQuery = (saved && saved.searchQuery) || '';
                if (ownsToolbar()) searchInput.value = currentSearchQuery;
                if (ownsToolbar()) pageTotal.textContent = String(pdfDoc.numPages);
                if (ownsToolbar()) {
                    downloadLink.href = url;
                    if (downloadFilename) downloadLink.setAttribute('download', downloadFilename); else downloadLink.removeAttribute('download');
                }
                updateSearchUi();
                showControls();
                if (name === 'main') ensureSheetUnitForCurrentPage();
                resetAnnotationState();
                buildThumbnails();
                if (saved && saved.zoom) {
                    currentZoom = Math.max(0.25, Math.min(4, saved.zoom));
                    return renderPage().then(function () {
                        if (saved.scrollLeft || saved.scrollTop) {
                            canvasContainer.scrollLeft = saved.scrollLeft || 0;
                            canvasContainer.scrollTop = saved.scrollTop || 0;
                        }
                    });
                }
                return fitWidth();
            }).catch(function (err) {
                hideControls();
                resetAnnotationState();
                clearThumbnails();
                showLoadError(canvasContainer, err);
            });
        }

        function unmount() {
            saveViewStateNow();
            if (currentCanvasContainer) currentCanvasContainer.removeEventListener('scroll', saveViewStateSoon);
            pdfDoc = null;
            canvas = null;
            overlayCanvas = null;
            pageWrap = null;
            currentViewport = null;
            currentSourceId = null;
            currentCanvasContainer = null;
            currentUrl = null;
            currentDownloadFilename = null;
            // saveViewStateNow() above has already persisted this; clearing it
            // keeps a post-unmount snapshot() honest rather than publishing the
            // previous document's query to a subscribed consumer.
            currentSearchQuery = '';
            thumbnailsOnlyMode = false;
            mirrorH = false;
            mirrorV = false;
            currentSheetUnit = null;
            drawingCapabilityEvidenceId = null;
            if (drawingCapabilityPanel && drawingCapabilityPanel.parentNode) drawingCapabilityPanel.parentNode.removeChild(drawingCapabilityPanel);
            drawingCapabilityPanel = null;
            regionDrag = null;
            if (ownsToolbar() && regionStatusEl) regionStatusEl.textContent = '';
            hideControls();
            clearThumbnails();
            resetAnnotationState();
            if (thumbnailsPanelVisibility) thumbnailsPanelVisibility();
        }

        // Re-syncs the ONE shared toolbar to THIS surface's own state -
        // called whenever focus switches TO this surface (setFocus above).
        function refreshToolbar() {
            if (!ownsToolbar()) return;
            if (!pdfDoc) { container.hidden = true; return; }
            container.hidden = false;
            downloadLink.href = currentUrl || '';
            if (currentDownloadFilename) downloadLink.setAttribute('download', currentDownloadFilename); else downloadLink.removeAttribute('download');
            searchInput.value = currentSearchQuery;
            updateNavState();
            pageTotal.textContent = pdfDoc ? String(pdfDoc.numPages) : '';
            updateSearchUi();
            updateOrientationStatus();
            if (name === 'main') updateAnnotationUi();
        }

        // CLAUDE-SNAPSHOT-DUAL-SURFACE-01: captures whatever THIS surface's
        // own <canvas> currently shows (its real rendered page, at
        // whatever zoom/rotation is active) and registers it as a new
        // derived Source, parented to THIS surface's own currentSourceId -
        // "active Main -> snapshot Main; active Eye -> snapshot Eye," never
        // inferred from rail selection. The shared toolbar's own snapshot
        // button (below) calls getFocused().takeSnapshot(), so it is
        // already scoped to whichever surface owns focus by construction.
        function takeSnapshot() {
            if (!pdfDoc || !canvas || !currentSourceId) return Promise.resolve(null);
            var dataUrl = canvas.toDataURL('image/png');
            var pageNum = currentPage;
            var stripEl = document.getElementById('document-tab-strip');
            var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
            if (!projectId) return Promise.resolve(null);
            return fetch('/api/v1/documents/' + encodeURIComponent(projectId) + '/sources/' + encodeURIComponent(currentSourceId) + '/snapshot', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl, page: pageNum }),
            }).then(function (resp) {
                return resp.json().then(function (body) { return { ok: resp.ok, status: resp.status, body: body }; });
            });
        }

        var api = {
            name: name,
            hasSheetEvidence: hasSheetEvidence,
            mount: mount,
            unmount: unmount,
            takeSnapshot: takeSnapshot,
            hasDoc: function () { return !!pdfDoc; },
            getSourceId: function () { return currentSourceId; },
            getPage: function () { return currentPage; },
            prevPage: function () { goToPage(currentPage - 1); },
            nextPage: function () { goToPage(currentPage + 1); },
            goToPage: goToPage,
            setPageFromInput: function (raw) {
                var n = parseInt(raw, 10);
                if (!isNaN(n)) goToPage(n); else if (ownsToolbar()) pageInput.value = String(currentPage);
            },
            zoomIn: function () { setZoom(currentZoom + 0.1); },
            zoomOut: function () { setZoom(currentZoom - 0.1); },
            getZoom: function () { return currentZoom; },
            fitWidth: fitWidth,
            fitPage: fitPage,
            rotate: rotate,
            mirrorHorizontal: mirrorHorizontal,
            mirrorVertical: mirrorVertical,
            resetOrientation: resetOrientation,
            onSearchInput: function (value) {
                currentSearchQuery = value || '';
                window.clearTimeout(searchDebounce);
                searchDebounce = window.setTimeout(function () { runSearch(value); }, 300);
            },
            onSearchEnter: function (shiftKey) {
                if (searchMatches.length) searchStep(shiftKey ? -1 : 1);
                else runSearch(currentSearchQuery);
            },
            setSearchQuery: function (value) { currentSearchQuery = value || ''; },
            subscribe: subscribe,
            emit: emit,
            getState: snapshot,
            searchStep: searchStep,
            print: function () { if (currentUrl) window.open(currentUrl, '_blank'); },
            setActiveTool: setActiveTool,
            escapeActiveTool: function () { if (activeTool) setActiveTool(activeTool); },
            deleteSelected: function () { if (selectedAnnotation) removeAnnotation(selectedAnnotation.pageNum, selectedAnnotation.id); },
            undo: undo,
            redo: redo,
            hasAnyAnnotations: hasAnyAnnotations,
            refreshToolbar: refreshToolbar,
            saveViewStateNow: saveViewStateNow,
            mountRememberedThumbnailsIfAny: mountRememberedThumbnailsIfAny,
        };
        surfaces[name] = api;
        return api;
    }

    // -------- Eye's Toolbox thumbnails panel (CLAUDE-DUAL-DOCUMENT-FOCUS-01,
    // Part 2/5/7) - shown only while Eye actually holds a paginated (PDF)
    // document; Toolbox returns to its normal tool content the rest of the
    // time. Driven from buildThumbnails()/unmount() above via this single
    // shared visibility function (not scattered per call site). ------------
    var toolboxNormalContent = document.getElementById('toolbox-normal-content');
    var toolboxEyeThumbnailsPanel = document.getElementById('toolbox-eye-thumbnails-panel');
    var thumbnailsPanelVisibility = null;
    if (toolboxNormalContent && toolboxEyeThumbnailsPanel) {
        thumbnailsPanelVisibility = function () {
            var eyeSurface = surfaces.eye;
            var eyeHasDoc = !!(eyeSurface && eyeSurface.hasDoc());
            toolboxEyeThumbnailsPanel.hidden = !eyeHasDoc;
            toolboxNormalContent.hidden = eyeHasDoc;
            // CLAUDE-DUAL-DOCUMENT-FOCUS-01 addendum A: Eye's own
            // whole-column visibility (Eye pane + divider vs. full-height
            // Toolbox) is eye_pane.js's own responsibility (it also knows
            // about the non-PDF states - a pasted image, Compare-active-
            // and-empty - that this file has no visibility into) - just
            // ask it to recompute now that Eye's PDF state changed.
            if (window.ArchioskEyeLayout) window.ArchioskEyeLayout.refresh();
        };
    }

    // -------- Event wiring: the ONE shared toolbar dispatches to
    // -------- whichever surface currently has focus. ---------------------
    if (prevBtn) prevBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.prevPage(); });
    if (nextBtn) nextBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.nextPage(); });
    if (pageInput) pageInput.addEventListener('change', function () { var s = getFocused(); if (s) s.setPageFromInput(pageInput.value); });
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.zoomOut(); });
    if (zoomInBtn) zoomInBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.zoomIn(); });
    if (fitWidthBtn) fitWidthBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.fitWidth(); });
    if (fitPageBtn) fitPageBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.fitPage(); });
    if (rotateBtn) rotateBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.rotate(); });
    if (mirrorHBtn) mirrorHBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.mirrorHorizontal(); });
    if (mirrorVBtn) mirrorVBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.mirrorVertical(); });
    if (resetOrientationBtn) resetOrientationBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.resetOrientation(); });
    if (searchInput) searchInput.addEventListener('input', function () { var s = getFocused(); if (s) s.onSearchInput(searchInput.value); });
    if (searchInput) searchInput.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        var s = getFocused();
        if (s) s.onSearchEnter(e.shiftKey);
    });
    if (searchPrevBtn) searchPrevBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.searchStep(-1); });
    if (searchNextBtn) searchNextBtn.addEventListener('click', function () { var s = getFocused(); if (s) s.searchStep(1); });
    if (printBtn) printBtn.addEventListener('click', function () {
        // A real, functional Print: opens the FOCUSED surface's own
        // original PDF (native browser PDF chrome) in a new tab.
        var s = getFocused();
        if (s) s.print();
    });

    // CLAUDE-SNAPSHOT-DUAL-SURFACE-01: captures whichever surface owns
    // this toolbar, registers a real new -01/-02 Source, then opens it
    // as a new, active Main tab via the SAME real navigation every other
    // "open a document" action in this app already uses (document_tabs.js
    // itself decides tab placement/pinning from that navigation - nothing
    // Main-tab-specific is special-cased here). Eye's own document state
    // is client-side-only and does not survive a page reload - if EYE
    // (not Main) triggered this, its current document identity is
    // stashed in a one-shot sessionStorage marker BEFORE navigating, so
    // eye_pane.js can restore it once on the next load ("Eye remains on
    // PDF B after the snapshot") without inventing a general Eye-
    // persists-across-reload feature.
    if (snapshotBtn) {
        snapshotBtn.addEventListener('click', function () {
            var s = getFocused();
            if (!s || !s.hasDoc()) return;
            var wasEye = window.__activeDocumentSurface === 'eye';
            snapshotBtn.disabled = true;
            if (snapshotStatusEl) snapshotStatusEl.textContent = 'Capturing…';
            s.takeSnapshot().then(function (result) {
                snapshotBtn.disabled = false;
                if (!result || !result.ok) {
                    var message = (result && result.body && result.body.message) || 'unknown error';
                    if (snapshotStatusEl) snapshotStatusEl.textContent = 'Could not create Snapshot: ' + message;
                    return;
                }
                if (snapshotStatusEl) snapshotStatusEl.textContent = '';
                var stripEl = document.getElementById('document-tab-strip');
                var baseUrl = stripEl ? stripEl.getAttribute('data-base-url') : null;
                if (!baseUrl) return;
                if (wasEye && window.ArchioskEyePane && window.ArchioskEyePane.getRestoreState) {
                    var restoreState = window.ArchioskEyePane.getRestoreState();
                    if (restoreState) {
                        var projectId = stripEl.getAttribute('data-project-id');
                        try {
                            window.sessionStorage.setItem(
                                'beehive:eye:pending-restore:' + projectId,
                                JSON.stringify(restoreState)
                            );
                        } catch (e) { /* ignore */ }
                    }
                }
                window.location.href = baseUrl + '?source=' + encodeURIComponent(result.body.source_id);
            });
        });
    }

    // Annotation/region toolbar - always dispatches to Main (see header
    // comment); the buttons themselves are disabled while Eye is focused
    // (applyFocusIndication above), so this only ever fires for Main.
    annotationToolButtons.forEach(function (btn) {
        btn.addEventListener('click', function () { var m = surfaces.main; if (m) m.setActiveTool(btn.dataset.tool); });
    });
    if (deleteBtn) deleteBtn.addEventListener('click', function () { var m = surfaces.main; if (m) m.deleteSelected(); });
    if (undoBtn) undoBtn.addEventListener('click', function () { var m = surfaces.main; if (m) m.undo(); });
    if (redoBtn) redoBtn.addEventListener('click', function () { var m = surfaces.main; if (m) m.redo(); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { var m = surfaces.main; if (m) m.escapeActiveTool(); }
    });
    window.addEventListener('beforeunload', function (e) {
        var anyAnnotations = Object.keys(surfaces).some(function (n) { return surfaces[n].hasAnyAnnotations(); });
        if (anyAnnotations) { e.preventDefault(); e.returnValue = ''; }
    });

    // -------- The Main surface (this file's own long-standing default) ---
    var mainSurface = createPdfSurface('main', document.getElementById('thumbnails-list'), document.getElementById('thumbnails-empty-state'));

    window.ArchioskPdfViewer = {
        mount: mainSurface.mount,
        unmount: mainSurface.unmount,
        createSurface: createPdfSurface,
        _hasSheetEvidence: mainSurface.hasSheetEvidence,
        setFocus: setFocus,
        getFocusedName: function () { return window.__activeDocumentSurface; },
    };

    // CLAUDE-P40-DTAB1, Section 6: flush every surface's own debounced
    // save on the way out, not just the one that happened to be focused.
    window.addEventListener('pagehide', function () {
        Object.keys(surfaces).forEach(function (n) { surfaces[n].saveViewStateNow(); });
    });

    // -------- Auto-mount (Main only) --------------------------------------
    var autoMountEl = document.getElementById('document-viewer-pdf-canvas');
    if (autoMountEl && autoMountEl.dataset.pdfUrl) {
        mainSurface.mount(autoMountEl.dataset.pdfUrl, autoMountEl, autoMountEl.dataset.pdfFilename || '', autoMountEl.dataset.sourceId || '');
    } else {
        var stripElForThumbnails = document.getElementById('document-tab-strip');
        var hasActiveDocumentSelection = !!(stripElForThumbnails && stripElForThumbnails.getAttribute('data-selected-source-id'));
        if (!hasActiveDocumentSelection) {
            mainSurface.mountRememberedThumbnailsIfAny();
        }
    }
})();
