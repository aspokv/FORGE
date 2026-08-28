import { ONBOARDING_STEPS } from "./musclePriorities";
import {
  anteriorNaLista,
  passosPendentes,
  prioridadesRespondidas,
  proximoNaLista,
  respostasIniciais,
} from "./onboardingResume";

const PERFIL_APOS_PRE_AVALIACAO = {
  sex: "female",
  experience: "Intermediário",
  goal: "Hipertrofia",
  days: 4,
  priorities: ["Glúteos", "Posteriores"],
  nutrition_assessment: { goal: "fat_loss", intensity: "moderado" },
  preassessment_applied_at: "2026-08-28T12:00:00+00:00",
};

describe("prioridades ja respondidas", () => {
  test("lista preenchida conta como respondida", () => {
    expect(prioridadesRespondidas({ priorities: ["Glúteos"] })).toBe(true);
  });

  test("treino equilibrado tambem e uma resposta", () => {
    // O caso que um teste ingenuo erraria: lista vazia com carimbo do servidor significa
    // "respondi e nao quis nenhuma", nao "nunca respondi".
    expect(prioridadesRespondidas({
      priorities: [], preassessment_applied_at: "2026-08-28T12:00:00+00:00",
    })).toBe(true);
  });

  test("perfil sem resposta nenhuma nao conta", () => {
    expect(prioridadesRespondidas({ priorities: [] })).toBe(false);
    expect(prioridadesRespondidas({})).toBe(false);
    expect(prioridadesRespondidas(null)).toBe(false);
  });
});

describe("passos pendentes", () => {
  test("quem respondeu a pre-avaliacao nao ve a etapa de prioridades", () => {
    const passos = passosPendentes(PERFIL_APOS_PRE_AVALIACAO);
    expect(passos).not.toContain("priorities");
    expect(passos.length).toBe(ONBOARDING_STEPS.length - 1);
  });

  test("quem nao respondeu ve todas as etapas", () => {
    expect(passosPendentes({})).toEqual([...ONBOARDING_STEPS]);
    expect(passosPendentes(null)).toEqual([...ONBOARDING_STEPS]);
  });

  test("a ordem das etapas restantes e preservada", () => {
    const passos = passosPendentes(PERFIL_APOS_PRE_AVALIACAO);
    const esperado = ONBOARDING_STEPS.filter((p) => p !== "priorities");
    expect(passos).toEqual(esperado);
  });

  test("as etapas que dependem de dados nao coletados continuam", () => {
    const passos = passosPendentes(PERFIL_APOS_PRE_AVALIACAO);
    // idade, altura e peso nao sao perguntados na pre-avaliacao
    expect(passos).toContain("profile");
    expect(passos).toContain("confirm");
  });
});

describe("valores iniciais do formulario", () => {
  test("traz o que ja foi respondido", () => {
    const r = respostasIniciais(PERFIL_APOS_PRE_AVALIACAO);
    expect(r.sex).toBe("female");
    expect(r.experience).toBe("Intermediário");
    expect(r.days).toBe(4);
    expect(r.goal).toBe("Hipertrofia");
    expect(r.priorities).toEqual(["Glúteos", "Posteriores"]);
  });

  test("traduz objetivo e ritmo alimentares para os nomes do formulario", () => {
    const r = respostasIniciais(PERFIL_APOS_PRE_AVALIACAO);
    expect(r.body_goal).toBe("fat_loss");
    expect(r.goal_intensity).toBe("moderado");
  });

  test("nao inventa campo que nao foi respondido", () => {
    const r = respostasIniciais(PERFIL_APOS_PRE_AVALIACAO);
    expect("age" in r).toBe(false);
    expect("weight_kg" in r).toBe(false);
  });

  test("campo vazio nao sobrescreve o padrao do formulario", () => {
    const r = respostasIniciais({ sex: "", experience: "   ", days: null });
    expect(r).toEqual({});
  });

  test("treino equilibrado chega como lista vazia, e nao como ausencia", () => {
    const r = respostasIniciais({
      priorities: [], preassessment_applied_at: "2026-08-28T12:00:00+00:00",
    });
    expect(r.priorities).toEqual([]);
  });

  test("perfil ausente devolve objeto vazio sem quebrar", () => {
    expect(respostasIniciais(null)).toEqual({});
    expect(respostasIniciais()).toEqual({});
  });

  test("a lista de prioridades e copiada, nao compartilhada", () => {
    const perfil = { priorities: ["Glúteos"] };
    const r = respostasIniciais(perfil);
    r.priorities.push("Bíceps");
    expect(perfil.priorities).toEqual(["Glúteos"]);
  });
});

describe("navegacao com etapas removidas", () => {
  const lista = ["profile", "history", "preferences", "confirm"];

  test("avanca pulando a etapa removida", () => {
    expect(proximoNaLista(lista, "history")).toBe("preferences");
  });

  test("volta pulando a etapa removida", () => {
    expect(anteriorNaLista(lista, "preferences")).toBe("history");
  });

  test("o fim e o comeco nao saem da lista", () => {
    expect(proximoNaLista(lista, "confirm")).toBeNull();
    expect(anteriorNaLista(lista, "profile")).toBeNull();
  });

  test("lista ausente cai na sequencia completa", () => {
    expect(proximoNaLista(null, "profile")).toBe(ONBOARDING_STEPS[1]);
    expect(proximoNaLista([], "profile")).toBe(ONBOARDING_STEPS[1]);
  });

  test("etapa desconhecida nao trava a navegacao", () => {
    expect(proximoNaLista(lista, "inventada")).toBeNull();
    expect(anteriorNaLista(lista, "inventada")).toBeNull();
  });
});
