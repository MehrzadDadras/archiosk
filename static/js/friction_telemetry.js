/* CLAUDE-RBAC-TOKENS-02 — noticing that somebody is stuck.

   Three signals, each of which is a real thing people do on a drawing surface
   when the software is not helping:

     rage_tap     repeated taps in the same small area in a short window
     dead_callout a press on something that LOOKS like a control and is not
     erratic_pan  rapid direction reversals while panning - hunting, not reading

   WHAT THIS DELIBERATELY IS NOT

   It is not analytics, and it must never become a click logger. Four
   constraints hold that line, and each one is asserted by a test:

     1. NOTHING IS SENT ON A SUCCESSFUL INTERACTION. A press that lands on a
        real control returns early. A dead-click detector that also fires on
        live controls is just surveillance with a friendlier name.

     2. NO PAGE CONTENT LEAVES. The payload is a signal name, the sheet
        already in the URL, and a callout target read from a data attribute
        this application itself wrote. No innerText, no textContent, no
        innerHTML, no cookies. What someone is reading is not our business;
        that they appear stuck is.

     3. AT MOST ONE REPORT PER SIGNAL PER COOLDOWN. The trigger for rage-tap
        is, by definition, somebody generating events quickly. Without a
        cooldown the detector becomes the flood - and the server's own
        MAX_OPEN_ESCALATIONS_PER_TOKEN exists because this one is not enough
        on its own.

     4. IT DEGRADES TO SILENCE. No token, no project, no fetch, or a refusal:
        nothing is retried and nothing is shown. A telemetry feature must
        never be the reason a drawing surface stops working.

   The suggestion that comes back is DETERMINISTIC and computed on the server
   from what the page already knows (see services/project_rbac.py's
   suggest_for_friction). No model is consulted on a three-tap trigger. */
(function () {
    "use strict";

    var COOLDOWN_MS = 45000;      /* per signal, per page load */
    var RAGE_TAPS = 3;            /* presses... */
    var RAGE_WINDOW_MS = 1200;    /* ...within this long... */
    var RAGE_RADIUS_PX = 44;      /* ...inside a fingertip of each other */
    var PAN_REVERSALS = 6;        /* direction changes... */
    var PAN_WINDOW_MS = 2500;     /* ...within this long */

    /* Anything that is genuinely a control. A press landing on one of these
       is a person succeeding, and nothing is reported. */
    var INTERACTIVE = "a,button,input,select,textarea,summary,[role=button]," +
                      "[data-sib],[data-field],[data-disc],[data-act],[tabindex]";

    var root = document.querySelector("[data-project-id]");
    if (!root) { return; }

    var projectId = root.getAttribute("data-project-id");
    var token = root.getAttribute("data-project-token") || "";
    if (!projectId || !token) { return; }   /* nothing to report to */

    var lastReported = {};

    function cooled(signal) {
        var now = Date.now();
        if (lastReported[signal] && now - lastReported[signal] < COOLDOWN_MS) {
            return false;
        }
        lastReported[signal] = now;
        return true;
    }

    function report(signal, extra) {
        if (!cooled(signal)) { return; }
        var body = {
            signal: signal,
            sheet_id: root.getAttribute("data-sheet-id") || null,
            callout_target: (extra && extra.calloutTarget) || null
        };
        /* Silence on every failure. A telemetry call must never be the reason
           a drawing stops working, so there is no retry and no error surface. */
        try {
            fetch("/project/" + encodeURIComponent(projectId) + "/friction", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Project-Token": token
                },
                body: JSON.stringify(body)
            }).then(function (response) {
                return response.ok ? response.json() : null;
            }).then(function (data) {
                if (data && data.suggestion) { offer(data.suggestion); }
            }).catch(function () { /* silence */ });
        } catch (err) { /* silence */ }
    }

    /* The suggestion surface. One line, dismissible, never modal - somebody
       already frustrated must not have to fight a dialog as well. */
    function offer(suggestion) {
        var existing = document.getElementById("np-friction-offer");
        if (existing) { existing.remove(); }

        var bar = document.createElement("div");
        bar.id = "np-friction-offer";
        bar.className = "friction-offer";
        bar.setAttribute("role", "status");

        var text = document.createElement("span");
        text.textContent = suggestion.message;      /* server-authored, closed set */
        bar.appendChild(text);

        if (suggestion.kind === "open_sheet" && suggestion.sheet_id) {
            var open = document.createElement("button");
            open.type = "button";
            open.className = "friction-offer-act";
            open.textContent = "Open";
            open.addEventListener("click", function () {
                var target = document.querySelector(
                    '[data-sib="' + suggestion.sheet_id + '"]');
                /* Dispatch the control the page already has, exactly as the
                   voice path does. Nothing here performs an action itself, so
                   a suggestion can never reach past what a tap could. */
                if (target) { target.click(); }
                bar.remove();
            });
            bar.appendChild(open);
        } else if (suggestion.kind === "reset_view") {
            var fit = document.createElement("button");
            fit.type = "button";
            fit.className = "friction-offer-act";
            fit.textContent = "Fit";
            fit.addEventListener("click", function () {
                var control = document.querySelector('.np-view [data-act="fit"]');
                if (control) { control.click(); }
                bar.remove();
            });
            bar.appendChild(fit);
        }

        var dismiss = document.createElement("button");
        dismiss.type = "button";
        dismiss.className = "friction-offer-dismiss";
        dismiss.setAttribute("aria-label", "Dismiss");
        dismiss.textContent = "×";
        dismiss.addEventListener("click", function () { bar.remove(); });
        bar.appendChild(dismiss);

        document.body.appendChild(bar);
        window.setTimeout(function () { bar.remove(); }, 12000);
    }

    /* ---- rage taps, and dead callouts ------------------------------- */
    var taps = [];

    document.addEventListener("pointerdown", function (event) {
        var live = event.target.closest && event.target.closest(INTERACTIVE);

        /* A press that landed on a real control is somebody succeeding.
           Constraint 1: return before anything is recorded or sent. */
        if (live && !live.hasAttribute("data-inert-callout")) {
            taps = [];
            return;
        }

        var now = Date.now();
        taps.push({ x: event.clientX, y: event.clientY, t: now });
        taps = taps.filter(function (tap) { return now - tap.t <= RAGE_WINDOW_MS; });

        /* A callout-shaped thing that does nothing: the single most useful
           signal on this surface, because it names its own target. */
        var callout = event.target.closest && event.target.closest("[data-callout-target]");
        if (callout) {
            report("dead_callout",
                   { calloutTarget: callout.getAttribute("data-callout-target") });
            return;
        }

        if (taps.length >= RAGE_TAPS) {
            var first = taps[0];
            var spread = Math.hypot(event.clientX - first.x, event.clientY - first.y);
            if (spread <= RAGE_RADIUS_PX) {
                var near = document.elementFromPoint(event.clientX, event.clientY);
                var nearby = near && near.closest && near.closest("[data-callout-target]");
                report("rage_tap", {
                    calloutTarget: nearby
                        ? nearby.getAttribute("data-callout-target") : null
                });
                taps = [];
            }
        }
    }, true);

    /* ---- erratic panning -------------------------------------------- */
    /* Hunting, not reading. Someone who knows where they are going pans in
       one direction; someone lost reverses repeatedly. */
    var panning = false;
    var lastX = 0;
    var lastDirection = 0;
    var reversals = [];

    document.addEventListener("pointerdown", function (event) {
        if (event.target.closest && event.target.closest(".np-stage, .cl-lake")) {
            panning = true;
            lastX = event.clientX;
            lastDirection = 0;
            reversals = [];
        }
    }, true);

    document.addEventListener("pointermove", function (event) {
        if (!panning) { return; }
        var dx = event.clientX - lastX;
        if (Math.abs(dx) < 4) { return; }        /* ignore hand tremor */
        var direction = dx > 0 ? 1 : -1;
        if (lastDirection !== 0 && direction !== lastDirection) {
            var now = Date.now();
            reversals.push(now);
            reversals = reversals.filter(function (t) { return now - t <= PAN_WINDOW_MS; });
            if (reversals.length >= PAN_REVERSALS) {
                report("erratic_pan", {});
                reversals = [];
            }
        }
        lastDirection = direction;
        lastX = event.clientX;
    }, true);

    function endPan() { panning = false; }
    document.addEventListener("pointerup", endPan, true);
    document.addEventListener("pointercancel", endPan, true);
}());
