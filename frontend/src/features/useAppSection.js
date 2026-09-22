import {useEffect, useState} from "react";

const sections = {inicio:"Hoje", treino:"Treino", nutricao:"Alimentação", evolucao:"Progresso", perfil:"Perfil", analise:"Análise", planos:"Planos"};
export const sectionFromLocation = () => sections[new URLSearchParams(window.location.search).get("view")] || "Hoje";

// Keep browser Back and refresh aligned with navigation; no user data is stored here.
export default function useAppSection() {
  const [section,setSection]=useState(sectionFromLocation);
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
