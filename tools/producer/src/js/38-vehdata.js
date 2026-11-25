// =====================================================================================
// PHANTOM A10-D: the parts, the six designs and the starting tuning (25 November 2026), after the desktop Vehicle Designer
// =====================================================================================
const PARTS = [
  { id: 'fans', name: 'Wheel fans', kind: 'loop', match: /fan/i, tone: [140, 700] },
  { id: 'boosters', name: 'Boosters', kind: 'loop', match: /turbo|booster|jet/i, tone: [220, 1800] },
  { id: 'wings', name: 'Wing transformation', kind: 'move', match: /wing.?deplo/i, tone: [95, 650], len: 4 },
  { id: 'pods', name: 'Pod tilt', kind: 'move', match: /thruster/i, tone: [130, 900], len: 2.5 },
  { id: 'legs', name: 'Legs', kind: 'move', match: /geared|motor/i, tone: [160, 1100], len: 2 },
  { id: 'flaps', name: 'Flaps and stabilisers', kind: 'move', match: /flap/i, tone: [260, 1500], len: 1.5 },
  { id: 'airbrake', name: 'Air brake', kind: 'move', match: /air.?brake/i, tone: [75, 2400], len: 1 },
  { id: 'latch', name: 'Wing latch', kind: 'hit', match: /latch|lock/i, tone: [190, 2600] },
  { id: 'touchdown', name: 'Touchdown', kind: 'hit', match: /touch|landing/i, tone: [60, 500] },
  { id: 'tyres', name: 'Tyres', kind: 'loop', match: /tyre|tire/i, tone: [55, 340] },
  { id: 'wind', name: 'Wind', kind: 'loop', match: /\bwind\b|_wind_/i, tone: [0, 950] },
  { id: 'hum', name: 'Cockpit hum', kind: 'loop', match: /cockpit|hum_/i, tone: [110, 220] },
];
// Each design is a clearly different treatment; every value can then be adjusted.
const DESIGNS = [
  { name: 'A. Grounded', pitch: 1, weight: 0, edge: 0, clunk: 0.15, echo: 0, layer: 0 },
  { name: 'B. Heavy hangar', pitch: 0.75, weight: 10, edge: -4, clunk: 0.7, echo: 0.35, layer: 0.3 },
  { name: 'C. Fast and sharp', pitch: 1.35, weight: -3, edge: 8, clunk: 0.45, echo: 0, layer: 0 },
  { name: 'D. Big set-piece', pitch: 0.9, weight: 7, edge: 5, clunk: 1, echo: 0.6, layer: 0.8 },
  { name: 'E. Sci-fi servo', pitch: 1.6, weight: 2, edge: 6, clunk: 0.35, echo: 0.45, layer: 0.7 },
  { name: 'F. Worn and rough', pitch: 0.85, weight: 4, edge: 3, clunk: 0.6, echo: 0.1, layer: 0.5, rough: true },
];
const VD = {
  pitch: { label: 'Pitch', min: 0.4, max: 2, step: 0.05, fine: 0.01, fmt: v => round(v, 2) + 'x', def: 1 },
  weight: { label: 'Weight', min: -10, max: 15, step: 0.5, fine: 0.05, fmt: fmtDb, def: 0 },
  edge: { label: 'Edge', min: -12, max: 12, step: 0.5, fine: 0.05, fmt: fmtDb, def: 0 },
  clunk: { label: 'Clunk', min: 0, max: 1.5, step: 0.05, fine: 0.01, fmt: v => round(v, 2), def: 0.15 },
  echo: { label: 'Echo', min: 0, max: 1, step: 0.05, fine: 0.01, fmt: pct, def: 0 },
  layer: { label: 'Layer', min: 0, max: 1.2, step: 0.05, fine: 0.01, fmt: v => round(v, 2), def: 0 },
  volume: { label: 'Volume', min: 0, max: 4, step: 0.1, fine: 0.01, fmt: v => round(v, 2), def: 1 },
  length: { label: 'Seconds', min: 0.5, max: 10, step: 0.5, fine: 0.1, fmt: v => round(v, 2) + ' s', def: 2 },
};
const TUNING = /*TUNING_DATA*/{};
const veh = {};
for (const part of PARTS) veh[part.id] = Object.assign({ name: 'A. Grounded', pitch: 1, weight: 0, edge: 0, clunk: 0.15, echo: 0, layer: 0, volume: 1, length: part.len ?? 0, source: '', rough: false },
  TUNING[part.id], saved.veh?.[part.id]);
const plainVeh = () => Object.fromEntries(Object.entries(veh).map(([k, { token, ...rest }]) => [k, rest]));
const macro = merge({ master: 1, rpm: 0.7, thrust: 0.7 }, saved.macro);
let vehMaster = macro.master;
