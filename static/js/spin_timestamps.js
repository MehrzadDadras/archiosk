/*
 * Spin timestamp presentation only.
 *
 * SpinRun.created_at remains the persisted source of truth and continues to
 * drive server-side ordering.  This small display pass lets the browser's
 * own locale/timezone turn that UTC ISO value into a useful local date/time.
 */
(function (root) {
    "use strict";

    function formatSpinTimestamp(value) {
        if (!value) return "";
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;

        // The application is English-language; keep the existing readable
        // date convention while leaving timezone resolution to the browser.
        var parts = new Intl.DateTimeFormat("en-US", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        }).formatToParts(date);
        var values = {};
        parts.forEach(function (part) { values[part.type] = part.value; });
        return values.year + "-" + values.month + "-" + values.day +
            " · " + values.hour + ":" + values.minute + " " + values.dayPeriod;
    }

    function renderSpinTimestamps(doc) {
        if (!doc) return;
        doc.querySelectorAll("[data-spin-timestamp]").forEach(function (node) {
            node.textContent = formatSpinTimestamp(node.getAttribute("data-spin-timestamp"));
        });
    }

    root.ArchioskSpinTimestamps = {
        format: formatSpinTimestamp,
        render: renderSpinTimestamps,
    };

    if (typeof document !== "undefined") {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", function () { renderSpinTimestamps(document); });
        } else {
            renderSpinTimestamps(document);
        }
    }
})(window);
