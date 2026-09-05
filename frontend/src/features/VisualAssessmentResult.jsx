import "./visual-assessment.css";

/**
 * O resultado da analise visual, na linguagem do produto.
 *
 * A versao anterior mostrava ao usuario o nome do provedor de IA ("Gemini Vision"), uma
 * contagem interna ("2 prioridades sugeridas") e, no caminho de erro, ate o nome da
 * variavel de ambiente que faltava configurar. Nada disso e assunto de quem esta usando o
 * aplicativo — e o nome da variavel nem deveria sair do servidor.
 *
 * Aqui a mesma resposta vira blocos legiveis. Nenhum dado e inventado: pontos fortes e
 * pontos de atencao sao derivados do campo `observations` que a analise ja devolve,
 * separando pelo nivel de desenvolvimento que ela mesma atribuiu.
 */

/** Niveis que a analise usa em `observations[musculo].development`. */
const FORTES = ["forte", "muito forte"];
const ATENCAO = ["fraco", "muito fraco"];

/**
 * Separa os musculos observados em fortes e em atencao.
 *
 * Observacao com confianca baixa fica de fora dos dois grupos: a propria analise esta
 * dizendo que nao enxergou direito, e transformar isso em "ponto forte" ou "ponto fraco"
 * seria dar como certo o que ela marcou como incerto.
 */
function separar(observations = {}) {
  const fortes = [];
  const atencao = [];
  Object.entries(observations || {}).forEach(([musculo, dado]) => {
    const nivel = String(dado?.development || "").toLowerCase();
    const confianca = String(dado?.confidence || "").toLowerCase();
    if (confianca === "baixa") return;
    if (FORTES.includes(nivel)) fortes.push(musculo);
    else if (ATENCAO.includes(nivel)) atencao.push(musculo);
  });
  return { fortes, atencao };
}

function Bloco({ titulo, children }) {
  if (!children) return null;
  return (
    <section className="va-bloco">
      <h4>{titulo}</h4>
      {children}
    </section>
  );
}

function Etiquetas({ itens, tom }) {
  if (!itens?.length) return null;
  return (
    <ul className={`va-etiquetas va-${tom}`}>
      {itens.map((x) => (
        <li key={x}>{x}</li>
      ))}
    </ul>
  );
}

export default function VisualAssessmentResult({ resultado }) {
  if (!resultado) return null;

  if (resultado.status !== "completed") {
    /*
     * Um so texto para qualquer falha. O motivo tecnico — chave ausente, modelo fora do
     * ar, resposta invalida — nao muda nada para quem esta na tela, e dizer qual variavel
     * falta e informacao de servidor vazando para o cliente.
     */
    return (
      <div className="notice" data-testid="visual-unavailable-notice">
        <b>Não foi possível concluir a análise agora</b>
        <p className="muted">
          Tente novamente em alguns minutos. Sua avaliação manual continua valendo.
        </p>
      </div>
    );
  }

  const { fortes, atencao } = separar(resultado.observations);
  const prioridades = resultado.suggested_priorities || [];
  const limitacoes = resultado.limitations || [];
  const temSimetria = resultado.symmetry_notes || resultado.proportion_notes;

  return (
    <div className="va-resultado" data-testid="visual-result-notice">
      <header className="va-topo">
        <b>Análise visual concluída</b>
        <span className="muted">Observações do FORGE sobre as fotos enviadas</span>
      </header>

      <Bloco titulo="Pontos fortes">
        {fortes.length ? (
          <Etiquetas itens={fortes} tom="forte" />
        ) : (
          <p className="muted">
            As fotos não deixaram nenhum grupo claramente destacado.
          </p>
        )}
      </Bloco>

      <Bloco titulo="Pontos de atenção">
        {atencao.length ? (
          <Etiquetas itens={atencao} tom="atencao" />
        ) : (
          <p className="muted">Nenhum grupo apareceu claramente abaixo dos demais.</p>
        )}
      </Bloco>

      {prioridades.length > 0 && (
        <Bloco titulo="Recomendações personalizadas">
          <ol className="va-prioridades">
            {prioridades.map((p, i) => (
              <li key={p}>
                <span>{String(i + 1).padStart(2, "0")}</span>
                {p}
              </li>
            ))}
          </ol>
        </Bloco>
      )}

      {temSimetria && (
        <Bloco titulo="Simetria e proporção">
          {resultado.symmetry_notes && <p>{resultado.symmetry_notes}</p>}
          {resultado.proportion_notes && <p>{resultado.proportion_notes}</p>}
        </Bloco>
      )}

      {limitacoes.length > 0 && (
        <Bloco titulo="Limitações da análise">
          <ul className="va-limitacoes">
            {limitacoes.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Bloco>
      )}

      <p className="va-aviso">
        São observações visuais a partir das fotos, não diagnóstico médico. Pose, luz,
        ângulo e roupa mudam a leitura. Sua avaliação manual continua valendo.
      </p>
    </div>
  );
}
