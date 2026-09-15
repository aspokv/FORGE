import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {Check, ChevronDown, Search, X} from "lucide-react";
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
  // Itens que a pessoa pesou: alimentos que existem no catalogo do diario e que o motor
  // nao sabe dimensionar, porque nao tem papel nem limite de porcao definidos.
  const [manuais, setManuais] = useState([]);
  const [sugestao, setSugestao] = useState(null);
  const [busca, setBusca] = useState("");
  const [achados, setAchados] = useState(null);
  const [buscando, setBuscando] = useState(false);

  useEffect(() => {
    let vivo = true;
    setDados(null); setEscolhidos([]); setPrevia(null); setAberto(null); setErro("");
    setManuais([]); setSugestao(null); setBusca(""); setAchados(null);
    axios.get(`${API}/nutrition/plan/draft/slots`, {params: {meal_index: mealIndex}})
      .then(r => {
        if (!vivo) return;
        setDados(r.data);
        const jaEscolhidos = (r.data.espacos || []).map(e => e.escolhido).filter(Boolean);
        setEscolhidos(jaEscolhidos);
        // Repetir o que a pessoa escolheu da ultima vez: montar cinco refeicoes do zero
        // toda semana cansa, e quem ja escolheu costuma repetir. O servidor so sugere
        // quando a refeicao esta vazia, nunca por cima de uma escolha atual.
        if (r.data.sugestao) {
          setSugestao(r.data.sugestao);
          setManuais(r.data.sugestao.manuais || []);
        }
        // O primeiro espaco vazio e obrigatorio ja abre: e onde a pessoa tem de agir, e
        // fazer ela tocar para descobrir isso seria um toque cobrado a toa.
        const primeiro = (r.data.espacos || []).find(e => e.obrigatorio && !e.escolhido);
        setAberto(primeiro ? primeiro.papel : null);
      })
      .catch(() => { if (vivo) setErro("Não foi possível abrir as opções desta refeição."); });
    return () => { vivo = false; };
  }, [API, mealIndex]);

  const recalcular = useCallback(async (ids, pesados) => {
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/compose`,
        {meal_index: mealIndex, food_ids: ids, manuais: pesados});
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
    recalcular(escolhidos, manuais);
    // O que a pessoa escolheu e o que ela pesou sao as unicas entradas reais: `dados` muda
    // como RESULTADO do recalculo, e incluir ele aqui faria o efeito chamar a si mesmo sem
    // parar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [escolhidos, manuais]);

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

  const procurar = async (texto) => {
    setBusca(texto);
    if (texto.trim().length < 2) { setAchados(null); return; }
    setBuscando(true);
    try {
      const r = await axios.get(`${API}/nutrition/plan/draft/search-food`,
        {params: {q: texto.trim()}});
      setAchados(r.data.foods || []);
    } catch { setAchados([]); }
    finally { setBuscando(false); }
  };

  /* Um alimento achado na busca entra de um jeito ou de outro, e a diferenca nao e
     escondida da pessoa: o que o motor sabe dimensionar entra com a grama calculada junto
     com o resto da refeicao; o que ele nao sabe entra com a grama que ELA informa. */
  const adicionarDaBusca = (alimento) => {
    setErro(""); setBusca(""); setAchados(null);
    if (alimento.dimensionavel) {
      setEscolhidos(atual => atual.includes(alimento.food_id) ? atual : [...atual, alimento.food_id]);
    } else {
      setManuais(atual => atual.some(m => m.food_id === alimento.food_id)
        ? atual
        : [...atual, {food_id: alimento.food_id, name: alimento.name, grams: 100}]);
    }
  };

  const mudarGrama = (foodId, valor) => {
    const n = Number(valor);
    setManuais(atual => atual.map(m =>
      m.food_id === foodId ? {...m, grams: Number.isFinite(n) && n > 0 ? n : m.grams} : m));
  };

  const removerAdicionado = (foodId) => {
    setErro("");
    setManuais(atual => atual.filter(m => m.food_id !== foodId));
    setEscolhidos(atual => atual.filter(f => f !== foodId));
  };

  const confirmar = async () => {
    setSalvando(true); setErro("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/choose`,
        {meal_index: mealIndex, archetype_id: "montado", food_ids: escolhidos, manuais});
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
  const pronto = falta.length === 0 && (escolhidos.length > 0 || manuais.length > 0);
  /* Passar da meta nao pode aparecer como barra cheia e "pronto". O motor dimensiona o que
     ele escolhe para fechar a conta, mas um item pesado pela pessoa entra por cima — e foi
     assim que a tela chegou a mostrar 870 de 760 kcal em verde. Confirmar continua liberado:
     a escolha e dela, e o numero e que precisa ser honesto. */
  const bruto = previa?.proporcao || 0;
  const passou = bruto > 1.05;
  const faltando = pronto && bruto < 0.9;
  const diferenca = Math.abs(Math.round(kcal - alvo));
  // Alimentos que nao aparecem em nenhum espaco: vieram da busca. Precisam de lugar
  // proprio, senao ficariam escolhidos e invisiveis.
  const nosEspacos = new Set((dados.espacos || []).map(e => e.escolhido).filter(Boolean));
  const avulsos = [
    ...(previa?.foods || []).filter(f => !nosEspacos.has(f.food_id) && !f.manual)
      .map(f => ({food_id: f.food_id, name: f.food?.name || f.food_id, grams: f.grams, pesado: false})),
    ...manuais.map(m => ({...m, pesado: true})),
  ];

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
        <b style={{width: `${proporcao * 100}%`}}
           className={passou ? "passou" : pronto && !faltando ? "cheia" : ""} />
      </div>
      <p className={passou ? "montar-falta montar-passou" : "montar-falta"}>
        {falta.length > 0
          ? <>Falta escolher: <b>{falta.join(", ")}</b></>
          : escolhidos.length === 0 && manuais.length === 0
            ? "Escolha o que você vai comer nesta refeição."
            : passou
              ? <><b>{diferenca} kcal</b> acima da meta desta refeição.</>
              : faltando
                ? <><b>{diferenca} kcal</b> abaixo da meta desta refeição.</>
                : "Pronto para confirmar."}
      </p>
    </div>

    {/*
      * A sugestao aparece como AVISO, e nao em silencio. Ver a refeicao ja preenchida sem
      * explicacao faria a pessoa achar que o aplicativo escolheu por ela.
      */}
    {sugestao && <p className="montar-sugestao" data-testid="montar-sugestao">
      {sugestao.texto}
      <button type="button" onClick={() => { setSugestao(null); setEscolhidos([]); setManuais([]); }}>
        Começar do zero
      </button>
    </p>}

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
                ? <>
                    {/* O nome cede e a grama nunca: era ela que aparecia cortada em "Ovo
                        inteiro · 5…", e o numero e justamente o dado da linha. */}
                    <span className="montar-espaco-alimento">{nomeEscolhido}</span>
                    {noPrato && <i>{noPrato.grams} g</i>}
                  </>
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

    {avulsos.length > 0 && <div className="montar-avulsos" data-testid="montar-avulsos">
      <p className="fg-etiqueta">Adicionados por você</p>
      {avulsos.map(item => (
        <div className="montar-avulso" key={item.food_id}>
          <span className="montar-avulso-nome">{item.name}</span>
          {/*
            * O que o motor sabe dimensionar mostra a grama calculada; o que ele nao sabe
            * abre um campo. Misturar os dois num campo editavel daria a entender que a
            * pessoa pode sobrescrever a conta da refeicao, e nao pode.
            */}
          {item.pesado ? (
            <label className="montar-avulso-grama">
              <input type="number" inputMode="decimal" min="1" max="2000"
                     value={item.grams}
                     aria-label={`Gramas de ${item.name}`}
                     data-testid={`grama-${item.food_id}`}
                     onChange={e => mudarGrama(item.food_id, e.target.value)} />
              <span>g</span>
            </label>
          ) : <span className="montar-avulso-calculado">{item.grams} g</span>}
          <button type="button" className="montar-avulso-tirar"
                  aria-label={`Remover ${item.name}`}
                  data-testid={`tirar-${item.food_id}`}
                  onClick={() => removerAdicionado(item.food_id)}>
            <X size={16} />
          </button>
        </div>
      ))}
    </div>}

    {/*
      * A busca e para quem ja sabe o que vai comer e nao quer rolar cinco espacos. Fica no
      * fim de proposito: a lista por funcao resolve para a maioria, e um campo de busca no
      * topo convidaria todo mundo a montar um prato de qualquer jeito.
      */}
    <div className="montar-busca">
      <label className="montar-busca-campo">
        <Search size={16} aria-hidden="true" />
        <input type="search" value={busca} placeholder="Buscar outro alimento"
               aria-label="Buscar outro alimento no catálogo"
               data-testid="montar-busca"
               onChange={e => procurar(e.target.value)} />
      </label>
      {buscando && <p className="montar-falta">Procurando...</p>}
      {achados && achados.length === 0 && !buscando &&
        <p className="montar-falta">Nenhum alimento com esse nome.</p>}
      {achados && achados.length > 0 && <ul className="montar-opcoes">
        {achados.map(alimento => (
          <li key={alimento.food_id}>
            <button type="button" className="montar-opcao"
                    data-testid={`achado-${alimento.food_id}`}
                    onClick={() => adicionarDaBusca(alimento)}>
              <span className="montar-opcao-nome">
                {alimento.name}
                {alimento.metodo && <em className="fg-selo-metodo">do método</em>}
                {!alimento.dimensionavel && <em className="montar-pesar">você pesa</em>}
              </span>
              <span className="montar-opcao-dado">{alimento.kcal_por_100g} kcal /100g</span>
            </button>
          </li>
        ))}
      </ul>}
    </div>

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
