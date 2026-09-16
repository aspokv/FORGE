import {useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import {CAPTURE_ASPECT,SCREEN_CAPTURES,screenBlend} from './screenSequence';
export default function ScreenSurface({textures,progress,fixed}){
 const front=useRef();const next=useRef();const fromMesh=useRef();const toMesh=useRef();
 useFrame(()=>{
  if(!front.current||!next.current)return;
  const state=fixed?{from:fixed,to:fixed,mix:0}:screenBlend(progress.current);
  const from=textures[state.from],to=textures[state.to];
  if(front.current.map!==from){front.current.map=from;front.current.needsUpdate=true;}
  if(next.current.map!==to){next.current.map=to;next.current.needsUpdate=true;}
  next.current.opacity=state.mix;
  fromMesh.current.scale.x=4.43*SCREEN_CAPTURES[state.from].width/SCREEN_CAPTURES[state.from].height;
  toMesh.current.scale.x=4.43*SCREEN_CAPTURES[state.to].width/SCREEN_CAPTURES[state.to].height;
 });
 const dimensions=[1,1];const scale=[4.43*CAPTURE_ASPECT,4.43,1];
 return <group position={[0,0,.022]}>
  <mesh ref={fromMesh} scale={scale}><planeGeometry args={dimensions}/><meshBasicMaterial ref={front} map={textures[fixed||'home']} toneMapped={false}/></mesh>
  <mesh ref={toMesh} scale={scale} position={[0,0,.001]} renderOrder={1}><planeGeometry args={dimensions}/><meshBasicMaterial ref={next} map={textures[fixed||'home']} toneMapped={false} transparent opacity={0} depthWrite={false}/></mesh>
 </group>;
}
