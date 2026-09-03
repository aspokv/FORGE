import {Check, Clock, Droplets, Dumbbell, House, Layers3, TrendingUp, UserRound, Utensils} from "lucide-react";
import planArt from "../assets/forge-plan-pull.webp";

/** Read-only composition based on the approved Home. Never mounts authenticated
 * Home or requests athlete data on the public page. All figures are sample data. */
export default function LandingProductPreview() {
  return <figure className="entry-product" aria-label="Demonstração da tela inicial do FORGE">
    <div className="entry-phone">
      <div className="entry-phone-speaker" aria-hidden="true" />
      <div className="entry-screen">
        <div className="entry-screen-brand">FORGE <UserRound size={16}/></div>
        <div className="entry-screen-greeting"><strong>Olá, Atleta.</strong><span>Seu próximo treino começa com direção.</span></div>
        <section className="entry-week"><h3>Resumo da semana</h3><div>{["SEG","TER","QUA","QUI","SEX","SÁB","DOM"].map((day,i)=><span key={day}>{day}<i className={i===2?"today":""}>{i<2&&<Check size={12}/>}</i></span>)}</div></section>
        <section className="entry-today"><h3>Plano de hoje</h3><div><img src={planArt} alt="Ilustração do treino de costas" width="72" height="82"/><div><strong>Pull 2</strong><span>Costas · Bíceps</span><small><Clock size={11}/>60 min <Layers3 size={11}/>16 séries</small></div><Dumbbell size={17}/></div></section>
        <section className="entry-nutrition"><h3>Nutrição</h3><span>Meta diária</span><div className="entry-calories"><svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26"/><circle cx="32" cy="32" r="26" strokeDasharray="98 164"/></svg><div><strong>1.420 <small>/ 2.400</small></strong><span>kcal consumidas</span></div></div><div className="entry-macros">{[["Proteínas","112 / 180 g"],["Carboidratos","150 / 260 g"],["Gorduras","41 / 70 g"]].map(([name,value])=><div key={name}><span>{name}</span><i/><small>{value}</small></div>)}</div></section>
        <section className="entry-water"><h3>Hidratação</h3><strong>1,5 <small>/ 2,5 L</small></strong><div aria-hidden="true">{Array.from({length:7},(_,i)=><Droplets key={i} size={20} className={i<4?"filled":""}/>)}</div></section>
        <div className="entry-phone-nav" aria-hidden="true">{[[House,"Início"],[Dumbbell,"Treino"],[Utensils,"Nutrição"],[TrendingUp,"Progresso"],[UserRound,"Perfil"]].map(([Icon,label])=><span key={label}><Icon size={16}/>{label}</span>)}</div>
      </div>
    </div>
    <figcaption>INTERFACE FORGE <span>Dados ilustrativos · plano conforme sua avaliação</span></figcaption>
  </figure>;
}
