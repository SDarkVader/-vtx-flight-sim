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

  // =========================================================================
  // AUTHORITATIVE TAXIWAY NETWORK (Curved Béziers with R >= 25m & 14m width)
  // Derived directly from VTX_fictional_airport_layout_proposal.json
  // =========================================================================
  taxiways_network: [
    {
      id: 'TWY-A',
      name: 'Taxiway Alpha',
      kind: 'polyline',
      points: [[-650, 100], [650, 100]],
      width: 14,
      holdpoints: [[-625, 100], [625, 100]]
    },
    {
      id: 'TWY-A-WEST-ENTRY',
      name: 'West Rapid Entry / Exit Fillet',
      kind: 'cubic_bezier',
      // Tuned for R_min = 28.0m (ICAO >= 25m requirement)
      control_points: [[-625, 0], [-625, 45], [-655, 75], [-650, 100]],
      width: 14,
      holdpoint: { pt: [-625, 28], heading: 0, rwy: '08/26', twy: 'A' }
    },
    {
      id: 'TWY-A-EAST-ENTRY',
      name: 'East Rapid Entry / Exit Fillet',
      kind: 'cubic_bezier',
      // Tuned for R_min = 28.0m (ICAO >= 25m requirement)
      control_points: [[625, 0], [625, 45], [655, 75], [650, 100]],
      width: 14,
      holdpoint: { pt: [625, 28], heading: 0, rwy: '08/26', twy: 'A' }
    },
    {
      id: 'TWY-B-SCHOOL',
      name: 'Taxiway Bravo (Flight Academy Link)',
      kind: 'cubic_bezier',
      control_points: [[-450, 100], [-450, 160], [-450, 200], [-450, 260]],
      width: 14,
      holdpoint: { pt: [-450, 110], heading: 0, rwy: '08-26', twy: 'B' }
    },
    {
      id: 'TWY-C-APRON',
      name: 'Taxiway Charlie (Terminal Apron Link)',
      kind: 'cubic_bezier',
      control_points: [[-245, 100], [-245, 150], [-245, 210], [-245, 260]],
      width: 14,
      holdpoint: { pt: [-245, 110], heading: 0, rwy: '08-26', twy: 'C' }
    },
    {
      id: 'TWY-D-REMOTE',
      name: 'Taxiway Delta (Remote Apron Link)',
      kind: 'cubic_bezier',
      control_points: [[585, 100], [585, 145], [630, 170], [630, 260]],
      width: 14
    },
    {
      id: 'TWY-APRON-CURVE',
      name: 'Apron High-Speed Connecting Curve',
      kind: 'cubic_bezier',
      control_points: [[-480, 280], [-500, 350], [-350, 402], [-260, 340]],
      width: 14
    }
  ],

  // =========================================================================
  // EXPANDED APRONS & VTOL / AIRCRAFT STANDS
  // =========================================================================
  aprons_expanded: [
    {
      id: 'VTX-ACADEMY-APRON',
      name: 'VTX Flight Academy Apron',
      center: [-425, 305],
      size: [560, 225]
    },
    {
      id: 'VTX-REMOTE-APRON',
      name: 'VTX Remote / Engineering Apron',
      center: [700, 355],
      size: [340, 205]
    },
    {
      id: 'R6-SOUTH-APRON',
      name: 'Argon R6 Flight Test Apron',
      center: [205, -85],
      size: [60, 55]
    }
  ],
  stands_expanded: [
    { id: 'VTX-STAND-1', name: 'Stand 1 (Academy Flight Line)', center: [-610, 285], radius: 14 },
    { id: 'VTX-STAND-2', name: 'Stand 2 (Academy Flight Line)', center: [-470, 285], radius: 14 },
    { id: 'VTX-STAND-3', name: 'Stand 3 (Terminal Apron)', center: [-340, 285], radius: 14 },
    { id: 'VTX-STAND-4', name: 'Stand 4 (Terminal Apron)', center: [-210, 285], radius: 14 },
    { id: 'VTX-STAND-5', name: 'Stand 5 (Remote Stand)', center: [590, 330], radius: 14 },
    { id: 'VTX-STAND-6', name: 'Stand 6 (Remote / MRO Stand)', center: [730, 330], radius: 14 },
    { id: 'R6-STAND-A', name: 'R6 Holding', center: [185, -90], radius: 9 },
    { id: 'R6-STAND-B', name: 'R6 Teardrop', center: [205, -90], radius: 9 },
    { id: 'R6-STAND-C', name: 'R6 Go Around', center: [225, -90], radius: 9 },
  ],

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
