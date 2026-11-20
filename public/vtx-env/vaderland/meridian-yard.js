import * as THREE from 'three';

export function buildMeridianYard(group,world,uniforms,common){
  const finishes={
    yardStone: 'c=stone*(.31+.50*key)+sky*.14;',
    yardMetal: 'c=(vec3(.022,.029,.035)+grain*.31)*(.46+.63*key)+sky*.23;',
    yardAmber: 'c=vec3(2.42,.94,.27)*(.72+.28*night);',
    yardTeal: 'c=vec3(.17,1.50,1.49)*(.72+.28*night);',
  };
  const layers=new Map();
  for(const shape of world.obstacles){
    if(!shape.id.startsWith('yard-'))continue;
    if(!layers.has(shape.skin))layers.set(shape.skin,{vertices:[],spans:[]});
    const batch=layers.get(shape.skin);
    for(const face of shape.faces)for(const index of face){
      batch.vertices.push(...shape.vertices[index].map((v,k)=>v+shape.center[k]));
    }
    batch.spans.push({end:batch.vertices.length/9,id:shape.id});
  }
  for(const [finish,batch] of layers){
    const geo=new THREE.BufferGeometry();
    geo.setAttribute('position',new THREE.Float32BufferAttribute(batch.vertices,3));
    geo.computeVertexNormals();
    const material=new THREE.ShaderMaterial({
      uniforms,side:THREE.DoubleSide,
      vertexShader:'varying vec3 p,n;void main(){p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
      fragmentShader:common+"\n"+[
        'uniform sampler2D alloyColor,granite;',
        'void main(){',
        'vec3 N=normalize(n)*(gl_FrontFacing?1.:-1.);',
        'vec3 R=reflect(normalize(p-cameraPosition),N);',
        'float key=max(dot(N,sun),0.);',
        'vec2 uv=vec2(.48*p.x+.72*p.y,p.z+.35*p.x-.23*p.y);',
        'vec3 grain=texture2D(alloyColor,uv*.44).rgb;',
        'vec3 stone=texture2D(granite,uv*.29).rgb;',
        'vec3 sky=skySample(daySky,R),c;',
        finishes[finish],
        'gl_FragColor=vec4(haze(c),1.);',
        '#include <colorspace_fragment>',
        '}',
      ].join('\n'),
    });
    const mesh=new THREE.Mesh(geo,material);
    mesh.name='Meridian Handling Yard '+finish;
    mesh.userData.surveySpans=batch.spans;
    group.add(mesh);
  }
}
