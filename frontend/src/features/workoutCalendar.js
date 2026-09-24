import {useEffect,useMemo,useState} from "react";

const dateKey=date=>[date.getFullYear(),date.getMonth(),date.getDate()].join("-");
/** "2026-09-24" no fuso LOCAL. `toISOString` daria UTC e voltaria um dia no Brasil. */
const emISO=date=>date.toLocaleDateString("sv-SE");
/** Data a partir de "2026-09-24" sem passar por UTC, pelo mesmo motivo. */
const deISO=iso=>{const[a,m,d]=String(iso||"").split("-").map(Number);
  return a&&m&&d?new Date(a,m-1,d):null;};

// Weekday metadata comes from the server's validated labels, never from session indexes.
export function scheduledProgram(program={}, now=new Date(), afterToday=false){
  const weekdays=program.calendar?.weekdays;
  if(!weekdays)return program;
  const sessions=program.sessions||[];
  const daAgenda=data=>sessions.find(s=>weekdays[String(s.day)]===(data.getDay()+6)%7)||null;

  /* As TROCAS DE DIA entram aqui, e não dá para pular esta parte.
     Este recálculo no cliente existe para o aplicativo aberto atravessar a meia-noite e
     virar o dia sozinho — e é por isso que ele decide `rest_day`, e não o servidor. Só que
     ele decidia pelo dia da SEMANA, que não sabe de troca: o servidor respondia
     `rest_day:false` com a sessão adiantada, e a tela escrevia "descanso" por cima. A
     troca ficava gravada, aparecia escrita como feita, e não acontecia. */
  const trocas=(program.calendar?.trocas||[]).filter(t=>t&&t.treinar_em&&t.descansar_em);
  const doDia=data=>{
    const iso=emISO(data);
    for(const t of trocas){
      if(t.descansar_em===iso)return null;            // cedeu o treino
      if(t.treinar_em===iso){const o=deISO(t.descansar_em);return o?daAgenda(o):null;}
    }
    return daAgenda(data);
  };

  const today=doDia(now);
  let next=null,nextDate=null;
  for(let offset=afterToday?1:0;offset<=7;offset++){
    const data=new Date(now);data.setDate(now.getDate()+offset);
    const match=doDia(data);
    if(match){next=match;nextDate=data;break;}
  }
  return {...program,active_day:today?.day??null,session:today?.label||"Descanso",
    rest_day:!today,calendar:{...program.calendar,today,next,next_date:nextDate?emISO(nextDate):null}};
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
