// Shared Main Airport harbour projection. Chart +Y is south; world +Y is north.
export function harbourWorldPoint(harbour, point) {
  return [harbour.origin[0] + point[0], harbour.origin[1] - point[1]];
}

export function drawHarbourMap(context, projection, harbour) {
  if (!harbour?.layout?.outer?.length) return;
  const g = context, {px, py, scaleM} = projection;
  const ring = points => points.forEach((point, index) => {
    const [x, y] = harbourWorldPoint(harbour, point);
    g[index ? 'lineTo' : 'moveTo'](px(x), py(y));
  });
  g.save(); g.fillStyle = 'rgba(75, 140, 175, 0.75)'; g.strokeStyle = '#68b5d8'; g.lineWidth = 1;
  g.beginPath(); ring(harbour.layout.outer); g.closePath();
  for (const island of harbour.layout.islands || []) {ring(island.ring); g.closePath();}
  g.fill('evenodd'); g.stroke();
  for (const [index, route] of (harbour.layout.routes || []).entries()) {
    g.strokeStyle = ['#efd48b', '#a4ddd2', '#b9b7ee'][index % 3];
    g.lineWidth = 1.5; g.setLineDash([5, 5]); g.beginPath(); ring(route.points); g.stroke(); g.setLineDash([]);
    for (const stop of route.stops || []) {
      const point = route.points[stop.index]; if (!point) continue;
      const [x, y] = harbourWorldPoint(harbour, point);
      g.fillStyle = g.strokeStyle; g.beginPath(); g.arc(px(x), py(y), Math.max(2, scaleM(4)), 0, Math.PI * 2); g.fill();
    }
  }
  if(harbour.timeTrial){
    const trial=harbour.timeTrial;
    g.strokeStyle='#81e6ee';g.lineWidth=2;g.setLineDash([4,4]);g.beginPath();
    trial.points.forEach(([x,y],i)=>g[i?'lineTo':'moveTo'](px(x),py(y)));
    g.stroke();g.setLineDash([]);
    for(const [i,gate] of trial.gates.entries()){
      const [x,y]=gate.center, [nx,ny]=gate.normal, d=gate.width_m*.5;
      g.strokeStyle=i?'#a8d6ed':'#ffb967';
      g.beginPath();g.moveTo(px(x-ny*d),py(y+nx*d));g.lineTo(px(x+ny*d),py(y-nx*d));g.stroke();
    }
    const [x,y]=trial.position;
    g.textAlign='center';g.fillStyle='#e9ffff';
    g.fillText(trial.name,px(x),py(y)-12);
  }
  for (const race of harbour.races || []) {
    g.strokeStyle = race.colour || '#ffb05f'; g.lineWidth = 1.5; g.setLineDash([3, 4]); g.beginPath();
    race.points.forEach(([x, y], i) => g[i ? 'lineTo' : 'moveTo'](px(x), py(y))); g.stroke(); g.setLineDash([]);
    for (const gate of race.gates) {
      const [x, y] = gate.center, [nx, ny] = gate.normal, d = gate.width_m * .5;
      g.beginPath(); g.moveTo(px(x - ny * d), py(y + nx * d)); g.lineTo(px(x + ny * d), py(y - nx * d)); g.stroke();
    }
  }
  if (harbour.races?.length) {
    const [x, y] = harbour.races[0].position;
    g.textAlign = 'center'; g.fillStyle = '#ffe9c4'; g.fillText('Lantern Race', px(x), py(y) - 12);
  }
  for (const pier of harbour.docks?.piers || []) {
    const [x, y] = harbourWorldPoint(harbour, pier.center);
    g.save(); g.translate(px(x), py(y)); g.rotate(pier.heading);
    g.fillStyle = '#c1ad88'; g.fillRect(-scaleM(pier.length) / 2, -scaleM(pier.width) / 2, scaleM(pier.length), scaleM(pier.width)); g.restore();
  }
  for (const path of harbour.docks?.access || []) {
    g.strokeStyle = '#c1ad88'; g.lineWidth = Math.max(1, scaleM(path.width)); g.beginPath(); ring(path.points); g.stroke();
  }
  if (harbour.accessPath?.length) {
    g.strokeStyle = '#d8c0a2'; g.lineWidth = 2; g.beginPath();
    harbour.accessPath.forEach(([x, y], i) => g[i ? 'lineTo' : 'moveTo'](px(x), py(y))); g.stroke();
  }
  for (const berth of harbour.docks?.berths || []) {
    const [x, y] = harbourWorldPoint(harbour, [berth.x, berth.y]);
    g.strokeStyle = '#8ce3c8'; g.lineWidth = 1; g.beginPath(); g.arc(px(x), py(y), Math.max(2, scaleM(7)), 0, Math.PI * 2); g.stroke();
  }
  g.textAlign = 'center'; g.fillStyle = '#e5f3e9';
  for (const mark of harbour.layout.landmarks || []) {
    if (!['marina', 'harbour', 'landing', 'cargo', 'dock'].includes(mark.kind)) continue;
    const [x, y] = harbourWorldPoint(harbour, [mark.x, mark.y]); g.fillText(mark.name, px(x), py(y) - 9);
  }
  g.restore();
}

export function drawHarbourBoats(g, {px, py, scaleM}, state) {
  if (!state?.available) return;
  g.save();
  for (const boat of state.boats || []) {
    const p = boat.position;
    if (!Array.isArray(p) || !p.every(Number.isFinite) || !Number.isFinite(boat.heading_rad)) continue;
    const selected = boat.id === state.selectedId;
    g.save(); g.translate(px(p[0]), py(p[1])); g.rotate(-boat.heading_rad);
    const length = Math.max(9, scaleM(boat.configuration?.length_m || 7));
    const width = Math.max(6, scaleM(boat.configuration?.beam_m || 8));
    g.fillStyle = selected ? '#f4c764' : '#d3e2df'; g.strokeStyle = '#102a31'; g.lineWidth = 1;
    g.beginPath(); g.moveTo(length / 2, 0); g.lineTo(-length / 2, -width / 2); g.lineTo(-length / 2, width / 2); g.closePath(); g.fill(); g.stroke();
    if (selected) {g.strokeStyle = '#f4c764'; g.beginPath(); g.arc(0, 0, Math.max(length, width) * .8, 0, Math.PI * 2); g.stroke();}
    g.restore();
  }
  g.restore();
}
