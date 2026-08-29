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
            if (origin) { origin.focus(); }
        }
    }

    function showSurface(fieldId) {
        openedFieldId = fieldId || null;
        body.setAttribute("data-scene", "surface");
        var back = document.getElementById("np-return");
        if (back) { back.focus(); }
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
        if (window.npViews && window.npViews["2"]) { window.npViews["2"].reset(); }
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

    function setOverlay(on) {
        if (!overlay || !semToggle) { return; }
        overlay.hidden = !on;
        semToggle.setAttribute("aria-pressed", on ? "true" : "false");
        semToggle.textContent = "Semantic overlay: " + (on ? "ON" : "OFF");
        if (!on && tip) { tip.hidden = true; }
    }
    window.npSetOverlay = setOverlay;

    if (semToggle) {
        semToggle.addEventListener("click", function () { setOverlay(overlay.hidden); });
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

    function open(on) {
        if (!panel) { return; }
        panel.hidden = !on;
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
