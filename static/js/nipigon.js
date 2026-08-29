/* ============================================================
   5 NIPIGON - Phase 2 Scenario 01

   Two coordination pathways that must not depend on each other.

   The GO path may not be a prerequisite for the manual path. If the
   only way to get a second pane is to ask GO first, then GO is not an
   assistant, it is a gate - and every "human-directed" claim about the
   surface becomes false the moment GO is wrong or silent. So the split
   control and the sibling browser work with GO never invoked, and
   nothing in the manual path reads GO's answer.

   No inline styles are written: the CSP refuses parsed style
   attributes, and everything here toggles attributes or classes.
   ============================================================ */
(function () {
    "use strict";

    var body = document.body;
    var pane2 = document.getElementById("np-pane2");
    var pane2Img = document.getElementById("np-pane2-img");
    var pane2Empty = document.getElementById("np-pane2-empty");
    var pane2Tag = document.getElementById("np-pane2-tag");
    var pane2Sheet = document.getElementById("np-pane2-sheet");
    var siblings = document.getElementById("np-siblings");
    var why = document.getElementById("np-why");
    var prov = document.getElementById("np-prov");

    var openedFieldId = null;

    /* ---- scenes ---------------------------------------------------- */

    function showField() {
        body.setAttribute("data-scene", "field");
        if (openedFieldId) {
            var origin = document.getElementById("field-" + openedFieldId);
            /* The tile came from inside a discipline, and coming back to a
               collapsed grid loses the reader's place - and focus lands on
               something display:none, which silently does nothing. So the
               discipline that holds it is reopened first. */
            if (origin) {
                var holder = origin.closest(".np-disc-sheets");
                if (holder && holder.hidden) {
                    holder.hidden = false;
                    var owner = document.querySelector(
                        "[aria-controls='" + holder.id + "']");
                    if (owner) { owner.setAttribute("aria-expanded", "true"); }
                }
                origin.focus();
            }
        }
    }

    function showSurface(fieldId) {
        openedFieldId = fieldId || null;
        body.setAttribute("data-scene", "surface");
        var back = document.getElementById("np-return");
        if (back) { back.focus(); }
        /* Now that the pane has layout, frame the selected room. */
        if (window.npFrameAnchor) { window.npFrameAnchor(); }
    }

    Array.prototype.forEach.call(document.querySelectorAll(".np-field"), function (field) {
        field.addEventListener("click", function () {
            var id = field.getAttribute("data-field");
            if (field.getAttribute("data-action") === "true") { return; }
            /* Only the anchor sheet has a verified selection and a verified
               relationship behind it. Opening another sheet into the same
               scenario would present coordination the evidence does not
               support, so the others stay closed and say nothing. */
            if (id !== "A204") { return; }
            showSurface(id);
        });
    });

    /* ---- disciplines ----------------------------------------------
       A discipline is a container, so pressing one OPENS IT rather than
       jumping somewhere. What it opens into differs by what is actually
       behind it, and every one of the three answers is truthful:

         - sheets delivered  -> its own Page-Fields, which then behave
                                exactly as they did when they were the top
                                level of this screen
         - named, none here  -> the note saying what the A100 index names
                                and what the source material contains
         - intake            -> the same refusal the Calm Lake prototype
                                gives, because it is the same non-feature

       One open at a time. Seven disciplines expanded together is the grid
       this object replaced, back again with more scrolling.
       ---------------------------------------------------------------- */
    var discButtons = Array.prototype.slice.call(
        document.querySelectorAll("[aria-controls^='sheets-']"));

    function collapseAll(except) {
        discButtons.forEach(function (btn) {
            if (btn === except) { return; }
            btn.setAttribute("aria-expanded", "false");
            var panel = document.getElementById(btn.getAttribute("aria-controls"));
            if (panel) { panel.hidden = true; }
        });
    }

    discButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            var panel = document.getElementById(btn.getAttribute("aria-controls"));
            if (!panel) { return; }
            var open = btn.getAttribute("aria-expanded") === "true";
            collapseAll(btn);
            btn.setAttribute("aria-expanded", open ? "false" : "true");
            panel.hidden = open;
        });
    });

    var returnBtn = document.getElementById("np-return");
    if (returnBtn) {
        returnBtn.addEventListener("click", function () {
            closePane2();
            showField();
        });
    }

    /* ---- pane 2 ---------------------------------------------------- */

    var sibButtons = Array.prototype.slice.call(document.querySelectorAll(".np-sib"));
    var sibIndex = -1;

    function loadSibling(index, tagText) {
        if (!sibButtons.length) { return; }
        if (index < 0) { index = sibButtons.length - 1; }
        if (index >= sibButtons.length) { index = 0; }
        sibIndex = index;
        var btn = sibButtons[index];

        sibButtons.forEach(function (other) { other.classList.remove("is-current"); });
        btn.classList.add("is-current");

        pane2Img.src = btn.getAttribute("data-asset");
        pane2Img.setAttribute("data-mono", btn.getAttribute("data-mono") || "false");
        pane2Img.alt = btn.getAttribute("data-sib") + " " + btn.getAttribute("data-title");
        pane2Img.hidden = false;
        pane2Empty.hidden = true;
        pane2Sheet.textContent = btn.getAttribute("data-sib") + " " + btn.getAttribute("data-title");
        if (tagText) { pane2Tag.textContent = tagText; }
        if (window.npSyncOverlay) { window.npSyncOverlay(btn.getAttribute("data-sib")); }
        if (window.npViews && window.npViews["2"]) {
            window.npViews["2"].focus = null;
            window.npViews["2"].reset();
        }
        var regoBtn = document.getElementById("np-regofocus");
        if (regoBtn) { regoBtn.hidden = true; }
    }

    function openPane2(mode) {
        body.setAttribute("data-split", mode);
        siblings.hidden = false;
    }

    function closePane2() {
        body.setAttribute("data-split", "none");
        siblings.hidden = true;
        why.hidden = true;
        prov.hidden = true;
        pane2Img.hidden = true;
        pane2Img.src = "";
        pane2Empty.hidden = false;
        pane2Tag.textContent = "Pane 2";
        pane2Sheet.textContent = "—";
        sibIndex = -1;
        sibButtons.forEach(function (b) { b.classList.remove("is-current"); });
    }

    /* ---- PATHWAY A - GO assisted ----------------------------------- */

    var askGo = document.getElementById("np-ask-go");
    if (askGo) {
        askGo.addEventListener("click", function () {
            openPane2("go");
            /* GO opens the ONE candidate carried by an explicit callout on
               the sheet. The panel below stays open beside it listing the
               candidates it did not choose and why, because a single
               confident answer is indistinguishable from a guess. */
            /* This is the difference between the two paths that actually
               matters. GO opens the DETAIL, cropped to the thing that was
               asked about; the manual path opens whole sheets to browse.
               Handing back a full E-size sheet and calling it an answer
               leaves the reader doing the finding GO claimed to have done. */
            var asset = askGo.getAttribute("data-go-asset");
            var sheet = askGo.getAttribute("data-go-sheet");
            if (asset) {
                pane2Img.src = asset;
                pane2Img.setAttribute("data-mono", askGo.getAttribute("data-go-mono") || "false");
                pane2Img.alt = sheet + " detail " + (askGo.getAttribute("data-go-detail") || "");
                pane2Img.hidden = false;
                pane2Empty.hidden = true;
                pane2Tag.textContent = "Pane 2 · GO selected";
                /* window-scoped, not bare: parseFocus and views live in the
                   VIEWPORT IIFE, and this handler is in another one. Calling
                   them bare threw a ReferenceError that aborted the rest of
                   the handler silently - the pane still loaded, so it looked
                   like a framing bug rather than a scope bug. */
                var gf = window.npParseFocus
                    ? window.npParseFocus(askGo, "data-go-focus", "data-go-view") : null;
                var v2 = window.npViews && window.npViews["2"];
                if (gf && v2) {
                    var apply = function () {
                        if (pane2Img.clientWidth) { v2.focusRect(gf.rect, gf.viewW, gf.viewH); }
                    };
                    if (pane2Img.complete && pane2Img.clientWidth) { apply(); }
                    else {
                        pane2Img.addEventListener("load", apply, { once: true });
                        requestAnimationFrame(apply);
                    }
                    var back = document.getElementById("np-regofocus");
                    if (back) {
                        back.hidden = false;
                        back.onclick = function () { v2.refocus(); };
                    }
                }
                pane2Sheet.textContent = sheet + " · " + askGo.getAttribute("data-go-title");
                if (window.npSyncOverlay) { window.npSyncOverlay(sheet); }
                if (window.npViews && window.npViews["2"]) { window.npViews["2"].reset(); }
                sibButtons.forEach(function (b) {
                    b.classList.toggle("is-current", b.getAttribute("data-sib") === sheet);
                    if (b.getAttribute("data-sib") === sheet) { sibIndex = sibButtons.indexOf(b); }
                });
            }
            why.hidden = false;
            prov.hidden = false;
        });
    }

    /* ---- PATHWAY B - human directed --------------------------------
       Reads nothing GO produced. It opens the pane on the first sibling
       and leaves the choosing to the person. */

    var split = document.getElementById("np-split");
    if (split) {
        split.addEventListener("click", function () {
            openPane2("manual");
            why.hidden = true;
            prov.hidden = false;
            loadSibling(0, "Pane 2 · summoned");
        });
    }

    var closeBtn = document.getElementById("np-close2");
    if (closeBtn) { closeBtn.addEventListener("click", closePane2); }
    window.npClosePane2 = closePane2;

    /* ---- local sibling stepping, inside pane 2 only ----------------
       Stepping is bounded to the detail-sheet family. It is deliberately
       NOT a global chain across unrelated surface types: stepping from a
       washroom detail to an elevation to a schedule would be movement
       without a relationship, which teaches the reader nothing. */

    sibButtons.forEach(function (btn, i) {
        btn.addEventListener("click", function () {
            if (body.getAttribute("data-split") === "none") { openPane2("manual"); }
            loadSibling(i, "Pane 2 · stepped");
        });
    });

    var prev = document.getElementById("np-prev");
    var next = document.getElementById("np-next");
    if (prev) { prev.addEventListener("click", function () { loadSibling(sibIndex - 1, "Pane 2 · stepped"); }); }
    if (next) { next.addEventListener("click", function () { loadSibling(sibIndex + 1, "Pane 2 · stepped"); }); }

    document.addEventListener("keydown", function (event) {
        if (body.getAttribute("data-scene") !== "surface") { return; }
        if (event.key === "Escape") {
            if (body.getAttribute("data-split") !== "none") { closePane2(); }
            else { showField(); }
        }
    });
}());

/* ============================================================
   VIEWPORT CONTROLLER - one per pane

   State is per pane by construction: each Viewport owns its own stage and
   its own numbers, so navigating Pane 2 cannot move Pane 1. That is the
   property the coordination view depends on - the thing you are
   coordinating FROM has to stay put while you go looking.

   A view transform is NOT a document change. Nothing here writes to the
   source PDF or to the derived native orientation; reset() returns to that
   derived value, which is what makes offering manual rotation safe.
   ============================================================ */
(function () {
    "use strict";

    var MIN = 0.2, MAX = 12;

    function Viewport(stage, body, zoomLabel) {
        this.stage = stage;
        this.body = body;
        this.label = zoomLabel;
        this.reset(true);
        this.bind();
    }

    Viewport.prototype.apply = function () {
        var st = this.stage.style;
        st.setProperty("--vx", this.x + "px");
        st.setProperty("--vy", this.y + "px");
        st.setProperty("--vs", this.scale);
        st.setProperty("--vr", this.rot + "deg");
        if (this.label) { this.label.textContent = Math.round(this.scale * 100) + "%"; }
    };

    Viewport.prototype.reset = function () {
        this.x = 0; this.y = 0; this.scale = 1; this.rot = 0;
        this.apply();
    };

    Viewport.prototype.fit = function () {
        /* The stage is laid out to fit its pane, so fit is the identity
           transform - but it must NOT clear a rotation the person chose.
           Fit is about size; Reset is about orientation. */
        this.x = 0; this.y = 0; this.scale = 1;
        this.apply();
    };

    Viewport.prototype.zoomBy = function (factor, ox, oy) {
        var next = Math.min(MAX, Math.max(MIN, this.scale * factor));
        if (next === this.scale) { return; }
        if (typeof ox === "number") {
            /* Keep the point under the cursor under the cursor. */
            var k = next / this.scale;
            this.x = ox - k * (ox - this.x);
            this.y = oy - k * (oy - this.y);
        }
        this.scale = next;
        this.apply();
    };

    /* Frame a rectangle expressed in the sheet's own point space.

       This is what replaced the cropped raster. A crop is now a VIEW onto the
       one vector asset - which is also why "return to the GO region" is a
       real thing the reader can do rather than a reload. */
    Viewport.prototype.focusRect = function (rect, viewW, viewH) {
        var img = this.stage.querySelector(".np-page");
        if (!img || !rect || !viewW || !viewH) { return; }
        var dw = img.clientWidth, dh = img.clientHeight;
        if (!dw || !dh) { return; }

        var pane = this.body.getBoundingClientRect();
        var pxPerPtX = dw / viewW, pxPerPtY = dh / viewH;
        var rw = rect.w * pxPerPtX, rh = rect.h * pxPerPtY;
        if (rw <= 0 || rh <= 0) { return; }

        /* 0.92 leaves a margin, so the thing you asked to see is not welded
           to the edge of the pane. */
        var s = Math.min(pane.width / rw, pane.height / rh) * 0.92;
        s = Math.min(MAX, Math.max(MIN, s));

        var cx = (rect.x + rect.w / 2) * pxPerPtX;
        var cy = (rect.y + rect.h / 2) * pxPerPtY;
        this.scale = s;
        this.x = s * (dw / 2 - cx);
        this.y = s * (dh / 2 - cy);
        this.apply();
        this.focus = { rect: rect, viewW: viewW, viewH: viewH };
    };

    Viewport.prototype.refocus = function () {
        if (this.focus) {
            this.focusRect(this.focus.rect, this.focus.viewW, this.focus.viewH);
        }
    };

    Viewport.prototype.rotateBy = function (deg) {
        this.rot = (this.rot + deg) % 360;
        this.apply();
    };

    Viewport.prototype.bind = function () {
        var self = this;

        this.body.addEventListener("wheel", function (e) {
            e.preventDefault();
            var r = self.body.getBoundingClientRect();
            self.zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12,
                        e.clientX - r.left - r.width / 2,
                        e.clientY - r.top - r.height / 2);
        }, { passive: false });

        var dragging = false, lastX = 0, lastY = 0;
        var pointers = {}, startDist = 0, startScale = 1;

        this.body.addEventListener("pointerdown", function (e) {
            pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
            var n = Object.keys(pointers).length;
            if (n === 1) {
                dragging = true; lastX = e.clientX; lastY = e.clientY;
                self.stage.classList.add("is-panning");
            } else if (n === 2) {
                var p = Object.keys(pointers).map(function (k) { return pointers[k]; });
                startDist = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
                startScale = self.scale;
                dragging = false;
                self.stage.classList.remove("is-panning");
            }
        });

        this.body.addEventListener("pointermove", function (e) {
            if (!(e.pointerId in pointers)) { return; }
            pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
            var ids = Object.keys(pointers);
            if (ids.length === 2 && startDist) {
                var p = ids.map(function (k) { return pointers[k]; });
                var d = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
                self.scale = Math.min(MAX, Math.max(MIN, startScale * (d / startDist)));
                self.apply();
                return;
            }
            if (!dragging) { return; }
            self.x += e.clientX - lastX;
            self.y += e.clientY - lastY;
            lastX = e.clientX; lastY = e.clientY;
            self.apply();
        });

        function release(e) {
            delete pointers[e.pointerId];
            if (!Object.keys(pointers).length) {
                dragging = false; startDist = 0;
                self.stage.classList.remove("is-panning");
            }
        }
        this.body.addEventListener("pointerup", release);
        this.body.addEventListener("pointercancel", release);

        this.body.addEventListener("dblclick", function (e) {
            var r = self.body.getBoundingClientRect();
            self.zoomBy(1.8, e.clientX - r.left - r.width / 2,
                             e.clientY - r.top - r.height / 2);
        });
    };

    function parseFocus(el, rectAttr, viewAttr) {
        if (!el) { return null; }
        var r = (el.getAttribute(rectAttr) || "").split(",").map(Number);
        var v = (el.getAttribute(viewAttr) || "").split(",").map(Number);
        if (r.length !== 4 || v.length !== 2 || !v[0]) { return null; }
        return { rect: { x: r[0], y: r[1], w: r[2], h: r[3] }, viewW: v[0], viewH: v[1] };
    }
    window.npParseFocus = parseFocus;

    var views = {};
    [["1", "np-stage1", "np-body1", "np-zoom1"],
     ["2", "np-stage2", "np-body2", "np-zoom2"]].forEach(function (spec) {
        var stage = document.getElementById(spec[1]);
        var body = document.getElementById(spec[2]);
        if (stage && body) {
            views[spec[0]] = new Viewport(stage, body, document.getElementById(spec[3]));
        }
    });
    window.npViews = views;

    /* Framing must wait for the pane to be VISIBLE, not merely for the image
       to load. On arrival the workspace is display:none, so clientWidth is 0 -
       and framing against 0 produces a transform that is silently wrong rather
       than obviously broken. A cached vector makes it worse: `load` never
       fires, so a load-listener alone would never run at all.

       So this is exported and called when the scene switches, and it verifies
       it has real layout before trusting it. */
    window.npFrameAnchor = function () {
        var v = views["1"];
        var img = document.getElementById("np-pane1-img");
        if (!v || !img) { return; }
        var f = parseFocus(img, "data-focus", "data-view");
        if (!f) { return; }
        var go = function () {
            if (!img.clientWidth) { return; }
            v.focusRect(f.rect, f.viewW, f.viewH);
        };
        if (img.complete && img.clientWidth) { go(); }
        else { img.addEventListener("load", go, { once: true }); requestAnimationFrame(go); }
    };
    window.addEventListener("resize", function () {
        if (views["1"]) { views["1"].refocus(); }
        if (views["2"]) { views["2"].refocus(); }
    });

    Array.prototype.forEach.call(document.querySelectorAll(".np-view"), function (bar) {
        var v = views[bar.getAttribute("data-pane")];
        if (!v) { return; }
        bar.addEventListener("click", function (e) {
            var btn = e.target.closest(".np-vbtn");
            if (!btn) { return; }
            var act = btn.getAttribute("data-act");
            if (act === "in") { v.zoomBy(1.25); }
            else if (act === "out") { v.zoomBy(1 / 1.25); }
            else if (act === "fit") { v.fit(); }
            else if (act === "rccw") { v.rotateBy(-90); }
            else if (act === "rcw") { v.rotateBy(90); }
            else if (act === "reset") { v.reset(); }
        });
    });

    /* ---- semantic overlay + pointing card -------------------------- */

    var overlay = document.getElementById("np-overlay");
    var semToggle = document.getElementById("np-sem-toggle");
    var tip = document.getElementById("np-tip");

    /* Take the overlay aspect from its own viewBox rather than hardcoding a
       ratio, so a second sheet with a different page box registers correctly
       without touching the stylesheet. */
    if (overlay) {
        var vb = (overlay.getAttribute("viewBox") || "").split(/\s+/);
        if (vb.length === 4 && +vb[2] && +vb[3]) {
            overlay.style.setProperty("--ov-aspect", vb[2] + " / " + vb[3]);
        }
    }

    function overlayIsOn() {
        return !!overlay && overlay.classList.contains("is-on");
    }
    window.npOverlayIsOn = overlayIsOn;

    function setOverlay(on) {
        if (!overlay || !semToggle) { return; }
        /* classList, not .hidden - see the note in nipigon.css. `hidden` is an
           HTMLElement property and does nothing on an SVG element, so writing
           it produced a state machine that reported cleanly while controlling
           nothing. */
        overlay.classList.toggle("is-on", !!on);
        overlay.removeAttribute("hidden");
        semToggle.setAttribute("aria-pressed", on ? "true" : "false");
        semToggle.textContent = "Semantic overlay: " + (on ? "ON" : "OFF");
        if (!on && tip) { tip.hidden = true; }
    }
    window.npSetOverlay = setOverlay;

    if (semToggle) {
        semToggle.addEventListener("click", function () { setOverlay(!overlayIsOn()); });
    }

    /* The overlay is only meaningful on the sheet it was derived from.
       Offering it over A801 would invite the reader to believe RS501's
       classification describes a washroom detail. */
    var currentSheet = null;
    window.npCurrentSheet = function () { return currentSheet; };

    window.npSyncOverlay = function (sheetId) {
        currentSheet = sheetId;
        if (!semToggle) { return; }
        var applies = sheetId === "RS501";
        /* The preference is the DEFAULT posture for a newly opened sheet,
           which is why it is read here rather than only at startup: opening
           RS501 should honour the setting without the reader touching
           anything. It still cannot turn on for a sheet with no
           classification - there would be nothing to draw. */
        var want = applies && !!(window.npPrefs && window.npPrefs.get("semantic_overlay"));
        setOverlay(want);
    };

    var strictTooltips = true;
    window.npSetStrictTooltips = function (on) { strictTooltips = !!on; };

    if (overlay && tip) {
        overlay.addEventListener("pointerover", function (e) {
            var line = e.target.closest(".np-sem");
            if (!line) { return; }
            Array.prototype.forEach.call(
                overlay.querySelectorAll(".np-sem.is-active"),
                function (n) { n.classList.remove("is-active"); });
            line.classList.add("is-active");

            document.getElementById("np-tip-token").textContent =
                line.getAttribute("data-token");
            var basis = line.getAttribute("data-basis");
            var badge = document.getElementById("np-tip-basis");
            badge.textContent = basis === "direct" ? "DIRECT / LOCATED" : "INFERRED";
            badge.className = "np-basis np-basis--" + basis;
            var kinds = { beam: "Structural beam", column: "Structural column",
                          angle: "Structural angle" };
            document.getElementById("np-tip-kind").textContent =
                kinds[line.getAttribute("data-kind")] || line.getAttribute("data-kind");
            /* Strict provenance OFF hides the grounding detail, never the
               basis badge: a reader must always be able to see whether a
               stroke is DIRECT or INFERRED, because that is the claim. */
            var ev = document.getElementById("np-tip-ev");
            var src = document.getElementById("np-tip-src");
            ev.textContent = line.getAttribute("data-evidence");
            src.textContent = "RS501 - 212109 RS501 STRUCTURAL FRAMING.pdf";
            ev.hidden = !strictTooltips;
            src.hidden = !strictTooltips;

            var host = document.getElementById("np-body2").getBoundingClientRect();
            tip.style.setProperty("--tip-x",
                Math.max(6, e.clientX - host.left + 12) + "px");
            tip.style.setProperty("--tip-y",
                Math.max(6, e.clientY - host.top + 12) + "px");
            tip.hidden = false;
        });
        overlay.addEventListener("pointerleave", function () { tip.hidden = true; });
    }
}());

/* ============================================================
   ENGINE DNA PREFERENCES

   One place for every flag that changes how a drawing is presented,
   moved off the drawing surface itself. A control that lives on the
   canvas competes with the canvas: the sheet is the subject, and a row
   of switches beside it teaches the reader that the switches matter as
   much as the drawing does.

   PRECEDENCE. Defaults ship as data in config/engine_preferences.json
   and reach the page as a JSON blob; a viewer's own choices live in
   localStorage under ARCHIOSK_ENGINE_PREFS and win. Storage can throw
   or come back empty - a private window, cleared site data, a browser
   set to block it - so every read is guarded and falls back to the
   shipped defaults rather than to an undefined engine.

   WHAT A PREFERENCE MAY NOT DO. None of these change a source document,
   a derived native orientation, or a classification. Turning the
   semantic overlay off does not un-classify anything; it stops drawing
   it. That boundary is why the panel is safe to expose at all.
   ============================================================ */
(function () {
    "use strict";

    var root = document.getElementById("np-prefs-data");
    if (!root) { return; }

    var schema;
    try {
        schema = JSON.parse(root.textContent);
    } catch (e) {
        return;
    }

    var KEY = schema.storage_key || "ARCHIOSK_ENGINE_PREFS";
    var defaults = {};
    var meta = {};
    (schema.groups || []).forEach(function (g) {
        (g.preferences || []).forEach(function (p) {
            defaults[p.id] = p["default"];
            meta[p.id] = p;
        });
    });

    function read() {
        var out = {};
        Object.keys(defaults).forEach(function (k) { out[k] = defaults[k]; });
        try {
            var raw = window.localStorage.getItem(KEY);
            if (raw) {
                var saved = JSON.parse(raw);
                Object.keys(out).forEach(function (k) {
                    if (k in saved) { out[k] = saved[k]; }
                });
            }
        } catch (e) { /* defaults stand */ }
        return out;
    }

    function write(state) {
        try {
            window.localStorage.setItem(KEY, JSON.stringify(state));
        } catch (e) { /* a viewer who cannot persist still gets a working page */ }
    }

    var state = read();
    var listeners = [];

    function emit() {
        listeners.forEach(function (fn) {
            try { fn(state); } catch (e) { /* one consumer must not break the rest */ }
        });
    }

    var prefs = {
        get: function (id) { return state[id]; },
        all: function () { var c = {}; Object.keys(state).forEach(function (k) { c[k] = state[k]; }); return c; },
        set: function (id, value) {
            if (!(id in defaults)) { return; }
            state[id] = value;
            write(state);
            emit();
        },
        reset: function () {
            state = {};
            Object.keys(defaults).forEach(function (k) { state[k] = defaults[k]; });
            write(state);
            emit();
            render();
        },
        subscribe: function (fn) {
            if (typeof fn !== "function") { return function () {}; }
            listeners.push(fn);
            try { fn(state); } catch (e) { /* see emit */ }
            return function () {
                var i = listeners.indexOf(fn);
                if (i !== -1) { listeners.splice(i, 1); }
            };
        }
    };
    window.npPrefs = prefs;

    /* ---- the panel ------------------------------------------------- */

    var panel = document.getElementById("np-prefs");
    var openBtn = document.getElementById("np-prefs-open");
    var closeBtn = document.getElementById("np-prefs-close");
    var resetBtn = document.getElementById("np-prefs-reset");
    var body = document.getElementById("np-prefs-body");

    function render() {
        if (!body) { return; }
        Array.prototype.forEach.call(body.querySelectorAll("[data-pref]"), function (el) {
            var id = el.getAttribute("data-pref");
            if (el.type === "checkbox") {
                el.checked = !!state[id];
            } else if (el.tagName === "BUTTON") {
                el.setAttribute("aria-pressed",
                    String(state[el.getAttribute("data-pref-group")] === el.value));
            }
        });
    }

    if (body) {
        body.addEventListener("change", function (e) {
            var el = e.target.closest("[data-pref]");
            if (!el || el.type !== "checkbox") { return; }
            prefs.set(el.getAttribute("data-pref"), el.checked);
        });
        body.addEventListener("click", function (e) {
            var btn = e.target.closest("[data-pref-group]");
            if (!btn) { return; }
            prefs.set(btn.getAttribute("data-pref-group"), btn.value);
            render();
        });
    }

    var scrim = document.getElementById("np-prefs-scrim");

    function open(on) {
        if (!panel) { return; }
        panel.hidden = !on;
        if (scrim) { scrim.hidden = !on; }
        if (openBtn) { openBtn.setAttribute("aria-expanded", on ? "true" : "false"); }
        if (on) {
            render();
            var first = panel.querySelector("[data-pref]");
            if (first) { first.focus(); }
        } else if (openBtn) {
            openBtn.focus();
        }
    }

    if (openBtn) { openBtn.addEventListener("click", function () { open(panel.hidden); }); }
    if (closeBtn) { closeBtn.addEventListener("click", function () { open(false); }); }
    /* A tap outside is how a dialog is dismissed on a phone, where the Close
       button is a small target at the top of a tall panel. */
    if (scrim) { scrim.addEventListener("click", function () { open(false); }); }
    if (resetBtn) { resetBtn.addEventListener("click", function () { prefs.reset(); }); }
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && panel && !panel.hidden) { open(false); }
    });

    /* ---- the surface subscribes ------------------------------------- */

    prefs.subscribe(function (s) {
        /* Theme is a token swap and nothing else - the DOM and the grid
           geometry are identical between fields. */
        document.body.setAttribute("data-theme", s.theme);

        /* The overlay flag is the DEFAULT posture, not an override: it is
           applied when a sheet is opened. Flipping it while RS501 is on
           screen should be visible immediately, so apply it now too - but
           only where a classification actually exists, which npSyncOverlay
           already gates. */
        if (window.npSetOverlay && window.npCurrentSheet) {
            window.npSetOverlay(!!s.semantic_overlay && window.npCurrentSheet() === "RS501");
        }

        if (window.npSetStrictTooltips) {
            window.npSetStrictTooltips(!!s.strict_provenance_tooltips);
        }
    });

    render();
}());

/* ============================================================
   DISMISS BY DRAGGING A PANE OFF THE SCREEN

   The gesture lives on the pane HEAD, not on the drawing, and that is
   the whole design of it. Dragging the drawing already pans it - which
   is the primary gesture on a coordination surface - so putting
   "dismiss" on the same drag would mean panning too far makes the pane
   you are comparing against disappear. Losing the reference mid-
   comparison is the worst accident available on this screen, so the two
   gestures get separate targets: the drawing pans, its header dismisses.

   PANE 1 IS NOT DISMISSIBLE, and this is not an oversight. It is the
   anchor: the thing being coordinated FROM. A workspace where the
   anchor can be swiped away is a workspace that can be left showing
   only an answer with nothing to check it against.

   Under threshold the pane springs back, so a hesitant drag costs
   nothing and the gesture is discoverable by trying it.
   ============================================================ */
(function () {
    "use strict";

    var pane = document.querySelector(".np-pane--2");
    var head = pane && pane.querySelector(".np-pane-head");
    if (!pane || !head) { return; }

    var dragging = false, startX = 0, dx = 0, id = null;
    var THRESHOLD = 0.32;   /* of the pane's own width */

    function set(x) {
        pane.style.setProperty("--dismiss-x", x + "px");
        pane.style.setProperty("--dismiss-fade", String(Math.max(0, 1 - Math.abs(x) / (pane.offsetWidth || 1))));
    }

    function clear() {
        /* Set to zero rather than removed. Removing the property left the
           computed transform sitting at its last value instead of falling
           back to 0px, so a short drag stayed offset instead of springing
           back - visible only by reading the computed transform, not the
           inline style, which read as cleared. */
        pane.style.setProperty("--dismiss-x", "0px");
        pane.style.setProperty("--dismiss-fade", "1");
    }

    head.addEventListener("pointerdown", function (e) {
        if (e.button !== undefined && e.button !== 0) { return; }
        dragging = true; startX = e.clientX; dx = 0; id = e.pointerId;
        pane.classList.add("is-dragging");
        try { head.setPointerCapture(id); } catch (err) { /* not fatal */ }
    });

    head.addEventListener("pointermove", function (e) {
        if (!dragging || e.pointerId !== id) { return; }
        dx = e.clientX - startX;
        set(dx);
    });

    function end() {
        if (!dragging) { return; }
        dragging = false;
        pane.classList.remove("is-dragging");
        var far = Math.abs(dx) > (pane.offsetWidth || 1) * THRESHOLD;
        if (far) {
            /* Let it leave in the direction it was thrown, then close. The
               close itself resets pane state, so nothing is left half-shut. */
            pane.classList.add("is-dismissing");
            set(dx > 0 ? (pane.offsetWidth + 40) : -(pane.offsetWidth + 40));
            window.setTimeout(function () {
                pane.classList.remove("is-dismissing");
                clear();
                if (window.npClosePane2) { window.npClosePane2(); }
            }, 160);
        } else {
            clear();
        }
        dx = 0; id = null;
    }
    head.addEventListener("pointerup", end);
    head.addEventListener("pointercancel", end);

    /* ---- FLICK TO DISMISS, on the drawing itself -------------------

       Speed is what separates the two intents, because the target
       cannot: a slow drag on a drawing means pan, and a fast throw
       means get rid of it. Both are the same finger on the same pixels.

       Three conditions must hold together, so ordinary panning can
       never trip it by accident:

         velocity   > 1.1 px/ms over the last 90ms - far above the speed
                      anyone moves at while reading a drawing
         distance   > 70px - a flick, not a twitch
         direction  horizontal by at least 2:1 - panning down a tall
                      sheet must never read as a sideways throw

       Pane 1 is excluded here as it is on the handle: the anchor is not
       dismissible by any gesture. */

    var body2 = document.getElementById("np-body2");
    if (!body2) { return; }

    var samples = [];
    var V_MIN = 1.1, D_MIN = 70, RATIO = 2;

    body2.addEventListener("pointerdown", function (e) {
        samples = [{ x: e.clientX, y: e.clientY, t: performance.now() }];
    });

    body2.addEventListener("pointermove", function (e) {
        var now = performance.now();
        samples.push({ x: e.clientX, y: e.clientY, t: now });
        /* Only the tail matters - a long slow pan that ends in a flick is
           still a flick, and a flick that ends in a pause is not. */
        while (samples.length > 2 && now - samples[0].t > 90) { samples.shift(); }
    });

    function flickEnd() {
        if (samples.length < 2) { samples = []; return; }
        var a = samples[0], b = samples[samples.length - 1];
        var dt = b.t - a.t;
        if (dt <= 0) { samples = []; return; }
        var fx = b.x - a.x, fy = b.y - a.y;
        var vx = Math.abs(fx) / dt;
        samples = [];

        if (vx < V_MIN) { return; }
        if (Math.abs(fx) < D_MIN) { return; }
        if (Math.abs(fx) < Math.abs(fy) * RATIO) { return; }

        pane.classList.add("is-dismissing");
        set(fx > 0 ? (pane.offsetWidth + 40) : -(pane.offsetWidth + 40));
        window.setTimeout(function () {
            pane.classList.remove("is-dismissing");
            clear();
            if (window.npClosePane2) { window.npClosePane2(); }
        }, 160);
    }
    body2.addEventListener("pointerup", flickEnd);
    body2.addEventListener("pointercancel", function () { samples = []; });
}());

/* =======================================================================
   VOICE - a second way to reach the controls that are already here.

   CLAUDE-VOICE-CONSISTENCY-02. Two rules, and everything below follows
   from them:

     1. It uses the SHARED engine (static/js/voice_input.js). This surface
        does not get its own recogniser, because the last page that had one
        needed the same defect fixed twice.

     2. It DISPATCHES REAL CONTROLS. Every branch ends in .click() on a
        button that is on the page and reachable by finger and by Tab.
        Nothing here performs an action itself, so voice cannot become a
        path around a guard the visible control carries - and a control
        that is disabled, absent or hidden simply cannot be spoken to
        either.

   The vocabulary is deliberately small and closed. An unrecognised
   sentence is reported back verbatim and does nothing: on a coordination
   surface, guessing which sheet someone meant is the one failure mode
   worth designing against.
   ======================================================================= */
(function () {
    "use strict";
    var button = document.getElementById("np-voice-button");
    var status = document.getElementById("np-voice-status");
    if (!button || typeof window.ArchioskVoiceInput !== "function") { return; }

    /* Recognisers punctuate and space sheet marks unpredictably - "A801"
       comes back as "a 801", "A-801", "eight oh one". Folding to bare
       alphanumerics catches the first two honestly; the spelled-out form is
       deliberately NOT guessed at. */
    function fold(text) {
        return (text || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    }

    function fire(el) {
        if (!el || el.disabled || el.hidden) { return false; }
        el.click();
        return true;
    }

    function dispatch(transcript) {
        var folded = fold(transcript);
        var lower = (transcript || "").toLowerCase();

        /* A named sheet wins over everything else: it is the most specific
           thing anyone says on this screen. */
        var sibs = document.querySelectorAll("[data-sib]");
        for (var i = 0; i < sibs.length; i += 1) {
            if (folded.indexOf(fold(sibs[i].getAttribute("data-sib"))) !== -1) {
                if (fire(sibs[i])) { return sibs[i].getAttribute("data-sib"); }
            }
        }

        /* ORDERED BY SPECIFICITY, and the order is load-bearing: the first
           match wins, so a short pattern placed early swallows the sentences
           a longer one was meant to catch. "go back" is the case that
           matters - it contains a bare "go", and GO used to be listed
           first, so the commonest navigation phrase on this screen would
           have opened a coordination pane instead of leaving. */
        var COMMANDS = [
            { re: /\bgo back\b|\bback\b|surfaces|all drawings/, id: "np-return", said: "Back to surfaces" },
            { re: /close( the)?( second)?( pane)?( two| 2)?\b/, id: "np-close2", said: "Close pane 2" },
            { re: /ask go\b|washroom detail|find the detail|^go\b|\bgo\b(?! (back|to))/, id: "np-ask-go", said: "Ask GO" },
            { re: /\bsplit\b|second pane|summon/, id: "np-split", said: "Split" },
            { re: /preferences|settings|engine/, id: "np-prefs-open", said: "Engine preferences" },
        ];
        for (var c = 0; c < COMMANDS.length; c += 1) {
            if (COMMANDS[c].re.test(lower)) {
                if (fire(document.getElementById(COMMANDS[c].id))) { return COMMANDS[c].said; }
            }
        }

        /* View controls belong to a pane, and there can be two. "Pane 2"
           addresses the second; anything else means the one in front. */
        var VIEW = [
            { re: /zoom in|closer|magnif/, act: "in", said: "Zoom in" },
            { re: /zoom out|further|smaller/, act: "out", said: "Zoom out" },
            { re: /\bfit\b|whole sheet|fit the page/, act: "fit", said: "Fit" },
            { re: /rotate (left|counter)|anticlockwise/, act: "rccw", said: "Rotate left" },
            { re: /rotate( right)?|clockwise/, act: "rcw", said: "Rotate right" },
            { re: /reset|native|upright/, act: "reset", said: "Reset" },
        ];
        var pane = /pane ?(two|2)|second pane/.test(lower) ? "2" : "1";
        for (var v = 0; v < VIEW.length; v += 1) {
            if (VIEW[v].re.test(lower)) {
                var bar = document.querySelector('.np-view[data-pane="' + pane + '"]');
                var btn = bar && bar.querySelector('[data-act="' + VIEW[v].act + '"]');
                if (fire(btn)) { return VIEW[v].said + " \u00b7 pane " + pane; }
            }
        }
        return null;
    }

    var heard = "";
    var final = false;

    var voice = window.ArchioskVoiceInput({
        buttonId: "np-voice-button",
        statusId: "np-voice-status",
        onStart: function () { heard = ""; final = false; },
        onTranscript: function (transcript, isFinal) {
            heard = transcript;
            if (isFinal) { final = true; }
        },
        onEnd: function () {
            if (!final || !heard.trim()) { return; }
            var did = dispatch(heard.trim());
            if (!voice) { return; }
            if (did) {
                voice.setStatus(did, false);
            } else {
                /* Verbatim, and no action. Reporting what was actually heard
                   is the difference between "I did not understand" and the
                   reader believing the microphone is deaf. */
                voice.setStatus("\u201c" + heard.trim() + "\u201d \u2014 no control here matches that.", true);
            }
            if (status) {
                window.setTimeout(function () { voice.setStatus("", false); }, 3200);
            }
        },
    });
}());
