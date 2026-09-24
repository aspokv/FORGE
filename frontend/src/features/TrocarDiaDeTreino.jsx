import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {CalendarSync, Check, Undo2} from "lucide-react";
import {mensagemDeErro} from "./mensagemDeErro";
import "./trocar-dia.css";

/**
 * Treinar hoje, e descansar noutro dia.
 *
 * Um atleta ia viajar no fim de semana e quis adiantar o treino de sábado para a quinta,
 * que na agenda dele é descanso. Não havia como: a tela de descanso não tem sessão, nem
 * lista de exercícios, nem botão de iniciar, e o único caminho oferecido era a Biblioteca
 * — que SUBSTITUI a sessão ativa. Resolver uma semana atípica exigia mexer no programa.
 *
 * A troca é uma exceção datada por cima do programa: vale para aquelas duas datas, vence
 * sozinha, e o programa continua sendo a verdade. Quem quer treinar em outros dias TODA
 * semana está pedindo outro programa, e isso se resolve na avaliação — não aqui.
 */

const NOMES = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

/** "quinta, 24/09" a partir de "2026-09-24", sem fuso no caminho.
 *
 * `new Date("2026-09-24")` é interpretado como UTC e, num fuso a oeste, volta um dia —
 * a tela diria "quarta" para a data que o servidor chamou de quinta. Montar a data pelos
 * três números evita isso inteiro. */
export function porExtenso(iso) {
  const [a, m, d] = String(iso || "").split("-").map(Number);
  if (!a || !m || !d) return String(iso || "");
  const data = new Date(a, m - 1, d);
  return `${NOMES[data.getDay()]}, ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

export default function TrocarDiaDeTreino({API, aoTrocar, axiosCliente = axios}) {
  const [estado, setEstado] = useState("carregando");
  const [dias, setDias] = useState([]);
  const [trocas, setTrocas] = useState([]);
  const [motivo, setMotivo] = useState("");
  const [escolhido, setEscolhido] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    setEstado("carregando");
    try {
      const r = await axiosCliente.get(`${API}/workout/trocas-de-dia`);
      setDias(r.data.dias || []);
      setTrocas(r.data.trocas || []);
      setMotivo(r.data.motivo || "");
      setEstado(r.data.disponivel ? "pronto" : "indisponivel");
    } catch (e) {
      setEstado("erro");
      setErro(mensagemDeErro(e, "Não foi possível carregar os seus dias."));
    }
  }, [API, axiosCliente]);

  useEffect(() => { carregar(); }, [carregar]);

  const hoje = dias[0]?.data;
  // Só os dias que TÊM treino podem ceder a sessão — e hoje não entra na lista, porque
  // trocar hoje por hoje não é troca.
  const candidatos = dias.filter(d => d.treino && d.data !== hoje);

  const trocar = async () => {
    if (!escolhido || enviando) return;
    setEnviando(true); setErro("");
    try {
      const r = await axiosCliente.post(`${API}/workout/trocar-dia`,
                                        {treinar_em: hoje, descansar_em: escolhido});
      // Devolve o programa já montado com a troca aplicada: quem recebe troca o estado sem
      // uma segunda ida ao servidor, e a tela não pisca entre um programa e o outro.
      await aoTrocar?.(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível trocar o dia."));
    } finally { setEnviando(false); }
  };

  const desfazer = async () => {
    if (enviando) return;
    setEnviando(true); setErro("");
    try {
      const r = await axiosCliente.delete(`${API}/workout/trocar-dia`);
      await aoTrocar?.(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível desfazer."));
    } finally { setEnviando(false); }
  };

  if (estado === "carregando") return null;

  if (estado === "indisponivel") {
    return (
      <section className="trocar-dia" data-testid="trocar-dia-indisponivel">
        <p className="trocar-dia-nota">{motivo}</p>
      </section>
    );
  }

  if (trocas.length) {
    return (
      <section className="trocar-dia" data-testid="trocar-dia-feita">
        <p className="trocar-dia-titulo"><Check size={14} aria-hidden="true" /> Dia trocado</p>
        {trocas.map(t => (
          <p className="trocar-dia-nota" key={`${t.treinar_em}-${t.descansar_em}`}>
            Treino de {porExtenso(t.descansar_em)} movido para {porExtenso(t.treinar_em)}.
          </p>
        ))}
        <button type="button" className="trocar-dia-desfazer" disabled={enviando}
                data-testid="trocar-dia-desfazer" onClick={desfazer}>
          <Undo2 size={14} aria-hidden="true" /> Voltar para a agenda do programa
        </button>
        {erro ? <p className="trocar-dia-erro" role="alert">{erro}</p> : null}
      </section>
    );
  }

  if (!candidatos.length) {
    // Acontece de verdade: programa de sete dias, ou semana em que tudo já foi trocado.
    // Dizer isso é melhor que mostrar um seletor vazio.
    return (
      <section className="trocar-dia" data-testid="trocar-dia-sem-candidatos">
        <p className="trocar-dia-nota">Não há outro dia com treino nesta semana para trocar.</p>
      </section>
    );
  }

  return (
    <section className="trocar-dia" data-testid="trocar-dia">
      <p className="trocar-dia-titulo">
        <CalendarSync size={14} aria-hidden="true" /> Precisa treinar hoje?
      </p>
      <p className="trocar-dia-nota">
        Escolha o dia que passa a ser o descanso. Seu programa não muda: vale só nesta semana.
      </p>
      <div className="trocar-dia-opcoes" role="radiogroup" aria-label="Dia para descansar">
        {candidatos.map(d => (
          <button key={d.data} type="button" role="radio" aria-checked={escolhido === d.data}
                  className={escolhido === d.data ? "escolhido" : ""}
                  data-testid={`trocar-dia-opcao-${d.data}`}
                  onClick={() => setEscolhido(d.data)}>
            <b>{porExtenso(d.data)}</b>
            <small>{d.label}</small>
          </button>
        ))}
      </div>
      <button type="button" className="trocar-dia-confirmar" disabled={!escolhido || enviando}
              data-testid="trocar-dia-confirmar" onClick={trocar}>
        {enviando ? "Trocando…" : "Treinar hoje"}
      </button>
      {erro ? <p className="trocar-dia-erro" role="alert" data-testid="trocar-dia-erro">{erro}</p> : null}
    </section>
  );
}
