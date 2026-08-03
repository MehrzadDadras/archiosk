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
    var renderTask = null;
    var pageTextCache = {};
    var searchMatches = [];
    var searchMatchIndex = -1;
    var searchDebounce = null;

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
    }

    function renderPage() {
        if (!pdfDoc || !canvas) return Promise.resolve();
        return pdfDoc.getPage(currentPage).then(function (page) {
            var viewport = page.getViewport({ scale: currentZoom, rotation: currentRotation });
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            var ctx = canvas.getContext('2d');
            if (renderTask) { try { renderTask.cancel(); } catch (e) { /* ignore - a newer render superseded it */ } }
            renderTask = page.render({ canvasContext: ctx, viewport: viewport });
            return renderTask.promise.then(function () { updateNavState(); });
        });
    }

    function goToPage(n) {
        if (!pdfDoc) return;
        n = Math.max(1, Math.min(pdfDoc.numPages, n));
        if (n === currentPage) { updateNavState(); return; }
        currentPage = n;
        renderPage();
    }

    function setZoom(z) {
        currentZoom = Math.max(0.25, Math.min(4, z));
        renderPage();
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
        });
    }

    function searchStep(delta) {
        if (!searchMatches.length) return;
        searchMatchIndex = (searchMatchIndex + delta + searchMatches.length) % searchMatches.length;
        goToPage(searchMatches[searchMatchIndex].page);
        updateSearchUi();
    }

    // -------- Mount / unmount -------------------------------------------
    function mount(url, canvasContainer, downloadFilename) {
        return loadPdfJs().then(function () {
            canvas = document.createElement('canvas');
            canvas.className = 'document-viewer-canvas';
            canvasContainer.textContent = '';
            canvasContainer.appendChild(canvas);
            return pdfjsLib.getDocument(url).promise;
        }).then(function (doc) {
            pdfDoc = doc;
            currentPage = 1;
            currentZoom = 1.0;
            currentRotation = 0;
            pageTextCache = {};
            searchMatches = [];
            searchMatchIndex = -1;
            searchInput.value = '';
            pageTotal.textContent = String(pdfDoc.numPages);
            downloadLink.href = url;
            if (downloadFilename) downloadLink.setAttribute('download', downloadFilename);
            updateSearchUi();
            showControls();
            return fitWidth();
        }).catch(function (err) {
            hideControls();
            // eslint-disable-next-line no-console
            if (window.console) console.error('PDF viewer failed to load', err);
        });
    }

    function unmount() {
        pdfDoc = null;
        canvas = null;
        hideControls();
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
        mount(autoMountEl.dataset.pdfUrl, autoMountEl, autoMountEl.dataset.pdfFilename || '');
    }
})();
