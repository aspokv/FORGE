import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {semanaDaDieta,numero,textoDosDias,totaisDaSemana,larguraDaBarra,textoDaDiferenca} from "./semanaDaDieta";

/**
 * A semana de alimentacao dentro da Evolucao.
 *
 * A proteina lidera porque e ela que decide hipertrofia: bater a caloria com pouca proteina
 * e pior que errar a caloria com a proteina no lugar.
 *
 * Sem grafico de proposito. A Evolucao acabou de ser enxugada justamente por excesso de
 * grafico; uma curva de calorias aqui desfaria isso. Numeros grandes e uma frase, na mesma
 * linguagem do bloco de quatro semanas do treino.
 */
export default function DietaEvolucao({API,profileId}){
  const [dados,setDados]=useState(null),[erro,setErro]=useState(false);
  useEffect(()=>{
    let vivo=true;setDados(null);setErro(false);
    axios.get(`${API}/nutrition/adherence-week`,{params:{days:7}})
      .then(r=>{if(vivo)setDados(r.data||{})})
      .catch(()=>{if(vivo){setDados({});setErro(true)}});
    return()=>{vivo=false};
  },[API,profileId]);
  const resumo=useMemo(()=>semanaDaDieta(dados),[dados]);
  const totais=useMemo(()=>totaisDaSemana(dados),[dados]);

  if(dados===null)return <p role="status">Carregando sua semana…</p>;
  if(erro)return <p role="alert">Não foi possível carregar sua semana de alimentação.</p>;

  return <>
  <section className="a6-panel dieta-semana" data-testid="dieta-semana">
    <span className="a6-eyebrow">Alimentação · últimos {resumo.janela} dias</span>
    <h2>{resumo.frase}</h2>

    {resumo.dias>0&&<>
      <div className="dieta-numeros">
        <div>
          <strong data-testid="dieta-proteina">{numero(resumo.proteinaPorDia)} g</strong>
          <span>proteína por dia</span>
          {resumo.metaProteina>0&&<small>meta {numero(resumo.metaProteina)} g</small>}
        </div>
        <div>
          <strong data-testid="dieta-kcal">{numero(resumo.kcalPorDia)}</strong>
          <span>kcal por dia</span>
          {resumo.metaKcal>0&&<small>meta {numero(resumo.metaKcal)}</small>}
        </div>
      </div>
      {/*
        * A legenda que impede o numero de mentir: sem ela alguem le "2.740 kcal por dia"
        * como se fossem os sete dias da semana.
        */}
      <p className="dieta-dias" data-testid="dieta-dias">
        Média dos dias que você registrou — {textoDosDias(resumo)}.
        {resumo.dias<resumo.janela&&" Os dias sem registro ficam de fora da conta."}
      </p>
    </>}

    {!resumo.dias&&<p className="dieta-dias">
      Registre o que você comeu na aba Nutrição e esta semana começa a contar.
    </p>}
  </section>

  {resumo.dias>0&&<section className="a6-panel dieta-totais" data-testid="dieta-totais" aria-label="Totais da semana">
    <span className="a6-eyebrow">Total dos {resumo.dias} {resumo.dias===1?"dia registrado":"dias registrados"}</span>
    <ul>
      {totais.map(linha=><li key={linha.chave}>
        <div className="dieta-linha-topo">
          <strong>{linha.nome}</strong>
          <span>{numero(linha.consumido)} <small>de {numero(linha.meta)} {linha.unidade}</small></span>
        </div>
        {/*
          * A barra para em 100% para nao vazar da caixa; quem conta que a pessoa passou da
          * meta e o texto ao lado, que nao tem teto.
          */}
        <div className="dieta-barra" role="progressbar" aria-label={linha.nome}
             aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(Math.min(1,linha.fracao)*100)}>
          <span className={linha.fracao>1.05?"dieta-barra-cheia":undefined} style={{width:larguraDaBarra(linha.fracao)}}/>
        </div>
        <small className="dieta-resto">{textoDaDiferenca(linha)}</small>
      </li>)}
    </ul>
  </section>}</>;
}
