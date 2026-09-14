import {useState} from "react";
import {NotebookPen} from "lucide-react";
import "./metodo-do-treinador.css";

/**
 * O metodo do treinador, dentro da Nutricao.
 *
 * O que este bloco responde e uma pergunta que nenhum contador de caloria responde: nao
 * QUANTO comer, e sim ONDE o carboidrato do dia cai, e por que. A meta diaria a pessoa ja
 * tem; o que faltava era a arquitetura — que refeicao serve para que, e o que muda entre um
 * dia low e um dia high.
 *
 * Os dados vem PRONTOS no ciclo, que a tela de nutricao ja busca. Sem requisicao propria:
 * uma segunda busca abriria a porta para os dois numeros divergirem, que foi exatamente o
 * defeito que o atleta encontrou no carboidrato do dia.
 *
 * Fechado por padrao, como a lista de compras: e referencia, e o plano do dia e o que a
 * pessoa abre todo dia.
 */
export default function MetodoDoTreinador({metodo}){
  const [aberto,setAberto]=useState(false);
  // O formato de hoje abre selecionado. Em dia de descanso `hoje` vem nulo de proposito — o
  // treinador nunca escreveu um formato de dia sem treino — e o bloco cai no low, que e o
  // padrao dos protocolos, sem afirmar que e o de hoje.
  const [aba,setAba]=useState(metodo?.hoje||"low");
  if(!metodo?.formatos)return null;

  const formato=metodo.formatos[aba]||metodo.formatos.low;
  const eHoje=metodo.hoje===aba;

  return <section className="metodo" data-testid="metodo-do-treinador">
    <button type="button" className="metodo-topo" aria-expanded={aberto} onClick={()=>setAberto(v=>!v)}>
      <NotebookPen size={17} aria-hidden="true"/>
      <span>
        <strong>O método</strong>
        <small>Como o dia é montado</small>
      </span>
      <span className="metodo-seta" aria-hidden="true">{aberto?"▾":"▸"}</span>
    </button>

    {aberto&&<div className="metodo-corpo">
      <div className="metodo-abas" role="tablist">
        {["low","high"].map(chave=>(
          <button key={chave} type="button" role="tab" aria-selected={aba===chave}
                  className={`metodo-aba${aba===chave?" metodo-aba-ativa":""}`}
                  onClick={()=>setAba(chave)}>
            {metodo.formatos[chave].rotulo}
            {metodo.hoje===chave&&<em>hoje</em>}
          </button>
        ))}
      </div>

      <p className="metodo-resumo">{formato.resumo}</p>
      <p className="metodo-total">
        {eHoje?"Hoje são ":"Neste formato, "}<b>{formato.carbo_g} g</b> de carboidrato no dia,
        divididos assim:
      </p>

      <ol className="metodo-refeicoes">
        {formato.refeicoes.map(r=>(
          <li key={r.papel} className={r.sem_carbo?"metodo-refeicao metodo-sem-amido":"metodo-refeicao"}>
            <div className="metodo-refeicao-topo">
              <strong>{r.nome}</strong>
              {/*
                * Tres estados, e nao dois. "0 g" nao e informacao em nenhum deles:
                *   - a refeicao que PERDEU o amido hoje diz "sem amido", com palavra, que e
                *     como o treinador escreveu no protocolo;
                *   - a refeicao que nunca teve carboidrato (a ceia e so proteina lenta) nao
                *     mostra numero nenhum — zero ali pareceria defeito;
                *   - o resto mostra a grama.
                */}
              {r.sem_carbo
                ? <span className="metodo-gramas">sem amido</span>
                : r.carbo.length>0&&<span className="metodo-gramas">{r.carbo_g} g</span>}
            </div>
            <p className="metodo-porque">{r.porque}</p>
            {r.proteina.length>0&&<Linha titulo="Proteína" itens={r.proteina}/>}
            {r.carbo.length>0&&!r.sem_carbo&&<Linha titulo="Carboidrato" itens={r.carbo}/>}
            {r.gordura.length>0&&<Linha titulo="Gordura" itens={r.gordura}/>}
            {r.acompanha.length>0&&<Linha titulo="Acompanha" itens={r.acompanha}/>}
          </li>
        ))}
      </ol>

      {/*
        * As regras vem com a razao junto. E a razao que faz a pessoa obedecer em vez de achar
        * que o aplicativo errou — "pese pronto" sozinho vira discussao, "pese pronto porque e
        * assim que a tabela mede" acaba a discussao.
        */}
      <h4 className="metodo-titulo">As regras</h4>
      <ul className="metodo-regras" data-testid="metodo-regras">
        {metodo.regras.map(r=>(
          <li key={r.chave}>
            <strong>{r.regra}</strong>
            <span>{r.porque}</span>
          </li>
        ))}
      </ul>
    </div>}
  </section>;
}

function Linha({titulo,itens}){
  return <p className="metodo-fontes">
    <span>{titulo}</span>
    {/*
      * "ou" e nao virgula: os protocolos sempre trazem alternativa dentro do mesmo papel, e
      * ler "frango, patinho, tilapia" daria a entender que sao os tres no mesmo prato.
      */}
    {itens.join(" ou ")}
  </p>;
}
