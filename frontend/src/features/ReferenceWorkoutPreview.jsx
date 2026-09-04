import {Bell,Check,ChevronRight} from "lucide-react";
import "./exercise-artwork.css";
import WorkoutVariationsButton from "./WorkoutVariationsButton";
import ExercisePhoto from "./ExercisePhoto";

const getExercise=(db,id)=>Array.isArray(db?.exercises)?(db.exercises.find(e=>e.id===id||e.exercise_id===id)||{}):{};
const toRpe=rir=>{const m=String(rir??"").match(/\d+/);return Math.max(5,Math.min(10,10-Number(m?.[0]||2)))};
const asArray=value=>Array.isArray(value)?value:(value==null||value===""?[]:[value]);
export default function ReferenceWorkoutPreview({db={},activeSession,items=[],onStart,onLibrary}){
  const safeItems=Array.isArray(items)?items:[];
  const raw=activeSession?.label||db?.program?.session||"Treino de hoje";
  const name=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const duration=activeSession?.duration||db?.program?.duration||"60 min";
  const rawFocus=activeSession?.focus??db?.program?.focus??[];
  const focus=asArray(rawFocus).slice(0,3);
  return <div className="reference-workout-v3" data-testid="reference-workout-preview">
    <header className="ref3-workout-head"><strong>FORGE</strong><button type="button" aria-label="Abrir biblioteca de treinos" onClick={onLibrary}><Bell size={22}/></button></header>
    <section className="ref3-workout-hero"><span>TREINO DE HOJE</span><div className="ref3-workout-title"><h1>{name}</h1><strong>{duration}</strong></div><div className="ref3-workout-chips">{(focus.length?focus:["Peitoral","Ombros","Tríceps"]).map(x=><i key={String(x)}>{String(x)}</i>)}</div><hr/><div className="ref3-warmup"><div><span>AQUECIMENTO</span><strong>Mobilidade + ativação</strong></div><b>8 min</b></div></section>
    <section className="ref3-exercises"><h2>EXERCÍCIOS</h2><div>{safeItems.map((x,i)=>{const item=x||{},ex=getExercise(db,item.exercise_id),exName=ex.name||item.name||item.exercise_id||`Exercício ${i+1}`,equipment=asArray(ex.equipment??item.equipment),artExercise={...item,...ex,equipment,name:exName,id:ex.id||item.exercise_id};return <article key={`${item.exercise_id||exName}-${i}`}><ExercisePhoto exercise={artExercise}/><div className="ref3-ex-copy"><strong>{exName}</strong><span>{item.sets??"-"} séries x {item.reps??"-"}</span></div><em>RPE {toRpe(item.rir)}</em><i className="ref3-check"><Check size={19}/></i></article>})}</div></section>
    <button type="button" className="ref3-start" data-testid="workout-preview-start" onClick={onStart}>INICIAR TREINO <ChevronRight size={20}/></button>
    <WorkoutVariationsButton onOpen={onLibrary}/>
  </div>;
}
