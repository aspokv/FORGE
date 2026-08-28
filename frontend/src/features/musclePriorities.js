/**
 * Prioridades musculares do onboarding.
 *
 * Antes existiam duas etapas sobrepostas: "Regioes prioritarias" (ate tres escolhas) e
 * um "Muscle Map" que percorria os 18 musculos perguntando desenvolvimento percebido E
 * prioridade de desenvolvimento — cerca de 36 decisoes antes de gerar o plano. O Muscle
 * Map saiu do fluxo: toda a intencao de desenvolvimento e capturada aqui.
 *
 * A LISTA ORDENADA e a fonte de verdade. A posicao define o papel, entao remover uma
 * regiao reordena sozinho e nunca sobra lacuna (prioridade 1 e 3 sem a 2).
 *
 * O motor nao precisa de adaptador: calculate_weekly_volume ja consulta o ranking antes
 * do desenvolvimento percebido, e get_assessment_internal trata avaliacao ausente como
 * "proporcional"/"normal" — valor neutro e honesto. Nada e inventado para inflar volume.
 *
 * Mora fora do App.js para poder ser testado com o Jest que ja vem no react-scripts.
 */

export const MAX_PRIORITIES = 3;

/** Ordem das etapas. O Muscle Map nao esta mais aqui. */
export const ONBOARDING_STEPS = [
  "profile", "history", "priorities", "preferences", "visual", "confirm",
];

export const RANK_LABEL = ["1 — Principal", "2 — Secundária", "3 — Secundária"];

export const LIMIT_MESSAGE =
  `Você já escolheu ${MAX_PRIORITIES} regiões. Remova uma para trocar.`;

export const BALANCED_MESSAGE = "Treino equilibrado — nenhuma região priorizada.";

/**
 * Liga/desliga uma regiao.
 *
 * @returns {{priorities: string[], warning: string}} lista nova e o aviso a exibir.
 *          A quarta tentativa nao altera a lista e devolve mensagem clara — o botao
 *          continua clicavel de proposito, senao o usuario nao receberia explicacao
 *          nenhuma ao tentar.
 */
export function togglePriority(priorities, region) {
  const atuais = priorities || [];
  const pos = atuais.indexOf(region);
  if (pos >= 0) {
    return { priorities: atuais.filter(v => v !== region), warning: "" };
  }
  if (atuais.length >= MAX_PRIORITIES) {
    return { priorities: atuais, warning: LIMIT_MESSAGE };
  }
  return { priorities: [...atuais, region], warning: "" };
}

/** Papel pela posicao: a primeira e a principal, as demais sao secundarias. */
export function roleFor(index) {
  return index === 0 ? "Principal" : "Secundária";
}

export function stepNumber(screen) {
  return ONBOARDING_STEPS.indexOf(screen) + 1;
}

export function nextStep(screen) {
  const i = ONBOARDING_STEPS.indexOf(screen);
  return i >= 0 && i < ONBOARDING_STEPS.length - 1 ? ONBOARDING_STEPS[i + 1] : null;
}

export function previousStep(screen) {
  const i = ONBOARDING_STEPS.indexOf(screen);
  return i > 0 ? ONBOARDING_STEPS[i - 1] : null;
}
