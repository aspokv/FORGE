import {useState} from "react";
import axios from "axios";
import {Check} from "lucide-react";
import "./prioridades-musculares.css";

/**
 * Trocar as regioes prioritarias sem refazer a avaliacao inteira.
 *
 * Por que isto existe: escolher prioridade e a primeira coisa que o FORGE pergunta, e e
 * justamente quando a pessoa menos sabe o que cada regiao significa. Quem errou ficava
 * preso — o Perfil LISTAVA as prioridades e nao deixava mexer, e o unico caminho era
 * responder o questionario inteiro de novo. Um atleta real travou assim.
 *
 * A ORDEM e o dado, e nao so quais foram marcadas: a primeira e a prioridade principal e
 * recebe mais atencao no plano. Por isso cada escolhida mostra o numero dela.
 */

export const GRUPOS_DE_REGIAO = {
  PEITORAL: ["Peitoral superior", "Peitoral esternal"],
  OMBROS: ["Deltóide anterior", "Deltóide lateral", "Deltóide posterior"],
  COSTAS: ["Dorsais / largura", "Costas / espessura", "Trapézio"],
  "BRAÇOS": ["Bíceps", "Braquial", "Tríceps"],
  PERNAS: ["Quadríceps", "Posteriores", "Glúteos", "Adutores", "Panturrilhas"],
  CORE: ["Abdômen", "Oblíquos"],
};

const MAXIMO = 3;
const PAPEL = ["principal", "secundária", "secundária"];

export default function PrioridadesMusculares({API, profileId, iniciais = [], onSalvo}) {
  const [escolhidas, setEscolhidas] = useState(() => iniciais.slice(0, MAXIMO));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [sugestao, setSugestao] = useState(null);
  const [salvo, setSalvo] = useState(false);

  const alternar = (regiao) => {
    setErro(""); setSalvo(""); setAviso(""); setSugestao(null);
    setEscolhidas(atual => {
      if (atual.includes(regiao)) return atual.filter(x => x !== regiao);
      if (atual.length >= MAXIMO) {
        setErro(`São no máximo ${MAXIMO} regiões. Tire uma antes de escolher outra.`);
        return atual;
      }
      return [...atual, regiao];
    });
  };

  const salvar = async () => {
    setSalvando(true); setErro(""); setAviso(""); setSalvo(false); setSugestao(null);
    try {
      const r = await axios.put(`${API}/training/priorities`,
        {priorities: escolhidas, profile_id: profileId});
      setSalvo(true);
      // O aviso so existe quando o treino NAO se recalcula — programa colado ou escolhido
      // da biblioteca. Dizer "salvo" e deixar o treino igual sem explicacao seria pior que
      // nao deixar trocar.
      setAviso(r.data?.aviso || "");
      setSugestao(r.data?.sugestao || null);
      if (onSalvo) onSalvo(r.data);
      /* Recarregar e o que a tela de preferencias de treino ja faz depois de salvar, e por
         um motivo: o programa novo precisa chegar em todas as abas, e esta tela nao tem
         como empurrar isso sozinha. So recarrega quando o treino REALMENTE mudou — com o
         aviso na tela, recarregar apagaria justamente a explicacao que a pessoa precisa
         ler. */
      if (r.data?.recalculou) setTimeout(() => window.location.reload(), 900);
    } catch (e) {
      setErro(e?.response?.data?.detail || "Não foi possível salvar suas prioridades agora.");
    } finally { setSalvando(false); }
  };

  const mudou = escolhidas.join("|") !== iniciais.slice(0, MAXIMO).join("|");

  return <section className="prioridades" data-testid="prioridades-musculares">
    <p className="prioridades-apoio">
      Escolha até {MAXIMO} regiões. A <b>primeira</b> recebe mais atenção no plano; as outras
      entram como secundárias. Sem nenhuma, o treino fica equilibrado.
    </p>

    <div className="prioridades-foco" data-testid="prioridades-foco">
      {escolhidas.length === 0
        ? <p className="prioridades-vazio">Treino equilibrado, nenhuma região priorizada.</p>
        : <ol>
            {escolhidas.map((regiao, i) => (
              <li key={regiao}>
                <b>{i + 1}</b><span>{regiao}</span><em>{PAPEL[i]}</em>
              </li>
            ))}
          </ol>}
    </div>

    {Object.entries(GRUPOS_DE_REGIAO).map(([grupo, regioes]) => (
      <div className="prioridades-grupo" key={grupo}>
        <p className="fg-etiqueta">{grupo}</p>
        <div className="prioridades-chips">
          {regioes.map(regiao => {
            const pos = escolhidas.indexOf(regiao);
            const marcada = pos >= 0;
            return (
              <button type="button" key={regiao} aria-pressed={marcada}
                      className={marcada ? "prioridade-chip marcada" : "prioridade-chip"}
                      data-testid={`prioridade-${regiao}`}
                      onClick={() => alternar(regiao)}>
                {marcada && <span className="prioridade-ordem">{pos + 1}</span>}
                {regiao}
              </button>
            );
          })}
        </div>
      </div>
    ))}

    {erro && <p className="fg-erro" role="alert">{erro}</p>}
    {aviso && <div className="prioridades-aviso" role="status" data-testid="prioridades-aviso">
      <p>{aviso}</p>
      {/*
        * As alternativas aparecem porque a escolha e dela, e nao minha. O FORGE aponta a
        * que melhor se encaixa e mostra as seguintes, em vez de empurrar 23 programas ou
        * decidir sozinho por ela.
        */}
      {(sugestao?.recomendados || []).length > 1 && <ul className="prioridades-alternativas">
        {sugestao.recomendados.slice(1).map(op => (
          <li key={op.id}>
            <b>{op.nome}</b>
            <span>{op.dias} sessões · {String(op.nivel || "").toLowerCase()}
              {op.cobertura > 0 && ` · ${Math.round(op.cobertura * 100)}% nas prioridades`}</span>
          </li>
        ))}
      </ul>}
    </div>}
    {salvo && !aviso && <p className="prioridades-ok" role="status">
      <Check size={15} aria-hidden="true" /> Prioridades salvas e treino recalculado.
    </p>}

    <button type="button" className="fg-btn fg-btn-cheio" disabled={salvando || !mudou}
            data-testid="salvar-prioridades" onClick={salvar}>
      {salvando ? "Salvando…" : "Salvar prioridades"}
    </button>
  </section>;
}
