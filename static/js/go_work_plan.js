/* Display the persisted procedure, then submit to the existing executor.
 * GET / Reload never starts, resumes or retries a plan. */
(() => {
  const surface = document.getElementById('go-work-plans');
  if (!surface) return;
  const actions = JSON.parse(surface.dataset.actions);
  document.querySelectorAll('.coverage-requirement').forEach(row => {
    const selected = row.querySelector('[name=required_role_id]');
    const update = () => row.querySelectorAll('select').forEach(input => { input.disabled = !selected.checked; });
    selected.addEventListener('change', update);
    update();
  });
  document.querySelectorAll('.go-attention form[method="post"], form.go-review-form').forEach(form => {
    form.addEventListener('submit', async event => {
      if (form.dataset.planExecuting === 'yes') return;
      const inputs = new FormData(form);
      if (!actions.includes(inputs.get('action') || '')) return;
      event.preventDefault();
      if (form.dataset.planPending === 'yes') return;
      form.dataset.planPending = 'yes';
      const message = document.createElement('p');
      message.setAttribute('role', 'status');
      message.textContent = 'Recording the work plan…';
      surface.replaceChildren(message);
      try {
        inputs.set('declare_work_plan', 'yes');
        const response = await fetch(form.getAttribute('action') || window.location.href, {method: 'POST', body: inputs,
          credentials: 'same-origin', headers: {'Accept': 'application/json'}});
        const result = await response.json();
        if (!response.ok || !result.plan || !result.html) throw new Error(result.error || 'Could not record the work plan.');
        // HTML comes only from the escaped server template, not model output.
        surface.innerHTML = result.html;
        surface.scrollIntoView({block: 'start', behavior: 'instant'});
        // Two animation frames permit the declared procedure to paint before
        // submitting. No hidden reload/resume timer survives navigation.
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const identifier = document.createElement('input');
        identifier.type = 'hidden'; identifier.name = 'plan_id'; identifier.value = result.plan.plan_id;
        form.appendChild(identifier);
        form.dataset.planExecuting = 'yes';
        form.requestSubmit();
      } catch (error) {
        message.textContent = error.message + ' No automatic retry was made.';
        surface.replaceChildren(message);
      } finally { delete form.dataset.planPending; }
    });
  });
})();
