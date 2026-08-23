/*
 * CLAUDE-DOCUMENT-RAIL-PROBE-EYE-TOOL-01, Part 3/4: PM Mark - a
 * lightweight, per-reviewer "this document interests me, keep it on my
 * review shortlist" flag, client-side only (localStorage, the SAME
 * username+Project scoping document_tabs.js's own PINNED_KEY already
 * establishes, for the identical cross-account-leakage reason - see
 * that file's own comment). It does not mean open in Main, open in
 * Eye, create a tab, archive, remove, or mutate project evidence -
 * marking many Documents while continuing to probe others must stay
 * cheap, reversible, and independent of every other row control.
 *
 * CLAUDE-DOCUMENT-RAIL-SEARCH-01, Part 1-5: the search field and the
 * Marked filter both resolve to the SAME row-visibility decision (Part
 * 5's own "Marked ON, search geotech -> marked Documents matching
 * geotech" requires them to compose, not compete) - kept in this one
 * file rather than a second file independently fighting over the same
 * `row.hidden` attribute. Filename matching only - a real, honest
 * repo-wide audit before writing this (services/bhive_parser.py,
 * services/case_workspace.py) found NO stored extracted document text
 * anywhere to search (BHiveParser.parse() extracts text once, in
 * memory, to classify requirements, then discards it - nothing persists
 * it) and no existing content-search route. Part 6's own "do not
 * fabricate full-content search for unsupported/unindexed formats" and
 * Part 9's "do not initiate a broad re-ingestion merely when typing"
 * both rule out building real content search here - #documents-search-
 * status states this limitation honestly on a zero-match search rather
 * than implying every Document's full text was checked. Folder/path
 * matching is likewise not meaningfully distinct from filename matching
 * for this rail's own Documents list today - `active_sources` (server-
 * rendered) carries no folder/path field of its own (this "Documents"
 * family is flat, unlike the separate Data Room/folder view reachable
 * via Overview's "Open Files"), so "path matching where useful" has
 * nothing further to match against here; a real Parts Yard record
 * covers the separate, larger shape/visual-search capability (Part 7).
 */
(function () {
    'use strict';

    var checkboxes = document.querySelectorAll('.pm-mark-checkbox');
    var filterBtn = document.getElementById('documents-marked-filter-btn');
    if (!checkboxes.length && !filterBtn) return;

    var stripEl = document.getElementById('document-tab-strip');
    var projectId = stripEl ? stripEl.getAttribute('data-project-id') : '';
    var usernameEl = document.querySelector('.workspace-user-name');
    var username = usernameEl ? usernameEl.textContent.trim() : 'anonymous';
    var MARKS_KEY = 'beehive:marks:' + username + ':' + projectId;
    var FILTER_KEY = 'beehive:marks-filter-active:' + username + ':' + projectId;

    // The SAME authorized, Project-scoped JSON island document_tabs.js's
    // own reconciliation already reads - never a second, separately-
    // trusted source of truth about which Sources currently exist.
    function activeSourceIds() {
        var el = document.getElementById('workspace-active-sources-data');
        if (!el) return null;
        try {
            var parsed = JSON.parse(el.textContent || '[]');
            var ids = {};
            (Array.isArray(parsed) ? parsed : []).forEach(function (s) { ids[s.id] = true; });
            return ids;
        } catch (e) {
            return null;
        }
    }

    function loadMarks() {
        try {
            var raw = window.localStorage.getItem(MARKS_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function saveMarks(ids) {
        try { window.localStorage.setItem(MARKS_KEY, JSON.stringify(ids)); } catch (e) { /* ignore */ }
    }

    // Same "revalidate on every load" precedent as document_tabs.js's
    // own pinned-tab reconciliation - a mark on a removed/foreign Source
    // can never silently persist past this load.
    var known = activeSourceIds();
    var marks = loadMarks();
    if (known) {
        var reconciled = marks.filter(function (id) { return known[id]; });
        if (reconciled.length !== marks.length) {
            marks = reconciled;
            saveMarks(marks);
        }
    }
    var markedSet = {};
    marks.forEach(function (id) { markedSet[id] = true; });

    function isMarked(id) { return !!markedSet[id]; }

    function setMarked(id, next) {
        if (next) { markedSet[id] = true; } else { delete markedSet[id]; }
        saveMarks(Object.keys(markedSet));
    }

    // CLAUDE-ICON-INTELLIGENCE-01: state-aware tooltip/label - "Mark
    // document" (inactive) / "Remove mark" (active) is the short,
    // explanatory title this pass's own Section 2 asks for; aria-label
    // keeps the fuller per-document form already established elsewhere
    // on this row (Keep/Eye), never a generic "Mark"/"Checkbox".
    function markRowName(cb) {
        var row = cb.closest('.tree-node-document');
        var nameEl = row ? row.querySelector('.tree-leaf') : null;
        return nameEl ? nameEl.textContent : '';
    }

    function syncCheckboxes() {
        Array.prototype.forEach.call(checkboxes, function (cb) {
            var marked = isMarked(cb.getAttribute('data-source-id'));
            cb.checked = marked;
            cb.title = marked ? 'Remove mark' : 'Mark document';
            cb.setAttribute('aria-label', marked
                ? ('Remove mark from ' + markRowName(cb))
                : ('Mark ' + markRowName(cb) + ' for review'));
        });
    }
    syncCheckboxes();

    // -------- Marked filter (Part 4) -------------------------------------
    var filterActive = false;
    try { filterActive = window.localStorage.getItem(FILTER_KEY) === 'true'; } catch (e) { filterActive = false; }

    // -------- Text search (CLAUDE-DOCUMENT-RAIL-SEARCH-01, Part 3-7) -----
    var searchInput = document.getElementById('documents-search-input');
    var searchStatusEl = document.getElementById('documents-search-status');
    var searchQuery = '';

    // Quoted phrases first (removed from the remainder so they aren't
    // ALSO split into bare terms), then whitespace-split bare terms -
    // Part 4/5's own "spaces default to AND, not OR" and "mixed
    // quoted-phrase + bare-term searches should also work."
    function parseQuery(raw) {
        var phrases = [];
        var remainder = raw.replace(/"([^"]+)"/g, function (m, p1) {
            var trimmed = p1.trim();
            if (trimmed) phrases.push(trimmed.toLowerCase());
            return ' ';
        });
        var terms = remainder.split(/\s+/).map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
        return { phrases: phrases, terms: terms };
    }

    function rowMatchesQuery(name, parsed) {
        var lowerName = name.toLowerCase();
        for (var i = 0; i < parsed.phrases.length; i++) {
            if (lowerName.indexOf(parsed.phrases[i]) === -1) return false;
        }
        for (var j = 0; j < parsed.terms.length; j++) {
            if (lowerName.indexOf(parsed.terms[j]) === -1) return false;
        }
        return true;
    }

    // Part 6: a cheap, honest ranking - no separate content/passage
    // signal exists to rank on (see this file's own header comment), so
    // the one real signal available (the whole query, quotes stripped,
    // appearing as one contiguous substring of the filename) floats
    // those rows above ones that only satisfy the AND-of-terms
    // requirement piecemeal. Array.prototype.sort is stable (ES2019+),
    // so ties keep their original relative order - nothing shuffles
    // unless a row is genuinely promoted.
    function isExactPhraseMatch(name, raw) {
        var flat = raw.replace(/"/g, '').trim().toLowerCase();
        if (!flat) return false;
        return name.toLowerCase().indexOf(flat) !== -1;
    }

    function applyFilter() {
        var raw = searchQuery;
        var hasQuery = !!raw.trim();
        var parsed = parseQuery(raw);
        var matchCount = 0;
        var visibleEntries = [];

        Array.prototype.forEach.call(checkboxes, function (cb) {
            var row = cb.closest('.tree-node-document');
            if (!row) return;
            var nameEl = row.querySelector('.tree-leaf');
            var name = nameEl ? nameEl.textContent : '';
            var matchesSearch = !hasQuery || rowMatchesQuery(name, parsed);
            var matchesMarked = !filterActive || isMarked(cb.getAttribute('data-source-id'));
            var visible = matchesSearch && matchesMarked;
            row.hidden = !visible;
            if (visible) {
                matchCount++;
                visibleEntries.push({ row: row, exact: hasQuery && isExactPhraseMatch(name, raw) });
            }
        });

        if (hasQuery) {
            visibleEntries.sort(function (a, b) { return (b.exact ? 1 : 0) - (a.exact ? 1 : 0); });
            visibleEntries.forEach(function (entry) { entry.row.parentNode.appendChild(entry.row); });
        }

        if (searchStatusEl) {
            if (hasQuery && matchCount === 0) {
                searchStatusEl.hidden = false;
                searchStatusEl.textContent = 'No filename matches. Document content search is not yet available.';
            } else {
                searchStatusEl.hidden = true;
                searchStatusEl.textContent = '';
            }
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', function () {
            searchQuery = searchInput.value;
            applyFilter();
        });
    }

    function setFilterActive(next) {
        filterActive = next;
        try { window.localStorage.setItem(FILTER_KEY, next ? 'true' : 'false'); } catch (e) { /* ignore */ }
        if (filterBtn) filterBtn.setAttribute('aria-pressed', String(next));
        applyFilter();
    }

    Array.prototype.forEach.call(checkboxes, function (cb) {
        // Never let a checkbox click bubble into the row's own name-
        // link/eye/tool controls - marking is deliberately independent
        // of every other row action.
        cb.addEventListener('click', function (e) { e.stopPropagation(); });
        cb.addEventListener('change', function () {
            setMarked(cb.getAttribute('data-source-id'), cb.checked);
            syncCheckboxes();
            applyFilter();
        });
    });

    if (filterBtn) {
        filterBtn.setAttribute('aria-pressed', String(filterActive));
        filterBtn.addEventListener('click', function () { setFilterActive(!filterActive); });
    }
    applyFilter();

    // -------- Image mode (CLAUDE-DOCUMENT-RAIL-SEARCH-01, Part 2/8-11) ---
    // Text and Image "share the same result list... use different input
    // surfaces" - switching modes never touches Main/Eye/Toolbox/tabs/
    // marks (Part 15), and never fabricates a result: services/image_
    // intelligence.py's own header comment ("no facial recognition, no
    // object/defect detection, no OCR over arbitrary image content...
    // never interprets what an image DEPICTS - EXIF metadata and pixel
    // dimensions only") is a real, already-established capability
    // boundary confirming no image/shape-search backend exists anywhere
    // in ARCHIOSK today - Part 10's own "do not fake it" is honored by
    // never calling a search endpoint at all here, only by preserving
    // the query image and showing the honest deferred state (governance/
    // spare-parts-yard.md carries the real capability this preserves a
    // UI path toward).
    var modeTextBtn = document.getElementById('documents-search-mode-text');
    var modeImageBtn = document.getElementById('documents-search-mode-image');
    var imageTray = document.getElementById('documents-image-search-tray');
    var imageEmptyEl = document.getElementById('documents-image-search-empty');
    var imagePreviewEl = document.getElementById('documents-image-search-preview');
    var imagePreviewImg = document.getElementById('documents-image-search-preview-img');
    var imageRunBtn = document.getElementById('documents-image-search-run');
    var imageReplaceBtn = document.getElementById('documents-image-search-replace');
    var imageClearBtn = document.getElementById('documents-image-search-clear');
    var imageCollapsedEl = document.getElementById('documents-image-search-collapsed');
    var imageCollapsedThumb = document.getElementById('documents-image-search-collapsed-thumb');
    var imageExpandBtn = document.getElementById('documents-image-search-expand');
    var imageCollapsedReplaceBtn = document.getElementById('documents-image-search-collapsed-replace');
    var imageCollapsedClearBtn = document.getElementById('documents-image-search-collapsed-clear');
    var imageStatusEl = document.getElementById('documents-image-search-status');
    // CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01 pilot: the one escape
    // hatch out of the honest no-match state above - never a second,
    // competing option alongside it.
    var imageOpenComposerBtn = document.getElementById('documents-image-search-open-composer');
    var imageOpenComposerForm = document.getElementById('documents-image-search-open-composer-form');
    var imageOpenComposerData = document.getElementById('documents-image-search-open-composer-data');
    var imageOpenComposerCase = document.getElementById('documents-image-search-open-composer-case');

    if (modeTextBtn && modeImageBtn && imageTray) {
        var searchMode = 'text';
        var imageDataUrl = null;
        var imageIsCollapsed = false;

        function renderSearchMode() {
            var isImage = searchMode === 'image';
            modeTextBtn.setAttribute('aria-pressed', String(!isImage));
            modeImageBtn.setAttribute('aria-pressed', String(isImage));
            if (searchInput) searchInput.hidden = isImage;
            if (!isImage) {
                imageTray.hidden = true;
                if (imageCollapsedEl) imageCollapsedEl.hidden = true;
                return;
            }
            if (imageIsCollapsed && imageDataUrl) {
                imageTray.hidden = true;
                if (imageCollapsedEl) {
                    imageCollapsedEl.hidden = false;
                    if (imageCollapsedThumb) imageCollapsedThumb.src = imageDataUrl;
                }
            } else {
                imageTray.hidden = false;
                if (imageCollapsedEl) imageCollapsedEl.hidden = true;
                var hasImage = !!imageDataUrl;
                if (imageEmptyEl) imageEmptyEl.hidden = hasImage;
                if (imagePreviewEl) imagePreviewEl.hidden = !hasImage;
                if (hasImage && imagePreviewImg) imagePreviewImg.src = imageDataUrl;
            }
        }

        function setSearchMode(next) {
            searchMode = next;
            renderSearchMode();
        }
        modeTextBtn.addEventListener('click', function () { setSearchMode('text'); });
        modeImageBtn.addEventListener('click', function () { setSearchMode('image'); });

        function loadImageFile(file) {
            if (!file || file.type.indexOf('image/') !== 0) return;
            var reader = new FileReader();
            reader.onload = function () {
                imageDataUrl = reader.result;
                imageIsCollapsed = false;
                if (imageStatusEl) imageStatusEl.hidden = true;
                renderSearchMode();
            };
            reader.readAsDataURL(file);
        }

        // CLAUDE-MOBILE-CAPTURE-01: the camera/gallery path. Feeds the exact
        // same loadImageFile() as paste and drop, so a photo taken on a phone
        // is handled identically to one pasted on a desktop - one code path,
        // no mobile-only behaviour. The input is reset after each pick so
        // choosing the same file twice still fires `change`.
        var imageFileInput = document.getElementById('documents-image-search-file');
        if (imageFileInput) {
            imageFileInput.addEventListener('change', function () {
                var files = imageFileInput.files;
                if (files && files.length) loadImageFile(files[0]);
                imageFileInput.value = '';
            });
        }

        imageTray.addEventListener('dragover', function (e) { e.preventDefault(); });
        imageTray.addEventListener('drop', function (e) {
            e.preventDefault();
            var files = e.dataTransfer && e.dataTransfer.files;
            if (files && files.length) loadImageFile(files[0]);
        });
        // Scoped to the tray itself (tabindex="0", click-then-paste is a
        // real, discoverable path) - the same idiom eye_pane.js's own
        // paste handler already established for Eye's drop target.
        imageTray.addEventListener('paste', function (e) {
            var items = e.clipboardData && e.clipboardData.items;
            if (!items) return;
            for (var i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image/') === 0) {
                    loadImageFile(items[i].getAsFile());
                    e.preventDefault();
                    return;
                }
            }
        });

        function clearImageQuery() {
            imageDataUrl = null;
            imageIsCollapsed = false;
            if (imageStatusEl) imageStatusEl.hidden = true;
            renderSearchMode();
        }
        function replaceImageQuery() {
            imageDataUrl = null;
            imageIsCollapsed = false;
            if (imageStatusEl) imageStatusEl.hidden = true;
            renderSearchMode();
            imageTray.focus();
        }

        if (imageClearBtn) imageClearBtn.addEventListener('click', clearImageQuery);
        if (imageCollapsedClearBtn) imageCollapsedClearBtn.addEventListener('click', clearImageQuery);
        if (imageReplaceBtn) imageReplaceBtn.addEventListener('click', replaceImageQuery);
        if (imageCollapsedReplaceBtn) imageCollapsedReplaceBtn.addEventListener('click', replaceImageQuery);
        if (imageExpandBtn) imageExpandBtn.addEventListener('click', function () { imageIsCollapsed = false; renderSearchMode(); });

        // Part 9: "once submitted, allow the large tray to collapse...
        // the PM must not have to recreate the image merely because the
        // tray collapsed" - collapsing preserves imageDataUrl untouched.
        // Part 10: no real search call - the honest deferred state is
        // the entire "result."
        if (imageRunBtn) {
            imageRunBtn.addEventListener('click', function () {
                if (!imageDataUrl) return;
                imageIsCollapsed = true;
                renderSearchMode();
                if (imageStatusEl) imageStatusEl.hidden = false;
            });
        }

        // CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01 pilot: passes the
        // still-only-client-side imageDataUrl (never uploaded/persisted
        // anywhere by this file) into ONE bounded Composer turn - see
        // routes/workspace.py's open_image_in_composer. The current Case,
        // if one is open, is read from the URL exactly the way every
        // other read-only "what page is this" signal in this app is
        // read - never trusted as an authorization boundary, only a soft
        // display/routing hint (same discipline as the Composer hotlink
        // origin-pointer pilot, ?case= there too).
        if (imageOpenComposerBtn && imageOpenComposerForm && imageOpenComposerData) {
            imageOpenComposerBtn.addEventListener('click', function () {
                if (!imageDataUrl) return;
                imageOpenComposerData.value = imageDataUrl;
                if (imageOpenComposerCase) {
                    var params = new URLSearchParams(window.location.search);
                    imageOpenComposerCase.value = params.get('case') || '';
                }
                imageOpenComposerForm.submit();
            });
        }

        renderSearchMode();
    }

    // Exposed for RAIL-SEARCH-01's own upcoming "Marked + search
    // coexist" requirement - a read-only lookup, never a second write
    // path for mark state.
    window.ArchioskDocumentMarks = { isMarked: isMarked, isFilterActive: function () { return filterActive; } };
})();
