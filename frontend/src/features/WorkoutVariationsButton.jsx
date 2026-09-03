import {useEffect,useState} from "react";
import axios from "axios";
import {BookOpen,ChevronRight,LockKeyhole} from "lucide-react";

export function sessionCategory(session,program={}) {
  const name=String(session?.label||program.session||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  for(const key of ["full body","upper","lower","pull","push","legs"]){
    if(name.includes(key))return key.replace(" ","_");
  }
  const focus=[name,...(session?.focus||program.focus||[])].join(" ").toLowerCase();
  if(/perna|quadr[ií]ceps|gl[uú]te|posterior de coxa/.test(focus))return "legs";
  if(/costas|dorsa|b[ií]ceps/.test(focus))return "pull";
  if(/peito|peitoral|tr[ií]ceps/.test(focus))return "push";
  return "full_body";
}

export default function WorkoutVariationsButton({onOpen}) {
  const [access,setAccess]=useState(null),[error,setError]=useState(false),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setError(false);
    axios.get(`${process.env.REACT_APP_BACKEND_URL||""}/api/billing/me`,{signal:controller.signal})
      .then(r=>{if(!controller.signal.aborted)setAccess(r.data.capabilities?.includes("workout_variations")===true)})
      .catch(()=>{if(!controller.signal.aborted)setError(true)});
    return()=>controller.abort();
  },[attempt]);
  return <button type="button" className="workout-variations-button" data-testid="workout-variations" disabled={!error&&access!==true} onClick={()=>error?setAttempt(v=>v+1):onOpen()}>
    {access?<BookOpen size={18}/>:<LockKeyhole size={17}/>}
    <span><strong>{error?"Tentar carregar biblioteca":access===null?"Verificando acesso…":"Escolher outra variação"}</strong><small>{access?"Biblioteca · substituir o treino atual":"Recurso FORGE Pro e Elite"}</small></span>
    <ChevronRight size={17}/>
  </button>;
}
