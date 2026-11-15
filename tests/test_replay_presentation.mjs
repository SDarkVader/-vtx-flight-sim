import assert from 'node:assert/strict';
import {test} from 'node:test';
import {replayFrameAsset,replayCockpitReadings} from '../public/replay-presentation.js';
import {worldMatches} from '../public/world-sync.js';
const visual={status:'server-asset-matches-record',variant:'phantom-a10c',model_xml_sha256:'a'.repeat(64),config_sha256:'b'.repeat(64),render_asset:'/assets/phantom-a10b-visual.glb'};
const frame={variant:visual.variant,provenance:{airframe_variant:visual.variant,model_xml_sha256:visual.model_xml_sha256,config_sha256:visual.config_sha256,render_asset:visual.render_asset},fuel_kg:[64.5,64.5]};
test('replay requires this frame to match the recorded model, variant, config and asset',()=>{
 assert.equal(replayFrameAsset(frame,{visual}),visual.render_asset);
 for(const field of ['airframe_variant','model_xml_sha256','config_sha256','render_asset']){
  assert.equal(replayFrameAsset({...frame,provenance:{...frame.provenance,[field]:'other'}},{visual}),null,field);
 }
 assert.equal(replayFrameAsset({...frame,variant:'other'},{visual}),null);
 assert.equal(replayFrameAsset(frame,{visual:{...visual,status:'unavailable'}}),null);
 assert.equal(replayFrameAsset(frame,{}),null);
});
test('replay sensor gaps remain unavailable while recorded fuel is shown',()=>{
 assert.deepEqual(replayCockpitReadings(frame),{altitude:'—',verticalSpeed:'—',speed:'—',fuel:'129.0'});
 assert.equal(replayCockpitReadings({...frame,fuel_kg:[5,null]}).fuel,'—');
});
test('terrain must match its recorded key, revision, seed and fingerprint',()=>{
 const env={key:'sandbox',id:'stage1-valley',version:'2',seed:41031,displayed_world_sha256:'a'.repeat(64)};
 const world={environment:'sandbox',id:env.id,version:env.version,seed:env.seed,displayed_world_sha256:env.displayed_world_sha256};
 assert.equal(worldMatches(world,env),true);
 assert.equal(worldMatches({...world,displayed_world_sha256:'b'.repeat(64)},env),false);
 assert.equal(worldMatches(world,null),false);
});

test('R6 frames may omit a separate top-level variant and configuration hash',()=>{
 const r6={...visual,variant:'r6-argon-20261103',config_sha256:null};
 const recorded={provenance:{airframe_variant:r6.variant,model_xml_sha256:r6.model_xml_sha256,render_asset:r6.render_asset}};
 assert.equal(replayFrameAsset(recorded,{visual:r6}),r6.render_asset);
 assert.equal(replayFrameAsset({...recorded,provenance:{...recorded.provenance,airframe_variant:'r6'}},{visual:r6}),null);
});
