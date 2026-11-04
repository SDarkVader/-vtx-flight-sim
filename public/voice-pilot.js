// Voice pilot for the Phantom (phantom-fbw-1). Intent level, deterministic: speech -> fixed grammar -> a patch on the
// operator panel's own command, sent by the panel heartbeat under the same lease and authority checks as the sliders.
// No language model is in the control loop (latency and determinism). Risky intents need a spoken "confirm".
// Read-backs use pilot-visible observation fields only (never rendering truth).

const UNITS = { zero: 0, oh: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19 };
const TENS = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const isNumWord = (w) => w in UNITS || w in TENS;

export function normalise(text) {
  const toks = String(text || '').toLowerCase().replace(/per cent/g, 'percent').replace(/%/g, ' percent ').replace(/[,!?;:]/g, ' ')
    .replace(/(\d)\.(\d)/g, '$1§$2').replace(/\./g, ' ').replace(/§/g, '.').replace(/-/g, ' ').split(/\s+/).filter(Boolean);
  const out = [];
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i];
    if (t === 'a' && toks[i + 1] === 'hundred') { out.push('100'); i++; continue; }
    if (isNumWord(t)) {
      let cur = 0, j = i;
      while (j < toks.length) {
        const w = toks[j];
        if (w in TENS) cur += TENS[w];
        else if (w in UNITS) cur += UNITS[w];
        else if (w === 'hundred') cur = (cur || 1) * 100;
        else if (w === 'and' && j + 1 < toks.length && isNumWord(toks[j + 1])) { /* "one hundred and five" */ }
        else break;
        j++;
      }
      if (toks[j] === 'point' && toks[j + 1] in UNITS) { out.push(String(cur + UNITS[toks[j + 1]] / 10)); i = j + 1; continue; }
      out.push(String(cur)); i = j - 1; continue;
    }
    out.push(t === 'half' ? '50' : t);
  }
  return (' ' + out.join(' ') + ' ').replace(/ (minus|negative) (\d+(?:\.\d+)?)/g, ' -$2');
}

const num = (s) => { const m = s.match(/(-?\d+(?:\.\d+)?)/); return m ? +m[1] : null; };
const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));
const has = (s, re) => re.test(s);
const fill = (n, v) => Array(n).fill(v);
const pct = (x) => `${Math.round(x)} percent`;

// returns {intent, patch?, say, risky?} ; intent 'confirm' | 'cancel' | 'status' | 'unknown' carry no patch
export function parseUtterance(text) {
  const s = normalise(text);
  const n = num(s);
  if (has(s, / (confirm|confirmed|affirmative|do it|execute) /)) return { intent: 'confirm', say: 'Confirmed.' };
  if (has(s, / (cancel|abort that|belay that|no) /)) return { intent: 'cancel', say: 'Cancelled.' };
  if (has(s, / (status|report|readout|how are we doing) /)) return { intent: 'status', say: '' };

  // boosters: spoken values are THRUST fractions; the plant's throttle commands rotor speed (thrust ~ omega^2)
  if (has(s, / boost(ers?)? /) || has(s, / afterburners? /)) {
    if (has(s, / (off|cut|kill|idle|zero) /) || has(s, / (cut|kill) (the )?boost/)) return { intent: 'boost', patch: { booster_throttle: [0, 0] }, say: 'Boosters off.' };
    if (has(s, / (full|max|maximum) /)) return { intent: 'boost', patch: { booster_throttle: [1, 1] }, say: 'Boosters full thrust.' };
    if (n !== null) {
      const f = clamp(n, 0, 100) / 100, thr = Math.sqrt(f);
      return { intent: 'boost', patch: { booster_throttle: [thr, thr] }, say: `Boosters ${pct(f * 100)} thrust, throttle ${pct(thr * 100)}.` };
    }
  }
  if (has(s, / (stop|halt|brakes? on|set (the )?brakes?|full brakes?) /)) return { intent: 'brake', patch: { brake: fill(4, 1), wheel_drive: fill(4, 0) }, say: 'Brakes on, drive zero.' };
  if (has(s, / (release (the )?brakes?|brakes? off) /)) return { intent: 'brake', patch: { brake: fill(4, 0) }, say: 'Brakes released.' };
  if (has(s, / (coast|neutral) /)) return { intent: 'drive', patch: { wheel_drive: fill(4, 0) }, say: 'Drive zero, coasting.' };
  if (has(s, / reverse /)) {
    const v = clamp(n ?? 20, 0, 100) / 100;
    return { intent: 'drive', patch: { wheel_drive: fill(4, -v), brake: fill(4, 0) }, say: `Reverse drive ${pct(v * 100)}.` };
  }
  if (has(s, / (drive|accelerate|wheels?) /) && n !== null) {
    const v = clamp(n, 0, 100) / 100;
    return { intent: 'drive', patch: { wheel_drive: fill(4, v), brake: fill(4, 0) }, say: `Wheel drive ${pct(v * 100)}.` };
  }
  if (has(s, / (take ?off|takeoff) (config|configuration|setup) /))
    return { intent: 'takeoff_config', patch: { wing: 'deploy', flap_deg: [30, 30], canard_fold: 'deployed', canard_pitch_deg: [0, 0], stability_mode: 'attitude', pitch: 0, roll: 0 },
      say: 'Take-off configuration: wings deploying, flaps thirty, canards deployed at zero, attitude hold.' };
  if (has(s, / (wings?) (out|deploy|extend) /) || has(s, / (deploy|extend) (the )?wings? /)) return { intent: 'wing', patch: { wing: 'deploy' }, say: 'Wings deploying.' };
  if (has(s, / (wings?) (in|stow|retract) /) || has(s, / (stow|retract) (the )?wings? /)) return { intent: 'wing', patch: { wing: 'stow' }, risky: true, say: 'Stow the wings?' };
  if (has(s, / flaps? /)) {
    let d = has(s, / (up|retract|clean) /) ? 0 : has(s, / (down|full) /) && n === null ? 30 : n;
    if (d === null) return { intent: 'unknown', say: 'Flaps to what angle?' };
    d = clamp(d, -5, 35);
    return { intent: 'flap', patch: { flap_deg: [d, d] }, say: `Flaps ${d} degrees.` };
  }
  // road downforce against nose rise (engineering/phantom/drs_flap.py: canards -5.4 deg cancel front unloading,
  // -9.6 deg keep a constant attitude at level stance)
  if (has(s, / (max|maximum) downforce /)) return { intent: 'downforce', patch: { canard_fold: 'deployed', canard_pitch_deg: [-10, -10] }, say: 'Maximum road downforce: canards minus ten.' };
  if (has(s, / (downforce|road trim|road aero) /)) return { intent: 'downforce', patch: { canard_fold: 'deployed', canard_pitch_deg: [-6, -6] }, say: 'Road downforce: canards deployed at minus six.' };
  if (has(s, / canards? /)) {
    if (has(s, / (fold|stow|in) /)) return { intent: 'canard', patch: { canard_fold: 'folded' }, risky: true, say: 'Fold the canards?' };
    if (has(s, / (deploy|out) /) && n === null) return { intent: 'canard', patch: { canard_fold: 'deployed' }, say: 'Canards deploying.' };
    if (n !== null) { const d = clamp(n, -20, 25); return { intent: 'canard', patch: { canard_pitch_deg: [d, d] }, say: `Canards ${d} degrees.` }; }
  }
  if (has(s, / (nose|pitch) /) && has(s, / (up|down) /)) {
    const d = clamp(n ?? 5, 0, 10) * (has(s, / down /) ? -1 : 1);
    return { intent: 'pitch', patch: { stability_mode: 'attitude', pitch: d / 10 }, say: `Attitude hold, pitch ${d} degrees.` };
  }
  if (has(s, / (level|wings level|hold attitude) /)) return { intent: 'level', patch: { stability_mode: 'attitude', pitch: 0, roll: 0 }, say: 'Levelling, attitude hold.' };
  if (has(s, / (hover|hold altitude) /)) return { intent: 'vs', patch: { stability_mode: 'attitude_vs', vertical_speed_m_s: 0 }, say: 'Holding altitude.' };
  if (has(s, / (climb|ascend|up) /) && n !== null) { const v = clamp(n, 0, 3); return { intent: 'vs', patch: { stability_mode: 'attitude_vs', vertical_speed_m_s: v }, say: `Climbing ${v} metres per second.` }; }
  if (has(s, / (descend|down) /) && n !== null) { const v = clamp(Math.abs(n), 0, 3); return { intent: 'vs', patch: { stability_mode: 'attitude_vs', vertical_speed_m_s: -v }, say: `Descending ${v} metres per second.` }; }
  if (has(s, / collective /) && n !== null) { const c = clamp(n, 0, 100) / 100; return { intent: 'collective', patch: { collective: c }, say: `Collective ${pct(c * 100)}.` }; }
  if (has(s, / (legs? (down|extend)|extend (the )?legs?) /)) return { intent: 'legs', patch: { leg_extension_m: fill(4, 0.52) }, say: 'Legs extending.' };
  if (has(s, / (legs? (up|retract)|retract (the )?legs?) /)) return { intent: 'legs', patch: { leg_extension_m: fill(4, 0) }, risky: true, say: 'Retract the legs?' };
  if (has(s, / (vtol|hover) mode /)) return { intent: 'mode', patch: { pod_tilt_deg: fill(4, 90), leg_extension_m: fill(4, 0.52) }, say: 'VTOL mode: pods vertical, legs extended.' };
  if (has(s, / road mode /)) return { intent: 'mode', patch: { pod_tilt_deg: fill(4, 0), leg_extension_m: fill(4, 0) }, risky: true, say: 'Road mode: pods down and legs up?' };
  if (has(s, / engine /)) {
    if (has(s, / (off|stop|shut ?down) /)) return { intent: 'engine', patch: { engine: 0 }, risky: true, say: 'Shut the engine down?' };
    if (has(s, / idle /)) return { intent: 'engine', patch: { engine: 0.15 }, say: 'Engine idle.' };
    if (has(s, / (on|start|run|full) /)) return { intent: 'engine', patch: { engine: 1 }, say: 'Engine running.' };
  }
  if (has(s, / (stability|augmentation) off /)) return { intent: 'stability', patch: { stability_mode: 'off' }, risky: true, say: 'Turn stability augmentation off?' };
  if (has(s, / rate damping /)) return { intent: 'stability', patch: { stability_mode: 'rate_damping' }, say: 'Rate damping.' };
  if (has(s, / attitude (mode|hold) /)) return { intent: 'stability', patch: { stability_mode: 'attitude' }, say: 'Attitude hold.' };
  return { intent: 'unknown', say: `Not understood: ${String(text || '').trim()}` };
}

export function statusReadback(view) {
  const o = view?.observation || {};
  const a = o.airspeed_m_s, h = o.radar_altimeter_m, vz = o.velocity_world_m_s?.[2];
  const parts = [];
  if (a != null) parts.push(`airspeed ${Math.round(a)} metres per second, ${Math.round(a * 2.23694)} miles per hour`);
  if (h != null) parts.push(`radar altitude ${Number(h).toFixed(1)} metres`);
  if (vz != null) parts.push(`vertical speed ${Number(vz).toFixed(1)}`);
  if (o.weight_on_wheels != null) parts.push(o.weight_on_wheels ? 'weight on wheels' : 'airborne');
  if (o.wing_state) parts.push(`wings ${Object.values(o.wing_state).join(' and ')}`);
  if (o.flap_deg) parts.push(`flaps ${Math.round(o.flap_deg[0] ?? o.flap_deg)}`);
  if (o.buffer_soc != null) parts.push(`battery ${Math.round(o.buffer_soc * 100)} percent`);
  const lamps = o.warning_lamps || [];
  parts.push(lamps.length ? `warnings: ${lamps.join(', ').toLowerCase().replace(/_/g, ' ')}` : 'no warnings');
  return parts.join('. ') + '.';
}

// Browser speech: push-to-talk recognition + spoken read-back. Returns null where the Web Speech API is missing.
export function createSpeech({ onText, onState, lang } = {}) {
  const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
  if (!SR) return null;
  const rec = new SR();
  rec.lang = lang || (typeof navigator !== 'undefined' && navigator.language) || 'en-GB';
  rec.continuous = true; rec.interimResults = false; rec.maxAlternatives = 1;
  let listening = false;
  rec.onresult = (e) => { for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) onText?.(e.results[i][0].transcript); };
  rec.onend = () => { if (listening) { try { rec.start(); } catch { /* already restarting */ } } else onState?.('off'); };
  rec.onerror = (e) => onState?.('error: ' + e.error);
  return {
    start() { listening = true; try { rec.start(); } catch { /* already started */ } onState?.('listening'); },
    stop() { listening = false; try { rec.stop(); } catch { /* not running */ } onState?.('off'); },
    get listening() { return listening; },
  };
}

export function speak(text) {
  if (typeof window === 'undefined' || !window.speechSynthesis || !text) return;
  const u = new SpeechSynthesisUtterance(text); u.rate = 1.05;
  window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
}
