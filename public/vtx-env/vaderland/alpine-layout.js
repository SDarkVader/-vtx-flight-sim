export const ALPINE_ZONES = [
  {id: 'village', name: 'Base village', area: 'East Ridge Ski Resort', point: [3920, 810]},
  {id: 'mid', name: 'Mid-station', area: 'East Ridge Ski Resort', point: [4170, 1100]},
  {id: 'summit', name: 'Lower ridge', area: 'East Ridge Ski Resort', point: [4600, 1930]},
  {id: 'mountain-foot', name: 'Mountain station', area: 'East Ridge Ski Resort', point: [6240, 3670]},
  {id: 'high-summit', name: 'High summit', area: 'East Ridge Ski Resort', point: [7060, 4680]},
  {id: 'cirque', name: 'Cirque launch', area: 'Northwest Cirque', point: [-7000, 6450]},
  {id: 'gorge', name: 'Cascade overlook', area: 'Northwest Cirque', point: [-4760, 3920]},
  {id: 'east-launch', name: 'Rocket launch', area: 'Northeast Range', point: [6900, 4800]},
  {id: 'race-west', name: 'West bank', area: 'Lantern Race crossing', point: [-660, -1944]},
  {id: 'race-east', name: 'East bank', area: 'Lantern Race crossing', point: [-300, -1944]},
  {id: 'east-gully', name: 'Gully overlook', area: 'East Gully', point: [7700, 3390]},
];

const [village, mid, summit, mountainFoot, highSummit, cirque, gorge, eastLaunch, raceWest, raceEast, eastGully] =
  ALPINE_ZONES.map(zone => zone.point);

export const ALPINE_ACCESS = [[3956.75, 992.98], [3900, 948], [3845, 893], [3865, 840], village];

export const ALPINE_LIFTS = [
  {id: 'lower-lift', name: 'Village lift', from: 'village', to: 'mid', points: [village, mid]},
  {id: 'upper-lift', name: 'Summit lift', from: 'mid', to: 'summit', points: [mid, summit]},
  {id: 'ridge-connector', name: 'Mountain connector', from: 'summit', to: 'mountain-foot',
    points: [summit, mountainFoot]},
  {id: 'high-lift', name: 'High summit lift', from: 'mountain-foot', to: 'high-summit',
    points: [mountainFoot, highSummit]},
];

export const ALPINE_ROUTES = [
  {id: 'meadow', name: 'Meadow Traverse', grade: 'Lower resort slope', color: '#9be0af', width: 36,
    kind: 'descent', from: 'mid', to: 'village', points: [mid, [4110, 1140], [4040, 1200], [3975, 1230],
      [3860, 1200], [3770, 1110], [3770, 1000], [3780, 905], [3858, 850], village]},
  {id: 'ridge', name: 'Ridge Run', grade: 'Upper resort slope', color: '#8ccfff', width: 44,
    kind: 'descent', from: 'summit', to: 'mid', points: [summit, [4500, 1795], [4380, 1630], [4270, 1480],
      [4250, 1350], [4160, 1230], mid]},
  {id: 'storm-face', name: 'Storm Face', grade: 'Expert · high mountain', color: '#c1d7ff', width: 62,
    kind: 'descent', from: 'high-summit', to: 'mountain-foot',
    points: [highSummit, [7080, 4580], [7000, 4570], [7020, 4470], [6900, 4370],
      [6890, 4250], [6760, 4200], [6710, 4110], [6570, 4060], [6470, 3900],
      [6370, 3960], [6280, 3810], mountainFoot]},
  {id: 'east-gully-run', name: 'East Gully', grade: 'Expert · unlit', color: '#dd987a',
    kind:'descent', from:'high-summit', to:'east-gully',
    points:[highSummit, [7180,4660], [7240,4570], [7340,4450], [7410,4330],
      [7520,4210], [7600,4040], [7660,3850], [7700,3620], eastGully]},
  {id: 'zipline', name: 'Ridge zip line', kind: 'zipline', color: '#ffe4b4',
    from: 'summit', to: 'mid', points: [summit, mid]},
  {id: 'race-crossing', name: 'Lantern Race zip line', kind: 'zipline', color: '#9ee8e6',
    from: 'race-west', to: 'race-east', points: [raceWest, raceEast], heights: [39, 13]},
  {id: 'cirque-face', name: 'Cirque Face', grade: 'Expert · unlit', color: '#e29980',
    kind: 'descent', from: 'cirque', to: 'gorge', points: [cirque, [-6870, 6320], [-6670, 6020],
      [-6350, 5660], [-6010, 5260], [-5670, 4840], [-5350, 4350], gorge]},
  {id: 'paraglider', name: 'Cirque to Cascade glide', color: '#f6cf83', kind: 'glider',
    from: 'cirque', to: 'gorge', points: [cirque, [-6650, 6200], [-6110, 5820], [-5570, 5160], [-5030, 4510], gorge],
    heights: [12, 280, 350, 290, 150, 12]},
  {id: 'base-jump', name: 'Cirque drop', color: '#e8ad90', kind: 'base',
    from: 'cirque', to: 'gorge', points: [cirque, [-6945, 6402], [-6870, 6320], [-6670, 6020], [-6010, 5260], gorge],
    heights: [6, 30, 50, 90, 140, 12]},
  {id: 'rocket', name: 'Northeast ridge climb', color: '#c7a7fd', kind: 'rocket',
    from: 'east-launch', to: 'east-launch', points: [eastLaunch, [7020, 4990], [6900, 5390], [6460, 5140], [6540, 4690], eastLaunch],
    heights: [12, 410, 920, 770, 250, 12]},
];
