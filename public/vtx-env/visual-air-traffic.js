// Opt-in, render-only airport traffic preview. Never enters the pilot observation or physics API.
import {buildTrafficRoute, sampleTrafficRoute} from './traffic-path.js';
import {sampleRideTrajectory} from './ride-trajectory.js';
const sampleRoute=(route,time)=>route.kind==='smooth-ride'?sampleRideTrajectory(route,time):sampleTrafficRoute(route,time);

export function clearOfPhysicalAircraft(traffic, physical) {
  return !physical || Math.hypot(traffic[0]-physical[0],traffic[1]-physical[1])>12 || Math.abs(traffic[2]-physical[2])>8;
}

export function createVisualAirTraffic({THREE, GLTFLoader, scene, aircraft}) {
  const actors = [];
  const loader = new GLTFLoader();
  const assets = new Map();
  const loadAsset = (spec) => {
    if (!assets.has(spec.asset)) assets.set(spec.asset, new Promise((resolve, reject) =>
      loader.load(spec.asset, gltf => {
        try{spec.prepareSource?.(gltf.scene);resolve(gltf.scene);}
        catch(error){reject(error);}
      }, progress => spec.onProgress?.(progress), reject)));
    return assets.get(spec.asset);
  };
  for (const spec of aircraft) {
    if (!Array.isArray(spec.cgLocal) || spec.cgLocal.length !== 3 ||
        !spec.cgLocal.every(Number.isFinite)) throw Error('Explicit CG reference required');
    const route = spec.waypoints ? buildTrafficRoute(spec.waypoints) : null;
    const root = new THREE.Group();
    root.name = 'visual-traffic-' + spec.id;
    scene.add(root);
    const pivot = new THREE.Group();
    root.add(pivot);
    const actor = {root, pivot, route, spec, ready:false};
    actors.push(actor);
    if(spec.makeModel){
      const model=spec.makeModel(THREE);
      model.position.set(-spec.cgLocal[0],-spec.cgLocal[1],-spec.cgLocal[2]);
      pivot.add(model);actor.rig=spec.onLoad?.(model);actor.ready=true;
      continue;
    }
    loadAsset(spec).then(source => {
      const instance = source.clone ? source.clone(true) : source;
      if (spec.validate && !spec.validate(instance)) throw Error('Model structure does not match '+spec.id);
      // Translation places the aircraft's declared local CG at the rotation origin.
      // The A10 export needs a Y-up to Z-up visual correction. The supplied
      // R6 GLB already uses the airport's Z-up frame and stays unrotated.
      if(spec.rotateToZUp&&instance.rotation)instance.rotation.x=Math.PI/2;
      instance.position.set(-spec.cgLocal[0],-spec.cgLocal[1],-spec.cgLocal[2]);
      pivot.add(instance);
      actor.rig = spec.onLoad?.(instance);
      actor.ready = true;
    }).catch(error => {
      console.warn('Traffic model unavailable', spec.id, error);
      spec.onError?.(error);
    });
  }
  return {
    update(timeSeconds) {
      for (const actor of actors) {
        const {route, root, pivot, spec} = actor;
        root.visible=spec.visible?.()??true;
        if(!root.visible)continue;
        // Passenger-demo paths finish on the runway; ordinary visual traffic may loop.
        const t = route&&spec.loop===false
          ? Math.max(0,Math.min(route.duration,timeSeconds + (spec.phaseSeconds || 0)))
          : route ? ((timeSeconds + (spec.phaseSeconds || 0)) % route.duration + route.duration) % route.duration : timeSeconds;
        const pose = spec.poseAt?.(timeSeconds) ?? sampleRoute(route, t);
        root.position.set(...pose.position);
        // X forward, Y left, Z up; yaw then pitch then bank in local axes.
        const yaw = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,0,1),pose.heading);
        const pitch = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),-pose.pitch);
        const prev = spec.poseAt?.(timeSeconds-.25) ?? sampleRoute(route, Math.max(0,t-.25));
        const next = spec.poseAt?.(timeSeconds+.25) ?? sampleRoute(route, Math.min(route.duration,t+.25));
        const delta = Math.atan2(Math.sin(next.heading-prev.heading),Math.cos(next.heading-prev.heading));
        const sampleSpan=spec.poseAt ? .5 : Math.min(route.duration,t+.25)-Math.max(0,t-.25);
        const turnRate = delta / Math.max(.001,sampleSpan);
        // Positive heading rate is a left turn. In X-forward/Y-left/Z-up,
        // bank the LEFT wing down by applying negative body-X rotation.
        const bank = Math.max(-.8,Math.min(.8,-Math.atan2(pose.speed*turnRate,9.80665)));
        const roll = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),bank);
        pivot.quaternion.copy(yaw).multiply(pitch).multiply(roll);
        actor.pose={...pose,bank};
        if(actor.ready)spec.onUpdate?.(actor.rig, pose, {time:pose.time??t,duration:route?.duration??83,bank});
      }
    },
    setRoute(id,route) {
      const actor=actors.find(a=>a.spec.id===id);
      if(!actor)throw Error('Unknown visual aircraft: '+id);
      if(!(route?.duration>0))throw Error('Invalid visual ride route');
      actor.route=route;
    },
    setWaypoints(id,waypoints) {
      const actor=actors.find(a=>a.spec.id===id);
      if(!actor)throw Error('Unknown visual aircraft: '+id);
      actor.route=buildTrafficRoute(waypoints);
    },
    getActor(id){return actors.find(a=>a.spec.id===id)||null;},
    get actors(){return actors;},
    dispose() { for (const a of actors) { scene.remove(a.root); a.root.clear(); } }
  };
}
