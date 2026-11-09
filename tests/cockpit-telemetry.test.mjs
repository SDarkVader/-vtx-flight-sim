import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';

const source=await readFile(new URL('../public/cockpit-telemetry.js',import.meta.url));
const {cockpitTelemetry}=await import('data:text/javascript;base64,'+source.toString('base64'));

test('Phantom instruments use live sensor readings and ground reference',()=>{
  assert.deepEqual(cockpitTelemetry({radar_altimeter_m:2.5,radar_altimeter_ground_reference_m:1.5,
    velocity_world_m_s:[3,4,-2],fuel_kg:[5,7]}),
    {altitude:'1.00',verticalSpeed:'-2.00',speed:'5.00',fuel:'12.00'});
});
test('R6 sensors and real zero readings remain available',()=>{
  assert.deepEqual(cockpitTelemetry({radar_clearance_m:0,gnss_velocity_mps:[0,0,0],fuel_kg:[0,0]}),
    {altitude:'0.00',verticalSpeed:'0.00',speed:'0.00',fuel:'0.00'});
});
test('missing, malformed, or non-finite readings are not invented',()=>{
  assert.deepEqual(cockpitTelemetry({radar_altimeter_m:2,velocity_world_m_s:[1,null,NaN],fuel_kg:[]}),
    {altitude:'—',verticalSpeed:'—',speed:'—',fuel:'—'});
});
