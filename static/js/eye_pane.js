/*
 * CLAUDE-P40-EYE1 - the Eye pane's own structural-scaffold interactivity.
 * Scope, stated honestly (Section 4's own explicit boundary): this is a
 * real paste/drop TARGET plus a real responsive image viewing canvas
 * (CLAUDE-P40-EYE1's own follow-up browser correction, Section 3) -
 * dragover/dragenter/drop and paste events are genuinely captured, an
 * image is genuinely read and previewed at a real, resizable scale with
 * zoom/pan/fit - but nothing beyond that. No editing, no annotation, no
 * chat/terminal attachment, no AI interpretation, no persistence, no
 * ingestion. The preview lives only in this tab's own memory (a data:
 * URL held by a plain <img>); nothing here ever calls fetch()/
 * XMLHttpRequest or writes to any Archiosk store. Deliberately not "no
 * interaction at all" (a drop target that doesn't react to a drop would
 * itself be the kind of misleading dead control Section 4 forbids) and
 * deliberately not "looks like it saves/analyzes" (which would
 * misrepresent unbuilt functionality) - display what was pasted/
 * dropped, in-session, state plainly that it is not saved, nothing more.
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
        canvas.hidden = false;

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
        image.removeAttribute('src');
        naturalWidth = 0;
        naturalHeight = 0;
        mode = 'fit';
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
    if (resetBtn) resetBtn.addEventListener('click', setFit);
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
