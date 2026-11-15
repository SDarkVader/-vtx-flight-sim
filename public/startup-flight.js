// Opening the cockpit may reveal its controls, but must not choose an aircraft
// or environment. The server's existing state remains authoritative.
function openPanels() {
  const cockpit = document.getElementById('cockpit-workspace');
  if (!cockpit) return;
  for (const [cls, id] of [['mission-open', 'mission-drawer'], ['controls-open', 'controls-drawer']]) {
    if (!cockpit.classList.contains(cls)) {
      document.querySelector(`.workspace-tabs button[aria-controls="${id}"]`)?.click();
    }
  }
}

document.getElementById('airframe')?.addEventListener('change', openPanels);
document.getElementById('start')?.addEventListener('click', openPanels);
openPanels();
