// Opens the cockpit ready to fly: on a fresh, idle simulator it places the
// Phantom FX-A A10-C on the Test Sandbox runway start and brings up the Mission
// and Controls menus. Choosing a vehicle or starting a flight also brings the
// menus up. This only drives the existing selection controls; it never starts a
// flight and never touches a flight that is already running or awaiting recovery.
const STARTUP_VARIANT = 'phantom-a10c';
const STARTUP_ENVIRONMENT = 'sandbox';
const FLAG = 'vtx-startup-flight-applied';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function openPanels() {
  const cockpit = document.getElementById('cockpit-workspace');
  if (!cockpit) return;
  for (const [cls, id] of [['mission-open', 'mission-drawer'], ['controls-open', 'controls-drawer']]) {
    if (!cockpit.classList.contains(cls)) {
      document.querySelector(`.workspace-tabs button[aria-controls="${id}"]`)?.click();
    }
  }
}

async function currentView() {
  const response = await fetch('/api/view', {cache: 'no-store'});
  if (!response.ok) throw Error(`HTTP ${response.status}`);
  return response.json();
}

function alreadyApplied() {
  try { return sessionStorage.getItem(FLAG) === '1'; } catch { return false; }
}
function markApplied() {
  try { sessionStorage.setItem(FLAG, '1'); } catch { /* storage unavailable: harmless */ }
}

async function waitFor(test, timeoutMs) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    try { if (await test()) return true; } catch { /* keep waiting */ }
    await sleep(250);
  }
  return false;
}

async function placeStartupAircraft(view) {
  const airframe = document.getElementById('airframe');
  const sandbox = document.getElementById('env-sandbox');
  if (!airframe || !sandbox) return;
  if (![...airframe.options].some(option => option.value === STARTUP_VARIANT)) return;
  const configuration = view.observation?.configuration;
  // Only replace the untouched default (idle R6 on the Main Airport pad), and
  // never on a cockpit pinned to a released model.
  if (configuration?.airframe_variant !== 'r6' || configuration?.identity?.pinned) return;
  if ((view.environment?.key || 'airport') !== 'airport') return;
  if (!await waitFor(() => typeof sandbox.onclick === 'function' && !airframe.disabled, 20000)) return;
  airframe.value = STARTUP_VARIANT;
  sandbox.click();
  const placed = await waitFor(async () => {
    const now = await currentView();
    return now.environment?.key === STARTUP_ENVIRONMENT
      && now.observation?.configuration?.airframe_variant === STARTUP_VARIANT;
  }, 30000);
  // Re-run the normal selection so the mission button and status match the aircraft.
  if (placed) document.dispatchEvent(new CustomEvent('vtx-preview-start'));
}

async function startup() {
  let view;
  try { view = await currentView(); } catch { return; }
  if (!view.active && !view.error && !view.recovery_notice && !alreadyApplied()) {
    await placeStartupAircraft(view);
  }
  markApplied();
  openPanels();
}

document.getElementById('airframe')?.addEventListener('change', openPanels);
document.getElementById('start')?.addEventListener('click', openPanels);
void startup();
