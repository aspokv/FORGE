import {useEffect,useId,useMemo,useState} from "react";
import axios from "axios";
import {numberBR} from "./AstraUI";

export function evolutionPoints(rows=[],days=28,now=Date.now()){
  const groups=new Map(), cutoff=days?now-days*86400000:-Infinity;
  for(const row of rows){
    const time=Date.parse(row.created_at),weight=Number(row.weight),reps=Number(row.reps);
    if(!Number.isFinite(time)||time<cutoff||time>now||!Number.isFinite(weight)||weight<0||!Number.isFinite(reps)||reps<=0)continue;
    const date=row.created_at.slice(0,10),key=row.session_id||date;
    let p=groups.get(key);
    if(!p){p={key,date,time,weight,reps,sets:0};groups.set(key,p);}
    p.sets++;
    if(weight>p.weight||(weight===p.weight&&reps>p.reps)){p.weight=weight;p.reps=reps;}
    p.time=Math.min(p.time,time);
  }
  return [...groups.values()].sort((a,b)=>a.time-b.time);
}
const dateLabel=date=>date.split("-").reverse().join("/");
export default function ExerciseEvolution({API,profileId,exercises=[],records=[]}){
  const uid=useId(),favoriteKey="forge:evolution:favorite:"+profileId;
  const options=useMemo(()=>[...exercises].filter(e=>e.id&&e.name).sort((a,b)=>a.name.localeCompare(b.name,"pt-BR")),[exercises]);
  const [favorite,setFavorite]=useState(()=>{try{return localStorage.getItem(favoriteKey)||"";}catch{return "";}});
  const [chosen,setChosen]=useState(""),[days,setDays]=useState(28),[result,setResult]=useState(null),[retry,setRetry]=useState(0),[selected,setSelected]=useState(null);
  const exerciseId=options.find(e=>e.id===chosen)?.id||options.find(e=>e.id===favorite)?.id||options.find(e=>records.some(r=>r.exercise===e.name))?.id||options[0]?.id||"";
  useEffect(()=>{
    if(!exerciseId)return;
    let live=true;setResult(null);setSelected(null);
    axios.get(API+"/exercise-history/"+encodeURIComponent(exerciseId)).then(r=>{if(live)setResult({id:exerciseId,rows:r.data.history||[]});}).catch(()=>{if(live)setResult({id:exerciseId,error:true});});
    return()=>{live=false;};
  },[API,profileId,exerciseId,retry]);
  const ready=result?.id===exerciseId;
  const points=evolutionPoints(ready?result.rows||[]:[],days);
  const index=selected==null?points.length-1:Math.min(selected,points.length-1),point=points[index];
  const values=points.map(p=>p.weight),low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,1);
  const x=i=>points.length===1?160:24+(points[i].time-points[0].time)/Math.max(1,points.at(-1).time-points[0].time)*272;
  const y=w=>120-(w-low+span*.15)/(span*1.3)*96;
  const line=points.map((p,i)=>(i?"L":"M")+x(i)+" "+y(p.weight)).join(" ");
  const toggleFavorite=()=>{const next=favorite===exerciseId?"":exerciseId;setFavorite(next);try{localStorage.setItem(favoriteKey,next);}catch{}};
  return <section className="a6-panel evolution-card" data-testid="progress-hero" aria-label="Sua evolução por exercício">
    <div className="evolution-heading"><h2>Sua evolução</h2><button type="button" aria-label="Favoritar exercício" aria-pressed={favorite===exerciseId&&!!exerciseId} disabled={!exerciseId} onClick={toggleFavorite}>{favorite===exerciseId?"★":"☆"}</button></div>
    <label className="evolution-select" htmlFor={uid+"exercise"}>Exercício
      <select id={uid+"exercise"} value={exerciseId} onChange={e=>{setChosen(e.target.value);setSelected(null);}}>{options.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>
    </label>
    <div className="evolution-periods" role="group" aria-label="Período do histórico">{[[28,"4 semanas"],[84,"12 semanas"],[0,"Disponível"]].map(([value,label])=><button type="button" key={value} aria-pressed={days===value} onClick={()=>{setDays(value);setSelected(null);}}>{label}</button>)}</div>
    {!exerciseId?<p>Seu catálogo de exercícios ainda não está disponível.</p>:!ready?<p role="status">Carregando histórico…</p>:result.error?<div role="alert"><p>Não foi possível carregar o histórico.</p><button type="button" onClick={()=>setRetry(v=>v+1)}>Tentar novamente</button></div>:!point?<p className="evolution-empty">Sem séries registradas neste período. Escolha outro exercício ou período.</p>:<>
      <div className="evolution-reading" aria-live="polite"><strong>{numberBR(point.weight)} <small>kg</small></strong><span>{point.reps} repetições na série de maior carga<br/>{point.sets} séries registradas · {dateLabel(point.date)}</span></div>
      <svg className="evolution-chart" viewBox="0 0 320 152" role="group" aria-label="Histórico de cargas por sessão">
        {[low,low+span/2,low+span].map((v,i)=><g key={i}><line x1="24" x2="296" y1={y(v)} y2={y(v)} stroke="#ffffff14"/><text x="24" y={y(v)-5}>{numberBR(v)} kg</text></g>)}
        <path d={line} fill="none" stroke="#ffb77d" strokeWidth="2.5"/>
        {points.map((p,i)=><g key={p.key}><circle cx={x(i)} cy={y(p.weight)} r={i===index?6:3} fill={i===index?"#ffe2bc":"#bd8962"}/><circle cx={x(i)} cy={y(p.weight)} r="12" fill="transparent" onClick={()=>setSelected(i)}><title>{dateLabel(p.date)}: {numberBR(p.weight)} kg × {p.reps}</title></circle></g>)}
        <text x="24" y="148">{dateLabel(points[0].date)}</text>{points.length>1&&<text x="296" y="148" textAnchor="end">{dateLabel(points.at(-1).date)}</text>}
      </svg>
      {points.length>1?<label className="evolution-scrubber">Explorar sessões<input aria-label="Sessão no gráfico" type="range" min="0" max={points.length-1} value={index} onChange={e=>setSelected(Number(e.target.value))}/></label>:<p>Primeiro registro. O histórico cresce com suas próximas sessões.</p>}
      <p className="evolution-note">Maior carga registrada em cada sessão, com repetições para dar contexto. Até 200 séries recentes.</p>
    </>}
  </section>;
}
