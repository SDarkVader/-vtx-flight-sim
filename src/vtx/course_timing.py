"""Shared trackside clocks measure ordered, physical crossings using simulation time."""


class CourseTiming:
    def __init__(self,courses):
        self.courses=courses
        self.previous=None
        self.runs={c['name']:dict(start=None,next=0,splits=[],last=None,best=None,laps=0) for c in courses}

    def sample(self,t,position):
        time=float(t);xyz=[float(v) for v in position[:3]]
        prev=self.previous
        if prev and 0<=time-prev[0]<.045:return
        self.previous=[time,xyz]
        if prev is None or not 0<time-prev[0]<2:return
        for c in self.courses:
            state=self.runs[c['name']];idx=state['next'];gate=c['gates'][idx]
            (x,y,z),(nx,ny)=gate['center'],gate['normal']
            if abs(xyz[0]-x)>40 or abs(xyz[1]-y)>40:continue
            before=(prev[1][0]-x)*nx+(prev[1][1]-y)*ny;after=(xyz[0]-x)*nx+(xyz[1]-y)*ny
            if not before<0<=after:continue
            f=-before/(after-before)
            p=[a+f*(b-a) for a,b in zip(prev[1],xyz)]
            if abs(-(p[0]-x)*ny+(p[1]-y)*nx)>gate['width_m']/2 or abs(p[2]-z)>3.5:continue
            stamp=prev[0]+f*(time-prev[0])
            if idx==0:
                if state['start'] is not None:
                    lap=round(stamp-state['start'],3);state['last']=lap
                    state['best']=min(state['best'],lap) if state['best'] is not None else lap;state['laps']+=1
                state['start']=stamp;state['splits']=[]
            elif c.get('sprint') and idx==len(c['gates'])-1:
                # A point-to-point course finishes at its last gate and waits for the start again.
                result=round(stamp-state['start'],3);state['last']=result;state['laps']+=1
                state['best']=min(state['best'],result) if state['best'] is not None else result
                state['start']=None;state['next']=0;continue
            else:state['splits'].append(round(stamp-state['start'],3))
            state['next']=(idx+1)%len(c['gates'])

    def restore(self,saved):
        if set(saved['runs'])!=set(self.runs):raise ValueError('Timing gates belong to a different course')
        self.previous=saved['previous'];self.runs=saved['runs']

    def save(self):
        return dict(previous=self.previous,runs=self.runs)
