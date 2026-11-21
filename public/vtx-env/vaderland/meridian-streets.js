import {MERIDIAN_STREET_PLAN} from './meridian-street-plan.js';

const FORMER_GRID = /^(North street|Terrace) \d+$/;

// The newer municipal street layout is shared by paint, lights, traffic and the map.
// Existing surveyed routes are retained so trials and established connections read the same.
export function meridianStreets(world) {
  const routes = world.vaderland?.routes ?? [];
  return world.id === 'vaderland-33' ? [...routes.filter(route=>!FORMER_GRID.test(route.name)), ...MERIDIAN_STREET_PLAN] : routes;
}
