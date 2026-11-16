// The extended airport's old default is partway down the new runway.
// Keep an explicitly selected departure, including the old point, intact.
export function missionDeparture({departure, explicit, variant, environment, runway}) {
  if (environment === 'airport' && variant.startsWith('phantom') && !explicit &&
      departure[0] === -700 && departure[1] === 0) {
    const west = Number.isFinite(runway?.x0) ? runway.x0 + 15 : -3885;
    return [west, 0];
  }
  return [...departure];
}
