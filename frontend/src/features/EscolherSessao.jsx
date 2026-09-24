import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {ListChecks, RotateCcw} from "lucide-react";
import {mensagemDeErro} from "./mensagemDeErro";
import "./escolher-sessao.css";

/**
 * Escolher qual sessão do programa treinar hoje.
 *
 * Um atleta adiantou o treino do fim de semana e, no dia seguinte, o FORGE ofereceu de
 * novo a sessão que ele acabara de fazer — a rotação não sabia que ele tinha treinado fora
 * da ordem. Ele quis fazer a seguinte e não teve como: a tela mostra UMA sessão, a que o
 * ponteiro aponta, e não havia onde escolher outra. Sem escolher, não dá para registrar
 * carga; sem registro, o treino não existe para o motor.
 *
 * A escolha vale para hoje e vence sozinha. Ao concluir, a rotação segue a partir do que
 * foi FEITO: quem fez o Pull hoje recebe o Legs amanhã.
 */
export default function EscolherSessao({API, aoEscolher, axiosCliente = axios}) {
  const [aberto, setAberto] = useState(false);
  const [estado, setEstado] = useState("ocioso");
  const [sessoes, setSessoes] = useState([]);
  const [escolhida, setEscolhida] = useState(null);
  const [ativa, setAtiva] = useState(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    setEstado("carregando"); setErro("");
    try {
      const r = await axiosCliente.get(`${API}/workout/sessoes-do-dia`);
      // Resposta que não traz a lista NÃO é lista vazia. Sem esta guarda, um endereço
      // errado cai no `index.html` que o servidor devolve para caminho desconhecido —
      // com status 200 — e a tela mostra um painel vazio como se o programa não tivesse
      // sessão nenhuma. Foi exatamente o que aconteceu quando a prop `API` não chegou
      // aqui: requisição 200, JSON que não era JSON, e nenhuma pista na tela.
      if (!Array.isArray(r.data?.sessoes)) throw new Error("resposta inesperada");
      setSessoes(r.data.sessoes);
      setEscolhida(r.data.escolhida ?? null);
      setAtiva(r.data.ativa ?? null);
      setEstado("pronto");
    } catch (e) {
      setEstado("erro");
      setErro(mensagemDeErro(e, "Não foi possível carregar as suas sessões."));
    }
  }, [API, axiosCliente]);

  useEffect(() => { if (aberto) carregar(); }, [aberto, carregar]);

  const escolher = async day => {
    if (enviando) return;
    setEnviando(true); setErro("");
    try {
      const r = await axiosCliente.post(`${API}/workout/escolher-sessao`, {day});
      setAberto(false);
      await aoEscolher?.(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível escolher essa sessão."));
    } finally { setEnviando(false); }
  };

  const desfazer = async () => {
    if (enviando) return;
    setEnviando(true); setErro("");
    try {
      const r = await axiosCliente.delete(`${API}/workout/escolher-sessao`);
      setAberto(false);
      await aoEscolher?.(r.data);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível desfazer."));
    } finally { setEnviando(false); }
  };

  if (!aberto) {
    return (
      <button type="button" className="escolher-sessao-abrir" data-testid="escolher-sessao-abrir"
              onClick={() => setAberto(true)}>
        <ListChecks size={15} aria-hidden="true" /> Trocar a sessão de hoje
      </button>
    );
  }

  return (
    <section className="escolher-sessao" data-testid="escolher-sessao">
      <p className="escolher-sessao-titulo">Qual treino você vai fazer hoje?</p>
      <p className="escolher-sessao-nota">
        Vale só para hoje. O próximo treino continua a partir do que você fizer.
      </p>

      {estado === "carregando" ? <p className="escolher-sessao-nota" role="status">Carregando…</p> : null}
      {estado === "erro" ? (
        <button type="button" className="escolher-sessao-desfazer" onClick={carregar}>
          Tentar de novo
        </button>
      ) : null}

      {estado === "pronto" && (
        <div className="escolher-sessao-opcoes" role="radiogroup" aria-label="Sessão de hoje">
          {sessoes.map(s => (
            <button key={s.day} type="button" role="radio" aria-checked={ativa === s.day}
                    className={ativa === s.day ? "escolhida" : ""} disabled={enviando}
                    data-testid={`escolher-sessao-${s.day}`} onClick={() => escolher(s.day)}>
              <b>{s.label}</b>
              <small>{s.exercicios} exercícios{s.demand ? ` · ${s.demand}` : ""}</small>
            </button>
          ))}
        </div>
      )}

      {/* Só aparece quando há o que desfazer: um botão de voltar sem escolha feita não
          volta para lugar nenhum. */}
      {escolhida != null && (
        <button type="button" className="escolher-sessao-desfazer" disabled={enviando}
                data-testid="escolher-sessao-desfazer" onClick={desfazer}>
          <RotateCcw size={14} aria-hidden="true" /> Voltar para o treino do programa
        </button>
      )}

      {erro ? <p className="escolher-sessao-erro" role="alert" data-testid="escolher-sessao-erro">{erro}</p> : null}
      <button type="button" className="escolher-sessao-fechar" data-testid="escolher-sessao-fechar"
              onClick={() => setAberto(false)}>Fechar</button>
    </section>
  );
}
