import {useCallback, useEffect, useRef, useState} from "react";
import axios from "axios";
import {mensagemDeErro} from "./mensagemDeErro";
import "./periodizacao-da-dieta.css";

/**
 * Periodização da dieta (Elite): uma chave liga e desliga.
 *
 * Desligada, a pessoa escolhe o tipo — corte ou ganho, a duração e o ritmo — e vê na hora
 * as semanas e o que muda no prato. Ligou, já está valendo: não existe um segundo botão de
 * "começar", porque a chave É a decisão. Desligou, a fase para e o plano fica como está
 * na semana em que parou.
 *
 * Ligada, o carboidrato muda um degrau a cada 7 dias, na meta E nas porções; proteína,
 * gordura e verduras ficam. A balança da sexta pode segurar um degrau. As regras estão em
 * backend/periodizacao_automatica.py.
 */
const FASES = [
  {id: "corte", nome: "Corte", texto: "O carboidrato desce um degrau por semana."},
  {id: "ganho", nome: "Ganho de massa", texto: "O carboidrato sobe um degrau por semana."},
];
const DURACOES = [2, 4, 6, 8, 12];
const RITMOS = [{id: "suave", nome: "Suave"}, {id: "moderado", nome: "Moderado"}, {id: "forte", nome: "Forte"}];
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

function Semanas({tabela, semanaAtual, historico}) {
  const aplicadas = Object.fromEntries((historico || []).map(h => [h.semana, h]));
  return <ol className="pd-semanas" data-testid="pd-semanas">
    {tabela.map(l => {
      const estado = semanaAtual == null ? "" : l.semana < semanaAtual ? "passada" : l.semana === semanaAtual ? "atual" : "";
      return <li key={l.semana} className={`pd-semana ${estado}`}>
        <span className="pd-semana-n">Semana {l.semana}</span>
        <b>{kcal(l.kcal)} kcal</b>
        <span>Carbo {g(l.carbs_g)}</span>
        {aplicadas[l.semana]?.decisao === "segurar" && <em className="pd-segurou">segurou</em>}
        {l.travou && <em className="pd-travou" title={l.travou}>no piso</em>}
      </li>;
    })}
  </ol>;
}

function Prato({mudancas, testId}) {
  if (!mudancas?.length) return null;
  return <ul className="pd-prato" data-testid={testId}>
    {mudancas.map((m, i) => <li key={i}>{m.refeicao}: {m.alimento} {m.de} g → <b>{m.para} g</b></li>)}
  </ul>;
}

export default function PeriodizacaoDaDieta({API, compacto = false}) {
  const [estado, setEstado] = useState(null);
  const [falhou, setFalhou] = useState(false);
  const [fase, setFase] = useState(null);
  const [semanas, setSemanas] = useState(4);
  const [ritmo, setRitmo] = useState("moderado");
  const [previa, setPrevia] = useState(null);
  const [erroDaPrevia, setErroDaPrevia] = useState("");
  const [trocando, setTrocando] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const pedido = useRef(0);

  const carregar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/nutrition/periodizacao`);
      setEstado(r.data); setFalhou(false);
      setFase(f => f || r.data?.fase_sugerida || "corte");
    } catch { setFalhou(true); }
  }, [API]);
  useEffect(() => { carregar(); }, [carregar]);

  const ativa = estado?.periodizacao?.status === "ativa" ? estado.periodizacao : null;
  const podeConfigurar = !compacto && estado?.liberado && !ativa && fase;

  // A prévia acompanha cada escolha: é o que a pessoa vai ligar, visto antes de ligar.
  useEffect(() => {
    if (!podeConfigurar) return undefined;
    const meu = ++pedido.current;
    const t = setTimeout(async () => {
      try {
        const r = await axios.post(`${API}/nutrition/periodizacao/previa`, {fase, semanas, ritmo});
        if (meu === pedido.current) { setPrevia(r.data); setErroDaPrevia(""); }
      } catch (e) {
        if (meu === pedido.current) { setPrevia(null); setErroDaPrevia(mensagemDeErro(e, "Não foi possível montar a progressão.")); }
      }
    }, 250);
    return () => clearTimeout(t);
  }, [API, podeConfigurar, fase, semanas, ritmo]);

  if (compacto) {
    if (!ativa) return null;
    const ultima = (ativa.historico || [])[ativa.historico.length - 1];
    return <p className="pd-compacto" data-testid="pd-compacto">
      <b>Periodização ligada · semana {estado.semana_atual} de {ativa.semanas}</b>
      <span>{nomeDaFase(ativa.fase)} · carbo {g(ativa.tabela[ativa.degrau]?.carbs_g)} · {ultima?.motivo}</span>
    </p>;
  }
  if (falhou) return null;
  if (!estado) return <section className="pd" aria-busy="true"><p className="muted">Carregando periodização…</p></section>;

  const liberado = !!estado.liberado;
  const ligada = !!ativa;
  const podeLigar = liberado && (ligada || (previa && !erroDaPrevia));

  const alternar = async () => {
    if (trocando || !podeLigar) return;
    setTrocando(true); setErro(""); setAviso("");
    try {
      if (ligada) {
        await axios.post(`${API}/nutrition/periodizacao/encerrar`);
        setAviso("Periodização desligada. Seu plano ficou como estava nesta semana.");
      } else {
        await axios.post(`${API}/nutrition/periodizacao/ativar`, {fase, semanas, ritmo});
        setAviso(`Ligada: ${semanas} semanas de ${nomeDaFase(fase).toLowerCase()}. A semana 1 é a sua dieta como está.`);
      }
      setPrevia(null);
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e, ligada ? "Não foi possível desligar." : "Não foi possível ligar a periodização."));
    } finally { setTrocando(false); }
  };

  const anterior = estado.periodizacao;
  const atual = ativa && (ativa.tabela[ativa.degrau] || ativa.tabela[0]);
  const ultima = ativa && (ativa.historico || [])[ativa.historico.length - 1];

  return <section className={`pd${ligada ? " pd-ligada" : ""}`} data-testid={ligada ? "pd-ativa" : liberado ? "pd-configurar" : "pd-bloqueado"}>
    <div className="pd-cabeca">
      <div>
        <p className="fg-etiqueta">PERIODIZAÇÃO DA DIETA · ELITE</p>
        <strong className="pd-titulo">
          {ligada ? `${nomeDaFase(ativa.fase)} · semana ${estado.semana_atual} de ${ativa.semanas}` : "Seu plano anda sozinho, semana a semana"}
        </strong>
      </div>
      <button type="button" role="switch" aria-checked={ligada} aria-label="Periodização da dieta"
              className="pd-chave" data-testid="pd-chave" aria-busy={trocando}
              disabled={trocando || !podeLigar} onClick={alternar}>
        <span className="pd-chave-trilho"><span className="pd-chave-bola"/></span>
        <span className="pd-chave-texto">{ligada ? "Ligada" : "Desligada"}</span>
      </button>
    </div>

    {aviso && <p className="pd-aviso" role="status" data-testid="pd-aviso">{aviso}</p>}
    {erro && <p className="fg-erro" role="alert">{erro}</p>}

    {!liberado && <p>Escolha 2 a 12 semanas de corte ou de ganho de massa e ligue a chave: o FORGE ajusta o
      carboidrato da meta e das suas refeições a cada semana, segurando quando o peso anda rápido
      demais. Disponível no plano Elite.</p>}

    {ligada && <>
      <p className="pd-meta">{kcal(atual.kcal)} kcal · Proteína {g(atual.protein_g)} · Carbo {g(atual.carbs_g)} · Gordura {g(atual.fat_g)}</p>
      {ultima?.motivo && <p className="pd-motivo" data-testid="pd-motivo">{ultima.motivo}</p>}
      <Prato mudancas={ultima?.mudancas} testId="pd-prato"/>
      <Semanas tabela={ativa.tabela} semanaAtual={estado.semana_atual} historico={ativa.historico}/>
      <p className="pd-nota">{nomeDaFase(ativa.fase)} {ativa.ritmo}. O degrau muda a cada 7 dias, quando você abre a nutrição.
        Pese toda sexta: é a balança que segura um degrau quando o peso anda rápido demais.
        Para trocar o tipo, desligue e escolha de novo.</p>
    </>}

    {liberado && !ligada && <>
      {anterior?.status === "concluida" && <p className="pd-motivo">Sua fase de {nomeDaFase(anterior.fase).toLowerCase()} de {anterior.semanas} semanas terminou. O plano ficou na última semana.</p>}
      <p>Escolha o tipo e ligue a chave. A semana 1 é a sua dieta como está; a partir da 2 o carboidrato
        muda um degrau por semana, na meta e nas porções. Proteína, gordura e verduras não mudam.</p>
      <span className="fg-etiqueta">Fase</span>
      <Chips nome="fase" opcoes={FASES} valor={fase} desabilitado={trocando} onEscolher={setFase}/>
      <small className="pd-dica">{FASES.find(f => f.id === fase)?.texto}</small>
      <span className="fg-etiqueta">Duração</span>
      <Chips nome="semanas" opcoes={DURACOES.map(n => ({id: n, nome: `${n} semanas`}))} valor={semanas}
             desabilitado={trocando} onEscolher={setSemanas}/>
      <span className="fg-etiqueta">Ritmo</span>
      <Chips nome="ritmo" opcoes={RITMOS} valor={ritmo} desabilitado={trocando} onEscolher={setRitmo}/>

      {erroDaPrevia && <p className="fg-erro" role="alert" data-testid="pd-erro-previa">{erroDaPrevia}</p>}
      {previa && !erroDaPrevia && <div className="pd-previa" data-testid="pd-previa">
        <p>Degrau de {previa.passo_kcal} kcal por semana. Carboidrato nunca abaixo de {previa.piso_carbo_g} g.</p>
        <Semanas tabela={previa.tabela}/>
        {previa.no_prato?.length > 0 && <span className="fg-etiqueta">No prato, na última semana</span>}
        <Prato mudancas={previa.no_prato} testId="pd-prato-previa"/>
      </div>}
    </>}
  </section>;
}
