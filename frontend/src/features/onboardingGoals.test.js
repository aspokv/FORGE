/**
 * Objetivo corporal do onboarding e as regras de transicao entre ritmos.
 *
 * Dois riscos que estes testes travam: trocar sem querer o valor persistido (quebraria
 * perfil existente) e deixar um ritmo agressivo ativo depois de mudar de objetivo.
 */
import {
  DEFAULT_BODY_GOAL, LEGACY_TRAINING_GOAL, defaultIntensityFor, goalFromCatalog,
  intensityForSubmit, intensityOnGoalChange,
} from "./onboardingGoals";

// Espelha GET /nutrition/goal-catalog
const CATALOGO = [
  {
    id: "muscle_gain", label: "Ganhar massa muscular",
    description: "Aumente massa muscular...", intensity_question: "Qual ritmo de ganho voce deseja?",
    default_intensity: "controlado",
    intensities: [
      { id: "controlado", label: "Controlado", recommended: true, advanced: false, delta_pct: 7 },
      { id: "moderado", label: "Moderado", recommended: false, advanced: false, delta_pct: 13 },
      { id: "agressivo", label: "Agressivo/Atleta", recommended: false, advanced: true, delta_pct: 18, warning: "..." },
    ],
  },
  {
    id: "fat_loss", label: "Emagrecer e definir",
    description: "Reduza gordura...", intensity_question: "Qual intensidade de emagrecimento voce deseja?",
    default_intensity: "moderado",
    intensities: [
      { id: "leve", label: "Leve", recommended: false, advanced: false, delta_pct: -13 },
      { id: "moderado", label: "Moderado", recommended: true, advanced: false, delta_pct: -18 },
      { id: "agressivo", label: "Agressivo/Atleta", recommended: false, advanced: true, delta_pct: -30, carb_range_g: [20, 50], warning: "..." },
    ],
  },
  {
    id: "maintenance", label: "Manter e recompor",
    description: "Mantenha o peso...", intensity_question: null,
    default_intensity: null, intensities: [],
  },
];

describe("a secao Objetivo trata so do corpo", () => {
  it("oferece exatamente os tres objetivos corporais", () => {
    expect(CATALOGO.map(g => g.id)).toEqual(["muscle_gain", "fat_loss", "maintenance"]);
  });

  it("nao oferece objetivo de treino nem prioridade muscular", () => {
    const rotulos = CATALOGO.map(g => g.label).join(" | ");
    expect(rotulos).not.toMatch(/desempenho/i);
    expect(rotulos).not.toMatch(/regi/i);
    expect(rotulos).not.toMatch(/priorizar/i);
  });

  it("comeca em Ganhar massa muscular, como antes", () => {
    expect(DEFAULT_BODY_GOAL).toBe("muscle_gain");
  });
});

describe("compatibilidade do valor gravado em profile.goal", () => {
  it("reaproveita Recomposicao para manter e recompor", () => {
    expect(LEGACY_TRAINING_GOAL.maintenance).toBe("Recomposição");
  });

  it("mantem Hipertrofia para ganho de massa", () => {
    expect(LEGACY_TRAINING_GOAL.muscle_gain).toBe("Hipertrofia");
  });

  it("da rotulo proprio ao emagrecimento, sem colidir com manutencao", () => {
    expect(LEGACY_TRAINING_GOAL.fat_loss).toBe("Emagrecimento");
    expect(LEGACY_TRAINING_GOAL.fat_loss).not.toBe(LEGACY_TRAINING_GOAL.maintenance);
  });

  it("cobre os tres objetivos e nada alem disso", () => {
    expect(Object.keys(LEGACY_TRAINING_GOAL).sort())
      .toEqual(["fat_loss", "maintenance", "muscle_gain"]);
  });
});

describe("ritmos revelados por objetivo", () => {
  it("ganho revela tres ritmos", () => {
    expect(goalFromCatalog(CATALOGO, "muscle_gain").intensities).toHaveLength(3);
  });

  it("emagrecimento continua com Leve, Moderado e Agressivo", () => {
    expect(goalFromCatalog(CATALOGO, "fat_loss").intensities.map(i => i.id))
      .toEqual(["leve", "moderado", "agressivo"]);
  });

  it("manter e recompor nao apresenta ritmo", () => {
    expect(goalFromCatalog(CATALOGO, "maintenance").intensities).toHaveLength(0);
    expect(defaultIntensityFor(CATALOGO, "maintenance")).toBe("");
    expect(intensityForSubmit(CATALOGO, "maintenance", "agressivo")).toBeNull();
  });
});

describe("padroes", () => {
  it("ganho comeca em Controlado", () => {
    expect(defaultIntensityFor(CATALOGO, "muscle_gain")).toBe("controlado");
  });

  it("emagrecimento segue comecando em Moderado", () => {
    expect(defaultIntensityFor(CATALOGO, "fat_loss")).toBe("moderado");
  });

  it("agressivo nunca e padrao de nenhum objetivo", () => {
    for (const g of CATALOGO) {
      expect(defaultIntensityFor(CATALOGO, g.id)).not.toBe("agressivo");
    }
  });
});

describe("transicao entre objetivos", () => {
  it("sair de cutting agressivo para ganho nao deixa o agressivo ativo", () => {
    expect(intensityOnGoalChange(CATALOGO, "muscle_gain")).toBe("controlado");
  });

  it("sair de superavit agressivo para emagrecimento nao deixa o agressivo ativo", () => {
    expect(intensityOnGoalChange(CATALOGO, "fat_loss")).toBe("moderado");
  });

  it("ir para manutencao limpa o ritmo", () => {
    expect(intensityOnGoalChange(CATALOGO, "maintenance")).toBe("");
  });

  it("ritmo de um objetivo nao atravessa para o outro no envio", () => {
    expect(intensityForSubmit(CATALOGO, "muscle_gain", "leve")).toBeNull();
    expect(intensityForSubmit(CATALOGO, "fat_loss", "controlado")).toBeNull();
  });

  it("ritmo valido do proprio objetivo e preservado", () => {
    expect(intensityForSubmit(CATALOGO, "muscle_gain", "moderado")).toBe("moderado");
    expect(intensityForSubmit(CATALOGO, "fat_loss", "agressivo")).toBe("agressivo");
  });
});

describe("robustez", () => {
  it("catalogo ainda nao carregado nao quebra a tela", () => {
    expect(goalFromCatalog([], "fat_loss")).toBeNull();
    expect(defaultIntensityFor(undefined, "fat_loss")).toBe("");
    expect(intensityForSubmit(undefined, "fat_loss", "moderado")).toBeNull();
  });

  it("objetivo desconhecido (perfil legado) nao envia ritmo", () => {
    expect(intensityForSubmit(CATALOGO, "Performance", "agressivo")).toBeNull();
    expect(defaultIntensityFor(CATALOGO, "Especialização")).toBe("");
  });
});
