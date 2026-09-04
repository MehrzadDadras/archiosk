/* Shared truthful elapsed-time status for existing long-running actions. */
(function () {
    'use strict';

    var active = null;
    var storageKey = 'archiosk:elapsed-action';

    function format(ms) {
        var seconds = Math.max(0, Math.floor(ms / 1000));
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor((seconds % 3600) / 60);
        seconds %= 60;
        function two(value) { return String(value).padStart(2, '0'); }
        return two(hours) + 'h:' + two(minutes) + 'm:' + two(seconds) + 's';
    }

    function region() {
        var node = document.getElementById('elapsed-action-status');
        if (node) return node;
        node = document.createElement('p');
        node.id = 'elapsed-action-status';
        node.className = 'elapsed-action-status mono';
        node.setAttribute('role', 'status');
        node.setAttribute('aria-live', 'polite');
        node.hidden = true;
        document.body.appendChild(node);
        return node;
    }

    function paint(action, state, startedAt) {
        var node = region();
        node.textContent = action + ' ' + state + ' — ' + format(Date.now() - startedAt);
        node.hidden = false;
    }

    function stop(state) {
        if (!active) return;
        window.clearInterval(active.timer);
        paint(active.action, state, active.startedAt);
        active = null;
    }

    function start(action, persist) {
        if (active) window.clearInterval(active.timer);
        var startedAt = Date.now();
        active = {action: action, startedAt: startedAt, timer: null};
        paint(action, 'started', startedAt);
        active.timer = window.setInterval(function () {
            if (active) paint(active.action, 'running', active.startedAt);
        }, 1000);
        if (persist) {
            try { sessionStorage.setItem(storageKey, JSON.stringify({action: action, startedAt: startedAt})); } catch (error) { /* unavailable */ }
        }
        return {completed: function () { stop('completed'); }, failed: function () { stop('failed'); }, cancelled: function () { stop('cancelled'); }};
    }

    function actionFor(url, text) {
        var value = ((url || '') + ' ' + (text || '')).toLowerCase();
        if (value.indexOf('delta spin') !== -1 || value.indexOf('spin_kind=delta') !== -1) return 'Delta Spin';
        if (value.indexOf('first spin') !== -1 || value.indexOf('/spin') !== -1 || value.indexOf('run_spin') !== -1) return 'First Spin';
        if (value.indexOf('gateway/orientation') !== -1 || value.indexOf('composer') !== -1 || value.indexOf('/ask') !== -1) return 'Composer';
        if (value.indexOf('export') !== -1 || value.indexOf('report') !== -1 || value.indexOf('download') !== -1) return 'Report export';
        return null;
    }

    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form || String(form.method).toLowerCase() !== 'post') return;
        var submitter = event.submitter || document.activeElement;
        var action = null;
        if (form.id === 'project-creation-form') {
            action = submitter && submitter.id === 'folder-submit-button' ? 'Folder upload and project creation' : 'File upload and project creation';
        } else {
            action = actionFor(form.action, submitter && submitter.textContent);
        }
        if (action) start(action, form.id === 'project-creation-form');
    }, true);

    var nativeFetch = window.fetch;
    if (nativeFetch) {
        window.fetch = function (input, options) {
            var url = typeof input === 'string' ? input : (input && input.url) || '';
            var action = actionFor(url, options && options.elapsedAction);
            if (!action) return nativeFetch.apply(this, arguments);
            var status = start(action, false);
            return nativeFetch.apply(this, arguments).then(function (response) {
                if (response.ok) status.completed(); else status.failed();
                return response;
            }).catch(function (error) {
                if (error && error.name === 'AbortError') status.cancelled(); else status.failed();
                throw error;
            });
        };
    }

    document.addEventListener('DOMContentLoaded', function () {
        try {
            var stored = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
            if (!stored) return;
            sessionStorage.removeItem(storageKey);
            active = {action: stored.action, startedAt: stored.startedAt, timer: null};
            stop(document.querySelector('.form-error') ? 'failed' : 'completed');
        } catch (error) { /* unavailable */ }
    });

    window.ArchioskElapsedStatus = {start: start, stop: stop, format: format};
})();
