import { ONBOARDING_STEPS } from "./musclePriorities";

/**
 * Retomada do questionario completo depois do pagamento.
 *
 * Quem passou pela pre-avaliacao ja respondeu perfil, objetivo, experiencia, dias e
 * regioes prioritarias. Abrir o questionario em branco faria a pessoa responder tudo de
 * novo logo depois de pagar, que e o pior momento possivel para parecer desorganizado.
 *
 * Duas coisas acontecem aqui: as respostas conhecidas viram valores iniciais do
 * formulario, e a etapa que ja esta inteiramente respondida sai da lista.
 */

/** O campo tem resposta? Zero e falso sao respostas; vazio e ausente nao sao. */
function respondido(valor) {
  if (valor === null || valor === undefined) return false;
  if (typeof valor === "string") return valor.trim() !== "";
  if (Array.isArray(valor)) return valor.length > 0;
  return true;
}

/**
 * Prioridades foram respondidas?
 *
 * Lista vazia e uma resposta legitima — significa "treino equilibrado". Por isso a
 * pergunta nao pode ser "a lista tem itens": quem escolheu equilibrado seria obrigado a
 * responder de novo. O carimbo que o servidor grava ao aplicar a pre-avaliacao e o que
 * distingue "respondeu e nao quis nenhuma" de "nunca respondeu".
 */
export function prioridadesRespondidas(perfil) {
  const p = perfil || {};
  return Boolean(p.preassessment_applied_at) || respondido(p.priorities);
}

/** Etapas que ainda fazem sentido perguntar. */
export function passosPendentes(perfil) {
  if (!perfil) return [...ONBOARDING_STEPS];
  return ONBOARDING_STEPS.filter(
    (passo) => !(passo === "priorities" && prioridadesRespondidas(perfil))
  );
}

/**
 * Valores iniciais do formulario a partir do perfil.
 *
 * Devolve apenas os campos com resposta: o formulario mescla isto sobre os proprios
 * padroes, e mandar `undefined` apagaria o padrao em vez de preservar.
 */
export function respostasIniciais(perfil) {
  const p = perfil || {};
  const inicial = {};

  ["sex", "experience", "goal", "days", "name", "age", "height_cm", "weight_kg"]
    .forEach((campo) => {
      if (respondido(p[campo])) inicial[campo] = p[campo];
    });

  if (respondido(p.priorities)) inicial.priorities = [...p.priorities];
  else if (prioridadesRespondidas(p)) inicial.priorities = [];

  // Objetivo e ritmo alimentares moram em nutrition_assessment; o formulario os chama de
  // body_goal e goal_intensity. Traduzir aqui evita que a tela conheca as duas grafias.
  const nutricao = p.nutrition_assessment || {};
  if (respondido(nutricao.goal)) inicial.body_goal = nutricao.goal;
  if (respondido(nutricao.intensity)) inicial.goal_intensity = nutricao.intensity;

  return inicial;
}

/** Proximo passo dentro de uma lista que pode ter etapas removidas. */
export function proximoNaLista(lista, atual) {
  const passos = lista && lista.length ? lista : ONBOARDING_STEPS;
  const i = passos.indexOf(atual);
  return i >= 0 && i < passos.length - 1 ? passos[i + 1] : null;
}

export function anteriorNaLista(lista, atual) {
  const passos = lista && lista.length ? lista : ONBOARDING_STEPS;
  const i = passos.indexOf(atual);
  return i > 0 ? passos[i - 1] : null;
}
