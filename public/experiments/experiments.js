const $ = id => document.getElementById(id);
const selectedKey = 'vtx-experiment-selected';
let selected = null;
let timer = null;
let listGeneration = 0;

async function api(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let body;
    try { body = await response.json(); } catch { body = {}; }
    throw Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

async function loadParameters() {
  const value = $('aircraft').value;
  const phantom = value.startsWith('phantom');
  $('engineering').hidden = !phantom;
  const table = $('parameters');
  table.replaceChildren();
  if (!phantom) return;
  const variant = value === 'phantom-fx-p6-off' ? 'phantom-fx' : value;
  try {
    const data = await api(`/api/experiment-parameters/${variant}`);
    if ($('aircraft').value !== value) return;
    for (const item of data.parameters) {
      const tr = document.createElement('tr');
      for (const value of [item.name, JSON.stringify(item.value), item.unit, item.label, item.source,
        `${item.minimum} to ${item.maximum}${item.length ? ` (${item.length} values)` : ''}`]) {
        const td = document.createElement('td');
        td.textContent = value;
        tr.appendChild(td);
      }
      table.appendChild(tr);
    }
  } catch (error) { $('message').textContent = error.message; }
}

async function showRuns() {
  const generation = ++listGeneration;
  const data = await api('/api/experiments');
  if (generation !== listGeneration) return data.experiments;
  const box = $('runs');
  const table = $('comparison');
  box.replaceChildren();
  table.replaceChildren();
  for (const item of data.experiments) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${item.id.slice(0, 8)} · ${item.airframe_variant || 'unknown'} · ${item.status}`;
    button.addEventListener('click', () => select(item.id));
    box.appendChild(button);
  }
  const complete = data.experiments.filter(item => item.status === 'completed').slice(0, 20);
  const rows = await Promise.all(complete.map(async item => {
    try {
      const root = `/api/experiments/${item.id}/files/`;
      const summary = await api(root + 'summary.json');
      let config = '—';
      if (item.airframe_variant?.startsWith('phantom')) {
        try { config = (await api(root + 'phantom_parameters.json')).config_sha256.slice(0, 12); }
        catch { config = 'unavailable'; }
      }
      return [item.id.slice(0, 8), item.airframe_variant || 'unknown', summary.outcome || 'unknown',
        String(summary.simulated_seconds ?? 'unknown'), String(summary.max_airframe_origin_altitude_m ?? 'unknown'), config];
    } catch { return [item.id.slice(0, 8), item.airframe_variant || 'unknown', 'evidence unavailable', '—', '—', '—']; }
  }));
  if (generation !== listGeneration) return data.experiments;
  for (const row of rows) {
    const tr = document.createElement('tr');
    for (const value of row) {
      const td = document.createElement('td');
      td.textContent = value;
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  return data.experiments;
}

async function refresh() {
  const id = selected;
  if (!id) return;
  try {
    const state = await api(`/api/experiments/${id}`);
    if (id !== selected) return;
    $('message').textContent = `${id.slice(0, 8)} · ${state.status} · ${state.progress_s.toFixed(2)} simulated seconds` +
      `${state.outcome ? ' · ' + state.outcome : ''}${state.error ? ' · ' + state.error : ''}` +
      `${state.abort_reason ? ' · ' + state.abort_reason : ''}`;
    const running = ['queued', 'running'].includes(state.status);

    const evidence = $('evidence');
    evidence.replaceChildren();
    if (running) {
      timer = setTimeout(refresh, 700);
      return;
    }
    if (state.run_id) {
      const zip = document.createElement('a');
      zip.href = `/api/experiments/${id}/export`;
      zip.textContent = 'Download evidence ZIP';
      evidence.appendChild(zip);
    }
    const names = ['request.json'];
    if (state.run_id) names.push('summary.json', 'events.jsonl');
    const phantom = state.run_id && state.airframe_variant?.startsWith('phantom');
    if (phantom) names.push('phantom_parameters.json', 'phantom_ledger.json');
    if (state.outcome === 'collision') names.push('crash_ring.npz');
    $('mass-properties').textContent = 'Not available for this run.';
    if (phantom) {
      try {
        const ledger = await api(`/api/experiments/${id}/files/phantom_ledger.json`);
        if (id !== selected) return;
        $('mass-properties').textContent = JSON.stringify(ledger.actual_start_mass_properties ?? 'Not recorded in this run.', null, 2);
      } catch { /* The run may have stopped before its ledger was written. */ }
    }
    if (id !== selected) return;
    for (const name of names) {
      const link = document.createElement('a');
      link.href = `/api/experiments/${id}/files/${name}`;
      link.textContent = name;
      evidence.appendChild(link);
    }
    await showRuns();
  } catch (error) { if (id === selected) $('message').textContent = error.message; }
}

function select(id) {
  clearTimeout(timer);
  selected = id;
  try { localStorage.setItem(selectedKey, id); } catch { /* History is still on the server. */ }
  void refresh();
}

$('aircraft').addEventListener('change', loadParameters);
void loadParameters();
showRuns().then(items => {
  let last;
  try { last = localStorage.getItem(selectedKey); } catch { /* Use server history. */ }
  if (last && items.some(item => item.id === last)) select(last);
  else if (items.length) select(items[0].id);
}).catch(error => { $('message').textContent = error.message; });
