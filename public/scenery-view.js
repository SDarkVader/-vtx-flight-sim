// Camera selection is presentation only. Physical aircraft/pilot selection is separate.
export const PHYSICAL_VIEW_ID='physical-plant';
const SCENERY_IDS=new Set(['a10-primary','r6-flight','r6-training','r6-teardrop','r6-go-around']);

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
