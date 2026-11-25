// Synthetic test audio: songs (sines, a calibration tone) and "Firefly-like" takes with silence at both ends.
const fs = require('fs'), path = require('path');
function wav(file, sr, ch, frames) {
  const n = frames.length / ch, buf = Buffer.alloc(44 + n * ch * 2);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * ch * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(ch, 22); buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * ch * 2, 28); buf.writeUInt16LE(ch * 2, 32); buf.writeUInt16LE(16, 34);
  buf.write('data', 36); buf.writeUInt32LE(n * ch * 2, 40);
  for (let i = 0; i < frames.length; i++) buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(frames[i] * 32767))), 44 + i * 2);
  fs.writeFileSync(file, buf);
}
const sr = 48000, dbl = db => 10 ** (db / 20);
const sine = (f, secs, db, ch = 2, phase = 0) => { const n = Math.round(sr * secs), a = dbl(db), out = new Float32Array(n * ch); for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) out[i * ch + c] = a * Math.sin(2 * Math.PI * f * i / sr + phase); return out; };
const A = path.join(__dirname, 'assets');
fs.mkdirSync(path.join(A, 'Radio'), { recursive: true }); fs.mkdirSync(path.join(A, 'Sounds'), { recursive: true });
wav(path.join(A, 'Radio', 'Calib_997Hz_minus20.wav'), sr, 2, sine(997, 40, -20));
wav(path.join(A, 'Radio', 'Song_Two_100Hz.wav'), sr, 2, sine(100, 30, -12));
wav(path.join(A, 'Radio', 'Song_Three_440Hz.wav'), sr, 2, sine(440, 30, -12));
// takes with 0.4 s of silence at the start and 0.5 s at the end
const withSilence = (body, lead, tail, ch = 1) => { const l = new Float32Array(Math.round(sr * lead) * ch), t = new Float32Array(Math.round(sr * tail) * ch); const out = new Float32Array(l.length + body.length + t.length); out.set(body, l.length); return out; };
const noiseBody = (secs, db) => { const n = Math.round(sr * secs), a = dbl(db), out = new Float32Array(n); let s = 0; for (let i = 0; i < n; i++) { const w = Math.random() * 2 - 1; s = 0.9 * s + 0.1 * w; out[i] = a * (0.6 * w + 2.4 * s) * (1 + 0.2 * Math.sin(2 * Math.PI * 3 * i / sr)); } return out; };
wav(path.join(A, 'Sounds', 'Firefly_audio_A_large_electric_ducted_fan_variation2.wav'), sr, 1, withSilence(noiseBody(4, -18), 0.4, 0.5));
const sweep = secs => { const n = Math.round(sr * secs), out = new Float32Array(n); let ph = 0; for (let i = 0; i < n; i++) { const f = 120 + 500 * i / n; ph += 2 * Math.PI * f / sr; out[i] = dbl(-9) * Math.sin(ph) * Math.min(1, i / 2000, (n - i) / 2000); } return out; };
wav(path.join(A, 'Sounds', 'Firefly-A_heavy-duty_electromechanical_aircraft_wing_deployment_mechanism_operating_at_close_range_A (1).wav'), sr, 1, withSilence(sweep(3), 0.4, 0.5));
wav(path.join(A, 'Sounds', 'Firefly_audio_A_precise_geared_electric_motor_whirs_with_a_smoot_variation2.wav'), sr, 1, withSilence(sweep(2), 0.2, 0.3));
const thump = () => { const n = Math.round(sr * 0.8), out = new Float32Array(n); for (let i = 0; i < n; i++) out[i] = dbl(-6) * Math.sin(2 * Math.PI * 55 * i / sr) * Math.exp(-6 * i / sr); return out; };
wav(path.join(A, 'Sounds', 'Touchdown_thump.wav'), sr, 1, withSilence(thump(), 0.1, 0.2));
wav(path.join(A, 'Sounds', 'Birds_distant_chirp.wav'), sr, 1, withSilence(sweep(0.5), 0.05, 0.1));
console.log(fs.readdirSync(A, { recursive: true }).join('\n'));
