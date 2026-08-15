/*
 * CLAUDE-P40-EYE1 (structural scaffold) + CLAUDE-MM5 (Image, Screenshot,
 * and Camera Evidence - the real governed visual-evidence surface Section
 * 7 asks Eye to become).
 *
 * EYE1's own scope boundary is now explicitly SUPERSEDED, not merely
 * extended: paste/drop/preview/zoom/pan/fit were already real; MM5 adds
 * genuine, view-only rotate/mirror/reset on the unsaved preview (Section
 * 4/11 - a plain CSS transform, nothing persisted), a real "Save to
 * project" action (services/image_intelligence.py's own register_
 * eye_capture via the new POST .../eye-capture route), and an explicit,
 * always-visible temporary-vs-saved status (Section 7's own required
 * distinction). What EYE1 deliberately left unbuilt and MM5 does NOT
 * build either: no in-place image editing/filters, no AI interpretation
 * (Section 24's own deferrals).
 *
 * Once saved, this pane hands off to static/js/drawing_image_viewer.js
 * (MM4) rather than reimplementing rotate/mirror/region-select/citation a
 * second time - see mountSavedView below. The preview lives only in this
 * tab's own memory until saved (a data: URL held by a plain <img> plus
 * the original File object, kept for the eventual multipart upload);
 * nothing here calls fetch() before the reviewer explicitly clicks "Save
 * to project".
 */
(function () {
    'use strict';

    var dropTarget = document.getElementById('eye-drop-target');
    if (!dropTarget) return;

    var emptyState = document.getElementById('eye-drop-target-empty');
    var noteEl = document.getElementById('eye-drop-target-note');
    var canvas = document.getElementById('eye-canvas');
    var viewport = document.getElementById('eye-canvas-viewport');
    var image = document.getElementById('eye-canvas-image');
    var zoomLevelEl = document.getElementById('eye-canvas-zoom-level');
    var zoomInBtn = document.getElementById('eye-canvas-zoom-in');
    var zoomOutBtn = document.getElementById('eye-canvas-zoom-out');
    var fitBtn = document.getElementById('eye-canvas-fit');
    var actualBtn = document.getElementById('eye-canvas-actual');
    var resetBtn = document.getElementById('eye-canvas-reset');
    var removeBtn = document.getElementById('eye-canvas-remove');
    var rotateBtn = document.getElementById('eye-canvas-rotate');
    var mirrorHBtn = document.getElementById('eye-canvas-mirror-h');
    var mirrorVBtn = document.getElementById('eye-canvas-mirror-v');
    var orientationStatusEl = document.getElementById('eye-orientation-status');
    var saveStatusEl = document.getElementById('eye-save-status');
    var saveBtn = document.getElementById('eye-save-btn');
    var descriptionInput = document.getElementById('eye-save-description');
    var savedViewEl = document.getElementById('eye-saved-view');

    // -------- CLAUDE-EYE-COMPARE-01: a second real document/image ------
    var documentView = document.getElementById('eye-document-view');
    var documentLabelEl = document.getElementById('eye-document-label');
    var documentNameEl = document.getElementById('eye-document-name');
    var documentClearBtn = document.getElementById('eye-document-clear');
    var documentBodyEl = document.getElementById('eye-document-body');
    var compareBtn = document.getElementById('toolbox-compare-btn');
    var IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'];
    var compareActive = false;
    var pdfPageTask = null; // the currently-mounted Eye-side PDF document, if any

    // -------- CLAUDE-EYE-COMPARE-01: Compare toggle (Part 1/6) -----------
    // A compact, per-Project-persisted toggle - "Compare remains active...
    // until changed/cancelled," not a one-time disposable click. Lives in
    // base.html's own shared Toolbox chrome (always rendered, regardless
    // of what's selected) but its STATE and Eye's own reaction to it are
    // owned here, alongside the rest of Eye's behavior.
    function compareKey() {
        var projectId = compareBtn && compareBtn.getAttribute('data-project-id');
        return projectId ? 'beehive:panel:compare-active:' + projectId : null;
    }

    function updateEmptyStateText() {
        if (!emptyState) return;
        var eyeIsEmpty = canvas.hidden && savedViewEl.hidden && documentView.hidden;
        if (!eyeIsEmpty) return;
        emptyState.textContent = compareActive
            ? 'Choose a document to compare.'
            : 'Paste or drop an image here to preview it.';
    }

    function setCompareActive(next, persist) {
        compareActive = next;
        if (compareBtn) compareBtn.setAttribute('aria-pressed', String(next));
        if (persist !== false) {
            var key = compareKey();
            if (key) { try { window.localStorage.setItem(key, next ? 'true' : 'false'); } catch (e) { /* ignore */ } }
        }
        updateEmptyStateText();
    }

    if (compareBtn) {
        var storedCompare = null;
        try { storedCompare = window.localStorage.getItem(compareKey()); } catch (e) { /* ignore */ }
        setCompareActive(storedCompare === 'true', false);
        compareBtn.addEventListener('click', function () {
            setCompareActive(!compareActive);
        });
    }

    var currentError = null;
    var naturalWidth = 0;
    var naturalHeight = 0;
    var currentScale = 1;
    // 'fit' auto-recalculates on container resize; 'manual' (a real
    // zoom/pan the reviewer chose) does not - Section 3's own "no
    // unintended stretching" applies just as much to silently snapping
    // a deliberate zoom back to Fit as it does to actual pixel
    // distortion.
    var mode = 'fit';
    var MIN_SCALE = 0.05;
    var MAX_SCALE = 8;
    var ZOOM_STEP = 1.25;

    // -------- CLAUDE-MM5: view-only orientation state (Section 4/11) ----
    var rotation = 0;
    var mirrorH = false;
    var mirrorV = false;
    var currentFile = null; // the real File object - needed for "Save to project"
    var saving = false;

    function normalizeRotation(r) { return ((r % 360) + 360) % 360; }

    function applyOrientation() {
        var scaleX = mirrorH ? -1 : 1;
        var scaleY = mirrorV ? -1 : 1;
        image.style.transform = 'rotate(' + rotation + 'deg) scale(' + scaleX + ',' + scaleY + ')';
    }

    function updateOrientationStatus() {
        if (!orientationStatusEl) return;
        var parts = [];
        if (rotation % 360) parts.push('Rotated ' + rotation + '° clockwise');
        if (mirrorH) parts.push('mirrored horizontally');
        if (mirrorV) parts.push('mirrored vertically');
        if (!parts.length) { orientationStatusEl.textContent = ''; return; }
        var text = parts.join(' and ');
        orientationStatusEl.textContent = text.charAt(0).toUpperCase() + text.slice(1) + ' — source unchanged';
    }

    function resetOrientation() {
        rotation = 0; mirrorH = false; mirrorV = false;
        applyOrientation();
        updateOrientationStatus();
    }

    function rotateStep() {
        rotation = normalizeRotation(rotation + 90);
        applyOrientation();
        updateOrientationStatus();
    }

    function mirrorHorizontal() { mirrorH = !mirrorH; applyOrientation(); updateOrientationStatus(); }
    function mirrorVertical() { mirrorV = !mirrorV; applyOrientation(); updateOrientationStatus(); }

    // -------- CLAUDE-MM5: temporary-vs-saved status (Section 7) ---------
    function setSaveStatus(text) { if (saveStatusEl) saveStatusEl.textContent = text; }

    // Once saved, hand off to the SAME real viewer MM4 built for a
    // persisted drawing/image Source - no rotate/mirror/region-select/
    // citation logic is reimplemented here.
    function mountSavedView(sourceId, projectId) {
        canvas.hidden = true;
        savedViewEl.hidden = false;
        savedViewEl.textContent = '';
        var img = document.createElement('img');
        img.className = 'document-viewer-image';
        img.alt = 'Saved to project';
        img.dataset.sourceId = sourceId;
        img.dataset.projectId = projectId;
        img.src = '/projects/' + encodeURIComponent(projectId) + '/workspace/sources/' + encodeURIComponent(sourceId) + '/file';
        savedViewEl.appendChild(img);
        if (window.ArchioskDrawingImageViewer) window.ArchioskDrawingImageViewer.mount(img);
    }

    function saveToProject() {
        if (!currentFile || saving) return;
        var projectId = dropTarget.getAttribute('data-project-id');
        if (!projectId) { setSaveStatus('No active project - cannot save.'); return; }
        saving = true;
        if (saveBtn) saveBtn.disabled = true;
        setSaveStatus('Saving…');

        var formData = new FormData();
        formData.append('image', currentFile, currentFile.name || 'image.png');
        if (descriptionInput && descriptionInput.value.trim()) {
            formData.append('description', descriptionInput.value.trim());
        }
        fetch('/api/v1/documents/' + encodeURIComponent(projectId) + '/eye-capture', {
            method: 'POST', credentials: 'same-origin', body: formData,
        }).then(function (resp) {
            return resp.json().then(function (body) { return { ok: resp.ok, body: body }; });
        }).then(function (result) {
            saving = false;
            if (saveBtn) saveBtn.disabled = false;
            if (!result.ok) {
                setSaveStatus('Could not save: ' + (result.body.message || 'unknown error'));
                return;
            }
            setSaveStatus('Saved to the project.');
            mountSavedView(result.body.source_id, projectId);
        }).catch(function () {
            saving = false;
            if (saveBtn) saveBtn.disabled = false;
            setSaveStatus('Could not save: network error.');
        });
    }

    // -------- Zoom / fit / pan (CLAUDE-P40-EYE1, unchanged) --------------
    function clearError() {
        if (currentError) { currentError.remove(); currentError = null; }
    }

    function showError(message) {
        clearError();
        var p = document.createElement('p');
        p.className = 'eye-drop-target-error';
        p.textContent = message;
        dropTarget.appendChild(p);
        currentError = p;
    }

    function computeFitScale() {
        if (!naturalWidth || !naturalHeight || !viewport.clientWidth || !viewport.clientHeight) return 1;
        return Math.min(viewport.clientWidth / naturalWidth, viewport.clientHeight / naturalHeight);
    }

    function centerScroll() {
        if (image.offsetWidth > viewport.clientWidth) {
            viewport.scrollLeft = (image.offsetWidth - viewport.clientWidth) / 2;
        }
        if (image.offsetHeight > viewport.clientHeight) {
            viewport.scrollTop = (image.offsetHeight - viewport.clientHeight) / 2;
        }
    }

    function applyScale(scale, opts) {
        currentScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale));
        image.style.width = Math.round(naturalWidth * currentScale) + 'px';
        image.style.height = Math.round(naturalHeight * currentScale) + 'px';
        if (zoomLevelEl) zoomLevelEl.textContent = Math.round(currentScale * 100) + '%';
        if (!opts || opts.center !== false) centerScroll();
    }

    function setFit() {
        mode = 'fit';
        applyScale(computeFitScale());
    }

    function setActualSize() {
        mode = 'manual';
        applyScale(1);
    }

    function zoomBy(factor) {
        mode = 'manual';
        applyScale(currentScale * factor, { center: false });
    }

    var resizeObserver = null;
    function watchResize() {
        if (resizeObserver || typeof window.ResizeObserver !== 'function') return;
        resizeObserver = new window.ResizeObserver(function () {
            if (mode === 'fit') applyScale(computeFitScale());
        });
        resizeObserver.observe(viewport);
    }

    function showCanvas(dataUrl) {
        clearError();
        // Part 5: Eye holds exactly one of {nothing, image, document} at a
        // time - loading a new pasted/dropped image replaces a Project
        // Document that was showing, the same way it already replaced an
        // earlier pasted image.
        clearDocumentView();
        if (emptyState) emptyState.hidden = true;
        if (noteEl) noteEl.hidden = true;
        savedViewEl.hidden = true;
        canvas.hidden = false;
        resetOrientation();
        setSaveStatus('Temporary preview — not saved to the project.');

        image.onload = function () {
            naturalWidth = image.naturalWidth;
            naturalHeight = image.naturalHeight;
            setFit();
            watchResize();
        };
        image.onerror = function () {
            canvas.hidden = true;
            showError('This image could not be displayed.');
            if (emptyState) emptyState.hidden = false;
            if (noteEl) noteEl.hidden = false;
        };
        image.src = dataUrl;
    }

    function clearPreview() {
        canvas.hidden = true;
        savedViewEl.hidden = true;
        savedViewEl.textContent = '';
        image.removeAttribute('src');
        naturalWidth = 0;
        naturalHeight = 0;
        mode = 'fit';
        currentFile = null;
        resetOrientation();
        if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null; }
        if (emptyState) emptyState.hidden = false;
        if (noteEl) noteEl.hidden = false;
        clearError();
        updateEmptyStateText();
    }

    function handleFile(file) {
        if (!file || file.type.indexOf('image/') !== 0) {
            showError('Only images are supported here.');
            return;
        }
        currentFile = file;
        var reader = new FileReader();
        reader.onload = function () { showCanvas(reader.result); };
        reader.onerror = function () { showError('This image could not be read.'); };
        reader.readAsDataURL(file);
    }

    // -------- CLAUDE-EYE-COMPARE-01: a second real document/image --------
    // (Part 1/2/3): a genuine, already-registered Project Document loaded
    // as a pure working-view action - never a mutation of the governed
    // Source (Part 6/2), never a second viewer architecture invented from
    // scratch (Part 3) - PDF reuses the same vendored PDF.js engine
    // static/js/pdf_viewer.js already loads (a second, independent
    // instance of the real library, not a fake one - pdf_viewer.js's own
    // module is a Display-only singleton with one shared toolbar, so it
    // cannot itself run a second, simultaneous instance inside Eye without
    // a much larger refactor of that shared module); an unsupported format
    // gets the IDENTICAL honest fallback card case_workspace.html's own
    // Display branch already renders for the same case, not a
    // reinterpretation of it.
    var eyePdfjsLibPromise = null;
    function loadEyePdfjsLib() {
        if (!eyePdfjsLibPromise) {
            // The SAME specifier pdf_viewer.js itself imports - the
            // browser's module map caches a dynamic import() by URL, so
            // this is a second reference to the one real, already-fetched
            // module instance, not a duplicate network fetch or a forked
            // copy of the library.
            eyePdfjsLibPromise = import('/static/js/vendor/pdfjs/pdf.min.mjs').then(function (mod) {
                mod.GlobalWorkerOptions.workerSrc = '/static/js/vendor/pdfjs/pdf.worker.min.mjs';
                return mod;
            });
        }
        return eyePdfjsLibPromise;
    }

    function eyeDocumentFallbackCard(fileUrl, downloadUrl) {
        var wrap = document.createElement('div');
        wrap.className = 'document-unavailable-preview';
        var p = document.createElement('p');
        p.className = 'pane-note';
        p.textContent = "This file type isn't previewable inside ARCHIOSK yet - the document itself is safely registered and untouched.";
        wrap.appendChild(p);
        var actions = document.createElement('div');
        actions.className = 'document-unavailable-preview-actions';
        var openLink = document.createElement('a');
        openLink.className = 'btn btn-ghost';
        openLink.href = fileUrl;
        openLink.target = '_blank';
        openLink.rel = 'noopener';
        openLink.textContent = 'Open externally';
        actions.appendChild(openLink);
        var downloadLink = document.createElement('a');
        downloadLink.className = 'btn btn-ghost';
        downloadLink.href = downloadUrl;
        downloadLink.textContent = 'Download';
        actions.appendChild(downloadLink);
        wrap.appendChild(actions);
        return wrap;
    }

    function renderEyePdf(fileUrl) {
        var container = document.createElement('div');
        container.className = 'eye-document-pdf';
        var toolbar = document.createElement('div');
        toolbar.className = 'eye-document-pdf-toolbar';
        var prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'eye-canvas-btn';
        prevBtn.textContent = 'Prev';
        var pageLabel = document.createElement('span');
        pageLabel.className = 'eye-canvas-zoom-level';
        var nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'eye-canvas-btn';
        nextBtn.textContent = 'Next';
        toolbar.appendChild(prevBtn);
        toolbar.appendChild(pageLabel);
        toolbar.appendChild(nextBtn);
        var canvasEl = document.createElement('canvas');
        canvasEl.className = 'eye-document-pdf-canvas';
        container.appendChild(toolbar);
        container.appendChild(canvasEl);
        documentBodyEl.appendChild(container);

        var pdfDoc = null;
        var pageNum = 1;
        // A single mutable token, checked (never reassigned/compared-by-
        // identity) at every async continuation below - clearDocumentView
        // flips .cancelled on THIS SAME object when the reviewer clears or
        // replaces Eye's content, so an in-flight page fetch/render from a
        // document that's no longer showing can never paint a stale canvas.
        var token = { cancelled: false };

        function renderPage() {
            pdfDoc.getPage(pageNum).then(function (page) {
                if (token.cancelled) return;
                var containerWidth = container.clientWidth || 400;
                var baseViewport = page.getViewport({ scale: 1 });
                var scale = Math.max(0.1, containerWidth / baseViewport.width);
                var viewport = page.getViewport({ scale: scale });
                canvasEl.width = viewport.width;
                canvasEl.height = viewport.height;
                var ctx = canvasEl.getContext('2d');
                page.render({ canvasContext: ctx, viewport: viewport });
                pageLabel.textContent = pageNum + ' / ' + pdfDoc.numPages;
                prevBtn.disabled = pageNum <= 1;
                nextBtn.disabled = pageNum >= pdfDoc.numPages;
            });
        }

        prevBtn.addEventListener('click', function () { if (pageNum > 1) { pageNum -= 1; renderPage(); } });
        nextBtn.addEventListener('click', function () { if (pdfDoc && pageNum < pdfDoc.numPages) { pageNum += 1; renderPage(); } });

        loadEyePdfjsLib().then(function (pdfjsLib) {
            if (token.cancelled) return null;
            return pdfjsLib.getDocument({ url: fileUrl }).promise;
        }).then(function (doc) {
            if (!doc || token.cancelled) return;
            pdfDoc = doc;
            renderPage();
        }).catch(function (err) {
            if (token.cancelled) return;
            documentBodyEl.textContent = '';
            var msg = document.createElement('p');
            msg.className = 'document-viewer-load-error';
            msg.textContent = 'This PDF could not be opened in Eye' + (err && err.message ? ': ' + err.message : '.');
            documentBodyEl.appendChild(msg);
        });

        return token;
    }

    function clearDocumentView() {
        if (pdfPageTask) { pdfPageTask.cancelled = true; }
        pdfPageTask = null;
        documentView.hidden = true;
        documentBodyEl.textContent = '';
        if (documentNameEl) documentNameEl.textContent = '';
        updateEmptyStateText();
    }

    // sourceId/name/kind/projectId all come from data-* attributes already
    // server-rendered on the rail leaf (or the Document toolbox pane) -
    // this function never calls anything but the existing, already-
    // authorized GET route that serves that Source's own file, and never
    // POSTs/mutates anything.
    function loadDocument(sourceId, name, kind, projectId) {
        if (!sourceId || !projectId) return;
        clearError();
        clearPreview(); // Part 5: mutually exclusive with the image state
        if (emptyState) emptyState.hidden = true;
        if (noteEl) noteEl.hidden = true;
        documentBodyEl.textContent = '';
        if (documentNameEl) documentNameEl.textContent = name || '';
        documentView.hidden = false;

        var fileUrl = '/projects/' + encodeURIComponent(projectId) + '/workspace/sources/' + encodeURIComponent(sourceId) + '/file';
        var downloadUrl = fileUrl + '?download=1';
        var ext = (name || '').split('.').pop().toLowerCase();

        if (kind === 'drawing' || IMAGE_EXTENSIONS.indexOf(ext) !== -1) {
            var img = document.createElement('img');
            img.className = 'eye-document-image';
            img.alt = name || 'Project document';
            img.src = fileUrl;
            documentBodyEl.appendChild(img);
        } else if (ext === 'pdf') {
            pdfPageTask = renderEyePdf(fileUrl);
        } else {
            documentBodyEl.appendChild(eyeDocumentFallbackCard(fileUrl, downloadUrl));
        }
    }

    if (documentClearBtn) {
        documentClearBtn.addEventListener('click', clearDocumentView);
    }

    // Part 1: "the simplest existing application grammar that works
    // reliably... a compact Open in Eye action" - one small button per
    // rail leaf, wired here (not a new drag-and-drop payload format) so
    // it works identically with mouse and keyboard.
    Array.prototype.forEach.call(document.querySelectorAll('.eye-send-btn'), function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            loadDocument(
                btn.getAttribute('data-source-id'),
                btn.getAttribute('data-source-name'),
                btn.getAttribute('data-source-kind'),
                btn.getAttribute('data-project-id')
            );
        });
    });

    dropTarget.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropTarget.classList.add('eye-drop-target-active');
    });
    dropTarget.addEventListener('dragleave', function () {
        dropTarget.classList.remove('eye-drop-target-active');
    });
    dropTarget.addEventListener('drop', function (e) {
        e.preventDefault();
        dropTarget.classList.remove('eye-drop-target-active');
        var files = e.dataTransfer && e.dataTransfer.files;
        if (files && files.length) handleFile(files[0]);
    });
    // A real paste event, not a placeholder - scoped to this element
    // itself (tabindex="0", so click-then-paste is a real, discoverable
    // path) rather than a document-wide listener that would collide
    // with the Chat composer/search input's own paste behavior.
    dropTarget.addEventListener('paste', function (e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (var i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image/') === 0) {
                handleFile(items[i].getAsFile());
                e.preventDefault();
                return;
            }
        }
        showError('Clipboard did not contain an image.');
    });

    if (zoomInBtn) zoomInBtn.addEventListener('click', function () { zoomBy(ZOOM_STEP); });
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', function () { zoomBy(1 / ZOOM_STEP); });
    if (fitBtn) fitBtn.addEventListener('click', setFit);
    if (actualBtn) actualBtn.addEventListener('click', setActualSize);
    if (resetBtn) resetBtn.addEventListener('click', function () { setFit(); resetOrientation(); });
    if (rotateBtn) rotateBtn.addEventListener('click', rotateStep);
    if (mirrorHBtn) mirrorHBtn.addEventListener('click', mirrorHorizontal);
    if (mirrorVBtn) mirrorVBtn.addEventListener('click', mirrorVertical);
    if (saveBtn) saveBtn.addEventListener('click', saveToProject);
    if (removeBtn) removeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        clearPreview();
    });

    // Mouse-wheel/trackpad zoom "when focused" (Section 3's own explicit
    // wording) - scoped to the viewport actually having focus, not just
    // hovered, so scrolling the surrounding page near Eye never gets
    // accidentally hijacked into a zoom.
    if (viewport) {
        viewport.addEventListener('wheel', function (e) {
            if (document.activeElement !== viewport) return;
            if (!naturalWidth) return;
            e.preventDefault();
            zoomBy(e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP);
        }, { passive: false });
    }

    window.ArchioskEyePane = { clear: clearPreview, setFit: setFit };
})();
