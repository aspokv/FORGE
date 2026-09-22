import {useEffect,useState} from 'react';
import axios from 'axios';
import ForgeDialog from './ForgeDialog';
import './meal-food-editor.css';

export default function MealFoodEditor({API,meal,mealIndex,onSaved,onClose}) {
  const [foodIndex,setFoodIndex]=useState(0),[query,setQuery]=useState('');
  const [options,setOptions]=useState([]),[selected,setSelected]=useState(null);
  const [status,setStatus]=useState('idle'),[error,setError]=useState(''),[attempt,setAttempt]=useState(0);
  const [saving,setSaving]=useState(false);
  const item=meal.foods?.[foodIndex];
  useEffect(()=>{
    setOptions([]);setSelected(null);setError('');
    if(!item||query.trim().length<2){setStatus('idle');return;}
    const controller=new AbortController();setStatus('loading');
    const timer=setTimeout(()=>{
      axios.post(`${API}/nutrition/substitute`,{meal_index:mealIndex,food_id:item.food_id,food_index:foodIndex,search:query.trim()},{signal:controller.signal})
        .then(r=>{if(!controller.signal.aborted){setOptions(r.data.options||[]);setStatus('ready');}})
        .catch(e=>{if(!controller.signal.aborted){setStatus('error');setError([402,403].includes(e.response?.status)?'A busca de alimentos no plano é exclusiva do Elite.':'Não foi possível buscar os alimentos. Tente novamente.');}});
    },250);
    return()=>{clearTimeout(timer);controller.abort();};
  },[API,mealIndex,item,foodIndex,query,attempt]);
  const save=async()=>{
    if(saving||!selected||!item)return;
    setSaving(true);setError('');
    try {
      const r=await axios.post(`${API}/nutrition/substitute`,{meal_index:mealIndex,food_id:item.food_id,food_index:foodIndex,substitute_food_id:selected.food_id,search:''});
      if(!r.data?.applied||!Array.isArray(r.data.plan?.meals))throw new Error('Invalid saved plan');
      onSaved(r.data.plan);onClose();
    } catch(e) {
      const detail=e.response?.data?.detail;
      setError(typeof detail==='string'?detail:typeof detail?.message==='string'?detail.message:'Não foi possível salvar. Sua escolha continua aqui; tente novamente.');
    } finally {setSaving(false);}
  };
  return <ForgeDialog open onOpenChange={open=>{if(!open)onClose();}} busy={saving} title={`Editar alimentos · ${meal.name}`} description="Escolha um alimento para substituir. A troca será salva no plano e continuará nos próximos dias." testId="meal-food-editor">
    <div className="meal-food-editor">
      <label>Alimento atual<select value={foodIndex} disabled={saving} onChange={e=>{setFoodIndex(Number(e.target.value));setQuery('');setSelected(null);}}>
        {(meal.foods||[]).map((food,index)=><option key={`${food.food_id}-${index}`} value={index}>{food.food?.name||food.food_id}</option>)}
      </select></label>
      <label>Buscar alimento<input type="search" value={query} disabled={saving||!item} maxLength={120} placeholder="Digite o nome do alimento" onChange={e=>{setQuery(e.target.value);setSelected(null);}} autoComplete="off"/></label>
      {!item?<p>Nenhum alimento cadastrado nesta refeição.</p>:status==='idle'?<p>Digite pelo menos duas letras. A busca mostra as opções permitidas para esta refeição.</p>:null}
      {status==='loading'&&<p role="status">Buscando alimentos…</p>}
      {status==='ready'&&!options.length&&<p role="status">Nenhuma opção compatível encontrada. Tente outro nome.</p>}
      {error&&<p role="alert">{error}</p>}
      {status==='error'&&<button className="fg-btn fg-btn-2" type="button" onClick={()=>setAttempt(n=>n+1)}>Tentar novamente</button>}
      {!!options.length&&<fieldset disabled={saving}><legend>Escolha a substituição</legend>{options.map(option=><label className="meal-food-option" key={option.food_id}>
        <input type="radio" name="replacement-food" value={option.food_id} checked={selected?.food_id===option.food_id} onChange={()=>setSelected(option)}/><span>{option.food?.name||option.food_id}</span>
      </label>)}</fieldset>}
      <button className="fg-btn fg-btn-cheio" type="button" disabled={saving||!selected||status!=='ready'} aria-busy={saving} onClick={save}>{saving?'Salvando…':'Salvar troca no plano'}</button>
      <button className="fg-btn fg-btn-2" type="button" disabled={saving} onClick={onClose}>Cancelar</button>
    </div>
  </ForgeDialog>;
}
