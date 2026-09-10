import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {X} from "lucide-react";
import {AstraPage,AstraIntro,AstraAction,AstraMeta,AstraIcon} from "./AstraUI";
import heroArt from "../assets/forge-home-duo-hero";
import {consumedTotals} from "./foodDiary";
import {completionStorageKey} from "./completeWorkout";
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

export function completionForToday(completion,now=new Date()){
  if(!completion?.completed_at)return null;
  const when=new Date(completion.completed_at);
  return dateKeyFor(when)&&dateKeyFor(when)===dateKeyFor(now)?completion:null;
}

export function inferredCompletionForToday(program={},recentSets=[],now=new Date()){
  const sessions=program.sessions||[],activeDay=Number(program.active_day);
  if(!sessions.length||!Number.isFinite(activeDay))return null;
  const today=dateKeyFor(now);
  const rows=(recentSets||[]).filter(row=>{
    if(row?.session_day==null)return false;
    const when=new Date(row.created_at),day=Number(row.session_day);
    return Number.isFinite(day)&&dateKeyFor(when)===today;
  }).sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime());
  if(!rows.length)return null;
  const loggedDay=Number(rows[0].session_day),session=sessions.find(item=>Number(item.day)===loggedDay);
  if(!session)return null;
  const plannedSets=(session.exercises||[]).reduce((sum,item)=>sum+Number(item.sets||0),0);
  const loggedSets=new Set(rows.filter(row=>Number(row.session_day)===loggedDay).map(row=>`${row.exercise_id||""}:${row.set_number??""}`)).size;
  if(loggedDay===activeDay&&(!plannedSets||loggedSets<plannedSets))return null;
  return {day:loggedDay,label:session.label||null,completed_at:rows[0].created_at,inferred:true};
}

export function sessionStatus(checkin,recentSets=[],now=new Date(),completion=null){
  if(completionForToday(completion,now))return "TREINO CONCLUÍDO HOJE";
  if(checkin)return "RECUPERAÇÃO REGISTRADA";
  const cutoff=now.getTime()-7*24*60*60*1000;
  return recentSets.some(row=>{const time=new Date(row.created_at).getTime();return time>=cutoff&&time<=now.getTime()})?"RITMO ATIVO":"PRONTO PARA INICIAR";
}

function storedCompletion(userId,now,program,recentSets){
  if(typeof window!=="undefined"&&userId){
    try{
      const raw=window.localStorage.getItem(completionStorageKey(userId));
      const saved=raw?completionForToday(JSON.parse(raw),now):null;
      if(saved)return saved;
    }catch{/* cache local corrompido nao pode quebrar a Home */}
  }
  return inferredCompletionForToday(program,recentSets,now);
}

export default function ReferenceHome({db,start,onRecoveryCheckin}){
  const p=db.program||{},userId=db.current_user?.id||db.profile?.user_id||db.profile?.id;
  const[nutrition,setNutrition]=useState(null),[mealLog,setMealLog]=useState([]),[hydration,setHydration]=useState(null),[checkin,setCheckin]=useState(null),[foodExtras,setFoodExtras]=useState([]);
  const[waterBusy,setWaterBusy]=useState(false),[checkinOpen,setCheckinOpen]=useState(false),[checkinBusy,setCheckinBusy]=useState(false);
  const[checkinForm,setCheckinForm]=useState({sleep:4,energy:4,motivation:4,soreness:2,stress:2});
  const[completion,setCompletion]=useState(()=>storedCompletion(userId,new Date(),p,db.recent_sets));
  useEffect(()=>{let alive=true;const day=localDateKey();Promise.allSettled([axios.get(`${API}/nutrition/plan`),axios.get(`${API}/nutrition/adherence/${day}`),axios.get(`${API}/hydration/${day}`),axios.get(`${API}/recovery/${day}`)]).then(([n,a,h,r])=>{if(!alive)return;if(n.status==="fulfilled")setNutrition(n.value.data);if(a.status==="fulfilled"){setMealLog(a.value.data.meals||[]);setFoodExtras(a.value.data.extras||[])}if(h.status==="fulfilled")setHydration(h.value.data);if(r.status==="fulfilled")setCheckin(r.value.data?.checkin||null)});return()=>{alive=false}},[]);
  useEffect(()=>{const sync=()=>setCompletion(storedCompletion(userId,new Date(),p,db.recent_sets));sync();if(typeof window!=="undefined")window.addEventListener("forge:workout-complete",sync);return()=>{if(typeof window!=="undefined")window.removeEventListener("forge:workout-complete",sync)}},[userId,p,db.recent_sets]);

  const sessions=p.sessions||[],activeIndex=Math.max(0,sessions.findIndex(s=>s.day===p.active_day));
  const active=sessions[activeIndex]||sessions[0]||{};
  const now=new Date(),todayCompletion=completionForToday(completion,now);
  const completedSession=todayCompletion?sessions.find(s=>Number(s.day)===Number(todayCompletion.day)):null;
  const shown=completedSession||active,items=shown.exercises||p.exercises||[];
  const plannedFromSession=items.reduce((s,x)=>s+Number(x.sets||0),0),plannedSets=Number(todayCompletion?.summary?.total_sets)||plannedFromSession;
  const completedSeconds=Number(todayCompletion?.summary?.duration_seconds||0),duration=completedSeconds?`${Math.max(1,Math.round(completedSeconds/60))} min`:shown.duration||p.duration||`${Math.max(35,Math.round(plannedSets*3.4))} min`;
  const raw=todayCompletion?.label||shown.label||p.session||"Treino de hoje",sessionName=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const focus=(shown.focus||p.focus||[]).slice(0,3);
  const firstName=(db.profile?.name||"").trim().split(" ")[0],displayName=firstName&&firstName.toLowerCase()!=="novo"?firstName:"Atleta";
  const dateLabel=referenceDateLabel(now),dayIndex=(now.getDay()+6)%7;
  const consumed=useMemo(()=>consumedTotals(nutrition?.meals,mealLog,foodExtras),[nutrition,mealLog,foodExtras]);
  const kcal=consumed.kcal,water=Number(hydration?.total_ml||0),waterGoal=Number(hydration?.goal_ml||2500);

  const addWater=async amount=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount});setHydration(r.data)}finally{setWaterBusy(false)}};
  const undoWater=async()=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.delete(`${API}/hydration/${localDateKey()}/last`);setHydration(r.data)}finally{setWaterBusy(false)}};
  const submitCheckin=async()=>{if(checkinBusy)return;setCheckinBusy(true);try{const r=await axios.post(`${API}/recovery`,{profile_id:db.profile?.id,local_date:localDateKey(),...checkinForm});setCheckin(r.data?.checkin||r.data);onRecoveryCheckin?.(r.data);setCheckinOpen(false)}finally{setCheckinBusy(false)}};
  const openPlan=()=>{if(todayCompletion)return;checkin?start():setCheckinOpen(true)};
  const completedTime=todayCompletion&&!todayCompletion.inferred?new Intl.DateTimeFormat("pt-BR",{hour:"2-digit",minute:"2-digit"}).format(new Date(todayCompletion.completed_at)):"";

  const monday=new Date(now);monday.setDate(now.getDate()-dayIndex);
  const trained=new Set((db.recent_sets||[]).map(row=>{const d=new Date(row.created_at);return Number.isNaN(d.getTime())?"":new Intl.DateTimeFormat("sv-SE").format(d)}));
  return <AstraPage screen={0} testId="reference-home-v3">
    <AstraIntro eyebrow={dateLabel} title={`Olá, ${displayName}.`} subtitle={todayCompletion?"Sessão concluída. Recuperação também faz parte do progresso.":"Seu próximo passo está aqui."}/>
    <section className={`a6-signature${todayCompletion?" a6-signature-completed":""}`} aria-labelledby="home-session-title">
    <div className="a6-hero" data-testid="home-top-hero"><img src={heroArt} alt="Homem e mulher atletas em ambiente de treino FORGE" loading="eager" fetchPriority="high" width="640" height="276"/><span className="a6-signature-motto">DISCIPLINA HOJE.<br/>RESULTADOS SEMPRE.</span></div>
    <div className="a6-panel a6-workout-card" data-testid="daily-briefing">
      <div className="a6-eyebrow">{todayCompletion?"SEU TREINO DE HOJE · CONCLUÍDO":"SEU TREINO DE HOJE"}</div>
      <h2 id="home-session-title">{sessionName}</h2><p>{focus.length?focus.join(" · "):"Treino completo"}</p>
      <AstraMeta duration={duration} sets={plannedSets}/>
      <div className={`a6-signature-status${todayCompletion?" a6-completed":""}`} role="status"><span aria-hidden="true"/>{sessionStatus(checkin,db.recent_sets,now,todayCompletion)}</div>
      {todayCompletion&&<div className="a6-completed-meta" data-testid="home-completed-at">{completedTime?`Concluído hoje às ${completedTime}`:"Concluído hoje"}</div>}
      <AstraAction testId="start-workout-button" disabled={Boolean(todayCompletion)} onClick={openPlan}>{todayCompletion?"Sessão concluída":"Iniciar sessão"}</AstraAction>
    </div>
    </section>
    <section data-testid="home-training-week">
      <div className="a6-section-title"><h2>Seu ritmo</h2><small>{p.week||"Ciclo atual"}</small></div>
      <div className="a6-week">{WEEK.map((label,i)=>{const d=new Date(monday);d.setDate(monday.getDate()+i);const done=trained.has(new Intl.DateTimeFormat("sv-SE").format(d));return <div key={label} className={`a6-day ${done?"a6-done":""} ${i===dayIndex?"a6-selected":""}`}><span>{label.charAt(0)}</span><strong aria-label={`${d.toLocaleDateString("pt-BR")}${done?", treino registrado":""}`}>{done?"✓":d.getDate()}</strong></div>})}</div>
    </section>
    <section className="a6-mini-grid" data-testid="home-acoes-rapidas">
      <article className="a6-panel a6-mini" data-testid="home-nutrition-progress"><AstraIcon name="nutrition"/><div><p>Nutrição</p><strong>{nutrition?`${Math.round(kcal).toLocaleString("pt-BR")} kcal`:"Sem plano"}</strong></div></article>
      <details className="a6-panel a6-mini-water" data-testid="home-hydration"><summary className="a6-mini a6-water"><AstraIcon name="water"/><div><p>Água</p><strong>{(water/1000).toLocaleString("pt-BR",{maximumFractionDigits:2})} L <span className="a6-muted">/ {(waterGoal/1000).toLocaleString("pt-BR",{maximumFractionDigits:1})} L</span></strong></div></summary><div className="a6-water-controls"><button type="button" data-testid="hydration-add-250" disabled={waterBusy} onClick={()=>addWater(250)}>+250 ml</button><button type="button" data-testid="hydration-add-500" disabled={waterBusy} onClick={()=>addWater(500)}>+500 ml</button><button type="button" data-testid="hydration-undo" aria-label="Desfazer água" disabled={waterBusy||water===0} onClick={undoWater}>Desfazer</button></div></details>
    </section>
    {checkinOpen&&<div className="ref3-sheet" data-testid="today-checkin-modal"><button className="ref3-sheet-close" onClick={()=>setCheckinOpen(false)}><X size={20}/></button><span>CHECK-IN DE HOJE</span><h2>Como você chega para o treino?</h2><div className="ref3-checkin-grid">{[["Sono","sleep"],["Energia","energy"],["Motivação","motivation"],["Dor muscular","soreness"],["Estresse","stress"]].map(([label,key])=><label key={key}><span>{label}</span><input type="range" min="1" max="5" value={checkinForm[key]} onChange={e=>setCheckinForm(f=>({...f,[key]:Number(e.target.value)}))}/><b>{checkinForm[key]}</b></label>)}</div><button className="ref3-primary" data-testid="save-today-checkin" disabled={checkinBusy} onClick={submitCheckin}>{checkinBusy?"Salvando…":"Salvar check-in"}</button><button className="ref3-direct" onClick={start}>Começar direto</button></div>}
  </AstraPage>;
}
