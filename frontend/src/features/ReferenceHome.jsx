import {useContext,useEffect,useMemo,useState} from "react";
import axios from "axios";
import AsyncState from "./AsyncState";
import ForgeDialog from "./ForgeDialog";
import {AstraPage,AstraAction,AstraMeta,AstraIcon,AstraNavigation} from "./AstraUI";
import {useScheduledProgram} from "./workoutCalendar";
import TrainingCardImage from "./TrainingCardImage";
import LembretePesagem from "./LembretePesagem";
import {consumedTotals} from "./foodDiary";
import {useWorkoutCompletion,sessionStatus,completionForToday} from "./workoutCompletionState";
import {sequenciaDeDias,volumeDaSemana,textoDaCarga,textoDeProntidao} from "./ritmoDaSemana";
export {completionForToday,inferredCompletionForToday,sessionStatus} from "./workoutCompletionState";
import "../home-signature.css";

const API=`${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const WEEK=["SEG","TER","QUA","QUI","SEX","SÁB","DOM"];
const dateKeyFor=date=>{if(!(date instanceof Date)||Number.isNaN(date.getTime()))return "";const p=n=>String(n).padStart(2,"0");return `${date.getFullYear()}-${p(date.getMonth()+1)}-${p(date.getDate())}`};
const localDateKey=()=>dateKeyFor(new Date());
const normalize=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
export const isPullPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)pull(\s|$)|dorsal|costas|largura|espessura/.test(key)};
export const isLegPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)legs?(\s|$)|perna|quadriceps|posterior|glute|panturrilha/.test(key)};
export const isPushPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)push(\s|$)|peito|peitoral|triceps|ombro/.test(key)};
export const planArtworkKindFor=(sessionName,focus=[])=>isPullPlan(sessionName,focus)?"pull":isLegPlan(sessionName,focus)?"legs":isPushPlan(sessionName,focus)?"push":"default";
export const planArtworkFor=(sessionName,focus=[])=>{const kind=planArtworkKindFor(sessionName,focus);return kind==="pull"?"/images/anatomy/pull-back.webp":kind==="legs"?"/images/anatomy/legs-quads-front.webp":kind==="push"?"/images/anatomy/push-front.webp":"/images/anatomy/push-front.webp"};
const referenceDateLabel=date=>new Intl.DateTimeFormat("pt-BR",{weekday:"long",day:"2-digit",month:"long"}).format(date).replace("-feira","").toUpperCase();

/*
 * O titulo do card nao pode partir palavra. "A · Quadriceps" saia como "A ·/QUADRI/CEPS"
 * na tela do atleta, porque o tamanho do titulo e fixo e o nome da sessao nao e: ele vem do
 * programa e varia de "Push 1" a "A · Quadriceps". CSS nao sabe contar caractere, entao o
 * degrau de tamanho e decidido aqui, onde o texto existe.
 */
export function classeDoTitulo(titulo){
  const n=String(titulo||"").trim().length;
  if(n>13) return "forge-nome-longo";
  if(n>8) return "forge-nome-medio";
  return undefined;
}

export default function ReferenceHome({db,start,onRecoveryCheckin}){
  const nav=useContext(AstraNavigation);
  const [attempt,setAttempt]=useState(0),[loadState,setLoadState]=useState({nutrition:"loading",water:"loading",recovery:"loading"});
  const [waterMessage,setWaterMessage]=useState(null),[checkinError,setCheckinError]=useState("");
  const retry=()=>setAttempt(n=>n+1);
  const p=useScheduledProgram(db.program||{}),userId=db.current_user?.id||db.profile?.user_id||db.profile?.id;
  const[nutrition,setNutrition]=useState(null),[mealLog,setMealLog]=useState([]),[hydration,setHydration]=useState(null),[checkin,setCheckin]=useState(null),[foodExtras,setFoodExtras]=useState([]);
  const[waterBusy,setWaterBusy]=useState(false),[checkinOpen,setCheckinOpen]=useState(false),[checkinBusy,setCheckinBusy]=useState(false);
  const[checkinForm,setCheckinForm]=useState({sleep:4,energy:4,motivation:4,soreness:2,stress:2});
  const {completion}=useWorkoutCompletion({userId,program:p,recentSets:db.recent_sets,API});
  useEffect(()=>{
    let alive=true;const day=localDateKey();
    setLoadState({nutrition:"loading",water:"loading",recovery:"loading"});
    Promise.allSettled([axios.get(`${API}/nutrition/plan`),axios.get(`${API}/nutrition/adherence/${day}`),axios.get(`${API}/hydration/${day}`),axios.get(`${API}/recovery/${day}`)]).then(([n,a,h,r])=>{
      if(!alive)return;
      const noPlan=n.status==="rejected"&&n.reason?.response?.status===404;
      if(n.status==="fulfilled")setNutrition(n.value.data);else if(noPlan)setNutrition(null);
      if(a.status==="fulfilled"){setMealLog(a.value.data.meals||[]);setFoodExtras(a.value.data.extras||[])}
      if(h.status==="fulfilled")setHydration(h.value.data);
      if(r.status==="fulfilled")setCheckin(r.value.data?.checkin||null);
      setLoadState({nutrition:noPlan?"empty":n.status==="fulfilled"&&a.status==="fulfilled"?"ready":"error",water:h.status==="fulfilled"?"ready":"error",recovery:r.status==="fulfilled"?"ready":"error"});
    });return()=>{alive=false};
  },[userId,attempt]);

  const sessions=p.sessions||[],activeIndex=Math.max(0,sessions.findIndex(s=>s.day===p.active_day));
  const active=p.rest_day?(p.calendar?.next||{}):(sessions[activeIndex]||sessions[0]||{});
  const now=new Date(),todayCompletion=completionForToday(completion,now),restDay=p.rest_day&&!todayCompletion;
  const completedSession=todayCompletion?.completed_session||null;
  const shown=todayCompletion?(completedSession||{label:todayCompletion.label}):active,items=shown.exercises||(todayCompletion?[]:p.exercises)||[];
  const plannedFromSession=items.reduce((s,x)=>s+Number(x.sets||0),0),plannedSets=todayCompletion?(todayCompletion.summary?.completed_sets??todayCompletion.summary?.total_sets??"—"):plannedFromSession;
  const completedSeconds=Number(todayCompletion?.summary?.duration_seconds||0),duration=completedSeconds?`${Math.max(1,Math.round(completedSeconds/60))} min`:todayCompletion?"Duração não registrada":shown.duration||p.duration||`${Math.max(35,Math.round(plannedSets*3.4))} min`;
  const raw=todayCompletion?.label||shown.label||p.session||"Treino de hoje";
  const sessionName=String(raw).replace(/^(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\s*[·—–-]\s*/i,"").trim()||raw;
  const focus=(shown.focus||(todayCompletion?[]:p.focus)||[]).slice(0,3);
  const dateLabel=referenceDateLabel(now),dayIndex=(now.getDay()+6)%7;
  const consumed=useMemo(()=>consumedTotals(nutrition?.meals,mealLog,foodExtras),[nutrition,mealLog,foodExtras]);
  // A meta vem de `targets`, o campo que o questionario mantem atualizado; `daily_totals`
  // (o que o plano de fato entrega) so responde quando nao existe meta gravada. E a mesma
  // leitura de App.js, para a Home e a tela de Nutricao nunca mostrarem numeros diferentes.
  const calorieGoal=Number(nutrition?.targets?.goal_calories||nutrition?.daily_totals?.kcal||0);
  const kcal=Number(consumed.kcal||0),water=Number(hydration?.total_ml||0),waterGoal=Number(hydration?.goal_ml||2500);
  const nutritionProgress=calorieGoal>0?Math.min(100,Math.max(0,kcal/calorieGoal*100)):0;
  const waterProgress=waterGoal>0?Math.min(100,Math.max(0,water/waterGoal*100)):0;

  const addWater=async amount=>{if(waterBusy)return;setWaterBusy(true);setWaterMessage(null);try{const r=await axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount});setHydration(r.data);setWaterMessage({kind:"success",text:"Hidratação atualizada."})}catch{setWaterMessage({kind:"error",text:"Não foi possível confirmar a atualização. Atualize o total antes de registrar novamente."})}finally{setWaterBusy(false)}};
  const undoWater=async()=>{if(waterBusy)return;setWaterBusy(true);setWaterMessage(null);try{const r=await axios.delete(`${API}/hydration/${localDateKey()}/last`);setHydration(r.data);setWaterMessage({kind:"success",text:"Hidratação atualizada."})}catch{setWaterMessage({kind:"error",text:"Não foi possível confirmar a atualização. Atualize o total antes de registrar novamente."})}finally{setWaterBusy(false)}};
  const submitCheckin=async()=>{if(checkinBusy)return;setCheckinBusy(true);setCheckinError("");try{const r=await axios.post(`${API}/recovery`,{profile_id:db.profile?.id,local_date:localDateKey(),...checkinForm});setCheckin(r.data?.checkin||r.data);onRecoveryCheckin?.(r.data);setCheckinOpen(false)}catch{setCheckinError("Não foi possível salvar seu check-in. Suas respostas continuam aqui; tente novamente.")}finally{setCheckinBusy(false)}};
  const openPlan=()=>{if(p.program_selection_required){start();return;}if(todayCompletion||restDay){start();return;}checkin?start():setCheckinOpen(true)};
  const completedTime=todayCompletion&&!todayCompletion.inferred?new Intl.DateTimeFormat("pt-BR",{hour:"2-digit",minute:"2-digit"}).format(new Date(todayCompletion.completed_at)):"";
  const introTitle=p.program_selection_required&&!todayCompletion?"Escolha seu programa.":todayCompletion?"Treino concluído.":restDay?"Hoje é recuperação.":"Seu treino está pronto.";
  const cycleLabel=String(p.week||"Ciclo atual").split("·")[0].trim();
  const tituloDoCard=p.program_selection_required&&!todayCompletion?"Escolha seu programa":sessionName;
  // No descanso os minutos e as series do card sao da PROXIMA sessao, nao de hoje. Dizer
  // "DESCANSO HOJE · AMANHÃ" resolve a contradicao de anunciar descanso com 63 min ao lado.
  const cardContext=p.program_selection_required&&!todayCompletion?"SEU PROGRAMA":todayCompletion?`${cycleLabel} · CONCLUÍDO`:restDay?"DESCANSO HOJE · PRÓXIMA SESSÃO":`${cycleLabel} · PRÓXIMA SESSÃO`;

  const monday=new Date(now);monday.setDate(now.getDate()-dayIndex);
  const trained=new Set((db.recent_sets||[]).map(row=>{const d=new Date(row.created_at);return Number.isNaN(d.getTime())?"":new Intl.DateTimeFormat("sv-SE").format(d)}));
  const sequencia=useMemo(()=>sequenciaDeDias(db.recent_sets,now),[db.recent_sets]);// eslint-disable-line react-hooks/exhaustive-deps
  const volume=useMemo(()=>volumeDaSemana(db.recent_sets,monday),[db.recent_sets]);// eslint-disable-line react-hooks/exhaustive-deps
  // O nivel vem do motor (`program.logic.recovery_level`), que media os tres ultimos
  // check-ins. Recalcular aqui, com o de hoje so, daria um rotulo diferente do treino real.
  const prontidao=textoDeProntidao(p.logic?.recovery_level);
  return <AstraPage screen={0} testId="reference-home-v3">
    <section className="forge-home-context" aria-labelledby="forge-home-title">
      <div className="a6-eyebrow">{dateLabel}{sequencia>1&&<em className="forge-sequencia" data-testid="home-sequencia">{sequencia} dias seguidos</em>}</div>
      <h1 id="forge-home-title" className="forge-home-sr-only">{introTitle}</h1>
    </section>
    {/* A pesagem de sexta: e o dado que a periodizacao e o Conselho usam para decidir a semana. */}
    <LembretePesagem API={API}/>
    <section className={`a6-signature${todayCompletion?" a6-signature-completed":""}`} aria-labelledby="home-session-title">
    <div className="a6-hero" data-testid="home-top-hero"><TrainingCardImage session={{...shown,label:raw}} program={todayCompletion?{}:p} profile={db.profile} focus={focus} loading="eager" fetchPriority="high" width="640" height="276"/></div>
    <div className="a6-panel a6-workout-card" data-testid="daily-briefing">
      <div className="a6-eyebrow" data-testid="home-cycle-context">{cardContext}</div>
      <h2 id="home-session-title" className={classeDoTitulo(tituloDoCard)}>{tituloDoCard}</h2><p>{focus.length?focus.join(" · "):todayCompletion?"Sessão registrada":"Treino completo"}</p>
      {(!p.program_selection_required||todayCompletion)&&<AstraMeta duration={duration} sets={plannedSets}/>}
    </div>
    <div className="a6-signature-footer">
      {(todayCompletion||restDay)&&<div className={`a6-signature-status${todayCompletion?" a6-completed":""}`} role="status"><span aria-hidden="true"/>{restDay?"Descanso programado":sessionStatus(checkin,db.recent_sets,now,todayCompletion)}</div>}
      {todayCompletion&&<div className="a6-completed-meta" data-testid="home-completed-at">{completedTime?`Concluído hoje às ${completedTime}`:"Concluído hoje"}</div>}
      <AstraAction testId="start-workout-button" onClick={openPlan}>{p.program_selection_required?"Escolher programa feminino":todayCompletion?"Ver resumo do treino":restDay?"Consultar próximo treino":"Ver treino de hoje"}</AstraAction>
    </div>
    </section>
    <section className="a6-mini-grid" data-testid="home-acoes-rapidas">
      <article className="a6-panel forge-progress-card" data-testid="home-nutrition-progress">
        {loadState.nutrition==="loading"?<AsyncState title="Carregando alimentação…"/>:loadState.nutrition==="error"?<AsyncState kind="error" title="Alimentação indisponível" onRetry={retry}/>:<button type="button" className="a6-mini forge-tile-action" onClick={nav.nutrition} aria-label="Abrir Nutrição"><AstraIcon name="nutrition"/><div className="forge-progress-copy"><p>Nutrição</p><strong>{nutrition?`${Math.round(kcal).toLocaleString("pt-BR")} kcal`:"Sem plano"}{nutrition&&calorieGoal>0&&<span> de {Math.round(calorieGoal).toLocaleString("pt-BR")} kcal</span>}</strong><div className="forge-progress-track" role="progressbar" aria-label="Progresso de nutrição" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(nutritionProgress)}><span style={{width:`${nutritionProgress}%`}}/></div></div></button>}</article>
      {loadState.water!=="ready"?<div className="a6-panel"><AsyncState kind={loadState.water==="error"?"error":"loading"} title={loadState.water==="error"?"Hidratação indisponível":"Carregando água…"} onRetry={loadState.water==="error"?retry:undefined}/></div>:<details className="a6-panel a6-mini-water forge-progress-card" data-testid="home-hydration"><summary className="a6-mini a6-water"><AstraIcon name="water"/><div className="forge-progress-copy"><p>Água</p><strong>{(water/1000).toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:2})} L <span>de {(waterGoal/1000).toLocaleString("pt-BR",{minimumFractionDigits:1,maximumFractionDigits:1})} L</span></strong><div className="forge-progress-track forge-progress-track-water" role="progressbar" aria-label="Progresso de hidratação" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(waterProgress)}><span style={{width:`${waterProgress}%`}}/></div></div></summary><div className="a6-water-controls"><button type="button" data-testid="hydration-add-250" disabled={waterBusy||waterMessage?.kind==="error"} onClick={()=>addWater(250)}>+250 ml</button><button type="button" data-testid="hydration-add-500" disabled={waterBusy||waterMessage?.kind==="error"} onClick={()=>addWater(500)}>+500 ml</button><button type="button" data-testid="hydration-undo" aria-label="Desfazer água" disabled={waterBusy||water===0||waterMessage?.kind==="error"} onClick={undoWater}>Desfazer</button></div>{waterMessage&&<AsyncState kind={waterMessage.kind} title={waterMessage.text} onRetry={waterMessage.kind==="error"?()=>{setWaterMessage(null);retry()}:undefined}/>}</details>}
    </section>
    <section data-testid="home-training-week">
      <div className="a6-section-title"><h2>Seu ritmo</h2><small>{cycleLabel}</small></div>
      <div className="a6-week">{WEEK.map((label,i)=>{const d=new Date(monday);d.setDate(monday.getDate()+i);const done=trained.has(new Intl.DateTimeFormat("sv-SE").format(d));return <div key={`${label}-${i}`} className={`a6-day ${done?"a6-done":""} ${i===dayIndex?"a6-selected":""}`}><span>{label.charAt(0)}</span><strong aria-label={`${d.toLocaleDateString("pt-BR")}${done?", treino registrado":""}`}><b>{d.getDate()}</b>{done&&<AstraIcon name="check"/>}</strong></div>})}</div>
    </section>
    <section className="forge-estado-grid" data-testid="home-estado-do-dia">
      {loadState.recovery!=="ready"?<AsyncState kind={loadState.recovery==="error"?"error":"loading"} title={loadState.recovery==="error"?"Check-in indisponível":"Carregando check-in…"} onRetry={loadState.recovery==="error"?retry:undefined}/>:checkin
        ?<article className={`a6-panel forge-estado forge-prontidao forge-prontidao-${prontidao.tom}`} data-testid="home-prontidao">
          <span className="a6-eyebrow">Prontidão</span>
          <strong>{prontidao.rotulo}</strong>
          <p>{prontidao.efeito}</p>
        </article>
        /* Sem check-in o cartao inteiro e o botao: um alvo de toque grande custa menos
           altura que um cartao com um botao dentro, e a altura e o que falta aqui. */
        :<button type="button" className="a6-panel forge-estado forge-prontidao forge-estado-acao" data-testid="home-prontidao" onClick={()=>setCheckinOpen(true)}>
          <span className="a6-eyebrow">Prontidão</span>
          <strong>Fazer check-in</strong>
          <p>Conte como você está hoje.</p>
        </button>}
      <article className="a6-panel forge-estado forge-semana-resumo" data-testid="home-volume-semana">
        <span className="a6-eyebrow">Esta semana</span>
        <strong>{volume.series} {volume.series===1?"série":"séries"}</strong>
        <p>{volume.kg>0?`${textoDaCarga(volume.kg)} levantados`:"Nenhuma carga registrada"}</p>
      </article>
    </section>
    <ForgeDialog open={checkinOpen} onOpenChange={setCheckinOpen} busy={checkinBusy} testId="today-checkin-modal" title="Como você está hoje?" description="Registre sua percepção para orientar os ajustes do treino.">
      <div className="forge-checkin-grid">{[["Sono","sleep","Ruim","Ótimo"],["Energia","energy","Baixa","Alta"],["Motivação","motivation","Baixa","Alta"],["Dor muscular","soreness","Nenhuma","Intensa"],["Estresse","stress","Baixo","Alto"]].map(([label,key,low,high])=><label key={key}><span>{label}<b>{checkinForm[key]} de 5</b></span><input type="range" min="1" max="5" value={checkinForm[key]} aria-valuetext={`${checkinForm[key]} de 5; 1: ${low}, 5: ${high}`} onChange={e=>setCheckinForm(f=>({...f,[key]:Number(e.target.value)}))}/><small>{low}<span>{high}</span></small></label>)}</div>
      {checkinError&&<AsyncState kind="error" title={checkinError}/>}
      <button className="fg-btn fg-btn-cheio" data-testid="save-today-checkin" disabled={checkinBusy} aria-busy={checkinBusy} onClick={submitCheckin}>{checkinBusy?"Salvando…":"Salvar check-in"}</button>
      {!(restDay||todayCompletion)&&<button className="fg-btn fg-btn-2" disabled={checkinBusy} onClick={()=>{setCheckinOpen(false);start()}}>Ver treino sem check-in</button>}
    </ForgeDialog>
  </AstraPage>;
}
