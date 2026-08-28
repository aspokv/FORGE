/**
 * Objetivo CORPORAL/ALIMENTAR do onboarding.
 *
 * A secao "Objetivo" tratava quatro coisas diferentes ao mesmo tempo: dois objetivos
 * corporais (ganhar massa, emagrecer), um objetivo de treino (desempenho) e uma
 * configuracao de prioridade muscular (priorizar uma regiao). Agora ela trata so o
 * objetivo corporal — prioridade muscular ja tem a etapa dela, e desempenho saiu da
 * selecao sem que o suporte no backend fosse removido.
 *
 * Os tres ids (muscle_gain / fat_loss / maintenance) sao os que
 * NutritionAssessmentIn.goal ja aceitava: nenhum enum novo foi inventado. Rotulo,
 * descricao, ritmos e avisos vem do backend (GET /nutrition/goal-catalog), entao a
 * metodologia continua com uma fonte de verdade so.
 *
 * Mora fora do App.js para poder ser testado com o Jest que ja vem no react-scripts.
 */

/**
 * Rotulo de treino que continua sendo gravado em profile.goal.
 *
 * profile.goal e historico/exibicao: determine_split recebe goal mas nunca ramifica
 * nele (o split sai de dias + experiencia), e nenhuma outra logica do backend le esse
 * valor. "Recomposição" e reaproveitado para manutencao, como ja existia. Emagrecer
 * ganha rotulo proprio porque nao pode dividir o mesmo valor com manutencao sem ficar
 * ambiguo — e _is_fat_loss_goal ja reconhece "emagrec".
 */
export const LEGACY_TRAINING_GOAL = {
  muscle_gain: "Hipertrofia",
  fat_loss: "Emagrecimento",
  maintenance: "Recomposição",
};

/** Mantem o padrao anterior do formulario ("Hipertrofia"). */
export const DEFAULT_BODY_GOAL = "muscle_gain";

export function goalFromCatalog(catalog, goalId) {
  return (catalog || []).find(g => g.id === goalId) || null;
}

/**
 * Ritmo padrao do objetivo. Vem do backend (Controlado no ganho, Moderado no
 * emagrecimento) e nunca e o Agressivo/Atleta. Manutencao nao tem ritmo.
 */
export function defaultIntensityFor(catalog, goalId) {
  const g = goalFromCatalog(catalog, goalId);
  if (!g || !(g.intensities || []).length) return "";
  return g.default_intensity || "";
}

/**
 * Ritmo a enviar ao backend.
 *
 * Um ritmo so vale dentro do objetivo a que pertence: "leve" nao existe em ganho,
 * "controlado" nao existe em emagrecimento, e manutencao nao tem ritmo nenhum. Assim
 * um valor herdado de uma troca de objetivo nunca atravessa para o outro lado.
 */
export function intensityForSubmit(catalog, goalId, intensity) {
  const g = goalFromCatalog(catalog, goalId);
  if (!g || !(g.intensities || []).length) return null;
  return (g.intensities || []).some(i => i.id === intensity) ? intensity : null;
}

/**
 * O que a intensidade vira quando o atleta troca de objetivo.
 *
 * Sempre o padrao do novo objetivo, nunca o valor anterior: "agressivo" existe nos dois
 * conjuntos, entao carregar o valor adiante deixaria um cutting agressivo virar um
 * superavit agressivo sem ninguem escolher — e o modo avancado jamais pode ser
 * selecionado automaticamente.
 */
export function intensityOnGoalChange(catalog, novoGoalId) {
  return defaultIntensityFor(catalog, novoGoalId);
}
