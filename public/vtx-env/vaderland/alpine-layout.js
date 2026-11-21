export const ALPINE_ZONES = [
  {id: 'village', name: 'Base village', area: 'East Ridge Ski Resort', point: [3920, 810]},
  {id: 'mid', name: 'Mid-station', area: 'East Ridge Ski Resort', point: [4170, 1100]},
  {id: 'summit', name: 'Lower ridge', area: 'East Ridge Ski Resort', point: [4600, 1930]},
  {id: 'mountain-foot', name: 'Mountain station', area: 'East Ridge Ski Resort', point: [6240, 3680]},
  {id: 'high-summit', name: 'High summit', area: 'East Ridge Ski Resort', point: [7060, 4680]},
  {id: 'cirque', name: 'Cirque launch', area: 'Northwest Cirque', point: [-7000, 6450]},
  {id: 'gorge', name: 'Cascade overlook', area: 'Northwest Cirque', point: [-4760, 3920]},
  {id: 'east-launch', name: 'Rocket launch', area: 'Northeast Range', point: [6900, 4800]},
  {id: 'race-west', name: 'West bank', area: 'Lantern Race crossing', point: [-660, -1944]},
  {id: 'race-east', name: 'East bank', area: 'Lantern Race crossing', point: [-300, -1944]},
  {id: 'east-gully', name: 'Gully overlook', area: 'East Gully', point: [7700, 3400]},
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
  {id: 'storm-face', name: 'Storm Face', grade: 'Expert · high mountain', color: '#c1d7ff', width: 30,
    kind: 'descent', from: 'high-summit', to: 'mountain-foot',
    points: [highSummit, [7100,4740], [7060,4760], [7060,4780], [6980,4640], [7000,4600],
      [7000,4560], [7020,4540], [7040,4540], [7020,4520], [7020,4500], [7060,4520],
      [7000,4460], [7020,4460], [7000,4440], [6940,4420], [6940,4440], [6920,4420],
      [6920,4480], [6880,4440], [6880,4460], [6840,4440], [6860,4380], [6860,4360],
      [6840,4380], [6820,4340], [6800,4320], [6760,4300], [6740,4280], [6760,4280],
      [6800,4260], [6780,4260], [6880,4180], [6860,4180], [6820,4160], [6860,4140],
      [6840,4120], [6840,4060], [6860,4020], [6740,3820], [6720,3760], [6700,3720],
      [6660,3700], [6580,3680], [6560,3660], [6500,3660], [6400,3560], [6320,3680], mountainFoot]},
  {id: 'east-gully-run', name: 'East Gully', grade: 'Expert · unlit', color: '#dd987a',
    kind:'descent', from:'high-summit', to:'east-gully',
    points:[highSummit, [7080,4700], [7060,4720], [7060,4760], [7080,4820], [7080,4840],
      [7060,4840], [7020,4780], [7000,4720], [6960,4640], [6960,4620], [6980,4580],
      [6980,4560], [7020,4500], [7060,4520], [7080,4540], [7120,4600], [7200,4680],
      [7220,4720], [7240,4740], [7300,4780], [7320,4780], [7260,4680], [7260,4660],
      [7240,4620], [7260,4580], [7300,4540], [7320,4500], [7340,4480], [7380,4480],
      [7400,4460], [7420,4460], [7480,4420], [7480,4400], [7500,4340], [7540,4320],
      [7560,4280], [7560,4080], [7620,4040], [7660,3980], [7660,3960], [7640,3940],
      [7600,3860], [7540,3800], [7540,3780], [7580,3780], [7620,3760], [7660,3720],
      [7680,3660], [7720,3620], [7700,3560], [7680,3400], eastGully]},
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

export function distanceToTrail(x,y,path) {
  let nearest=Infinity;
  for(let i=1;i<path.length;i++){
    const [ax,ay]=path[i-1],[bx,by]=path[i],dx=bx-ax,dy=by-ay;
    const t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/Math.max(1,dx*dx+dy*dy)));
    nearest=Math.min(nearest,Math.hypot(x-ax-dx*t,y-ay-dy*t));
  }
  return nearest;
}

export function besideTrail(route,[x,y],dx,dy,clearance,side) {
  const edge=route.width*.5+clearance;
  const length=Math.hypot(dx,dy)||1;
  return [side,-side,side*1.6,-side*1.6]
    .map(offset=>[x-dy/length*edge*offset,y+dx/length*edge*offset])
    .find(([px,py])=>distanceToTrail(px,py,route.points)>=edge);
}
