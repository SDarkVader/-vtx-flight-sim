import * as THREE from 'three';

// The fleet already publishes these boxes. The board finish uses those same
// meshes and follows their authoritative transform on restore.
export function dressHarbourDecks(harbour,decks,uniforms,common){
  const mat=new THREE.ShaderMaterial({uniforms,vertexShader:`
    varying vec3 p; varying vec3 n; varying vec2 deck; varying vec2 dimensions;
    void main(){
      vec4 wp=modelMatrix*vec4(position,1.);p=wp.xyz;
      n=normalize(mat3(modelMatrix)*normal);
      dimensions=vec2(length(modelMatrix[0].xyz),length(modelMatrix[1].xyz));
      deck=position.xy*dimensions;gl_Position=projectionMatrix*viewMatrix*wp;
    }`,fragmentShader:'varying vec2 deck;varying vec2 dimensions;'+common+`
    void main(){
      float board=floor(deck.x/.34),s=fract(deck.x/.34);
      float groove=min(s,1.-s)*.34;
      float joint=(1.-smoothstep(.007,.020+min(.025,fwidth(groove)),groove))*(1.-smoothstep(.036,.20,fwidth(deck.x)));
      float timber=fbm(vec2(deck.x*13.,deck.y*.64));
      vec3 c=mix(vec3(.065,.045,.034),vec3(.24,.142,.075),.30+.50*timber+.18*hash(vec2(board,14.)));
      c*=1.-.58*joint;
      float edge=dimensions.y*.5-abs(deck.y);
      float trim=1.-smoothstep(.08,.16,edge);
      c=mix(c,vec3(.030,.046,.058),trim);
      float inset=(1.-smoothstep(.08,.15,abs(edge-.25)))*(1.-smoothstep(.24,.35,abs(mod(deck.x+2.,4.)-2.)));
      c+=vec3(.88,.48,.12)*inset;
      if(abs(n.z)<.65){
        c=vec3(.031,.050,.065)*(.76+.36*cos(deck.x*3.1));
        c+=vec3(.67,.32,.069)*(1.-smoothstep(.028,.080,abs(p.z-7.94)));
      }
      gl_FragColor=vec4(haze(c*mix(1.,.72,night)),1.);
      #include <colorspace_fragment>
    }`});
  for(const [name,collider] of decks){
    const node=harbour.structureNodes.get(name);
    node.material.dispose();node.material=mat;
    node.userData.sceneryIds=[collider];
  }
}

export function dressLanding(group,w,harbour,uniforms,common){
  dressHarbourDecks(harbour,w.vaderland.landing.chart_structures.map(id=>[id,'deck-'+id]),uniforms,common);
  const c=document.createElement('canvas');c.width=1024;c.height=128;
  const x=c.getContext('2d');x.fillStyle='#152633';x.fillRect(0,0,c.width,c.height);
  x.fillStyle='#f1b35e';x.fillRect(0,120,1024,5);x.font='600 75px system-ui';
  x.textAlign='center';x.fillText('AIRPORT   LANDING',512,91);
  const map=new THREE.CanvasTexture(c);map.colorSpace=THREE.SRGBColorSpace;map.anisotropy=8;
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(9.3,.62),new THREE.MeshBasicMaterial({map,side:THREE.FrontSide}));
  sign.position.set(142,-542.12,15.68);sign.rotation.x=Math.PI/2;group.add(sign);
}
