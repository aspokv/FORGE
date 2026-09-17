import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {ArrowRight, Check, Loader2, Minus, ShieldCheck, TrendingDown, X} from "lucide-react";
import "./conselho.css";

/**
 * O Conselho: a semana medida vira UMA decisao, e o motor responde por ela.
 *
 * Por que esta tela e diferente de todo grafico que o FORGE ja tinha: um grafico e um
 * espelho, e espelho nao decide nada. Aqui a pessoa le um veredito, o motivo com os
 * numeros que o produziram, a mudanca proposta, e a aposta que o motor faz sobre a
 * semana seguinte. Na semana seguinte ele volta dizendo se acertou.
 *
 * Tres decisoes de interface que vem direto das travas do motor:
 *
 *   1. A LEITURA aparece junto do veredito, sempre. Um veredito sem os numeros e um
 *      palpite com tipografia bonita, e a pessoa precisa poder discordar do motor
 *      olhando a mesma coisa que ele olhou.
 *   2. "Agora nao" tem o mesmo peso visual de "Aplicar". Quem conhece o contexto que o
 *      banco nao tem, uma viagem, uma gripe, uma prova, e a pessoa.
 *   3. Quando a alavanca e SEM_LEITURA ou ADERENCIA, nao existe botao de aplicar,
 *      porque nao existe mudanca. A tela nao inventa uma acao para parecer util.
 */

const ROTULO_DA_ALAVANCA={
  sem_leitura:{texto:"Sem leitura",tom:"neutro"},
  aderencia:{texto:"Aderência",tom:"atencao"},
  treino:{texto:"Treino",tom:"treino"},
  perda_rapida:{texto:"Segurar",tom:"atencao"},
  caloria:{texto:"Caloria",tom:"acao"},
  manter:{texto:"Manter",tom:"bom"},
};

const SEM_MUDANCA=["sem_leitura","aderencia"];

/**
 * Decimal com virgula, que e como se escreve peso no Brasil.
 *
 * O backend ja escreve as FRASES assim. Esta tela monta numeros por conta propria, e
 * `toFixed` devolve ponto: a mesma tela mostrava "seu peso cai entre 0,28 kg" na frase e
 * "0.00 kg" no quadro de leitura, logo abaixo. So apareceu olhando a tela com dado real.
 */
function numero(valor,casas=2,sinal=false){
  if(valor==null||Number.isNaN(valor))return "—";
  const texto=sinal&&valor>=0?`+${valor.toFixed(casas)}`:valor.toFixed(casas);
  return texto.replace(".",",");
}

function Numero({rotulo,valor,detalhe}){
  return <div className="conselho-numero">
    <span className="conselho-numero-rotulo">{rotulo}</span>
    <strong>{valor}</strong>
    {detalhe?<small>{detalhe}</small>:null}
  </div>;
}

/** A leitura que gerou o veredito, em quatro numeros. */
function Leitura({estado}){
  const comida=estado?.comida||{},peso=estado?.peso||{},volume=estado?.volume||{},
    prontidao=estado?.prontidao||{};
  const kg=peso.kg_por_semana;
  return <div className="conselho-leitura" data-testid="conselho-leitura">
    <Numero
      rotulo="Registro"
      valor={`${comida.dias_registrados??0}/${comida.janela_dias??7}`}
      detalhe={comida.kcal_media?`${Math.round(comida.kcal_media)} kcal em média`:"dias anotados"}/>
    <Numero
      rotulo="Peso"
      valor={peso.suficiente&&kg!=null?`${numero(kg,2,true)} kg`:"—"}
      detalhe={peso.suficiente?`por semana, em ${peso.dias_cobertos} dias`:"pesagens insuficientes"}/>
    <Numero
      rotulo="Volume"
      valor={volume.suficiente&&volume.variacao!=null
        ?`${volume.variacao>0?"+":""}${Math.round(volume.variacao*100)}%`:"—"}
      detalhe={volume.suficiente?`${volume.series_agora} séries, base ${volume.series_base}`
        :"poucas semanas de treino"}/>
    <Numero
      rotulo="Pior dia"
      valor={prontidao.suficiente?prontidao.pior_dia:"—"}
      detalhe={prontidao.suficiente?`prontidão ${numero(prontidao.pior_pontuacao,1)}`:"poucos check-ins"}/>
  </div>;
}

/** O placar corrido. E ele que transforma o motor em alguem que arrisca junto. */
function Retrospecto({retrospecto,placar}){
  const julgadas=retrospecto?.julgadas||0;
  if(!julgadas&&!placar)return null;
  return <div className="conselho-placar" data-testid="conselho-placar">
    {placar?<p className={placar.resultado==="acertou"?"placar-acertou":"placar-errou"}>
      <ShieldCheck size={14}/>
      {placar.resultado==="acertou"?"Semana passada eu acertei."
        :placar.resultado==="errou"?"Semana passada eu errei."
          :"Semana passada não deu para conferir."}
      {placar.previsto?<span> Eu disse que {placar.previsto}.</span>:null}
    </p>:null}
    {julgadas>0?<span className="placar-corrido">
      {retrospecto.acertos} de {julgadas} previsões certas
    </span>:null}
  </div>;
}

export default function Conselho({API,axiosCliente=axios}){
  const [dados,setDados]=useState(null);
  const [estadoDaTela,setEstadoDaTela]=useState("carregando");
  const [enviando,setEnviando]=useState(false);
  const [aviso,setAviso]=useState("");

  const buscar=useCallback(async()=>{
    try{
      const r=await axiosCliente.get(`${API}/conselho`);
      setDados(r.data);
      setEstadoDaTela("pronto");
    }catch(erro){
      // NUNCA o detalhe cru: em 402 ele e um objeto, e renderizar objeto derruba a tela.
      if(erro?.response?.status===402)setEstadoDaTela("bloqueado");
      else setEstadoDaTela("erro");
    }
  },[API,axiosCliente]);

  useEffect(()=>{buscar()},[buscar]);

  const responder=async aceitar=>{
    setEnviando(true);setAviso("");
    try{
      const r=await axiosCliente.post(`${API}/conselho/aplicar`,{aceitar});
      const status=r.data?.status;
      if(status==="aplicada")setAviso("Feito. Sua meta já está valendo.");
      else if(status==="manual")setAviso(r.data?.mensagem||"Essa mudança é no treino, e quem faz é você.");
      else if(status==="recusada")setAviso("Combinado. Fica como está, e eu te chamo semana que vem.");
      else if(status==="ja_aplicada")setAviso("Essa mudança já estava aplicada.");
      await buscar();
    }catch{
      setAviso("Não consegui registrar sua resposta agora. Tente de novo.");
    }finally{setEnviando(false)}
  };

  if(estadoDaTela==="carregando")return <section className="conselho conselho-vazio">
    <Loader2 className="girando" size={18}/><p>Lendo sua semana...</p>
  </section>;

  if(estadoDaTela==="bloqueado")return <section className="conselho conselho-bloqueado"
    data-testid="conselho-bloqueado">
    <span className="conselho-etiqueta">O Conselho</span>
    <h3>Seu treinador semanal está no FORGE Elite</h3>
    <p>
      Toda semana o FORGE cruza o que você comeu, o que você levantou, como você acordou e
      o que a balança disse, decide UMA coisa para mudar, explica o porquê com os seus
      números e assume uma previsão. Na semana seguinte ele volta para dizer se acertou.
    </p>
  </section>;

  if(estadoDaTela==="erro")return <section className="conselho conselho-vazio">
    <p>Não consegui ler sua semana agora.</p>
    <button className="conselho-secundario" onClick={buscar}>Tentar de novo</button>
  </section>;

  const decisao=dados?.decisao||{};
  const alavanca=ROTULO_DA_ALAVANCA[decisao.alavanca]||ROTULO_DA_ALAVANCA.sem_leitura;
  const mudanca=decisao.mudanca;
  const jaRespondeu=!!dados?.aplicada;
  const podeAplicar=!!mudanca&&!SEM_MUDANCA.includes(decisao.alavanca)&&!jaRespondeu;

  return <section className={`conselho tom-${alavanca.tom}`} data-testid="conselho">
    <header className="conselho-topo">
      <span className="conselho-etiqueta">O Conselho · {dados?.semana}</span>
      <span className={`conselho-alavanca tom-${alavanca.tom}`}>{alavanca.texto}</span>
    </header>

    <Retrospecto retrospecto={dados?.retrospecto} placar={dados?.placar_anterior}/>

    <h3 data-testid="conselho-titulo">{decisao.titulo}</h3>
    <p className="conselho-motivo" data-testid="conselho-motivo">{decisao.motivo}</p>

    {mudanca?<div className="conselho-mudanca" data-testid="conselho-mudanca">
      {mudanca.tipo==="kcal"
        ?<div className="conselho-troca">
          <span className="de">{Math.round(mudanca.de)} kcal</span>
          <ArrowRight size={16}/>
          <strong className="para">{Math.round(mudanca.para)} kcal</strong>
          <span className={mudanca.delta<0?"delta corte":"delta soma"}>
            {mudanca.delta<0?<TrendingDown size={13}/>:<Minus size={13}/>}
            {mudanca.delta>0?"+":""}{Math.round(mudanca.delta)}
          </span>
        </div>
        :<div className="conselho-troca">
          <strong className="para">
            {mudanca.tipo==="agenda"?`Mover de ${mudanca.de} para ${mudanca.para}`
              :mudanca.tipo==="descarga"?`Tirar ${Math.abs(mudanca.percentual)}% da carga`
                :`Voltar a ${mudanca.series_alvo} séries`}
          </strong>
        </div>}
      {mudanca.trava?<small className="conselho-trava">{mudanca.trava}</small>:null}
    </div>:null}

    {decisao.previsao?.frase?<p className="conselho-previsao" data-testid="conselho-previsao">
      <strong>Se eu estiver certo,</strong> {decisao.previsao.frase}. Te cobro disso na
      semana que vem.
    </p>:null}

    {podeAplicar?<div className="conselho-acoes">
      <button className="conselho-principal" disabled={enviando}
        onClick={()=>responder(true)} data-testid="conselho-aplicar">
        {enviando?<Loader2 className="girando" size={15}/>:<Check size={15}/>}
        {mudanca.tipo==="kcal"?"Aplicar no meu plano":"Entendi, vou fazer"}
      </button>
      <button className="conselho-secundario" disabled={enviando}
        onClick={()=>responder(false)} data-testid="conselho-recusar">
        <X size={15}/>Agora não
      </button>
    </div>:null}

    {jaRespondeu?<p className="conselho-resolvido" data-testid="conselho-resolvido">
      {dados.aplicada.status==="aplicada"
        ?`Aplicado: ${Math.round(dados.aplicada.de)} para ${Math.round(dados.aplicada.para)} kcal.`
        :dados.aplicada.status==="recusada"?"Você deixou como estava nesta semana."
          :"Essa mudança está com você, na tela de treino."}
    </p>:null}

    {aviso?<p className="conselho-aviso" role="status">{aviso}</p>:null}

    <Leitura estado={dados?.estado}/>
  </section>;
}
