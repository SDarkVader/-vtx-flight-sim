// Visual identities and engineering references are deliberately separate.
// These CG values locate a render pivot; they do not revise the physical plant.
export const VEHICLE_MODELS = Object.freeze({
  'phantom-a10-81c823e2': Object.freeze({label:'Phantom A10 · glass roof (latest)',kind:'fixed-wing/VTOL',asset:'/assets/phantom-a10-blendstra-81c823e2.glb',rotateToZUp:true,dimensions_m:[5.8,4.5,1.8],cgLocal:[-0.15156246846624952,0.00004531509472356366,0.5529781802070567],animation:'a10-28-joint',flightModel:'visual-only',sourceVersion:'81c823e2-71aa-4da1-b924-1c1cb030664f'}),
  'r6': Object.freeze({label:'Argon R6 · Task 01 assembly (scripted flight)',kind:'rotorcraft',asset:'/assets/airframe-r6-blendstra-rig.glb?v=7325d0b3',sha256:'7325d0b303398c4ec0e9ece398cdcf63176db2555205b06c4d32a74a095c1489',rotateToZUp:false,dimensions_m:[7,6,3],cgLocal:[-0.0003,0.0792,1.4097],animation:'rotor',flightModel:'visual-only',sourceRevision:'P0-V4A-assembly-r6',calibrationId:'ARGON-R6-LIVE-STABILITY-CALIBRATION-20261101'}),
  'phantom-a10-legacy': Object.freeze({label:'Phantom A10 · earlier export',kind:'fixed-wing/VTOL',asset:'/assets/phantom-a10.glb',dimensions_m:[5.8,4.5,1.8],cgLocal:[-0.15156246846624952,0.00004531509472356366,0.5529781802070567],animation:'a10-joints',flightModel:'visual-only'}),
  'phantom-a9': Object.freeze({label:'Phantom A9 · earlier cassette',kind:'fixed-wing/VTOL',asset:'/assets/phantom-a9.glb',dimensions_m:[5.8,4.5,1.8],cgLocal:[0,0,.55],animation:'a9-joints',flightModel:'visual-only'}),
  'academy-twin': Object.freeze({label:'Academy twin · original lightweight aircraft',kind:'fixed-wing',dimensions_m:[8,11,2.4],cgLocal:[0,0,1.1],animation:'none',flightModel:'visual-only'}),
  'trainer': Object.freeze({label:'Trainer · original lightweight aircraft',kind:'fixed-wing',dimensions_m:[7,9,2.1],cgLocal:[0,0,1],animation:'none',flightModel:'visual-only'}),
  'service-rotorcraft': Object.freeze({label:'Service rotorcraft · original lightweight VTOL',kind:'rotorcraft',dimensions_m:[7,6,2.4],cgLocal:[0,0,1.2],animation:'rotor',flightModel:'visual-only'}),
  'ground-service': Object.freeze({label:'Airport service vehicle · original lightweight model',kind:'ground',dimensions_m:[4,2,2],cgLocal:[0,0,1],animation:'wheels',flightModel:'visual-only'}),
  'physical-plant': Object.freeze({label:'Colin physical aircraft',kind:'physical',asset:null,dimensions_m:null,cgLocal:null,animation:'physical',flightModel:'physics-authoritative'})
});
export const DEFAULT_VISUAL_MODEL='phantom-a10-81c823e2';
export function vehicleModel(id){const model=VEHICLE_MODELS[id];if(!model)throw Error('Unknown vehicle model: '+id);return model;}
