import {BookOpen,ChevronRight,Clock} from "lucide-react";
import "./exercise-artwork.css";
import WorkoutVariationsButton from "./WorkoutVariationsButton";
import ExercisePhoto from "./ExercisePhoto";
import {planArtworkFor} from "./ReferenceHome";

const getExercise=(db,id)=>Array.isArray(db?.exercises)?(db.exercises.find(e=>e.id===id||e.exercise_id===id)||{}):{};
const asArray=value=>Array.isArray(value)?value:(value==null||value===""?[]:[value]);
export default function ReferenceWorkoutPreview({db={},activeSession,items=[],onStart,onLibrary}){
  const safeItems=Array.isArray(items)?items:[];
  const raw=activeSession?.label||db?.program?.session||"Treino de hoje";
  const name=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const duration=activeSession?.duration||db?.program?.duration||"60 min";
  const rawFocus=activeSession?.focus??db?.program?.focus??[];
  const focus=asArray(rawFocus).slice(0,3);
  const totalSets=safeItems.reduce((sum,x)=>sum+Number(x?.sets||0),0);
  const anatomy=planArtworkFor(name,focus);
  return <div className="reference-workout-v3 astra-training" data-testid="reference-workout-preview">
    <header className="ref3-workout-head"><span className="astra-wordmark" aria-label="FORGE"/><button type="button" aria-label="Abrir biblioteca de treinos" onClick={onLibrary}><BookOpen size={21}/></button></header>
    <section className="astra-training-intro"><p className="eyebrow">SEU PROGRAMA</p><h1>Treino.</h1><p>Um passo mais forte, a cada sessão.</p></section>
    <div className="astra-tabs"><button className="active">Sessão atual</button><button onClick={onLibrary}>Biblioteca</button></div>
    <section className="astra-training-summary">
      <div><p className="eyebrow">{String(activeSession?.label||"SESSÃO ATUAL").toUpperCase()}</p><h2>{name}</h2><p>{focus.length?focus.join(" e "):"Treino completo"}</p><div className="astra-meta"><span><Clock size={14}/>{duration}</span><span>{totalSets} séries</span></div></div>
      <img src={anatomy} alt="" loading="eager"/>
    </section>
    <button className="astra-warmup" type="button"><span className="astra-warmup-icon">✣</span><span><b>Aquecimento</b><small>Mobilidade e ativação</small></span><em>8 min</em><ChevronRight size={17}/></button>
    <div className="astra-section-head"><h2>Exercícios</h2><small>{safeItems.length} no total · prévia</small></div>
    <section className="astra-exercise-list">{safeItems.map((x,i)=>{const item=x||{},ex=getExercise(db,item.exercise_id),exName=ex.name||item.name||item.exercise_id||`Exercício ${i+1}`,equipment=asArray(ex.equipment??item.equipment),artExercise={...item,...ex,equipment,name:exName,id:ex.id||item.exercise_id};return <article key={`${item.exercise_id||exName}-${i}`}><ExercisePhoto exercise={artExercise}/><div><b>{exName}</b><small>{item.sets??"-"} × {item.reps??"-"} · RIR {String(item.rir??2).replace(/[^0-9–-]/g,"")||2}</small></div><span>{String(i+1).padStart(2,"0")}</span></article>})}</section>
    <button type="button" className="astra-primary astra-training-cta" data-testid="workout-preview-start" onClick={onStart}>Iniciar sessão <ChevronRight size={19}/></button>
    <WorkoutVariationsButton onOpen={onLibrary}/>
  </div>;
}
