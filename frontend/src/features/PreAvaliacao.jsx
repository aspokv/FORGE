import { togglePriority } from "./musclePriorities";
import { ritmoPadrao, ritmosDoObjetivo } from "./signupSteps";

/**
 * As seis perguntas curtas que antecedem o pagamento.
 *
 * Quais perguntas existem vem do CATALOGO do servidor, nao de uma lista escrita aqui:
 * as de alimentacao so aparecem quando o plano escolhido a inclui, e o ritmo agressivo
 * chega marcado como bloqueado quando o plano nao e o Elite. Decidir isso na tela
 * criaria uma segunda regra de capacidade, que envelheceria sozinha.
 */

function Opcoes({ titulo, ajuda, opcoes, valor, onEscolher, erro, teste }) {
  return (
    <fieldset className="pa-bloco" data-testid={teste}>
      <legend>{titulo}</legend>
      {ajuda && <p className="muted">{ajuda}</p>}
      <div className="pa-opcoes">
        {opcoes.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`pa-opcao${valor === o.id ? " selected" : ""}${o.locked ? " locked" : ""}`}
            disabled={o.locked}
            onClick={() => onEscolher(o.id)}
            data-testid={`${teste}-${o.id}`}
          >
            <b>{o.label}</b>
            {o.description && <span>{o.description}</span>}
            {o.locked && <em className="pa-cadeado">Disponível no Elite</em>}
            {o.recommended && !o.locked && <em className="pa-recomendado">Recomendado</em>}
          </button>
        ))}
      </div>
      {erro && <p className="form-error">{erro}</p>}
    </fieldset>
  );
}

export default function PreAvaliacao({ catalogo, respostas, onMudar, erros, aviso, onAviso }) {
  const cat = catalogo || {};
  const r = respostas || {};
  const set = (campo, valor) => onMudar({ ...r, [campo]: valor });

  const alternarRegiao = (regiao) => {
    const { priorities, warning } = togglePriority(r.priorities || [], regiao);
    onAviso(warning);
    onMudar({ ...r, priorities });
  };

  const trocarObjetivoAlimentar = (id) => {
    // Trocar o objetivo invalida o ritmo anterior: "leve" nao existe em ganho de massa.
    onMudar({ ...r, body_goal: id, goal_intensity: ritmoPadrao(cat, id) });
  };

  const ritmos = ritmosDoObjetivo(cat, r.body_goal);

  return (
    <div className="pre-avaliacao">
      <Opcoes
        titulo="Seu perfil"
        ajuda="Define a ênfase padrão e as faixas de referência do seu plano."
        opcoes={cat.sexes || []}
        valor={r.sex}
        onEscolher={(v) => set("sex", v)}
        erro={erros.sex}
        teste="pa-sexo"
      />

      <Opcoes
        titulo="Seu objetivo de treino"
        opcoes={cat.training_goals || []}
        valor={r.goal}
        onEscolher={(v) => set("goal", v)}
        erro={erros.goal}
        teste="pa-objetivo"
      />

      <Opcoes
        titulo="Sua experiência"
        opcoes={cat.experiences || []}
        valor={r.experience}
        onEscolher={(v) => set("experience", v)}
        erro={erros.experience}
        teste="pa-experiencia"
      />

      <fieldset className="pa-bloco" data-testid="pa-dias">
        <legend>Dias disponíveis por semana</legend>
        <p className="muted">É isto que define a divisão do seu treino.</p>
        <div className="pa-dias">
          {(cat.days || []).map((d) => (
            <button
              key={d}
              type="button"
              className={`pa-dia${r.days === d ? " selected" : ""}`}
              onClick={() => set("days", d)}
              data-testid={`pa-dias-${d}`}
            >
              {d}
            </button>
          ))}
        </div>
        {erros.days && <p className="form-error">{erros.days}</p>}
      </fieldset>

      <fieldset className="pa-bloco" data-testid="pa-prioridades">
        <legend>Regiões prioritárias</legend>
        <p className="muted">
          Escolha até {cat.max_priorities || 3}. A primeira recebe mais atenção. Se não
          escolher nenhuma, o FORGE distribui o volume de forma equilibrada.
        </p>
        <div className="pa-regioes">
          {(cat.regions || []).map((regiao) => {
            const pos = (r.priorities || []).indexOf(regiao);
            return (
              <button
                key={regiao}
                type="button"
                className={`pa-regiao${pos >= 0 ? " selected" : ""}`}
                onClick={() => alternarRegiao(regiao)}
                data-testid={`pa-regiao-${regiao}`}
              >
                {pos >= 0 && <em>{pos + 1}</em>}
                {regiao}
              </button>
            );
          })}
        </div>
        {aviso && <p className="form-note">{aviso}</p>}
        {erros.priorities && <p className="form-error">{erros.priorities}</p>}
      </fieldset>

      {cat.includes_nutrition && (
        <>
          <Opcoes
            titulo="Seu objetivo alimentar"
            opcoes={(cat.body_goals || []).map((g) => ({
              id: g.id,
              label: g.label,
              description: g.description,
            }))}
            valor={r.body_goal}
            onEscolher={trocarObjetivoAlimentar}
            erro={erros.body_goal}
            teste="pa-objetivo-alimentar"
          />

          {ritmos.length > 0 && (
            <Opcoes
              titulo="Ritmo desejado"
              opcoes={ritmos}
              valor={r.goal_intensity}
              onEscolher={(v) => set("goal_intensity", v)}
              erro={erros.goal_intensity}
              teste="pa-ritmo"
            />
          )}
        </>
      )}
    </div>
  );
}
