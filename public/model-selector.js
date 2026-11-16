import {knownAircraft, flownEvidence} from './aircraft-selection.js?v=1';

const airframe = document.getElementById('airframe');
const startConfiguration = document.getElementById('phantom-start');
const status = document.getElementById('validation');
const start = document.getElementById('start');
const evidence = document.getElementById('aircraft-evidence');
let loadedVariant = '';
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
  evidence.textContent = flownEvidence(view);
  evidence.hidden = !evidence.textContent;
  document.getElementById('r6-pilot-record').hidden = actual !== 'r6-argon-20261103';
  if (knownAircraft(airframe, view)) {
    airframe.value = actual;
    loadedVariant = actual;
    const title = airframe.selectedOptions[0].textContent.split(' · ')[0];
    start.firstChild.textContent = `New ${title} mission `;
  } else {
    airframe.value = '';
    airframe.disabled = !!view.active;
    start.disabled = true;
    status.textContent = view.inspection_selection_known === false ? 'Choose an aircraft explicitly before starting.' : actual ? `Loaded aircraft ${actual} is not in this selector.` : 'Aircraft identity unavailable; reconnect before starting.';
    return;
  }
  airframe.disabled = !!view.active;
  startConfiguration.disabled = !!view.active;
  start.disabled = !!view.active || document.documentElement.dataset.vtxWorldUnavailable === '1';
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
    const envSelect = document.getElementById('environment-select');
    const payload = {airframe_variant: variant, start_configuration: startConfiguration.value,
      departure: document.getElementById('dep').value.split(',').map(Number)};
    if (envSelect?.value) payload.environment = envSelect.value;
    const response = await fetch('/api/model-preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
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
  start.disabled = true;
  status.textContent = 'Aircraft status unavailable; reconnect before starting.';
});
