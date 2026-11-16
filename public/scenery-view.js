// Camera selection is presentation only. Physical aircraft/pilot selection is separate.
export const PHYSICAL_VIEW_ID='physical-plant';
export const SCENERY_VEHICLES=Object.freeze([
 Object.freeze({id:'a10-primary',label:'Phantom A10 · scheduled flight'}),
 Object.freeze({id:'r6-flight',label:'Argon R6 · holding flight'}),
 Object.freeze({id:'r6-training',label:'Argon R6 · training flight'}),
 Object.freeze({id:'r6-teardrop',label:'Argon R6 · teardrop flight'}),
 Object.freeze({id:'r6-go-around',label:'Argon R6 · go-around flight'}),
]);
const SCENERY_IDS=new Set(SCENERY_VEHICLES.map(vehicle=>vehicle.id));

// Offsets are relative to the scenery actor's rotation centre, not the physical aircraft.
export function sceneryPassengerSeat(id){
 if(!SCENERY_IDS.has(id))throw Error('Unknown scenery vehicle');
 return id==='a10-primary'?[.9,0,1.48]:[0,0,.45];
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
