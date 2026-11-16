// Main Airport's world record defines the runway. Older recordings and the
// offline preview predate that record and retain the previous painted bounds.
const LEGACY_PRIMARY = Object.freeze({
  id: '08/26', x0: -716, x1: 3900, yc: 0, width: 30,
  shoulder_width: 4, elevation_m: 0, default_start: Object.freeze([-700, 0]),
});

export function resolvePrimaryRunway(world) {
  const source = world?.runway ?? LEGACY_PRIMARY;
  const finite = ['x0', 'x1', 'yc', 'width', 'shoulder_width', 'elevation_m'];
  if (source.id !== '08/26' || !finite.every(key => Number.isFinite(source[key])) ||
      source.x1 <= source.x0 || source.width <= 0 || source.shoulder_width < 0 ||
      !Array.isArray(source.default_start) || source.default_start.length !== 2 ||
      !source.default_start.every(Number.isFinite)) {
    throw new Error('Invalid Main Airport runway record');
  }
  return {...source, default_start: [...source.default_start],
    length: source.x1 - source.x0, center: [(source.x0 + source.x1) / 2, source.yc]};
}

export function primaryRunwayCues(world) {
  const runway = resolvePrimaryRunway(world);
  const {x0, x1, yc, width, shoulder_width, elevation_m, length, center} = runway;
  const edgeLights = [], thresholdLights = [];
  for (let x = x0 + 6; x <= x1 - 10; x += 25) {
    const color = x < x0 + 300 || x > x1 - 300 ? '#ffb822' : '#fff3d0';
    for (const y of [yc - width / 2 - .4, yc + width / 2 + .4]) edgeLights.push([x, y, color]);
  }
  const thresholdHalf = width / 2 - 1;
  for (let i = 0; i <= 8; i++) {
    const y = yc + thresholdHalf * (i / 4 - 1);
    thresholdLights.push([x0 + 1, y, '#35e060'], [x1 - 1, y, '#ff3a2a'],
      [x0, y, '#ff3a2a'], [x1 - 2, y, '#35e060']);
  }
  return {
    runway,
    surface: {x: center[0], y: yc, length, width: width + 2 * shoulder_width, z: elevation_m + .021},
    centerline: [x0 + 20, x1 - 20],
    numbers: [{label: '08', x: x0 + 36, rotation: Math.PI / 2},
      {label: '26', x: x1 - 36, rotation: -Math.PI / 2}],
    thresholdBands: [{x: x0, color: '#22e055'}, {x: x1 - 3, color: '#ff2211'}],
    edgeLights, thresholdLights,
    // These are decorative PAPI housings; their lamps do not indicate a live glide slope.
    papi: [{x: x0 + 300, y: yc - width / 2 - 9, rotation: 0},
      {x: x1 - 300, y: yc + width / 2 + 9, rotation: Math.PI}],
  };
}
