/* eslint-disable react/no-unstable-nested-components */
import {useEffect,useMemo,useRef,useState} from "react";
import axios from "axios";
import {motion} from "framer-motion";
import {Activity,BarChart3,Bell,BrainCircuit,Check,ChevronRight,CircleUserRound,Dumbbell,FileUp,Home,Info,LineChart,LockKeyhole,LogOut,Play,RotateCcw,ShieldCheck,Sliders,Sparkles,TimerReset,TrendingUp,Trophy,UserRound,Utensils,X} from "lucide-react";
import "@/App.css";
import "./features/builder.css";
import "./features/auth.css";
import "./features/acquisition.css";
import "./features/manual-workout.css";
import "./features/performance-os.css";
import ProgramBuilder from "./features/ProgramBuilder";
import {findTechnique,TECHNIQUE_FALLBACK} from "./features/techniques";
import {AuthProvider,useAuth} from "./features/AuthContext";
import {anteriorNaLista,passosPendentes,proximoNaLista,respostasIniciais} from "./features/onboardingResume";
import Landing from "./features/Landing";
import PasswordReset from "./features/PasswordReset";
import SignupFlow,{PagamentoPendente} from "./features/SignupFlow";
import {LoginScreen,InviteScreen} from "./features/AuthScreens";
import AdminPanel from "./features/AdminPanel";
import Nutrition from "./features/Nutrition";
import Billing from "./features/Billing";
import ManualWorkout from "./features/ManualWorkout";
import {completeWorkout} from "./features/completeWorkout";
import {LEGACY_TRAINING_GOAL,DEFAULT_BODY_GOAL,goalFromCatalog,intensityForSubmit,intensityOnGoalChange} from "./features/onboardingGoals";
import {ONBOARDING_STEPS,RANK_LABEL,togglePriority,roleFor,nextStep,previousStep} from "./features/musclePriorities";
import {splitOptions,TRAINING_METHODS} from "./features/trainingSplits";
const API=`${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const GROUPS={PEITORAL:["Peitoral superior","Peitoral esternal"],OMBROS:["Deltóide anterior","Deltóide lateral","Deltóide posterior"],COSTAS:["Dorsais / largura","Costas / espessura","Trapézio"],BRAÇOS:["Bíceps","Braquial","Tríceps"],PERNAS:["Quadríceps","Posteriores","Glúteos","Adutores","Panturrilhas"],CORE:["Abdômen","Oblíquos"]};


const FALLBACK={profile:{id:"demo",name:"Rafael Mendes",goal:"Hipertrofia com especialização",experience:"Avançado",days:4,session_minutes:70,priorities:["Deltóide lateral","Peitoral superior","Posteriores"],assessment:{}},program:{week:"Semana 3 de 6",session:"Upper A — tensão e largura",duration:"67 min",focus:["Peitoral superior","Deltóide lateral"],exercises:[{exercise_id:"incline-smith",sets:3,reps:"6–8",rir:"1–2",rest:"3 min",load:82},{exercise_id:"lat-pulldown",sets:3,reps:"8–10",rir:"1–2",rest:"2 min",load:62},{exercise_id:"lateral-raise",sets:4,reps:"12–20",rir:"1–2",rest:"90 s",load:12}]},exercises:[],muscles:[],recent_sets:[],demo:true};
const navIcons={Hoje:Home,Treino:Dumbbell,"Alimentação":Utensils,Progresso:TrendingUp,Análise:BarChart3,Planos:ShieldCheck,Perfil:UserRound};
function AthleteShell(){const{user,signOut}=useAuth();const profileId=user?.id;const[db,setDb]=useState(null),[tab,setTab]=useState("Hoje"),[loading,setLoading]=useState(true),[assessment,setAssessment]=useState(false),[analytics,setAnalytics]=useState(null),[report,setReport]=useState(null),[coach,setCoach]=useState(false),[coachText,setCoachText]=useState(""),[busy,setBusy]=useState(false),[builder,setBuilder]=useState(false),[manualOpen,setManualOpen]=useState(false),[techDetail,setTechDetail]=useState(null),[previewData,setPreviewData]=useState(null);useEffect(()=>{if(!user)return;axios.get(`${API}/bootstrap`).then(r=>{const data=r.data;setDb(data);if(data.profile?.onboarding_required&&user?.role==="ATHLETE")setAssessment(true)}).catch(()=>{setDb(null)}).finally(()=>setLoading(false))},[user?.id]);useEffect(()=>{if(!db)return;if(["Progresso","Análise"].includes(tab))axios.get(`${API}/analytics`).then(r=>setAnalytics(r.data));if(tab==="Análise")axios.get(`${API}/weekly-report`).then(r=>setReport(r.data))},[tab,!!db]);const context=useMemo(()=>{if(!db)return{};return{profile:db.profile,assessment:db.profile.assessment,program:db.program,priorities:db.profile.priorities,recent_sets:db.recent_sets,weekly_volume:analytics?.volume,recovery:db.profile.recovery,baseline:db.profile.baseline}},[db,analytics]);const ask=async question=>{setBusy(true);setCoachText("");try{const r=await fetch(`${API}/coach`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question,context})}),reader=r.body.getReader(),decoder=new TextDecoder();let done=false;while(!done){const part=await reader.read();done=part.done;decoder.decode(part.value||new Uint8Array()).split("\n\n").forEach(x=>{if(x.startsWith("data: ")&&!x.includes("[DONE]")){try{const j=JSON.parse(x.slice(6));setCoachText(t=>t+(j.text||j.error||""))}catch{setCoachText("Resposta indisponível.")}}})}}catch{setCoachText("Coach temporariamente indisponível.")}finally{setBusy(false)}};const finish=async form=>{if(form.automation_mode==="FORGE_ASSISTED"){try{const r=await axios.post(`${API}/program/preview`,form);setPreviewData({form,program:r.data.program});setAssessment(false)}catch{setDb(x=>({...x,profile:{...x.profile,...form}}));setAssessment(false);setPreviewData(null)}}else{try{const payload={...form,profile_id:user?.id||form.profile_id};const r=await axios.post(`${API}/assessment`,payload);setDb(x=>({...x,profile:r.data.profile,program:r.data.program}))}catch{setDb(x=>({...x,profile:{...x.profile,...form}}))}setAssessment(false)}};const approve=async()=>{if(!previewData)return;try{const payload={...previewData.form,profile_id:user?.id||previewData.form.profile_id};const r=await axios.post(`${API}/assessment`,payload);setDb(x=>({...x,profile:r.data.profile,program:r.data.program}))}catch{setDb(x=>({...x,profile:{...x.profile,...previewData.form}}))}setPreviewData(null)};if(!db&&!loading)return <div className="auth-shell"><div className="auth-card"><p className="muted">Erro ao carregar dados do perfil. Tente novamente.</p></div></div>;if(assessment)return <DeepAssessment onDone={finish}initialForm={previewData?.form||respostasIniciais(db?.profile)}passos={passosPendentes(db?.profile)}/>;if(previewData)return <ProgramPreview program={previewData.program}onApprove={approve}onBack={()=>setAssessment(true)}/>;if(!db)return <div className="auth-shell"><div className="auth-card"><p className="muted">Carregando seu perfil...</p></div></div>;const techniques=db.techniques||TECHNIQUE_FALLBACK;const openBuilder=()=>setBuilder(true);const openManual=()=>setManualOpen(true);const manualActivated=res=>{setDb(x=>({...x,program:res.program,profile:{...x.profile,custom_program:res.custom||x.profile.custom_program,automation_mode:"FORGE_PRO",current_session_day:1,exercise_substitutions:{}}}));setManualOpen(false)};const savedProgram=res=>{setDb(x=>({...x,program:res.program,profile:{...x.profile,custom_program:res.custom||null,automation_mode:res.custom?"FORGE_PRO":x.profile.automation_mode}}));setBuilder(false)};const onExerciseSubstituted=res=>{setDb(x=>({...x,program:res.program,profile:{...x.profile,exercise_substitutions:res.exercise_substitutions}}))};const onWorkoutCompleted=res=>{setDb(x=>({...x,program:res.program}))};return <div className="forge-shell"><aside className="rail"><div className="brand"><span className="brand-mark">F</span><span>FORGE</span></div><p className="rail-caption">ADVANCED TRAINING OS</p><Nav tab={tab}setTab={setTab}/><div className="rail-bottom"><div className="status-dot"/> Engine online<br/><span>{user?.role==="ATHLETE"?"Personal profile":"Admin mode"}</span></div></aside><main className="main"><header className="topbar"><div><p className="eyebrow">{tab.toUpperCase()} / 06 JUN 2026</p><h1>{tab==="Hoje"?`Bom treino, ${(db.profile.name||"Atleta").split(" ")[0]}.`:tab}</h1></div><button className="icon-button"data-testid="profile-open-button"onClick={()=>setTab("Perfil")}><CircleUserRound size={20}/></button></header>{loading?<div className="loading"data-testid="loading-state">Carregando seu sistema...</div>:<Page tab={tab}db={db}analytics={analytics}report={report}techniques={techniques}start={()=>setTab("Treino")}openCoach={()=>setCoach(true)}openBuilder={openBuilder}openManual={openManual}openTech={setTechDetail}redo={()=>setAssessment(true)}signOut={signOut}user={user}goHome={()=>setTab("Hoje")}onExerciseSubstituted={onExerciseSubstituted}onWorkoutCompleted={onWorkoutCompleted}/>}</main><div className="mobile-nav"><Nav tab={tab}setTab={setTab}/></div>{coach&&<Coach onClose={()=>setCoach(false)}text={coachText}busy={busy}ask={ask}/>}{builder&&<ProgramBuilder API={API}profile={db.profile}exercises={db.exercises}techniques={techniques}program={db.profile.custom_program||db.program}onSaved={savedProgram}onClose={()=>setBuilder(false)}/>}{manualOpen&&<ManualWorkout API={API}profile={db.profile}exercises={db.exercises}onActivated={manualActivated}onOpenBuilder={()=>{setManualOpen(false);setBuilder(true)}}onClose={()=>setManualOpen(false)}/>}{techDetail&&<TechniqueDetail t={techDetail}onClose={()=>setTechDetail(null)}/>}</div>}
function Nav({tab,setTab}){return <nav>{Object.entries(navIcons).map(([name,Icon])=><button key={name}className={tab===name?"nav-item active":"nav-item"}data-testid={`nav-${name.toLowerCase()}`}onClick={()=>setTab(name)}><Icon size={18}/><span>{name==="Hoje"?"Início":name==="Alimentação"?"Nutrição":name}</span></button>)}</nav>}
function Page({tab,db,analytics,report,techniques,start,openCoach,openBuilder,openManual,openTech,redo,signOut,user,goHome,onExerciseSubstituted,onWorkoutCompleted}){if(tab==="Treino")return <Workout db={db}techniques={techniques}openTech={openTech}goHome={goHome}onExerciseSubstituted={onExerciseSubstituted}onWorkoutCompleted={onWorkoutCompleted}/>;if(tab==="Planos")return <Billing API={API}/>;if(tab==="Progresso")return <Progress analytics={analytics}profileId={db?.profile?.id}/>;if(tab==="Análise")return <Analysis db={db}analytics={analytics}report={report}openCoach={openCoach}/>;if(tab==="Perfil")return <Profile db={db}redo={redo}openBuilder={openBuilder}openManual={openManual}signOut={signOut}user={user}/>;if(tab==="Alimentação")return <Nutrition db={db}API={API}profileId={db?.profile?.id}/>;return <Today db={db}start={start}openCoach={openCoach}openBuilder={openBuilder}openManual={openManual}/>}
function Today({db,start,openCoach,openBuilder,openManual}){
  const p=db.program||{};
  const manual=p.logic?.manual;
  const activeSession=p.sessions?.find(s=>s.day===p.active_day)||p.sessions?.[0];
  const exercises=activeSession?.exercises||p.exercises||[];
  const preview=exercises.slice(0,4).map(x=>({...x,name:db.exercises?.find(e=>e.id===x.exercise_id)?.name||x.name||x.exercise_name||x.exercise_id}));
  const plannedSets=exercises.reduce((sum,x)=>sum+Number(x.sets||0),0);
  const logs=db.recent_sets||[],now=Date.now(),weekMs=7*24*60*60*1000;
  const volumeIn=(from,to)=>logs.filter(x=>{const t=Date.parse(x.created_at);return t>=from&&t<to}).reduce((sum,x)=>sum+Number(x.weight||0)*Number(x.reps||0),0);
  const currentVolume=volumeIn(now-weekMs,now),previousVolume=volumeIn(now-2*weekMs,now-weekMs);
  const volumeChange=previousVolume?Math.round((currentVolume-previousVolume)/previousVolume*100):null;
  const bestSet=logs.reduce((best,x)=>{const e1rm=Number(x.weight||0)*(1+Number(x.reps||0)/30);return e1rm>(best?.e1rm||0)?{...x,e1rm}:best},null);
  const recoveryLabel={HIGH:"Alta",NORMAL:"Normal",LOW:"Baixa",VERY_LOW:"Muito baixa"}[p.logic?.recovery_level]||"Sem check-in";
  return <div className="content performance-home forge-home-final">
    <div className="forge-mobile-mast"><span>FORGE</span><Bell size={18}/></div>
    <div className="performance-heading">
      <div><p className="eyebrow">FORGE / PERFORMANCE OS</p><h2>Seu próximo nível começa agora.</h2></div>
      <span className="live-pill"><i/> SISTEMA ADAPTATIVO ATIVO</span>
    </div>
    <section className="panel signal forge-coach-hero">
      <div className="coach-signal-head"><div className="coach-icon"><BrainCircuit size={20}/></div><p className="eyebrow">COACH IA</p></div>
      <h3>Plano ajustado para sua hipertrofia.</h3>
      <p className="muted">{p.logic?.days||db.profile.days} sessões · {manual?"estrutura manual preservada":"carga, volume e recuperação recalibrados"}.</p>
      <button className="coach-arrow"data-testid="open-coach-button"onClick={openCoach}aria-label="Falar com o Coach IA"><ChevronRight size={16}/></button>
    </section>
    <div className="today-section-label"><span><Dumbbell size={14}/> Treino de hoje</span><button onClick={start}>Ver plano <ChevronRight size={13}/></button></div>
    <section className="panel command forge-workout-preview">
      <div className="preview-list">
        {preview.map((x,i)=><div key={x.exercise_id||i}><span className="preview-icon"><Dumbbell size={16}/></span><div><small>{["PUSH","PULL","LEGS","DELT"][i]}</small><b>{x.name||x.exercise_name||["Supino inclinado","Remada curvada","Agachamento","Elevação lateral"][i]}</b><em>{x.sets} × {x.reps} · {x.load?`${x.load} kg · `:""}RIR {x.rir}</em></div></div>)}
      </div>
      <div className="preview-progress"><div className="performance-dial planned"><span>{plannedSets||"—"}<small>{plannedSets?" séries":""}</small></span><em>prescrição de hoje</em></div></div>
      <button className="primary-button"data-testid="start-workout-button"onClick={start}>Iniciar treino <ChevronRight size={18}/></button>
    </section>
    <div className="forge-metric-grid" aria-label="Indicadores de performance">
      <article className="metric-wide"><span>VOLUME REAL</span><small>Últimos 7 dias</small><b>{Math.round(currentVolume).toLocaleString("pt-BR")} <em>kg</em></b><i className="metric-bars"/><small className={volumeChange!=null&&volumeChange>=0?"positive":""}>{volumeChange==null?"Criando sua linha de base":`${volumeChange>=0?"+":""}${volumeChange}% vs semana anterior`}</small></article>
      <article className="metric-wide"><span>PERFORMANCE</span><small>Melhor e1RM registrado</small><b>{bestSet?bestSet.e1rm.toFixed(1):"—"} <em>{bestSet?"kg":"sem histórico"}</em></b><i className="metric-line"/><small className="positive">{bestSet?(db.exercises?.find(e=>e.id===bestSet.exercise_id)?.name||"Série registrada"):"Complete séries para calcular"}</small></article>
      <article><span>MÉTODO</span><b>{p.logic?.quality_gate?.method_profile?.label||"FORGE"}</b><small>{p.logic?.split||"Divisão adaptativa"}</small></article>
      <article><span>RECUPERAÇÃO</span><b>{recoveryLabel}</b><small>{p.logic?.recovery_level?"check-in mais recente":"Sem dados inventados"}</small></article>
      <article><span>PROGRESSO</span><b>{logs.length}</b><small>séries no histórico recente</small></article>
    </div>
    <div className="forge-home-tools"><button className="text-button"data-testid="open-builder-today"onClick={openBuilder}><Sliders size={13}/> {manual?"Editar programa":"Program Builder"}</button><button className="text-button"data-testid="open-manual-today"onClick={openManual}><FileUp size={13}/> Estrutura manual</button></div>
  </div>
}
const LOAD_LABEL={FIRST_TIME:"Primeira vez",LOAD_UP:"Aumentar carga",KEEP_LOAD:"Manter carga",ADD_REPS:"Buscar mais reps",REDUCE_LOAD:"Reduzir carga"};
function Workout({db,techniques,openTech,goHome,onExerciseSubstituted,onWorkoutCompleted}){
  const p=db.program||{};
  const activeSession=p.sessions?.find(s=>s.day===p.active_day)||p.sessions?.[0];
  const items=activeSession?.exercises||p.exercises||[];
  const hints=db.program?.progression_hints||{};
  const[done,setDone]=useState({});
  const[timer,setTimer]=useState(0);
  const[timerTotal,setTimerTotal]=useState(0);
  const[swap,setSwap]=useState(null);
  const[setInputs,setSetInputs]=useState({});
  const[setErr,setSetErr]=useState({});
  const[finishResult,setFinishResult]=useState(null);
  const[finishing,setFinishing]=useState(false);
  const[partialReason,setPartialReason]=useState("");
  const[showPartial,setShowPartial]=useState(false);
  const[discomfort,setDiscomfort]=useState("none");
  const finishLock=useRef(false);
  const[startedAt,setStartedAt]=useState(()=>Date.now());
  useEffect(()=>{const init={};items.forEach(x=>{const hint=hints[x.exercise_id]||{};for(let n=0;n<x.sets;n++)init[`${x.exercise_id}-${n}`]={weight:hint.last_weight||x.load||0,reps:hint.last_reps||x.reps?.split("–")?.[0]||"8",rir:String(x.rir||"2").match(/\d+/)?.[0]||"2"};});setSetInputs(init)},[items,!!Object.keys(hints).length]);
  const[draftState,setDraftState]=useState("idle");
  const draftTimer=useRef(null),draftReady=useRef(false),lastSaved=useRef("");
  const draftDay=activeSession?.day;
  // Recupera o preenchimento em andamento: refresh, queda de conexao ou sair e voltar
  // antes de "Concluir treino" nao pode perder o que ja foi digitado.
  useEffect(()=>{
    if(!db.profile?.id||draftDay==null||!items.length)return;
    let alive=true;draftReady.current=false;
    axios.get(`${API}/workout/session-draft`,{params:{day:draftDay}}).then(r=>{
      if(!alive)return;
      const saved=r.data?.inputs||{};
      setSetInputs(prev=>{
        const merged=Object.keys(saved).length?{...prev,...saved}:prev;
        lastSaved.current=JSON.stringify(merged);
        return merged;
      });
      if(r.data?.saved_at&&Object.keys(saved).length)setDraftState("saved");
    }).catch(()=>{}).finally(()=>{if(alive)draftReady.current=true});
    return()=>{alive=false};
  },[db.profile?.id,draftDay,items.length]);
  // Autosave com debounce: salva 1,5 s depois da ultima alteracao, nao a cada tecla.
  useEffect(()=>{
    if(!draftReady.current||draftDay==null)return;
    const payload=JSON.stringify(setInputs);
    if(!Object.keys(setInputs).length||payload===lastSaved.current)return;
    setDraftState("saving");
    clearTimeout(draftTimer.current);
    draftTimer.current=setTimeout(()=>{
      axios.put(`${API}/workout/session-draft`,{day:draftDay,inputs:setInputs})
        .then(()=>{lastSaved.current=payload;setDraftState("saved")})
        .catch(()=>setDraftState("error"));
    },1500);
    return()=>clearTimeout(draftTimer.current);
  },[setInputs,draftDay]);
  useEffect(()=>{if(!timer)return;const i=setInterval(()=>setTimer(x=>Math.max(0,x-1)),1000);return()=>clearInterval(i)},[timer]);
  const parseRestSeconds=r=>{if(!r)return 90;const n=parseInt(r);if(!isNaN(n))return n<10?n*60:n;const m=r.match(/(\d+)/);return m?parseInt(m[1])*60:90};
  const mark=(id,n,tech,rest)=>{if(done[id+n])return;const v=setInputs[`${id}-${n}`]||{weight:0,reps:8,rir:2};const rir=Math.max(0,Math.min(5,Number(v.rir)));if(!Number.isFinite(rir)){setSetErr(x=>({...x,[id+n]:true}));return}setDone(x=>({...x,[id+n]:true}));const secs=parseRestSeconds(rest);setTimer(secs);setTimerTotal(secs);axios.post(`${API}/sets`,{profile_id:db.profile.id,exercise_id:id,set_number:n+1,weight:Number(v.weight||0),reps:Number(v.reps||8),rir,session_day:activeSession?.day,technique:tech||"Straight Sets"}).catch(()=>{setDone(x=>({...x,[id+n]:false}));setSetErr(x=>({...x,[id+n]:true}))})};
  const completedEntries=items.flatMap(x=>Array.from({length:x.sets},(_,n)=>({key:x.exercise_id+n,value:setInputs[`${x.exercise_id}-${n}`]}))).filter(x=>done[x.key]);
  const actualVolume=completedEntries.reduce((sum,x)=>sum+Number(x.value?.weight||0)*Number(x.value?.reps||0),0);
  const averageRir=completedEntries.length?completedEntries.reduce((sum,x)=>sum+Number(x.value?.rir||0),0)/completedEntries.length:null;
  const finish=async()=>{if(finishLock.current)return;const total=items.reduce((a,x)=>a+x.sets,0);const completed=completedEntries.length;if(completed<total&&!partialReason.trim()){setShowPartial(true);return}setFinishing(true);const r=await completeWorkout({post:(u,b)=>axios.post(u,b),api:API,day:activeSession?.day,completedSets:completed,totalSets:total,startedAt,lock:finishLock,onCompleted:onWorkoutCompleted,partialReason,discomfort,volumeKg:actualVolume,averageRir:averageRir==null?null:Number(averageRir.toFixed(1))});if(r)setFinishResult(r);if(!r||r.error)setFinishing(false)};
  const openNextWorkout=()=>{setFinishResult(null);setDone({});setSetErr({});setPartialReason("");setShowPartial(false);setDiscomfort("none");setTimer(0);setTimerTotal(0);setStartedAt(Date.now());finishLock.current=false};
  const recLevel=p.logic?.recovery_level;
  const recMsg=recLevel==="LOW"?"Volume ajustado à sua recuperação de hoje.":recLevel==="VERY_LOW"?"Sessão adaptada à sua recuperação de hoje.":p.logic?.block_type==="deload"?"Semana de descarga — volume reduzido de propósito.":null;
  const totalSessionSets=items.reduce((sum,x)=>sum+(Number(x.sets)||0),0);
  const averageRest=Math.round(items.reduce((sum,x)=>sum+parseRestSeconds(x.rest)*(Number(x.sets)||0),0)/Math.max(1,totalSessionSets));
  if(!items.length)return <div className="content workout-page"><div className="empty-state"data-testid="workout-empty-state"><Dumbbell size={22}/><h3>Nenhuma sessão disponível</h3><p className="muted">Gere ou aprove um programa para ver o treino de hoje.</p></div></div>;
  if(finishResult&&!finishResult.error)return <div className="content workout-page workout-complete-page"data-testid="workout-complete-page">
    <section className="completion-hero">
      <span className="completion-seal"><Check size={30}/></span>
      <p className="eyebrow">SESSÃO REGISTRADA · PERFORMANCE REAL</p>
      <h2>{finishResult.completedSession?.label||"Treino concluído"}</h2>
      <p className="muted">O motor já atualizou sua sequência e preparou a próxima sessão.</p>
      <div className="completion-metrics">
        <div><span>SÉRIES</span><b>{finishResult.completed}/{finishResult.total}</b><small>{finishResult.adherence}% de aderência</small></div>
        <div><span>VOLUME REAL</span><b>{finishResult.volumeKg.toLocaleString("pt-BR")}<em> kg</em></b><small>carga × repetições</small></div>
        <div><span>RIR MÉDIO</span><b>{finishResult.averageRir??"—"}</b><small>{finishResult.averageRir==null?"sem leitura":"esforço registrado"}</small></div>
        <div><span>DURAÇÃO</span><b>{finishResult.minutes}<em> min</em></b><small>tempo da sessão</small></div>
      </div>
    </section>
    <section className="next-session-card">
      <div><p className="eyebrow">PRÓXIMA SESSÃO</p><h3>{finishResult.nextSession?.label||"Próximo treino"}</h3><p className="muted">Já disponível na sua sequência FORGE.</p></div>
      <button className="primary-button"data-testid="workout-open-next"onClick={openNextWorkout}>Ver próximo treino <ChevronRight size={17}/></button>
    </section>
    <button className="text-button completion-home"data-testid="workout-finish-gohome"onClick={goHome}>Voltar para Hoje</button>
  </div>;
  return <div className="content workout-page">
    <div className="workout-head"><div><p className="eyebrow">EM EXECUÇÃO · {p.week}</p><h2>{activeSession?.label||p.session}</h2><p className="muted">Demanda {activeSession?.demand||"MODERATE"} · registre o trabalho real.</p></div>{draftState!=="idle"&&<span className={`autosave-pill ${draftState}`}data-testid="autosave-status">{draftState==="saving"?"salvando...":draftState==="saved"?"salvo automaticamente":"sem conexão — tentando salvar"}</span>}</div>
    <section className="workout-overview">
      <div className="muscle-map" role="img" aria-label="Mapa muscular frontal e posterior"/>
      <div className="workout-overview-copy"><span>GRUPO MUSCULAR</span><b>{activeSession?.label?.split(/[—-]/)?.[0]||"Hipertrofia"}</b><small>Duração estimada · {p.duration||"70 min"}</small></div>
      <div className="workout-kpis"><div><span>VOLUME REAL</span><b>{Math.round(actualVolume).toLocaleString("pt-BR")} <small>kg</small></b><em>{completedEntries.length?"carga × reps registradas":"aguardando séries"}</em></div><div><span>ADERÊNCIA</span><b>{completedEntries.length}<small>/{totalSessionSets}</small></b><em>séries concluídas</em></div><div><span>RIR MÉDIO</span><b>{averageRir==null?"—":averageRir.toFixed(1)}</b><em>{averageRir==null?"sem histórico nesta sessão":"esforço informado"}</em></div><div><span>DESCANSO ALVO</span><b>{averageRest}<small>s</small></b><em>prescrição média</em></div></div>
    </section>
    {recMsg&&<div className="session-banner"data-testid="session-adapted-banner"><ShieldCheck size={16}/><div><b>SESSÃO ADAPTADA</b><p>{recMsg}</p></div></div>}
    <div className={timer>0?"rest-banner active":"rest-banner"}data-testid="rest-timer">
      <div className="rest-label"><TimerReset size={14}/>{timer>0?"Descanso":"Pronto para a próxima série"}</div>
      <div className="rest-time">{timer>0?`${Math.floor(timer/60)}:${String(timer%60).padStart(2,"0")}`:"—"}</div>
      {timer>0&&<div className="rest-bar"><b style={{width:`${100-(timer/Math.max(1,timerTotal)*100)}%`}}/></div>}
    </div>
    {items.map((x,i)=>{
      const ex=db.exercises?.find(e=>e.id===x.exercise_id)||{name:x.exercise_id};
      const tech=findTechnique(techniques,x.technique_id,x.technique);
      const isAdv=tech.id!=="straight";
      const hint=hints[x.exercise_id];
      return <section className="exercise"key={x.exercise_id+i}>
        <div className="exercise-title">
          <div>
            <span className="exercise-index">0{i+1}</span><h3>{ex.name}</h3>
            <p className="muted">{x.reps} reps · RIR {x.rir} · {x.rest}</p>
            {x.note&&<p className="muted" style={{marginTop:6}}>· {x.note}</p>}
            <button className={isAdv?"technique-badge":"technique-badge plain"}data-testid={`technique-badge-${x.exercise_id}-${i}`}onClick={()=>openTech(tech)}><Info size={12}/>{tech.name}</button>
          </div>
          <button className="swap"data-testid={`swap-${x.exercise_id}`}onClick={()=>setSwap(ex)}><RotateCcw size={15}/> Substituir</button>
        </div>
        {hint&&hint.last_weight>0&&<div className="progression-hint"data-testid={`progression-hint-${x.exercise_id}`}>
          <div><span>Última sessão</span><b>{hint.last_weight}kg × {hint.last_reps}</b></div>
          {hint.suggested_load&&hint.suggested_load!==hint.last_weight?<div className="suggest"><span>Sugestão</span><b>{hint.suggested_load}kg × {hint.last_reps}</b></div>:<div className="suggest"><span>{LOAD_LABEL[hint.action]||hint.action}</span><b className="reason">{hint.reason}</b></div>}
        </div>}
        <div className="set-grid">
          <span>SÉRIE</span><span>ALVO</span><span>CARGA</span><span>REPS</span><span>RIR</span><span>STATUS</span>
          {Array.from({length:x.sets},(_,n)=><div className={done[x.exercise_id+n]?"set-row completed":"set-row"}key={n}>
            <b>{n+1}</b><span>{x.reps}</span>
            <input aria-label={`Carga ${ex.name} ${n+1}`}data-testid={`weight-${x.exercise_id}-${n+1}`}type="text"inputMode="decimal"value={setInputs[`${x.exercise_id}-${n}`]?.weight??x.load??0}onChange={e=>setSetInputs(p=>({...p,[`${x.exercise_id}-${n}`]:{...p[`${x.exercise_id}-${n}`],weight:e.target.value}}))}/>
            <input aria-label={`Reps ${ex.name} ${n+1}`}data-testid={`reps-${x.exercise_id}-${n+1}`}type="text"inputMode="numeric"value={setInputs[`${x.exercise_id}-${n}`]?.reps??x.reps?.split("–")?.[0]??"8"}onChange={e=>setSetInputs(p=>({...p,[`${x.exercise_id}-${n}`]:{...p[`${x.exercise_id}-${n}`],reps:e.target.value}}))}/>
            <input aria-label={`RIR ${ex.name} ${n+1}`}data-testid={`rir-${x.exercise_id}-${n+1}`}type="number"inputMode="numeric"min="0"max="5"value={setInputs[`${x.exercise_id}-${n}`]?.rir??"2"}onChange={e=>setSetInputs(p=>({...p,[`${x.exercise_id}-${n}`]:{...p[`${x.exercise_id}-${n}`],rir:e.target.value}}))}/>
            <button className="set-check"data-testid={`complete-set-${x.exercise_id}-${n+1}`}onClick={()=>mark(x.exercise_id,n,tech.name,x.rest)}>{done[x.exercise_id+n]?<Check size={17}/>:<span/>}{setErr[x.exercise_id+n]&&<span style={{color:"var(--accent)",fontSize:9,marginLeft:4}}>!</span>}</button>
          </div>)}
        </div>
      </section>
    })}
    <section className="session-checkout">
      <div><p className="eyebrow">COMO O CORPO RESPONDEU?</p><p className="muted">Esse sinal melhora os próximos ajustes sem inventar recuperação.</p></div>
      <div className="discomfort-options"role="group"aria-label="Desconforto na sessão">
        {[{id:"none",label:"Sem desconforto"},{id:"mild",label:"Leve desconforto"},{id:"stop",label:"Dor limitante"}].map(x=><button type="button"key={x.id}className={discomfort===x.id?"active":""}onClick={()=>setDiscomfort(x.id)}>{x.label}</button>)}
      </div>
    </section>
    {showPartial&&<section className="partial-completion"data-testid="partial-completion-panel"><p className="eyebrow">CONCLUSÃO PARCIAL · {completedEntries.length}/{totalSessionSets} SÉRIES</p><h3>O que interrompeu a sessão?</h3><div className="partial-reasons">{["Faltou tempo","Fadiga acima do esperado","Dor ou desconforto","Equipamento indisponível","Outro"].map(reason=><button type="button"key={reason}className={partialReason===reason?"active":""}onClick={()=>setPartialReason(reason)}>{reason}</button>)}</div><p className="muted">O FORGE registra a aderência real e usa o motivo na revisão — nunca transforma um treino parcial em treino completo.</p></section>}
    {finishResult?.error&&<div className="workout-feedback error"data-testid="workout-finish-msg">{finishResult.message}</div>}
    {(!finishResult||finishResult.error)&&<button className="finish-button"data-testid="finish-workout-button"disabled={finishing}onClick={finish}><Check size={18}/> {finishing?"Concluindo…":"Concluir treino"}</button>}
    {swap&&<Swap ex={swap}close={()=>setSwap(null)}onSubstituted={onExerciseSubstituted}/>}
  </div>
}
function TechniqueDetail({t,onClose}){return <div className="technique-modal"data-testid="workout-technique-detail"><div className="coach-panel technique-card"><div className="coach-header"><div><p className="eyebrow">TÉCNICA · {t.name.toUpperCase()}</p><h2>{t.short}</h2></div><button className="icon-button"data-testid="close-technique-modal"onClick={onClose}><X size={20}/></button></div><p className="muted">Fadiga estimada: {t.fatigue}</p><p className="technique-block"><b>Como funciona.</b> {t.description}</p><p className="technique-block"><b>Protocolo.</b> {t.protocol}</p><p className="technique-block"><b>Quando usar.</b> {t.when}</p></div></div>}
function Swap({ex,close,onSubstituted}){const[a,setA]=useState([]);const[busy,setBusy]=useState(false);const[err,setErr]=useState("");useEffect(()=>{axios.get(`${API}/exercises/${ex.id}/alternatives`).then(r=>setA(r.data.alternatives))},[ex]);const pick=async x=>{setBusy(true);setErr("");try{const r=await axios.post(`${API}/exercises/substitute`,{original_exercise_id:ex.id,new_exercise_id:x.id});onSubstituted(r.data);close()}catch(e){setErr("Não foi possível substituir agora.")}finally{setBusy(false)}};return <div className="coach-overlay"><div className="coach-panel"><div className="coach-header"><div><p className="eyebrow">EXERCISE MATCHING ENGINE</p><h2>Substituir {ex.name}</h2></div><button className="icon-button"data-testid="close-swap-button"onClick={close}><X size={20}/></button></div><p className="muted">Mesmo alvo e padrão, com diferença de estabilidade e fadiga.</p>{err&&<p className="muted"style={{color:"var(--accent)"}}data-testid="swap-error">{err}</p>}<div className="coach-suggestions">{a.map((x,i)=><button key={x.id||x.name}data-testid={`alternative-${i+1}`}disabled={busy}onClick={()=>pick(x)}><b>{i?`ALTERNATIVA ${i+1}`:"MELHOR SUBSTITUIÇÃO"}</b><br/>{x.name}<small>{x.reason}</small></button>)}</div></div></div>}
function WeightTracker({profileId}){
  const[history,setHistory]=useState(null);
  const[input,setInput]=useState("");
  const[busy,setBusy]=useState(false);
  const[err,setErr]=useState("");
  useEffect(()=>{if(!profileId)return;axios.get(`${API}/nutrition/weight`).then(r=>setHistory(r.data.history||[])).catch(()=>setHistory([]))},[profileId]);
  const latest=history&&history.length?[...history].sort((a,b)=>b.date.localeCompare(a.date))[0]:null;
  const recent=history?[...history].sort((a,b)=>b.date.localeCompare(a.date)).slice(0,8):[];
  const log=async()=>{
    const v=Number(input);
    if(!v||v<=0){setErr("Informe um peso válido.");return}
    setBusy(true);setErr("");
    try{const r=await axios.post(`${API}/nutrition/weight`,{weight_kg:v});setHistory(h=>[{weight_kg:r.data.weight,date:r.data.date},...(h||[]).filter(x=>x.date!==r.data.date)]);setInput("")}
    catch{setErr("Não foi possível registrar o peso agora.")}
    finally{setBusy(false)}
  };
  return <section className="panel weight-panel">
    <p className="eyebrow">PESO CORPORAL</p>
    {history===null?<div className="skeleton-block"style={{height:60,marginTop:10}}/>:<>
      <div className="weight-current"><b>{latest?latest.weight_kg:"—"}</b><span>{latest?`kg · ${latest.date}`:"kg · sem registros"}</span></div>
      <div className="weight-input-row">
        <input type="text"inputMode="decimal"placeholder="Novo peso (kg)"data-testid="weight-input"value={input}onChange={e=>setInput(e.target.value)}/>
        <button className="secondary-button"data-testid="weight-log-button"onClick={log}disabled={busy}>{busy?"Salvando...":"Registrar"}</button>
      </div>
      {err&&<p className="muted"style={{color:"var(--accent)",fontSize:11,marginTop:6}}>{err}</p>}
      {recent.length>0?<div className="weight-history"data-testid="weight-history">{recent.map((w,i)=><div key={w.date+i}className="weight-history-row"><span>{w.date}</span><b>{w.weight_kg}kg</b></div>)}</div>
        :<p className="muted"style={{fontSize:12,marginTop:12}}>Nenhum peso registrado ainda.</p>}
    </>}
  </section>
}
function Progress({analytics,profileId}){
  if(!analytics)return <div className="content"><div className="skeleton-block"style={{height:88}}/><div className="skeleton-block"style={{height:160,marginTop:16}}/></div>;
  const points=(analytics.trend||[]).filter(x=>Number(x.load)>0);
  const trendChange=points.length>1&&Number(points[0].load)>0?((Number(points.at(-1).load)-Number(points[0].load))/Number(points[0].load)*100):null;
  return <div className="content">
    <div className="section-intro"><p className="eyebrow">PROGRESSÃO</p><h2>O que está subindo?</h2><p className="muted">Histórico por exercício e tendência de performance.</p></div>
    <section className="panel chart-panel">
      <div className="panel-top"><div><p className="eyebrow">CARGA EFETIVA</p><h3>{trendChange==null?"Linha de base":`${trendChange>=0?"+":""}${trendChange.toFixed(1).replace(".",",")}%`} <span className="trend">{trendChange==null?"histórico insuficiente":"últimas 4 semanas"}</span></h3></div><LineChart size={21}/></div>
      {analytics?.trend?.length?<div className="chart"><div className="chart-line">{analytics.trend.map((p,i)=><div key={p.week}style={{height:`${35+i*17}%`}}><b>{p.load}</b><span>{p.week}</span></div>)}</div></div>
        :<p className="muted"style={{marginTop:12}}>Ainda sem histórico suficiente para um gráfico.</p>}
    </section>
    <section className="panel">
      <p className="eyebrow">PRs / HISTÓRICO POR EXERCÍCIO</p>
      {(analytics?.prs||[]).length?(analytics.prs||[]).map(p=><div className="pr-row"key={p.exercise}><div className="pr-icon"><Trophy size={16}/></div><div><b>{p.exercise}</b><p className="muted">{p.date} · tendência disponível</p></div><strong>{p.value}</strong></div>)
        :<p className="muted"data-testid="prs-empty-state">Registre séries no treino para ver seus PRs aqui.</p>}
    </section>
    <WeightTracker profileId={profileId}/>
  </div>
}
function Analysis({db,analytics,report,openCoach}){const[rows,setRows]=useState([]),[explain,setExplain]=useState(false);useEffect(()=>{axios.get(`${API}/muscle-map/${db.profile.id}`).then(r=>setRows(r.data.rows))},[db.profile.id]);return <div className="content"><div className="section-intro"><p className="eyebrow">MEU FÍSICO / MUSCLE MAP</p><h2>Leitura do seu bloco.</h2><p className="muted">Desenvolvimento × prioridade × volume × frequência.</p></div><section className="panel"><div className="panel-top"><div><p className="eyebrow">MUSCLE MAP</p><h3>Regiões que orientam o engine</h3></div><Activity size={20}/></div><div className="muscle-grid">{rows.filter(x=>x.priority!=="normal"||x.score>3).slice(0,14).map(r=><div className="muscle-row"key={r.muscle}data-testid={`muscle-row-${r.muscle}`}><div><b>{r.muscle}</b><p>{r.development} · {r.status}</p></div><span>{r.volume} séries · {r.frequency}x</span><strong>{r.priority}</strong></div>)}</div></section><div className="analysis-grid"><section className="panel"><p className="eyebrow">VOLUME POR REGIÃO</p>{(analytics?.volume||[]).map(v=><div className="volume-line"key={v.name}><div><span>{v.name}</span><strong>{v.value} <em>/ {v.target}</em></strong></div><div className="bar"><b style={{width:`${Math.min(100,v.value/v.target*100)}%`}}/></div></div>)}</section><section className="panel recovery-panel"><p className="eyebrow">RECOVERY SIGNAL</p><div className="recovery-score">3.8 <span>/ 5</span></div><p className="muted">Sobreposição indireta e sono entram no ajuste.</p></section></div>{report&&<section className="panel report"><p className="eyebrow">WEEKLY TRAINING REPORT</p><h3>{report.headline}</h3>{report.signals.map(s=><p className="report-line"key={s}><Check size={15}/>{s}</p>)}</section>}<div className="action-row"><button className="secondary-button"data-testid="explain-program-button"onClick={()=>setExplain(!explain)}>Por que meu treino é assim?</button><button className="secondary-button"data-testid="analysis-coach-button"onClick={openCoach}><BrainCircuit size={17}/> Analisar com Forge Coach</button></div>{explain&&<section className="panel explanation"data-testid="program-explanation"><p className="eyebrow">EXPLAINABLE PROGRAMMING</p><p>Prioridades manuais têm peso elevado. O engine aumenta frequência ou posição na sessão sem inflar séries indefinidamente; pontos fortes recebem manutenção e a distribuição considera recuperação, sobreposição e disponibilidade.</p></section>}</div>}
function Profile({db,redo,openBuilder,openManual,signOut,user}){
  const[visual,setVisual]=useState(false),[file,setFile]=useState(null),[notice,setNotice]=useState(false),[visionResult,setVisionResult]=useState(null);
  const manual=db.program?.logic?.manual;
  const splits=splitOptions(db.profile.days,db.profile.experience);
  const[split,setSplit]=useState(db.program?.logic?.split_id||db.profile.split_preference||splits[0]?.id||"full_body");
  const[method,setMethod]=useState(db.profile.training_method||db.program?.logic?.quality_gate?.method_profile?.id||"balanced_hypertrophy");
  const[savingTraining,setSavingTraining]=useState(false),[trainingNotice,setTrainingNotice]=useState("");
  const saveTraining=async()=>{setSavingTraining(true);setTrainingNotice("");try{const r=await axios.put(`${API}/training/preferences`,{split_preference:split,training_method:method});setTrainingNotice(r.data.manual_program_active?"Preferência salva. Ela será aplicada quando você voltar ao programa automático.":"Método salvo. Recalculando seu programa…");setTimeout(()=>window.location.reload(),650)}catch(e){setTrainingNotice(e?.response?.data?.detail||"Não foi possível salvar agora.")}finally{setSavingTraining(false)}};
  const send=async()=>{const f=new FormData();f.append("profile_id",db.profile.id);f.append("consent","true");f.append("views",JSON.stringify(["frente"]));if(file)f.append("photos",file);try{const r=await fetch(`${API}/visual-assessment`,{method:"POST",body:f,headers:{Authorization:`Bearer ${localStorage.getItem("forge_token")||""}`}});const data=await r.json();setNotice(true);setVisionResult(data)}catch{setNotice(true);setVisionResult(null)}};
  return <div className="content">
    <div className="section-intro"><p className="eyebrow">PERFIL LOCAL</p><h2>{db.profile.name}</h2><p className="muted">{db.profile.experience} · {db.profile.goal} · {db.profile.days} dias por ciclo</p></div>
    <section className="panel profile-panel"><div className="avatar">{(db.profile.name||"AF").split(" ").map(x=>x[0]).slice(0,2).join("")}</div><div><p className="eyebrow">CONFIGURAÇÃO ATUAL</p><h3>{db.profile.session_minutes} min · {manual?"FORGE_PRO (manual)":db.profile.automation_mode||"FORGE_ASSISTED"}</h3><p className="muted">{user?`${user.email} · ${user.plan||"—"} · ${user.status||"—"}`:"Assessment V2 salvo"}</p></div></section>
    <section className="panel training-preferences"data-testid="training-preferences"><div className="panel-top"><div><p className="eyebrow">ARQUITETURA DO TREINO</p><h3>Divisão e método FORGE</h3></div><span className="live-pill"><i/> MOTOR DETERMINÍSTICO</span></div><p className="muted">Você escolhe a preferência; o FORGE limita as opções ao que cabe nos seus dias e na sua recuperação.</p>
      <div className="training-setting"><p className="eyebrow">DIVISÃO · {db.profile.days} DIAS</p><div className="training-option-grid">{splits.map(x=><button type="button"key={x.id}className={split===x.id?"active":""}data-testid={`split-${x.id}`}onClick={()=>setSplit(x.id)}><b>{x.label}</b><small>{x.recommended?"Recomendação FORGE":"Opção compatível"}</small></button>)}</div></div>
      <div className="training-setting"><p className="eyebrow">MÉTODO DE PROGRESSÃO</p><div className="training-option-grid methods">{TRAINING_METHODS.map(x=><button type="button"key={x.id}className={method===x.id?"active":""}data-testid={`method-${x.id}`}onClick={()=>setMethod(x.id)}><b>{x.label}</b><small>{x.description}</small></button>)}</div></div>
      {manual&&<p className="notice">Seu programa manual permanece intocado. Esta preferência vale quando o modo automático for reativado.</p>}{trainingNotice&&<p className="notice"data-testid="training-preferences-notice">{trainingNotice}</p>}<button className="primary-button"data-testid="save-training-preferences"disabled={savingTraining}onClick={saveTraining}>{savingTraining?"Salvando…":"Aplicar divisão e recalcular"}</button>
    </section>
    <section className="panel"><p className="eyebrow">AÇÕES</p><div className="action-row"><button className="secondary-button"data-testid="redo-assessment-button"onClick={redo}>Refazer avaliação</button><button className="secondary-button"data-testid="open-builder-button"onClick={openBuilder}><Sliders size={16}/> {manual?"Editar programa manual":"Program Builder Pro"}</button><button className="secondary-button"data-testid="open-manual-button"onClick={openManual}><FileUp size={16}/> Criar meu próprio treino</button><button className="secondary-button"data-testid="visual-assessment-button"onClick={()=>setVisual(!visual)}><FileUp size={16}/> Analisar meu físico</button>{signOut&&<button className="secondary-button"data-testid="signout-button"onClick={signOut}><LogOut size={16}/> Sair da conta</button>}</div>
      {visual&&<div className="visual-upload"><p className="muted">Análise visual estimada. Pose, luz, ângulo e roupa alteram a interpretação; não mede composição nem diagnostica condições médicas.</p><label className="upload-box"data-testid="photo-upload-label"><FileUp size={20}/>{file?file.name:"Adicionar foto"}<input data-testid="photo-upload-input"type="file"accept="image/*"onChange={e=>setFile(e.target.files[0])}/></label><button className="primary-button"data-testid="submit-visual-assessment"onClick={send}>Enviar com consentimento</button>{notice&&(visionResult?.status==="completed"?<div className="notice"data-testid="visual-result-notice"><b>Análise concluída</b><span className="muted"> · Gemini Vision · {visionResult.suggested_priorities?.length||0} prioridades sugeridas</span><div className="priority-list"style={{marginTop:8}}>{(visionResult.suggested_priorities||[]).map((p,i)=><div key={p}><span>0{i+1}</span>{p}<b>Foco</b></div>)}</div>{visionResult.symmetry_notes&&<p className="muted"style={{marginTop:6,fontSize:11}}>{visionResult.symmetry_notes}</p>}{visionResult.proportion_notes&&<p className="muted"style={{fontSize:11}}>{visionResult.proportion_notes}</p>}{visionResult.limitations?.length>0&&<p className="muted"style={{fontSize:10,marginTop:4}}>Limitações: {visionResult.limitations.join("; ")}</p>}<p className="muted"style={{fontSize:10,marginTop:6}}>A avaliação manual continua válida. O Vision complementa, não substitui.</p></div>:<div className="notice"data-testid="visual-unavailable-notice">{visionResult?.status==="error"?`Erro: ${visionResult.message}`:"Análise visual indisponível. Verifique se GEMINI_API_KEY está configurada."}</div>)}</div>}
    </section>
    <section className="panel"><p className="eyebrow">PRIORIDADES MANUAIS</p><div className="priority-list">{(db.profile.priorities||[]).map((p,i)=><div key={p}><span>0{i+1}</span>{p}<b>Alta</b></div>)}</div></section>
  </div>
}
function Coach({onClose,text,busy,ask}){const[q,setQ]=useState(""),suggestions=["Por que tenho este volume?","Meu peito superior está evoluindo?","Devo aumentar o deltoide lateral?"];return <div className="coach-overlay"><div className="coach-panel"><div className="coach-header"><div><p className="eyebrow">FORGE COACH · CONTEXTO REAL</p><h2>O que você quer entender?</h2></div><button className="icon-button"data-testid="close-coach-button"onClick={onClose}><X size={20}/></button></div><div className="coach-suggestions">{suggestions.map(x=><button key={x}data-testid={`coach-suggestion-${x.slice(0,5)}`}onClick={()=>{setQ(x);ask(x)}}>{x}</button>)}</div><div className="coach-answer">{busy?<div className="loading"><Sparkles size={16}/> Lendo assessment e histórico...</div>:text?<p data-testid="coach-response">{text}</p>:<p className="muted">Pergunte sobre progressão, volume, recovery ou substituição.</p>}</div><form onSubmit={e=>{e.preventDefault();ask(q)}}><input data-testid="coach-question-input"value={q}onChange={e=>setQ(e.target.value)}placeholder="Ex.: Estou estagnado no supino..."/><button data-testid="coach-submit-button"className="primary-button"type="submit"><ChevronRight size={18}/></button></form></div></div>}
function DeepAssessment({onDone,initialForm,passos}){const lista=(passos&&passos.length)?passos:ONBOARDING_STEPS;const[screen,setScreen]=useState(lista[0]),[avisoPrioridade,setAvisoPrioridade]=useState(""),[form,setForm]=useState(()=>({...{profile_id:crypto.randomUUID(),name:"Novo atleta",age:"",sex:"",height_cm:"",weight_kg:"",training_years:"",consistency_years:"",experience:"Intermediário",body_goal:DEFAULT_BODY_GOAL,goal_intensity:"",secondary_goal:"",days:3,session_minutes:60,split:"",split_preference:"",training_method:"balanced_hypertrophy",trains_near_failure:true,uses_rir:true,tracks_loads:true,equipment:["Academia completa"],gym_complete:true,recovery:{sleep_hours:7,stress:3},assessment:{},priorities:[],baseline:[],automation_mode:"FORGE_ASSISTED"},...(initialForm||{})})),[file,setFile]=useState(null);const[goalCatalog,setGoalCatalog]=useState([]);
  useEffect(()=>{let vivo=true;axios.get(`${API}/nutrition/goal-catalog`).then(r=>{if(vivo)setGoalCatalog(r.data.goals||[])}).catch(()=>{});return()=>{vivo=false}},[]);
  const objetivoAtual=goalFromCatalog(goalCatalog,form.body_goal);
  const ritmos=objetivoAtual?.intensities||[];
  // Trocar de objetivo sempre reseta o ritmo para o padrao do novo objetivo — nunca
  // carrega o anterior, senao um cutting agressivo viraria superavit agressivo sozinho.
  const escolherObjetivo=id=>setForm(x=>({...x,body_goal:id,goal_intensity:intensityOnGoalChange(goalCatalog,id)}));
  const set=(k,v)=>setForm(x=>({...x,[k]:v})),setNested=(k,v)=>setForm(x=>({...x,[k]:{...x[k],[k.includes(".")?k.split(".")[1]:k]:v}}));
  // Remover uma regiao reordena sozinho: a posicao vem do indexOf na lista, entao nunca
  // sobra lacuna (prioridade 1 e 3 sem a 2).
  const alternarRegiao=m=>{const r=togglePriority(form.priorities,m);setAvisoPrioridade(r.warning);set("priorities",r.priorities)};
  const treinoEquilibrado=()=>{setAvisoPrioridade("");set("priorities",[])};const back=()=>{const p=anteriorNaLista(lista,screen);if(p)setScreen(p)};const next=()=>{const n=proximoNaLista(lista,screen);if(n)setScreen(n);else onDone({...form,goal:LEGACY_TRAINING_GOAL[form.body_goal]||form.goal,goal_intensity:intensityForSubmit(goalCatalog,form.body_goal,form.goal_intensity),age:Number(form.age)||null,height_cm:Number(form.height_cm)||null,weight_kg:Number(form.weight_kg)||null,training_years:Number(form.training_years)||0,consistency_years:Number(form.consistency_years)||0})};const formRef=useRef(form);formRef.current=form;const Field=useMemo(()=>({label,k,type="text"})=><label className="deep-field"><span>{label}</span><input data-testid={`assessment-${k}`}type={type}value={k.includes(".")?formRef.current[k.split(".")[0]][k.split(".")[1]]:formRef.current[k]}onChange={e=>k.includes(".")?setNested(k,e.target.value):set(k,e.target.value)}/></label>,[]);const step=lista.indexOf(screen)+1,totalSteps=lista.length;return <div className="onboarding deep"><div className="onboard-top"><div className="brand"><span className="brand-mark">F</span><span>FORGE</span></div><span>{step} / {totalSteps}</span></div><div className="onboard-progress"><b style={{width:`${step/totalSteps*100}%`}}/></div><motion.section className="onboard-scene deep-scene"key={screen}initial={{opacity:0,x:12}}animate={{opacity:1,x:0}}>{screen==="profile"&&<><p className="eyebrow">01 / PERFIL DO ATLETA</p><h1>Conheça o atleta antes do treino.</h1><p className="onboard-copy">Uma avaliação esportiva profunda, em cenas curtas.</p><div className="field-grid"><Field label="Nome"k="name"/><Field label="Idade"k="age"type="number"/><Field label="Altura (cm)"k="height_cm"type="number"/><Field label="Peso (kg)"k="weight_kg"type="number"/><Field label="Anos de musculação"k="training_years"type="number"/><Field label="Anos consistentes"k="consistency_years"type="number"/></div><Choice label="Perfil"value={form.sex}options={["Feminino","Masculino"]}onChange={v=>set("sex",v)}/><Choice label="Experiência"value={form.experience}options={["Recreativo","Intermediário","Avançado","Bodybuilder"]}onChange={v=>set("experience",v)}/><div className="choice"><p className="eyebrow">Objetivo</p><div className="mode-grid goal-grid">{goalCatalog.map(g=><button key={g.id}type="button"data-testid={`goal-${g.id}`}aria-pressed={form.body_goal===g.id}className={form.body_goal===g.id?"mode active":"mode"}onClick={()=>escolherObjetivo(g.id)}><b>{g.label}</b><small>{g.description}</small></button>)}</div></div>{ritmos.length>0&&<div className="intensity-block"><p className="eyebrow">{objetivoAtual.intensity_question}</p><div className="intensity-cards">{ritmos.map(op=><button key={op.id}type="button"data-testid={`intensity-${op.id}`}aria-pressed={form.goal_intensity===op.id}className={`intensity-card${form.goal_intensity===op.id?" active":""}${op.advanced?" advanced":""}`}onClick={()=>set("goal_intensity",op.id)}><span className="intensity-head"><b>{op.label}</b>{op.recommended&&<em className="intensity-tag">recomendado</em>}{op.advanced&&<em className="intensity-tag adv">avançado</em>}</span><small>{op.description}</small><span className="intensity-meta">{`${op.delta_pct>0?"+":""}${op.delta_pct}% do gasto`}{op.carb_range_g?` · ${op.carb_range_g[0]}–${op.carb_range_g[1]}g de carboidrato/dia`:""}</span></button>)}</div>{ritmos.find(o=>o.id===form.goal_intensity)?.warning&&<p className="intensity-warning"data-testid="intensity-warning">{ritmos.find(o=>o.id===form.goal_intensity).warning}</p>}</div>}<div className="days-control"><p className="eyebrow">DIAS DISPONÍVEIS / 1 A 7</p><div>{[1,2,3,4,5,6,7].map(n=><button key={n}className={form.days===n?"day active":"day"}data-testid={`days-${n}`}onClick={()=>set("days",n)}>{n}</button>)}</div></div></>}{screen==="history"&&<><p className="eyebrow">02 / HISTÓRICO DE TREINO</p><h1>Como você treinou até aqui?</h1><p className="onboard-copy">Experiência não significa automaticamente mais dias.</p><div className="field-grid"><Field label="Divisão atual"k="split"/><Field label="Duração média (min)"k="session_minutes"type="number"/></div><Choice label="Treina próximo da falha?"value={form.trains_near_failure?"Sim":"Não"}options={["Sim","Não"]}onChange={v=>set("trains_near_failure",v==="Sim")}/><Choice label="Usa RIR?"value={form.uses_rir?"Sim":"Não"}options={["Sim","Não"]}onChange={v=>set("uses_rir",v==="Sim")}/><Choice label="Registra cargas e progressão?"value={form.tracks_loads?"Sim":"Não"}options={["Sim","Não"]}onChange={v=>set("tracks_loads",v==="Sim")}/></>}{screen==="priorities"&&<><p className="eyebrow">03 / REGIÕES PRIORITÁRIAS</p><h1>O que você quer priorizar?</h1><p className="onboard-copy">Escolha até três regiões. A primeira será sua prioridade principal e receberá mais atenção no plano. As demais serão prioridades secundárias.</p><p className="muted"style={{marginTop:10}}>Se você não escolher nenhuma região, o FORGE distribuirá o treino de forma equilibrada.</p><div className="focus-summary"data-testid="priority-summary"><p className="eyebrow">SEU FOCO</p>{form.priorities.length===0?<p className="muted"data-testid="priority-summary-empty">Treino equilibrado — nenhuma região priorizada.</p>:<ol className="focus-list">{form.priorities.map((m,i)=><li key={m}><b>{i+1}</b><span>{m}</span><em>{roleFor(i)}</em></li>)}</ol>}</div>{Object.entries(GROUPS).map(([grupo,itens])=><div key={grupo}className="choice"><p className="eyebrow">{grupo}</p><div className="region-grid">{itens.map(m=>{const pos=form.priorities.indexOf(m),escolhido=pos>=0;return <button key={m}type="button"data-testid={`priority-${m}`}aria-pressed={escolhido}className={escolhido?"region-chip picked":"region-chip"}onClick={()=>alternarRegiao(m)}>{escolhido&&<span className={pos===0?"region-rank":"region-rank sec"}>{pos+1}</span>}<span className="region-name">{m}</span>{escolhido&&<em className="region-role">{RANK_LABEL[pos]}</em>}</button>})}</div></div>)}{avisoPrioridade&&<p className="region-warning"data-testid="priority-limit-warning">{avisoPrioridade}</p>}<button className="secondary-button balanced-button"type="button"data-testid="balanced-training-button"onClick={treinoEquilibrado}>Treino equilibrado — não quero priorizar nenhuma região.</button></>}{screen==="preferences"&&<><p className="eyebrow">04 / PREFERÊNCIAS E RECOVERY</p><h1>O que cabe na sua recuperação?</h1><div className="field-grid"><Field label="Horas de sono"k="recovery.sleep_hours"type="number"/><Field label="Estresse (1–5)"k="recovery.stress"type="number"/></div><Choice label="Academia completa?"value={form.gym_complete?"Sim":"Não"}options={["Sim","Não"]}onChange={v=>{set("gym_complete",v==="Sim");set("equipment",v==="Sim"?["Academia completa"]:[])}}/><Choice label="Modo de automação"value={form.automation_mode}options={form.experience==="Bodybuilder"?["FORGE_ASSISTED","FORGE_PRO","FORGE_AUTO"]:["FORGE_AUTO","FORGE_ASSISTED","FORGE_PRO"]}onChange={v=>set("automation_mode",v)}/></>}{screen==="visual"&&<><p className="eyebrow">05 / VISUAL ASSESSMENT · OPCIONAL</p><h1>Adicionar uma segunda visão?</h1><p className="onboard-copy">A análise visual estimada depende de modelo Vision compatível; nunca diagnostica ou mede com precisão.</p><label className="upload-box"data-testid="assessment-photo-label"><FileUp size={20}/>{file?file.name:"Selecionar fotografia"}<input data-testid="assessment-photo-input"type="file"accept="image/*"onChange={e=>setFile(e.target.files[0])}/></label><p className="muted">Sem modelo Vision, a foto não gera resultados inventados.</p></>}{screen==="confirm"&&<><p className="eyebrow">06 / PROGRAM ASSISTED</p><h1>Seu mapa está pronto para revisão.</h1><p className="onboard-copy">FORGE vai recomendar uma divisão para {form.days} {form.days===1?"dia":"dias"}, sem template fixo.</p><div className="review-summary"><div><b>{form.priorities.length}</b><span>prioridades</span></div><div><b>{form.priorities.length?form.priorities[0]:"Equilibrado"}</b><span>{form.priorities.length?"principal":"distribuição"}</span></div><div><b>{form.automation_mode}</b><span>controle</span></div></div><p className="muted">No modo Assisted, você aprova antes de aplicar.</p></>}</motion.section><div className="deep-actions">{screen!=="profile"&&<button className="secondary-button"type="button"data-testid="assessment-back-button"onClick={back}>Voltar</button>}<button className="secondary-button"data-testid="save-assessment-later-button"onClick={()=>localStorage.setItem("forge_assessment_draft",JSON.stringify(form))}>Salvar e continuar depois</button><button className="primary-button"data-testid="assessment-next-button"onClick={next}>{screen==="confirm"?"Gerar recomendação":"Continuar"}<ChevronRight size={18}/></button></div><p className="onboard-note"><LockKeyhole size={14}/> Perfil novo separado do demo.</p></div>}
function Choice({label,value,options,onChange}){return <div className="choice"><p className="eyebrow">{label}</p><div>{options.map(x=><button key={x}className={value===x?"choice-button selected":"choice-button"}data-testid={`choice-${x.replaceAll(" ","-")}`}onClick={()=>onChange(x)}>{x}</button>)}</div></div>}
function ProgramPreview({program,onApprove,onBack}){const p=program||{};return <div className="onboarding deep-scene"><div className="onboard-scene"><p className="eyebrow">PREVIEW DO PROGRAMA</p><h1>Seu programa FORGE ASSISTED</h1><p className="onboard-copy">{p.name||"Programa adaptativo"} · {p.week||""}</p></div><section className="panel"><div className="panel-top"><div><p className="eyebrow">LÓGICA</p><h3>{p.logic?.split||p.name}</h3></div></div><p className="muted">{p.logic?.days||0} sessões · volume ×{p.logic?.recovery_modifier||1}. Prioridade manual preservada.</p></section>{(p.sessions||[]).map((s,i)=><section className="panel"key={i}><p className="eyebrow">DIA {s.day} · {s.label} · {s.demand}</p><div className="focus-row">{(s.focus||[]).map(f=><span key={f}>{f}</span>)}</div>{(s.exercises||[]).map((x,j)=><div className="muscle-row"key={j}><div><b>{x.exercise_id}</b><p>{x.sets}×{x.reps} RIR {x.rir} · {x.rest}{x.technique_id!=="straight"?` · ${x.technique}`:""}</p></div></div>)}</section>)}<div className="deep-actions"style={{marginTop:28}}><button className="secondary-button"data-testid="preview-back-button"onClick={onBack}>Voltar e ajustar</button><button className="primary-button"data-testid="approve-program-button"onClick={onApprove}><Check size={18}/> Aprovar programa</button></div></div>}
// Rotas publicas: a raiz passa a ser a pagina de venda, e nao um desvio para o login.
// E o unico endereco que precisa ser divulgado.
// /recuperar tem que ser publica: quem esqueceu a senha nao consegue entrar para pedi-la.
const ROTAS_PUBLICAS=["/","","/assinar","/login","/recuperar"];
function Router(){const{user,ready,route,navigate,signIn,signOut,reload}=useAuth();const[planoEscolhido,setPlanoEscolhido]=useState("");
  // Quem ainda nao pagou nao entra no aplicativo. A tela obedece; quem garante e o
  // backend, que devolve 403 em toda rota paga.
  const aguardandoPagamento=Boolean(user)&&user.status==="PENDING_PAYMENT"&&user.role!=="SUPER_ADMIN";
  const voltandoDoCheckout=route.startsWith("/assinatura/retorno");
  useEffect(()=>{if(!ready)return;const inviteMatch=route.match(/^\/invite\/(.+)/);if(inviteMatch)return;if(!user){if(!ROTAS_PUBLICAS.includes(route)&&!route.startsWith("/recuperar/"))navigate("/",true);return}if(aguardandoPagamento){if(route!=="/assinatura"&&!route.startsWith("/assinatura/retorno"))navigate("/assinatura",true);return}if(user.role==="SUPER_ADMIN"&&(route==="/login"||route==="/"||route===""))navigate("/admin",true);if(user.role==="ATHLETE"&&(route==="/login"||route==="/admin"||route==="/"||route===""||route==="/assinar"||route.startsWith("/assinatura")))navigate("/app",true)},[user,ready,route,navigate,aguardandoPagamento]);
  if(!ready)return <div className="auth-shell"><div className="auth-card"><p className="muted">Carregando FORGE...</p></div></div>;
  const inviteMatch=route.match(/^\/invite\/(.+)/);if(inviteMatch)return <InviteScreen token={inviteMatch[1]}/>;
  if(!user){if(route==="/login")return <LoginScreen/>;if(route==="/recuperar"||route.startsWith("/recuperar/"))return <PasswordReset/>;if(route==="/assinar")return <SignupFlow API={API}planoInicial={planoEscolhido}onEntrar={()=>navigate("/login")}onCancelar={()=>navigate("/")}onAutenticar={signIn}/>;return <Landing API={API}onComecar={code=>{setPlanoEscolhido(code);navigate("/assinar")}}onEntrar={()=>navigate("/login")}/>}
  if(aguardandoPagamento)return <PagamentoPendente API={API}user={user}onSair={signOut}retornando={voltandoDoCheckout}onLiberado={reload}/>;
  if(user.role==="SUPER_ADMIN"&&route.startsWith("/admin"))return <AdminPanel/>;return <AthleteShell/>}
function App(){return <AuthProvider><Router/></AuthProvider>}
export default App;
