import * as THREE from 'three';

const finishes={
  loopStone:'c=stone*(.46+.54*key)+sky*.19;',
  loopMetal:'c=(vec3(.014,.020,.031)+grain*.15)*(.56+.56*key)+sky*.26;',
  loopBed:'c=texture2D(asphaltColor,uv*.23).rgb*(.28+.52*key)+sky*.14;',
  loopBank:'c=(vec3(.026,.022,.036)+texture2D(asphaltColor,uv*.29).rgb*.46)*(.43+.55*key)+sky*.18;',
  loopGold:'c=vec3(3.5,1.08,.19);',
  loopViolet:'c=vec3(1.73,.47,3.28);',
};

function hullBatches(group,world,uniforms,common){
  const layers=new Map();
  for(const shape of world.obstacles){
    if(!shape.id.startsWith('vertical-loop-'))continue;
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
      uniforms,
      vertexShader:'varying vec3 p,n;void main(){p=position;n=normal;gl_Position=projectionMatrix*viewMatrix*vec4(p,1.);}',
      fragmentShader:common+"\n"+[
        'uniform sampler2D alloyColor,granite,asphaltColor;',
        'void main(){',
        'vec3 N=normalize(n),R=reflect(normalize(p-cameraPosition),N);',
        'float key=max(dot(N,sun),0.);',
        'vec2 uv=vec2(.51*p.x+.74*p.y,p.z+.31*p.x-.21*p.y);',
        'vec3 grain=texture2D(alloyColor,uv*.48).rgb;',
        'vec3 stone=texture2D(granite,uv*.32).rgb;',
        'vec3 sky=skySample(daySky,R),c;',
        finishes[finish],
        'gl_FragColor=vec4(haze(c),1.);',
        '#include <colorspace_fragment>',
        '}',
      ].join('\n'),
    });
    const mesh=new THREE.Mesh(geo,material);
    mesh.name='Cathedral vertical loops '+finish;
    mesh.userData.surveySpans=batch.spans;
    group.add(mesh);
  }
}

function strip(group,positions,material,name){
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
  const mesh=new THREE.Mesh(geo,material);
  mesh.name=name;
  group.add(mesh);
}

function quad(layers,key,a,b,c,d){
  for(const vertex of [a,b,c,c,b,d])layers[key].push(...vertex.toArray());
}

function deckDetail(group,track){
  const sections=track.cross_sections.map(row=>row.map(p=>new THREE.Vector3(...p)));
  const normals=track.normals.map(p=>new THREE.Vector3(...p));
  const layers={under:[],web:[],edge:[],glow:[],mark:[],warning:[]};
  const tint=new THREE.Color(track.color);
  const graphMaterials={
    under:new THREE.MeshBasicMaterial({color:0x232833,side:THREE.DoubleSide}),
    web:new THREE.MeshBasicMaterial({color:0x212e43,side:THREE.DoubleSide}),
    edge:new THREE.MeshBasicMaterial({color:tint.clone().multiplyScalar(2.2),side:THREE.DoubleSide,toneMapped:false}),
    glow:new THREE.MeshBasicMaterial({color:tint,side:THREE.DoubleSide,toneMapped:false,
      blending:THREE.AdditiveBlending,transparent:true,opacity:.19,depthWrite:false}),
    mark:new THREE.MeshBasicMaterial({color:0xaaa5a1,side:THREE.DoubleSide}),
    warning:new THREE.MeshBasicMaterial({color:tint,side:THREE.DoubleSide}),
  };
  const normalLift=(v,i,h)=>v.clone().addScaledVector(normals[i],h);
  const edge=(i,side,h,extra=0)=>normalLift(sections[i][side===-1?0:3],i,h)
    .add(new THREE.Vector3(0,extra*side,0));
  const lane=(i,n)=>normalLift(sections[i][1].clone().lerp(sections[i][2],n),i,.032);
  let length=0;
  for(let i=1;i<sections.length;i++){
    length+=sections[i][1].distanceTo(sections[i-1][1]);
    const onLoop=i>=track.loop_in && i<=track.loop_out;
    const withRails=i>8 && i<sections.length-8;
    if(withRails)for(const side of [-1,1]){
      const deep=onLoop?2.28:1.23;
      quad(layers,'under',edge(i-1,side,-.16,.025),edge(i-1,side,-.82,.025),
        edge(i,side,-.16,.025),edge(i,side,-.82,.025));
      quad(layers,'under',edge(i-1,side,-deep,.09),edge(i-1,side,-deep-.32,.09),
        edge(i,side,-deep,.09),edge(i,side,-deep-.32,.09));
      if(onLoop){
        quad(layers,'web',edge(i-1,side,-.77,.027),edge(i-1,side,-.96,.027),
          edge(i,side,-deep-.12,.091),edge(i,side,-deep-.30,.091));
      }
      quad(layers,'edge',edge(i-1,side,-.17,.05),edge(i-1,side,-.43,.05),
        edge(i,side,-.17,.05),edge(i,side,-.43,.05));
      quad(layers,'glow',edge(i-1,side,-.04,.039),edge(i-1,side,-.60,.039),
        edge(i,side,-.04,.039),edge(i,side,-.60,.039));
    }
    if(withRails){
      for(const [a,b] of [[.025,.063],[.937,.975]]){
        quad(layers,'mark',lane(i-1,a),lane(i-1,b),lane(i,a),lane(i,b));
      }
    }
    if(withRails && length%12<4){
      quad(layers,'mark',lane(i-1,.488),lane(i-1,.512),lane(i,.488),lane(i,.512));
    }
    if(withRails && !onLoop && i%4===0){
      for(const [a,b] of [[.10,.19],[.81,.9]]){
        quad(layers,'warning',lane(i-1,a),lane(i-1,b),lane(i,a+.045),lane(i,b+.045));
      }
    }
  }
  for(const [key,positions] of Object.entries(layers))
    strip(group,positions,graphMaterials[key],track.name+' '+key);
}

function entrySign(group,track){
  const board=document.createElement('canvas');board.width=1024;board.height=148;
  const pen=board.getContext('2d'), gold=track.color;
  const [lead,title]=track.id==='full'?['CATHEDRAL','GRAND LOOP']:['CATHEDRAL','SWITCHBACK'];
  pen.fillStyle='#11151d';pen.fillRect(0,0,1024,148);
  pen.strokeStyle=gold;pen.lineWidth=6;pen.strokeRect(12,9,1000,130);
  pen.textAlign='center';pen.fillStyle=gold;pen.font='800 24px system-ui';
  pen.fillText(lead,512,42);
  pen.fillStyle='#fff0d9';pen.font='italic 900 64px system-ui';
  pen.fillText(title,512,112);
  for(const x of [66,918]){
    pen.fillStyle=gold;pen.font='900 88px system-ui';pen.fillText('›',x+19,111);
  }
  const texture=new THREE.CanvasTexture(board);texture.colorSpace=THREE.SRGBColorSpace;
  const portrait=new THREE.Mesh(new THREE.PlaneGeometry(track.width_m+1.85,1.43),
    new THREE.MeshBasicMaterial({map:texture,toneMapped:false}));
  portrait.rotation.set(Math.PI/2,0,-Math.PI/2,'ZYX');
  portrait.position.set(...track.sign);
  portrait.position.x-=.105;
  portrait.name=track.name+' entry lettering';
  group.add(portrait);
}

export function buildVerticalLoops(group,world,uniforms,common){
  hullBatches(group,world,uniforms,common);
  for(const track of world.vaderland.vertical_loops){
    deckDetail(group,track);
    entrySign(group,track);
  }
}