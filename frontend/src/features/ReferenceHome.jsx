import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {X} from "lucide-react";
import {AstraPage,AstraIntro,AstraAction,AstraMeta,AstraIcon} from "./AstraUI";
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
  const consumed=useMemo(()=>consumedTotals(nutrition?.meals,mealLog,foodExtras),[nutrition,mealLog,foodExtras]);
  const kcal=consumed.kcal,water=Number(hydration?.total_ml||0),waterGoal=Number(hydration?.goal_ml||2500);

  const addWater=async amount=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount});setHydration(r.data)}finally{setWaterBusy(false)}};
  const undoWater=async()=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.delete(`${API}/hydration/${localDateKey()}/last`);setHydration(r.data)}finally{setWaterBusy(false)}};
  const submitCheckin=async()=>{if(checkinBusy)return;setCheckinBusy(true);try{const r=await axios.post(`${API}/recovery`,{profile_id:db.profile?.id,local_date:localDateKey(),...checkinForm});setCheckin(r.data?.checkin||r.data);onRecoveryCheckin?.(r.data);setCheckinOpen(false)}finally{setCheckinBusy(false)}};
  const openPlan=()=>checkin?start():setCheckinOpen(true);

  const monday=new Date(now);monday.setDate(now.getDate()-dayIndex);
  const trained=new Set((db.recent_sets||[]).map(row=>{const d=new Date(row.created_at);return Number.isNaN(d.getTime())?"":new Intl.DateTimeFormat("sv-SE").format(d)}));
  return <AstraPage screen={0} testId="reference-home-v3">
    <AstraIntro eyebrow={dateLabel} title={`Olá, ${displayName}.`} subtitle="Seu próximo passo está aqui."/>
    <div className="a6-hero" data-testid="home-top-hero"><img src={athleteArt} alt="Atleta em ambiente de treino" loading="eager" fetchPriority="high"/><div className="a6-hero-copy">DISCIPLINA HOJE.<br/>RESULTADOS SEMPRE.</div></div>
    <section className="a6-panel a6-workout-card" data-testid="daily-briefing">
      <div className="a6-split"><div className="a6-eyebrow">SEU TREINO DE HOJE</div><span className="a6-pill">{String(active.label||p.session||"Sessão atual").split(/[—–]/)[0].trim()}</span></div>
      <h2>{sessionName}</h2><p>{focus.length?focus.join(" · "):"Treino completo"}</p>
      <AstraMeta duration={duration} sets={plannedSets}/>
      <AstraAction testId="start-workout-button" onClick={openPlan}>Começar treino</AstraAction>
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
