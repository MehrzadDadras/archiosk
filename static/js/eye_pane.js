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
