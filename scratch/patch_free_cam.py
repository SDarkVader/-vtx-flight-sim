with open('public/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Import createFreeCamera
old_import = "import {buildServiceRoads} from './vtx-env/service-roads.js?v=1';"
new_import = "import {buildServiceRoads} from './vtx-env/service-roads.js?v=1';\nimport {createFreeCamera} from './free-camera.js?v=3';"
assert old_import in text, 'old_import not found'
text = text.replace(old_import, new_import, 1)

# 2. Instantiate freeCam after orbit
old_orbit = "orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';"
new_orbit = "orbit.touches.TWO=THREE.TOUCH.DOLLY_ROTATE;renderer.domElement.style.touchAction='none';\nconst freeCam=createFreeCamera(camera,renderer,viewport,m=>setCameraMode(m));"
assert old_orbit in text, 'old_orbit not found'
text = text.replace(old_orbit, new_orbit, 1)

# 3. Update setCameraMode and camera onclick
old_setcam = """function setCameraMode(mode){cameraMode=mode;orbit.enabled=mode!=='cockpit';renderer.domElement.style.touchAction='none';$('cockpit-look').hidden=mode!=='cockpit';$('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';$('camera').textContent=mode==='chase'?'Chase camera':'Free orbit';}
$('camera').onclick=()=>setCameraMode(cameraMode==='chase'?'orbit':'chase');"""

new_setcam = """function setCameraMode(mode){
 cameraMode=mode;
 orbit.enabled=(mode==='chase');
 if(mode==='free'){orbit.enabled=false;freeCam.activate(orbit.target);}
 else{freeCam.deactivate();}
 renderer.domElement.style.touchAction='none';
 $('cockpit-look').hidden=mode!=='cockpit';
 $('cockpit').textContent=mode==='cockpit'?'Exit cockpit · C':'Cockpit · C';
 $('camera').textContent=mode==='free'?'Chase camera':'Free roam camera';
}
$('camera').onclick=()=>setCameraMode(cameraMode==='free'?'chase':'free');"""

assert old_setcam in text, 'old_setcam not found'
text = text.replace(old_setcam, new_setcam, 1)

# 4. Update zoomCamera
old_zoom = """function zoomCamera(factor){
 if(cameraMode==='cockpit'){toast('Zoom is available in the external camera.');return;}
 const offset=camera.position.clone().sub(orbit.target),distance=offset.length();"""

new_zoom = """function zoomCamera(factor){
 if(cameraMode==='cockpit'){toast('Zoom is available in the external camera.');return;}
 if(cameraMode==='free'){freeCam.zoom(factor);return;}
 const offset=camera.position.clone().sub(orbit.target),distance=offset.length();"""

assert old_zoom in text, 'old_zoom not found'
text = text.replace(old_zoom, new_zoom, 1)

# 5. Update animate loop camera handling
old_anim = """  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);}
  if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position).add(new THREE.Vector3(-.30,.02,.25).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));const cp=Math.cos(cockpitPitch);cameraTarget.copy(camera.position).add(new THREE.Vector3(Math.sin(cockpitYaw)*cp,-Math.cos(cockpitYaw)*cp,Math.sin(cockpitPitch)).applyQuaternion(q));camera.lookAt(cameraTarget);}else{camera.up.set(0,0,1);orbit.update();}"""

new_anim = """  if(cameraMode==='chase'){const delta=pos.clone().sub(orbit.target);camera.position.add(delta);orbit.target.copy(pos);camera.up.set(0,0,1);orbit.update();}
  else if(cameraMode==='cockpit'){const cabin=truth.body_poses.cabin,a=cabin.quaternion_wxyz;q.set(a[1],a[2],a[3],a[0]);camera.position.set(...cabin.position).add(new THREE.Vector3(-.30,.02,.25).applyQuaternion(q));camera.up.copy(new THREE.Vector3(0,0,1).applyQuaternion(q));const cp=Math.cos(cockpitPitch);cameraTarget.copy(camera.position).add(new THREE.Vector3(Math.sin(cockpitYaw)*cp,-Math.cos(cockpitYaw)*cp,Math.sin(cockpitPitch)).applyQuaternion(q));camera.lookAt(cameraTarget);}
  else if(cameraMode==='free'){freeCam.update(0.08);}
  else{camera.up.set(0,0,1);orbit.update();}"""

assert old_anim in text, 'old_anim not found'
text = text.replace(old_anim, new_anim, 1)

# 6. Expose freeCam in debug object
old_dbg = "if(new URLSearchParams(location.search).has('debug'))window.__vtx={scene,camera,renderer,orbit,THREE,sky,environment,setCameraMode,"
new_dbg = "if(new URLSearchParams(location.search).has('debug'))window.__vtx={scene,camera,renderer,orbit,freeCam,THREE,sky,environment,setCameraMode,"
assert old_dbg in text, 'old_dbg not found'
text = text.replace(old_dbg, new_dbg, 1)

with open('public/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully patched public/app.js with Free Roam Camera!')
