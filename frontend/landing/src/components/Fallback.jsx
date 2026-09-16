import {useEffect,useRef} from 'react';
import {SCREEN_CAPTURES,SCREEN_SEQUENCE,screenBlend} from '../scene/screenSequence';
export default function Fallback({progress,chapter=0,reduced=false,rotation,active=true,finishColor='#444'}){
 const shell=useRef();const images=useRef({});
 useEffect(()=>{
  let raf;let angle=-17;
  const draw=()=>{
   const p=progress?.current||0;const blend=screenBlend(p);
   for(const [id,img] of Object.entries(images.current))if(img){img.style.opacity=id===blend.to&&blend.from!==blend.to?blend.mix:id===blend.from?1:0;img.style.zIndex=id===blend.to?2:1;}
   const target=-17+Math.sin(p*Math.PI*2)*20+(rotation?.current.x||0)*57.3+blend.turn*57.3;
   angle=reduced?target:angle+(target-angle)*.12;
   if(shell.current)shell.current.style.transform=`perspective(1100px) rotateY(${angle}deg) rotateX(${(rotation?.current.y||0)*57.3}deg) rotateZ(-4deg)`;
   if(active)raf=requestAnimationFrame(draw);
  };
  draw();return()=>cancelAnimationFrame(raf);
 },[progress,reduced,rotation,active]);
 const selected=SCREEN_SEQUENCE[chapter];
 return <div className="capture-device" ref={shell} style={{borderColor:finishColor}} role="img" aria-label={`Tela real do Forge: ${SCREEN_CAPTURES[selected].label}`}>
  {Object.entries(SCREEN_CAPTURES).map(([id,screen])=><img ref={el=>images.current[id]=el} key={id} src={screen.src} width={screen.width} height={screen.height} alt="" aria-hidden="true" draggable="false" decoding="async" style={{opacity:id===selected?1:0}}/>)}
 </div>;
}
