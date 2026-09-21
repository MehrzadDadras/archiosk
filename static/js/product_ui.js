/* Presentation only: density, progressive disclosure and accessible table labels. */
(() => {
  const body = document.body;
  document.querySelectorAll('[data-ui-density-choice]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.uiDensityChoice === body.dataset.uiDensity));
    button.addEventListener('click', () => {
      const mode = button.dataset.uiDensityChoice;
      if (!['work', 'inspect'].includes(mode)) return;
      body.dataset.uiDensity = mode;
      document.querySelectorAll('[data-ui-density-choice]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
      const url = new URL(location.href);
      url.searchParams.set('density', mode);
      history.replaceState(null, '', url);
      document.querySelectorAll('form[aria-label="Reload current review"]').forEach(form => {
        let field = form.querySelector('[name=density]');
        if (!field) { field = document.createElement('input'); field.type = 'hidden'; field.name = 'density'; form.append(field); }
        field.value = mode;
      });
      document.querySelectorAll('a').forEach(link => { if (link.textContent.trim() === 'Reload') link.href = url.href; });
    });
  });
  document.querySelectorAll('.survey-evaluation table').forEach(table => {
    const headers = [...table.querySelectorAll('thead th')].map(cell => cell.textContent.trim());
    if (!headers.length || table.querySelector('tbody [colspan], tbody [rowspan]')) return;
    table.classList.add('ui-stack-table');
    table.querySelectorAll('tbody tr').forEach(row => [...row.cells].forEach((cell, index) => {
      cell.dataset.columnLabel = headers[index] || '';
    }));
  });
})();
