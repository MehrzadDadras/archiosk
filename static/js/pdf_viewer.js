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
 */
(function () {
    'use strict';

    var container = document.getElementById('workspace-document-controls');
    if (!container) return;

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
    if (!prevBtn || !nextBtn || !pageInput || !zoomOutBtn || !zoomInBtn || !searchInput) return;

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

    // -------- PDF.js state ---------------------------------------------
    var pdfjsLib = null;
    var pdfDoc = null;
    var canvas = null;
    var currentPage = 1;
    var currentZoom = 1.0;
    var currentRotation = 0;
    // CLAUDE-MM4 Section 7: view-only orientation state, layered ON TOP
    // of the existing PDF.js-baked rotation via a plain CSS transform on
    // pageWrap (see applyMirrorTransform below) - the underlying PDF
    // bytes are never touched by either currentRotation or these.
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
    var viewStateSaveTimer = null;
    // CLAUDE-P40-LTH1: true only while the currently-built thumbnail
    // list belongs to a REMEMBERED Document (Section 3) rather than the
    // one actually mounted on THIS page (no #document-viewer-pdf-canvas
    // exists at all in that case) - changes only how a thumbnail click
    // behaves (see buildThumbnails' own click handler and
    // navigateToDocumentPage below): a real page navigation instead of
    // goToPage(), since there is no live canvas here to render into.
    var thumbnailsOnlyMode = false;

    // -------- Per-tab viewer state persistence (CLAUDE-P40-DTAB1,
    // Section 6) - "where the existing viewer architecture supports it
    // safely, preserve state independently for each open Document tab."
    // This is a full-page-reload app (no live SPA instance to hold state
    // in memory across a tab switch - see static/js/document_tabs.js's
    // own header comment) - persisted to localStorage keyed by username
    // + Project + source id, restored on the NEXT mount() for that same
    // Document instead of always starting at page 1/100%/0deg. Username-
    // scoped for the same cross-account-leakage reason document_tabs.js
    // already establishes. ------------------------------------------
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
            searchQuery: searchInput ? searchInput.value : ''
        };
        try { window.localStorage.setItem(viewStateKey(currentSourceId), JSON.stringify(state)); } catch (e) { /* ignore */ }
    }

    // -------- Remembered Document context (CLAUDE-P40-LTH1, Section 3) --
    // This is a full-page-reload app - "remember" means client-side
    // persistence + revalidation on the NEXT load, not an in-memory
    // carry-over from one page to the next. Same key shape as
    // viewStateKey above (username + Project, matching document_tabs.js's
    // own established cross-account-leakage guard) so switching accounts
    // or Projects never leaks another workspace's last-viewed Document.
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

    // Only ever called when THIS page has no Document of its own
    // selected (see the auto-mount section at the bottom of this file) -
    // never overrides an actually-active Document's own thumbnails, and
    // never picks a Document on its own (Section 3's explicit "do not
    // arbitrarily choose a Document merely because the Project contains
    // one or more Documents") - only the literal last-viewed one,
    // revalidated fresh against activeSourcesFromJson() every time. A
    // stale, removed, or unauthorized remembered id clears itself and
    // falls through to the pane's own default empty state - never a
    // broken reference, never another Project's data (the key itself is
    // Project-scoped, so a foreign Project's id could not even be
    // looked up from here).
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
            // CLAUDE-P40-VW7B-QA1: same object-form fix as mount()'s
            // own getDocument() call - see that call site's own
            // comment for why a bare string was never valid here.
            return pdfjsLib.getDocument({ url: match.file_url }).promise;
        }).then(function (doc) {
            pdfDoc = doc;
            currentSourceId = match.id;
            var saved = loadViewState(match.id);
            currentPage = (saved && typeof saved.page === 'number' && saved.page >= 1 && saved.page <= doc.numPages) ? saved.page : 1;
            buildThumbnails();
        }).catch(function () {
            // Section 7: fails closed to the empty state, never a
            // partially-built or broken thumbnail list.
            thumbnailsOnlyMode = false;
            pdfDoc = null;
        });
    }

    // A thumbnail click in thumbnailsOnlyMode has no live canvas to
    // render into (no Document is actually open on this page) - a real
    // navigation to the Document route instead, landing directly on the
    // clicked page by writing it into the SAME view-state store mount()
    // already reads on load (loadViewState above), not a new mechanism.
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

    function saveViewStateSoon() {
        window.clearTimeout(viewStateSaveTimer);
        viewStateSaveTimer = window.setTimeout(saveViewStateNow, 400);
    }

    function showControls() { container.hidden = false; }
    function hideControls() { container.hidden = true; }

    function loadPdfJs() {
        if (pdfjsLib) return Promise.resolve(pdfjsLib);
        return import('/static/js/vendor/pdfjs/pdf.min.mjs').then(function (mod) {
            pdfjsLib = mod;
            pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/js/vendor/pdfjs/pdf.worker.min.mjs';
            return pdfjsLib;
        });
    }

    function updateNavState() {
        pageInput.value = String(currentPage);
        prevBtn.disabled = currentPage <= 1;
        nextBtn.disabled = !pdfDoc || currentPage >= pdfDoc.numPages;
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
        updateThumbnailCurrent();
    }

    // -------- Thumbnails (CLAUDE-P40-VW7A-QA2, Section 3) ---------------
    // One real <button role="listitem"> per page, lazily rendered via
    // IntersectionObserver so opening a long PDF doesn't render every
    // page's thumbnail up front - only the ones actually scrolled near.
    // Scope, stated honestly: this viewer shows one page at a time on a
    // single <canvas> (Section 2's own page-navigation model), not a
    // continuous multi-page scroll surface - "thumbnail list follows page
    // changes from scrolling" therefore has nothing to listen for beyond
    // what already drives it: every goToPage() (toolbar prev/next, the
    // page-number input, search-result jumps, or a thumbnail click
    // itself) funnels through updateNavState() -> updateThumbnailCurrent()
    // below, so the highlighted thumbnail and the rendered page can never
    // drift out of sync regardless of which control changed the page.
    var thumbnailsList = document.getElementById('thumbnails-list');
    var thumbnailsEmptyState = document.getElementById('thumbnails-empty-state');
    var thumbnailRows = [];
    var thumbnailObserver = null;
    var THUMBNAIL_WIDTH = 140;

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
        // CLAUDE-P40-LTH1: the pane itself is a permanent structural
        // surface now (see templates/base.html's own comment on
        // .lists-pane) - "nothing to show" is communicated by this
        // empty-state message reappearing, not by hiding the pane.
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
            // CLAUDE-P40-LTH1: a remembered Document (thumbnailsOnlyMode)
            // has no live canvas on THIS page to render into - a real
            // navigation to the Document route instead of goToPage().
            row.addEventListener('click', function () {
                var n = parseInt(this.dataset.page, 10);
                if (thumbnailsOnlyMode) { navigateToDocumentPage(n); } else { goToPage(n); }
            });
            thumbnailsList.appendChild(row);
            thumbnailRows.push(row);
            if (thumbnailObserver) thumbnailObserver.observe(row);
            else renderThumbnail(n);
        }
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
            return renderTask.promise.then(function () { updateNavState(); redrawAnnotations(); });
        });
    }

    function goToPage(n) {
        if (!pdfDoc) return;
        n = Math.max(1, Math.min(pdfDoc.numPages, n));
        if (n === currentPage) { updateNavState(); return; }
        currentPage = n;
        // A selection is tied to a specific page's own rendered overlay -
        // carrying it across a page change would either select nothing
        // (Section 4's "clear active-tool indication" applies to
        // selection too) or, worse, silently act on the wrong page's
        // annotation if two pages ever reused the same id.
        selectedAnnotation = null;
        updateAnnotationUi();
        renderPage();
        saveViewStateSoon();
    }

    function setZoom(z) {
        currentZoom = Math.max(0.25, Math.min(4, z));
        renderPage();
        saveViewStateSoon();
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
    }

    // -------- Orientation: mirror + reset (CLAUDE-MM4 Section 7) --------
    // Mirror is deliberately NOT baked into the PDF.js render viewport
    // the way currentRotation is (that would require re-deriving PDF.js's
    // own viewport math for a transform it has no native concept of) -
    // instead a plain CSS transform on pageWrap (the SAME element already
    // wrapping both canvas and overlayCanvas together, so the rendered
    // page and any annotations/regions drawn on it always mirror as one
    // unit, never independently). This composes as ROTATE-then-MIRROR
    // (PDF.js bakes rotation into the canvas raster FIRST; the CSS
    // transform mirrors that already-rotated raster on top) - a
    // different, but equally valid, composition order from services/
    // drawing_intelligence.py's own MIRROR-then-rotate convention (used
    // by static/js/drawing_image_viewer.js, which has no PDF.js baked-
    // rotation constraint to work around). What matters for correctness
    // is that THIS pipeline's own forward (render) and inverse (pointer
    // coordinate correction below) compose consistently with EACH OTHER,
    // which flippedCanvasPoint below is written to guarantee, not that
    // every drawing surface in this app shares one universal order.
    function applyMirrorTransform() {
        if (!pageWrap) return;
        var scaleX = mirrorH ? -1 : 1;
        var scaleY = mirrorV ? -1 : 1;
        pageWrap.style.transform = (scaleX !== 1 || scaleY !== 1) ? ('scale(' + scaleX + ',' + scaleY + ')') : '';
    }

    function updateOrientationStatus() {
        if (!orientationStatusEl) return;
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
    }

    function mirrorVertical() {
        mirrorV = !mirrorV;
        applyMirrorTransform();
        updateOrientationStatus();
        saveViewStateSoon();
    }

    function resetOrientation() {
        currentRotation = 0;
        mirrorH = false;
        mirrorV = false;
        applyMirrorTransform();
        renderPage();
        updateOrientationStatus();
        saveViewStateSoon();
    }

    // A raw on-screen pointer position, corrected for the CURRENT mirror
    // state, in CANVAS pixel space - i.e. "undo the CSS mirror" before
    // handing the point to PDF.js's own currentViewport.convertToPdfPoint
    // (which already inverts PDF.js's OWN baked-in rotation). Composing
    // these two inversions in this order is exactly the inverse of this
    // pipeline's own forward composition (see applyMirrorTransform's own
    // comment above) - proven correct by tests/test_mm4_drawing_
    // intelligence.py's equivalent round-trip property for the shared
    // mirror math, and re-verified live (create a region while mirrored,
    // reset orientation, confirm the region redisplays in the same real
    // drawing location).
    function flippedCanvasPoint(pt) {
        return {
            x: mirrorH && canvas ? (canvas.width - pt.x) : pt.x,
            y: mirrorV && canvas ? (canvas.height - pt.y) : pt.y,
        };
    }

    // -------- Search (Section: "search... where applicable") -----------
    // Real full-document text search via PDF.js's own text-content
    // extraction (page.getTextContent()) - not a placeholder. Searches
    // every page once per query (cached per page in pageTextCache so
    // repeated searches in the same document don't re-extract), jumps
    // to and cycles through matches by page.
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
        searchPrevBtn.disabled = searchMatches.length === 0;
        searchNextBtn.disabled = searchMatches.length === 0;
        if (searchMatches.length) {
            searchCount.textContent = (searchMatchIndex + 1) + ' / ' + searchMatches.length;
        } else {
            searchCount.textContent = searchInput.value.trim() ? 'No matches' : '';
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

    // -------- Annotations (CLAUDE-P40-VW7A-QA2, Section 4) ---------------
    // A transparent <canvas> overlay drawn on top of the page canvas
    // (mount() below wraps both in one .document-viewer-page-wrap).
    // Coordinates are stored in PDF page space (PDFPageProxy's own
    // unscaled/unrotated point system, via the current PageViewport's
    // convertToPdfPoint/convertToViewportPoint) rather than raw canvas
    // pixels, so an annotation drawn at one zoom/rotation still lands in
    // the correct place after zooming, rotating, or fitting - it is
    // redrawn from this page-space data on every renderPage(), never
    // baked into a fixed pixel position.
    //
    // Honest scope boundary (Section 4's own explicit permission to stop
    // and report rather than fake a control): the original Document file
    // is NEVER touched - this is purely an in-memory client-side overlay,
    // reset on every mount()/unmount(). There is no Save/Export button
    // for it (base.html's own comment on #doc-annotate-* documents why) -
    // no PDF-writing library is vendored in this repo (only the
    // rendering half of PDF.js - see vendor/pdfjs/README.md), and adding
    // one is a real new-dependency decision (tools/dependency_fit.py)
    // this stage does not make silently. #doc-annotation-status and the
    // beforeunload warning below are how "clearly indicate unsaved
    // changes... warn before discarding" is satisfied without a
    // nonfunctional save control - annotations are real, interactive,
    // and undoable for the current browser session; they are not
    // persisted anywhere, and nothing in this file claims otherwise.
    var annotationsByPage = {};
    var annotationIdCounter = 1;
    var undoStack = [];
    var redoStack = [];
    var activeTool = null;
    var selectedAnnotation = null;
    var inkDrawing = null;
    var highlightDrag = null;
    var activeTextBox = null;
    // CLAUDE-MM4: drag-to-select-rectangle state for the "region" tool -
    // same shape as highlightDrag (x1/y1/x2/y2 in PDF-page space), kept
    // separate so a region selection is never confused with an ephemeral,
    // never-persisted highlight annotation.
    var regionDrag = null;
    var currentStructuralUnitId = null;
    var currentProjectId = null; // set from the canvas container's own dataset, see mount() below

    var annotationToolButtons = [];
    ['doc-annotate-text', 'doc-annotate-highlight', 'doc-annotate-ink', 'doc-annotate-select', 'doc-region-select'].forEach(function (id) {
        var btn = document.getElementById(id);
        if (btn) annotationToolButtons.push(btn);
    });
    var deleteBtn = document.getElementById('doc-annotate-delete');
    var undoBtn = document.getElementById('doc-annotate-undo');
    var redoBtn = document.getElementById('doc-annotate-redo');
    var annotationStatusEl = document.getElementById('doc-annotation-status');

    function uid() { return 'a' + (annotationIdCounter++); }

    function getPageAnnotations(n) {
        return annotationsByPage[n] || (annotationsByPage[n] = []);
    }

    function hasAnyAnnotations() {
        return Object.keys(annotationsByPage).some(function (k) { return annotationsByPage[k].length > 0; });
    }

    function updateAnnotationUi() {
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
            // CLAUDE-MM4: rendered in a distinct teal (matches the app's
            // own evidence/region accent elsewhere) so a region-in-
            // progress is never visually confused with an ephemeral
            // highlight annotation while dragging.
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

    // -------- Drawing regions (CLAUDE-MM4 Section 4/6/12) ----------------
    // Real, PERSISTED AddressableRegions - distinct from the ephemeral,
    // never-saved annotations above (Section 4: "create direct evidence
    // anchored to that region"). Reuses this same overlay's own pointer/
    // coordinate infrastructure (including the mirror-flip correction
    // every other tool now shares) rather than a second selection
    // mechanism.
    function apiDocumentsBase() {
        var stripEl = document.getElementById('document-tab-strip');
        var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
        return '/api/v1/documents/' + encodeURIComponent(projectId || '');
    }

    // Sheet StructuralUnit for the CURRENTLY DISPLAYED page - fetched
    // lazily (not on every mount(), only when the reviewer actually
    // activates the region tool) and re-fetched on every page change,
    // since each PDF page is its own sheet (register_drawing_sheet_
    // structure's own one-unit-per-page contract).
    var currentSheetUnit = null;

    function ensureSheetUnitForCurrentPage() {
        if (!regionStatusEl || !currentSourceId) return Promise.resolve(null);
        if (currentSheetUnit && currentSheetUnit.order_index === (currentPage - 1)) {
            return Promise.resolve(currentSheetUnit);
        }
        regionStatusEl.textContent = 'Looking up this sheet…';
        return fetch(apiDocumentsBase() + '/structural-units?source_id=' + encodeURIComponent(currentSourceId), {
            credentials: 'same-origin',
        }).then(function (resp) { return resp.json(); }).then(function (body) {
            var units = (body && body.structural_units) || [];
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

    // Converts a PDF-user-space point (origin bottom-left, y-up - the
    // SAME frame page.mediabox.width/height, stored server-side by
    // services/drawing_intelligence.py, already describes) into this
    // module's own normalized 0-1, origin top-left, y-down convention -
    // the one every AddressableRegion is stored in. Assumes a zero-
    // origin mediabox (true for the overwhelming majority of real-world
    // PDFs, including this repository's own hand-built test fixture) -
    // a nonzero mediabox origin is a known, undocumented-until-now edge
    // case this stage does not correct for.
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
        annotationToolButtons.forEach(function (btn) { btn.setAttribute('aria-pressed', 'false'); });
        updateAnnotationUi();
    }

    annotationToolButtons.forEach(function (btn) {
        btn.addEventListener('click', function () { setActiveTool(btn.dataset.tool); });
    });
    if (deleteBtn) deleteBtn.addEventListener('click', function () {
        if (selectedAnnotation) removeAnnotation(selectedAnnotation.pageNum, selectedAnnotation.id);
    });
    if (undoBtn) undoBtn.addEventListener('click', undo);
    if (redoBtn) redoBtn.addEventListener('click', redo);
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && activeTool) { setActiveTool(activeTool); }
    });
    window.addEventListener('beforeunload', function (e) {
        if (hasAnyAnnotations()) { e.preventDefault(); e.returnValue = ''; }
    });

    // -------- Mount / unmount -------------------------------------------
    // CLAUDE-P40-VW7A-QA2: a real-browser check reported the header
    // controls never appearing, with no visible cause - this mount()
    // used to fail SILENTLY (a console.error only) whenever loadPdfJs()/
    // getDocument() rejected for any reason, leaving both the canvas
    // container and the top-menu controls simply blank with no signal
    // to act on. Failure is now VISIBLE in the canvas container itself -
    // "do not render inactive placeholders... report the exact
    // technical boundary" applies just as much to an unexplained blank
    // box as to a decorative dead button.
    function showLoadError(canvasContainer, err) {
        canvasContainer.textContent = '';
        var msg = document.createElement('p');
        msg.className = 'document-viewer-load-error';
        msg.textContent = 'This PDF could not be opened in the viewer' + (err && err.message ? ': ' + err.message : '.');
        canvasContainer.appendChild(msg);
        if (window.console) console.error('PDF viewer failed to load', err);
    }

    function mount(url, canvasContainer, downloadFilename, sourceId) {
        currentSourceId = sourceId || null;
        currentCanvasContainer = canvasContainer;
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
            // CLAUDE-P40-VW7B-QA1: getDocument() requires an object
            // with a `url` property in this vendored build (6.2.108) -
            // it does NOT normalize a bare string into {url: ...} the
            // way some PDF.js versions/docs suggest (confirmed by
            // reading the shipped, minified source directly rather
            // than assuming: getDocument(t={}) immediately reads
            // t.url, which is undefined for a plain string - the exact
            // "getDocument - expected either `data`, `range`, or `url`
            // parameter" throw a real-browser check reported for every
            // PDF, universally, not a document-specific defect).
            return pdfjsLib.getDocument({ url: url }).promise;
        }).then(function (doc) {
            pdfDoc = doc;
            thumbnailsOnlyMode = false;
            // CLAUDE-P40-LTH1: a REAL Document is actually mounted here -
            // this becomes the new "last governed Document context" for
            // this Project, read back by mountRememberedThumbnailsIfAny()
            // the next time this reviewer lands on a page with no
            // Document of its own selected (Overview, an Investigation,
            // Chat, ...).
            rememberLastPdfSource(currentSourceId);
            var saved = loadViewState(currentSourceId);
            var hasSavedPage = saved && typeof saved.page === 'number' && saved.page >= 1 && saved.page <= doc.numPages;
            currentPage = hasSavedPage ? saved.page : 1;
            currentRotation = (saved && typeof saved.rotation === 'number') ? saved.rotation : 0;
            mirrorH = !!(saved && saved.mirrorH);
            mirrorV = !!(saved && saved.mirrorV);
            currentSheetUnit = null;
            if (regionStatusEl) regionStatusEl.textContent = '';
            applyMirrorTransform();
            updateOrientationStatus();
            pageTextCache = {};
            searchMatches = [];
            searchMatchIndex = -1;
            // Section 6: "search position/query where safe and
            // appropriate" - the QUERY TEXT is restored (visibly, in the
            // field) but a saved query is deliberately NOT auto-re-run
            // here: runSearch() jumps to its first match, which could
            // silently override the just-restored page/scroll position
            // if the reviewer had since scrolled past that match - the
            // unsafe half of "safe and appropriate." Re-running search
            // remains one click/Enter away, with the query already typed.
            searchInput.value = (saved && saved.searchQuery) || '';
            pageTotal.textContent = String(pdfDoc.numPages);
            downloadLink.href = url;
            if (downloadFilename) downloadLink.setAttribute('download', downloadFilename);
            updateSearchUi();
            showControls();
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
        thumbnailsOnlyMode = false;
        mirrorH = false;
        mirrorV = false;
        currentSheetUnit = null;
        regionDrag = null;
        if (regionStatusEl) regionStatusEl.textContent = '';
        hideControls();
        clearThumbnails();
        resetAnnotationState();
    }

    // -------- Event wiring ------------------------------------------------
    prevBtn.addEventListener('click', function () { goToPage(currentPage - 1); });
    nextBtn.addEventListener('click', function () { goToPage(currentPage + 1); });
    pageInput.addEventListener('change', function () {
        var n = parseInt(pageInput.value, 10);
        if (!isNaN(n)) goToPage(n); else pageInput.value = String(currentPage);
    });
    zoomOutBtn.addEventListener('click', function () { setZoom(currentZoom - 0.1); });
    zoomInBtn.addEventListener('click', function () { setZoom(currentZoom + 0.1); });
    fitWidthBtn.addEventListener('click', fitWidth);
    fitPageBtn.addEventListener('click', fitPage);
    rotateBtn.addEventListener('click', rotate);
    if (mirrorHBtn) mirrorHBtn.addEventListener('click', mirrorHorizontal);
    if (mirrorVBtn) mirrorVBtn.addEventListener('click', mirrorVertical);
    if (resetOrientationBtn) resetOrientationBtn.addEventListener('click', resetOrientation);
    searchInput.addEventListener('input', function () {
        window.clearTimeout(searchDebounce);
        searchDebounce = window.setTimeout(function () { runSearch(searchInput.value); }, 300);
    });
    searchInput.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        if (searchMatches.length) searchStep(e.shiftKey ? -1 : 1);
        else runSearch(searchInput.value);
    });
    searchPrevBtn.addEventListener('click', function () { searchStep(-1); });
    searchNextBtn.addEventListener('click', function () { searchStep(1); });
    printBtn.addEventListener('click', function () {
        // A real, functional Print: opens the original PDF (native
        // browser PDF chrome, which DOES support print/save on its
        // own) in a new tab - genuinely simpler and more reliable than
        // re-implementing print pagination for a canvas-rendered page,
        // and never leaves the reviewer without a working Print action.
        if (downloadLink.href) window.open(downloadLink.href, '_blank');
    });

    window.ArchioskPdfViewer = { mount: mount, unmount: unmount };

    // CLAUDE-P40-DTAB1, Section 6: the debounced saveViewStateSoon()
    // (400ms) is enough for ordinary use, but a fast tab click right
    // after a zoom/rotate/page change could otherwise navigate away
    // before that timer fires - flush synchronously on the way out so
    // no state is silently lost on a quick tab switch.
    window.addEventListener('pagehide', saveViewStateNow);

    // -------- Auto-mount ---------------------------------------------
    // Self-contained, like every other IIFE in this app's static/js/
    // files (case_workspace.js's own setUpConversationTagsAndTasks etc.
    // each check `if (!element) return` at the top rather than relying
    // on inline per-page script ordering) - checks for the canvas
    // container templates/case_workspace.html renders ONLY when the
    // active Source's own file_path ends in .pdf, and mounts
    // immediately if present. No inline per-page <script> needed, and
    // no dependency on this file loading before/after any other one -
    // this is a full-page-reload app (no client-side routing), so
    // "the active document changes" always means a fresh page load,
    // which always re-runs this exact check fresh.
    var autoMountEl = document.getElementById('document-viewer-pdf-canvas');
    if (autoMountEl && autoMountEl.dataset.pdfUrl) {
        mount(autoMountEl.dataset.pdfUrl, autoMountEl, autoMountEl.dataset.pdfFilename || '', autoMountEl.dataset.sourceId || '');
    } else {
        // CLAUDE-P40-LTH1: no PDF is mounted on THIS page. If a Document
        // of SOME kind is still the active Display selection (a drawing/
        // DOCX/TXT Source - #document-tab-strip's own data-selected-
        // source-id, the same signal document_tabs.js already reads),
        // that Document genuinely has no pages of its own - the pane's
        // default empty state is correct and stays as-is, and the
        // remembered PDF (if any) is deliberately left untouched rather
        // than shown, since it no longer describes what is actually on
        // screen. Only with NO Document selected at all (Overview, an
        // Investigation, Chat, or no Project open) does a remembered
        // Document genuinely apply.
        var stripElForThumbnails = document.getElementById('document-tab-strip');
        var hasActiveDocumentSelection = !!(stripElForThumbnails && stripElForThumbnails.getAttribute('data-selected-source-id'));
        if (!hasActiveDocumentSelection) {
            mountRememberedThumbnailsIfAny();
        }
    }
})();
