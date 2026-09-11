import {AstraPage,AstraIntro,AstraMeta} from "./AstraUI";
import {useScheduledProgram} from "./workoutCalendar";
import TrainingCardImage from "./TrainingCardImage";
import "./completed-workout.css";
export default function CompletedWorkout({db,completion,onLibrary}){
 const program=useScheduledProgram(db.program||{},true),sessions=program.sessions||[];
 const completed=completion.completed_session||null;
 const next=program.calendar?.next||sessions.find(s=>Number(s.day)===Number(program.active_day))||null,summary=completion.summary||{};
 const time=completion.inferred?"":new Intl.DateTimeFormat("pt-BR",{hour:"2-digit",minute:"2-digit"}).format(new Date(completion.completed_at));
 const exercises=db.exercises||[];
 const nameOf=item=>exercises.find(e=>e.id===item.exercise_id)?.name||item.name||item.exercise_id;
 return <AstraPage screen={1} testId="workout-completed-today" onLibrary={onLibrary}>
  <AstraIntro eyebrow="SEU PROGRAMA" title="Treino." subtitle="Sessão registrada. Consulte seu resumo e o que vem depois."/>
  <div className="a6-tabs" role="group" aria-label="Visualização do treino"><button type="button" className="a6-selected" aria-pressed="true">Sessão concluída</button><button type="button" onClick={onLibrary}>Biblioteca</button></div>
  <section className="a6-panel completed-workout-card">
   <p className="a6-eyebrow">CONCLUÍDO HOJE{time?" · "+time:""}</p>
   <h2>{completion.label||completed?.label||"Treino concluído"}</h2>
   <p role="status">Sua sessão foi registrada.</p>
   {summary.completed_sets!=null&&<p>{summary.completed_sets} séries registradas{summary.duration_seconds?" · "+Math.max(1,Math.round(summary.duration_seconds/60))+" min":""}</p>}
   <details className="a6-details"><summary>Ver resumo da sessão</summary>
    {summary.partial_reason&&<p>Conclusão parcial: {summary.partial_reason}</p>}
    {completed?<><p>Exercícios previstos para a sessão:</p><ul>{(completed.exercises||[]).map((x,i)=><li key={i}>{nameOf(x)}</li>)}</ul></>:<p>Os detalhes dos exercícios não foram preservados neste registro antigo.</p>}
   </details>
  </section>
  {next?<section className="a6-panel completed-next-card" data-testid="saved-program-preview">
    <div className="completed-next-heading"><div><p className="a6-eyebrow">PROGRAMA ATUAL</p><p>{program.name||"Programa salvo"}</p><h2>{next.label||"Próxima sessão"}</h2><p>{(next.focus||[]).join(" · ")}</p></div><TrainingCardImage session={next} program={program} profile={db.profile} width="120" height="100"/></div>
    <AstraMeta duration={next.duration||program.duration||"Duração não informada"} sets={(next.exercises||[]).reduce((n,x)=>n+Number(x.sets||0),0)}/>
    <details className="a6-details"><summary>Ver prévia</summary><ul>{(next.exercises||[]).map((x,i)=><li key={i}>{nameOf(x)}<small>{x.sets} séries · {x.reps} repetições</small></li>)}</ul></details>
    <details className="a6-details"><summary>Ver sequência do programa</summary><ol>{sessions.map((s,i)=><li key={`${s.day}-${i}`}>{s.label||`Sessão ${i+1}`}{Number(s.day)===Number(next.day)&&<small>Próxima sessão do programa</small>}</li>)}</ol></details>
    <p>Programa salvo disponível para consulta. A sessão concluída hoje permanece no histórico.</p>
   </section>:<p role="status">Nenhuma sessão ativa disponível no programa atual.</p>}
 </AstraPage>;
}
