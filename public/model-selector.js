import {knownAircraft, flownEvidence} from './aircraft-selection.js?v=1';
import {SCENERY_VEHICLES} from './scenery-view.js?v=20261117-traffic-10';

const airframe = document.getElementById('airframe');
const mainAircraft = document.getElementById('main-aircraft');
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
    mainAircraft.disabled = true;
    startConfiguration.disabled = true;
    start.disabled = true;
  }
}

function showActual(view) {
  const actual = view.observation?.configuration?.airframe_variant;
  mainAircraft.disabled = !!view.active;
  mainAircraft.value = view.inspection_selection_known !== false && ['r6', 'phantom-a10c'].includes(actual) ? actual : '';
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

async function applyPreview(variant, {selecting = false} = {}) {
  if (pending || airframe.disabled) return;
  setBusy(true);
  status.textContent = 'Loading the selected aircraft…';
  try {
    const envSelect = document.getElementById('environment-select');
    const payload = {airframe_variant: variant, start_configuration: startConfiguration.value,
      departure: document.getElementById('dep').value.split(',').map(Number)};
    const departureChoice = {variant, departure: payload.departure};
    if (selecting) document.dispatchEvent(new CustomEvent('vtx-aircraft-departure-request', {detail: departureChoice}));
    payload.departure = departureChoice.departure;
    if (envSelect?.value) payload.environment = envSelect.value;
    const response = await fetch('/api/model-preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.detail || `HTTP ${response.status}`);
    if (result.observation?.configuration?.airframe_variant !== variant) throw Error('Server returned a different aircraft.');
    if (departureChoice.original) document.dispatchEvent(new CustomEvent('vtx-aircraft-departure-applied', {detail: departureChoice}));
    if (selecting) document.dispatchEvent(new CustomEvent('vtx-aircraft-selected', {detail: result}));
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
      mainAircraft.disabled = true;
      // Keep controls disabled until a fresh server view arrives.
    }
  }
}

const vehicleDialog = document.createElement('dialog');
vehicleDialog.innerHTML = `<div class="dialog-head"><h2>Choose vehicle</h2><button type="button" data-vehicle-close>Close</button></div>
  <label class="control-label">Vehicle<select data-vehicle-choice></select></label>
  <p data-vehicle-status role="status"></p>
  <button type="button" data-vehicle-select>Select vehicle</button>`;
document.body.append(vehicleDialog);
const vehicleChoice = vehicleDialog.querySelector('[data-vehicle-choice]');
const vehicleStatus = vehicleDialog.querySelector('[data-vehicle-status]');
const chooseButton = vehicleDialog.querySelector('[data-vehicle-select]');
vehicleDialog.querySelector('[data-vehicle-close]').addEventListener('click', () => vehicleDialog.close());
document.getElementById('models').addEventListener('click', () => {
  const placeholder = new Option('Choose a vehicle', '');
  placeholder.disabled = true;
  const aircraft = document.createElement('optgroup');
  aircraft.label = 'Current aircraft · in development';
  const earlier = document.createElement('optgroup');
  earlier.label = 'Earlier and experimental aircraft';
  for (const option of airframe.options) {
    if (!option.value) continue;
    const item = option.cloneNode(true);
    item.disabled = option.disabled || airframe.disabled;
    (option.value === 'phantom-a10c' || option.value === 'r6' ? aircraft : earlier).append(item);
  }
  const boats = document.createElement('optgroup');
  boats.label = 'Ricochet boats';
  boats.append(new Option('Ricochet · Airport Landing', 'boat:ricochet-airport'),
    new Option('Ricochet · Lantern Marina', 'boat:ricochet-marina'));
  const passengers = document.createElement('optgroup');
  passengers.label = 'Ride as passenger';
  for (const vehicle of SCENERY_VEHICLES) passengers.append(new Option(vehicle.label, `scenery:${vehicle.id}`));
  vehicleChoice.replaceChildren(placeholder, aircraft, boats, passengers, earlier);
  vehicleChoice.value = '';
  vehicleStatus.textContent = airframe.disabled ? 'Save or end your active aircraft flight before choosing another aircraft. Boats and passenger seats remain available.' : '';
  vehicleDialog.showModal();
});
chooseButton.addEventListener('click', async () => {
  const value = vehicleChoice.value;
  if (!value) {vehicleStatus.textContent = 'Choose a vehicle.'; return;}
  if (!value.startsWith('boat:') && !value.startsWith('scenery:')) {
    if (airframe.disabled) {vehicleStatus.textContent = 'Save or end the current flight before switching aircraft.'; return;}
    airframe.value = value;
    airframe.dispatchEvent(new Event('change', {bubbles: true}));
    vehicleDialog.close();
    airframe.scrollIntoView({block: 'center', behavior: 'smooth'});
    return;
  }
  chooseButton.disabled = true;
  const scenic = value.startsWith('scenery:');
  vehicleStatus.textContent = scenic ? 'Boarding passenger flight…' : 'Selecting boat…';
  try {
    await new Promise((resolve, reject) => document.dispatchEvent(new CustomEvent(scenic?'vtx-ride-scenery':'vtx-choose-boat',
      {detail: scenic?{vehicleId:value.slice(8),resolve,reject}:{boatId:value.slice(5),resolve,reject}})));
    vehicleDialog.close();
  } catch (error) {
    vehicleStatus.textContent = error.message;
  } finally {
    chooseButton.disabled = false;
  }
});
airframe.addEventListener('change', () => { void applyPreview(airframe.value, {selecting: true}); });
mainAircraft.addEventListener('change', () => {
  if (mainAircraft.disabled || airframe.disabled) return;
  airframe.value = mainAircraft.value;
  void applyPreview(airframe.value, {selecting: true});
});
document.addEventListener('vtx-aircraft-state', event => {if (!pending) showActual(event.detail);});
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
