import {
  ASSESSMENT_MODE_FULL,
  ASSESSMENT_MODE_RESUME,
  passosDoAssessment,
  deveAbrirBuilderDepois,
  deveMostrarPreview,
} from "./reassessmentMode";
import { ONBOARDING_STEPS } from "./musclePriorities";

describe("reassessment mode", () => {
  const perfilRespondido = {
    priorities: ["Peitoral superior"],
    preassessment_applied_at: "2026-08-31T00:00:00Z",
  };

  test("resume pode pular prioridades ja respondidas", () => {
    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_RESUME)).not.toContain("priorities");
  });

  test("refazer avaliacao sempre reabre todas as etapas", () => {
    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_FULL)).toEqual(ONBOARDING_STEPS);
    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_FULL)).toContain("priorities");
  });

  test("cada modo de automacao segue um destino diferente", () => {
    expect(deveMostrarPreview("FORGE_ASSISTED")).toBe(true);
    expect(deveMostrarPreview("FORGE_AUTO")).toBe(false);
    expect(deveAbrirBuilderDepois("FORGE_PRO")).toBe(true);
    expect(deveAbrirBuilderDepois("FORGE_AUTO")).toBe(false);
  });
});
