import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {NotebookPen, Plus, Trash2, X} from "lucide-react";
import AsyncState from "./AsyncState";
import FoodDiaryEditor from "./FoodDiaryEditor";
import {mensagemDeErro} from "./mensagemDeErro";
import "./diario-livre.css";

/**
 * Registrar o que se comeu DE VERDADE, separado do plano.
 *
 * O FORGE ja guardava isso, mas de um jeito que ninguem usava: o botao se chamava
 * "Adicionar um extra", ficava no fim da tela entre outras acoes, e o que era registrado
 * aparecia como "Extra · 320 kcal", sem dizer de que refeicao era. Empilhado embaixo do
 * plano, parecia um apendice do plano.
 *
 * São duas coisas diferentes e agora moram em lugares diferentes:
 *
 *   O PLANO diz o que comer. Fica onde sempre esteve.
 *   O DIÁRIO diz o que foi comido. Fica aqui em cima, com nome de refeição e soma.
 *
 * Quem nao segue o plano num dia continua tendo o dia contado, que e o que faz a leitura
 * semanal do Conselho valer alguma coisa: sem registro, ele responde "essa semana eu nao
 * sei" e para por ai.
 */

export default function DiarioLivre({API, dia, diario, aoMudar, axiosCliente = axios}) {
  const [refeicoes, setRefeicoes] = useState([]);
  const [aberto, setAberto] = useState(null);      // id da refeição sendo registrada
  const [estado, setEstado] = useState("carregando");
  const [erro, setErro] = useState("");
  const [removendo,setRemovendo]=useState(null);

  const carregar = useCallback(async () => {
    setEstado("carregando");
    try {
      const r = await axiosCliente.get(`${API}/nutrition/refeicoes-do-diario`);
      setRefeicoes(r.data.refeicoes || []);
      setEstado("pronto");
    } catch (e) {
      // 402 = o plano nao inclui o diario livre. Nao e erro, e um convite.
      setEstado(e?.response?.status === 402 ? "bloqueado" : "erro");
    }
  }, [API, axiosCliente]);

  useEffect(() => { carregar(); }, [carregar]);

  const registros = (diario?.extras || []).filter(e => e.refeicao);
  const total = registros.reduce((soma, e) => soma + Number(e?.actual?.totals?.kcal || 0), 0);

  const remover = async entryId => {
    if(removendo)return;setRemovendo(entryId);setErro("");
    try {
      await axiosCliente.delete(`${API}/nutrition/consumed-extra/${entryId}`);
      await aoMudar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível remover esse registro."));
    } finally {setRemovendo(null)}
  };

  if (estado === "carregando") return <AsyncState title="Carregando diário…"/>;
  if (estado === "erro") return <AsyncState kind="error" title="Não foi possível carregar o diário" onRetry={carregar}/>;

  if (estado === "bloqueado") return (
    <section className="diario-livre diario-bloqueado" data-testid="diario-bloqueado">
      <span className="diario-etiqueta"><NotebookPen size={13} /> Diário livre</span>
      <h3>Comeu fora do plano? Registre assim mesmo</h3>
      <p>
        No FORGE Elite você anota o que comeu de verdade, refeição por refeição, mesmo
        quando o dia não seguiu o plano. O dia continua contado, e o Conselho continua
        tendo o que ler no domingo.
      </p>
    </section>
  );

  return (
    <section className="diario-livre" data-testid="diario-livre">
      <header className="diario-topo">
        <div>
          <span className="diario-etiqueta"><NotebookPen size={13} /> Diário livre</span>
          <h3>Seu diário de hoje</h3>
        </div>
        {registros.length > 0 && (
          <strong className="diario-total" data-testid="diario-total">
            {Math.round(total)} <small>kcal</small>
          </strong>
        )}
      </header>

      <p className="diario-explicacao">
        Registre refeições fora do plano sem alterar a dieta original.
      </p>

      <details className="forge-diary-picker"><summary><Plus size={16} aria-hidden="true"/> Registrar refeição fora do plano</summary>
      <div className="diario-refeicoes" role="group" aria-label="Refeição a registrar">
        {refeicoes.map(r => {
          const doDia = registros.filter(e => e.refeicao === r.id);
          const kcal = doDia.reduce((s, e) => s + Number(e?.actual?.totals?.kcal || 0), 0);
          return (
            <button key={r.id} type="button" className={doDia.length ? "diario-refeicao tem" : "diario-refeicao"}
                    data-testid={`diario-refeicao-${r.id}`} onClick={() => setAberto(r.id)}
                    aria-label={doDia.length ? `${r.nome}, ${Math.round(kcal)} kcal registradas` : `Registrar ${r.nome}`}>
              <span>{r.nome}</span>
              {doDia.length ? <b>{Math.round(kcal)} kcal</b> : <i aria-hidden="true"><Plus size={13} /></i>}
            </button>
          );
        })}
      </div>

      </details>

      {registros.length > 0 && (
        <ul className="diario-registros" data-testid="diario-registros">
          {registros.map(e => (
            <li key={e.entry_id}>
              <div>
                <b>{e.refeicao_nome}</b>
                <span>{(e.actual?.foods || []).map(f => `${f.name} (${f.grams} g)`).join(" · ")}</span>
              </div>
              <strong>{Math.round(e.actual?.totals?.kcal || 0)} kcal</strong>
              <button type="button" aria-label={`Remover ${e.refeicao_nome}`}
                      data-testid={`diario-remover-${e.entry_id}`} disabled={Boolean(removendo)} aria-busy={removendo===e.entry_id} onClick={() => remover(e.entry_id)}>
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {erro ? <p className="diario-erro" role="alert" data-testid="diario-erro">{erro}</p> : null}

      {aberto && (
        <div className="diario-editor" data-testid="diario-editor">
          <div className="diario-editor-topo">
            <b>{refeicoes.find(r => r.id === aberto)?.nome}</b>
            <button type="button" aria-label="Fechar" data-testid="diario-fechar"
                    onClick={() => setAberto(null)}><X size={16} /></button>
          </div>
          <FoodDiaryEditor
            API={API} mealIndex={null} refeicao={aberto} dia={dia}
            mealName={refeicoes.find(r => r.id === aberto)?.nome}
            onSaved={async () => { setAberto(null); await aoMudar(); }}
            onClose={() => setAberto(null)} />
        </div>
      )}
    </section>
  );
}
