document.addEventListener('DOMContentLoaded', () => {
    const chips = document.querySelectorAll('.registry-filter .chip');
    const rows = document.querySelectorAll('#registry-table tbody tr[data-category]');

    chips.forEach((chip) => {
        chip.addEventListener('click', () => {
            chips.forEach((c) => c.classList.remove('active'));
            chip.classList.add('active');

            const category = chip.dataset.category;
            rows.forEach((row) => {
                row.hidden = Boolean(category) && row.dataset.category !== category;
            });
        });
    });
});
