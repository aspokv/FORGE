import {useId,useState} from "react";
import ExerciseEvolution from "./ExerciseEvolution";
import {AstraPage,AstraIntro,numberBR} from "./AstraUI";

export function AstraChart({points,unit="kg"}) {
  const id=useId();
  if(points.length<2)return <p className="a6-chart-empty">O gráfico aparece após dois registros válidos.</p>;
  const vals=points.map(p=>Number(p.value)),lo=Math.min(...vals),hi=Math.max(...vals);
  const span=Math.max(hi-lo,1),min=lo-span*.2,max=hi+span*.2;
  const x=i=>38+i*264/(points.length-1),y=v=>130-(v-min)/(max-min)*100;
  const line=points.map((p,i)=>`${i?"L":"M"}${x(i)} ${y(p.value)}`).join(" ");
  return <svg className="a6-line-chart" viewBox="0 0 320 166" role="img" aria-label={points.map(p=>`${p.label}: ${numberBR(p.value)} ${unit}`).join(", ")}>
    <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#FF8A42" stopOpacity=".19"/><stop offset="1" stopColor="#FF8A42" stopOpacity="0"/></linearGradient></defs>
    {[min,(min+max)/2,max].map(v=><g key={v}><line x1="26" x2="310" y1={y(v)} y2={y(v)} stroke="#313534" strokeWidth=".7"/><text x="0" y={y(v)+4}>{numberBR(v)}</text></g>)}<text x="28" y="12">{unit}</text>
    <path d={`M38 138 ${line.replace(/^M/,"L")} L302 138Z`} fill={`url(#${id})`}/><path d={line} fill="none" stroke="#FFB77D" strokeWidth="2.5"/>
    {points.map((p,i)=><g key={`${p.label}-${i}`}><circle cx={x(i)} cy={y(p.value)} r="3.8" fill="#FFD6AE"/><text x={x(i)} y={y(p.value)-11} textAnchor="middle" style={{fill:"#f7ddc5",fontSize:10}}>{numberBR(p.value)}</text><text x={x(i)} y="157" textAnchor="middle">{p.label}</text></g>)}
  </svg>;
}
export default function AstraProgress({analytics,weightPanel,photosPanel,details,API,profileId,exercises}) {
  const [tab,setTab]=useState("load");
  const records=(analytics?.prs||[]).filter(x=>Number(x.weight)>0);
  const calendar=analytics?.adherence_calendar||[],trained=calendar.filter(x=>x.trained).length;
  return <AstraPage screen={3} testId="astra-progress">
    <AstraIntro eyebrow="CADA SESSÃO CONTA" title="Evolução." subtitle="Seu histórico, sessão por sessão."/>
    <div className="a6-tabs" role="group" aria-label="Métrica de evolução">{[["load","Desempenho"],["weight","Peso"],["photos","Fotos"]].map(([key,label])=><button type="button" key={key} aria-pressed={key===tab} className={key===tab?"a6-selected":""} onClick={()=>setTab(key)}>{label}</button>)}</div>
    {!analytics?<p role="status">Carregando analytics…</p>:tab==="load"?<>
      <ExerciseEvolution key={profileId} API={API} profileId={profileId} exercises={exercises} records={records}/>
      <div className="a6-section-title"><h2>Suas melhores marcas</h2></div>
      <div className="a6-pr-grid">{records.slice(0,2).map(p=><div className="a6-panel a6-pr" key={p.exercise}><p>{p.exercise}</p><strong>{numberBR(p.weight)} <small>kg</small></strong><div className="a6-delta">{p.delta_weight>0?`+${numberBR(p.delta_weight)} kg desde o início`:"Melhor série registrada"}</div></div>)}</div>
      {!records.length&&<p data-testid="prs-empty-state">Complete séries com carga para ver suas marcas.</p>}
      <div className="a6-section-title"><h2>Consistência</h2><small style={{color:"var(--done)"}}>{trained} dias com treino / 28 dias</small></div>
      <div className="a6-adherence" aria-label={`${trained} dias com treino registrado`}>{calendar.map(x=><span key={x.date} title={`${x.date}${x.trained?": treino registrado":""}`} className={`a6-tick ${x.trained?"a6-ok":""}`}/>)}</div>
      <div className="a6-week-labels">{[0,1,2,3].map(i=><span key={i}>S{i+1} · {calendar.slice(i*7,i*7+7).filter(x=>x.trained).length}</span>)}</div>
      <details className="a6-details"><summary>Mais detalhes da evolução</summary><div className="a6-editor">{details}</div></details>
    </>:tab==="weight"?<div className="a6-editor">{weightPanel}<AstraChart points={(analytics.body_trend||[]).slice(-4).filter(x=>Number(x.weight)>0).map(x=>({label:x.date,value:Number(x.weight)}))}/></div>:<div className="a6-editor">{photosPanel}</div>}
  </AstraPage>;
}
