with open('scratch/capture_checkpoint3.mjs', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. School
code = code.replace(
    '''// 1. VTX-SCHOOL: Flight Academy & Simulation Centre
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-555, 570, 36);
  v.orbit.target.set(-555, 635, 29);
  v.orbit.update();
});''',
    '''// 1. VTX-SCHOOL: Flight Academy & Simulation Centre
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-555, 560, 38);
  v.orbit.target.set(-555, 635, 29);
  v.orbit.update();
});'''
)

# 2. HQ
code = code.replace(
    '''// 2. VTX-HQ: Passenger Terminal & Dispatch Concourse
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-200, 545, 45);
  v.orbit.target.set(-200, 620, 38);
  v.orbit.update();
});''',
    '''// 2. VTX-HQ: Passenger Terminal & Dispatch Concourse
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(-200, 530, 48);
  v.orbit.target.set(-200, 620, 38);
  v.orbit.update();
});'''
)

# 4. Tower & Fire
code = code.replace(
    '''// 4. VTX-TOWER & VTX-FIRE: ATC Tower (45m) & Airport Fire Station
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(330, 470, 55);
  v.orbit.target.set(320, 575, 45);
  v.orbit.update();
});''',
    '''// 4. VTX-TOWER & VTX-FIRE: ATC Tower (45m) & Airport Fire Station
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(350, 440, 70);
  v.orbit.target.set(350, 580, 45);
  v.orbit.update();
});'''
)

# 5. Cargo
code = code.replace(
    '''// 5. VTX-CARGO: Air Freight Depot & Sea Containers
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(680, 530, 36);
  v.orbit.target.set(680, 600, 30);
  v.orbit.update();
});''',
    '''// 5. VTX-CARGO: Air Freight Depot & Sea Containers
await page.evaluate(() => {
  const v = window.__vtx;
  v.setCameraMode('orbit');
  v.camera.position.set(680, 510, 42);
  v.orbit.target.set(680, 600, 30);
  v.orbit.update();
});'''
)

with open('scratch/capture_checkpoint3.mjs', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated capture_checkpoint3.mjs camera positions")
