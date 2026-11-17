import * as THREE from 'three';
import {drawFlightDisplay, flightDisplayReadings} from './flight-display.js?v=3';

// Cabin-mounted avionics only. The authored airframe is never modified here.
export function createPhantomAvionics({document: doc = globalThis.document} = {}) {
  // Rasterize above display resolution, without blurred mip levels at the pilot's eye.
  const canvas = doc.createElement('canvas'); canvas.width = 2560; canvas.height = 720;
  const context = canvas.getContext('2d'), texture = new THREE.CanvasTexture(canvas);
  context.setTransform(2,0,0,2,0,0);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false; texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter; texture.anisotropy = 8;
  const root = new THREE.Group(); root.name = 'phantom-cockpit-avionics'; root.visible = false;
  const panel = new THREE.Group(); panel.position.set(.85, .15, .10);
  panel.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(new THREE.Vector3(0,-1,0),new THREE.Vector3(0,0,1),new THREE.Vector3(-1,0,0)));
  const frame = new THREE.Mesh(new THREE.BoxGeometry(.68,.195,.012),new THREE.MeshStandardMaterial({color:'#152126',roughness:.65,metalness:.25,depthTest:false,depthWrite:false}));
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(.66,.1856),new THREE.MeshBasicMaterial({map:texture,toneMapped:false,depthTest:false,depthWrite:false}));
  frame.renderOrder = 30; screen.renderOrder = 31; screen.position.z = .012;
  panel.add(frame, screen); root.add(panel);
  let lastKey = null;
  return {root,
    update(pose, observation, visible, stale = false) {
      const p=pose?.position, q=pose?.quaternion_wxyz;
      const valid=Array.isArray(p)&&p.length===3&&p.every(Number.isFinite)&&Array.isArray(q)&&q.length===4&&q.every(Number.isFinite)&&Math.abs(Math.hypot(...q)-1)<.01;
      root.visible = !!visible && valid;
      if(!root.visible)return;
      root.position.set(...p); root.quaternion.set(q[1],q[2],q[3],q[0]);
      const key = `${observation?.observation_id}:${observation?.t_s}:${stale}`;
      if(key!==lastKey){lastKey=key;drawFlightDisplay(context,flightDisplayReadings(observation,{stale}));texture.needsUpdate=true;}
    },
    dispose(){frame.geometry.dispose();screen.geometry.dispose();frame.material.dispose();screen.material.dispose();texture.dispose();root.removeFromParent();}
  };
}
