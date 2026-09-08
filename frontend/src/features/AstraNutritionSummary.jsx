import {useId} from "react";
import {numberBR} from "./AstraUI";

export default function AstraNutritionSummary({consumed,targets}) {
  const id=useId(),goal=Number(targets.goal_calories||targets.kcal||0),pct=goal>0?consumed.kcal/goal*100:0;
  const remaining=Math.round(goal-consumed.kcal);
  return <section className="a6-panel a6-gauge-panel">
    <div className="a6-gauge"><svg viewBox="0 0 252 215" role="img" aria-label={`${numberBR(consumed.kcal)} de ${numberBR(goal)} quilocalorias`}><defs><linearGradient id={id}><stop stopColor="#DD6130"/><stop offset="1" stopColor="#FFB568"/></linearGradient></defs><path d="M 56 185 A 94 94 0 1 1 196 185" fill="none" stroke="#282b2b" strokeWidth="10" strokeLinecap="round" pathLength="100"/><path d="M 56 185 A 94 94 0 1 1 196 185" fill="none" stroke={`url(#${id})`} strokeWidth="10" strokeLinecap="round" pathLength="100" strokeDasharray={`${Math.min(100,Math.max(0,pct))} 100`}/></svg>
      <div className="a6-gauge-percent">{goal>0?`${Math.round(pct)}%`:"—"}<small>da meta</small></div>
      <div className="a6-gauge-label"><div className="a6-eyebrow">CONSUMIDO HOJE</div><strong>{numberBR(Math.round(consumed.kcal))}</strong><p>kcal</p><p style={{marginTop:9}}>{goal>0?<>{numberBR(Math.abs(remaining))} kcal {remaining>=0?"restantes":"acima da meta"}<br/>de {numberBR(goal)}</>:"Meta não definida"}</p></div>
    </div>
    <div className="a6-macros">{[["","Proteína","protein_g"],["a6-carb","Carbo","carbs_g"],["a6-fat","Gordura","fat_g"]].map(([cls,label,key])=>{const v=Number(consumed[key]||0),g=Number(targets[key]||0);return <div className={`a6-macro ${cls}`} key={key}><p>{label}</p><strong>{numberBR(Math.round(v))}<small> g</small></strong><div className="a6-goal">de {numberBR(g)} g</div><div className="a6-bar"><span style={{width:`${g?Math.min(100,Math.max(0,v/g*100)):0}%`}}/></div></div>})}</div>
  </section>;
}
