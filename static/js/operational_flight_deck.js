/* Anchor navigation opens the selected evidence inspector; no application writes. */
(() => {
  const reveal = () => {
    let id;
    try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (_) { return; }
    const panel = document.getElementById(id);
    if (!panel || !panel.classList.contains('fd-operation')) return;
    panel.open = true;
    panel.scrollIntoView({block: 'start'});
    panel.querySelector('summary')?.focus({preventScroll: true});
  };
  window.addEventListener('hashchange', reveal);
  reveal();
})();
