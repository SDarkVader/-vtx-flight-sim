import test from 'node:test';
import assert from 'node:assert/strict';
import {sceneryClock} from '../public/vtx-env/vaderland/scenery-clock.js';

test('city animation follows authoritative speed, pause and recovery',()=>{
  const clock=sceneryClock(),view={environment:{key:'vaderland-16'},run_id:'fixture',active:true,paused:false};
  clock.receive({...view,scenery_time_s:10},0);
  clock.receive({...view,scenery_time_s:10.025},100);
  assert.equal(clock.at(150),10.0125);
  assert.equal(clock.at(1100),10.025);
  clock.receive({...view,scenery_time_s:10.03,paused:true},1100);
  assert.equal(clock.at(3000),10.03);
  clock.receive({...view,scenery_time_s:4},3001);
  assert.equal(clock.at(4000),4);
});
