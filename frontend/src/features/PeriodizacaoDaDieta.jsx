import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {mensagemDeErro} from "./mensagemDeErro";
import "./periodizacao-da-dieta.css";

/**
 * Periodização da dieta (Elite): o plano anda sozinho, semana a semana.
 *
 * No corte o carboidrato desce um degrau por semana; no ganho, sobe. A proteína e a
 * gordura ficam. O degrau entra na meta E nas porções das refeições — "carboidrato
 * 190 g" não diz nada no almoço, "batata 250 g → 205 g" diz. A balança da sexta pode
 * segurar um degrau quando o peso anda rápido demais. As regras estão em
 * backend/periodizacao_automatica.py.
 */
const FASES = [
  {id: "corte", nome: "Corte", texto: "O carboidrato desce um degrau por semana."},
  {id: "ganho", nome: "Ganho de massa", texto: "O carboidrato sobe um degrau por semana."},
];
const DURACOES = [2, 4, 6, 8, 12];
const RITMOS = [
  {id: "suave", nome: "Suave"}, {id: "moderado", nome: "Moderado"}, {id: "forte", nome: "Forte"},
];
const nomeDaFase = f => (f === "ganho" ? "Ganho de massa" : "Corte");
const kcal = n => Math.round(Number(n) || 0).toLocaleString("pt-BR");
const g = n => `${Math.round(Number(n) || 0)} g`;

function Chips({opcoes, valor, onEscolher, nome, desabilitado}) {
  return <div className="pd-chips" role="radiogroup" aria-label={nome}>
    {opcoes.map(o => (
      <button type="button" key={o.id} role="radio" aria-checked={valor === o.id} disabled={desabilitado}
              className={valor === o.id ? "pd-chip marcado" : "pd-chip"} data-testid={`pd-${nome}-${o.id}`}
              onClick={() => onEscolher(o.id)}>{o.nome}</button>
    ))}
  </div>;
}

function Tabela({tabela, semanaAtual, historico}) {
  const aplicadas = Object.fromEntries((historico || []).map(h => [h.semana, h]));
  return <ol className="pd-semanas" data-testid="pd-semanas">
    {tabela.map(l => {
      const h = aplicadas[l.semana];
      const estado = semanaAtual == null ? "" : l.semana < semanaAtual ? "passada" : l.semana === semanaAtual ? "atual" : "";
      return <li key={l.semana} className={`pd-semana ${estado}`}>
        <span className="pd-semana-n">Semana {l.semana}</span>
        <b>{kcal(l.kcal)} kcal</b>
        <span>Carbo {g(l.carbs_g)}</span>
        {h?.decisao === "segurar" && <em className="pd-segurou">segurou</em>}
        {l.travou && <em className="pd-travou" title={l.travou}>no piso</em>}
      </li>;
    })}
  </ol>;
}

export default function PeriodizacaoDaDieta({API, compacto = false}) {
  const [estado, setEstado] = useState(null);
  const [falhou, setFalhou] = useState(false);
  const [fase, setFase] = useState(null);
  const [semanas, setSemanas] = useState(4);
  const [ritmo, setRitmo] = useState("moderado");
  const [previa, setPrevia] = useState(null);
  const [ocupado, setOcupado] = useState("");
  const [erro, setErro] = useState("");
  const [confirmarFim, setConfirmarFim] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/nutrition/periodizacao`);
      setEstado(r.data); setFalhou(false);
      setFase(f => f || r.data?.fase_sugerida || "corte");
    } catch { setFalhou(true); }
  }, [API]);
  useEffect(() => { carregar(); }, [carregar]);

  const ativa = estado?.periodizacao?.status === "ativa" ? estado.periodizacao : null;

  if (compacto) {
    if (!ativa) return null;
    const ultima = (ativa.historico || [])[ativa.historico.length - 1];
    return <p className="pd-compacto" data-testid="pd-compacto">
      <b>Periodização · semana {estado.semana_atual} de {ativa.semanas}</b>
      <span>{nomeDaFase(ativa.fase)} · carbo {g(ativa.tabela[ativa.degrau]?.carbs_g)} · {ultima?.motivo}</span>
    </p>;
  }
  if (falhou) return null;
  if (!estado) return <section className="pd" aria-busy="true"><p className="muted">Carregando periodização…</p></section>;

  if (!estado.liberado) {
    return <section className="pd pd-bloqueado" data-testid="pd-bloqueado">
      <p className="fg-etiqueta">ELITE</p>
      <strong>Periodização da dieta</strong>
      <p>Escolha 2 a 12 semanas de corte ou de ganho de massa, e o FORGE ajusta o carboidrato
        da meta e das suas refeições a cada semana, segurando quando o peso anda rápido demais.</p>
    </section>;
  }

  const verPrevia = async () => {
    setOcupado("previa"); setErro("");
    try { setPrevia((await axios.post(`${API}/nutrition/periodizacao/previa`, {fase, semanas, ritmo})).data); }
    catch (e) { setPrevia(null); setErro(mensagemDeErro(e, "Não foi possível montar a progressão.")); }
    finally { setOcupado(""); }
  };
  const comecar = async () => {
    setOcupado("ativar"); setErro("");
    try { await axios.post(`${API}/nutrition/periodizacao/ativar`, {fase, semanas, ritmo}); setPrevia(null); await carregar(); }
    catch (e) { setErro(mensagemDeErro(e, "Não foi possível começar a periodização.")); }
    finally { setOcupado(""); }
  };
  const encerrar = async () => {
    setOcupado("encerrar"); setErro("");
    try { await axios.post(`${API}/nutrition/periodizacao/encerrar`); setConfirmarFim(false); await carregar(); }
    catch (e) { setErro(mensagemDeErro(e, "Não foi possível encerrar.")); }
    finally { setOcupado(""); }
  };

  if (ativa) {
    const atual = ativa.tabela[ativa.degrau] || ativa.tabela[0];
    const ultima = (ativa.historico || [])[ativa.historico.length - 1];
    return <section className="pd" data-testid="pd-ativa">
      <p className="fg-etiqueta">PERIODIZAÇÃO DA DIETA · {nomeDaFase(ativa.fase).toUpperCase()} {ativa.ritmo.toUpperCase()}</p>
      <strong className="pd-titulo">Semana {estado.semana_atual} de {ativa.semanas}</strong>
      <p className="pd-meta">{kcal(atual.kcal)} kcal · Proteína {g(atual.protein_g)} · Carbo {g(atual.carbs_g)} · Gordura {g(atual.fat_g)}</p>
      {ultima?.motivo && <p className="pd-motivo" data-testid="pd-motivo">{ultima.motivo}</p>}
      {ultima?.mudancas?.length > 0 && <ul className="pd-prato" data-testid="pd-prato">
        {ultima.mudancas.map((m, i) => <li key={i}>{m.refeicao}: {m.alimento} {m.de} g → <b>{m.para} g</b></li>)}
      </ul>}
      <Tabela tabela={ativa.tabela} semanaAtual={estado.semana_atual} historico={ativa.historico}/>
      <p className="pd-nota">O degrau muda a cada 7 dias, quando você abre a nutrição. Pese toda sexta:
        é a balança que segura um degrau quando o peso anda rápido demais.</p>
      {erro && <p className="fg-erro" role="alert">{erro}</p>}
      {!confirmarFim
        ? <button type="button" className="fg-btn fg-btn-2" data-testid="pd-encerrar" onClick={() => setConfirmarFim(true)}>Encerrar a periodização</button>
        : <div className="pd-confirmar">
            <p>Encerrar agora? Seu plano fica como está nesta semana.</p>
            <button type="button" className="fg-btn fg-btn-cheio" data-testid="pd-encerrar-confirmar" disabled={!!ocupado} onClick={encerrar}>
              {ocupado === "encerrar" ? "Encerrando…" : "Encerrar"}</button>
            <button type="button" className="fg-btn fg-btn-2" disabled={!!ocupado} onClick={() => setConfirmarFim(false)}>Continuar a fase</button>
          </div>}
    </section>;
  }

  const anterior = estado.periodizacao;
  return <section className="pd" data-testid="pd-configurar">
    <p className="fg-etiqueta">PERIODIZAÇÃO DA DIETA · ELITE</p>
    <strong className="pd-titulo">Seu plano anda sozinho, semana a semana</strong>
    {anterior?.status === "concluida" && <p className="pd-motivo">Sua fase de {nomeDaFase(anterior.fase).toLowerCase()} de {anterior.semanas} semanas terminou. O plano ficou na última semana.</p>}
    <p>A semana 1 é a sua dieta como está. A partir da 2, o carboidrato muda um degrau por semana,
      na meta e nas porções. Proteína, gordura e verduras não mudam.</p>

    <span className="fg-etiqueta">Fase</span>
    <Chips nome="fase" opcoes={FASES} valor={fase} desabilitado={!!ocupado} onEscolher={v => { setFase(v); setPrevia(null); }}/>
    <small className="pd-dica">{FASES.find(f => f.id === fase)?.texto}</small>
    <span className="fg-etiqueta">Duração</span>
    <Chips nome="semanas" opcoes={DURACOES.map(n => ({id: n, nome: `${n} semanas`}))} valor={semanas}
           desabilitado={!!ocupado} onEscolher={v => { setSemanas(v); setPrevia(null); }}/>
    <span className="fg-etiqueta">Ritmo</span>
    <Chips nome="ritmo" opcoes={RITMOS} valor={ritmo} desabilitado={!!ocupado} onEscolher={v => { setRitmo(v); setPrevia(null); }}/>

    {erro && <p className="fg-erro" role="alert">{erro}</p>}
    {!previa && <button type="button" className="fg-btn fg-btn-cheio" data-testid="pd-ver-previa" disabled={!!ocupado} onClick={verPrevia}>
      {ocupado === "previa" ? "Montando…" : "Ver a progressão"}</button>}

    {previa && <div className="pd-previa" data-testid="pd-previa">
      <p>Degrau de {previa.passo_kcal} kcal por semana. Carboidrato nunca abaixo de {previa.piso_carbo_g} g.</p>
      <Tabela tabela={previa.tabela}/>
      {previa.no_prato?.length > 0 && <>
        <span className="fg-etiqueta">No prato, na última semana</span>
        <ul className="pd-prato">{previa.no_prato.map((m, i) => <li key={i}>{m.refeicao}: {m.alimento} {m.de} g → <b>{m.para} g</b></li>)}</ul>
      </>}
      <button type="button" className="fg-btn fg-btn-cheio" data-testid="pd-comecar" disabled={!!ocupado} onClick={comecar}>
        {ocupado === "ativar" ? "Começando…" : `Começar ${semanas} semanas de ${nomeDaFase(fase).toLowerCase()}`}</button>
    </div>}
  </section>;
}
