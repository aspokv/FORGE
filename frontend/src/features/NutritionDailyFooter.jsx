import {useEffect,useState} from "react";
import axios from "axios";
import {Droplets,ChartNoAxesCombined} from "lucide-react";
import {localFoodDate} from "./foodDiary";

export default function NutritionDailyFooter({API,consumed,goalCalories}) {
  const [water,setWater]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setError("");
    axios.get(`${API}/hydration/${localFoodDate()}`,{signal:controller.signal}).then(r=>{if(!controller.signal.aborted)setWater(r.data)}).catch(()=>{if(!controller.signal.aborted)setError("Não foi possível carregar a hidratação.")});
    return()=>controller.abort();
  },[API,attempt]);
  const update=async amount=>{
    if(busy)return;
    setBusy(true);setError("");
    try {
      const url=`${API}/hydration/${localFoodDate()}`;
      const r=amount===null?await axios.delete(`${url}/last`):await axios.post(url,{amount_ml:amount});
      setWater(r.data);
    }catch{setError("Não foi possível confirmar a atualização. Confira o total antes de repetir.")}
    finally{setBusy(false)}
  };
  const total=Number(water?.total_ml||0),goal=Number(water?.goal_ml||0);
  const remaining=Math.round(Number(goalCalories||0)-consumed.kcal);
  const liters=ml=>(ml/1000).toLocaleString("pt-BR",{maximumFractionDigits:2});
  return <section className="nutrition-daily-footer" aria-label="Resumo do dia">
    <article><header><Droplets size={19}/><h3>Hidratação de hoje</h3></header>
      {water?<><strong>{liters(total)} L <small>{goal>0?`/ ${liters(goal)} L`:"registrados"}</small></strong>{goal>0&&<progress aria-label="Meta de hidratação" max={goal} value={Math.min(total,goal)}/>}<p>{goal>0?(total>=goal?"Meta de água atingida.":`Faltam ${liters(goal-total)} L para sua meta.`):"Sua meta ainda não foi definida."}</p><div className="daily-water-actions"><button disabled={busy} onClick={()=>update(250)}>+250 ml</button><button disabled={busy} onClick={()=>update(500)}>+500 ml</button><button disabled={busy||total===0} onClick={()=>update(null)}>Desfazer</button></div></>:!error&&<p role="status">Carregando hidratação…</p>}
      {error&&<div role="alert"><p>{error}</p><button disabled={busy} onClick={()=>setAttempt(v=>v+1)}>Atualizar total</button></div>}
    </article>
    <article><header><ChartNoAxesCombined size={19}/><h3>Seu consumo hoje</h3></header><strong>{Math.round(consumed.kcal).toLocaleString("pt-BR")} <small>kcal registradas</small></strong><p>{goalCalories>0?(remaining>=0?`${remaining.toLocaleString("pt-BR")} kcal restantes para a meta.`:`${Math.abs(remaining).toLocaleString("pt-BR")} kcal acima da meta.`):"Registre suas refeições para acompanhar o dia."}</p><div className="daily-macro-summary"><span>Proteínas<b>{Math.round(consumed.protein_g)} g</b></span><span>Carboidratos<b>{Math.round(consumed.carbs_g)} g</b></span><span>Gorduras<b>{Math.round(consumed.fat_g)} g</b></span></div><small>Inclui refeições registradas e extras, sem alterar seu plano.</small></article>
  </section>;
}
