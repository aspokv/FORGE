import {useState} from "react";
import axios from "axios";
import {Plus} from "lucide-react";
import "./acrescentar-refeicao.css";

/**
 * Acrescentar uma refeicao ao plano, na posicao que a pessoa escolher.
 *
 * O caso do atleta: ele tem cafe da manha e quer um PRE-TREINO antes. Ate aqui a unica
 * forma era refazer o questionario mudando a quantidade de refeicoes, o que joga fora o
 * cardapio inteiro.
 *
 * A tela diz o que vai acontecer ANTES de acontecer: as outras refeicoes encolhem, porque o
 * dia tem a mesma caloria dividida em mais partes. Descobrir isso depois seria pior.
 */

// Nomes que o motor reconhece e usa para escolher o tipo de prato. "Pre-treino" monta um
// pre-treino de verdade; um nome inventado cai no padrao de almoco.
const SUGESTOES = ["Pré-treino", "Pós-treino", "Lanche da manhã", "Lanche da tarde", "Ceia"];

const MAXIMO = 6;

export default function AcrescentarRefeicao({API, refeicoes = [], onAcrescentada}) {
  const [aberto, setAberto] = useState(false);
  const [nome, setNome] = useState("");
  const [posicao, setPosicao] = useState(refeicoes.length);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const cheio = refeicoes.length >= MAXIMO;

  const salvar = async () => {
    setSalvando(true); setErro("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/add-meal`,
        {nome: nome.trim(), posicao});
      setAberto(false); setNome("");
      if (onAcrescentada) onAcrescentada(r.data);
    } catch (e) {
      setErro(e?.response?.data?.detail || "Não foi possível acrescentar a refeição agora.");
    } finally { setSalvando(false); }
  };

  return <section className="acrescentar" data-testid="acrescentar-refeicao">
    <button type="button" className="acrescentar-topo" aria-expanded={aberto}
            data-testid="abrir-acrescentar" disabled={cheio}
            onClick={() => setAberto(v => !v)}>
      <Plus size={17} aria-hidden="true" />
      <span>
        <strong>Acrescentar uma refeição</strong>
        <small>{cheio
          ? `O plano já tem ${MAXIMO} refeições, que é o máximo.`
          : "Um pré-treino, uma ceia, o que faltar no seu dia."}</small>
      </span>
    </button>

    {aberto && !cheio && <div className="acrescentar-corpo">
      <label className="acrescentar-campo">
        <span className="fg-etiqueta">Nome da refeição</span>
        <input type="text" value={nome} maxLength={40} placeholder="Pré-treino"
               data-testid="nome-da-refeicao"
               onChange={e => { setNome(e.target.value); setErro(""); }} />
      </label>

      <div className="acrescentar-sugestoes">
        {SUGESTOES.map(s => (
          <button type="button" key={s} className="acrescentar-sugestao"
                  data-testid={`sugestao-${s}`} onClick={() => { setNome(s); setErro(""); }}>
            {s}
          </button>
        ))}
      </div>

      <div className="acrescentar-onde">
        <span className="fg-etiqueta">Onde ela entra</span>
        <div className="acrescentar-posicoes">
          {/* Uma posicao por "fresta" entre refeicoes: antes da primeira, entre cada par, e
              no fim. E assim que a pessoa pensa — "antes do cafe da manha". */}
          <button type="button" aria-pressed={posicao === 0} data-testid="posicao-0"
                  className={posicao === 0 ? "acrescentar-posicao marcada" : "acrescentar-posicao"}
                  onClick={() => setPosicao(0)}>
            Antes de {refeicoes[0]?.name || "tudo"}
          </button>
          {refeicoes.map((r, i) => (
            <button type="button" key={r.name + i} aria-pressed={posicao === i + 1}
                    data-testid={`posicao-${i + 1}`}
                    className={posicao === i + 1 ? "acrescentar-posicao marcada" : "acrescentar-posicao"}
                    onClick={() => setPosicao(i + 1)}>
              Depois de {r.name}
            </button>
          ))}
        </div>
      </div>

      {/* O efeito colateral e dito ANTES, e nao descoberto depois. */}
      <p className="acrescentar-nota">
        O dia continua com a mesma meta de calorias, então as outras refeições ficam menores.
        Os alimentos que você escolheu continuam; só as porções mudam.
      </p>

      {erro && <p className="fg-erro" role="alert">{erro}</p>}

      <div className="acrescentar-acoes">
        <button type="button" className="fg-btn fg-btn-cheio"
                disabled={salvando || nome.trim().length < 2}
                data-testid="salvar-refeicao" onClick={salvar}>
          {salvando ? "Acrescentando…" : "Acrescentar refeição"}
        </button>
        <button type="button" className="fg-btn fg-btn-2" disabled={salvando}
                onClick={() => { setAberto(false); setErro(""); }}>
          Cancelar
        </button>
      </div>
    </div>}
  </section>;
}
