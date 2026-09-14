import {useEffect,useState} from "react";
import axios from "axios";
import "./carboidrato-do-dia.css";

const CLASSES={
  prioritario:{rotulo:"Dia do seu ponto fraco",cor:"alta"},
  treino:{rotulo:"Dia de treino",cor:"normal"},
  descanso:{rotulo:"Dia de descanso",cor:"baixa"},
};

/**
 * O carboidrato do dia, concentrado no treino do ponto fraco.
 *
 * Por que isto e possivel aqui e quase em lugar nenhum: o FORGE sabe qual sessao treina qual
 * musculo E sabe a meta alimentar da pessoa. Quem tem so um dos dois nao consegue ligar.
 *
 * INFORMATIVO por enquanto: mostra a meta do dia, e nao um cardapio diferente por dia.
 * Regerar as refeicoes de sete dias mexe no gerador de plano, que ja esta servindo gente — e
 * a meta ja e util sozinha, porque a pessoa ajusta a porcao sabendo que hoje o alvo e maior.
 *
 * Quando nao ha o que ciclar, o bloco mostra o MOTIVO em vez de sumir. Cada motivo tem um
 * conserto que a propria pessoa faz; sumir em silencio deixaria ela sem saber que existe.
 */
export default function CarboidratoDoDia({API}){
  const [dados,setDados]=useState(null);
  useEffect(()=>{
    let vivo=true;
    axios.get(`${API}/nutrition/carb-cycle`)
      .then(r=>{if(vivo)setDados(r.data||{})})
      .catch(()=>{if(vivo)setDados({ativo:false})});
    return()=>{vivo=false};
  },[API]);

  if(!dados)return null;

  if(!dados.ativo){
    if(!dados.motivo)return null;
    return <section className="carbo-dia carbo-dia-inativo" data-testid="carboidrato-do-dia">
      <span className="a6-eyebrow">Carboidrato por dia</span>
      <p>{dados.motivo}</p>
    </section>;
  }

  const hoje=dados.hoje||{},info=CLASSES[hoje.classe]||CLASSES.treino;
  const base=dados.base||{};
  const diferenca=Math.round((hoje.carbs_g||0)-(base.carbs_g||0));

  return <section className={`carbo-dia carbo-dia-${info.cor}`} data-testid="carboidrato-do-dia">
    <span className="a6-eyebrow">{info.rotulo}</span>
    <div className="carbo-dia-numero">
      <strong data-testid="carbo-do-dia">{Math.round(hoje.carbs_g)} g</strong>
      <span>de carboidrato hoje</span>
    </div>
    {/*
      * A diferenca contra a media e o que explica o numero. Sem ela, "582 g" nao diz nada
      * para quem tinha 439 g na cabeca — parece que a meta mudou do nada.
      */}
    {diferenca!==0&&<p className="carbo-dia-comparacao">
      {diferenca>0?`${diferenca} g a mais`:`${Math.abs(diferenca)} g a menos`} que a sua média
      de {Math.round(base.carbs_g)} g.
    </p>}
    <p className="carbo-dia-nota">
      A semana continua somando o mesmo: o que sobe no dia do ponto fraco sai do descanso.
      Proteína e gordura não mudam.
    </p>
  </section>;
}
