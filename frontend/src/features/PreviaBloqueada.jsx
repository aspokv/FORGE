import { Lock, ShieldCheck, Sparkles } from "lucide-react";

import { resumoDaPrevia } from "./signupSteps";

/**
 * Previa parcialmente bloqueada, mostrada antes do pagamento.
 *
 * O componente NAO decide o que esconder. O servidor manda a previa ja sem exercicio e
 * sem refeicao, e marca `locked`; aqui so desenhamos o cadeado. Se o bloqueio morasse na
 * tela, bastaria abrir o inspetor para ler o que ainda nao foi pago.
 */

function Cadeado({ children }) {
  return (
    <div className="previa-bloqueado" aria-label="Disponível após a ativação">
      <span className="previa-cadeado">
        <Lock size={13} /> Disponível após a ativação
      </span>
      <div className="previa-borrado" aria-hidden="true">
        {children}
      </div>
    </div>
  );
}

export default function PreviaBloqueada({ previa, onAtivar, ocupado, children }) {
  if (!previa) return null;
  const resumo = resumoDaPrevia(previa);
  const nutricao = previa.nutrition || {};

  return (
    <section className="previa" data-testid="previa-bloqueada">
      <p className="eyebrow">
        <Sparkles size={13} /> Sua prévia
      </p>
      <h2>{previa.headline}</h2>

      <div className="previa-numeros">
        <div>
          <b>{resumo.dias}</b>
          <span>dias por semana</span>
        </div>
        <div>
          <b>{resumo.sessoes}</b>
          <span>sessões montadas</span>
        </div>
        <div>
          <b>{resumo.split}</b>
          <span>divisão</span>
        </div>
      </div>

      <p className="eyebrow spaced">Sua semana</p>
      <ul className="previa-sessoes">
        {(previa.training?.sessions || []).map((s, i) => (
          <li key={`${s.label}-${i}`} data-testid={`previa-sessao-${i}`}>
            <div className="previa-sessao-topo">
              <b>{s.label}</b>
              <span>{(s.regions || []).join(" · ")}</span>
            </div>
            <Cadeado>
              <span className="previa-linha longa" />
              <span className="previa-linha media" />
              <span className="previa-linha curta" />
            </Cadeado>
          </li>
        ))}
      </ul>

      <p className="eyebrow spaced">Seu foco</p>
      <div className="previa-foco">
        {(previa.focus?.regions || []).map((r) => (
          <span key={r.region} className={r.role === "Principal" ? "destaque" : ""}>
            {r.region} <em>{r.role}</em>
          </span>
        ))}
        <p className="muted">{previa.focus?.note}</p>
      </div>

      <p className="eyebrow spaced">Sua alimentação</p>
      {nutricao.included ? (
        <div className="previa-nutricao" data-testid="previa-nutricao">
          <p className="signup-chosen">
            <b>{nutricao.body_goal_label}</b>
            {nutricao.protocol && <> — ritmo {nutricao.protocol.intensity_label}</>}
          </p>
          {nutricao.protocol && (
            <ul className="previa-protocolo">
              <li>
                <b>
                  {nutricao.protocol.delta_pct > 0 ? "+" : ""}
                  {nutricao.protocol.delta_pct}%
                </b>
                <span>{nutricao.protocol.delta_pct > 0 ? "de superávit" : "de déficit"}</span>
              </li>
              <li>
                <b>{nutricao.protocol.protein_g_per_kg} g/kg</b>
                <span>de proteína</span>
              </li>
              {nutricao.protocol.carb_range_g && (
                <li>
                  <b>
                    {nutricao.protocol.carb_range_g[0]}–{nutricao.protocol.carb_range_g[1]} g
                  </b>
                  <span>de carboidrato</span>
                </li>
              )}
            </ul>
          )}
          <Cadeado>
            <span className="previa-linha longa" />
            <span className="previa-linha media" />
          </Cadeado>
          <p className="muted">{nutricao.note}</p>
        </div>
      ) : (
        <p className="previa-sem-nutricao" data-testid="previa-sem-nutricao">
          {nutricao.note}
        </p>
      )}

      {children}

      <button
        type="button"
        className="btn primary previa-cta"
        disabled={ocupado}
        onClick={onAtivar}
        data-testid="previa-cta"
      >
        {ocupado ? "Abrindo pagamento..." : previa.cta}
      </button>
      <p className="plan-footnote">
        <ShieldCheck size={14} /> Pagamento pelo Mercado Pago. O FORGE não armazena dados
        do seu cartão.
      </p>
    </section>
  );
}
