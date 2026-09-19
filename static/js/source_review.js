/* Controls collect human display premises only. The existing server owns H. */
(() => {
  const field = document.getElementById('review-field');
  const showReading = () => {
    const option = field.selectedOptions[0];
    document.getElementById('selected-reading').textContent = option ? option.dataset.reading : 'No structured reading available';
    document.getElementById('selected-anchor').textContent = option ? JSON.stringify(JSON.parse(option.dataset.anchor), null, 2) : '';
  };
  if (field) { field.addEventListener('change', showReading); showReading(); }
  let points = null;
  const image = document.getElementById('review-original');
  const status = document.getElementById('corner-status');
  if (!image || !status) return;
  document.getElementById('pick-corners').onclick = () => {
    points = [];
    status.textContent = 'Select top-left, top-right, bottom-right, bottom-left.';
    image.scrollIntoView({block: 'center'});
  };
  image.onclick = event => {
    if (!points) return;
    event.preventDefault();
    const rect = image.getBoundingClientRect();
    points.push([(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height]);
    document.getElementById('corners').value = JSON.stringify(points);
    status.textContent = points.length + ' of 4 corners selected';
    if (points.length === 4) points = null;
  };
})();
