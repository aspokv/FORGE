import {Suspense,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {Environment,Lightformer,ContactShadows,Html,useGLTF,useTexture,PerformanceMonitor} from '@react-three/drei';
import {MathUtils,Vector3,SRGBColorSpace,LinearFilter,LinearMipmapLinearFilter} from 'three';
import {PRODUCT} from '../config';
import {SCREEN_CAPTURES,screenBlend} from './screenSequence';
import ScreenSurface from './ScreenSurface';
import {screenDpr,performanceBounds} from './renderQuality';

function Device({progress,finish,rotation,autoRotate,reduced,onHotspot,mobile}){
 const {nodes}=useGLTF(PRODUCT.modelUrl,PRODUCT.dracoPath);const group=useRef();const refs=useRef({});
 const textures=useTexture(Object.fromEntries(Object.entries(SCREEN_CAPTURES).map(([id,s])=>[id,s.src])));
 const gl=useThree(state=>state.gl);
 useEffect(()=>{Object.values(textures).forEach(t=>{t.colorSpace=SRGBColorSpace;t.anisotropy=Math.min(8,gl.capabilities.getMaxAnisotropy());t.magFilter=LinearFilter;t.minFilter=LinearMipmapLinearFilter;t.generateMipmaps=true;t.needsUpdate=true;})},[textures,gl]);
 const position=useMemo(()=>new Vector3(),[]);
 useFrame(({camera,clock},delta)=>{
  const dt=Math.min(delta,.05), p=progress.current;
  const zoom=Math.sin(Math.min(1,p/.37)*Math.PI)*.85;
  const exploded=MathUtils.smoothstep(p,.37,.53)*(1-MathUtils.smoothstep(p,.72,.91));
  if(autoRotate&&!reduced)rotation.current.x+=dt*.45;
  group.current.rotation.y=MathUtils.damp(group.current.rotation.y,(mobile?-.18:-.30)+Math.sin(p*Math.PI*2)*(mobile?.24:.36)+rotation.current.x+screenBlend(p).turn,5,dt);
  group.current.rotation.x=MathUtils.damp(group.current.rotation.x,.07+rotation.current.y,5,dt);
  group.current.rotation.z=MathUtils.damp(group.current.rotation.z,-.055*(1-exploded),5,dt);
  group.current.position.y=reduced?0:Math.sin(clock.elapsedTime*.65)*.035;
  const offsets={Body:-exploded*.95,Rim:-exploded*.85,Screen:.19+exploded*1.25,Nutrition:.16+exploded*.53,Evolution:.13-exploded*.21};
  Object.entries(refs.current).forEach(([key,mesh])=>{if(mesh)mesh.position.z=MathUtils.damp(mesh.position.z,offsets[key]??0,6,dt)});
  position.set(mobile?0:.1, .05+zoom*.35,mobile?8.65-zoom:8.15-zoom*1.1);camera.position.lerp(position,1-Math.exp(-dt*4));camera.lookAt(0,.1,0);
 });
 const selected=PRODUCT.finishes[finish];
 return <group ref={group} scale={mobile?.94:1}>
  {['Body','Rim','Evolution','Nutrition','Screen'].map(name=>{const node=nodes[PRODUCT.parts[name.toLowerCase()]]||nodes[name];if(!node)return null;const isFace=['Screen','Nutrition','Evolution'].includes(name);return <mesh key={name} ref={el=>refs.current[name]=el} geometry={node.geometry} position={node.position} castShadow receiveShadow>
   <meshStandardMaterial color={isFace?'#111111':selected.color} metalness={isFace?.15:selected.metalness} roughness={isFace?.44:selected.roughness}/>
   {isFace&&<ScreenSurface textures={textures} progress={progress} fixed={name==='Screen'?undefined:name==='Nutrition'?'nutrition':'meals'}/>}
   {name==='Body'&&<mesh position={[0,0,-.108]} rotation={[0,Math.PI,0]}><ringGeometry args={[.31,.37,48]}/><meshStandardMaterial color="#ff632b" metalness={.7} roughness={.3}/></mesh>}
  </mesh>})}
  {[['Treino',[1.18,.95,1.4],0],['Alimentação',[-1.18,0,.65],1],['Refeições',[1.18,-1.25,-.1],2]].map(([label,pos,index])=><Html key={label} position={pos} center zIndexRange={[20,10]} style={{display:progress.current>.41&&progress.current<.78?'block':'none'}}><button className="hotspot" onClick={()=>onHotspot(index)} aria-label={`Explorar ${label}`}><span>+</span><b>{label}</b></button></Html>)}
 </group>;
}
export default function ProductScene(props){
 const [nativeDpr,setNativeDpr]=useState(()=>window.devicePixelRatio||1);
 const [quality,setQuality]=useState(1);
 useEffect(()=>{
  const resize=()=>setNativeDpr(window.devicePixelRatio||1);
  window.addEventListener('resize',resize);
  return()=>window.removeEventListener('resize',resize);
 },[]);
 const dpr=screenDpr(nativeDpr,quality);
 return <Canvas frameloop={props.active?'always':'never'} shadows={!props.mobile} dpr={dpr} camera={{position:[0,0,8.2],fov:38}} gl={{antialias:true,alpha:true,powerPreference:'high-performance'}} onCreated={({gl})=>{gl.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();props.onFailure()},{once:true})}}>
  <ambientLight intensity={.55}/><directionalLight position={[4,7,5]} intensity={3}/><directionalLight position={[-5,1,2]} intensity={1.8} color="#e5e8f0"/>
  <Suspense fallback={null}><Environment resolution={props.mobile?128:256}><Lightformer form="rect" intensity={4} position={[0,4,3]} scale={[8,2,1]}/><Lightformer form="rect" intensity={3} position={[-4,0,2]} rotation={[0,Math.PI/3,0]} scale={[2,8,1]}/><Lightformer form="rect" color="#ff763f" intensity={1.3} position={[4,-1,-2]} rotation={[0,-Math.PI/3,0]} scale={[2,7,1]}/></Environment>
  <Device {...props}/>{!props.mobile&&<ContactShadows position={[0,-2.75,0]} opacity={.28} scale={12} blur={2.5} far={6} resolution={256} frames={1}/>}
  {props.active&&<PerformanceMonitor bounds={performanceBounds} ms={250} iterations={10} threshold={.75} onDecline={()=>setQuality(q=>Math.max(0,q-.25))} onIncline={()=>setQuality(q=>Math.min(1,q+.25))}/>}
  </Suspense>
 </Canvas>;
}
