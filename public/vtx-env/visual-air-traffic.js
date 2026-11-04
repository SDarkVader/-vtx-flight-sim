// Opt-in, render-only airport traffic preview. Never enters the pilot observation or physics API.
import {buildTrafficRoute, sampleTrafficRoute} from './traffic-path.js';

export function createVisualAirTraffic({THREE, GLTFLoader, scene, aircraft}) {
  const actors = [];
  const loader = new GLTFLoader();
  for (const spec of aircraft) {
    if (!Array.isArray(spec.cgLocal) || spec.cgLocal.length !== 3 ||
        !spec.cgLocal.every(Number.isFinite)) throw Error('Explicit CG reference required');
    const route = buildTrafficRoute(spec.waypoints);
    const root = new THREE.Group();
    root.name = 'visual-traffic-' + spec.id;
    scene.add(root);
    const pivot = new THREE.Group();
    root.add(pivot);
    const actor = {root, pivot, route, spec, ready:false};
    actors.push(actor);
    loader.load(spec.asset, gltf => {
      // Translation places the aircraft's declared local CG at the rotation origin.
      gltf.scene.position.set(-spec.cgLocal[0],-spec.cgLocal[1],-spec.cgLocal[2]);
      pivot.add(gltf.scene);
      actor.ready = true;
    }, undefined, error => console.warn('Traffic model unavailable', spec.id, error));
  }
  return {
    update(timeSeconds) {
      for (const actor of actors) {
        const {route, root, pivot, spec} = actor;
        const t = ((timeSeconds + (spec.phaseSeconds || 0)) % route.duration + route.duration) % route.duration;
        const pose = sampleTrafficRoute(route, t);
        root.position.set(...pose.position);
        // X forward, Y left, Z up; yaw then pitch then bank in local axes.
        const yaw = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),pose.heading);
        const pitch = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-pose.pitch);
        const prev = sampleTrafficRoute(route, Math.max(0,t-.25));
        const next = sampleTrafficRoute(route, Math.min(route.duration,t+.25));
        const delta = Math.atan2(Math.sin(next.heading-prev.heading),Math.cos(next.heading-prev.heading));
        const turnRate = delta / Math.max(.001,Math.min(route.duration,t+.25)-Math.max(0,t-.25));
        const bank = Math.max(-.45,Math.min(.45,Math.atan2(pose.speed*turnRate,9.80665)));
        const roll = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),bank);
        pivot.quaternion.copy(yaw).multiply(pitch).multiply(roll);
      }
    },
    dispose() { for (const a of actors) { scene.remove(a.root); a.root.clear(); } }
  };
}
