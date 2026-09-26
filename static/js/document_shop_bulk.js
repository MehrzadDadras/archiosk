(() => {
  const form = document.getElementById('document-bulk');
  if (!form) return;
  const key = 'archiosk-document-selection:' + form.dataset.selectionScope + ':' + form.dataset.view;
  const boxes = [...document.querySelectorAll('input[form="document-bulk"][name="project_id"]:not(:disabled)')];
  let previous = [];
  try { previous = JSON.parse(sessionStorage.getItem(key) || '[]'); } catch (_) {}
  boxes.forEach(box => { box.checked = Array.isArray(previous) && previous.includes(box.value); });
  function refresh() {
    const selected = boxes.filter(box => box.checked);
    document.getElementById('document-selected-count').textContent = selected.length + ' selected';
    const actions = document.getElementById('document-bulk-actions');
    if (actions) actions.hidden = !selected.length;
    const compare = document.getElementById('document-compare');
    if (compare) compare.disabled = selected.length !== 2 || selected.some(box => box.dataset.compatible !== 'true');
    try { sessionStorage.setItem(key, JSON.stringify(selected.map(box => box.value))); } catch (_) {}
  }
  boxes.forEach(box => box.addEventListener('change', refresh));
  document.getElementById('document-select-all').addEventListener('click', () => { boxes.forEach(box => { box.checked = true; }); refresh(); });
  document.getElementById('document-clear-selection').addEventListener('click', () => { boxes.forEach(box => { box.checked = false; }); refresh(); });
  refresh();
})();
