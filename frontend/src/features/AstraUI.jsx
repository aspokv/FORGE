import {createContext, useContext} from "react";
import brand from "../assets/logotipo_forge_em_metal_forjado.png";

export const AstraNavigation = createContext({});
const paths={home:'M3 10 12 3 21 10M5 9v12h5v-7h4v7h5V9',training:'m6 3 15 15M3 6l6-6M0 3l3-3M15 24l6-6M18 21l6-6M5 8l3-3M16 19l3-3',nutrition:'M5 3v7m3-7v7M3 3v6q0 3 4 3v9m11-18q-5 4-4 10h4m0-10v18',progress:'M4 3v17h17M7 15l4-5 4 2 5-7',profile:'M8 7a4 4 0 1 0 8 0 4 4 0 1 0-8 0M4 21v-2a8 8 0 0 1 16 0v2',chevron:'m9 5 7 7-7 7',clock:'M12 7v5l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18',water:'M12 2s-7 9-7 13a7 7 0 0 0 14 0C19 11 12 2 12 2M8 15a4 4 0 0 0 4 4',check:'m5 12 4 4L19 6',book:'M12 5v16M3 4h5q4 0 4 2 0-2 4-2h5v15h-5q-4 0-4 2 0-2-4-2H3Z',settings:'M4 5h16M4 12h16M4 19h16M8 3v4M16 10v4M10 17v4',camera:'M3 7h4l2-3h6l2 3h4v14H3ZM12 10a4 4 0 1 0 0 8 4 4 0 1 0 0-8',shield:'m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z M8 12l3 3 5-6'};
export function AstraIcon({name}) {return <svg className="a6-ico" viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]||paths.chevron}/></svg>}
export function AstraPage({screen,children,onLibrary,testId}) {
  const nav=useContext(AstraNavigation);
  return <div className={`a6 a6-screen-${screen}`} data-testid={testId}>
    <header className="a6-app-header"><div className="a6-logo" role="img" aria-label="FORGE"><img src={brand} alt="" width="1672" height="941"/></div><button type="button" className="a6-iconbutton" aria-label={onLibrary?"Abrir biblioteca de treinos":"Abrir perfil"} onClick={onLibrary||nav.profile}><AstraIcon name={onLibrary?"book":"profile"}/></button></header>
    <div className="a6-scroll">{children}</div>
  </div>;
}
export function AstraIntro({eyebrow,title,subtitle}) {return <div className="a6-intro"><div className="a6-eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle&&<p>{subtitle}</p>}</div>}
export function AstraAction({children,onClick,testId,disabled}) {return <button type="button" className="a6-primary" data-testid={testId} disabled={disabled} onClick={onClick}>{children}<AstraIcon name="chevron"/></button>}
export function AstraMeta({duration,sets}) {return <div className="a6-meta"><span><AstraIcon name="clock"/>{duration}</span><span><AstraIcon name="training"/>{sets} séries</span></div>}
export function AstraRow({icon,title,subtitle,onClick,testId,expanded}) {return <button type="button" className="a6-profile-row" data-testid={testId} aria-expanded={expanded} onClick={onClick}><span className="a6-iconbox"><AstraIcon name={icon}/></span><span className="a6-copy"><h3>{title}</h3><p>{subtitle}</p></span><AstraIcon name="chevron"/></button>}
export const astraDate=(date=new Date())=>new Intl.DateTimeFormat("pt-BR",{weekday:"long",day:"2-digit",month:"long"}).format(date).replace("-feira","").toUpperCase();
export const numberBR=n=>Number(n).toLocaleString("pt-BR",{maximumFractionDigits:1});
export function AstraBottomNav({tab,onChange}) {
  return <nav className="a6-bottom-nav" aria-label="Navegação principal">{[["Hoje","Início","home"],["Treino","Treino","training"],["Alimentação","Nutrição","nutrition"],["Progresso","Evolução","progress"],["Perfil","Perfil","profile"]].map(([key,label,icon])=><button type="button" key={key} data-testid={`nav-${key.toLowerCase()}`} aria-current={tab===key?"page":undefined} onClick={()=>onChange(key)}><AstraIcon name={icon}/>{label}</button>)}</nav>;
}
