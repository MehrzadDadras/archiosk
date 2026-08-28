/* ============================================================
   CLAUDE-CALM-LAKE-SURFACE-PROTOTYPE-01 - calm_lake.js

   Behaviour for the Calm Lake structural wireframe ONLY. Loaded by
   exactly one template. It shares no state, no globals and no selectors
   with pdf_viewer.js, case_workspace.js or anything else in static/js/,
   deliberately: this is an experiment about surface behaviour, and
   coupling it to a shipping viewer would make it expensive to delete.

   IT IMPLEMENTS THE LOOK VERB, WHICH IS THE POINT.

   The grammar's 5.3 is a hard sequencing constraint, not a preference:
   pdf_viewer.js resolves 30 document controls by getElementById against
   base.html's menu bar, so a meaningful share of the "51% permanent
   chrome" is the IMPLEMENTATION of Look, not accretion. Reducing chrome
   before a canvas-native Look vocabulary exists deletes navigation and
   leaves a drawing nobody can move. This file builds one - pan, zoom,
   fit, and document switching without a rail - to show the vocabulary
   is constructible. It does not license deleting chrome anywhere else.

   FOUR VERBS, ONE HANDLER TABLE. Look / Point / Ask / Commit are
   dispatched from VERBS below at every viewport. There is no branch on
   width anywhere in this file, and there must not be one: if a verb
   behaved differently at 390px than at 1600px, the single-grammar claim
   would be false in the one place hardest to notice.

   ONE SUMMONED SHEET AT A TIME, enforced in showOnly(). Two overlapping
   sheets is how a calm surface becomes competing permanent panes again,
   which main.css's own phone breakpoint already rejected in writing.
   The cost is real and accepted: you cannot read the Why sheet and the
   Composer side by side. If that is the wrong call, showOnly() is the
   one function to change.
   ============================================================ */
(function () {
    "use strict";

    var body = document.body;
    var lake = document.getElementById("cl-lake");
    var plan = document.getElementById("cl-plan");
    if (!lake || !plan) { return; }

    /* --------------------------------------------------------
       Proportions and positions arrive as data-* attributes and are
       applied through the CSSOM. They are NOT emitted as inline style
       attributes: app.py's CSP sets default-src 'self' with no
       style-src directive, so a parsed style attribute is refused.
       Setting element.style from a nonce-approved script is unaffected.
       -------------------------------------------------------- */
    Array.prototype.forEach.call(plan.querySelectorAll(".cl-mark"), function (mark) {
        mark.style.setProperty("--w-mark-x", mark.getAttribute("data-x") + "%");
        mark.style.setProperty("--w-mark-y", mark.getAttribute("data-y") + "%");
    });

    Array.prototype.forEach.call(document.querySelectorAll(".cl-halflife"), function (bar) {
        var spent = bar.getAttribute("data-spent");
        if (spent && spent !== "None") {
            bar.style.setProperty("--w-spent", spent + "%");
        }
    });

    /* ========================================================
       LOOK - pan, zoom, fit
       ======================================================== */

    var view = { x: 0, y: 0, scale: 1 };
    var MIN_SCALE = 0.4;
    var MAX_SCALE = 4;

    function applyView() {
        plan.style.setProperty("--w-tx", view.x + "px");
        plan.style.setProperty("--w-ty", view.y + "px");
        plan.style.setProperty("--w-scale", view.scale);
        /* LOD INVARIANCE. Marks are annotations ABOUT the drawing, not
           content of it, so they counter-scale and stay legible at every
           zoom. The grammar's 6.3 requires exactly this: annotation
           density may thin as a drawing zooms out, but the route to a
           finding's basis must not - a finding that becomes uncitable at
           overview zoom is uncitable precisely when a reader is forming a
           summary judgement. */
        plan.style.setProperty("--w-inv", 1 / view.scale);
    }

    function zoomBy(factor) {
        view.scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale * factor));
        readerAdjustedView = true;
        applyView();
        wakeLook();
    }

    /* PLAN_W/PLAN_H are the .cl-plan box in CSS pixels, which is also the
       SVG's own viewBox. Kept as constants rather than measured, because
       measuring the element we are about to scale reads back the previous
       scale and fit() would drift on every call. */
    var PLAN_W = 1000;
    var PLAN_H = 700;
    var FIT_MARGIN = 0.92;

    /* A real fit, not scale = 1.

       Getting this wrong is not cosmetic at 390px: the sheet is 1000 CSS
       pixels wide, so an unfitted surface opens showing roughly a third of
       one room and no title block, and a reader cannot tell whether they are
       looking at the whole drawing or a corner of it. On a surface whose
       entire claim is "the drawing occupies the screen", opening zoomed into
       an unlabelled fragment falsifies the claim on arrival. */
    function fit() {
        var box = lake.getBoundingClientRect();
        var scale = 1;
        if (box.width && box.height) {
            scale = Math.min(box.width / PLAN_W, box.height / PLAN_H) * FIT_MARGIN;
            scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
        }
        view.x = 0;
        view.y = 0;
        view.scale = scale;
        readerAdjustedView = false;
        applyView();
        wakeLook();
    }

    /* Re-fit when the surface changes size, unless the reader has taken
       control of the view themselves - refitting under someone who has
       deliberately zoomed in would throw away their position. This is
       element geometry, not a viewport branch: the grammar does not change,
       only how much of the sheet is in frame. */
    var readerAdjustedView = false;

    var refitTimer = null;
    window.addEventListener("resize", function () {
        if (readerAdjustedView) { return; }
        window.clearTimeout(refitTimer);
        refitTimer = window.setTimeout(fit, 120);
    });

    var dragging = false;
    var moved = false;
    var dragStart = null;

    lake.addEventListener("pointerdown", function (event) {
        /* A press on a mark is Point, not Look. */
        if (event.target.closest(".cl-mark, .cl-look, .cl-selection")) { return; }
        dragging = true;
        moved = false;
        dragStart = { x: event.clientX - view.x, y: event.clientY - view.y };
        lake.classList.add("is-panning");
        plan.classList.add("is-dragging");
        try { lake.setPointerCapture(event.pointerId); } catch (e) { /* not capturable */ }
    });

    lake.addEventListener("pointermove", function (event) {
        wakeLook();
        if (!dragging || !dragStart) { return; }
        moved = true;
        readerAdjustedView = true;
        view.x = event.clientX - dragStart.x;
        view.y = event.clientY - dragStart.y;
        applyView();
    });

    function endDrag() {
        dragging = false;
        dragStart = null;
        lake.classList.remove("is-panning");
        plan.classList.remove("is-dragging");
    }

    lake.addEventListener("pointerup", endDrag);
    lake.addEventListener("pointercancel", endDrag);

    lake.addEventListener("wheel", function (event) {
        event.preventDefault();
        zoomBy(event.deltaY < 0 ? 1.12 : 1 / 1.12);
    }, { passive: false });

    /* Double-tap to fit - the gesture 5.3 names, and the reason there is
       no persistent fit control in a menu bar anywhere on this surface. */
    lake.addEventListener("dblclick", function (event) {
        if (event.target.closest(".cl-mark")) { return; }
        fit();
    });

    Array.prototype.forEach.call(document.querySelectorAll(".cl-look-btn"), function (btn) {
        btn.addEventListener("click", function () {
            var what = btn.getAttribute("data-look");
            if (what === "in") { zoomBy(1.25); }
            else if (what === "out") { zoomBy(1 / 1.25); }
            else { fit(); }
        });
    });

    fit();

    /* The Look affordances recede when idle - the games-HUD pattern, not
       a permanent readout. This is the mechanism that lets the surface be
       navigable without being chromed, and it is the single behaviour
       most worth judging visually: "how long is calm" is not a question
       prose can answer. */
    var look = document.getElementById("cl-look");
    var RECEDE_AFTER = 2200;
    var recedeTimer = null;

    function wakeLook() {
        if (!look) { return; }
        look.classList.add("is-awake");
        window.clearTimeout(recedeTimer);
        recedeTimer = window.setTimeout(function () {
            look.classList.remove("is-awake");
        }, RECEDE_AFTER);
    }

    wakeLook();   /* announce the vocabulary once, then recede */

    /* ========================================================
       SHEETS - one at a time
       ======================================================== */

    var index = document.getElementById("cl-index");
    var depth = document.getElementById("cl-depth");
    var composer = document.getElementById("cl-composer");
    var instrument = document.getElementById("cl-instrument");
    var scrim = document.getElementById("cl-scrim");

    var sheets = [index, depth, composer, instrument];

    function showOnly(target) {
        sheets.forEach(function (sheet) {
            if (sheet) { sheet.hidden = (sheet !== target); }
        });
        if (scrim) { scrim.hidden = !target; }
        body.setAttribute("data-state", target ? (target.id || "sheet") : (disturbed ? "disturbed" : "base"));
        syncVerbs();
    }

    function dismiss() { showOnly(null); }

    var disturbed = !!document.querySelector(".cl-disturbance");
    body.setAttribute("data-state", disturbed ? "disturbed" : "base");

    Array.prototype.forEach.call(document.querySelectorAll("[data-dismiss]"), function (btn) {
        btn.addEventListener("click", dismiss);
    });

    if (scrim) { scrim.addEventListener("click", dismiss); }

    /* One key, one meaning, at every viewport. */
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") { dismiss(); }
    });

    /* ========================================================
       POINT - selection, and the depth sheet

       Selection supplies CONTEXT and never authorization. Pointing sets
       what Ask and Commit are about; it does not grant permission to
       act, and Commit's own gate is what grants that.
       ======================================================== */

    var selectionBar = document.getElementById("cl-selection");
    var selectionTag = document.getElementById("cl-selection-tag");
    var boundSelection = document.getElementById("cl-bound-selection");
    var verbReason = document.getElementById("cl-verb-reason");
    var selected = null;

    function setSelection(id, tag) {
        selected = id ? { id: id, tag: tag } : null;

        Array.prototype.forEach.call(document.querySelectorAll(".cl-mark"), function (mark) {
            mark.classList.toggle("is-selected", !!id && mark.getAttribute("data-finding") === id);
        });

        if (selectionBar) { selectionBar.hidden = !id; }
        if (selectionTag && id) { selectionTag.textContent = tag; }

        if (boundSelection) {
            boundSelection.hidden = !id;
            if (id) { boundSelection.textContent = tag; }
        }

        syncVerbs();
    }

    function openDepth(id) {
        if (!depth) { return; }
        var found = false;
        Array.prototype.forEach.call(depth.querySelectorAll(".cl-finding"), function (card) {
            var match = (card.id === "finding-" + id);
            card.hidden = !match;
            if (match) { found = true; }
        });
        if (!found) { return; }
        showOnly(depth);
        depth.scrollTop = 0;
    }

    /* Every route into depth goes through openDepth(), so there is
       exactly one way a claim can be shown and it always carries its
       verification badge and its basis with it. */
    Array.prototype.forEach.call(document.querySelectorAll(".cl-mark"), function (mark) {
        mark.addEventListener("click", function (event) {
            event.stopPropagation();
            var id = mark.getAttribute("data-finding");
            setSelection(id, mark.getAttribute("data-tag"));
            openDepth(id);
        });
    });

    Array.prototype.forEach.call(document.querySelectorAll("[data-open-finding]"), function (btn) {
        btn.addEventListener("click", function () {
            var id = btn.getAttribute("data-open-finding");
            var mark = document.querySelector('.cl-mark[data-finding="' + id + '"]');
            setSelection(id, mark ? mark.getAttribute("data-tag") : id);
            openDepth(id);
        });
    });

    var clearBtn = document.getElementById("cl-selection-clear");
    if (clearBtn) {
        clearBtn.addEventListener("click", function () { setSelection(null, null); });
    }

    /* SHOW ON DRAWING - depth returning to the object. Dismisses the
       sheet, because the answer to "where is it" is the drawing, not a
       panel sitting on top of the drawing. */
    Array.prototype.forEach.call(document.querySelectorAll("[data-show]"), function (btn) {
        btn.addEventListener("click", function () {
            var id = btn.getAttribute("data-show");
            var mark = document.getElementById("mark-" + id);
            dismiss();
            fit();
            if (!mark) { return; }
            setSelection(id, mark.getAttribute("data-tag"));
            mark.classList.remove("is-shown");
            void mark.offsetWidth;          /* restart the one-shot pulse */
            mark.classList.add("is-shown");
        });
    });

    /* ========================================================
       LOOK - document switching without a rail
       ======================================================== */

    var docSwitch = document.getElementById("cl-doc-switch");
    if (docSwitch) {
        docSwitch.addEventListener("click", function () {
            showOnly(index && index.hidden ? index : null);
        });
    }

    Array.prototype.forEach.call(document.querySelectorAll(".cl-index-item"), function (item) {
        item.addEventListener("click", function () {
            Array.prototype.forEach.call(document.querySelectorAll(".cl-index-item"), function (other) {
                other.classList.remove("is-current");
            });
            item.classList.add("is-current");

            var name = item.querySelector(".cl-index-name");
            var sheetCount = item.querySelector(".cl-index-sheets");
            var activeName = document.getElementById("cl-active-doc-name");
            var activeIndex = document.getElementById("cl-active-doc-index");
            var boundDoc = document.getElementById("cl-bound-doc");

            if (activeName && name) { activeName.textContent = name.textContent; }
            if (activeIndex && sheetCount) {
                activeIndex.textContent = "1 of " + sheetCount.textContent.split(" ")[0];
            }
            if (boundDoc && name) { boundDoc.textContent = name.textContent; }

            dismiss();
            fit();
        });
    });

    /* ========================================================
       THE VERB BAR - one table, no width branch
       ======================================================== */

    var VERBS = {
        look: function () {
            /* Look is not a mode. It wakes the affordances and offers the
               only Look action a phone cannot express by gesture alone -
               changing document. */
            wakeLook();
            showOnly(index && index.hidden ? index : null);
        },
        point: function () {
            /* Point with something already selected reopens its depth.
               Point with nothing selected says what to do, rather than
               silently doing nothing. */
            if (selected) { openDepth(selected.id); return; }
            dismiss();
            flashReason("Point at an object on the drawing.");
        },
        ask: function () {
            showOnly(composer && composer.hidden ? composer : null);
            if (composer && !composer.hidden) {
                var field = document.getElementById("cl-ask-field");
                if (field) { field.focus(); }
            }
        },
        commit: function () {
            if (!selected) { return; }
            openDepth(selected.id);
            var btn = document.querySelector('[data-commit="' + selected.id + '"]');
            if (btn) { btn.focus(); }
        }
    };

    var verbButtons = Array.prototype.slice.call(document.querySelectorAll("[data-verb]"));

    verbButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var fn = VERBS[btn.getAttribute("data-verb")];
            if (fn) { fn(); }
        });
    });

    function syncVerbs() {
        var openSheet = sheets.filter(function (s) { return s && !s.hidden; })[0] || null;

        verbButtons.forEach(function (btn) {
            var verb = btn.getAttribute("data-verb");
            var active =
                (verb === "look" && openSheet === index) ||
                (verb === "ask" && openSheet === composer) ||
                (verb === "point" && openSheet === depth);
            btn.setAttribute("aria-pressed", active ? "true" : "false");
        });

        var commit = document.getElementById("cl-verb-commit");
        if (commit) {
            commit.disabled = !selected;
            commit.setAttribute("aria-disabled", selected ? "false" : "true");
        }

        if (verbReason && !reasonHeld) {
            if (selected) {
                verbReason.textContent =
                    "Ask and Commit are about " + selected.tag +
                    ". Selection supplies context, not authorization.";
            } else {
                verbReason.textContent = "Commit needs a selection. Point at something first.";
            }
        }
    }

    var reasonHeld = false;
    var reasonTimer = null;

    function flashReason(text) {
        if (!verbReason) { return; }
        reasonHeld = true;
        verbReason.textContent = text;
        window.clearTimeout(reasonTimer);
        reasonTimer = window.setTimeout(function () {
            reasonHeld = false;
            syncVerbs();
        }, 2600);
    }

    /* ========================================================
       COMMIT stays effortful

       The prototype does not perform the action. It shows that the
       action HAS a gate and that the gate is where the friction lives.
       Calm applies to understanding; friction at the approval gate is a
       feature, not a defect to smooth away.
       ======================================================== */
    Array.prototype.forEach.call(document.querySelectorAll("[data-commit]"), function (btn) {
        btn.addEventListener("click", function () {
            var note = btn.parentNode.querySelector(".cl-commit-note");
            if (note) {
                note.textContent =
                    "Prototype - a real Commit opens the Approval Gate here, " +
                    "attributed and confirmed, and does not complete from this click.";
            }
        });
    });

    var instrumentToggle = document.getElementById("cl-instrument-toggle");
    if (instrumentToggle) {
        instrumentToggle.addEventListener("click", function () {
            showOnly(instrument && instrument.hidden ? instrument : null);
        });
    }

    /* A press on the drawing itself dismisses. The surface is what you
       return to, so returning to it should not require finding a
       control. A press that was actually a pan does not count. */
    lake.addEventListener("click", function (event) {
        if (moved) { moved = false; return; }
        if (event.target.closest(".cl-mark, .cl-look, .cl-selection")) { return; }
        dismiss();
    });

    syncVerbs();
}());
