import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';

const threeUrl = new URL('../public/vendor/three.module.js', import.meta.url).href;
const mapUrl = new URL('../public/vtx-env/harbour-map.js', import.meta.url).href;
const source = (await readFile(new URL('../public/vtx-env/harbour.js', import.meta.url), 'utf8'))
  .replace("from 'three'", `from '${threeUrl}'`)
  .replace(/from '\.\/harbour-map\.js(?:\?[^']*)?'/, `from '${mapUrl}'`);
const mod = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

function makeMiniDom() {
  class MiniNode {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.attributes = new Map();
      this.dataset = {};
      this.listeners = new Map();
      this.hidden = false;
      this.disabled = false;
      this.checked = true;
      this.value = '';
      this.textContent = '';
      this.id = '';
      this._innerHTML = '';
    }
    setAttribute(k, v) {
      this.attributes.set(k, String(v));
      if (k.startsWith('data-')) {
        const camel = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        this.dataset[camel] = String(v);
      }
      if (k === 'value') this.value = String(v);
      if (k === 'min') this.min = String(v);
      if (k === 'max') this.max = String(v);
      if (k === 'hidden') this.hidden = true;
    }
    getAttribute(k) {
      if (k.startsWith('data-')) {
        const camel = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        if (camel in this.dataset) return this.dataset[camel];
      }
      return this.attributes.get(k) ?? null;
    }
    append(...nodes) {
      this.children.push(...nodes);
    }
    replaceChildren(...nodes) {
      this.children = [...nodes];
    }
    remove() {}
    addEventListener(type, fn) {
      if (!this.listeners.has(type)) this.listeners.set(type, []);
      this.listeners.get(type).push(fn);
    }
    dispatch(type, event = {}) {
      for (const fn of this.listeners.get(type) || []) {
        fn({stopPropagation() {}, ...event});
      }
    }
    set innerHTML(html) {
      this._innerHTML = html;
      this.children = [];
      const tagRe = /<(details|summary|p|div|button|label|select|option|input|output)\b([^>]*)>([\s\S]*?)<\/\1>|<(input)\b([^>]*)>/g;
      const parseFragment = (fragment, parent) => {
        let m;
        const re = new RegExp(tagRe.source, 'g');
        while ((m = re.exec(fragment)) !== null) {
          const tag = m[1] || m[4];
          const attrStr = m[2] ?? m[5] ?? '';
          const inner = m[3] ?? '';
          const node = new MiniNode(tag);
          for (const am of attrStr.matchAll(/([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g)) {
            node.setAttribute(am[1], am[2] ?? '');
          }
          if (inner && /<[a-z]/i.test(inner)) {
            parseFragment(inner, node);
          } else {
            node.textContent = inner;
          }
          parent.append(node);
        }
      };
      parseFragment(html, this);
    }
    get innerHTML() {
      return this._innerHTML;
    }
    _all() {
      const out = [];
      const walk = n => {
        for (const c of n.children) {
          out.push(c);
          walk(c);
        }
      };
      walk(this);
      return out;
    }
    querySelectorAll(sel) {
      const all = this._all();
      if (sel === '[data-command]') return all.filter(n => n.getAttribute('data-command') !== null);
      const m = sel.match(/^\[([a-zA-Z0-9_-]+)="([^"]*)"\]$/);
      if (m) return all.filter(n => n.getAttribute(m[1]) === m[2]);
      return [];
    }
    querySelector(sel) {
      return this.querySelectorAll(sel)[0] || null;
    }
  }
  return {
    activeElement: null,
    host: new MiniNode('div'),
    createElement(tag) {
      return new MiniNode(tag);
    },
  };
}

test('harbour helm controls & selectable Option 1 / Option 2 hydro-ski profiles', async () => {
  // Static & DOM contract checks for primary trim, profile selector, profile-gated ski controls, and achieved-angle readout
  assert.ok(source.includes('data-harbour="profile"'), 'harbour.js must expose a hydro profile selector');
  assert.ok(source.includes('rc01-planing-3pt-v1'), 'harbour.js must include Option 1 (rc01-planing-3pt-v1)');
  assert.ok(source.includes('rc01-hydrofoil-ski-v1'), 'harbour.js must include Option 2 (rc01-hydrofoil-ski-v1)');
  assert.ok(source.includes('rc01-real-components-v1'), 'harbour.js must include Baseline (rc01-real-components-v1)');
  assert.ok(source.includes('data-harbour="ski-controls"'), 'harbour.js must expose profile-gated hydro-ski controls');
  assert.ok(source.includes('data-command="ski_incidence_deg"'), 'missing ski_incidence_deg slider');
  assert.ok(source.includes('data-command="ski_differential_deg"'), 'missing ski_differential_deg slider');
  assert.ok(source.includes('data-command="aft_ski_incidence_deg"'), 'missing aft_ski_incidence_deg slider');
  assert.ok(source.includes('data-command="ecu_assist"'), 'missing ecu_assist slider');
  assert.ok(source.includes('data-harbour="actuator-telemetry"'), 'missing achieved-angle / saturation telemetry readout');
  assert.ok(source.includes('<details open><summary class="section-label">Surface trim</summary>'), 'surface trim controls must be open by default');
  assert.ok(source.includes('CAPSIZED'), 'capsized status must surface in harbour telemetry');

  // Behavioral test: switching between Legacy, Option 1 (rc01-planing-3pt-v1), and Option 2 (rc01-hydrofoil-ski-v1)
  const doc = makeMiniDom();
  const actions = [];
  const makeState = (profileId = null) => {
    const hasSkis = Boolean(profileId);
    const hasAftAndEcu = profileId === 'rc01-planing-3pt-v1' || profileId === 'rc01-hydrofoil-ski-v1';
    const command = {
      throttle: 0,
      differential_thrust: 0,
      rudder_deg: 0,
      elevator_deg: 0,
      aileron_deg: 0,
      reverse_bucket: 0,
      ...(hasSkis ? {ski_incidence_deg: 4.0, ski_differential_deg: 0.0} : {}),
      ...(hasAftAndEcu ? {aft_ski_incidence_deg: 2.0, ecu_assist: 1.0} : {}),
    };
    const surface_limits = {
      throttle: {min: 0, max: 1},
      differential_thrust: {min: -1, max: 1},
      rudder_deg: {min: -30, max: 30},
      elevator_deg: {min: -20, max: 20},
      aileron_deg: {min: -25, max: 25},
      reverse_bucket: {min: 0, max: 1},
      ...(hasSkis ? {ski_incidence_deg: {min: -6, max: 12}, ski_differential_deg: {min: -4, max: 4}} : {}),
      ...(hasAftAndEcu ? {aft_ski_incidence_deg: {min: -8, max: 10}, ecu_assist: {min: 0, max: 1}} : {}),
    };
    const control_surfaces = {
      rudder: {achieved_deg: 0.0, saturated: false},
      elevator: {achieved_deg: 0.0, saturated: false},
      aileron: {achieved_deg: 0.0, saturated: false},
      ...(hasSkis ? {skis: {port_achieved_deg: 4.0, stbd_achieved_deg: 4.0, port_load_pct: 22, stbd_load_pct: 22, saturated: false}} : {}),
      ...(hasAftAndEcu ? {
        aft_ski: {achieved_deg: 2.0},
        ecu: {mode: profileId === 'rc01-hydrofoil-ski-v1' ? 'FOIL_BORNE' : 'PLANING_TRIM'},
      } : {}),
    };
    return {
      available: true,
      initialized: true,
      selectedId: 'ricochet-airport',
      berths: [{id: 'airport-landing-ricochet', name: 'Airport Landing', compatibleProfileIds: ['ricochet-concept-a']}],
      occupancy: {'airport-landing-ricochet': 'ricochet-airport'},
      boats: [{
        id: 'ricochet-airport',
        name: 'Ricochet · Airport Landing',
        variant: 'ricochet-concept-a',
        profile_id: profileId,
        position: [0, 0, 7],
        speed_mps: 0,
        dockedAt: 'airport-landing-ricochet',
        body_poses: {airframe: {position: [0, 0, 7], quaternion_wxyz: [1, 0, 0, 0]}},
        command,
        surface_limits,
        control_surfaces,
        capsized: false,
        flags: [],
      }],
    };
  };

  let currentState = makeState(null);
  const api = async (url, payload) => {
    if (url === '/api/harbour/action') {
      actions.push(payload);
      if (payload.action === 'restart') {
        currentState = makeState(payload.profile ?? null);
      }
    }
    return currentState;
  };

  const controls = mod.createHarbourControls({host: doc.host, api, document: doc});
  try {
    controls.setWorld({harbour: {waterLevelM: 7, layout: {outer: [[0, 0], [10, 0], [10, 10]]}}});
    controls.setEnabled(true);
    await controls.refresh();

    const profileSelect = controls.panel.querySelector('[data-harbour="profile"]');
    const skiControls = controls.panel.querySelector('[data-harbour="ski-controls"]');
    const actTel = controls.panel.querySelector('[data-harbour="actuator-telemetry"]');
    assert.ok(profileSelect, 'profile selector must be rendered');
    assert.equal(profileSelect.value, '');
    assert.equal(skiControls.hidden, true);

    // Select Option 1 (rc01-planing-3pt-v1)
    profileSelect.value = 'rc01-planing-3pt-v1';
    profileSelect.dispatch('change');
    await new Promise(r => setTimeout(r, 20));
    assert.equal(actions.at(-1)?.action, 'restart');
    assert.equal(actions.at(-1)?.boatId, 'ricochet-airport');
    assert.equal(actions.at(-1)?.profile, 'rc01-planing-3pt-v1');
    assert.equal(profileSelect.value, 'rc01-planing-3pt-v1');
    assert.equal(skiControls.hidden, false);
    assert.ok(actTel.textContent.includes('ECU PLANING_TRIM'), `expected ECU mode in ${actTel.textContent}`);
    assert.ok(actTel.textContent.includes('Skis P/S 4.0/4.0°'), `expected ski angles in ${actTel.textContent}`);
    assert.ok(actTel.textContent.includes('Aft 2.0°'), `expected aft ski angle in ${actTel.textContent}`);

    // Select Option 2 (rc01-hydrofoil-ski-v1)
    profileSelect.value = 'rc01-hydrofoil-ski-v1';
    profileSelect.dispatch('change');
    await new Promise(r => setTimeout(r, 20));
    assert.equal(actions.at(-1)?.action, 'restart');
    assert.equal(actions.at(-1)?.profile, 'rc01-hydrofoil-ski-v1');
    assert.equal(profileSelect.value, 'rc01-hydrofoil-ski-v1');
    assert.equal(skiControls.hidden, false);
    assert.ok(actTel.textContent.includes('ECU FOIL_BORNE'), `expected FOIL_BORNE ECU mode in ${actTel.textContent}`);
  } finally {
    controls.dispose();
  }
});
