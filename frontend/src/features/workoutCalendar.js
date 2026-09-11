import {useEffect,useMemo,useState} from "react";

const dateKey=date=>[date.getFullYear(),date.getMonth(),date.getDate()].join("-");
// Weekday metadata comes from the server's validated labels, never from session indexes.
export function scheduledProgram(program={}, now=new Date(), afterToday=false){
  const weekdays=program.calendar?.weekdays;
  if(!weekdays)return program;
  const sessions=program.sessions||[],weekday=(now.getDay()+6)%7;
  const today=sessions.find(s=>weekdays[String(s.day)]===weekday)||null;
  let next=null,nextDate=null;
  for(let offset=afterToday?1:0;offset<=7;offset++){
    const match=sessions.find(s=>weekdays[String(s.day)]===(weekday+offset)%7);
    if(match){next=match;nextDate=new Date(now);nextDate.setDate(now.getDate()+offset);break;}
  }
  return {...program,active_day:today?.day??null,session:today?.label||"Descanso",
    rest_day:!today,calendar:{...program.calendar,today,next,next_date:nextDate?nextDate.toLocaleDateString("sv-SE"):null}};
}
export function useScheduledProgram(program,afterToday=false){
  const [day,setDay]=useState(()=>dateKey(new Date()));
  useEffect(()=>{
    const refresh=()=>setDay(dateKey(new Date()));
    const timer=setInterval(refresh,30000);
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",refresh);
    return()=>{clearInterval(timer);window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);};
  },[]);
  return useMemo(()=>scheduledProgram(program,new Date(...day.split("-").map(Number)),afterToday),[program,day,afterToday]);
}
