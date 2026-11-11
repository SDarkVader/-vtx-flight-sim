const fs=require('fs');
const f=process.argv[2], b=fs.readFileSync(f);
if(b.toString('utf8',0,4)!=='glTF')throw Error('Not GLB');
const jlen=b.readUInt32LE(12),doc=JSON.parse(b.subarray(20,20+jlen).toString('utf8'));
const nodes=doc.nodes||[],parent=new Map();nodes.forEach((n,i)=>(n.children||[]).forEach(k=>parent.set(k,i)));
const pathOf=i=>{let a=[];for(let k=i;k!==undefined;k=parent.get(k)){a.unshift(nodes[k].name||'#'+k);if(a.length>40)break;}return a.join(' > ')};
console.log('file',f,'nodes',nodes.length,'meshes',doc.meshes?.length,'scene',doc.scene,'root node count',doc.scenes?.[doc.scene||0]?.nodes?.length);
console.log('metadata',JSON.stringify({withPhysicalBody:nodes.filter(n=>n.extras?.physical_body).length,withPhantomJoint:nodes.filter(n=>n.extras?.phantom_joint).length,namedBodies:nodes.filter(n=>/^(airframe|cabin|nacelle[1-4]|rotor[1-4])$/.test(n.name||'')).map(n=>n.name)}));
for(let i=0;i<nodes.length;i++){
 const n=nodes[i];if(/^(VTX_VISUAL_ZUP_ROOT|airframe|cabin|nacelle[1-4]|rotor[1-4]|gear[1-6]|shaft[1-4])$|beacon|pivot|route|target|cg|centre|center|origin/i.test(n.name||'')||n.extras?.physical_body==='airframe'){
 console.log('NODE',i,'name',n.name,'parent',parent.get(i),'path',pathOf(i),'T',JSON.stringify(n.translation),'R',JSON.stringify(n.rotation),'S',JSON.stringify(n.scale),'mesh',n.mesh,'extras',(JSON.stringify(n.extras)||'').slice(0,180));
 }}
