import {writeFileSync,mkdirSync} from 'node:fs';
import {Group,Mesh,MeshStandardMaterial} from 'three';
import {RoundedBoxGeometry} from 'three/addons/geometries/RoundedBoxGeometry.js';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
globalThis.FileReader=class {readAsArrayBuffer(blob){blob.arrayBuffer().then(b=>{this.result=b;this.onloadend?.()})}readAsDataURL(blob){blob.arrayBuffer().then(b=>{this.result=`data:${blob.type};base64,${Buffer.from(b).toString('base64')}`;this.onloadend?.()})}};
const model=new Group();model.name='ForgeDevice';
function part(name,size,z,color,metalness=.8){const m=new Mesh(new RoundedBoxGeometry(...size,3,.13),new MeshStandardMaterial({color,metalness,roughness:.24}));m.name=name;m.position.z=z;model.add(m)}
part('Body',[2.94,4.8,.2],0,'#292929');
part('Rim',[2.96,4.82,.07],.08,'#7b7b7b');
part('Evolution',[2.77,4.62,.03],.13,'#242424');
part('Nutrition',[2.77,4.62,.03],.16,'#191919');
part('Screen',[2.79,4.64,.035],.19,'#070707',.05);
const glb=await new GLTFExporter().parseAsync(model,{binary:true});mkdirSync('public/models',{recursive:true});writeFileSync('public/models/forge-device.glb',Buffer.from(glb));console.log(`Created ${glb.byteLength} byte demo GLB`);
