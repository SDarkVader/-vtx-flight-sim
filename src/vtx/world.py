"""Stage 1 only. Shared terrain data for renderer, contact and map validation."""
from __future__ import annotations
from dataclasses import asdict
import math
import numpy as np
from .mission_selection import MapPoint, SurfaceDecision


class TestWorld:
    __test__ = False
    id = 'stage1-extended-airfield-recovery'
    version = '4'
    environment_key = 'airport'
    label = 'Main Airport'
    half = 4000.
    n = 401
    default_departure = [-700., 0.]
    default_destination = [-50., 20.]
    def __init__(self, seed=41031):
        self.seed = seed
        xs = np.linspace(-self.half,self.half,self.n)
        x,y = np.meshgrid(xs,xs)
        edge=np.clip((np.maximum(abs(x),abs(y))-220)/240,0,1)
        edge=edge*edge*(3-2*edge)
        self.heights = edge*(22+14*np.sin(x/81)**2+21*np.cos(y/107)**2)
        # The east/west takeoff strip continues past the former 500 m
        # heightfield boundary. Blend smoothly into the existing hills at
        # its sides; the same samples drive collision and rendering.
        shoulder = np.clip((np.abs(y) - 30.) / 40., 0., 1.)
        shoulder = shoulder * shoulder * (3. - 2. * shoulder)
        self.heights *= shoulder
        self.obstacles = [
            dict(id='hangar',kind='box',center=[85.,45.,9.],half=[23.,17.,9.],color='#606f7a',landable=True),
            dict(id='workshop',kind='box',center=[150.,-95.,5.],half=[23.,21.,5.],color='#627970',landable=True),
            dict(id='tower',kind='box',center=[115.,115.,29.],half=[9.,9.,29.],color='#71838a',landable=False),
            dict(id='freight',kind='box',center=[-100.,105.,4.],half=[18.,11.,4.],color='#ae735c',landable=True),
            dict(id='ridge-block',kind='box',center=[-175.,-110.,12.],half=[14.,30.,12.],color='#747b76',landable=False),
            dict(id='dispatch',kind='box',center=[45.,110.,12.],half=[14.,12.,12.],color='#355453',landable=True),
            dict(id='arcade',kind='box',center=[185.,45.,6.],half=[15.,11.,6.],color='#634e56',landable=True),
            dict(id='operations',kind='box',center=[50.,-145.,8.],half=[15.,12.,8.],color='#496c70',landable=True),
            dict(id='terminal',kind='box',center=[-145.,100.,7.],half=[15.,12.,7.],color='#725d50',landable=True),
        ]
        rng=np.random.default_rng(seed)
        for i in range(36):
            angle=rng.uniform(0,2*math.pi);r=rng.uniform(125,210)
            cx,cy=r*np.cos(angle),r*np.sin(angle)
            if abs(cy) < 38:
                continue
            if any(abs(cx-o['center'][0])<o['half'][0]+12 and abs(cy-o['center'][1])<o['half'][1]+12 for o in self.obstacles):continue
            height=float(rng.uniform(5,13));radius=float(rng.uniform(.7,1.6))
            self.obstacles.append(dict(id=f'tree-{i}',kind='cylinder',center=[float(cx),float(cy),height/2],half=[radius,radius,height/2],color='#536a55',landable=False))
        self.water=dict(x=-265.,y=30.,half_x=28.,half_y=80.)

    def terrain_z(self,x,y):
        """Exact piecewise planar interpolation of the same heightfield samples."""
        u=np.clip((x+self.half)/(2*self.half)*(self.n-1),0,self.n-1.000001)
        v=np.clip((y+self.half)/(2*self.half)*(self.n-1),0,self.n-1.000001)
        i,j=int(u),int(v);a,b=u-i,v-j
        h=self.heights
        # MuJoCo heightfield cell uses the lower-left/upper-right diagonal.
        if a>b:return float((1-a)*h[j,i]+(a-b)*h[j,i+1]+b*h[j+1,i+1])
        return float((1-b)*h[j,i]+(b-a)*h[j+1,i]+a*h[j+1,i+1])

    def surface_z(self,x,y):
        z=self.terrain_z(x,y)
        for o in self.obstacles:
            if o['kind']=='box' and abs(x-o['center'][0])<=o['half'][0] and abs(y-o['center'][1])<=o['half'][1]:
                z=max(z,o['center'][2]+o['half'][2])
        return z

    def validate(self,point:MapPoint,purpose:str) -> SurfaceDecision:
        x,y=point.x_m,point.y_m
        if max(abs(x),abs(y))>self.half-8:return SurfaceDecision(False,'Outside the surveyed terrain support boundary')
        w=self.water
        if abs(x-w['x'])<w['half_x']+4 or abs(y-w['y'])<w['half_y']+4:
            if abs(x-w['x'])<w['half_x']+4 and abs(y-w['y'])<w['half_y']+4:
                return SurfaceDecision(False,'Water: no flotation or submerged support model')
        z=self.surface_z(x,y)
        foot_z=[self.surface_z(x+1.9*math.cos(a),y+1.9*math.sin(a)) for a in np.arange(6)*math.pi/3]
        if max(foot_z)-min(foot_z)>.065:return SurfaceDecision(False,'Uneven six-foot support exceeds the provisional preflight limit')
        for a in np.linspace(0,2*math.pi,25)[:-1]:
            px,py=x+4.1*math.cos(a),y+4.1*math.sin(a)
            if self.surface_z(px,py)>z+.15:return SurfaceDecision(False,'Aircraft swept footprint intersects a surface edge or obstacle')
        for o in self.obstacles:
            ox,oy,oz=o['center'];hx,hy,hz=o['half']
            dx=max(abs(x-ox)-hx,0);dy=max(abs(y-oy)-hy,0)
            inside=abs(x-ox)<=hx and abs(y-oy)<=hy
            if inside and z>=oz+hz-.01:
                if not o['landable']:return SurfaceDecision(False,'This structure is not a supported landing surface')
                if hx-abs(x-ox)<4.5 or hy-abs(y-oy)<4.5:return SurfaceDecision(False,'Roof edge: insufficient rotor and gear margin')
            elif math.hypot(dx,dy)<5.5 and oz+hz>z+.2:
                return SurfaceDecision(False,'Obstacle blocks rotor clearance or the immediate vertical approach column')
        # This verifies a local vertical approach column, not an obstacle-free route.
        return SurfaceDecision(True,'Six-foot support, swept footprint and local vertical approach column are clear',z)

    def public(self):
        return dict(id=self.id,version=self.version,environment=self.environment_key,
                    label=self.label,seed=self.seed,half_m=self.half,
                    default_departure=list(self.default_departure),
                    default_destination=list(self.default_destination),
                    heights_m=self.heights.tolist(),obstacles=self.obstacles,water=self.water,
                    scale_m=100,validation='Local support and vertical approach only; pilot must assess the route')


class SandboxWorld(TestWorld):
    id = 'stage1-valley'
    version = '2'
    environment_key = 'sandbox'
    label = 'Test Sandbox'
    half = 1000.
    n = 201
    default_departure = [-700., 0.]
    default_destination = [-50., 20.]

    def __init__(self, seed=41031):
        self.seed = seed
        xs = np.linspace(-self.half, self.half, self.n)
        x, y = np.meshgrid(xs, xs)
        edge = np.clip((np.maximum(abs(x), abs(y)) - 220) / 240, 0, 1)
        edge = edge * edge * (3 - 2 * edge)
        self.heights = edge * (22 + 14 * np.sin(x / 81) ** 2 + 21 * np.cos(y / 107) ** 2)
        # Extended east-west runway corridor (+X / Heading 090) matching the
        # Phantom A10-B spawn orientation so the vehicle faces directly down
        # a 1,900 m flat takeoff strip.
        shoulder = np.clip((np.abs(y) - 30.) / 40., 0., 1.)
        shoulder = shoulder * shoulder * (3. - 2. * shoulder)
        self.heights *= shoulder
        self.obstacles = [
            dict(id='hangar', kind='box', center=[85., 45., 9.], half=[23., 17., 9.], color='#606f7a', landable=True),
            dict(id='workshop', kind='box', center=[150., -95., 5.], half=[23., 21., 5.], color='#627970', landable=True),
            dict(id='tower', kind='box', center=[115., 115., 29.], half=[9., 9., 29.], color='#71838a', landable=False),
            dict(id='freight', kind='box', center=[-100., 105., 4.], half=[18., 11., 4.], color='#ae735c', landable=True),
            dict(id='ridge-block', kind='box', center=[-175., -110., 12.], half=[14., 30., 12.], color='#747b76', landable=False),
        ]
        rng = np.random.default_rng(seed)
        for i in range(36):
            angle = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(125, 210)
            cx, cy = r * np.cos(angle), r * np.sin(angle)
            if abs(cy) < 38:
                continue
            if any(abs(cx - o['center'][0]) < o['half'][0] + 12 and abs(cy - o['center'][1]) < o['half'][1] + 12 for o in self.obstacles):
                continue
            height = float(rng.uniform(5, 13))
            radius = float(rng.uniform(.7, 1.6))
            self.obstacles.append(dict(id=f'tree-{i}', kind='cylinder', center=[float(cx), float(cy), height / 2], half=[radius, radius, height / 2], color='#536a55', landable=False))
        self.water = dict(x=-265., y=140., half_x=28., half_y=80.)


ENVIRONMENTS = {
    'airport': TestWorld,
    'sandbox': SandboxWorld,
}

ENVIRONMENT_ALIASES = {
    'airport': 'airport',
    'main-airport': 'airport',
    'main_airport': 'airport',
    'stage1-extended-airfield-recovery': 'airport',
    'sandbox': 'sandbox',
    'test-sandbox': 'sandbox',
    'test_sandbox': 'sandbox',
    'stage1-valley': 'sandbox',
}


def resolve_environment_key(value) -> str:
    if value is None:
        return 'airport'
    if not isinstance(value, str):
        raise ValueError('Unknown environment')
    key = ENVIRONMENT_ALIASES.get(value.strip().lower())
    if key is None:
        raise ValueError('Unknown environment')
    return key


def make_world(environment: str | None = 'airport', seed: int = 41031):
    key = resolve_environment_key(environment)
    return ENVIRONMENTS[key](seed=seed)
