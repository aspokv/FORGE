import {Bell,Check,ChevronRight,Dumbbell} from "lucide-react";
import "./exercise-artwork.css";

const getExercise=(db,id)=>db.exercises?.find(e=>e.id===id||e.exercise_id===id)||{};
const toRpe=rir=>{const m=String(rir??"").match(/\d+/);return Math.max(5,Math.min(10,10-Number(m?.[0]||2)))};
const normalize=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const ART_RULES=[
  {slot:0,terms:["remada apoiada no peito","remada com peito apoiado","remada peito apoiado","chest supported row","chest supported","row chest supported"]},
  {slot:1,terms:["puxada unilateral na polia","puxada unilateral","pulldown unilateral","single arm pulldown","single arm lat pulldown","one arm pulldown"]},
  {slot:2,terms:["remada curvada com barra","remada curvada barra","barbell row","bent over row"]},
  {slot:3,terms:["pullover com halter","pullover halter","dumbbell pullover"]},
  {slot:4,terms:["crucifixo inverso com halteres","crucifixo inverso halteres","reverse dumbbell fly","reverse fly dumbbell","rear delt fly"]},
  {slot:5,terms:["rosca direta com barra","rosca barra","barbell curl"]},
];
export const artworkSlotFor=(...values)=>{const key=normalize(values.join(" "));const rule=ART_RULES.find(item=>item.terms.some(term=>key.includes(normalize(term))));return rule?.slot??-1};
const ExerciseArtwork=({slot,label})=>{const style=slot>=0?{"--art-y":`${slot*-82}px`,"--art-y-small":`${slot*-72}px`,backgroundImage:"url(/images/reference/workout-exercises-sprite.webp)"}:undefined;return <div className={`ref3-ex-art${slot<0?" fallback":""}`}style={style}role="img"aria-label={label}>{slot<0&&<Dumbbell size={27}/>}</div>};

export default function ReferenceWorkoutPreview({db,activeSession,items,onStart,onLibrary}){
  const raw=activeSession?.label||db.program?.session||"Treino de hoje";
  const name=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const duration=activeSession?.duration||db.program?.duration||"60 min";
  const focus=(activeSession?.focus||db.program?.focus||[]).slice(0,3);
  return <div className="reference-workout-v3" data-testid="reference-workout-preview">
    <header className="ref3-workout-head"><strong>FORGE</strong><button type="button" aria-label="Abrir biblioteca de treinos" onClick={onLibrary}><Bell size={22}/></button></header>
    <section className="ref3-workout-hero"><span>TREINO DE HOJE</span><div className="ref3-workout-title"><h1>{name}</h1><strong>{duration}</strong></div><div className="ref3-workout-chips">{(focus.length?focus:["Peitoral","Ombros","Tríceps"]).map(x=><i key={x}>{x}</i>)}</div><hr/><div className="ref3-warmup"><div><span>AQUECIMENTO</span><strong>Mobilidade + ativação</strong></div><b>8 min</b></div></section>
    <section className="ref3-exercises"><h2>EXERCÍCIOS</h2><div>{items.map((x,i)=>{const ex=getExercise(db,x.exercise_id),exName=ex.name||x.name||x.exercise_id,slot=artworkSlotFor(exName,x.exercise_id);return <article key={`${x.exercise_id}-${i}`}><ExerciseArtwork slot={slot} label={`Ilustração de ${exName}`}/><div className="ref3-ex-copy"><strong>{exName}</strong><span>{x.sets} séries x {x.reps}</span></div><em>RPE {toRpe(x.rir)}</em><i className="ref3-check"><Check size={19}/></i></article>})}</div></section>
    <button type="button" className="ref3-start" data-testid="workout-preview-start" onClick={onStart}>INICIAR TREINO <ChevronRight size={20}/></button>
  </div>;
}
