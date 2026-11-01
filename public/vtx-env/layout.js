// Shared layout for the Vader's Taxis airfield (world metres: x east, y north, z up).
// All of this is VISUAL ONLY. Physical collision comes exclusively from
// src/vtx/world.py (heightfield + obstacle boxes/cylinders) and is untouched.
// Everything here sits on the flat central test area (|x|,|y| < 220, z = 0),
// is flush with the ground (paint/decals), or is attached to an existing
// physical building within LAYOUT.maxTrimDepth metres of its wall.

export const LAYOUT = {
  maxTrimDepth: 0.8,           // furthest any non-physical trim projects from a collider wall
  spawn: [0, 0],               // default sortie departure (A) – VTX stand 1
  destination: [-50, 20],      // default sortie destination (B)
  apron: { x0: -60, x1: 110, y0: -22, y1: 28 },
  runways: [
    { id: '08/26', name: 'Runway 08/26', center: [0, 0], length: 1432, width: 30, heading: 90, status: 'open' },
    { id: '03/21', name: 'Runway 03/21', center: [235, 0], length: 980, width: 23, heading: 55, axis: [0.57357644, 0.81915204], status: 'open' },
    { id: '18/36', name: 'Former Runway 18/36 (Closed)', center: [-180, 0], length: 800, width: 18, heading: 0, axis: [0, 1], status: 'closed' },
  ],
  runway: { x0: -716, x1: 716, yc: 0, width: 30, heading: 'E-W' },
  taxiways: [ // north-south connectors from runway edge to apron edge
    { x: -45, y0: -50, y1: -22, width: 12, id: 'A' },
    { x: 30, y0: -50, y1: -22, width: 12, id: 'B' },
    { x: 90, y0: -50, y1: -22, width: 12, id: 'C' },
  ],
  roads: [
    { id: 'west', width: 9, pts: [[-72, 3], [-72, 100]] },
    { id: 'east', width: 9, pts: [[110, 3], [185, 3], [185, 33]] },
    { id: 'north', width: 9, pts: [[20, 28], [20, 96], [115, 96], [115, 105]] },
    { id: 'workshop', width: 9, pts: [[100, -65], [150, -65], [150, -73]] },
    { id: 'operations', width: 9, pts: [[30, -80], [30, -128], [50, -128], [50, -132]] },
  ],
  pads: [
    { id: 'stand-1', x: 0, y: 0, r: 9 },
    { id: 'pad-b', x: -50, y: 20, r: 9 },
  ],
  stands: [ // painted parking stands on the apron
    { x: 40, y: 0, size: 16 }, { x: 70, y: -8, size: 16 }, { x: -30, y: -4, size: 16 },
  ],
  // Phase-2 reservation: an aircraft-sized portal on the apron's northern edge
  // leading to a descent ramp and basement flight chamber. Only floor paint is
  // built in Phase 1; nothing here is solid and the ground stays landable.
  undergroundPortal: {
    center: [-30, 43], size: [20, 30], mouthY: 28, descentDirection: [0, 1],
    note: 'RESERVED – VTX DEEP BAY ACCESS (PHASE 2)',
  },
};

// Visual theme for every physical obstacle box in world.py.
export const BUILDINGS = {
  hangar:     { kind: 'hangar',    name: 'VADER’S TAXIS HQ  /  VTX AVIATION HANGAR' },
  dispatch:   { kind: 'office',    name: 'DISPATCH  24/7' },
  tower:      { kind: 'tower',     name: 'VTX  CONTROL' },
  workshop:   { kind: 'workshop',  name: 'VTX  ENGINEERING' },
  operations: { kind: 'ops',       name: 'FLIGHT OPERATIONS' },
  terminal:   { kind: 'terminal',  name: 'PEOPLE  ·  PLACES  ·  A BRIGHTER TOMORROW' },
  arcade:     { kind: 'brick',     name: 'THE STRATEGY ROOM' },
  freight:    { kind: 'cargo',     name: 'VADER’S TAXIS  CARGO' },
  'ridge-block': { kind: 'stack',  name: 'ODD PARTS  ·  BIG IDEAS' },
};
