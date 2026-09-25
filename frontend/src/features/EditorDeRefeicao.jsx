import {useEffect, useState} from "react";
import axios from "axios";
import {buscarNoCatalogo} from "./buscaDeAlimentos";
import {mensagemDeErro} from "./mensagemDeErro";
import "./food-diary.css";
import "./acrescentar-refeicao.css";
import "./editor-de-refeicao.css";

/**
 * Montar uma refeição do jeito da pessoa (Elite): o nome, os alimentos e as gramas.
 *
 * O pedido foi "total livre arbítrio": excluir o café da manhã, criar de novo e botar o
 * que quiser. Aqui o motor não propõe nem redimensiona — a pessoa decide, e a tela mostra
 * quanto aquilo dá antes de salvar. Serve para criar uma refeição nova e para refazer uma
 * que já existe.
 *
 * A busca é só no catálogo do FORGE: alimento de fonte externa não tem lugar no plano, e
 * aceitar na tela para recusar ao salvar seria pior que não oferecer.
 */
const SUGESTOES = ["Café da manhã", "Almoço", "Lanche", "Jantar", "Ceia", "Pré-treino", "Pós-treino"];
const MAX_ITENS = 12;
const MACROS = ["kcal", "protein_g", "carbs_g", "fat_g"];

export function itensDaRefeicao(refeicao) {
  return (refeicao?.foods || []).map(f => ({
    food_id: f.food_id, nome: f.food?.name || f.food_id, gramas: f.grams, base: f.food || {},
  }));
}

export function totaisDosItens(itens) {
  const soma = {kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0};
  for (const item of itens || []) {
    const base = item.base || {};
    const fator = Number(item.gramas || 0) / (Number(base.grams) || 100);
    MACROS.forEach(m => { soma[m] += (Number(base[m]) || 0) * fator; });
  }
  return soma;
}

const gramaValida = g => Number.isFinite(Number(g)) && Number(g) > 0 && Number(g) <= 2000;

export default function EditorDeRefeicao({API, modo = "criar", refeicao, indice, refeicoes = [], dia, onSalvo, onFechar}) {
  const editando = modo === "editar";
  const [catalogo, setCatalogo] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [nome, setNome] = useState(editando ? refeicao?.name || "" : "");
  const [posicao, setPosicao] = useState(refeicoes.length);
  const [itens, setItens] = useState(() => (editando ? itensDaRefeicao(refeicao) : []));
  const [busca, setBusca] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    const c = new AbortController();
    axios.get(`${API}/nutrition/consumed-foods`, {signal: c.signal})
      .then(r => setCatalogo(r.data?.foods || []))
      .catch(() => { if (!c.signal.aborted) setErro("Não foi possível carregar o catálogo. Feche e tente de novo."); })
      .finally(() => { if (!c.signal.aborted) setCarregando(false); });
    return () => c.abort();
  }, [API]);

  const termo = busca.trim();
  const {itens: achados, aproximado} = termo.length >= 2 ? buscarNoCatalogo(catalogo, termo) : {itens: [], aproximado: false};
  const escolhidos = new Set(itens.map(i => i.food_id));
  const resultados = achados.filter(f => !escolhidos.has(f.id)).slice(0, 8);
  const totais = totaisDosItens(itens);
  const podeSalvar = nome.trim().length >= 2 && itens.length > 0 && itens.every(i => gramaValida(i.gramas));

  const acrescentar = alimento => {
    setItens(v => [...v, {food_id: alimento.id, nome: alimento.name, gramas: 100, base: alimento}]);
    setBusca(""); setErro("");
  };

  const salvar = async () => {
    if (salvando || !podeSalvar) return;
    setSalvando(true); setErro("");
    const corpo = {nome: nome.trim(), dia,
                   itens: itens.map(i => ({food_id: i.food_id, grams: Number(i.gramas)}))};
    try {
      const r = editando
        ? await axios.put(`${API}/nutrition/plan/meals/${indice}`, {...corpo, nome_atual: refeicao?.name})
        : await axios.post(`${API}/nutrition/plan/meals`, {...corpo, posicao});
      if (!Array.isArray(r.data?.plan?.meals)) throw new Error("plano sem refeições");
      onSalvo(r.data.plan);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível salvar a refeição. Suas escolhas continuam aqui; tente de novo."));
    } finally { setSalvando(false); }
  };

  return <section className="food-diary-editor editor-de-refeicao" data-testid="editor-de-refeicao"
                  aria-label={editando ? `Montar ${refeicao?.name}` : "Nova refeição"}>
    <h3>{editando ? `Montar ${refeicao?.name} do seu jeito` : "Nova refeição"}</h3>
    <p>Você escolhe os alimentos e as gramas. O FORGE não redimensiona esta refeição.</p>

    <label className="acrescentar-campo">
      <span className="fg-etiqueta">Nome da refeição</span>
      <input type="text" value={nome} maxLength={40} placeholder="Café da manhã" disabled={salvando}
             data-testid="editor-nome" onChange={e => { setNome(e.target.value); setErro(""); }}/>
    </label>
    <div className="acrescentar-sugestoes">
      {SUGESTOES.map(s => (
        <button type="button" key={s} className="acrescentar-sugestao" disabled={salvando}
                onClick={() => { setNome(s); setErro(""); }}>{s}</button>
      ))}
    </div>

    {!editando && <div className="acrescentar-onde">
      <span className="fg-etiqueta">Onde ela entra</span>
      <div className="acrescentar-posicoes">
        <button type="button" aria-pressed={posicao === 0} data-testid="editor-posicao-0"
                className={posicao === 0 ? "acrescentar-posicao marcada" : "acrescentar-posicao"}
                onClick={() => setPosicao(0)}>Antes de {refeicoes[0]?.name || "tudo"}</button>
        {refeicoes.map((r, i) => (
          <button type="button" key={r.name + i} aria-pressed={posicao === i + 1}
                  data-testid={`editor-posicao-${i + 1}`}
                  className={posicao === i + 1 ? "acrescentar-posicao marcada" : "acrescentar-posicao"}
                  onClick={() => setPosicao(i + 1)}>Depois de {r.name}</button>
        ))}
      </div>
    </div>}

    <span className="fg-etiqueta">Alimentos</span>
    {!itens.length && <p className="editor-vazio">Nenhum alimento ainda. Busque abaixo e toque para acrescentar.</p>}
    {itens.map((item, i) => (
      <div className="food-diary-item" key={`${item.food_id}-${i}`} data-testid={`editor-item-${i}`}>
        <div><strong>{item.nome}</strong></div>
        <label>Gramas
          <input type="number" min="1" max="2000" step="any" value={item.gramas} disabled={salvando}
                 aria-label={`Gramas de ${item.nome}`} data-testid={`editor-gramas-${i}`}
                 onChange={e => setItens(v => v.map((x, j) => j === i ? {...x, gramas: e.target.value} : x))}/>
        </label>
        <button type="button" disabled={salvando} aria-label={`Tirar ${item.nome}`}
                data-testid={`editor-tirar-${i}`}
                onClick={() => setItens(v => v.filter((_, j) => j !== i))}>Tirar</button>
      </div>
    ))}

    <label>Acrescentar alimento
      <input enterKeyHint="search" value={busca} placeholder="Arroz, frango, ovo…"
             data-testid="editor-busca" disabled={salvando || itens.length >= MAX_ITENS}
             onChange={e => setBusca(e.target.value)}
             onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); } }}/>
    </label>
    {carregando ? <p role="status">Carregando catálogo…</p> : termo.length >= 2 && (
      <div className="food-diary-results">
        {resultados.map(f => (
          <button key={f.id} type="button" disabled={salvando} data-testid={`editor-resultado-${f.id}`}
                  onClick={() => acrescentar(f)}>
            {f.name}<small>{f.kcal} kcal / {f.grams || 100} g</small>
          </button>
        ))}
        {aproximado && resultados.length > 0 && <p className="food-diary-aproximado" role="status">
          Nada exato para “{termo}”. Estes são os mais parecidos — confira o nome.</p>}
        {!resultados.length && <p>Nenhum alimento com esse nome. Confira a grafia ou busque pelo ingrediente.</p>}
      </div>
    )}

    <p className="food-diary-total" aria-live="polite" data-testid="editor-totais">
      {Math.round(totais.kcal)} kcal · P {Math.round(totais.protein_g)} g · C {Math.round(totais.carbs_g)} g · G {Math.round(totais.fat_g)} g
    </p>
    {erro && <p className="fg-erro" role="alert">{erro}</p>}

    <div className="food-diary-acoes">
      <button type="button" className="fg-btn fg-btn-cheio" data-testid="editor-salvar"
              disabled={salvando || !podeSalvar} onClick={salvar}>
        {salvando ? "Salvando…" : editando ? "Salvar refeição" : "Criar refeição"}
      </button>
      <button type="button" className="fg-btn fg-btn-2" disabled={salvando} onClick={onFechar}>Cancelar</button>
    </div>
  </section>;
}
