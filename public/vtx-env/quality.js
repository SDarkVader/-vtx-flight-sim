// Rendering quality tiers. Visual cost only: no tier changes anything with a physics
// counterpart (terrain heights, obstacle boxes, tree cylinders, pads, landing surfaces).
//   low    phone default; never heavier than the pre-tier phone view
//   lite   desktop ?lite
//   medium desktop ?quality=medium (about the pre-tier desktop cost)
//   high   desktop default
// Override with ?quality=low|lite|medium|high. ?tm=aces|agx|neutral overrides tone mapping (for comparison only).
import * as THREE from 'three';

const TIERS = {
  low: {
    name: 'low', antialias: false, pixelRatio: 0.8, shadows: false, shadowSize: 0,
    forest: 350, facadePpm: 14, airfieldPpm: 7, detailMaps: false, localLights: 0,
    heightFog: false, glow: false, clouds: 16, anisotropy: 4, drape: 'flat', sunDisc: true,
  },
  lite: {
    name: 'lite', antialias: true, pixelRatio: 1.2, shadows: false, shadowSize: 0,
    forest: 700, facadePpm: 14, airfieldPpm: 7, detailMaps: false, localLights: 2,
    heightFog: true, glow: true, clouds: 26, anisotropy: 8, drape: 'full', sunDisc: true,
  },
  medium: {
    name: 'medium', antialias: true, pixelRatio: 1.2, shadows: true, shadowSize: 2048,
    forest: 1700, facadePpm: 24, airfieldPpm: 11, detailMaps: false, localLights: 3,
    heightFog: true, glow: true, clouds: 26, anisotropy: 8, drape: 'full', sunDisc: true,
  },
  high: {
    name: 'high', antialias: true, pixelRatio: 1.5, shadows: true, shadowSize: 4096,
    forest: 2600, facadePpm: 24, airfieldPpm: 11, detailMaps: true, localLights: 4,
    heightFog: true, glow: true, clouds: 40, anisotropy: 16, drape: 'full', sunDisc: true,
  },
};

const TONE = { aces: THREE.ACESFilmicToneMapping, agx: THREE.AgXToneMapping, neutral: THREE.NeutralToneMapping };

export function resolveQuality({ mobile = false, search = '' } = {}) {
  const p = new URLSearchParams(search);
  const asked = (p.get('quality') || '').toLowerCase();
  const name = TIERS[asked] ? asked : mobile ? 'low' : p.has('lite') ? 'lite' : 'high';
  const q = { ...TIERS[name] };
  const tm = (p.get('tm') || '').toLowerCase();
  q.toneMapping = TONE[tm] ?? THREE.ACESFilmicToneMapping;
  q.toneMappingName = TONE[tm] ? tm : 'aces';
  q.exposure = q.toneMappingName === 'aces' ? 1.05 : q.toneMappingName === 'neutral' ? 0.95 : 1.25;
  return q;
}

export const DEFAULT_QUALITY = TIERS.medium;
export function tierOf(opts) { return (opts && opts.quality) || DEFAULT_QUALITY; }
