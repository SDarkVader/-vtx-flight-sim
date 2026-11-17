// Camera selection is presentation only. Physical aircraft/pilot selection is separate.
export const PHYSICAL_VIEW_ID='physical-plant';
export const SCENERY_VEHICLES=Object.freeze([
 Object.freeze({id:'a10-primary',label:'Phantom A10 · scheduled flight'}),
 Object.freeze({id:'r6-flight',label:'Argon R6 · holding flight'}),
 Object.freeze({id:'r6-training',label:'Argon R6 · training flight'}),
 Object.freeze({id:'r6-teardrop',label:'Argon R6 · teardrop flight'}),
 Object.freeze({id:'r6-go-around',label:'Argon R6 · go-around flight'}),
 Object.freeze({id:'a10-training',label:'Phantom A10 · training flight'}),
 Object.freeze({id:'r6-holiday',label:'Argon R6 · holiday flight'}),
 Object.freeze({id:'a10-teardrop',label:'Phantom A10 · teardrop flight'}),
 Object.freeze({id:'r6-circuit',label:'Argon R6 · circuit flight'}),
 Object.freeze({id:'a10-holiday',label:'Phantom A10 · holiday flight'}),
]);
const SCENERY_IDS=new Set(SCENERY_VEHICLES.map(vehicle=>vehicle.id));

// Offsets are relative to the scenery actor's rotation centre, not the physical aircraft.
export function sceneryPassengerSeat(id){
 if(!SCENERY_IDS.has(id))throw Error('Unknown scenery vehicle');
 // R6's cabin datum is [0,0,1.56], with the existing pilot eye
 // [-.30,.02,.25]; subtract the unchanged scenic model's render CG.
 return id.startsWith('a10-')?[.9,0,1.48]:[-.2997,-.0592,.4003];
}

export function sceneryPassengerSight(id, yaw, pitch) {
 if(!SCENERY_IDS.has(id))throw Error('Unknown scenery vehicle');
 const cp=Math.cos(pitch);
 return id.startsWith('a10-')?[Math.cos(yaw)*cp,Math.sin(yaw)*cp,Math.sin(pitch)]:[Math.sin(yaw)*cp,-Math.cos(yaw)*cp,Math.sin(pitch)];
}

export function airportViewSelection(id=PHYSICAL_VIEW_ID,{passenger=false}={}){
 if(id!==PHYSICAL_VIEW_ID&&!SCENERY_IDS.has(id))throw Error('Unknown airport view');
 return Object.freeze({id,scenery:id!==PHYSICAL_VIEW_ID,passenger:passenger&&id==='a10-primary'});
}

export function sceneryPoseAt({actorId,time,sceneTime,passengerRide,rideRoute,rideTime,sampleRide,sampleOperations}){
 if(actorId==='a10-primary'&&passengerRide&&rideRoute){
  return {...sampleRide(rideRoute,rideTime+time-sceneTime),operation:'passenger ride',mode:'scripted'};
 }
 return sampleOperations(actorId,time);
}
