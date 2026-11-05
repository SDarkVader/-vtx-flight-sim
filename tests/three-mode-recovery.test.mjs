import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const app=readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../public/index.html',import.meta.url),'utf8');
test('unified airport defaults to real physical aircraft, not scripted ride',()=>{
  assert.match(app,/selectedVehicleId='physical-plant'/);
  assert.match(app,/let rideEnabled=false;/);
  assert.match(app,/<option value="physical-plant" selected>/);
  assert.match(app,/\$\('view-mode'\)\.textContent='PHYSICAL STATE - LIVE';/);
});
test('scripted preview remains an explicit operator choice',()=>{
  assert.match(app,/id="ride-start"/);
  assert.match(app,/passengerRide=true/);
  assert.match(app,/selectedVehicleId='a10-primary'/);
});
test('manual web and mobile controls remain wired to physics API',()=>{
  assert.match(html,/id="takeover"/);
  assert.match(html,/id="engine"/);
  assert.match(app,/api\('\/api\/operator',\{authority:'manual'\}\)/);
  assert.match(app,/api\('\/api\/action'/);
  assert.match(app,/const mobile=matchMedia/);
});
