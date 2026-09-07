import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {ChevronRight,Clock,Droplet,Layers3,RotateCcw,Utensils,X} from "lucide-react";
import athleteArt from "../assets/forge-home-athlete-reference.jpg";
import {consumedTotals} from "./foodDiary";

const API=`${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const WEEK=["SEG","TER","QUA","QUI","SEX","SÁB","DOM"];
const localDateKey=()=>{const d=new Date(),p=n=>String(n).padStart(2,"0");return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`};
const normalize=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
export const isPullPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)pull(\s|$)|dorsal|costas|largura|espessura/.test(key)};
export const isLegPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)legs?(\s|$)|perna|quadriceps|posterior|glute|panturrilha/.test(key)};
export const isPushPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)push(\s|$)|peito|peitoral|triceps|ombro/.test(key)};
export const planArtworkKindFor=(sessionName,focus=[])=>isPullPlan(sessionName,focus)?"pull":isLegPlan(sessionName,focus)?"legs":isPushPlan(sessionName,focus)?"push":"default";
export const planArtworkFor=(sessionName,focus=[])=>{const kind=planArtworkKindFor(sessionName,focus);return kind==="pull"?"/images/anatomy/pull-back.webp":kind==="legs"?"/images/anatomy/legs-quads-front.webp":kind==="push"?"/images/anatomy/push-front.webp":"/images/anatomy/push-front.webp"};
const referenceDateLabel=date=>new Intl.DateTimeFormat("pt-BR",{weekday:"long",day:"2-digit",month:"long"}).format(date).replace("-feira","").toUpperCase();

export default function ReferenceHome({db,start,onRecoveryCheckin}){
  const p=db.program||{};
  const[nutrition,setNutrition]=useState(null),[mealLog,setMealLog]=useState([]),[hydration,setHydration]=useState(null),[checkin,setCheckin]=useState(null),[foodExtras,setFoodExtras]=useState([]);
  const[waterBusy,setWaterBusy]=useState(false),[checkinOpen,setCheckinOpen]=useState(false),[checkinBusy,setCheckinBusy]=useState(false);
  const[checkinForm,setCheckinForm]=useState({sleep:4,energy:4,motivation:4,soreness:2,stress:2});
  useEffect(()=>{let alive=true;const day=localDateKey();Promise.allSettled([axios.get(`${API}/nutrition/plan`),axios.get(`${API}/nutrition/adherence/${day}`),axios.get(`${API}/hydration/${day}`),axios.get(`${API}/recovery/${day}`)]).then(([n,a,h,r])=>{if(!alive)return;if(n.status==="fulfilled")setNutrition(n.value.data);if(a.status==="fulfilled"){setMealLog(a.value.data.meals||[]);setFoodExtras(a.value.data.extras||[])}if(h.status==="fulfilled")setHydration(h.value.data);if(r.status==="fulfilled")setCheckin(r.value.data?.checkin||null)});return()=>{alive=false}},[]);

  const sessions=p.sessions||[],activeIndex=Math.max(0,sessions.findIndex(s=>s.day===p.active_day));
  const active=sessions[activeIndex]||sessions[0]||{},items=active.exercises||p.exercises||[];
  const plannedSets=items.reduce((s,x)=>s+Number(x.sets||0),0),duration=active.duration||p.duration||`${Math.max(35,Math.round(plannedSets*3.4))} min`;
  const raw=active.label||p.session||"Treino de hoje",sessionName=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const focus=(active.focus||p.focus||[]).slice(0,3);
  const firstName=(db.profile?.name||"").trim().split(" ")[0],displayName=firstName&&firstName.toLowerCase()!=="novo"?firstName:"Atleta";
  const now=new Date(),dateLabel=referenceDateLabel(now),dayIndex=(now.getDay()+6)%7;
  const targets=nutrition?.targets||{},daily=nutrition?.daily_totals||{},goalKcal=Number(targets.goal_calories||daily.kcal||0);
  const consumed=useMemo(()=>consumedTotals(nutrition?.meals,mealLog,foodExtras),[nutrition,mealLog,foodExtras]);
  const kcal=consumed.kcal,water=Number(hydration?.total_ml||0),waterGoal=Number(hydration?.goal_ml||2500);

  const addWater=async amount=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount});setHydration(r.data)}finally{setWaterBusy(false)}};
  const undoWater=async()=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.delete(`${API}/hydration/${localDateKey()}/last`);setHydration(r.data)}finally{setWaterBusy(false)}};
  const submitCheckin=async()=>{if(checkinBusy)return;setCheckinBusy(true);try{const r=await axios.post(`${API}/recovery`,{profile_id:db.profile?.id,local_date:localDateKey(),...checkinForm});setCheckin(r.data?.checkin||r.data);onRecoveryCheckin?.(r.data);setCheckinOpen(false)}finally{setCheckinBusy(false)}};
  const openPlan=()=>checkin?start():setCheckinOpen(true);

  return <div className="reference-home-v3 astra-home" data-testid="reference-home-v3">
    <section className="astra-home-intro">
      <p className="eyebrow">{dateLabel}</p><h1>Olá, {displayName}.</h1><p>Seu próximo passo está aqui.</p>
    </section>
    <section className="astra-home-hero" data-testid="home-top-hero">
      <img src={athleteArt} alt="Atleta FORGE" loading="eager" fetchPriority="high"/><div>DISCIPLINA HOJE.<br/>RESULTADOS SEMPRE.</div>
    </section>
    <section className="astra-today-card" data-testid="daily-briefing">
      <div className="astra-today-top"><div><p className="eyebrow">SEU TREINO DE HOJE</p><h2>{sessionName}</h2><p>{focus.length?focus.join(" · "):"Treino completo"}</p></div><span className="pill">{String(active.label||"Sessão atual").split(/[—–]/)[0].trim()}</span></div>
      <div className="astra-meta"><span><Clock size={15}/>{duration}</span><span><Layers3 size={15}/>{plannedSets} séries</span></div>
      <button type="button" className="astra-primary" data-testid="start-workout-button" onClick={openPlan}>Começar treino <ChevronRight size={17}/></button>
    </section>
    <section className="astra-week-block" data-testid="home-training-week">
      <div className="astra-section-head"><h2>Seu ritmo</h2><small>Semana {Math.max(1,activeIndex+1)} de {Math.max(1,sessions.length)}</small></div>
      <div className="astra-week-grid">{WEEK.map((label,i)=>{const done=i<dayIndex&&i<activeIndex,current=i===dayIndex;return <div key={label} className={`astra-day ${done?"done ":""}${current?"current":""}`}><span>{label.charAt(0)}</span><strong>{done?"✓":i+1}</strong></div>})}</div>
    </section>
    <section className="astra-mini-grid" data-testid="home-acoes-rapidas">
      <article className="astra-mini" data-testid="home-nutrition-progress"><Utensils size={18}/><div><p>Nutrição</p><strong>{Math.round(kcal).toLocaleString("pt-BR")} <small>/ {Math.round(goalKcal||0).toLocaleString("pt-BR")} kcal</small></strong></div></article>
      <article className="astra-mini water" data-testid="home-hydration"><Droplet size={18}/><div><p>Água</p><strong>{(water/1000).toLocaleString("pt-BR",{maximumFractionDigits:2})} L <small>/ {(waterGoal/1000).toLocaleString("pt-BR",{maximumFractionDigits:1})} L</small></strong></div><div className="astra-water-actions"><button disabled={waterBusy} onClick={()=>addWater(250)}>+250</button><button aria-label="Desfazer água" disabled={waterBusy||water===0} onClick={undoWater}><RotateCcw size={12}/></button></div></article>
    </section>
    {checkinOpen&&<div className="ref3-sheet" data-testid="today-checkin-modal"><button className="ref3-sheet-close" onClick={()=>setCheckinOpen(false)}><X size={20}/></button><span>CHECK-IN DE HOJE</span><h2>Como você chega para o treino?</h2><div className="ref3-checkin-grid">{[["Sono","sleep"],["Energia","energy"],["Motivação","motivation"],["Dor muscular","soreness"],["Estresse","stress"]].map(([label,key])=><label key={key}><span>{label}</span><input type="range" min="1" max="5" value={checkinForm[key]} onChange={e=>setCheckinForm(f=>({...f,[key]:Number(e.target.value)}))}/><b>{checkinForm[key]}</b></label>)}</div><button className="ref3-primary" data-testid="save-today-checkin" disabled={checkinBusy} onClick={submitCheckin}>{checkinBusy?"Salvando…":"Salvar check-in"}</button><button className="ref3-direct" onClick={start}>Começar direto</button></div>}
  </div>;
}
