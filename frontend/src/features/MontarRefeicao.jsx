import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {Check, ChevronDown} from "lucide-react";
import "./montar-refeicao.css";

/**
 * Montar a refeicao escolhendo alimento por alimento.
 *
 * A diferenca para o que ja existia: ali a pessoa escolhia uma COMBINACAO pronta e depois
 * trocava item por item. Aqui ela comeca do zero e ve a barra encher enquanto escolhe.
 *
 * Por que a lista e separada por funcao do prato, e nao uma lista unica com tudo: esta
 * escrito no motor, em maiusculas, que macro ajusta a refeicao e nao inventa a refeicao.
 * Escolha livre de uma lista so produz prato que fecha o numero e nao e comida. Separado por
 * funcao, a liberdade continua e o prato absurdo nao acontece.
 *
 * Quem decide a GRAMA e sempre o servidor. A tela manda quais alimentos foram escolhidos e
 * recebe de volta a porcao calculada — nunca o contrario. Calcular porcao aqui criaria um
 * segundo numero para a mesma pergunta, que foi exatamente o defeito corrigido na meta do
 * carboidrato do dia.
 */
export default function MontarRefeicao({API, mealIndex, onPronto, onCancelar}) {
  const [dados, setDados] = useState(null);
  const [escolhidos, setEscolhidos] = useState([]);
  const [previa, setPrevia] = useState(null);
  const [aberto, setAberto] = useState(null);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let vivo = true;
    setDados(null); setEscolhidos([]); setPrevia(null); setAberto(null); setErro("");
    axios.get(`${API}/nutrition/plan/draft/slots`, {params: {meal_index: mealIndex}})
      .then(r => {
        if (!vivo) return;
        setDados(r.data);
        const jaEscolhidos = (r.data.espacos || []).map(e => e.escolhido).filter(Boolean);
        setEscolhidos(jaEscolhidos);
        // O primeiro espaco vazio e obrigatorio ja abre: e onde a pessoa tem de agir, e
        // fazer ela tocar para descobrir isso seria um toque cobrado a toa.
        const primeiro = (r.data.espacos || []).find(e => e.obrigatorio && !e.escolhido);
        setAberto(primeiro ? primeiro.papel : null);
      })
      .catch(() => { if (vivo) setErro("Não foi possível abrir as opções desta refeição."); });
    return () => { vivo = false; };
  }, [API, mealIndex]);

  const recalcular = useCallback(async (ids) => {
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/compose`,
        {meal_index: mealIndex, food_ids: ids});
      setPrevia(r.data);
      // Os espacos voltam junto com a previa porque escolher um alimento muda as OUTRAS
      // listas: o que entrou na proteina some da proteina extra.
      setDados(d => d ? {...d, espacos: r.data.espacos, falta: r.data.falta} : d);
    } catch {
      setErro("Não foi possível calcular as porções agora.");
    }
  }, [API, mealIndex]);

  useEffect(() => {
    if (!dados) return;
    recalcular(escolhidos);
    // `escolhidos` e a unica entrada real: `dados` muda como RESULTADO do recalculo, e
    // incluir ele aqui faria o efeito chamar a si mesmo sem parar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [escolhidos]);

  const alternar = (papel, foodId) => {
    setErro("");
    setEscolhidos(atual => {
      const doEspaco = (dados?.espacos || []).find(e => e.papel === papel);
      const anterior = doEspaco?.escolhido;
      // Um alimento por espaco: tocar noutro TROCA, e nao soma. Somar dois carboidratos no
      // mesmo espaco e o caminho mais curto para o prato incoerente.
      const sem = atual.filter(f => f !== anterior && f !== foodId);
      return foodId === anterior ? sem : [...sem, foodId];
    });
  };

  const confirmar = async () => {
    setSalvando(true); setErro("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/choose`,
        {meal_index: mealIndex, archetype_id: "montado", food_ids: escolhidos});
      onPronto(r.data);
    } catch {
      setErro("Não foi possível salvar esta refeição. Tente de novo.");
    } finally { setSalvando(false); }
  };

  if (erro && !dados) return <p className="fg-erro" role="alert">{erro}</p>;
  if (!dados) return <div className="fg-esqueleto" aria-label="Carregando as opções" />;

  const kcal = Math.round(previa?.totais?.kcal || 0);
  const alvo = previa?.alvo || dados.target_cal || 0;
  const proporcao = Math.min(1, previa?.proporcao || 0);
  const falta = dados.falta || [];
  const pronto = falta.length === 0 && escolhidos.length > 0;

  return <section className="montar" data-testid="montar-refeicao">
    {/*
      * O alvo fica grudado no topo enquanto a pessoa rola as listas. Sem isso ela escolhe
      * um alimento, rola para ver o proximo espaco, e perde de vista justamente o numero
      * que ela esta tentando fechar.
      */}
    <div className="montar-alvo">
      <div className="montar-alvo-linha">
        <b data-testid="montar-kcal">{kcal}</b>
        <span>de {Math.round(alvo)} kcal</span>
      </div>
      <div className="montar-barra" role="progressbar"
           aria-valuenow={kcal} aria-valuemin={0} aria-valuemax={Math.round(alvo)}
           aria-label={`${kcal} de ${Math.round(alvo)} kcal`}>
        <b style={{width: `${proporcao * 100}%`}} className={pronto ? "cheia" : ""} />
      </div>
      <p className="montar-falta">
        {falta.length > 0
          ? <>Falta escolher: <b>{falta.join(", ")}</b></>
          : escolhidos.length === 0
            ? "Escolha o que você vai comer nesta refeição."
            : "Pronto para confirmar."}
      </p>
    </div>

    {dados.espacos.map(espaco => {
      const escolhido = espaco.escolhido;
      const nomeEscolhido = escolhido
        ? (espaco.alimentos.find(a => a.food_id === escolhido)?.name || escolhido)
        : null;
      const noPrato = (previa?.foods || []).find(f => f.food_id === escolhido);
      const estaAberto = aberto === espaco.papel;
      return (
        <div className={`montar-espaco${escolhido ? " preenchido" : ""}`} key={espaco.papel}>
          <button type="button" className="montar-espaco-topo"
                  aria-expanded={estaAberto}
                  data-testid={`espaco-${espaco.papel}`}
                  onClick={() => setAberto(p => p === espaco.papel ? null : espaco.papel)}>
            <span className="montar-espaco-nome">
              <b>{espaco.rotulo}</b>
              {!espaco.obrigatorio && <em>opcional</em>}
            </span>
            <span className="montar-espaco-valor">
              {/* A grama so aparece depois que o servidor calculou. Antes disso nao existe
                  numero nenhum para mostrar, e inventar um seria mentir. */}
              {nomeEscolhido
                ? <>{nomeEscolhido}{noPrato && <i> · {noPrato.grams} g</i>}</>
                : <span className="montar-vazio">escolher</span>}
            </span>
            <ChevronDown size={16} className={estaAberto ? "girado" : ""} aria-hidden="true" />
          </button>

          {estaAberto && <ul className="montar-opcoes">
            {espaco.alimentos.map(alimento => {
              const marcado = alimento.food_id === escolhido;
              return (
                <li key={alimento.food_id}>
                  <button type="button" aria-pressed={marcado}
                          className={marcado ? "montar-opcao marcada" : "montar-opcao"}
                          data-testid={`opcao-${alimento.food_id}`}
                          onClick={() => alternar(espaco.papel, alimento.food_id)}>
                    <span className="montar-opcao-nome">
                      {alimento.name}
                      {alimento.metodo && <em className="fg-selo-metodo">do método</em>}
                    </span>
                    <span className="montar-opcao-dado">{alimento.kcal_por_100g} kcal /100g</span>
                    {marcado && <Check size={16} aria-hidden="true" />}
                  </button>
                </li>
              );
            })}
          </ul>}
        </div>
      );
    })}

    {erro && <p className="fg-erro" role="alert">{erro}</p>}

    <div className="fg-guiado-acoes">
      <button type="button" className="fg-btn fg-btn-cheio" disabled={!pronto || salvando}
              onClick={confirmar} data-testid="confirmar-montagem">
        {salvando ? "Salvando..." : "Confirmar esta refeição"} <Check size={18} />
      </button>
      <button type="button" className="fg-guiado-cancelar" onClick={onCancelar} disabled={salvando}>
        Ver combinações prontas
      </button>
    </div>
  </section>;
}
