import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {Check} from "lucide-react";
import "./escolher-refeicao.css";
import {mensagemDeErro} from "./mensagemDeErro";

/**
 * Escolher a refeicao do jeito que um treinador pergunta.
 *
 * A tela anterior mostrava as combinacoes prontas e escondia a troca atras de um botao
 * "Trocar" em cada linha, um alimento por vez, com tres alternativas. Toda a capacidade
 * estava la; o que faltava era PERGUNTAR.
 *
 * Aqui sao duas perguntas, na ordem em que o treinador faz:
 *
 *   1. Qual montagem — "ou farinha de arroz e whey, ou farinha de arroz e aveia".
 *   2. Qual alimento dentro dela — "escolha a sua carne: quando a pessoa nao tem frango,
 *      ela tem um patinho".
 *
 * Tres decisoes que parecem detalhe e nao sao:
 *
 * A GRAMA VEM SEMPRE DO SERVIDOR. Cada alternativa chega com a porcao dela, calculada
 * simulando a refeicao inteira — 150 g de frango viram 128 g de patinho e 62 g de whey.
 * Calcular isso aqui criaria um segundo numero para a mesma pergunta.
 *
 * A MARGEM FICA VISIVEL. "Se passar um pouquinho das calorias nao tem problema": sem o
 * numero na tela a pessoa persegue o valor exato, que e o oposto do que o metodo pede.
 *
 * A ORDEM E RECOMENDACAO. O topo de cada lista e o que a maioria vai escolher, entao ela
 * segue a pontuacao do metodo — frango e patinho na frente, salmao no fim.
 */
export default function EscolherRefeicao({API, mealIndex, onPronto, onMontarDoZero}) {
  const [dados, setDados] = useState(null);
  const [combinacao, setCombinacao] = useState(null);
  // O que a pessoa trocou dentro da montagem: papel -> food_id.
  const [trocado, setTrocado] = useState({});
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const buscar = useCallback((idDaCombinacao) => {
    setErro("");
    return axios.get(`${API}/nutrition/plan/draft/escolhas`, {
      params: {meal_index: mealIndex, ...(idDaCombinacao ? {combinacao: idDaCombinacao} : {})},
    });
  }, [API, mealIndex]);

  useEffect(() => {
    let vivo = true;
    setDados(null); setCombinacao(null); setTrocado({}); setErro("");
    buscar(null)
      .then(r => { if (vivo) { setDados(r.data); setCombinacao(r.data.escolhida); } })
      .catch(e => { if (vivo) setErro(mensagemDeErro(e, "Não foi possível carregar as opções.")); });
    return () => { vivo = false; };
  }, [buscar]);

  // Trocar de montagem zera as trocas: as perguntas de dentro sao outras, e manter a
  // escolha anterior gravaria um alimento que a nova montagem nem tem.
  const escolherCombinacao = async (id) => {
    if (id === combinacao) return;
    setCombinacao(id); setTrocado({}); setErro("");
    try {
      const r = await buscar(id);
      setDados(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível carregar essa combinação."));
    }
  };

  const escolhida = (dados?.combinacoes || []).find(c => c.id === combinacao)
    || (dados?.combinacoes || [])[0];

  /** Os alimentos que vao ser gravados: a montagem, com as trocas por cima. */
  const idsEscolhidos = () => {
    if (!escolhida) return [];
    const porPapel = new Map();
    escolhida.itens.forEach(i => porPapel.set(i.papel || i.food_id, i.food_id));
    Object.entries(trocado).forEach(([papel, fid]) => porPapel.set(papel, fid));
    return [...porPapel.values()];
  };

  /** O total da refeicao como ela esta agora, contando as trocas. */
  const totalAgora = () => {
    if (!escolhida) return 0;
    const porPapel = new Map();
    escolhida.itens.forEach(i => porPapel.set(i.papel || i.food_id, i.kcal));
    (dados?.trocas || []).forEach(t => {
      const fid = trocado[t.papel];
      if (!fid) return;
      const op = t.opcoes.find(o => o.food_id === fid);
      if (op) porPapel.set(t.papel, op.kcal);
    });
    return Math.round([...porPapel.values()].reduce((s, v) => s + v, 0));
  };

  const confirmar = async () => {
    setSalvando(true); setErro("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/choose`, {
        meal_index: mealIndex,
        archetype_id: escolhida?.id || "default",
        food_ids: idsEscolhidos(),
      });
      onPronto(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível salvar esta refeição."));
    } finally { setSalvando(false); }
  };

  if (erro && !dados) return <p className="fg-erro" role="alert">{erro}</p>;
  if (!dados) return <div className="fg-esqueleto" aria-label="Carregando as opções" />;

  const alvo = dados.alvo || {};
  const agora = totalAgora();
  const diferenca = agora - (alvo.kcal || 0);
  const dentro = Math.abs(diferenca) <= (alvo.tolerancia || 0);

  return (
    <section className="escolher" data-testid="escolher-refeicao">
      <header className="escolher-topo">
        <h3>{dados.pergunta}</h3>
        {/*
          * O alvo e a margem na mesma linha, de proposito. O numero sozinho vira meta a
          * perseguir; com a margem do lado ele vira faixa, que e como o treinador pensa.
          */}
        <p className="escolher-alvo" data-testid="escolher-alvo">
          <b>{alvo.kcal} kcal</b>
          <span> · pode variar {alvo.tolerancia} pra mais ou pra menos</span>
        </p>
      </header>

      <div className="escolher-lista" role="radiogroup" aria-label="Combinações">
        {(dados.combinacoes || []).map(c => (
          <button type="button" key={c.id} role="radio" aria-checked={c.id === escolhida?.id}
                  className={`escolher-combo${c.id === escolhida?.id ? " marcada" : ""}`}
                  data-testid={`combinacao-${c.id}`}
                  onClick={() => escolherCombinacao(c.id)}>
            <span className="escolher-combo-topo">
              <b>{c.titulo}</b>
              {/* O selo transforma uma lista ordenada numa recomendação com autor. */}
              {c.do_metodo && <em className="escolher-selo" data-testid={`selo-${c.id}`}>do método</em>}
              <span className="escolher-kcal">{c.kcal} kcal</span>
            </span>
            <small>{c.resumo}</small>
          </button>
        ))}
      </div>

      {(dados.trocas || []).map(t => (
        <div className="escolher-troca" key={t.papel} data-testid={`troca-${t.papel}`}>
          <p className="escolher-rotulo">
            {t.rotulo}
            {t.explicacao && <span> {t.explicacao}</span>}
          </p>
          <div className="escolher-opcoes" role="radiogroup" aria-label={t.rotulo}>
            {t.opcoes.map(o => {
              const marcada = (trocado[t.papel] || t.atual) === o.food_id;
              return (
                <button type="button" key={o.food_id} role="radio" aria-checked={marcada}
                        className={`escolher-chip${marcada ? " marcada" : ""}`}
                        data-testid={`opcao-${t.papel}-${o.food_id}`}
                        onClick={() => setTrocado(x => ({...x, [t.papel]: o.food_id}))}>
                  <span>{o.nome}</span>
                  {/* A porcao ao lado do nome, sempre: escolher sem ver quanto e
                      escolher no escuro, e foi a reclamacao do "100 g de whey". */}
                  <b>{o.gramas} g</b>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <p className={`escolher-conta${dentro ? "" : " fora"}`} data-testid="escolher-conta">
        {agora} kcal {dentro
          ? "— dentro da faixa."
          : `— ${diferenca > 0 ? "acima" : "abaixo"} da faixa em ${Math.abs(diferenca) - (alvo.tolerancia || 0)} kcal.`}
      </p>

      {erro && <p className="fg-erro" role="alert">{erro}</p>}

      <div className="escolher-acoes">
        <button type="button" className="fg-btn fg-btn-cheio" disabled={salvando || !escolhida}
                data-testid="confirmar-refeicao" onClick={confirmar}>
          <Check size={16} aria-hidden="true" /> {salvando ? "Salvando…" : "É essa"}
        </button>
        {onMontarDoZero && (
          <button type="button" className="fg-btn-2" data-testid="ir-montar-do-zero"
                  onClick={onMontarDoZero}>
            Quero montar do zero
          </button>
        )}
      </div>
    </section>
  );
}
