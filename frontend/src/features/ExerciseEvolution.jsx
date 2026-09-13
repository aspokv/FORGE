import {useEffect,useId,useMemo,useState} from "react";
import axios from "axios";
import {numberBR} from "./AstraUI";
import {exercicioPadrao,opcoesDoSeletor} from "./evolucaoResumo";

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
const dataCurta=date=>date.split("-").reverse().slice(0,2).join("/");

/**
 * A evolucao de um exercicio.
 *
 * A leitura e sempre a da sessao MAIS RECENTE, com a diferenca desde a primeira do periodo
 * logo abaixo — e essa diferenca que responde "estou evoluindo?". Nao ha cursor de sessoes:
 * quem quer o detalhe de um ponto toca nele e le o titulo, e quem nao quer nao paga por um
 * controle a mais na tela.
 */
export default function ExerciseEvolution({API,profileId,exercises=[],records=[],milestones=[]}){
  const uid=useId(),favoriteKey="forge:evolution:favorite:"+profileId;
  const options=useMemo(()=>[...exercises].filter(e=>e.id&&e.name).sort((a,b)=>a.name.localeCompare(b.name,"pt-BR")),[exercises]);
  const [favorite,setFavorite]=useState(()=>{try{return localStorage.getItem(favoriteKey)||"";}catch{return "";}});
  const [chosen,setChosen]=useState(""),[days,setDays]=useState(28),[result,setResult]=useState(null),[retry,setRetry]=useState(0);
  const exerciseId=exercicioPadrao({escolhido:chosen,favorito:favorite,milestones,opcoes:options});
  const {seus,demais}=useMemo(()=>opcoesDoSeletor(options,milestones,records),[options,milestones,records]);
  useEffect(()=>{
    if(!exerciseId)return;
    let live=true;setResult(null);
    axios.get(API+"/exercise-history/"+encodeURIComponent(exerciseId)).then(r=>{if(live)setResult({id:exerciseId,rows:r.data.history||[]});}).catch(()=>{if(live)setResult({id:exerciseId,error:true});});
    return()=>{live=false;};
  },[API,profileId,exerciseId,retry]);
  const ready=result?.id===exerciseId;
  const points=evolutionPoints(ready?result.rows||[]:[],days);
  const atual=points.at(-1),primeiro=points[0];
  const variacao=atual&&primeiro&&points.length>1?Math.round((atual.weight-primeiro.weight)*10)/10:0;
  const values=points.map(p=>p.weight),low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,1);
  // O desenho comeca em x=48: os rotulos de carga ficam ANTES dele, fora da area da linha.
  // Antes eles eram escritos em x=24, o mesmo ponto onde a linha nasce, e a linha os riscava.
  const x=i=>points.length===1?180:48+(points[i].time-primeiro.time)/Math.max(1,atual.time-primeiro.time)*252;
  const y=w=>112-(w-low+span*.18)/(span*1.36)*88;
  const line=points.map((p,i)=>(i?"L":"M")+x(i)+" "+y(p.weight)).join(" ");
  const toggleFavorite=()=>{const next=favorite===exerciseId?"":exerciseId;setFavorite(next);try{localStorage.setItem(favoriteKey,next);}catch{}};
  const lista=(rotulo,itens)=>itens.length?<optgroup label={rotulo}>{itens.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</optgroup>:null;
  return <section className="a6-panel evolution-card" data-testid="progress-hero" aria-label="Evolução por exercício">
    <div className="evolution-heading"><h2>Um exercício de cada vez</h2><button type="button" aria-label="Favoritar exercício" aria-pressed={favorite===exerciseId&&!!exerciseId} disabled={!exerciseId} onClick={toggleFavorite}>{favorite===exerciseId?"★":"☆"}</button></div>
    <label className="evolution-select" htmlFor={uid+"exercise"}>Exercício
      <select id={uid+"exercise"} value={exerciseId} onChange={e=>setChosen(e.target.value)}>
        {seus.length?<>{lista("Seus exercícios",seus)}{lista("Catálogo",demais)}</>:options.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
      </select>
    </label>
    <div className="evolution-periods" role="group" aria-label="Período do histórico">{[[28,"4 semanas"],[84,"12 semanas"],[0,"Disponível"]].map(([value,label])=><button type="button" key={value} aria-pressed={days===value} onClick={()=>setDays(value)}>{label}</button>)}</div>
    {!exerciseId?<p>Seu catálogo de exercícios ainda não está disponível.</p>:!ready?<p role="status">Carregando histórico…</p>:result.error?<div role="alert"><p>Não foi possível carregar o histórico.</p><button type="button" onClick={()=>setRetry(v=>v+1)}>Tentar novamente</button></div>:!atual?<p className="evolution-empty">Sem séries registradas neste período. Escolha outro exercício ou período.</p>:<>
      <div className="evolution-reading" aria-live="polite">
        <strong>{numberBR(atual.weight)} <small>kg</small></strong>
        {/* A variacao e a resposta; a leitura de hoje sozinha nao diz se subiu. */}
        {variacao>0?<em className="evolution-alta" data-testid="evolution-variacao">+{numberBR(variacao)} kg desde {dataCurta(primeiro.date)}</em>
          :variacao<0?<em className="evolution-queda" data-testid="evolution-variacao">{numberBR(variacao)} kg desde {dataCurta(primeiro.date)}</em>
          :<em data-testid="evolution-variacao">{points.length>1?"Mesma carga do início do período":"Primeiro registro do período"}</em>}
        <span>{atual.reps} repetições na melhor série · {dateLabel(atual.date)}</span>
      </div>
      {points.length>1&&<svg className="evolution-chart" viewBox="0 0 320 140" role="img" aria-label={`Carga por sessão: ${points.map(p=>`${dateLabel(p.date)} ${numberBR(p.weight)} kg`).join(", ")}`}>
        {[high,low].map(v=><g key={v}><line x1="48" x2="308" y1={y(v)} y2={y(v)} stroke="#ffffff10"/><text x="40" y={y(v)+4} textAnchor="end">{numberBR(v)}</text></g>)}
        <path d={line} fill="none" stroke="#ffb77d" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        {points.map((p,i)=><circle key={p.key} cx={x(i)} cy={y(p.weight)} r={i===points.length-1?5:3} fill={i===points.length-1?"#ffe2bc":"#a8764f"}><title>{dateLabel(p.date)}: {numberBR(p.weight)} kg × {p.reps}</title></circle>)}
        <text x="48" y="134">{dataCurta(primeiro.date)}</text><text x="308" y="134" textAnchor="end">{dataCurta(atual.date)}</text>
      </svg>}
      {points.length===1&&<p className="evolution-note">Seu histórico cresce a cada sessão registrada.</p>}
    </>}
  </section>;
}
