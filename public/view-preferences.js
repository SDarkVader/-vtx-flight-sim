// View preferences are presentation-only. They never select an aircraft,
// change a flight, or replace a physics checkpoint.
const PREFIX = 'vtx.view.v1:';
const modes = new Set(['chase', 'cockpit', 'orbit', 'free']);
const finiteVector = value => Array.isArray(value) && value.length === 3 &&
  value.every(x => typeof x === 'number' && Number.isFinite(x) && Math.abs(x) <= 100000);
const finiteAngle = (value, limit) => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit;

function key(variant, environment) {
  const valid = x => typeof x === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(x);
  return valid(variant) && valid(environment) ? PREFIX + variant + ':' + environment : null;
}

function normalized(value) {
  if (!value || typeof value !== 'object' || !modes.has(value.mode) ||
      !finiteAngle(value.cockpitYaw, Math.PI / 2) || !finiteAngle(value.cockpitPitch, Math.PI / 3)) return null;
  const result = {mode:value.mode, cockpitYaw:value.cockpitYaw, cockpitPitch:value.cockpitPitch};
  if (finiteVector(value.chaseOffset) && Math.hypot(...value.chaseOffset) > 1e-6) result.chaseOffset = [...value.chaseOffset];
  if (finiteVector(value.freePosition) && finiteVector(value.freeAim) &&
      Math.hypot(...value.freeAim.map((v, i) => v - value.freePosition[i])) > 1e-6) {
    result.freePosition = [...value.freePosition]; result.freeAim = [...value.freeAim];
  }
  // A free view without its location cannot be faithfully restored.
  if (result.mode === 'free' && !result.freePosition) return null;
  return result;
}

export function createViewPreferenceStore(storage) {
  const memory = new Map();
  return {
    save(variant, environment, preference) {
      const id = key(variant, environment), value = normalized(preference);
      if (!id || !value) return false;
      memory.set(id, value);
      try { storage?.setItem(id, JSON.stringify(value)); } catch { /* memory still covers this session */ }
      return true;
    },
    load(variant, environment) {
      const id = key(variant, environment);
      if (!id) return null;
      if (memory.has(id)) return normalized(memory.get(id));
      try { return normalized(JSON.parse(storage?.getItem(id) || 'null')); } catch { return null; }
    },
  };
}
