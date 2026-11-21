// Where people are: a smoothed floor-area density of Meridian and the airport, computed from the
// surveyed architecture (footprint x storeys per 100 m cell, blurred over about 200 m).
// Light, traffic and fog glow follow it, so the busy core is bright, the wards are dim and
// open land is dark.
export const DENSITY_BOUNDS={x0:-4200,x1:4200,y0:-1300,y1:5900,cell:100};

export function cityDensity(w){
  const {x0,x1,y0,y1,cell}=DENSITY_BOUNDS;
  const nx=Math.round((x1-x0)/cell),ny=Math.round((y1-y0)/cell);
  let g=new Float32Array(nx*ny);
  for(const o of w.obstacles){
    if(o.role!=='architecture')continue;
    const [x,y]=o.center,[a,b,c]=o.half;
    if(x<x0||x>x1||y<y0||y>y1)continue;
    const foot=o.kind==='cylinder'?Math.PI*a*a:4*a*b;
    const floors=Math.min(60,Math.max(1,2*c/3.5));
    const i0=Math.max(0,Math.floor((x-a-x0)/cell)),i1=Math.min(nx-1,Math.floor((x+a-x0)/cell));
    const j0=Math.max(0,Math.floor((y-b-y0)/cell)),j1=Math.min(ny-1,Math.floor((y+b-y0)/cell));
    const share=foot*floors/((i1-i0+1)*(j1-j0+1))/(cell*cell);
    for(let j=j0;j<=j1;j++)for(let i=i0;i<=i1;i++)g[j*nx+i]+=share;
  }
  for(let pass=0;pass<3;pass++)g=blur(g,nx,ny,2);
  const level=new Float32Array(nx*ny);
  for(let k=0;k<g.length;k++)level[k]=1-Math.exp(-Math.max(0,g[k])/1.6);
  function sample(x,y){
    const u=(x-x0)/cell-.5,v=(y-y0)/cell-.5;
    const i=Math.floor(u),j=Math.floor(v),fu=u-i,fv=v-j;
    const at=(a,b)=>(a<0||b<0||a>=nx||b>=ny)?0:level[b*nx+a];
    return (at(i,j)*(1-fu)+at(i+1,j)*fu)*(1-fv)+(at(i,j+1)*(1-fu)+at(i+1,j+1)*fu)*fv;
  }
  return {sample,level,nx,ny,bounds:DENSITY_BOUNDS};
}

function blur(src,nx,ny,r){
  const tmp=new Float32Array(nx*ny),out=new Float32Array(nx*ny),n=2*r+1;
  for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){let s=0;for(let k=-r;k<=r;k++){const q=Math.min(nx-1,Math.max(0,i+k));s+=src[j*nx+q];}tmp[j*nx+i]=s/n;}
  for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){let s=0;for(let k=-r;k<=r;k++){const q=Math.min(ny-1,Math.max(0,j+k));s+=tmp[q*nx+i];}out[j*nx+i]=s/n;}
  return out;
}

// Deterministic 0..1 hash of a position, for thinning lamps and traffic without randomness.
export function hash2(x,y){
  const s=Math.sin(x*12.9898+y*78.233)*43758.5453;return s-Math.floor(s);
}
