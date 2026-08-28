/* ============================================================
   CLAUDE-CALM-LAKE-SURFACE-PROTOTYPE-01 - calm_lake.js

   Behaviour for the Calm Lake surface. Loaded by exactly one template.
   Shares no state, no globals and no selectors with pdf_viewer.js,
   case_workspace.js or anything else in static/js/, deliberately: this
   is an experiment about surface behaviour, and coupling it to a
   shipping viewer would make it expensive to delete.

   IT IMPLEMENTS THE LOOK VERB, WHICH IS THE POINT.

   The grammar's 5.3 is a hard sequencing constraint: pdf_viewer.js
   resolves 30 document controls by getElementById against base.html's
   menu bar, so a meaningful share of the "51% permanent chrome" is the
   IMPLEMENTATION of Look, not accretion. Reducing chrome before a
   canvas-native Look vocabulary exists deletes navigation and leaves a
   drawing nobody can move. This file builds one to look at; it does not
   license deleting chrome anywhere else.

   NO VIEWPORT BRANCH ANYWHERE IN THIS FILE. There is no matchMedia, no
   innerWidth test, and no width comparison. Where behaviour must differ
   between a phone and a desktop, this file states a FACT and lets CSS
   decide the spatial consequence:

     - "a sheet is open"  -> body.is-docked. At 390px that class has no
       rule attached; at >=1024px it insets the body by the dock width.
     - "can this be swiped" -> the grab handle's own visibility, read
       from the element, because the handle is display:none where there
       is no touch gesture to afford.

   That is what keeps a single interaction grammar honest. A verb that
   behaved differently at 390px than at 1600px would falsify the claim in
   the place hardest to notice, so the claim is enforced by construction
   rather than by care.

   ONE SUMMONED SHEET AT A TIME, enforced in showOnly(). Two overlapping
   sheets is how a calm surface becomes competing permanent panes again,
   which main.css's own phone breakpoint already rejected in writing.
   ============================================================ */
(function () {
    "use strict";

    var body = document.body;
    var lake = document.getElementById("cl-lake");
    var plan = document.getElementById("cl-plan");
    if (!lake || !plan) { return; }

    /* Duration of the sheet slide and the dock inset. Kept in step with
       --w-slide in calm_lake.css; if that changes, change this. */
    var SLIDE_MS = 280;

    /* --------------------------------------------------------
       Proportions and positions arrive as data-* attributes and are
       applied through the CSSOM. They are NOT emitted as inline style
       attributes: app.py's CSP sets default-src 'self' with no
       style-src directive, so a parsed style attribute is refused.
       Setting element.style from a nonce-approved script is unaffected.
       -------------------------------------------------------- */
    /* ========================================================
       THE TWO SCENES

       Scene 1 is the entry environment; Scene 2 is the working
       surface. Only one is on the page at a time - the CSS drives
       that off body[data-scene], so this code changes ONE attribute
       and never hides anything itself.

       The opened field's territory is remembered so a return
       contracts back to the tile the person came from rather than
       dumping them at the top of an unfamiliar grid. Territory is
       already deterministic in the markup; this just re-focuses it.
       ======================================================== */

    var body = document.body;
    var openedFieldId = null;

    function showField() {
        body.setAttribute("data-scene", "field");
        /* Focus returns to the tile that was opened, not to the top of
           the document. A keyboard or screen-reader user who came from
           M-201 lands back on M-201. */
        if (openedFieldId) {
            var origin = document.getElementById("field-" + openedFieldId);
            if (origin) { origin.focus(); }
        }
    }

    function showSurface(fieldId) {
        openedFieldId = fieldId || null;
        body.setAttribute("data-scene", "surface");
        var back = document.getElementById("cl-return");
        if (back) { back.focus(); }
    }

    Array.prototype.forEach.call(document.querySelectorAll(".cl-field"), function (field) {
        field.addEventListener("click", function () {
            /* An action tile opens no surface - there is nothing behind it
               yet. Saying so is better than transitioning to an empty
               workspace and letting the person work out why it is blank. */
            if (field.getAttribute("data-action") === "true") {
                flashReason("Project intake is not built in this prototype.");
                return;
            }
            if (field.getAttribute("data-field") === "M-201") {
                showSurface("M-201");
                refitSoon(40);
                return;
            }
            flashReason("Only M-201 opens in this prototype.");
        });
    });

    var returnBtn = document.getElementById("cl-return");
    if (returnBtn) {
        returnBtn.addEventListener("click", function () {
            dismiss();
            showField();
        });
    }

    /* SCENE 1 - Page-Field pins. Same CSP-safe idiom as .cl-mark below: the
       coordinate rides on a data attribute and is written through the CSSOM,
       because app.py's CSP refuses a parsed inline style attribute.

       data-mini-x/y are ALREADY projected into the miniature's cropped
       viewBox by the route - they are not the raw sheet percentages, which
       would place the pin in the wrong room. */
    Array.prototype.forEach.call(document.querySelectorAll(".cl-field-pin"), function (pin) {
        pin.style.setProperty("--w-pin-x", pin.getAttribute("data-mini-x") + "%");
        pin.style.setProperty("--w-pin-y", pin.getAttribute("data-mini-y") + "%");
    });

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
       LOOK - pan, zoom, fit, focus
       ======================================================== */

    var PLAN_W = 1000;
    var PLAN_H = 700;
    var FIT_MARGIN = 0.96;
    var MIN_SCALE = 0.3;
    var MAX_SCALE = 4;

    var view = { x: 0, y: 0, scale: 1 };
    var readerAdjustedView = false;

    function applyView() {
        plan.style.setProperty("--w-tx", view.x + "px");
        plan.style.setProperty("--w-ty", view.y + "px");
        plan.style.setProperty("--w-scale", view.scale);
        /* LOD INVARIANCE. Pins are annotations ABOUT the drawing, not
           content of it, so they counter-scale and hold their size at
           every zoom. The grammar's 6.3 requires it: a finding that
           becomes uncitable at overview zoom is uncitable precisely when
           a reader is forming a summary judgement. */
        plan.style.setProperty("--w-inv", 1 / view.scale);
    }

    function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

    function fitScale() {
        var box = lake.getBoundingClientRect();
        if (!box.width || !box.height) { return 1; }
        return clamp(
            Math.min(box.width / PLAN_W, box.height / PLAN_H) * FIT_MARGIN,
            MIN_SCALE, MAX_SCALE
        );
    }

    /* A real fit, not scale = 1. The sheet is 1000 CSS px wide, so at
       390px an unfitted surface opens showing a fragment of one room
       with no way to tell it is a fragment - which falsifies "the
       drawing occupies the screen" on arrival. */
    function fit() {
        view.x = 0;
        view.y = 0;
        view.scale = fitScale();
        readerAdjustedView = false;
        applyView();
        wakeLook();
    }

    function zoomBy(factor) {
        view.scale = clamp(view.scale * factor, MIN_SCALE, MAX_SCALE);
        readerAdjustedView = true;
        applyView();
        wakeLook();
    }

    /* SHOW ON DRAWING - a real pan to the coordinate, not just a fit.

       The plan is centred in the lake, so a pin at (px%, py%) sits
       (dx, dy) from the plan's own centre. Centring it is therefore just
       tx = -dx * scale. Done as one transition rather than a jump, so
       the movement reads as travelling to the evidence within the same
       space - which is the whole point of not leaving the workspace. */
    function focusOnMark(mark) {
        var px = parseFloat(mark.getAttribute("data-x"));
        var py = parseFloat(mark.getAttribute("data-y"));
        if (isNaN(px) || isNaN(py)) { return; }

        /* Close enough to read the surrounding drawing, not so close that
           the reader loses where they are on the sheet. */
        var scale = clamp(Math.max(fitScale() * 2.1, 0.85), MIN_SCALE, MAX_SCALE);
        var dx = (px / 100) * PLAN_W - PLAN_W / 2;
        var dy = (py / 100) * PLAN_H - PLAN_H / 2;

        view.scale = scale;
        view.x = -dx * scale;
        view.y = -dy * scale;
        readerAdjustedView = true;
        applyView();
        wakeLook();
    }

    var dragging = false;
    var moved = false;
    var dragStart = null;

    lake.addEventListener("pointerdown", function (event) {
        /* A press on a pin is Point, not Look. */
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
       no persistent fit control in a menu bar on this surface. */
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

    /* Re-fit when the surface changes size - a rotation, a window
       resize, or the dock opening - unless the reader has taken control
       of the view themselves, because refitting under someone who
       deliberately zoomed in throws away their position. */
    var refitTimer = null;
    function refitSoon(delay) {
        window.clearTimeout(refitTimer);
        refitTimer = window.setTimeout(function () {
            /* The guard is re-checked HERE, when the timer fires, not when
               it was scheduled. Show-on-drawing dismisses the sheet - which
               schedules a refit - and then focuses the coordinate a few
               milliseconds later. With the check at schedule time the refit
               still ran afterwards and reset the view to fit, so the
               surface travelled nowhere and the defect was invisible in
               every structural test. */
            if (readerAdjustedView) { return; }
            fit();
        }, delay || 120);
    }

    window.addEventListener("resize", function () { refitSoon(120); });

    /* The Look affordances recede when idle - the games-HUD pattern, not
       a permanent readout. This is what lets the surface be navigable
       without being chromed, and it is the behaviour most worth judging
       visually: "how long is calm" is not a question prose can answer. */
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

    fit();

    /* ========================================================
       SHEETS - one at a time, and they move rather than appear

       `hidden` cannot be transitioned, so opening clears hidden and adds
       .is-open on the next frame; closing reverses and sets hidden once
       the slide has finished. The guard on the close timer matters: a
       reader who reopens the same sheet inside 280ms would otherwise
       have it hidden out from under them by the earlier timeout.
       ======================================================== */

    var index = document.getElementById("cl-index");
    var horizon = document.getElementById("cl-horizon");
    var depth = document.getElementById("cl-depth");
    var composer = document.getElementById("cl-composer");
    var instrument = document.getElementById("cl-instrument");
    var scrim = document.getElementById("cl-scrim");

    var sheets = [index, horizon, depth, composer, instrument].filter(Boolean);
    var openSheet = null;

    function closeSheetEl(sheet) {
        if (!sheet || sheet.hidden) { return; }
        sheet.classList.remove("is-open");
        window.setTimeout(function () {
            if (!sheet.classList.contains("is-open")) { sheet.hidden = true; }
        }, SLIDE_MS);
    }

    function openSheetEl(sheet) {
        sheet.hidden = false;
        sheet.scrollTop = 0;
        /* Force a style/layout flush so the browser commits the closed
           transform before the open class lands - that is what makes the
           slide run instead of jumping.

           Deliberately NOT requestAnimationFrame. An earlier version used
           a double rAF and the sheet never opened at all wherever the
           frame clock is throttled: `hidden` was cleared but `is-open`
           never arrived, leaving the sheet parked off-screen at
           translateY(100%) while assistive technology was told it was
           present. Reading offsetWidth is synchronous and cannot stall,
           so the worst case degrades to appearing without the slide -
           which is the correct behaviour, not a broken one. */
        void sheet.offsetWidth;
        sheet.classList.add("is-open");
    }

    function showOnly(target) {
        sheets.forEach(function (sheet) {
            if (sheet !== target) { closeSheetEl(sheet); }
        });
        if (target) { openSheetEl(target); }
        openSheet = target || null;

        if (scrim) {
            if (target) {
                scrim.hidden = false;
                void scrim.offsetWidth;
                scrim.classList.add("is-open");
            } else {
                scrim.classList.remove("is-open");
                window.setTimeout(function () {
                    if (!scrim.classList.contains("is-open")) { scrim.hidden = true; }
                }, SLIDE_MS);
            }
        }

        /* A FACT, not a width decision. CSS attaches a meaning to this
           class only where there is room to dock; at 390px it does
           nothing. See the header note. */
        body.classList.toggle("is-docked", !!target);
        body.setAttribute("data-state", target ? target.id : (disturbed ? "disturbed" : "base"));

        /* The drawing makes room rather than being hidden - refit once
           the inset has finished animating. */
        refitSoon(SLIDE_MS + 40);
        syncVerbs();
    }

    function dismiss() { showOnly(null); }

    var disturbed = !!document.querySelector(".cl-disturbance");
    body.setAttribute("data-state", disturbed ? "disturbed" : "base");

    Array.prototype.forEach.call(document.querySelectorAll("[data-dismiss]"), function (btn) {
        btn.addEventListener("click", dismiss);
    });

    if (scrim) { scrim.addEventListener("click", dismiss); }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") { dismiss(); }
    });

    /* --------------------------------------------------------
       SWIPE TO DISMISS.

       Gated on the grab handle being VISIBLE, which is element state
       rather than a viewport test: the handle is display:none wherever
       there is no touch gesture to afford, so this reads "is this a
       surface that can be pulled" instead of "how wide is the screen".
       -------------------------------------------------------- */
    sheets.forEach(function (sheet) {
        var grab = sheet.querySelector(".cl-grab");
        var head = sheet.querySelector(".cl-sheet-head");
        var startY = null;
        var offset = 0;

        function canSwipe(event) {
            if (!grab || !grab.offsetHeight) { return false; }
            if (event.target.closest("button, input, a")) { return false; }
            /* Only from the top of the sheet, so a swipe never fights
               the sheet's own scrolling. */
            return sheet.scrollTop <= 0 &&
                   (event.target === grab || (head && head.contains(event.target)) || event.target === sheet);
        }

        sheet.addEventListener("pointerdown", function (event) {
            if (!canSwipe(event)) { return; }
            startY = event.clientY;
            offset = 0;
            sheet.style.transition = "none";
        });

        sheet.addEventListener("pointermove", function (event) {
            if (startY === null) { return; }
            offset = Math.max(0, event.clientY - startY);
            sheet.style.transform = "translateY(" + offset + "px)";
        });

        function endSwipe() {
            if (startY === null) { return; }
            startY = null;
            sheet.style.transition = "";
            sheet.style.transform = "";
            if (offset > 90) { dismiss(); }
            offset = 0;
        }

        sheet.addEventListener("pointerup", endSwipe);
        sheet.addEventListener("pointercancel", endSwipe);
        sheet.addEventListener("pointerleave", endSwipe);
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

    /* Every route into depth goes through here, so there is exactly one
       way a claim can be shown and it always carries its verification
       badge and its basis with it. */
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
    }

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
       sheet and travels to the coordinate, because the answer to "where
       is it" is the drawing, not a panel sitting on top of the drawing. */
    Array.prototype.forEach.call(document.querySelectorAll("[data-show]"), function (btn) {
        btn.addEventListener("click", function () {
            var id = btn.getAttribute("data-show");
            var mark = document.getElementById("mark-" + id);
            dismiss();
            if (!mark) { return; }
            setSelection(id, mark.getAttribute("data-tag"));
            /* After the dock has released, so the focus is computed
               against the width the drawing actually ends up with. */
            window.setTimeout(function () {
                focusOnMark(mark);
                mark.classList.remove("is-shown");
                void mark.offsetWidth;      /* restart the one-shot ring */
                mark.classList.add("is-shown");
                /* The ring is removed on a timer rather than left to the
                   animation to finish. A stalled timeline - a background
                   tab, a throttled frame - would otherwise leave a focus
                   ring on the drawing permanently, which is exactly the
                   "always moving, always there" chrome this surface is
                   built to avoid. The class is the state; the animation
                   only decorates it. */
                window.setTimeout(function () {
                    mark.classList.remove("is-shown");
                }, 1200);
            }, SLIDE_MS + 30);
        });
    });

    /* ========================================================
       LOOK - document switching without a rail
       ======================================================== */

    var docSwitch = document.getElementById("cl-doc-switch");
    if (docSwitch) {
        docSwitch.addEventListener("click", function () {
            showOnly(openSheet === index ? null : index);
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
            readerAdjustedView = false;
            refitSoon(SLIDE_MS + 40);
        });
    });

    /* ========================================================
       THE VERB BAR - one table, no width branch
       ======================================================== */

    var VERBS = {
        look: function () {
            wakeLook();
            showOnly(openSheet === index ? null : index);
        },
        point: function () {
            /* Point with something selected reopens its depth. Point with
               nothing selected says what to do, rather than silently
               doing nothing. */
            if (selected) { openDepth(selected.id); return; }
            dismiss();
            flashReason("Point at something on the drawing.");
        },
        ask: function () {
            showOnly(openSheet === composer ? null : composer);
            if (openSheet === composer) {
                var field = document.getElementById("cl-ask-field");
                if (field) { window.setTimeout(function () { field.focus(); }, SLIDE_MS); }
            }
        },
        commit: function () {
            if (!selected) { return; }
            openDepth(selected.id);
            var btn = document.querySelector('[data-commit="' + selected.id + '"]');
            if (btn) { window.setTimeout(function () { btn.focus(); }, SLIDE_MS); }
        }
    };

    var verbButtons = Array.prototype.slice.call(document.querySelectorAll("[data-verb]"));

    verbButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var fn = VERBS[btn.getAttribute("data-verb")];
            if (fn) { fn(); }
        });
    });

    var reasonHeld = false;
    var reasonTimer = null;

    function syncVerbs() {
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
            verbReason.textContent = selected
                ? "Ask and Commit are about " + selected.tag +
                  ". Selection supplies context, not authorization."
                : "Commit needs a selection. Point at something first.";
        }
    }

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

    /* The tracked band and the instrumentation toggle are just two more
       ways into the same one-at-a-time sheet model. */
    var horizonToggle = document.getElementById("cl-horizon-toggle");
    if (horizonToggle) {
        horizonToggle.addEventListener("click", function () {
            showOnly(openSheet === horizon ? null : horizon);
        });
    }

    var instrumentToggle = document.getElementById("cl-instrument-toggle");
    if (instrumentToggle) {
        instrumentToggle.addEventListener("click", function () {
            showOnly(openSheet === instrument ? null : instrument);
        });
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

    /* A press on the drawing returns to it. The surface is what you come
       back to, so coming back should not require finding a control. A
       press that was actually a pan does not count. */
    lake.addEventListener("click", function (event) {
        if (moved) { moved = false; return; }
        if (event.target.closest(".cl-mark, .cl-look, .cl-selection")) { return; }
        dismiss();
    });

    syncVerbs();
}());
