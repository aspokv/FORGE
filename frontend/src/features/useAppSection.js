import {useEffect, useState} from "react";
import {resumeDate} from "./workoutResume";

const sections = {inicio:"Hoje", treino:"Treino", nutricao:"Alimentação", evolucao:"Progresso", perfil:"Perfil", analise:"Análise", planos:"Planos"};
export const sectionFromLocation = () => sections[new URLSearchParams(window.location.search).get("view")] || "Hoje";

function initialSection(userId) {
  if(new URLSearchParams(window.location.search).has("view"))return sectionFromLocation();
  if(userId)try {
    const saved=JSON.parse(localStorage.getItem(`forge_last_section:${userId}`)||"null");
    if(saved?.date===resumeDate()&&saved.section==="Treino")return "Treino";
  }catch { /* A blocked or corrupt local cache is optional. */ }
  return sectionFromLocation();
}
// The URL wins. A fresh browser entry can recover the last training tab for this user/day.
export default function useAppSection(userId) {
  const [section,setSection]=useState(()=>initialSection(userId));
  useEffect(()=>{
    if(userId)try{localStorage.setItem(`forge_last_section:${userId}`,JSON.stringify({date:resumeDate(),section}));}catch{}
  },[userId,section]);
  useEffect(()=>{
    const onPop=()=>setSection(sectionFromLocation());
    window.addEventListener("popstate",onPop);
    return()=>window.removeEventListener("popstate",onPop);
  },[]);
  const navigate=next=>{
    const key=Object.keys(sections).find(key=>sections[key]===next);
    if(!key)return;
    const url=new URL(window.location.href);
    if(sectionFromLocation()!==next){
      if(key==="inicio")url.searchParams.delete("view");else url.searchParams.set("view",key);
      window.history.pushState({},"",url);
    }
    setSection(next);
  };
  return [section,navigate];
}
