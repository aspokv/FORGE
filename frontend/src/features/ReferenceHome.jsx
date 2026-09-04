import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {Check,ChevronRight,Clock,Droplet,Layers3,UserRound,X} from "lucide-react";
import planPullArt from "../assets/forge-plan-pull.webp";
import heroArt from "../assets/forge-home-athlete-reference.jpg";
import fallbackArt from "../assets/forge-gym-cinematic.jpg";
import "../home-hero-card.css";
import {consumedTotals} from "./foodDiary";

const API=`${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const WEEK=["SEG","TER","QUA","QUI","SEX","SÁB","DOM"];
const localDateKey=()=>{const d=new Date(),p=n=>String(n).padStart(2,"0");return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`};
const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
const normalize=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
export const isPullPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)pull(\s|$)|dorsal|costas|largura|espessura/.test(key)};
export const isLegPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)legs?(\s|$)|perna|quadriceps|posterior|glute|panturrilha/.test(key)};
export const isPushPlan=(sessionName,focus=[])=>{const key=normalize([sessionName,...focus].join(" "));return /(^|\s)push(\s|$)|peito|peitoral|triceps|ombro/.test(key)};
export const planArtworkKindFor=(sessionName,focus=[])=>isPullPlan(sessionName,focus)?"pull":isLegPlan(sessionName,focus)?"legs":isPushPlan(sessionName,focus)?"push":"default";
export const planArtworkFor=(sessionName,focus=[])=>{const kind=planArtworkKindFor(sessionName,focus);return kind==="pull"?planPullArt:kind==="legs"?"/images/anatomy/legs-quads-front.webp":kind==="push"?"/images/anatomy/push-front.webp":fallbackArt};
const Macro=({label,value,goal,tone})=>{const pct=goal?clamp(value/goal*100,0,100):0;return <div className={`ref3-macro ${tone}`}><span>{label}</span><i><b style={{width:`${pct}%`}}/></i><strong>{Math.round(value).toLocaleString("pt-BR")} <em>/ {Math.round(goal||0).toLocaleString("pt-BR")} g</em></strong></div>};
const referenceDateLabel=date=>{const raw=new Intl.DateTimeFormat("pt-BR",{weekday:"long",day:"2-digit",month:"long"}).format(date).replace("-feira","");const cap=raw.charAt(0).toUpperCase()+raw.slice(1);return cap.replace(/ de ([a-záàâãéêíóôõúç]+)/i,(_,m)=>` de ${m.charAt(0).toUpperCase()+m.slice(1)}`)};

export default function ReferenceHome({db,start,onRecoveryCheckin}){
  const p=db.program||{};
  const [nutrition,setNutrition]=useState(null),[mealLog,setMealLog]=useState([]),[hydration,setHydration]=useState(null),[checkin,setCheckin]=useState(null);
  const [foodExtras,setFoodExtras]=useState([]);
  const [waterOpen,setWaterOpen]=useState(false),[waterBusy,setWaterBusy]=useState(false),[checkinOpen,setCheckinOpen]=useState(false),[checkinBusy,setCheckinBusy]=useState(false);
  const [checkinForm,setCheckinForm]=useState({sleep:4,energy:4,motivation:4,soreness:2,stress:2});
  useEffect(()=>{let alive=true;const day=localDateKey();Promise.allSettled([axios.get(`${API}/nutrition/plan`),axios.get(`${API}/nutrition/adherence/${day}`),axios.get(`${API}/hydration/${day}`),axios.get(`${API}/recovery/${day}`)]).then(([n,a,h,r])=>{if(!alive)return;if(n.status==="fulfilled")setNutrition(n.value.data);if(a.status==="fulfilled"){setMealLog(a.value.data.meals||[]);setFoodExtras(a.value.data.extras||[])}if(h.status==="fulfilled")setHydration(h.value.data);if(r.status==="fulfilled")setCheckin(r.value.data?.checkin||null)});return()=>{alive=false}},[]);

  const sessions=p.sessions||[],activeIndex=Math.max(0,sessions.findIndex(s=>s.day===p.active_day));
  const active=sessions[activeIndex]||sessions[0]||{},items=active.exercises||p.exercises||[];
  const plannedSets=items.reduce((s,x)=>s+Number(x.sets||0),0),duration=active.duration||p.duration||`${Math.max(35,Math.round(plannedSets*3.4))} min`;
  const raw=active.label||p.session||"Treino de hoje",sessionName=String(raw).split(/[—–]/).map(x=>x.trim()).filter(Boolean).pop()||raw;
  const focus=(active.focus||p.focus||[]).slice(0,3),planArtwork=planArtworkFor(sessionName,focus);
  const firstName=(db.profile?.name||"").trim().split(" ")[0];
  const displayName=firstName&&firstName.toLowerCase()!=="novo"?firstName:"Atleta";
  const now=new Date(),dateLabel=referenceDateLabel(now);
  const dayIndex=(now.getDay()+6)%7;

  const targets=nutrition?.targets||{},daily=nutrition?.daily_totals||{},goalKcal=Number(targets.goal_calories||daily.kcal||0),goalProtein=Number(targets.protein_g||0),goalCarbs=Number(targets.carbs_g||0),goalFat=Number(targets.fat_g||0);
  const consumed=useMemo(()=>consumedTotals(nutrition?.meals,mealLog,foodExtras),[nutrition,mealLog,foodExtras]);
  const kcal=consumed.kcal,kcalPct=goalKcal?clamp(kcal/goalKcal*100,0,100):0;
  const water=Number(hydration?.total_ml||0),waterGoal=Number(hydration?.goal_ml||2500),waterPct=waterGoal?clamp(water/waterGoal*100,0,100):0,filledDrops=Math.round(waterPct/100*7);

  const addWater=async amount=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount});setHydration(r.data)}finally{setWaterBusy(false)}};
  const undoWater=async()=>{if(waterBusy)return;setWaterBusy(true);try{const r=await axios.delete(`${API}/hydration/${localDateKey()}/last`);setHydration(r.data)}finally{setWaterBusy(false)}};
  const submitCheckin=async()=>{if(checkinBusy)return;setCheckinBusy(true);try{const r=await axios.post(`${API}/recovery`,{profile_id:db.profile?.id,local_date:localDateKey(),...checkinForm});setCheckin(r.data?.checkin||r.data);onRecoveryCheckin?.(r.data);setCheckinOpen(false)}finally{setCheckinBusy(false)}};
  const openPlan=()=>checkin?start():setCheckinOpen(true);
  const fallbackPlanArtwork=e=>{if(e.currentTarget.dataset.fallback==="1")return;e.currentTarget.dataset.fallback="1";e.currentTarget.src=fallbackArt};

  return <div className="reference-home-v3" data-testid="reference-home-v3">
    <section className="ref3-top-hero" data-testid="home-top-hero">
      <img src={heroArt} alt="Ambiente de treino FORGE" loading="eager"/>
      <div className="ref3-top-hero-shade"/>
      <div className="ref3-top-hero-copy">
        <strong className="ref3-top-hero-brand">FORGE</strong>
        <h1>Olá, {displayName}</h1>
        <p>Pronto para mais um dia de<br/>evolução?</p>
      </div>
      <div className="ref3-top-hero-avatar"><UserRound size={24}/></div>
      <div className="ref3-top-hero-motto"><span>DISCIPLINA</span><span>GERA</span><span>RESULTADOS</span></div>
    </section>

    <section className="ref3-week" data-testid="home-training-week"><h2>Resumo da semana</h2><div className="ref3-week-days">{WEEK.map((label,i)=>{const done=i<dayIndex&&i<activeIndex,current=i===dayIndex;return <div key={label} className={`${done?"done ":""}${current?"current":""}`}><span>{label}</span><i>{done?<Check size={18}/>:null}</i></div>})}</div></section>

    <section className="ref3-plan" data-testid="daily-briefing"><h2>Plano de hoje</h2><p>{dateLabel}</p><button type="button" className="ref3-plan-card" onClick={openPlan}><div className="ref3-plan-art"><img src={planArtwork} alt={`Treino ${sessionName}`} loading="eager" onError={fallbackPlanArtwork}/></div><div className="ref3-plan-copy"><strong>{sessionName}</strong><small>{focus.length?focus.join(", "):"Treino completo"}</small><div><em><Clock size={15}/>{duration}</em><em><Layers3 size={15}/>{plannedSets} séries</em></div></div><ChevronRight size={20}/></button><button className="ref3-a11y" data-testid="start-workout-button" onClick={start}>Começar treino</button>{!checkin&&<button className="ref3-a11y" data-testid="checkin-primary-button" onClick={()=>setCheckinOpen(true)}>Fazer check-in</button>}</section>

    <section className="ref3-nutrition" data-testid="home-nutrition-progress"><h2>Nutrição</h2><p>Meta diária</p><div className="ref3-calorie-row"><div className="ref3-calorie-ring" style={{background:`conic-gradient(#ff934f ${kcalPct}%,#262626 0)`}}><i/></div><div><strong>{Math.round(kcal).toLocaleString("pt-BR")} <em>/ {Math.round(goalKcal||0).toLocaleString("pt-BR")}</em></strong><span>kcal consumidas</span></div></div><div className="ref3-macros"><Macro label="Proteínas" value={consumed.protein_g} goal={goalProtein} tone="protein"/><Macro label="Carboidratos" value={consumed.carbs_g} goal={goalCarbs} tone="carbs"/><Macro label="Gorduras" value={consumed.fat_g} goal={goalFat} tone="fat"/></div></section>

    <section className="ref3-hydration" data-testid="home-hydration"><button type="button" className="ref3-water-main" onClick={()=>setWaterOpen(v=>!v)}><h2>Hidratação</h2><strong>{(water/1000).toLocaleString("pt-BR",{maximumFractionDigits:2})} <em>/ {(waterGoal/1000).toLocaleString("pt-BR",{maximumFractionDigits:1})} L</em></strong><span>Copos registrados</span><div className="ref3-drops">{Array.from({length:7},(_,i)=><Droplet key={i} size={30} className={i<filledDrops?"filled":""}/>)}</div></button>{waterOpen&&<div className="ref3-water-actions"><button data-testid="hydration-add-250" disabled={waterBusy} onClick={()=>addWater(250)}>+250 ml</button><button data-testid="hydration-add-500" disabled={waterBusy} onClick={()=>addWater(500)}>+500 ml</button><button data-testid="hydration-undo" disabled={waterBusy} onClick={undoWater}>Desfazer</button></div>}</section>

    {checkinOpen&&<div className="ref3-sheet" data-testid="today-checkin-modal"><button className="ref3-sheet-close" onClick={()=>setCheckinOpen(false)}><X size={20}/></button><span>CHECK-IN DE HOJE</span><h2>Como você chega para o treino?</h2><div className="ref3-checkin-grid">{[["Sono","sleep"],["Energia","energy"],["Motivação","motivation"],["Dor muscular","soreness"],["Estresse","stress"]].map(([label,key])=><label key={key}><span>{label}</span><input type="range" min="1" max="5" value={checkinForm[key]} onChange={e=>setCheckinForm(f=>({...f,[key]:Number(e.target.value)}))}/><b>{checkinForm[key]}</b></label>)}</div><button className="ref3-primary" data-testid="save-today-checkin" disabled={checkinBusy} onClick={submitCheckin}>{checkinBusy?"Salvando…":"Salvar check-in"}</button><button className="ref3-direct" onClick={start}>Começar direto</button></div>}
  </div>;
}
