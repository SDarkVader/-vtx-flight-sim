'use strict';
/* VTX Producer. One page, no uploads: every file stays on this device.
   Mix: four channel strips, a master limiter, loudness and spectrum meters, sends, ducking and the project file.
   Music: your songs through a character rack. Vehicle: the Phantom A10-D parts, tuning of 25 Nov 2026 and the
   10 Hz flight replay, from the desktop Vehicle Designer. Scene: looping and random ambience layers.
   Takes: library, waveform editor, Firefly prompt notebook and bounce to WAV. */
const $ = id => document.getElementById(id);
const el = (tag, props = {}, ...kids) => { const n = Object.assign(document.createElement(tag), props); n.append(...kids); return n; };
const svgEl = (tag, attrs = {}) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in attrs) n.setAttribute(k, attrs[k]); return n; };
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const decimals = n => (String(n).split('.')[1] || '').length;
const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;
const mmss = s => Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}` : '0:00';
const debounce = (fn, ms) => { let t = 0; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const AC = window.AudioContext || window.webkitAudioContext;
const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
const AUDIO = /\.(mp3|mpeg|m4a|aac|ogg|opus|wav|flac|aif|aiff)$/i;
const dbToLin = db => db <= -79.9 ? 0 : 10 ** (db / 20);
const linToDb = x => x <= 1e-9 ? -Infinity : 20 * Math.log10(x);
const pct = v => Math.round(v * 100) + '%';
const dbText = (v, d = 1) => v <= -79.9 ? '−∞' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
const fmtDb = v => dbText(v, round(v, 1) === round(v, 0) ? 0 : 1) + ' dB';
const uid = () => Math.random().toString(36).slice(2, 8);
const stem = name => name.replace(/\.[^.]+$/, '');
function merge(base, over) {   // copy over onto base, only for keys base already has, same type
  if (!over || typeof over !== 'object') return base;
  for (const k of Object.keys(base)) {
    if (!(k in over)) continue;
    if (base[k] && typeof base[k] === 'object' && !Array.isArray(base[k])) merge(base[k], over[k]);
    else if (typeof over[k] === typeof base[k]) base[k] = over[k];
  }
  return base;
}

const ICON = {
  play: '<path d="M8 5.5v13l11-6.5z"/>', pause: '<path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/>',
  prev: '<path d="M6 5h2.5v14H6zM20 5v14L9.5 12z"/>', next: '<path d="M15.5 5H18v14h-2.5zM4 5l10.5 7L4 19z"/>',
  mix: '<path d="M5 3h2v6H5zm0 8h2v10H5zm6-8h2v10h-2zm0 12h2v6h-2zm6-12h2v4h-2zm0 6h2v12h-2zM3 9h6v2H3zm6 4h6v2H9zm6-7h6v2h-6z"/>',
  music: '<path d="M9 4l11-2v13.2a3.3 3.3 0 1 1-2-3V6.3L11 7.6V18a3.3 3.3 0 1 1-2-3z"/>',
  jet: '<path d="M12 2.5l1.7 6.6 7.8 4.1v2.4l-7.5-1.7.9 4.6 2.4 1.5v1.5L12 20.2l-5.3 1v-1.5l2.4-1.5.9-4.6-7.5 1.7v-2.4l7.8-4.1z"/>',
  scene: '<path d="M2 15c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3v3c-2.5 0-2.5-3-5-3s-2.5 3-5 3-2.5-3-5-3-2.5 3-5 3zM2 8c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3v3c-2.5 0-2.5-3-5-3s-2.5 3-5 3-2.5-3-5-3-2.5 3-5 3z"/>',
  takes: '<path d="M3 10h2v4H3zm4-4h2v12H7zm4-3h2v18h-2zm4 4h2v10h-2zm4 2h2v6h-2z"/>',
  tracks: '<path d="M2 5h9v4H2zm11 0h9v4h-9zM2 11h6v4H2zm8 0h12v4H10zM2 17h13v4H2zm15 0h5v4h-5z"/>',
};
const icon = (name, size = 24) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="currentColor" aria-hidden="true">${ICON[name]}</svg>`;

// ---------- remembered settings: one project in this browser ----------
const KEY = 'vtx-sound-studio-2';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch {}
const prefs = merge({ haptics: true, clicks: false, tuneStatic: true, cockpit: false, fine: false, wake: false,
  repeat: 'all', shuffle: false, lock: true, tab: 'tracks', musicView: 'deck', keepTakes: true, keepSongs: false, bypass: false, bits16: false }, saved.prefs);
function persist() {
  clearTimeout(persist.t);
  persist.t = setTimeout(() => { try { localStorage.setItem(KEY, JSON.stringify(collect())); } catch {} }, 400);
}
const say = (text, ms = 4000) => { say.until = Date.now() + ms; $('nowSub').textContent = text; };
say.until = 0;
