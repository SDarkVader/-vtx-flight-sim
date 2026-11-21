import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';

const source=await readFile(new URL('../public/cockpit-telemetry.js',import.meta.url));
const {cockpitTelemetry,phantomCockpitStates,phantomCockpitAuthority,phantomCockpitSwitches,phantomSystemIndications}=await import('data:text/javascript;base64,'+source.toString('base64'));

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

test('Phantom cockpit reports applied brake command and observed gear and wing states',()=>{
  assert.deepEqual(phantomCockpitStates({
    pod_tilt_deg:[0,.2,1,0],leg_extension_m:[0,0,0,0],canard_fold_deg:[0,0],
    wing_state:{left:'locked',right:'sliding_out'},
  },{
    command:{brake:[1,.5,0,0],wing:'deploy',pitch:.34,roll:-.1,yaw:0},
    boosters:[{side:'right',spool:.76},{side:'left',spool:.65}],
    phantom:{transition_ecu:{airbrake:'on'}},
  }),{brakes:'0%–100%',gear:'Road · 0°',legs:'Retracted',wings:'L locked / R sliding out',canards:'Deployed',airbrake:'On',stick:'34% / -10% / 0%',boosters:'65% / 76%',frontWheels:'—',rearWheels:'—',rudder:'—',ailerons:'—'});
});

test('Phantom cockpit keeps absent feedback unavailable and shows distinct gear states',()=>{
  assert.deepEqual(phantomCockpitStates(),{
    brakes:'—',gear:'—',legs:'—',wings:'—',canards:'—',airbrake:'—',stick:'—',boosters:'—',frontWheels:'—',rearWheels:'—',rudder:'—',ailerons:'—',
  });
  const vtol=phantomCockpitStates({pod_tilt_deg:[90,89,90,90],leg_extension_m:[.52,.51,.52,.52],canard_fold_deg:[90,-90]},{command:{brake:[0,0,0,0]}});
  assert.equal(vtol.gear,'VTOL · 90°');
  assert.equal(vtol.legs,'Extended');
  assert.equal(vtol.canards,'Folded');
  assert.equal(vtol.brakes,'Released');
  assert.equal(phantomCockpitStates({canard_fold_deg:[null,0]}).canards,'—');
});

test('a partial brake command offers release and controls use held commands',()=>{
  const truth={command:{brake:[0,0,.01,0],pod_tilt_deg:[90,90,90,90],
    leg_extension_m:[0,0,0,0],wing:'deploy',canard_fold:'folded',airbrake:'off'},
    phantom:{transition_ecu:{airbrake:'off'},wheel_rad_s:[2*Math.PI,0,-4*Math.PI,0],rudder_deg:4}};
  const observed={pod_tilt_deg:[12,14,13,15],leg_extension_m:[0,.05,0,.12],wing_state:{left:'swinging',right:'locked'}};
  const states=phantomCockpitStates(observed,truth);
  assert.equal(states.brakes,'0%–1%');
  assert.equal(states.gear,'12°–15° → 90°');
  assert.equal(states.legs,'0.00–0.12 → 0.00 m');
  assert.equal(states.frontWheels,'60 / 0');
  assert.equal(states.rearWheels,'120 / 0');
  const controls=phantomCockpitSwitches(truth);
  assert.deepEqual(controls.brakes,{label:'Release',selected:true,patch:{brake:[0,0,0,0]}});
  assert.deepEqual(controls.gear.patch,{pod_tilt_deg:[0,0,0,0]});
  assert.deepEqual(controls.wings.patch,{wing:'stow'});
  assert.equal(phantomCockpitSwitches({command:{airbrake:'off'}}).airbrake,null);
});

test('selected switch positions remain distinct from measured indications',()=>{
  const controls=phantomCockpitSwitches({command:{pod_tilt_deg:[90,90,90,90],wing:'stow'}});
  const lights=phantomSystemIndications({gear:'18°–23° → 90°',wings:'locked',brakes:'Released'});
  assert.equal(controls.gear.selected,true);
  assert.equal(lights.gear,'transit');
  assert.equal(controls.wings.selected,false);
  assert.equal(lights.wings,'active');
  assert.equal(lights.brakes,'inactive');
  assert.equal(lights.airbrake,'inactive');
});
test('cockpit distinguishes available authority from active, pending, and read-only states',()=>{
  const view={active:true,authority:'manual',observation:{warning_lamps:[]}};
  const held={available:true,engaged:true};
  assert.equal(phantomCockpitAuthority(view,{available:true}).canCommand,false);
  assert.equal(phantomCockpitAuthority(view,held).label,'Manual control active');
  assert.equal(phantomCockpitAuthority(view,{...held,waiting:true}).canCommand,false);
  assert.equal(phantomCockpitAuthority(view,held,{stale:true}).canTake,false);
  assert.equal(phantomCockpitAuthority({...view,paused:true},held).canTake,false);
  assert.equal(phantomCockpitAuthority({...view,authority:'colin'},held).label,'Colin has control');
  assert.equal(phantomCockpitAuthority(view,held,{recording:true}).canCommand,false);
});
