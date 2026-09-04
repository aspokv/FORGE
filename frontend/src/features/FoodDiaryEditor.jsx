import {useEffect,useState} from "react";
import axios from "axios";
import {localFoodDate} from "./foodDiary";
import "./food-diary.css";

const clean=s=>String(s||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
export const matchesFoodQuery=(food,query)=>{
  const terms=clean(query).split(/\s+/).filter(Boolean);
  if(!terms.length)return true;
  const text=clean([food.name,...(food.aliases||[])].join(" "));
  return terms.every(term=>text.includes(term));
};
export default function FoodDiaryEditor({API,mealIndex,mealName,onSaved,onClose}) {
  const [catalog,setCatalog]=useState([]),[query,setQuery]=useState(""),[items,setItems]=useState([]);
  const [error,setError]=useState(""),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true);
  const [entryId]=useState(()=>crypto.randomUUID());
  const [date]=useState(localFoodDate);
  useEffect(()=>{
    const c=new AbortController();
    axios.get(`${API}/nutrition/consumed-foods`,{signal:c.signal}).then(r=>setCatalog(r.data.foods||[])).catch(()=>{if(!c.signal.aborted)setError("Não foi possível carregar o catálogo. Feche e tente novamente.")}).finally(()=>{if(!c.signal.aborted)setLoading(false)});
    return()=>c.abort();
  },[API]);
  const results=catalog.filter(f=>matchesFoodQuery(f,query)).slice(0,12);
  const totals=items.reduce((sum,item)=>{["kcal","protein_g","carbs_g","fat_g"].forEach(k=>sum[k]+=Number(item[k]||0)*Number(item.amount||0)/Number(item.grams||100));return sum},{kcal:0,protein_g:0,carbs_g:0,fat_g:0});
  const save=async()=>{
    if(busy||!items.length)return;
    setBusy(true);setError("");
    try {
      await axios.post(`${API}/nutrition/consumed-meal`,{date,meal_index:mealIndex,entry_id:entryId,foods:items.map(f=>({food_id:f.id,grams:Number(f.amount)}))});
      await onSaved();
      onClose();
    } catch {setError("Não foi possível confirmar o registro. Tente salvar novamente; o mesmo registro não será duplicado.");}
    finally {setBusy(false);}
  };
  return <section className="food-diary-editor" aria-label="Registrar o que comi">
    <h3>{mealIndex==null?"Adicionar um extra":`O que você comeu no ${mealName}?`}</h3>
    <p>{mealIndex==null?"Soma ao consumo de hoje, sem substituir refeições.":"Substitui apenas a contagem desta refeição hoje. Sua dieta original não muda."}</p>
    <p>Informe gramas da parte comestível, sem osso. Confira se o alimento está cru ou preparado e registre óleo/molhos à parte. Valores estimados.</p>
    <label>Buscar alimento<input autoFocus value={query} onChange={e=>setQuery(e.target.value)} placeholder="Feijão, costela, alface…" disabled={busy}/></label>
    {loading?<p role="status">Carregando catálogo…</p>:<div className="food-diary-results">{results.map(f=><button key={f.id} type="button" disabled={busy||items.length>=40} onClick={()=>setItems(v=>[...v,{...f,amount:100}])}>{f.name}<small>{f.kcal} kcal / {f.grams||100} g</small></button>)}{!results.length&&<p>Alimento não encontrado. Tente buscar os ingredientes separadamente.</p>}</div>}
    {items.map((f,i)=><div className="food-diary-item" key={`${f.id}-${i}`}><div><strong>{f.name}</strong><small>{f.source||"Catálogo FORGE"}</small></div><label>Gramas<input aria-label={`Gramas de ${f.name} ${i+1}`} type="number" min="1" max="5000" step="any" value={f.amount} disabled={busy} onChange={e=>setItems(v=>v.map((x,j)=>i===j?{...x,amount:e.target.value}:x))}/></label><button type="button" disabled={busy} onClick={()=>setItems(v=>v.filter((_,j)=>j!==i))}>Remover</button></div>)}
    <p aria-live="polite">{Math.round(totals.kcal)} kcal · P {Math.round(totals.protein_g)} g · C {Math.round(totals.carbs_g)} g · G {Math.round(totals.fat_g)} g</p>
    {error&&<p role="alert">{error}</p>}
    <div className="action-row"><button type="button" className="primary-button" onClick={save} disabled={busy||!items.length||items.some(f=>!Number.isFinite(Number(f.amount))||Number(f.amount)<=0||Number(f.amount)>5000)}>{busy?"Salvando…":"Salvar consumo"}</button><button type="button" className="secondary-button" disabled={busy} onClick={onClose}>Cancelar</button></div>
  </section>;
}
