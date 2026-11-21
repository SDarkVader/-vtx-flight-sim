import {knownAircraft, flownEvidence} from './aircraft-selection.js?v=1';
import {SCENERY_VEHICLES} from './scenery-view.js?v=20261117-traffic-10';

const byId = id => document.getElementById(id);
const airframe = byId('airframe'), main = byId('main-aircraft'), start = byId('start');
const startConfiguration = byId('phantom-start'), status = byId('validation');
const mainAircraft = ['phantom-a10c', 'r6'];
let view, pending = false, boatId = null;

function showActual(next) {
  view = next;
  if (pending) return;
  const known = knownAircraft(airframe, view);
  const actual = known ? view.observation.configuration.airframe_variant : '';
  airframe.value = actual;
  main.value = boatId ? 'boat:' + boatId : mainAircraft.includes(actual) ? actual : '';
  main.disabled = airframe.disabled = false;
  startConfiguration.disabled = !!view.active;
  if (view.start_configuration) startConfiguration.value = view.start_configuration;
  start.disabled = !!view.active || !known || !!boatId || document.documentElement.dataset.vtxWorldUnavailable === '1';
  byId('aircraft-evidence').textContent = flownEvidence(view);
  byId('aircraft-evidence').hidden = !byId('aircraft-evidence').textContent;
  byId('r6-pilot-record').hidden = actual !== 'r6-argon-20261103';
  if (known) start.firstChild.textContent = 'New ' + airframe.selectedOptions[0].textContent.split(' · ')[0] + ' mission ';
  else if (!boatId) status.textContent = 'Choose a vehicle to begin.';
}

async function request(path, body) {
  const options = body === undefined ? {cache:'no-store'} :
    {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw Error(result.detail || 'HTTP ' + response.status);
  return result;
}

async function preview(variant, selecting, position, targetEnvironment) {
  const previous = view;
  const same = previous?.observation?.configuration?.airframe_variant === variant;
  if (selecting && same && previous.active) {
    document.dispatchEvent(new CustomEvent('vtx-aircraft-selected', {detail:previous}));
    return;
  }
  const current = previous?.environment?.key || byId('environment-select')?.value;
  const environment = targetEnvironment || (variant === 'r6-argon-20261103' ? 'r6-valley-20261103' :
    selecting && current === 'r6-valley-20261103' ? 'airport' : current);
  const choice = {variant, departure:position || byId('dep').value.split(',').map(Number)};
  if (selecting && environment === current)
    document.dispatchEvent(new CustomEvent('vtx-aircraft-departure-request', {detail:choice}));
  const payload = {airframe_variant:variant, start_configuration:startConfiguration.value, environment};
  if (environment === current) payload.departure = choice.departure;
  if (previous?.active) payload.save_run_id = previous.run_id;
  const result = await request('/api/model-preview', payload);
  if (result.observation?.configuration?.airframe_variant !== variant ||
      (environment && result.environment?.key !== environment)) throw Error('Server returned a different aircraft or environment.');
  view = result;
  document.dispatchEvent(new CustomEvent('vtx-aircraft-selected', {detail:result}));
  status.textContent = previous?.active ? 'Previous flight saved. Ready at the selected departure.' :
    'Selected ' + variant + '; no flight started.';
}

function board(value) {
  const scenic = value.startsWith('scenery:');
  return new Promise((resolve, reject) => {
    const event = new CustomEvent(scenic ? 'vtx-ride-scenery' : 'vtx-choose-boat', {cancelable:true,
      detail:scenic ? {vehicleId:value.slice(8),resolve,reject} : {boatId:value.slice(5),resolve,reject}});
    document.dispatchEvent(event);
    if (!event.defaultPrevented) reject(Error('Cockpit is still loading.'));
  });
}

async function choose(value, {selecting=true, position, environment} = {}) {
  if (pending || !value) throw Error('Wait for a vehicle selection.');
  pending = true;
  let failure;
  document.documentElement.dataset.vtxPreviewPending = '1';
  main.disabled = airframe.disabled = startConfiguration.disabled = start.disabled = true;
  try {
    if (value.startsWith('boat:') || value.startsWith('scenery:')) {
      await board(value);
      if (value.startsWith('boat:')) status.textContent = 'Ricochet helm selected.';
    } else {
      await preview(value, selecting, position, environment);
    }
  } catch (error) {
    try {view = await request('/api/view');} catch {view = null;}
    failure = error.message;
    throw error;
  } finally {
    pending = false;
    document.documentElement.dataset.vtxPreviewPending = '0';
    if (view) {
      showActual(view);
      document.dispatchEvent(new CustomEvent('vtx-selection-settled',{detail:view}));
    }
    else main.disabled = airframe.disabled = false;
    if (failure) status.textContent = failure;
  }
}

const dialog = document.createElement('dialog');
dialog.innerHTML = '<div class="dialog-head"><h2>Choose vehicle</h2><button type="button" data-vehicle-close>Close</button></div><label class="control-label">Vehicle<select data-vehicle-choice></select></label><p data-vehicle-status role="status"></p><button type="button" data-vehicle-select>Load vehicle</button>';
document.body.append(dialog);
const choice = dialog.querySelector('[data-vehicle-choice]'), message = dialog.querySelector('[data-vehicle-status]');
const load = dialog.querySelector('[data-vehicle-select]');
dialog.querySelector('[data-vehicle-close]').addEventListener('click', () => dialog.close());
function openSelector(historicalOnly) {
  const group = (label, options) => {
    const node = document.createElement('optgroup'); node.label = label; node.append(...options); return node;
  };
  const placeholder = new Option('Choose a vehicle', ''); placeholder.disabled = true;
  const history = group('Historical and experimental aircraft', Array.from(airframe.options)
    .filter(o=>o.value && !mainAircraft.includes(o.value)).map(o=>o.cloneNode(true)));
  choice.replaceChildren(placeholder, ...(historicalOnly ? [history] : [
    group('Main vehicles', Array.from(main.options).filter(o=>o.value).map(o=>o.cloneNode(true))),
    history, group('Ride as passenger', SCENERY_VEHICLES.map(v=>new Option(v.label, 'scenery:'+v.id)))]));
  choice.value = historicalOnly && main.value ? '' : main.value || airframe.value;
  message.textContent = view?.active ? 'Changing aircraft saves the current flight in Flight records.' : '';
  dialog.showModal();
}
byId('models').addEventListener('click', () => openSelector(false));
byId('historical-vehicles').addEventListener('click', () => openSelector(true));
load.addEventListener('click', async () => {
  if (!choice.value) {message.textContent = 'Choose a vehicle.'; return;}
  load.disabled = true; message.textContent = 'Loading vehicle…';
  try {await choose(choice.value); dialog.close();}
  catch (error) {message.textContent = error.message;}
  finally {load.disabled = false;}
});
for (const menu of [main, airframe]) menu.addEventListener('change', () => {
  if (!menu.disabled) void choose(menu.value).catch(()=>{});
});
startConfiguration.addEventListener('change', () => {
  if (!startConfiguration.disabled) void choose(airframe.value, {selecting:false}).catch(()=>{});
});
document.addEventListener('vtx-preview-start', e => {
  choose(airframe.value, {selecting:false, position:e.detail.position, environment:e.detail.environment}).then(e.detail.resolve, e.detail.reject);
});
document.addEventListener('vtx-vehicle-focus', e => {
  boatId = e.detail.boatId || null;
  if (view && !pending) showActual(view);
});
document.addEventListener('vtx-aircraft-state', e => {showActual(e.detail);});
request('/api/view').then(next => {if (!view && !pending) showActual(next);}).catch(() => {
  if (!view) status.textContent = 'Aircraft status unavailable.';
});
