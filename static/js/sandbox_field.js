/* Presentation of SandboxStore objects. Outline checkboxes own selection. */
document.addEventListener('DOMContentLoaded', () => {
    const surface = document.querySelector('.sandbox-spatial');
    if (!surface) return;
    const field = surface.querySelector('.sandbox-field');
    const scroll = surface.querySelector('.sandbox-field-scroll');
    const status = surface.querySelector('[role="status"]');
    let busy = false, blocked = false, dragging = false;
    const cards = [...field.querySelectorAll('[data-field-object]')];
    function place(card, x, y) {
        card.dataset.x = Math.max(0, Math.min(10000, x));
        card.dataset.y = Math.max(0, Math.min(10000, y));
        card.style.left = card.dataset.x + 'px';
        card.style.top = card.dataset.y + 'px';
        field.style.width = Math.max(900, ...cards.map(c => +c.dataset.x + 292)) + 'px';
        field.style.height = Math.max(560, ...cards.map(c => +c.dataset.y + 260)) + 'px';
    }
    // A page must not submit an old revision while its own move is in flight.
    document.addEventListener('submit', event => {
        if (busy || dragging || blocked) {
            event.preventDefault();
            event.stopImmediatePropagation();
            event.target.dispatchEvent(new Event('composer:settled'));
            status.textContent = blocked ? 'Refresh before making further changes.' : 'Finish moving before sending.';
        }
    }, true);
    async function save(card, before) {
        if (+card.dataset.x === before.x && +card.dataset.y === before.y) return;
        busy = true;
        status.textContent = 'Saving position…';
        try {
            const response = await fetch(surface.dataset.moveUrl, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': surface.dataset.csrf},
                body: JSON.stringify({object_id: card.dataset.fieldObject,
                    x: +card.dataset.x, y: +card.dataset.y, sandbox_base: surface.dataset.base})
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Position could not be saved.');
            surface.dataset.base = result.sandbox_base;
            document.querySelectorAll('input[name="sandbox_base"]').forEach(input => { input.value = result.sandbox_base; });
            status.textContent = 'Position saved.';
        } catch (error) {
            place(card, before.x, before.y);
            blocked = true; // Response loss may hide a successful write; never guess a new revision.
            status.textContent = error.message + ' Refresh before making further changes.';
        } finally { busy = false; }
    }
    cards.forEach(card => {
        place(card, +card.dataset.x, +card.dataset.y);
        const checkbox = document.getElementById('sandbox-object-' + card.dataset.fieldObject);
        const select = card.querySelector('.sandbox-field-select');
        const reflect = () => {
            select.setAttribute('aria-pressed', String(checkbox.checked));
            card.classList.toggle('is-selected', checkbox.checked);
        };
        select.addEventListener('click', () => { checkbox.click(); });
        checkbox.addEventListener('change', reflect);
        reflect();
        const handle = card.querySelector('.sandbox-move');
        let drag = null;
        handle.addEventListener('pointerdown', event => {
            if (event.button !== 0 || busy || blocked || dragging) return;
            drag = {x: +card.dataset.x, y: +card.dataset.y, px: event.clientX, py: event.clientY,
                sx: scroll.scrollLeft, sy: scroll.scrollTop, id: event.pointerId};
            dragging = true;
            handle.setPointerCapture(event.pointerId);
            card.classList.add('is-moving');
        });
        handle.addEventListener('pointermove', event => {
            if (!drag || event.pointerId !== drag.id) return;
            place(card, drag.x + event.clientX - drag.px + scroll.scrollLeft - drag.sx,
                drag.y + event.clientY - drag.py + scroll.scrollTop - drag.sy);
        });
        function finish(event, cancel) {
            if (!drag || event.pointerId !== drag.id) return;
            const before = drag; drag = null; dragging = false;
            card.classList.remove('is-moving');
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
            if (cancel) place(card, before.x, before.y);
            else save(card, before);
        }
        handle.addEventListener('pointerup', event => finish(event, false));
        handle.addEventListener('pointercancel', event => finish(event, true));
        handle.addEventListener('lostpointercapture', event => finish(event, true));
        handle.addEventListener('keydown', event => {
            const delta = {ArrowLeft: [-20, 0], ArrowRight: [20, 0], ArrowUp: [0, -20], ArrowDown: [0, 20]}[event.key];
            if (!delta) return;
            event.preventDefault();
            if (busy || blocked || dragging) return;
            const before = {x: +card.dataset.x, y: +card.dataset.y};
            place(card, before.x + delta[0], before.y + delta[1]);
            save(card, before);
        });
    });
});
