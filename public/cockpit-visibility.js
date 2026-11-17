// Render-only treatment of the near-camera P08 display and P09 seat/straps.
// IDs correspond to the retained source model; no physics objects are removed.
import {setArgonCutaway} from './argon-cutaway.js?v=3';
const legacyPanelIds = new Set([
  'c2429ce8-6150-4824-a737-11e0f6d01426',
  '34228c0c-4338-4907-8959-e7b1c4db6458',
  '0d53fec8-d68d-4af8-9def-a5347d5cf09f',
]);
const obstructionIds = new Set([
  '963c37d8-0be2-448c-a668-82f1d7011cc3', // pilot backrest
  '06308b39-7a36-4823-8f5a-7dd3ce9034f6', // pilot cushion
  'bcf0647a-f78e-427a-879b-eca4b0df77ec', // pilot headrest
  '39b901bd-b424-462a-b178-322ac4ef8bb8',
  '5851af17-b111-4c74-b3f2-fb0c67f26d9c',
  '95e06bfb-8006-4e4f-853f-898c3df9975d',
  'bd38666d-4b5d-4446-9c92-f51d6e1beeff',
]);
const phantomInteriorObstructions = new Set([
  'TUB_L_A_PILLAR_CLOSED_SHEAR_MEMBER', 'TUB_R_A_PILLAR_CLOSED_SHEAR_MEMBER',
  'TUB_L_FRONT_CONTINUOUS_SHEAR_WALL', 'TUB_R_FRONT_CONTINUOUS_SHEAR_WALL',
]);

export function isCockpitObstruction(node) {
  // The Phantom's integrated hull has an opaque exterior armour primitive
  // across the interior sight line. Hide that render primitive only in the
  // cockpit; the source model and MuJoCo colliders stay untouched.
  const phantomShell=node.name?.startsWith('PHANTOM_A8_') && ['A6 VTX Phantom satin gunmetal armour','A6 sharp black polygon windscreen','A6 dark carbon structural CFRP','A8 ventilated intake duct internal carbon liner'].includes(node.material?.name);
  const phantomSideGlass=node.name?.startsWith('PHANTOM_')&&node.name.includes('SIDEGLASS')&&node.material?.name==='A6 sharp black polygon windscreen';
  return Boolean(node.isMesh && (phantomShell || phantomSideGlass || phantomInteriorObstructions.has(node.name) || legacyPanelIds.has(node.userData?.blendstra_id) || node.userData?.legacyCockpitPanel || obstructionIds.has(node.userData?.blendstra_id) || node.userData?.cockpitObstruction));
}

export function setCockpitVisibility(root, inCockpit) {
  if (!root) return;
  setArgonCutaway(root,inCockpit);
  root.traverse(node => {
    if (!isCockpitObstruction(node)) return;
    if (node.userData.originalVisibility === undefined) node.userData.originalVisibility = node.visible;
    const legacy = legacyPanelIds.has(node.userData?.blendstra_id) || node.userData?.legacyCockpitPanel;
    node.visible = legacy || inCockpit ? false : node.userData.originalVisibility;
  });
}
