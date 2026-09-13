import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {linhasDaSessao,idsDaSessao,quantosComHistorico} from "./sessaoDeHoje";

/**
 * O treino de hoje com o que superar em cada exercicio.
 *
 * Abre a Evolucao respondendo a pergunta que a pessoa faz antes de treinar — "quanto eu
 * peguei da ultima vez nisso aqui?" — em vez de pedir que ela escolha um exercicio entre
 * cento e setenta e cinco. Se hoje e peito dominante, a lista e a de peito dominante.
 *
 * Num dia de descanso a sessao mostrada e a PROXIMA, porque a pergunta continua valendo: e
 * no descanso que a pessoa planeja o que vai levantar amanha.
 */
export default function SessaoEvolucao({API,profileId,sessao,catalogo=[],descanso=false}){
  const exercicios=useMemo(()=>sessao?.exercises||[],[sessao]);
  const ids=useMemo(()=>idsDaSessao(exercicios),[exercicios]);
  const [desempenhos,setDesempenhos]=useState(null);
  const [erro,setErro]=useState(false);
  const chave=ids.join(",");
  useEffect(()=>{
    if(!chave){setDesempenhos({});return;}
    let vivo=true;setDesempenhos(null);setErro(false);
    axios.get(API+"/session-last-performance",{params:{ids:chave}})
      .then(r=>{if(vivo)setDesempenhos(r.data?.performances||{});})
      .catch(()=>{if(vivo){setDesempenhos({});setErro(true);}});
    return()=>{vivo=false;};
  },[API,profileId,chave]);
  const linhas=useMemo(()=>linhasDaSessao({exercicios,catalogo,desempenhos:desempenhos||{}}),[exercicios,catalogo,desempenhos]);
  const comHistorico=quantosComHistorico(linhas);
  if(!linhas.length)return null;
  return <section className="a6-panel sessao-evolucao" data-testid="sessao-evolucao" aria-label={descanso?"Próximo treino":"Treino de hoje"}>
    <span className="a6-eyebrow">{descanso?"Próximo treino":"Treino de hoje"}</span>
    <h2>{sessao?.label||"Sua sessão"}</h2>
    {/* Sem historico nao ha o que superar, e prometer superacao seria mentira. */}
    <p className="sessao-evolucao-guia">{desempenhos===null?"Buscando suas últimas cargas…":comHistorico?"Suas últimas cargas. Supere o que der.":"Primeira vez neste treino. Estes números viram sua base."}</p>
    <ul className="sessao-evolucao-lista">
      {linhas.map((l,i)=><li key={`${l.id}-${i}`}>
        <div className="sessao-evolucao-nome">
          <strong>{l.nome}</strong>
          <small>{l.prescrito.series}×{l.prescrito.reps}</small>
        </div>
        {l.estreia
          ?<div className="sessao-evolucao-marca sessao-evolucao-estreia">{desempenhos===null?"—":"Estreia"}</div>
          :<div className="sessao-evolucao-marca"><b>{l.carga} kg</b><small>× {l.reps} · {l.data}</small></div>}
      </li>)}
    </ul>
    {erro&&<p className="sessao-evolucao-guia" role="status">Não foi possível carregar suas cargas anteriores. O treino segue disponível.</p>}
  </section>;
}
