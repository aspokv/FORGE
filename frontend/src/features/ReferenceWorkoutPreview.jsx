import {Bell,BookOpen,Check,ChevronRight} from "lucide-react";

const APPROVED_THUMBS=[1,2,3,4,5].map(i=>`/images/reference/exercise-${i}.jpg`);
const thumb=i=>APPROVED_THUMBS[Math.min(i,APPROVED_THUMBS.length-1)];
const getExercise=(db,id)=>db.exercises?.find(e=>e.id===id||e.exercise_id===id)||{};
const toRpe=rir=>{const m=String(rir??"").match(/\d+/);return Math.max(5,Math.min(10,10-Number(m?.[0]||2)))};

export default function ReferenceWorkoutPreview({db,activeSession,items,onStart,onLibrary}){
  const raw=activeSession?.label||db.program?.session||"Treino de hoje";
  const name=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const duration=activeSession?.duration||db.program?.duration||"60 min";
  const focus=(activeSession?.focus||db.program?.focus||[]).slice(0,3);
  return <div className="reference-workout-v3" data-testid="reference-workout-preview">
    <header className="ref3-workout-head"><strong>FORGE</strong><div><button type="button" aria-label="Biblioteca de treinos" onClick={onLibrary}><BookOpen size={20}/></button><span><Bell size={22}/></span></div></header>
    <section className="ref3-workout-hero"><span>TREINO DE HOJE</span><div className="ref3-workout-title"><h1>{name}</h1><strong>{duration}</strong></div><div className="ref3-workout-chips">{(focus.length?focus:["Peitoral","Ombros","Tríceps"]).map(x=><i key={x}>{x}</i>)}</div><hr/><div className="ref3-warmup"><div><span>AQUECIMENTO</span><strong>Mobilidade + ativação</strong></div><b>8 min</b></div></section>
    <section className="ref3-exercises"><h2>EXERCÍCIOS</h2><div>{items.map((x,i)=>{const ex=getExercise(db,x.exercise_id),exName=ex.name||x.name||x.exercise_id;return <article key={`${x.exercise_id}-${i}`}><img src={thumb(i)} alt=""/><div className="ref3-ex-copy"><strong>{exName}</strong><span>{x.sets} séries x {x.reps}</span></div><em>RPE {toRpe(x.rir)}</em><i className="ref3-check"><Check size={19}/></i></article>})}</div></section>
    <button type="button" className="ref3-start" data-testid="workout-preview-start" onClick={onStart}>INICIAR TREINO <ChevronRight size={20}/></button>
  </div>;
}
