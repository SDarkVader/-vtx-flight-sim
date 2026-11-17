import {cockpitTelemetry} from './cockpit-telemetry.js?v=1';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toFixed(digits) : '—';
export function flightDisplayReadings(observation, {stale = false} = {}) {
  const o = observation || {}, basic = cockpitTelemetry(o), attitude = o.attitude_deg;
  return {...basic, available: !!observation, stale,
    state: stale ? 'STALE' : o.active ? o.paused ? 'PAUSED' : 'LIVE' : 'INSPECTION',
    time: fmt(o.t_s), airspeed: fmt(o.airspeed_m_s),
    heading: Number.isFinite(attitude?.yaw) ? fmt((90 - attitude.yaw % 360 + 360) % 360, 0).padStart(3, '0') : '—',
    pitch: Number.isFinite(attitude?.pitch) ? attitude.pitch : null,
    bank: Number.isFinite(attitude?.roll) ? attitude.roll : null,
    power: fmt(o.generator_kw ?? o.engine_shaft_kw),
    rpm: Array.isArray(o.fan_rpm) && o.fan_rpm.every(Number.isFinite) ? o.fan_rpm.map(n => fmt(n, 0)).join(' / ') : '—',
    warnings: Array.isArray(o.warning_lamps) ? o.warning_lamps : [],
  };
}

// A glass flight deck: tapes, a live horizon, a heading ribbon and system readouts.
// Drawing consumes observations only; it has no vehicle-control access.
export function drawFlightDisplay(c, r) {
  const font = (size, weight = '600') => {c.font = `${weight} ${size}px Inter, ui-monospace, monospace`;};
  const text = (value, x, y, size = 18, color = '#adc3c6', weight = '600') => {font(size,weight);c.fillStyle=color;c.fillText(value,x,y);};
  c.clearRect(0,0,1280,360);c.fillStyle='#0a151a';c.fillRect(0,0,1280,360);
  c.strokeStyle='#263b43';c.lineWidth=1;c.strokeRect(1,1,1278,358);
  text('VTX',20,28,22,'#e0e9e7','650');text('PHANTOM  /  FLIGHT DECK',86,27,15);
  c.fillStyle=r.stale?'#f1b35d':'#c6e879';c.fillRect(1070,16,5,5);
  c.textAlign='right';text(`${r.state}   ${r.time} s`,1260,26,15,r.stale?'#f1b35d':'#a6c0b3');c.textAlign='left';
  c.strokeStyle='#263b43';c.beginPath();c.moveTo(18,40);c.lineTo(1262,40);c.moveTo(258,55);c.lineTo(258,310);c.moveTo(966,55);c.lineTo(966,310);c.stroke();
  text('AIR SPEED',24,77,16);text('m/s',198,77,15);text(r.airspeed,24,127,42,'#e4efed','550');
  text('GROUND',24,172,14);text(`${r.speed} m/s`,24,202,25,'#c6e879');
  text('VERTICAL',24,247,14);text(`${r.verticalSpeed} m/s`,24,278,25,'#d3e4df');
  // Heading ribbon stays separate from the pitch/roll horizon.
  c.fillStyle='#12232a';c.fillRect(280,53,664,40);
  const hdg=Number(r.heading);
  if(Number.isFinite(hdg))for(let i=-3;i<=3;i++){
    const x=612+i*84;c.strokeStyle='#567580';c.beginPath();c.moveTo(x,82);c.lineTo(x,91);c.stroke();
    if(i){c.textAlign='center';text(String((Math.round(hdg/10)*10+i*10+360)%360).padStart(3,'0'),x,74,15);c.textAlign='left';}
  }
  c.fillStyle='#0a151a';c.fillRect(564,53,96,40);c.textAlign='center';text(`${r.heading}°`,612,80,24,'#c6e879','600');c.textAlign='left';
  c.save();c.beginPath();c.rect(280,100,664,208);c.clip();c.translate(612,204);
  if(r.pitch!==null&&r.bank!==null){
    c.rotate(-r.bank*Math.PI/180);c.translate(0,r.pitch*3);
    c.fillStyle='#244b5a';c.fillRect(-800,-1000,1600,1000);c.fillStyle='#504c3e';c.fillRect(-800,0,1600,1000);
    c.strokeStyle='#c6dad7';c.lineWidth=2;c.beginPath();c.moveTo(-800,0);c.lineTo(800,0);c.stroke();
    for(let p=-30;p<=30;p+=5){if(!p)continue;const y=-p*3,w=p%10===0?56:32;
      c.strokeStyle='#b2c9cd';c.lineWidth=1;c.beginPath();c.moveTo(-w,y);c.lineTo(-10,y);c.moveTo(10,y);c.lineTo(w,y);c.stroke();
      if(p%10===0)text(String(Math.abs(p)),w+9,y+5,14,'#c3d9d9');
    }
  }else{c.fillStyle='#15272e';c.fillRect(-400,-150,800,300);text('ATTITUDE UNAVAILABLE',-117,0,17);}
  c.restore();
  // Slim flight-director reference and speed/altitude tapes.
  c.strokeStyle='#edc773';c.lineWidth=3;c.beginPath();c.moveTo(545,204);c.lineTo(583,204);c.lineTo(594,211);c.moveTo(630,211);c.lineTo(641,204);c.lineTo(679,204);c.stroke();
  const tape=(x,value,step,title)=>{
    c.fillStyle='#102129';c.fillRect(x,105,62,198);c.strokeStyle='#415a63';c.strokeRect(x,105,62,198);
    const v=Number(value);
    if(Number.isFinite(v))for(let i=-3;i<=3;i++){const y=204-i*26,n=Math.round(v/step)*step+i*step;
      if(n>=0){text(String(Math.round(n)),x+7,y+5,13,'#8ba7af');c.strokeStyle='#7b969f';c.beginPath();c.moveTo(x+48,y);c.lineTo(x+60,y);c.stroke();}}
    c.fillStyle='#071116';c.fillRect(x-4,188,70,31);c.strokeStyle='#b6cfcc';c.strokeRect(x-4,188,70,31);text(value,x+3,210,16,'#eef4eb','600');text(title,x,299,11,'#a4bdc2');
  };
  tape(293,r.airspeed,10,'m/s');tape(870,r.altitude,10,'RADAR m');
  text('RADAR HEIGHT',986,78,15);text(`${r.altitude} m`,986,117,34,'#e4efed','550');
  text('FUEL',986,164,14);text(`${r.fuel} kg`,1114,164,24,'#c6e879');
  text('POWER',986,201,14);text(`${r.power} kW`,1114,201,24,'#d3e4df');
  text('FAN RPM  /  1 · 2 · 3 · 4',986,246,13);text(r.rpm,986,276,16,'#c0d2d4');
  c.strokeStyle='#263b43';c.beginPath();c.moveTo(18,321);c.lineTo(1262,321);c.stroke();
  const status=r.warnings.length?r.warnings.join(' / ').replaceAll('_',' '):r.available?'SYSTEMS NORMAL':'WAITING FOR TELEMETRY';
  c.fillStyle=r.warnings.length?'#f1b35d':'#c6e879';c.fillRect(20,337,5,5);text(status,36,345,14,r.warnings.length?'#f1b35d':'#92b1ac');
}
