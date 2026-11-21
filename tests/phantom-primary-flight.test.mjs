import assert from 'node:assert/strict';
import test from 'node:test';
import {flightTapeMarks,primaryFlightReadings,viewBearing,compassTicks} from '../public/phantom-primary-flight.js';

test('flight tapes follow measured values and omit unavailable scales',()=>{
  assert.deepEqual(flightTapeMarks('75.0',10),[{label:70,top:65},{label:80,top:35}]);
  assert.deepEqual(flightTapeMarks('—',10),[]);
  assert.ok(flightTapeMarks('0.25',10).every(mark=>mark.label>=0));
});

test('primary heading and attitude reflect sensors and clear on stale data',()=>{
  const observation={attitude_deg:{yaw:90.3,pitch:12.5,roll:-8},airspeed_m_s:40};
  const fresh=primaryFlightReadings(observation,false);
  assert.equal(fresh.headingDegrees,'000°');
  assert.equal(fresh.pitchDegrees,'12.5°');
  assert.equal(fresh.bankDegrees,'-8.0°');
  const stale=primaryFlightReadings(observation,true);
  assert.equal(stale.headingDegrees,'—');
  assert.equal(stale.airspeed,'—');
  assert.equal(stale.pitch,null);
});

test('view compass follows world viewing direction and wraps through north',()=>{
  assert.equal(viewBearing(1,0),90);
  assert.equal(viewBearing(0,-1),180);
  assert.equal(viewBearing(-1,0),270);
  assert.equal(viewBearing(0,0),null);
  assert.deepEqual(compassTicks(359).find(tick=>tick.label==='N'),{label:'N',position:51.25});
  assert.deepEqual(compassTicks(1).find(tick=>tick.label==='N'),{label:'N',position:48.75});
});
