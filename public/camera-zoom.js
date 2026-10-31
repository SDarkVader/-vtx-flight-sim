// Clamp external-camera distance without changing its aim point.
export function zoomDistance(distance,factor,min,max){
 if(![distance,factor,min,max].every(Number.isFinite)||distance<=0||factor<=0||min<=0||max<min)throw new RangeError('Invalid camera distance');
 return Math.min(max,Math.max(min,distance*factor));
}
