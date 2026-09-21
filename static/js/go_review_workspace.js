/* Navigation and disclosure only. Existing forms execute the governed owners. */
(() => {
  document.querySelectorAll('[data-open-review-section]').forEach(link => {
    link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      if (!target) return;
      for (let node = target; node; node = node.parentElement) {
        if (node.tagName === 'DETAILS') node.open = true;
      }
      target.scrollIntoView({block: 'start'});
    });
  });
})();
