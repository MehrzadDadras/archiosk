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
    var overlayCanvas = null;
    var pageWrap = null;
    var currentViewport = null;

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
        if (window.ArchioskListsThumbnailsSplit) window.ArchioskListsThumbnailsSplit.hide();
    }

    function buildThumbnails() {
        clearThumbnails();
        if (!thumbnailsList || !pdfDoc) return;
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
            row.addEventListener('click', function () { goToPage(parseInt(this.dataset.page, 10)); });
            thumbnailsList.appendChild(row);
            thumbnailRows.push(row);
            if (thumbnailObserver) thumbnailObserver.observe(row);
            else renderThumbnail(n);
        }
        if (window.ArchioskListsThumbnailsSplit) window.ArchioskListsThumbnailsSplit.show();
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

    var annotationToolButtons = [];
    ['doc-annotate-text', 'doc-annotate-highlight', 'doc-annotate-ink', 'doc-annotate-select'].forEach(function (id) {
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
        var pt = canvasPointFromEvent(e);
        var pdfPt = currentViewport.convertToPdfPoint(pt.x, pt.y);
        if (activeTool === 'ink') {
            inkDrawing = { points: [{ x: pdfPt[0], y: pdfPt[1] }] };
            try { overlayCanvas.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
        } else if (activeTool === 'highlight') {
            highlightDrag = { x1: pdfPt[0], y1: pdfPt[1], x2: pdfPt[0], y2: pdfPt[1] };
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
        if (!currentViewport || (!inkDrawing && !highlightDrag)) return;
        var pt = canvasPointFromEvent(e);
        var pdfPt = currentViewport.convertToPdfPoint(pt.x, pt.y);
        if (inkDrawing) {
            inkDrawing.points.push({ x: pdfPt[0], y: pdfPt[1] });
        } else if (highlightDrag) {
            highlightDrag.x2 = pdfPt[0];
            highlightDrag.y2 = pdfPt[1];
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
        redrawAnnotations();
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

    function mount(url, canvasContainer, downloadFilename) {
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
            resetAnnotationState();
            buildThumbnails();
            return fitWidth();
        }).catch(function (err) {
            hideControls();
            resetAnnotationState();
            clearThumbnails();
            showLoadError(canvasContainer, err);
        });
    }

    function unmount() {
        pdfDoc = null;
        canvas = null;
        overlayCanvas = null;
        pageWrap = null;
        currentViewport = null;
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
