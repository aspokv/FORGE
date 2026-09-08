import {useState} from "react";
import ExercisePhoto from "./ExercisePhoto";
import {planArtworkFor} from "./ReferenceHome";
import {AstraPage,AstraIntro,AstraMeta,AstraAction,AstraIcon} from "./AstraUI";

const asArray=value=>Array.isArray(value)?value:(value==null||value===""?[]:[value]);
export default function ReferenceWorkoutPreview({db={},activeSession,items=[],onStart,onLibrary}){
  const [warmupOpen,setWarmupOpen]=useState(false);
  const safeItems=Array.isArray(items)?items:[];
  const raw=activeSession?.label||db.program?.session||"Treino de hoje";
  const name=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const focus=asArray(activeSession?.focus??db.program?.focus).slice(0,3);
  const duration=activeSession?.duration||db.program?.duration||"Duração não informada";
  const totalSets=safeItems.reduce((sum,x)=>sum+Number(x?.sets||0),0);
  return <AstraPage screen={1} testId="reference-workout-preview" onLibrary={onLibrary}>
    <AstraIntro eyebrow="SEU PROGRAMA" title="Treino." subtitle="Um passo mais forte, a cada sessão."/>
    <div className="a6-tabs" role="group" aria-label="Visualização do treino"><button type="button" className="a6-selected" aria-pressed="true">Sessão atual</button><button type="button" aria-pressed="false" onClick={onLibrary}>Biblioteca</button></div>
    <section className="a6-panel a6-training-summary">
      <div className="a6-summary-copy"><div className="a6-eyebrow">{String(raw).split(/[—–]/)[0]}{db.program?.week?` · ${db.program.week}`:""}</div><h2>{name}</h2><p>{focus.join(" e ")||"Treino completo"}</p><AstraMeta duration={duration} sets={totalSets}/></div>
      <img className="a6-anatomy" src={planArtworkFor(name,focus)} alt={`Mapa dos músculos da sessão: ${focus.join(", ")}`}/>
    </section>
    <button className="a6-warmup" type="button" aria-expanded={warmupOpen} onClick={()=>setWarmupOpen(x=>!x)}><span className="a6-iconbox"><AstraIcon name="training"/></span><span><b>Aquecimento</b><p>Mobilidade e ativação</p></span><small>8 min</small><AstraIcon name="chevron"/></button>
    {warmupOpen&&<p className="a6-warmup-detail">Mobilidade + ativação antes da sessão. Respeite a amplitude confortável e a orientação do seu profissional.</p>}
    <div className="a6-section-title"><h2>Exercícios</h2><small>{safeItems.length} no total · prévia</small></div>
    <section className="a6-exercises">{safeItems.map((item,i)=>{
      const x=item||{},ex=asArray(db.exercises).find(e=>e.id===x.exercise_id||e.exercise_id===x.exercise_id)||{};
      const exName=ex.name||x.name||x.exercise_id||`Exercício ${i+1}`;
      return <article className="a6-exercise" key={`${x.exercise_id||exName}-${i}`}><ExercisePhoto exercise={{...x,...ex,name:exName,id:ex.id||x.exercise_id,equipment:asArray(ex.equipment??x.equipment)}}/><div className="a6-exercise-text"><h3>{exName}</h3><p>{x.sets??"—"} × {x.reps??"—"} · RIR {x.rir??"—"}</p></div><span className="a6-number">{String(i+1).padStart(2,"0")}</span></article>;
    })}</section>
    <div className="a6-training-cta"><AstraAction testId="workout-preview-start" onClick={onStart}>Iniciar sessão</AstraAction></div>
  </AstraPage>;
}
