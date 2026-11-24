// Authoritative Live Minimap & Tactical Display for VTX Flight Simulator.
// Renders the genuine mathematical geometry graph of runways, curved Bézier taxiways,
// aprons, stands, holding points, and facility complexes from LAYOUT with sub-millimetre parity.
// The user's navigation overlay uses the active vehicle's GNSS and attitude sensors.
import { LAYOUT } from './layout.js';
import {primaryRunwayCues} from './runway-layout.js?v=20261116-runway-1';
import {drawHarbourMap, drawHarbourBoats} from './harbour-map.js?v=20261116-harbour-3';
import {ALPINE_ACCESS,ALPINE_LIFTS,ALPINE_ROUTES,ALPINE_ZONES} from './vaderland/alpine-layout.js';
import {meridianStreets} from './vaderland/meridian-streets.js';

function evalCubicBezier(p0, p1, p2, p3, t) {
  const mt = 1 - t, mt2 = mt * mt, mt3 = mt2 * mt, t2 = t * t, t3 = t2 * t;
  return [
    mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0],
    mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]
  ];
}

const backgroundCache = new WeakMap();

const facilityLabelFont = scaleM => `bold ${Math.max(9, Math.round(scaleM(12)))}px system-ui`;

export function mapZoomLimits(worldHalf,aspect=1){
  return {min:1000/(Math.max(100,worldHalf*2)*Math.max(1,aspect)*1.1),max:10};
}
export function mapScaleBar(projection,cssWidth,bufferWidth){
  const maxPixels=Math.min(140,cssWidth*.36),pixelsPerMetre=projection.scaleM(1)*cssWidth/bufferWidth;
  const metres=maxPixels/pixelsPerMetre,base=10**Math.floor(Math.log10(metres));
  const distance=[5,2,1].map(n=>n*base).find(n=>n<=metres)||base/2;
  return {metres:distance,pixels:distance*pixelsPerMetre,label:distance>=1000?`${distance/1000} km`:`${distance} m`};
}

function drawMapScale(ctx,canvas,projection){
  const rect=canvas.getBoundingClientRect();if(!(rect.width>0&&rect.height>0))return;
  const bar=mapScaleBar(projection,rect.width,canvas.width),sx=canvas.width/rect.width,sy=canvas.height/rect.height;
  ctx.save();ctx.scale(sx,sy);ctx.fillStyle='#07131de8';ctx.fillRect(7,rect.height-48,bar.pixels+24,41);
  ctx.fillStyle='#e5efeb';ctx.font='600 11px ui-monospace,monospace';ctx.textAlign='left';ctx.fillText('0',15,rect.height-31);ctx.textAlign='right';ctx.fillText(bar.label,15+bar.pixels,rect.height-31);
  ctx.strokeStyle='#e5efeb';ctx.lineWidth=2;ctx.setLineDash([]);ctx.beginPath();ctx.moveTo(15,rect.height-24);ctx.lineTo(15,rect.height-16);ctx.lineTo(15+bar.pixels,rect.height-16);ctx.lineTo(15+bar.pixels,rect.height-24);ctx.stroke();ctx.restore();
}

export function liveMapObservation(view, ageMs, replaying) {
  return view?.active && ageMs <= 2000 && !replaying ? view.observation : null;
}

// Phantom reports the yaw of its +X nose. The R6's forward datum is -Y.
// Both use counterclockwise world yaw. Compass headings increase clockwise from north.
export function aircraftMapFix(observation) {
  const position = observation?.gnss_xy_m;
  if (!Number.isFinite(position?.[0]) || !Number.isFinite(position?.[1])) return null;
  const phantom = observation.attitude_deg;
  const yaw = phantom ? phantom.yaw : observation.attitude_xyz_deg?.[2];
  let bearing = null;
  if (phantom && Number.isFinite(yaw)) bearing = 90 - yaw;
  else if (Number.isFinite(yaw)) {
    const [roll, pitch] = observation.attitude_xyz_deg.map(deg => deg * Math.PI / 180);
    const lateral = Math.sin(pitch) * Math.sin(roll), forward = Math.cos(roll);
    if (Math.hypot(lateral, forward) > 1e-6) bearing = 180 - yaw + Math.atan2(lateral, forward) * 180 / Math.PI;
  }
  const heading = bearing === null ? null : (bearing % 360 + 360) % 360;
  const measured = observation.velocity_world_m_s ?? observation.gnss_velocity_mps;
  const velocity = Number.isFinite(measured?.[0]) && Number.isFinite(measured?.[1]) ? measured : null;
  return {position, heading, velocity};
}

function drawAircraftMarker(ctx, canvas, proj, fix) {
  const bounds = canvas.getBoundingClientRect();
  if (bounds.width <= 0 || bounds.height <= 0) return;
  const sx = canvas.width / bounds.width, sy = canvas.height / bounds.height;
  const w = bounds.width, h = bounds.height;
  const x = proj.px(fix.position[0]) / sx, y = proj.py(fix.position[1]) / sy;
  const outside = x < 0 || x > w || y < 0 || y > h;
  let markerX = x, markerY = y, angle = fix.heading === null ? null : fix.heading * Math.PI / 180;
  if (outside) {
    const dx = x - w / 2, dy = y - h / 2;
    const fraction = Math.min((w / 2 - 12) / Math.abs(dx), (h / 2 - 12) / Math.abs(dy));
    markerX = w / 2 + dx * fraction;
    markerY = h / 2 + dy * fraction;
    angle = Math.atan2(dx, -dy);
  }
  ctx.save();
  ctx.scale(sx, sy);
  ctx.translate(markerX, markerY);
  if (!outside && fix.velocity && Math.hypot(...fix.velocity.slice(0, 2)) > .5) {
    ctx.save();
    ctx.strokeStyle = '#2fe3ffcc';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(proj.scaleM(2 * fix.velocity[0]) / sx, -proj.scaleM(2 * fix.velocity[1]) / sy);
    ctx.stroke();
    ctx.restore();
  }
  ctx.save();
  ctx.fillStyle = '#2fe3ff';
  ctx.strokeStyle = '#0a1a24';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 3;
  ctx.beginPath();
  if (angle === null) {
    ctx.arc(0, 0, 5, 0, Math.PI * 2);
  } else {
    ctx.rotate(angle);
    ctx.moveTo(0, -11);
    ctx.lineTo(7, 8);
    ctx.lineTo(0, 5);
    ctx.lineTo(-7, 8);
    ctx.closePath();
  }
  ctx.stroke();
  ctx.fill();
  ctx.restore();

  const label = outside ? 'Aircraft off map' : 'Your aircraft';
  ctx.font = 'bold 11px system-ui';
  const right = markerX + 13 + ctx.measureText(label).width <= w;
  ctx.textAlign = right ? 'left' : 'right';
  ctx.textBaseline = 'middle';
  ctx.lineWidth = 3;
  ctx.strokeStyle = '#0a1a24';
  ctx.fillStyle = '#2fe3ff';
  const labelY = Math.max(8, Math.min(h - 8, markerY)) - markerY;
  ctx.strokeText(label, right ? 13 : -13, labelY);
  ctx.fillText(label, right ? 13 : -13, labelY);
  ctx.restore();
}

export class TacticalMinimap {
  constructor(canvas, { isLarge = false, redraw } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.isLarge = isLarge;
    this.zoom = 0.5;
    this.airportZoom = 0.5;
    this.worldHalf = 500;
    this.center = [0, 100]; // centered to capture both runways and northern facilities
    this.airportCenter = [0, 100];
    this.tacticalMode = false; // false: airport, true: whole world
    this.suppressPointerClick = false;
    this.redraw = redraw ?? (() => { if (this.lastRender) this.render(...this.lastRender); });
    
    this.bindEvents();
  }

  bindEvents() {
    const c = this.canvas;
    c.addEventListener('wheel',e=>{e.preventDefault();const r=c.getBoundingClientRect();this.zoomBy(Math.exp(Math.max(-.4,Math.min(.4,-e.deltaY*.002))),[(e.clientX-r.left)*c.width/r.width,(e.clientY-r.top)*c.height/r.height]);},{passive:false});
    c.addEventListener('keydown',e=>{if(['+','=','-','_'].includes(e.key)){e.preventDefault();e.stopPropagation();this.zoomBy(e.key==='-'||e.key==='_'?1/1.4:1.4);}});
    
    // Double click to toggle tactical zoom
    c.addEventListener('dblclick', (e) => {
      if (this.isNavigationClick(e)) return;
      this.tacticalMode = !this.tacticalMode;
      this.zoom = this.tacticalMode ? 1000 / (this.worldHalf * 2 * Math.max(1, c.width / c.height)) : this.airportZoom;
      this.center = this.tacticalMode ? [0, 0] : [...this.airportCenter];
      backgroundCache.delete(c);
      e.preventDefault();
    });

    const pointers = new Map();
    const dragThreshold = 5;
    let redrawPending = false;
    const pinchDistance = () => {
      const [first, second] = pointers.values();
      return Math.hypot(second[0] - first[0], second[1] - first[1]);
    };
    const movePointer = e => {
      const previous = pointers.get(e.pointerId);
      if (!previous) return;
      const point = [e.clientX, e.clientY];
      const dx = point[0] - previous[0], dy = point[1] - previous[1];
      if (!dx && !dy) return;
      if (pointers.size > 1) {
        const previousDistance = pointers.size === 2 ? pinchDistance() : 0;
        pointers.set(e.pointerId, point);
        if (previousDistance > 0) this.zoomBy(pinchDistance() / previousDistance);
        return;
      }
      if (!this.suppressPointerClick && Math.hypot(dx, dy) < dragThreshold) return;
      this.suppressPointerClick = true;
      pointers.set(e.pointerId, point);
      const rect = c.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const span = 1000 / this.zoom;
      this.center[0] -= dx * span / rect.width;
      this.center[1] += dy * span * c.height / (rect.height * c.width);
      if (redrawPending) return;
      redrawPending = true;
      requestAnimationFrame(() => {
        redrawPending = false;
        this.redraw();
      });
    };
    c.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      this.suppressPointerClick = pointers.size > 0;
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      if (e.isTrusted) c.setPointerCapture(e.pointerId);
    });
    c.addEventListener('pointermove', e => {
      if (e.buttons & 1) movePointer(e);
    });
    c.addEventListener('pointerup', e => {
      if (!pointers.has(e.pointerId)) return;
      movePointer(e);
      pointers.delete(e.pointerId);
      // Pointer capture may deliver a click after a release outside the map.
      const rect = c.getBoundingClientRect();
      if (e.clientX < rect.left || e.clientX >= rect.right || e.clientY < rect.top || e.clientY >= rect.bottom) {
        this.suppressPointerClick = true;
      }
    });
    const cancelPointer = e => {
      if (pointers.delete(e.pointerId)) this.suppressPointerClick = true;
    };
    c.addEventListener('pointercancel', cancelPointer);
    c.addEventListener('lostpointercapture', cancelPointer);
  }

  isNavigationClick(event) {
    return this.suppressPointerClick && event.isTrusted === true;
  }

  zoomBy(factor,anchor=[this.canvas.width/2,this.canvas.height/2]){
    if(!Number.isFinite(factor)||factor<=0)return;
    const before=this.getProjection(),point=[before.unpx(anchor[0]),before.unpy(anchor[1])];
    const limits=mapZoomLimits(this.worldHalf,this.canvas.width/this.canvas.height);
    this.zoom=Math.max(limits.min,Math.min(limits.max,this.zoom*factor));
    const after=this.getProjection();this.center[0]+=point[0]-after.unpx(anchor[0]);this.center[1]+=point[1]-after.unpy(anchor[1]);
    backgroundCache.delete(this.canvas);
    this.redraw();
  }

  getProjection(worldHalf = 500) {
    const w = this.canvas.width, h = this.canvas.height;
    const span = 1000 / this.zoom;
    const spanY = span * h / w;
    const cx = this.center[0], cy = this.center[1];
    return {
      w, h,
      px: x => ((x - cx) / span + 0.5) * w,
      py: y => (0.5 - (y - cy) / spanY) * h,
      scaleM: m => (m / span) * w,
      unpx: sx => (sx / w - 0.5) * span + cx,
      unpy: sy => (0.5 - sy / h) * spanY + cy
    };
  }

  buildBackgroundLayer(world, proj) {
    const layer = document.createElement('canvas');
    layer.width = proj.w; layer.height = proj.h;
    const g = layer.getContext('2d');
    const { px, py, scaleM, w, h } = proj;

    // 1. Terrain elevation contour background
    g.fillStyle = '#1c2826'; g.fillRect(0, 0, w, h);
    if (world && world.heights_m) {
      const n = world.heights_m.length;
      const step = Math.max(1, Math.floor(n / 64));
      for (let j = 0; j < n - 1; j += step) {
        for (let i = 0; i < n - 1; i += step) {
          const v = world.heights_m[j][i];
          const wx = -world.half_m + (i / (n - 1)) * world.half_m * 2;
          const wy = -world.half_m + (j / (n - 1)) * world.half_m * 2;
          const shade = Math.min(85, Math.round(35 + v * 0.9));
          g.fillStyle = `rgb(${shade},${shade + 22},${shade + 14})`;
          const x0 = px(wx), y0 = py(wy);
          const x1 = px(wx + (step / (n - 1)) * world.half_m * 2);
          const y1 = py(wy + (step / (n - 1)) * world.half_m * 2);
          g.fillRect(x0, y1, Math.max(1, x1 - x0 + 1), Math.max(1, y0 - y1 + 1));
        }
      }
    }

    // 2. Lake water
    if (world && world.water) {
      const { x, y, half_x, half_y } = world.water;
      g.fillStyle = 'rgba(75, 140, 175, 0.75)';
      g.fillRect(px(x - half_x), py(y + half_y), scaleM(half_x * 2), scaleM(half_y * 2));
      g.strokeStyle = '#68b5d8'; g.lineWidth = 1;
      g.strokeRect(px(x - half_x), py(y + half_y), scaleM(half_x * 2), scaleM(half_y * 2));
    }

    if (world?.harbour) {
      g.save();
      g.font = facilityLabelFont(scaleM);
      drawHarbourMap(g, proj, world.harbour);
      g.restore();
    }

    // Grid covers the visible extent; spacing expands for the world view.
    const spacing = this.zoom < 0.3 ? 1000 : 200;
    g.strokeStyle = 'rgba(150, 195, 180, 0.12)'; g.lineWidth = 1;
    const xmin = proj.unpx(0), xmax = proj.unpx(w);
    const ymin = proj.unpy(h), ymax = proj.unpy(0);
    for (let x = Math.ceil(xmin / spacing) * spacing; x <= xmax; x += spacing) {
      g.beginPath(); g.moveTo(px(x), 0); g.lineTo(px(x), h); g.stroke();
    }
    for (let y = Math.ceil(ymin / spacing) * spacing; y <= ymax; y += spacing) {
      g.beginPath(); g.moveTo(0, py(y)); g.lineTo(w, py(y)); g.stroke();
    }

    if(world?.vaderland){
      const line=(points,width,color)=>{
        if(!points.length)return;
        g.strokeStyle=color;g.lineWidth=Math.max(.65,scaleM(width));g.beginPath();
        points.forEach(([x,y],i)=>g[i?'lineTo':'moveTo'](px(x),py(y)));g.stroke();
      };
      for(const route of world.vaderland.air_trials??[]){
        g.setLineDash([4,3]);
        line(route.gates.map(gate=>gate.center),2,route.name==='Parallax Thread'?'#ffb771':'#8debfa');
        g.setLineDash([]);
      }
      for(const stream of world.vaderland.streams||[])line(stream.points,stream.width_m,'#68b7cf');
      for(const road of meridianStreets(world))line(road.points,road.width_m,
        road.edge_color??({viaduct:'#edb770',express:'#b99acb',boulevard:'#b9a48b',lane:'#706e65',cycleway:'#a38471'}[road.kind]??'#868988'));
      for(const o of world.obstacles){
        if(o.role!=='architecture')continue;
        const [x,y]=o.center,[a,b]=o.half;g.fillStyle='#a6a4a1';
        g.fillRect(px(x-a),py(y+b),Math.max(.65,scaleM(a*2)),Math.max(.65,scaleM(b*2)));
      }
      const r=world.runway;line([[r.x0,r.yc],[r.x1,r.yc]],r.width+8,'#f4e2b7');
      if(world.id==='vaderland-33'){
        line(ALPINE_ACCESS,12,'#e7bd7a');
        for(const route of [...ALPINE_LIFTS,...ALPINE_ROUTES]){
          if(route.kind!=='descent')g.setLineDash([3,3]);
          line(route.points,12,route.color??'#c4d3e2');
          g.setLineDash([]);
        }
        g.font='10px system-ui';g.textAlign='center';
        for(const zone of ALPINE_ZONES){
          const x=px(zone.point[0]),y=py(zone.point[1]);
          g.fillStyle='#fff2d7';
          g.beginPath();g.arc(x,y,2.4,0,Math.PI*2);g.fill();
          if(['village','high-summit','cirque','east-launch','race-west'].includes(zone.id)){
            const caption=zone.id==='high-summit'?zone.name:zone.area;
            const labelY=y+(zone.id==='high-summit'?13:-7);
            g.lineWidth=3;g.strokeStyle='#17252a';
            g.strokeText(caption,x,labelY);g.fillText(caption,x,labelY);
          }
        }
      }
      g.font='11px system-ui';g.textAlign='center';g.lineWidth=3;g.strokeStyle='#17252a';
      for(const place of world.vaderland.places){
        const x=px(place.point[0]),y=py(place.point[1])-7;g.strokeText(place.name,x,y);
        g.fillStyle='#e8e3ca';g.fillText(place.name,x,y);
      }
      return layer;
    }
    const isSandbox = world && (world.environment === 'sandbox' || world.id === 'stage1-valley');
    if (isSandbox) {
      // Stage 1 Valley Test Sandbox east-west runway (Runway 09/27: 1,900m x 42m) & cross apron
      g.fillStyle = 'rgba(195, 212, 202, 0.14)';
      g.fillRect(px(-18), py(160), scaleM(36), scaleM(320));
      g.save();
      g.fillStyle = '#22252a';
      g.fillRect(px(-950), py(21), scaleM(1900), scaleM(42));
      g.strokeStyle = 'rgba(255,255,255,0.75)'; g.lineWidth = Math.max(1, scaleM(0.8));
      g.setLineDash([scaleM(16), scaleM(18)]);
      g.beginPath(); g.moveTo(px(-910), py(0)); g.lineTo(px(910), py(0)); g.stroke();
      g.setLineDash([]);
      g.fillStyle = '#ffffff';
      g.font = `bold ${Math.max(8, Math.round(scaleM(13)))}px "Arial Black", sans-serif`;
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText('09', px(-880), py(0));
      g.fillText('27', px(880), py(0));
      g.fillStyle = '#22e055'; g.fillRect(px(-950), py(21), scaleM(3), scaleM(42));
      g.fillStyle = '#ff2211'; g.fillRect(px(947), py(21), scaleM(3), scaleM(42));
      g.restore();
      g.strokeStyle = 'rgba(212, 246, 106, 0.55)';
      g.lineWidth = 1.2;
      g.beginPath();
      g.arc(px(0), py(0), Math.max(5, scaleM(12)), 0, Math.PI * 2);
      g.stroke();

      if (world.obstacles) {
        for (const o of world.obstacles) {
          const [ox, oy] = o.center, [hx, hy] = o.half;
          if (o.kind === 'cylinder') {
            g.fillStyle = '#536a55';
            g.beginPath();
            g.arc(px(ox), py(oy), Math.max(1.5, scaleM(hx)), 0, Math.PI * 2);
            g.fill();
          } else {
            g.fillStyle = o.landable ? '#8ca094' : '#a07865';
            g.fillRect(px(ox - hx), py(oy + hy), scaleM(hx * 2), scaleM(hy * 2));
            g.strokeStyle = o.landable ? '#d4f66a' : '#ffaa77';
            g.lineWidth = 1;
            g.strokeRect(px(ox - hx), py(oy + hy), scaleM(hx * 2), scaleM(hy * 2));
            g.fillStyle = '#eef2ed';
            g.font = `bold ${Math.max(8, Math.round(scaleM(9)))}px system-ui`;
            g.textAlign = 'center';
            g.textBaseline = 'middle';
            g.fillText(o.id.toUpperCase(), px(ox), py(oy));
          }
        }
      }
      return layer;
    }

    // 4. Expanded Aprons
    if (LAYOUT.aprons_expanded) {
      for (const ap of LAYOUT.aprons_expanded) {
        const [aw, ah] = ap.size; const [acx, acy] = ap.center;
        g.fillStyle = '#40454b';
        g.fillRect(px(acx - aw / 2), py(acy + ah / 2), scaleM(aw), scaleM(ah));
        g.strokeStyle = '#f5b800'; g.lineWidth = 1.2;
        g.strokeRect(px(acx - aw / 2), py(acy + ah / 2), scaleM(aw), scaleM(ah));
        g.fillStyle = 'rgba(235, 230, 215, 0.4)';
        g.font = `bold ${Math.max(9, Math.round(scaleM(18)))}px system-ui`;
        g.textAlign = 'center';
        g.fillText(ap.name, px(acx), py(acy));
      }
    }

    // 5. Central Operational Apron
    if (LAYOUT.apron) {
      const { x0, x1, y0, y1 } = LAYOUT.apron;
      g.fillStyle = '#454a50';
      g.fillRect(px(x0), py(y1), scaleM(x1 - x0), scaleM(y1 - y0));
      g.strokeStyle = '#f5b800'; g.lineWidth = 1;
      g.strokeRect(px(x0), py(y1), scaleM(x1 - x0), scaleM(y1 - y0));
    }

    // 6. Runways
    // Runway 08/26 uses the same world record as the 3D paint and lights.
    const primary = primaryRunwayCues(world), runway = primary.runway;
    g.save();
    g.fillStyle = '#22252a';
    g.fillRect(px(runway.x0), py(runway.yc + runway.width / 2), scaleM(runway.length), scaleM(runway.width));
    g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = Math.max(1, scaleM(0.8));
    g.setLineDash([scaleM(14), scaleM(16)]);
    g.beginPath(); g.moveTo(px(primary.centerline[0]), py(runway.yc)); g.lineTo(px(primary.centerline[1]), py(runway.yc)); g.stroke();
    g.setLineDash([]);
    // Heading numbers '08' and '26'
    g.fillStyle = '#ffffff';
    g.font = `bold ${Math.max(8, Math.round(scaleM(14)))}px "Arial Black", sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (const {label, x} of primary.numbers) g.fillText(label, px(x), py(runway.yc));
    // Threshold green/red markers
    for (const {x, color} of primary.thresholdBands) {
      g.fillStyle = color; g.fillRect(px(x), py(runway.yc + runway.width / 2), scaleM(3), scaleM(runway.width));
    }
    g.restore();

    // Runway 03/21 (Secondary: 980m x 23m, 55 deg)
    g.save();
    g.translate(px(235), py(0));
    const rwy21Ang = -Math.atan2(0.81915204, 0.57357644); // Canvas Y is inverted
    g.rotate(rwy21Ang);
    const r21Len = scaleM(980), r21W = scaleM(23);
    g.fillStyle = '#22252a';
    g.fillRect(-r21Len / 2, -r21W / 2, r21Len, r21W);
    g.strokeStyle = 'rgba(255,255,255,0.7)'; g.lineWidth = Math.max(1, scaleM(0.8));
    g.setLineDash([scaleM(12), scaleM(14)]);
    g.beginPath(); g.moveTo(-r21Len / 2 + scaleM(20), 0); g.lineTo(r21Len / 2 - scaleM(20), 0); g.stroke();
    g.setLineDash([]);
    g.fillStyle = '#ffffff';
    g.font = `bold ${Math.max(8, Math.round(scaleM(12)))}px "Arial Black", sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText('03', -r21Len / 2 + scaleM(35), 0);
    g.fillText('21', r21Len / 2 - scaleM(35), 0);
    g.restore();

    // Closed Runway 18/36 (North-South at x = -180m)
    g.save();
    g.fillStyle = '#2b2e32';
    g.fillRect(px(-189), py(400), scaleM(18), scaleM(800));
    g.fillStyle = '#f5b800';
    g.font = `bold ${Math.max(10, Math.round(scaleM(16)))}px Arial, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let y = -300; y <= 300; y += 150) g.fillText('X', px(-180), py(y));
    g.restore();

    // 7. Taxiway Network (Curved Béziers & Polylines)
    if (LAYOUT.taxiways_network) {
      for (const twy of LAYOUT.taxiways_network) {
        g.strokeStyle = '#22252a'; g.lineWidth = Math.max(2, scaleM(twy.width || 14));
        g.beginPath();
        if (twy.kind === 'cubic_bezier') {
          const cps = twy.control_points;
          for (let i = 0; i <= 32; i++) {
            const pt = evalCubicBezier(cps[0], cps[1], cps[2], cps[3], i / 32);
            if (i === 0) g.moveTo(px(pt[0]), py(pt[1]));
            else g.lineTo(px(pt[0]), py(pt[1]));
          }
        } else if (twy.kind === 'polyline' && twy.points) {
          g.moveTo(px(twy.points[0][0]), py(twy.points[0][1]));
          g.lineTo(px(twy.points[1][0]), py(twy.points[1][1]));
        }
        g.stroke();

        // Yellow taxiway centerline
        g.strokeStyle = '#f5b800'; g.lineWidth = Math.max(1, scaleM(0.6));
        g.beginPath();
        if (twy.kind === 'cubic_bezier') {
          const cps = twy.control_points;
          for (let i = 0; i <= 32; i++) {
            const pt = evalCubicBezier(cps[0], cps[1], cps[2], cps[3], i / 32);
            if (i === 0) g.moveTo(px(pt[0]), py(pt[1]));
            else g.lineTo(px(pt[0]), py(pt[1]));
          }
        } else if (twy.kind === 'polyline' && twy.points) {
          g.moveTo(px(twy.points[0][0]), py(twy.points[0][1]));
          g.lineTo(px(twy.points[1][0]), py(twy.points[1][1]));
        }
        g.stroke();
      }
    }

    // 7.5 Airfield Service Road Network
    g.save();
    g.strokeStyle = '#2b2e32'; g.lineWidth = Math.max(1.5, scaleM(10));
    g.beginPath();
    const rCps = [[-720, 695], [-650, 735], [220, 735], [800, 695]];
    for (let i = 0; i <= 32; i++) {
      const pt = evalCubicBezier(rCps[0], rCps[1], rCps[2], rCps[3], i / 32);
      if (i === 0) g.moveTo(px(pt[0]), py(pt[1])); else g.lineTo(px(pt[0]), py(pt[1]));
    }
    g.stroke();
    g.lineWidth = Math.max(1.2, scaleM(8));
    g.beginPath();
    g.moveTo(px(-650), py(490));
    g.lineTo(px(-100), py(490));
    g.lineTo(px(40), py(520));
    g.lineTo(px(240), py(500));
    g.lineTo(px(475), py(530));
    g.lineTo(px(680), py(540));
    g.stroke();
    g.strokeStyle = 'rgba(255, 255, 255, 0.45)'; g.lineWidth = Math.max(0.8, scaleM(0.4));
    g.setLineDash([scaleM(4), scaleM(4)]);
    g.beginPath();
    for (let i = 0; i <= 32; i++) {
      const pt = evalCubicBezier(rCps[0], rCps[1], rCps[2], rCps[3], i / 32);
      if (i === 0) g.moveTo(px(pt[0]), py(pt[1])); else g.lineTo(px(pt[0]), py(pt[1]));
    }
    g.moveTo(px(-650), py(490));
    g.lineTo(px(-100), py(490));
    g.lineTo(px(40), py(520));
    g.lineTo(px(240), py(500));
    g.stroke();
    g.setLineDash([]);
    g.restore();

    // 8. Stands 1 to 6
    if (LAYOUT.stands_expanded) {
      for (let idx = 0; idx < LAYOUT.stands_expanded.length; idx++) {
        const st = LAYOUT.stands_expanded[idx];
        const sx = px(st.center[0]), sy = py(st.center[1]), sr = scaleM(st.radius);
        g.fillStyle = '#26292d';
        g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.fill();
        g.strokeStyle = '#f5b800'; g.lineWidth = 1.2;
        g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.stroke();
        g.fillStyle = '#f5b800';
        g.font = `bold ${Math.max(8, Math.round(scaleM(6)))}px system-ui`;
        g.textAlign = 'center'; g.textBaseline = 'middle';
        g.fillText(String(idx + 1), sx, sy);
      }
    }

    // 9. Physical Building Footprints
    if (world && world.obstacles) {
      for (const o of world.obstacles) {
        g.fillStyle = o.landable ? '#8ca094' : '#a07865';
        const [ox, oy] = o.center, [hx, hy] = o.half;
        g.fillRect(px(ox - hx), py(oy + hy), scaleM(hx * 2), scaleM(hy * 2));
      }
    }

    // 10. Facility Complex Badges & Labels
    const facilities = [
      { id: 'SCHOOL', label: '🎓 VTX ACADEMY', pt: [-555, 635], col: '#f5b800' },
      { id: 'HQ', label: '🏢 HQ / TERMINAL', pt: [-200, 620], col: '#38a8e0' },
      { id: 'ENG', label: '⚙️ MRO SKUNKWORKS', pt: [40, 590], col: '#e08838' },
      { id: 'TOWER', label: '📡 ATC TOWER', pt: [240, 555], col: '#ff5533' },
      { id: 'FIRE', label: '🚒 FIRE STN 9', pt: [475, 600], col: '#ff3322' },
      { id: 'CARGO', label: '📦 CARGO HUB', pt: [680, 600], col: '#e0c038' },
      { id: 'VOLCANO', label: '🌋 VOLCANO / BASEMENT', pt: [-30, 220], col: '#ff4400' }
    ];
    for (const f of facilities) {
      const fx = px(f.pt[0]), fy = py(f.pt[1]);
      g.fillStyle = 'rgba(15, 20, 25, 0.85)';
      const textW = Math.max(50, Math.round(scaleM(80)));
      g.fillRect(fx - textW / 2, fy - 10, textW, 20);
      g.strokeStyle = f.col; g.lineWidth = 1;
      g.strokeRect(fx - textW / 2, fy - 10, textW, 20);
      g.fillStyle = f.col;
      g.font = facilityLabelFont(scaleM);
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.fillText(f.label, fx, fy);
    }

    return layer;
  }

  render(world, { observation, track, departure, destination, harbourState }) {
    if (!world) return;
    this.lastRender=[world,{observation,track,departure,destination,harbourState}];
    this.worldHalf = world.half_m;
    const isSandbox = world.environment === 'sandbox' || world.id === 'stage1-valley';
    this.airportZoom = isSandbox ? 1 : world.runway ? .12 : .5;
    this.airportCenter = isSandbox ? [0, 0] : world.runway
      ? [(world.runway.x0 + world.runway.x1) / 2, world.runway.yc + 100] : [0, 100];
    const proj = this.getProjection(world.half_m);
    const { px, py, scaleM, w, h } = proj;

    // Cache or redraw background
    let bg = backgroundCache.get(this.canvas);
    const worldKey = JSON.stringify([world.id, world.version, world.seed, world.displayed_world_sha256, world.runway]);
    if (!bg || bg.worldKey !== worldKey || bg.w !== w || bg.h !== h || bg.zoom !== this.zoom || bg.cx !== this.center[0] || bg.cy !== this.center[1]) {
      const layer = this.buildBackgroundLayer(world, proj);
      bg = { layer, worldKey, w, h, zoom: this.zoom, cx: this.center[0], cy: this.center[1] };
      backgroundCache.set(this.canvas, bg);
    }
    this.ctx.drawImage(bg.layer, 0, 0);
    drawHarbourBoats(this.ctx, proj, harbourState);

    // Dynamic flight track breadcrumbs
    if (track && track.length > 1) {
      this.ctx.strokeStyle = '#2fe3ffcc';
      this.ctx.lineWidth = Math.max(1.5, scaleM(1.2));
      this.ctx.beginPath();
      track.forEach((p, i) => {
        if (i === 0) this.ctx.moveTo(px(p[0]), py(p[1]));
        else this.ctx.lineTo(px(p[0]), py(p[1]));
      });
      this.ctx.stroke();
    }

    // Departure (A) and Destination (B) Markers
    for (const [p, label, col] of [[departure, 'A', '#2fe3ff'], [destination, 'B', '#ffaa22']]) {
      if (!p) continue;
      const x = px(p[0]), y = py(p[1]);
      this.ctx.fillStyle = col;
      this.ctx.beginPath(); this.ctx.arc(x, y, Math.max(6, scaleM(6)), 0, Math.PI * 2); this.ctx.fill();
      this.ctx.strokeStyle = '#ffffff'; this.ctx.lineWidth = 1.5;
      this.ctx.stroke();
      this.ctx.fillStyle = '#0a1a1c';
      this.ctx.font = `bold ${Math.max(9, Math.round(scaleM(7)))}px system-ui`;
      this.ctx.textAlign = 'center'; this.ctx.textBaseline = 'middle';
      this.ctx.fillText(label, x, y + 0.5);
    }

    const fix = aircraftMapFix(observation);
    if (fix) {
      const p = fix.position;
      const velocity = fix.velocity;
      const speed = velocity ? Math.hypot(velocity[0], velocity[1]).toFixed(1) : '—';
      const heading = fix.heading === null ? '—' : String(Math.round(fix.heading) % 360).padStart(3, '0');
      // Tactical HUD Telemetry Overlay (Top & Bottom Readouts)
      this.ctx.fillStyle = 'rgba(8, 12, 16, 0.85)';
      this.ctx.fillRect(8, 8, 210, 48);
      this.ctx.strokeStyle = '#2fe3ff44'; this.ctx.lineWidth = 1;
      this.ctx.strokeRect(8, 8, 210, 48);

      this.ctx.fillStyle = '#2fe3ff';
      this.ctx.font = 'bold 11px monospace';
      this.ctx.textAlign = 'left';
      this.ctx.fillText(`POS X: ${p[0].toFixed(1)}m  Y: ${p[1].toFixed(1)}m`, 14, 23);
      this.ctx.fillText(`HDG: ${heading}°  SPD: ${speed}m/s`, 14, 37);
      const clearance = observation.radar_clearance_m ?? (observation.radar_altimeter_m != null ? Math.max(0, observation.radar_altimeter_m - (observation.radar_altimeter_ground_reference_m || 0)) : null);
      this.ctx.fillText(`ALT: ${clearance == null ? 'unavailable' : clearance.toFixed(1) + 'm AGL'}`, 14, 50);

      // Tactical Mode Indicator & Zoom Pill
      this.ctx.fillStyle = this.tacticalMode ? '#f5b800' : 'rgba(235, 240, 245, 0.7)';
      this.ctx.font = 'bold 10px system-ui';
      this.ctx.textAlign = 'right';
      const isSandbox = world && (world.environment === 'sandbox' || world.id === 'stage1-valley');
      this.ctx.fillText(this.tacticalMode ? 'WORLD' : (isSandbox ? 'SANDBOX' : 'AIRPORT'), w - 10, 18);
      this.ctx.fillStyle = 'rgba(255,255,255,0.45)';
      this.ctx.fillText('DBL-CLICK / PINCH ZOOM', w - 10, 32);
      drawAircraftMarker(this.ctx, this.canvas, proj, fix);
    }
    drawMapScale(this.ctx,this.canvas,proj);
  }
}
