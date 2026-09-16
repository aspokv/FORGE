import {Component,Suspense,lazy,useEffect,useRef,useState} from 'react';
import {RotateCcw,MoveHorizontal} from 'lucide-react';
import {PRODUCT} from '../config';
import {SCREEN_CAPTURES,SCREEN_SEQUENCE} from '../scene/screenSequence';
import Fallback from './Fallback';
const Scene=lazy(()=>import('../scene/ProductScene'));
class SceneBoundary extends Component{state={failed:false};static getDerivedStateFromError(){return{failed:true}}componentDidCatch(){this.props.onFailure?.()}render(){return this.state.failed?this.props.fallback:this.props.children}}
export default function ProductStage({progress,chapter,reduced,onHotspot}){
 const [mobile,setMobile]=useState(()=>innerWidth<760);const [supported,setSupported]=useState(true);const [finish,setFinish]=useState(0);const [autoRotate,setAutoRotate]=useState(false);const [visible,setVisible]=useState(true);const stage=useRef();const rotation=useRef({x:0,y:0});const drag=useRef(null);
 useEffect(()=>{const mq=matchMedia('(max-width:759px)');const change=()=>setMobile(mq.matches);mq.addEventListener('change',change);try{const c=document.createElement('canvas');const gl=c.getContext('webgl2')||c.getContext('webgl');setSupported(!!gl);gl?.getExtension('WEBGL_lose_context')?.loseContext()}catch{setSupported(false)}return()=>mq.removeEventListener('change',change)},[]);
 useEffect(()=>{const io=new IntersectionObserver(([entry])=>setVisible(entry.isIntersecting),{rootMargin:'100px'});if(stage.current)io.observe(stage.current);return()=>io.disconnect()},[]);
 function pointerDown(e){if(e.target.closest('button'))return;drag.current={x:e.clientX,y:e.clientY};e.currentTarget.setPointerCapture?.(e.pointerId);setAutoRotate(false)}
 function pointerMove(e){if(!drag.current)return;const dx=e.clientX-drag.current.x;const dy=e.clientY-drag.current.y;rotation.current.x+=dx*.007;rotation.current.y=Math.max(-.5,Math.min(.5,rotation.current.y+dy*.003));drag.current={x:e.clientX,y:e.clientY}}
 const fallback=<Fallback progress={progress} chapter={chapter} reduced={reduced} rotation={rotation} active={visible} finishColor={PRODUCT.finishes[finish].color}/>;
 return <div className="product-stage" ref={stage}>
  <div className="stage-watermark" aria-hidden="true">FORGE</div><div className="stage-index"><span>FORGE OS</span><span>0{chapter+1} / {String(SCREEN_SEQUENCE.length).padStart(2,'0')}</span></div>
  <div className="canvas-wrap" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
  <SceneBoundary fallback={fallback} onFailure={()=>setSupported(false)}>{supported?<Suspense fallback={fallback}><Scene active={visible} progress={progress} chapter={chapter} finish={finish} rotation={rotation} autoRotate={autoRotate} reduced={reduced} mobile={mobile} onHotspot={onHotspot} onFailure={()=>setSupported(false)}/></Suspense>:fallback}</SceneBoundary>
  </div>
  {supported&&<div className="product-controls"><div className="finish-picker" role="group" aria-label="Acabamento do dispositivo demonstrativo">{PRODUCT.finishes.map((f,i)=><button key={f.name} aria-label={f.name} aria-pressed={finish===i} onClick={()=>setFinish(i)}><i style={{background:f.color}}/></button>)}<span>{PRODUCT.finishes[finish].name}</span></div><button className="rotate-button" aria-pressed={autoRotate} onClick={()=>setAutoRotate(v=>!v)}><RotateCcw size={14}/>360°</button><button className="reset-button" aria-label="Restaurar vista frontal" onClick={()=>{rotation.current={x:0,y:0};setAutoRotate(false)}}>Frente</button></div>}
  <span className="drag-note"><MoveHorizontal size={13}/>{supported?'Arraste para explorar':'Modo leve'}<span>Tela real · {SCREEN_CAPTURES[SCREEN_SEQUENCE[chapter]].label}</span></span>
 </div>
}
