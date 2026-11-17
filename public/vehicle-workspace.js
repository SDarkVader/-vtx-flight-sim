// Presentation and input focus only; switching panels never changes a plant or authority.
export function createVehicleWorkspace({host, harbourPanel, onAircraft, onHarbour, onChange = () => {}, document: doc = globalThis.document}) {
  const nav = doc.createElement('div');
  nav.id = 'vehicle-control-navigation'; nav.className = 'map-tools';
  const aircraft = doc.createElement('button'), harbour = doc.createElement('button');
  aircraft.type = harbour.type = 'button';
  aircraft.textContent = 'Aircraft controls'; harbour.textContent = 'Harbour & boats';
  aircraft.addEventListener('click', onAircraft); harbour.addEventListener('click', onHarbour);
  nav.append(aircraft, harbour); host.prepend(nav);
  const passenger = doc.createElement('p');
  passenger.id = 'passenger-control-note'; passenger.className = 'muted';
  passenger.textContent = 'Passenger seat. This scenic craft has no pilot controls. Use Aircraft controls to return to your physical aircraft.';
  host.append(harbourPanel, passenger);
  let mode = 'aircraft';
  const show = next => {
    if (!['aircraft', 'boat', 'passenger'].includes(next)) throw Error('Unknown vehicle controls');
    if (next !== mode) onChange(next);
    mode = next; host.dataset.vehicleControls = mode;
    for (const child of host.children) {
      if (child === nav) continue;
      child.inert = child === harbourPanel ? mode !== 'boat' : child === passenger ? false : mode !== 'aircraft';
    }
    aircraft.setAttribute('aria-pressed', String(mode === 'aircraft'));
    harbour.setAttribute('aria-pressed', String(mode === 'boat'));
  };
  show(mode);
  return {show, get mode() {return mode;}, get aircraftInput() {return mode === 'aircraft';}};
}
