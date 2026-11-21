import {flightDisplayReadings} from './flight-display.js?v=3';

export function primaryFlightReadings(observation, stale) {
  const flight = flightDisplayReadings(stale ? null : observation, {stale});
  const degrees = value => Number.isFinite(value) ? `${value.toFixed(1)}°` : '—';
  const heading = Number(flight.heading);
  return {...flight, pitchDegrees: degrees(flight.pitch), bankDegrees: degrees(flight.bank),
    headingDegrees: Number.isFinite(heading) ? `${String(heading % 360).padStart(3, '0')}°` : '—'};
}

export function flightTapeMarks(value, step) {
  const number = Number(value);
  if (!Number.isFinite(number)) return [];
  const centre = Math.floor(number / step);
  return [-1,0,1,2].map(offset => {
    const label = (centre + offset) * step;
    return {label, top:50 - 30 * (label - number) / step};
  }).filter(({label,top}) => label >= 0 && top >= 6 && top <= 94);
}

export function viewBearing(east, north) {
  if (!Number.isFinite(east) || !Number.isFinite(north) || Math.hypot(east,north) < 1e-7) return null;
  return (Math.atan2(east,north) * 180 / Math.PI + 360) % 360;
}

export function compassTicks(bearing) {
  if (!Number.isFinite(bearing)) return [];
  const base = Math.floor(bearing / 10) * 10;
  const cardinal = {0:'N',90:'E',180:'S',270:'W'};
  return [-3,-2,-1,0,1,2,3,4].map(offset => {
    const increment = base + offset * 10, course = (increment + 360) % 360;
    return {label:cardinal[course] ?? String(course).padStart(3,'0'), position:50 + (increment-bearing)*1.25};
  }).filter(({position})=>position>=5&&position<=95);
}

function updateMarks(scale, marks, direction) {
  while (scale.childElementCount < marks.length) scale.append(document.createElement('span'));
  while (scale.childElementCount > marks.length) scale.lastElementChild.remove();
  for (const [index, mark] of marks.entries()) {
    const tick = scale.children[index];
    tick.textContent = mark.label;
    tick.style[direction] = `${mark.position}%`;
  }
}

export function createViewCompass(root) {
  const scale=root.querySelector('#phantom-compass-scale');
  const label=root.querySelector('#phantom-view-bearing');
  let lastBearing;
  return (bearing, visible) => {
    const hidden = !visible || bearing === null;
    if (root.hidden!==hidden) root.hidden=hidden;
    if (hidden) return;
    const quantizedBearing=Math.round(bearing*2)/2;
    if (lastBearing===quantizedBearing) return;
    lastBearing=quantizedBearing;
    updateMarks(scale,compassTicks(quantizedBearing),'left');
    label.textContent=`${String(Math.round(quantizedBearing)%360).padStart(3,'0')}°`;
  };
}

function paintInstrument(canvas, context, draw) {
  if (!context || canvas.hidden) return;
  const {width,height} = canvas.getBoundingClientRect();
  if (!width || !height) return;
  const scale = window.devicePixelRatio || 1;
  const pixelWidth = Math.round(width * scale), pixelHeight = Math.round(height * scale);
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  context.setTransform(pixelWidth / width,0,0,pixelHeight / height,0,0);
  draw(context,width,height,scale);
}

export function createViewAttitude(canvas) {
  const context = canvas.getContext('2d');
  let flight, opacity = .76;

  function draw(c,width,height) {
    c.clearRect(0,0,width,height);
    c.save();
    c.translate(width / 2,height / 2);
    c.rotate(-flight.bank * Math.PI / 180);
    c.strokeStyle = `rgb(213 236 245 / ${.38 + opacity * .4})`;
    c.shadowColor = '#0a1320';
    c.shadowBlur = 2;
    c.lineWidth = 1;
    const centreMark = Math.round(flight.pitch / 10) * 10;
    for (const angle of [centreMark - 10,centreMark,centreMark + 10]) {
      if (Math.abs(angle) > 90) continue;
      const y = (flight.pitch - angle) * 1.7;
      const outer = angle === 0 ? 43 : 31;
      c.setLineDash(angle < 0 ? [3,2] : []);
      c.beginPath();
      c.moveTo(-outer,y);
      c.lineTo(-15,y);
      c.moveTo(15,y);
      c.lineTo(outer,y);
      c.stroke();
    }
    c.restore();
  }

  const paint = () => paintInstrument(canvas,context,draw);
  new ResizeObserver(paint).observe(canvas);
  return {
    opacity(value) {
      opacity = value;
      paint();
    },
    update(readings) {
      flight = readings;
      canvas.hidden = !Number.isFinite(flight.pitch) || !Number.isFinite(flight.bank);
      if (canvas.hidden) return;
      canvas.setAttribute('aria-label',`Aircraft attitude. Pitch ${flight.pitchDegrees}. Bank ${flight.bankDegrees}.`);
      paint();
    },
  };
}

function drawHorizon(context, width, height, flight, opacity, pixelRatio) {
  const c = context;
  const x = Math.round(width * pixelRatio / 2) / pixelRatio;
  const y = Math.round(height * pixelRatio * .53) / pixelRatio;
  c.clearRect(0,0,width,height);
  if (!Number.isFinite(flight?.pitch) || !Number.isFinite(flight?.bank)) {
    c.fillStyle = `rgb(20 36 49 / ${opacity})`;
    c.fillRect(0,0,width,height);
    c.fillStyle = '#eaf4fc';
    c.font = '600 11px system-ui';
    c.textAlign = 'center';
    c.fillText('ATTITUDE UNAVAILABLE',x,y);
    return;
  }

  const pitchScale = height / 32, extent = Math.max(width,height) + 90 * pitchScale;
  c.save();
  c.translate(x,y);
  const roll = -flight.bank * Math.PI / 180;
  c.rotate(roll);
  c.translate(0, flight.pitch * pitchScale);
  c.fillStyle = `rgb(40 92 126 / ${opacity})`;
  c.fillRect(-extent,-extent,2 * extent,extent);
  c.fillStyle = `rgb(100 72 51 / ${opacity})`;
  c.fillRect(-extent,0,2 * extent,extent);
  c.strokeStyle = '#f1f8fc';
  c.lineWidth = 1;
  c.beginPath();
  c.moveTo(-extent,0);
  c.lineTo(extent,0);
  c.stroke();
  c.font = '700 10px system-ui';
  c.fillStyle = '#f0f7fd';
  c.textAlign = 'center';
  for (let angle = -85; angle <= 85; angle += 5) {
    if (angle === 0 || Math.abs(angle - flight.pitch) > 31) continue;
    const longTick = angle % 10 === 0, dy = -angle * pitchScale, tickWidth = longTick ? 24 : 14;
    c.beginPath();
    c.moveTo(-tickWidth,dy);
    c.lineTo(tickWidth,dy);
    c.stroke();
    if (longTick) {
      for (const tx of [-tickWidth-9,tickWidth+9]) {
        const ty = dy + 3;
        const screenY = y + tx * Math.sin(roll) + (ty + flight.pitch * pitchScale) * Math.cos(roll);
        if (screenY >= 9 && screenY < height - 1) c.fillText(String(Math.abs(angle)),tx,ty);
      }
    }
  }
  c.restore();

  c.strokeStyle = '#ffd786';
  c.lineWidth = 2;
  c.beginPath();
  c.moveTo(x - 35,y); c.lineTo(x - 13,y); c.lineTo(x - 8,y + 5);
  c.moveTo(x + 8,y + 5); c.lineTo(x + 13,y); c.lineTo(x + 35,y);
  c.stroke();
  c.fillStyle = '#ffd786';
  c.fillRect(x - 1,y - 1,2,2);
}

export function createPrimaryFlightDisplay(deck) {
  const canvas = deck.querySelector('#phantom-attitude');
  const context = canvas.getContext('2d');
  const airspeed = deck.querySelector('#phantom-airspeed-tape');
  const altitude = deck.querySelector('#phantom-altitude-tape');
  let flight, opacity = .76;

  const paint = () => paintInstrument(canvas,context,
    (c,width,height,scale) => drawHorizon(c,width,height,flight,opacity,scale));

  function showTape(tape, value, step) {
    updateMarks(tape,flightTapeMarks(value,step).map(({label,top})=>({label,position:top})),'top');
  }

  new ResizeObserver(paint).observe(canvas);
  return {
    opacity(value) {
      opacity = value;
      paint();
    },
    update(readings) {
      flight = readings;
      showTape(airspeed,readings.airspeed,10);
      showTape(altitude,readings.altitude,10);
      const description = readings.pitch === null || readings.bank === null
        ? 'Artificial horizon, attitude unavailable'
        : `Artificial horizon. Pitch ${readings.pitchDegrees}. Bank ${readings.bankDegrees}.`;
      canvas.setAttribute('aria-label',description);
      paint();
    },
  };
}
