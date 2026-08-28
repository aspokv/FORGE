/**
 * Etapa unica de prioridades musculares.
 *
 * O Muscle Map (18 telas, ~36 decisoes) saiu do onboarding. Estes testes travam o que
 * passou a ser a fonte de verdade: a LISTA ORDENADA, onde a posicao define o papel.
 */
import {
  BALANCED_MESSAGE, LIMIT_MESSAGE, MAX_PRIORITIES, ONBOARDING_STEPS, RANK_LABEL,
  nextStep, previousStep, roleFor, stepNumber, togglePriority,
} from "./musclePriorities";

const escolher = (...regioes) =>
  regioes.reduce((lista, r) => togglePriority(lista, r).priorities, []);

describe("etapas do onboarding", () => {
  it("nao inclui mais o Muscle Map", () => {
    expect(ONBOARDING_STEPS).not.toContain("muscle");
  });

  it("passou a ter seis etapas", () => {
    expect(ONBOARDING_STEPS).toHaveLength(6);
    expect(ONBOARDING_STEPS).toEqual([
      "profile", "history", "priorities", "preferences", "visual", "confirm",
    ]);
  });

  it("prioridades continua sendo a terceira etapa", () => {
    expect(stepNumber("priorities")).toBe(3);
  });

  it("avanca de prioridades direto para preferencias", () => {
    expect(nextStep("priorities")).toBe("preferences");
  });

  it("voltar de preferencias cai em prioridades, nao no muscle map", () => {
    expect(previousStep("preferences")).toBe("priorities");
  });

  it("a primeira etapa nao tem anterior e a ultima nao tem proxima", () => {
    expect(previousStep("profile")).toBeNull();
    expect(nextStep("confirm")).toBeNull();
  });
});

describe("selecionar regioes", () => {
  it("nenhuma selecao e um estado valido", () => {
    expect(escolher()).toEqual([]);
  });

  it("a primeira escolha vira a principal", () => {
    const lista = escolher("Glúteos");
    expect(lista).toEqual(["Glúteos"]);
    expect(roleFor(0)).toBe("Principal");
  });

  it("segunda e terceira viram secundarias", () => {
    const lista = escolher("Glúteos", "Quadríceps", "Deltóide lateral");
    expect(lista).toEqual(["Glúteos", "Quadríceps", "Deltóide lateral"]);
    expect(roleFor(1)).toBe("Secundária");
    expect(roleFor(2)).toBe("Secundária");
  });

  it("os rotulos numerados batem com a ordem", () => {
    expect(RANK_LABEL).toEqual(["1 — Principal", "2 — Secundária", "3 — Secundária"]);
  });
});

describe("limite de tres", () => {
  it("a quarta selecao nao entra e explica o motivo", () => {
    const tres = escolher("Glúteos", "Quadríceps", "Bíceps");
    const r = togglePriority(tres, "Tríceps");
    expect(r.priorities).toEqual(tres);
    expect(r.warning).toBe(LIMIT_MESSAGE);
    expect(r.warning).toMatch(/Remova uma/);
  });

  it("o limite e tres", () => {
    expect(MAX_PRIORITIES).toBe(3);
    expect(escolher("a", "b", "c", "d")).toHaveLength(3);
  });

  it("selecionar dentro do limite nao gera aviso", () => {
    expect(togglePriority(["Glúteos"], "Bíceps").warning).toBe("");
  });
});

describe("remover reorganiza a ordem", () => {
  it("tirar a principal promove a seguinte", () => {
    const tres = escolher("Glúteos", "Quadríceps", "Bíceps");
    const { priorities } = togglePriority(tres, "Glúteos");
    expect(priorities).toEqual(["Quadríceps", "Bíceps"]);
    expect(roleFor(priorities.indexOf("Quadríceps"))).toBe("Principal");
  });

  it("tirar a do meio nao deixa lacuna entre a 1 e a 3", () => {
    const tres = escolher("Glúteos", "Quadríceps", "Bíceps");
    const { priorities } = togglePriority(tres, "Quadríceps");
    expect(priorities).toEqual(["Glúteos", "Bíceps"]);
    // as posicoes seguem contiguas: 0 e 1, sem buraco
    expect(priorities.map((_, i) => i)).toEqual([0, 1]);
  });

  it("remover libera espaco para uma nova escolha", () => {
    const tres = escolher("Glúteos", "Quadríceps", "Bíceps");
    const semUma = togglePriority(tres, "Bíceps").priorities;
    const r = togglePriority(semUma, "Tríceps");
    expect(r.warning).toBe("");
    expect(r.priorities).toEqual(["Glúteos", "Quadríceps", "Tríceps"]);
  });

  it("tocar de novo na mesma regiao remove", () => {
    expect(togglePriority(["Glúteos"], "Glúteos").priorities).toEqual([]);
  });

  it("remover limpa o aviso de limite", () => {
    const tres = escolher("Glúteos", "Quadríceps", "Bíceps");
    expect(togglePriority(tres, "Glúteos").warning).toBe("");
  });
});

describe("treino equilibrado", () => {
  it("tem uma mensagem propria para o resumo", () => {
    expect(BALANCED_MESSAGE).toMatch(/equilibrado/i);
    expect(BALANCED_MESSAGE).toMatch(/nenhuma regi/i);
  });

  it("lista vazia e uma escolha legitima, nao um estado invalido", () => {
    expect(togglePriority([], "Glúteos").priorities).toEqual(["Glúteos"]);
    expect(togglePriority(["Glúteos"], "Glúteos").priorities).toEqual([]);
  });
});

describe("robustez", () => {
  it("lista ausente nao quebra", () => {
    expect(togglePriority(undefined, "Glúteos").priorities).toEqual(["Glúteos"]);
    expect(togglePriority(null, "Glúteos").warning).toBe("");
  });

  it("nao duplica uma regiao ja escolhida", () => {
    const lista = escolher("Glúteos", "Glúteos");
    expect(lista).toEqual([]);
  });
});
