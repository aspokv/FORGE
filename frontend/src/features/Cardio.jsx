import {useCallback, useEffect, useMemo, useState} from "react";
import axios from "axios";
import {Activity, Plus, Timer, Trash2} from "lucide-react";
import {mensagemDeErro} from "./mensagemDeErro";
import "./cardio.css";

/**
 * A aba de cardio: o que foi feito na esteira, na bike, na escada.
 *
 * Por que o número da máquina não vira comida
 * -------------------------------------------
 * A esteira diz "412 kcal". Esse número é otimista por duas razões conhecidas: ele é
 * BRUTO, ou seja, inclui o que a pessoa gastaria sentada no mesmo tempo, e sai de uma
 * fórmula genérica que não sabe o peso real nem a composição de quem está em cima dela.
 *
 * Além disso, o alvo calórico do FORGE já nasce de um TDEE com fator de atividade: boa
 * parte do gasto de cardio já está contada ali. Devolver a caloria da esteira como
 * permissão para comer mais contaria o mesmo gasto duas vezes, com um número inflado.
 *
 * O que o cardio faz de verdade está no Conselho: quando o resultado pede mais déficit e
 * a comida já está no piso, ele manda somar cardio em vez de cortar comida. E quando a
 * perda está rápida demais, ele manda tirar cardio antes de mandar comer mais.
 */

const HOJE = () => new Date().toISOString().slice(0, 10);

export default function Cardio({API, axiosCliente = axios}) {
  const [modalidades, setModalidades] = useState([]);
  const [sessoes, setSessoes] = useState([]);
  const [leitura, setLeitura] = useState(null);
  const [estado, setEstado] = useState("carregando");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [aberto, setAberto] = useState(false);

  const [modality, setModality] = useState("");
  const [minutes, setMinutes] = useState("");
  const [kcal, setKcal] = useState("");
  const [data, setData] = useState(HOJE);
  const [note, setNote] = useState("");

  const carregar = useCallback(async () => {
    try {
      const [m, l] = await Promise.all([
        axiosCliente.get(`${API}/cardio/modalities`),
        axiosCliente.get(`${API}/cardio`),
      ]);
      const lista = m.data.modalities || [];
      setModalidades(lista);
      setModality(atual => atual || lista[0] || "");
      setSessoes(l.data.sessoes || []);
      setLeitura(l.data.leitura || null);
      setEstado("pronto");
    } catch (e) {
      setEstado("erro");
      setErro(mensagemDeErro(e, "Não foi possível carregar seus cardios."));
    }
  }, [API, axiosCliente]);

  useEffect(() => { carregar(); }, [carregar]);

  const limpar = () => { setMinutes(""); setKcal(""); setNote(""); setData(HOJE()); };

  const registrar = async evento => {
    evento?.preventDefault?.();
    if (salvando) return;
    const min = Number(minutes);
    if (!Number.isFinite(min) || min < 1) {
      setErro("Quantos minutos você fez?");
      return;
    }
    setSalvando(true);
    setErro("");
    try {
      await axiosCliente.post(`${API}/cardio`, {
        // O token é a idempotência: se a requisição for repetida, o servidor grava a
        // mesma sessão por cima em vez de criar uma segunda.
        client_token: `cardio-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
        kind: "free",
        modality,
        minutes: Math.round(min),
        kcal_reported: kcal === "" ? null : Math.round(Number(kcal)),
        date: data,
        note: note.trim(),
        completed: true,
      });
      limpar();
      setAberto(false);
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível registrar esse cardio."));
    } finally {
      setSalvando(false);
    }
  };

  const remover = async token => {
    setErro("");
    try {
      await axiosCliente.delete(`${API}/cardio/${token}`);
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível remover esse registro."));
    }
  };

  // O número grande é a SEMANA CORRENTE, e não a média da janela. Registrar 42 minutos e
  // ler "10 min / semana" na mesma tela parece que o aplicativo perdeu a sessão: a média
  // de quatro semanas é o que o Conselho usa, e ela fica na linha de resumo.
  const naSemana = leitura?.minutos_na_semana ?? 0;
  const mediaSemanal = leitura?.minutos_por_semana || 0;
  const agrupado = useMemo(() => {
    const mapa = new Map();
    for (const s of sessoes) {
      const dia = s.date || "";
      if (!mapa.has(dia)) mapa.set(dia, []);
      mapa.get(dia).push(s);
    }
    return [...mapa.entries()];
  }, [sessoes]);

  if (estado === "carregando") return (
    <section className="cardio-aba" data-testid="cardio-carregando">
      <p className="cardio-vazio">Carregando seus cardios…</p>
    </section>
  );

  return (
    <section className="cardio-aba" data-testid="cardio-aba">
      <header className="cardio-topo">
        <div>
          <span className="cardio-etiqueta"><Activity size={13} /> Cardio</span>
          <h3>Esteira, bike, escada</h3>
        </div>
        <strong className="cardio-semana" data-testid="cardio-semana-atual">
          {naSemana} <small>min esta semana</small>
        </strong>
      </header>

      {leitura?.sessoes > 0 && (
        <p className="cardio-resumo" data-testid="cardio-resumo">
          {leitura.sessoes} {leitura.sessoes > 1 ? "sessões" : "sessão"} em{" "}
          {leitura.janela_dias} dias · {leitura.minutos} minutos · média de{" "}
          <b data-testid="cardio-media-semanal">{mediaSemanal} min por semana</b>
          {leitura.kcal_reported > 0
            ? ` · ${leitura.kcal_reported} kcal pelo painel das máquinas`
            : ""}
        </p>
      )}

      {!aberto && (
        <button type="button" className="cardio-abrir" data-testid="cardio-abrir"
                onClick={() => setAberto(true)}>
          <Plus size={15} /> Registrar um cardio
        </button>
      )}

      {aberto && (
        <form className="cardio-form" data-testid="cardio-form" onSubmit={registrar}>
          <div className="cardio-linha">
            <label>
              <span>Modalidade</span>
              <select value={modality} data-testid="cardio-modalidade"
                      onChange={e => setModality(e.target.value)}>
                {modalidades.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </label>
            <label>
              <span>Dia</span>
              <input type="date" value={data} max={HOJE()} data-testid="cardio-data"
                     onChange={e => setData(e.target.value)} />
            </label>
          </div>

          <div className="cardio-linha">
            <label>
              <span>Tempo</span>
              <div className="cardio-campo-com-unidade">
                <input type="number" inputMode="numeric" min="1" max="360" value={minutes}
                       placeholder="30" data-testid="cardio-minutos"
                       onChange={e => setMinutes(e.target.value)} />
                <em>min</em>
              </div>
            </label>
            <label>
              <span>Calorias <i>opcional</i></span>
              <div className="cardio-campo-com-unidade">
                <input type="number" inputMode="numeric" min="0" max="3000" value={kcal}
                       placeholder="—" data-testid="cardio-kcal"
                       onChange={e => setKcal(e.target.value)} />
                <em>kcal</em>
              </div>
            </label>
          </div>

          <label className="cardio-observacao">
            <span>Observação <i>opcional</i></span>
            <input type="text" value={note} maxLength={280} data-testid="cardio-nota"
                   placeholder="Inclinação 8, 6 km/h"
                   onChange={e => setNote(e.target.value)} />
          </label>

          <p className="cardio-aviso">
            O número da máquina entra como registro, e não como permissão para comer mais.
            Ele é bruto e sai de uma fórmula genérica, e sua meta de calorias já conta a
            atividade. Quem decide se o plano muda é a balança, no Conselho da semana.
          </p>

          <div className="cardio-acoes">
            <button type="submit" className="cardio-salvar" disabled={salvando}
                    data-testid="cardio-salvar">
              {salvando ? "Registrando…" : "Registrar"}
            </button>
            <button type="button" className="cardio-cancelar" data-testid="cardio-cancelar"
                    onClick={() => { setAberto(false); setErro(""); }}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {erro ? <p className="cardio-erro" role="alert" data-testid="cardio-erro">{erro}</p> : null}

      {agrupado.length === 0 ? (
        <p className="cardio-vazio" data-testid="cardio-vazio">
          Nenhum cardio registrado nos últimos {leitura?.janela_dias || 28} dias.
        </p>
      ) : (
        <ul className="cardio-lista" data-testid="cardio-lista">
          {agrupado.map(([dia, doDia]) => (
            <li key={dia}>
              <b className="cardio-dia">{formatarDia(dia)}</b>
              <ul>
                {doDia.map(s => (
                  <li key={s.client_token} data-testid={`cardio-item-${s.client_token}`}>
                    <span className="cardio-item-icone"><Timer size={14} /></span>
                    <div>
                      <b>{s.modality}</b>
                      <small>
                        {s.minutes} min
                        {s.kcal_reported ? ` · ${s.kcal_reported} kcal` : ""}
                        {s.rpe ? ` · RPE ${s.rpe}` : ""}
                      </small>
                      {s.note ? <small className="cardio-item-nota">{s.note}</small> : null}
                    </div>
                    <button type="button" aria-label={`Remover ${s.modality} de ${s.minutes} minutos`}
                            data-testid={`cardio-remover-${s.client_token}`}
                            onClick={() => remover(s.client_token)}>
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatarDia(iso) {
  if (!iso) return "Sem data";
  const hoje = HOJE();
  if (iso === hoje) return "Hoje";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}
