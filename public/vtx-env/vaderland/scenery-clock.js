// Interpolate between two received simulation stamps. Never predict past native state.
export function sceneryClock(){
  let sample=null;
  return {
    receive(view,wall){
      const t=view.scenery_time_s;if(!Number.isFinite(t)){sample=null;return;}
      const id=[view.environment?.key,view.run_id??'inspection',view.active,view.paused].join('/');
      const reset=!sample||id!==sample.id||t<sample.t||wall-sample.wall>500;
      const still=!!view.paused||(!view.active&&!!view.run_id);
      const from=reset||still?t:sample.t;
      const interval=reset?0:Math.max(1,wall-sample.wall);
      sample={id,t,from,wall,interval};
    },
    at(wall,fallback){
      if(!sample)return fallback;
      const f=sample.interval?Math.max(0,Math.min(1,(wall-sample.wall)/sample.interval)):1;
      return sample.from+(sample.t-sample.from)*f;
    },
  };
}
