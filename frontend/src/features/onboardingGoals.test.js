/**
 * Objetivos do onboarding: nome simples na tela, valor tecnico no banco.
 *
 * O risco desta mudanca e trocar sem querer o valor persistido e quebrar perfil
 * existente — por isso os testes travam os quatro valores.
 */
import { GOALS, FAT_LOSS_GOAL, cutIntensityForSubmit } from "./onboardingGoals";

describe("os quatro objetivos", () => {
  it("aparecem com nome simples, na ordem do produto", () => {
    expect(GOALS.map(g => g.l)).toEqual([
      "Ganhar massa muscular",
      "Emagrecer e definir",
      "Melhorar desempenho",
      "Priorizar uma região",
    ]);
  });

  it("continuam enviando ao backend os valores tecnicos que ja existiam", () => {
    expect(GOALS.map(g => g.v)).toEqual([
      "Hipertrofia", "Recomposição", "Performance", "Especialização",
    ]);
  });

  it("todos tem uma explicacao curta", () => {
    GOALS.forEach(g => {
      expect(typeof g.d).toBe("string");
      expect(g.d.length).toBeGreaterThan(20);
    });
  });

  it("nao inventa objetivo novo", () => {
    expect(GOALS).toHaveLength(4);
  });
});

describe("intensidade de emagrecimento", () => {
  it("so acompanha o objetivo de emagrecer", () => {
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, "agressivo")).toBe("agressivo");
    expect(FAT_LOSS_GOAL).toBe("Recomposição");
  });

  it("nao vai junto de outro objetivo, mesmo se ja tinha sido escolhida", () => {
    for (const outro of ["Hipertrofia", "Performance", "Especialização"]) {
      expect(cutIntensityForSubmit(outro, "agressivo")).toBeNull();
    }
  });

  it("nada escolhido vira null, para o backend usar o padrao dele", () => {
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, "")).toBeNull();
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, undefined)).toBeNull();
  });

  it("nao seleciona agressivo por conta propria", () => {
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, "")).not.toBe("agressivo");
  });

  it("preserva a escolha leve e moderada", () => {
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, "leve")).toBe("leve");
    expect(cutIntensityForSubmit(FAT_LOSS_GOAL, "moderado")).toBe("moderado");
  });
});
