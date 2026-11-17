// Pilot-view presentation only. Source geometry, cabin eye and vehicle state
// are unchanged; the same material is restored when leaving the cockpit.
const originals=new WeakMap();
export function isArgonRotorHousing(node){
  const name=(node.name||'').replaceAll('_',' ');
  const body=node.userData?.physical_body||node.parent?.name||'';
  return !!node.isMesh && (node.userData.argonRotorHousing || /^nacelle[1-4]$/.test(body)&&!node.userData.pitch_axis || /^P02.*F[1-4].*(open annular duct|nacelle inlet lip|pitch actuator ring)/.test(name) || /^Phase2 Duct (Livery Band|Lip Glow) F[1-4]/.test(name));
}
export function setArgonCutaway(root,enabled){
  root?.traverse(node=>{
    if(!isArgonRotorHousing(node))return;
    const original=originals.get(node);
    if(!enabled){
      if(original){for(const m of [].concat(node.material))m.dispose();node.material=original;originals.delete(node);}
      return;
    }
    if(original)return;
    originals.set(node,node.material);
    const cut=source=>{
      const m=source.clone();m.transparent=true;m.depthWrite=false;
      m.onBeforeCompile=(shader,renderer)=>{
        source.onBeforeCompile.call(m,shader,renderer);
        shader.fragmentShader=shader.fragmentShader.replace('#include <opaque_fragment>',`
          float sight = smoothstep(0.72,0.93,normalize(vViewPosition).z);
          float nearby = 1.0-smoothstep(4.5,5.0,length(vViewPosition));
          diffuseColor.a *= mix(1.0,0.055,sight*nearby);
          #include <opaque_fragment>`);
      };
      m.customProgramCacheKey=()=> 'vtx-argon-pilot-cutaway-v1';
      return m;
    };
    node.material=Array.isArray(node.material)?node.material.map(cut):cut(node.material);
  });
}
