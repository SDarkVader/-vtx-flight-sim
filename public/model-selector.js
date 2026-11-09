const airframe = document.getElementById('airframe');
const startConfiguration = document.getElementById('phantom-start');
const status = document.getElementById('validation');
const start = document.getElementById('start');
let loadedVariant = airframe.value;
let pending = false;

function setBusy(value) {
  pending = value;
  document.documentElement.dataset.vtxPreviewPending = value ? '1' : '0';
  if (value) {
    airframe.disabled = true;
    startConfiguration.disabled = true;
    start.disabled = true;
  }
}

function showActual(view) {
  const actual = view.observation?.configuration?.airframe_variant;
  if (actual && [...airframe.options].some(option => option.value === actual)) {
    airframe.value = actual;
    loadedVariant = actual;
    const title = airframe.selectedOptions[0].textContent.split(' · ')[0];
    start.firstChild.textContent = `New ${title} mission `;
  }
  airframe.disabled = !!view.active;
  startConfiguration.disabled = !!view.active;
  start.disabled = !!view.active;
}

async function currentView() {
  const response = await fetch('/api/view', {cache: 'no-store'});
  if (!response.ok) throw Error(`HTTP ${response.status}`);
  return response.json();
}

async function applyPreview(variant) {
  if (pending) return;
  setBusy(true);
  status.textContent = 'Loading the selected aircraft…';
  try {
    const response = await fetch('/api/model-preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({airframe_variant: variant, start_configuration: startConfiguration.value,
        departure: document.getElementById('dep').value.split(',').map(Number)}),
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.detail || `HTTP ${response.status}`);
    if (result.observation?.configuration?.airframe_variant !== variant) throw Error('Server returned a different aircraft.');
    status.textContent = `Selected ${variant}; no flight started.`;
  } catch (error) {
    status.textContent = `Selection not applied: ${error.message}`;
  } finally {
    try {
      const view = await currentView();
      setBusy(false);
      showActual(view);
    } catch {
      setBusy(false);
      airframe.value = loadedVariant;
      // Keep controls disabled until a fresh server view arrives.
    }
  }
}

document.getElementById('models').addEventListener('click', () => {
  airframe.focus();
  airframe.scrollIntoView({block: 'center', behavior: 'smooth'});
});
airframe.addEventListener('change', () => { void applyPreview(airframe.value); });
startConfiguration.addEventListener('change', () => {
  if (airframe.value.startsWith('phantom') && !airframe.disabled) void applyPreview(airframe.value);
});
document.addEventListener('vtx-preview-start', () => {
  if (!airframe.disabled) void applyPreview(airframe.value);
});
currentView().then(view => { if (!pending) showActual(view); }).catch(() => {
  status.textContent = 'Aircraft status unavailable; reconnect before starting.';
});
