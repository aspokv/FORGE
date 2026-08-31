import { ONBOARDING_STEPS } from "./musclePriorities";
import { passosPendentes } from "./onboardingResume";

export const ASSESSMENT_MODE_RESUME = "resume";
export const ASSESSMENT_MODE_FULL = "full";

/** Retomada evita repeticao; refazer avaliacao reabre absolutamente todas as etapas. */
export function passosDoAssessment(perfil, mode = ASSESSMENT_MODE_RESUME) {
  return mode === ASSESSMENT_MODE_FULL
    ? [...ONBOARDING_STEPS]
    : passosPendentes(perfil);
}

export function deveAbrirBuilderDepois(automationMode) {
  return automationMode === "FORGE_PRO";
}

export function deveMostrarPreview(automationMode) {
  return automationMode === "FORGE_ASSISTED";
}
