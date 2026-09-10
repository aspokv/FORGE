import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {completionStorageKey} from "./completeWorkout";
const dateKeyFor=date=>{if(!(date instanceof Date)||Number.isNaN(date.getTime()))return "";const p=n=>String(n).padStart(2,"0");return `${date.getFullYear()}-${p(date.getMonth()+1)}-${p(date.getDate())}`};

export function completionForToday(completion,now=new Date()){
  if(!completion?.completed_at)return null;
  const when=new Date(completion.completed_at);
  return dateKeyFor(when)&&dateKeyFor(when)===dateKeyFor(now)?completion:null;
}

export function inferredCompletionForToday(program={},recentSets=[],now=new Date()){
  const sessions=program.sessions||[],activeDay=Number(program.active_day);
  if(!sessions.length||!Number.isFinite(activeDay))return null;
  const today=dateKeyFor(now);
  const rows=(recentSets||[]).filter(row=>{
    if(row?.session_day==null)return false;
    const when=new Date(row.created_at),day=Number(row.session_day);
    return Number.isFinite(day)&&dateKeyFor(when)===today;
  }).sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime());
  if(!rows.length)return null;
  const loggedDay=Number(rows[0].session_day),session=sessions.find(item=>Number(item.day)===loggedDay);
  if(!session)return null;
  const plannedSets=(session.exercises||[]).reduce((sum,item)=>sum+Number(item.sets||0),0);
  const loggedSets=new Set(rows.filter(row=>Number(row.session_day)===loggedDay).map(row=>`${row.exercise_id||""}:${row.set_number??""}`)).size;
  if(loggedDay===activeDay&&(!plannedSets||loggedSets<plannedSets))return null;
  return {day:loggedDay,label:session.label||null,completed_at:rows[0].created_at,inferred:true};
}

export function sessionStatus(checkin,recentSets=[],now=new Date(),completion=null){
  if(completionForToday(completion,now))return "TREINO CONCLUÍDO HOJE";
  if(checkin)return "RECUPERAÇÃO REGISTRADA";
  const cutoff=now.getTime()-7*24*60*60*1000;
  return recentSets.some(row=>{const time=new Date(row.created_at).getTime();return time>=cutoff&&time<=now.getTime()})?"RITMO ATIVO":"PRONTO PARA INICIAR";
}

export function storedCompletion(userId,now,program,recentSets){
  if(typeof window!=="undefined"&&userId){
    try{
      const raw=window.localStorage.getItem(completionStorageKey(userId));
      const saved=raw?completionForToday(JSON.parse(raw),now):null;
      if(saved)return saved;
    }catch{/* cache local corrompido nao pode quebrar a Home */}
  }
  return inferredCompletionForToday(program,recentSets,now);
}


export function nextSessionAfter(program={},completion){
 // Only the authenticated completion endpoint can confirm the next session.
 return completion?.next_session_status==="confirmed"?completion.next_session||null:null;
}
export function useWorkoutCompletion({userId,program,recentSets,API}){
 const context=useMemo(()=>({active_day:program?.active_day,sessions:program?.sessions}),[program?.active_day,program?.sessions]);
 const [record,setRecord]=useState(()=>storedCompletion(userId,new Date(),context,recentSets));
 const [status,setStatus]=useState("loading");
 const [tick,setTick]=useState(0);
 useEffect(()=>{
   let live=true;
   const sync=()=>{if(live)setRecord(previous=>{const cached=storedCompletion(userId,new Date(),context,recentSets),current=completionForToday(previous);return current&&(!cached||new Date(current.completed_at)>=new Date(cached.completed_at))?current:cached;});};
   const read=()=>{
     sync();setStatus("loading");
     axios.get(API+"/workout/completion",{params:{profile_id:userId}}).then(r=>{
       if(!live)return;
       const server=r.data?.completion;
       if(server){setRecord(previous=>previous?.day===server.day||new Date(previous?.completed_at||0)<=new Date(server.completed_at)?server:previous);}
       setStatus("ready");
     }).catch(()=>{if(live)setStatus("error");});
   };
   read();
   const timer=setInterval(()=>{sync();setTick(v=>v+1);},60000);
   window.addEventListener("forge:workout-complete",read);
   window.addEventListener("storage",read);
   window.addEventListener("focus",read);
   return()=>{live=false;clearInterval(timer);window.removeEventListener("forge:workout-complete",read);window.removeEventListener("storage",read);window.removeEventListener("focus",read);};
 },[userId,context,recentSets,API]);
 return {completion:completionForToday(record),status,retry:()=>window.dispatchEvent(new Event("forge:workout-complete")),tick};
}
