"""Ordered point-to-point gates on the native simulation clock."""
from .course_timing import CourseTiming


def _dot(u,v):
    return sum(a*b for a,b in zip(u,v))


class AirTrialTiming(CourseTiming):
    def __init__(self, ground, air):
        super().__init__(ground)
        self.air = air
        for course in air:
            self.runs[course['name']]=dict(start=None,next=0,splits=[],last=None,best=None,laps=0)

    def sample(self, t, position, *, air_allowed=True, contact=False):
        prev = self.previous
        super().sample(t,position)
        if not prev or self.previous is prev or not 0 < self.previous[0]-prev[0] < 2:
            return
        if not air_allowed or contact:
            for course in self.air:
                self.runs[course['name']].update(start=None,next=0,splits=[])
            return
        now,xyz=self.previous
        for course in self.air:
            state=self.runs[course['name']]
            gates=course['gates']
            idx=state['next']
            gate=gates[idx]
            center=gate['center']
            before=[q-r for q,r in zip(prev[1],center)]
            after=[q-r for q,r in zip(xyz,center)]
            a,b=(_dot(gate['normal'],v) for v in (before,after))
            if not a < 0 <= b:
                continue
            f=-a/(b-a)
            local=[u+f*(v-u) for u,v in zip(before,after)]
            if abs(_dot(local,gate['right']))>gate['width_m']/2 or abs(_dot(local,gate['up']))>gate['height_m']/2:
                continue
            stamp=prev[0]+f*(now-prev[0])
            if idx==0:
                state.update(start=stamp,next=1,splits=[])
            elif idx==len(gates)-1:
                result=round(stamp-state['start'],3)
                state.update(start=None,next=0,last=result,laps=state['laps']+1)
                state['best']=min(result,state['best']) if state['best'] is not None else result
            else:
                state['splits'].append(round(stamp-state['start'],3))
                state['next']+=1