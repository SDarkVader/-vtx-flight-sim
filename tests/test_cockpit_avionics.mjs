import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const source=await readFile(new URL('../public/cockpit-avionics.js',import.meta.url),'utf8');
const {avionicsReadings}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
assert.equal(avionicsReadings(null),null);
const data=avionicsReadings({t_s:12.3,radar_clearance_m:5.123,gnss_velocity_mps:[3,4,-1],
  engine_shaft_kw:18.5,fuel_kg:[1,2,3,4],rotor_rpm:[100,200,300,400],
  cabin_level_enabled:true,cabin_level_powered:true,warning_lamps:[]});
assert.equal(data.clearance,'5.12');assert.equal(data.vertical,'-1.0');assert.equal(data.speed,'5.0');
assert.equal(data.power,'18.5');assert.equal(data.fuel,'10.0');assert.equal(data.rpms,'100 / 200 / 300 / 400');
assert.equal(data.level,'POWERED');
const absent=avionicsReadings({radar_clearance_m:null});
assert.equal(absent.clearance,'—');assert.equal(absent.fuel,'—');assert.equal(absent.rpms,'—');
