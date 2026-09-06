import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import VisualAssessmentResult from "./VisualAssessmentResult";

/**
 * O resultado da analise nao pode falar de infraestrutura.
 *
 * A tela mostrava o nome do provedor de IA, uma contagem interna e, no caminho de erro, o
 * nome da variavel de ambiente que faltava configurar. Esses testes existem para nenhum
 * deles voltar sem alguem perceber — o do erro em especial, porque nome de variavel de
 * servidor num texto de cliente e vazamento, nao so feiura.
 */
const render = (resultado) =>
  new DOMParser().parseFromString(
    renderToStaticMarkup(<VisualAssessmentResult resultado={resultado} />),
    "text/html"
  );

const COMPLETO = {
  status: "completed",
  observations: {
    Peitoral: { development: "forte", confidence: "alta" },
    Dorsais: { development: "muito forte", confidence: "média" },
    Panturrilhas: { development: "fraco", confidence: "alta" },
    Ombros: { development: "muito fraco", confidence: "média" },
    Abdômen: { development: "proporcional", confidence: "alta" },
    Glúteos: { development: "fraco", confidence: "baixa" },
  },
  symmetry_notes: "Lados aparentam simetria semelhante.",
  proportion_notes: "Tronco proporcional aos membros.",
  suggested_priorities: ["Panturrilhas", "Ombros"],
  limitations: ["Foto única, de frente."],
};

const PROIBIDOS = [
  "Gemini",
  "GEMINI_API_KEY",
  "Forge Vision",
  "prioridades sugeridas",
  "API",
  "modelo",
];

test("nenhum termo tecnico ou nome de provedor aparece no resultado", () => {
  const texto = render(COMPLETO).body.textContent;
  PROIBIDOS.forEach((termo) => expect(texto).not.toContain(termo));
});

test("nenhum termo tecnico aparece quando a analise falha", () => {
  ["error", "unavailable"].forEach((status) => {
    const texto = render({ status, message: "GEMINI_API_KEY ausente" }).body.textContent;
    PROIBIDOS.forEach((termo) => expect(texto).not.toContain(termo));
    // A mensagem crua do servidor tambem nao pode vazar para a tela.
    expect(texto).not.toContain("ausente");
    expect(texto).toContain("Não foi possível concluir a análise agora");
  });
});

test("o resultado vem organizado nos blocos pedidos", () => {
  const texto = render(COMPLETO).body.textContent;
  [
    "Análise visual concluída",
    "Observações do FORGE",
    "Pontos fortes",
    "Pontos de atenção",
    "Prioridades de treino",
    "Simetria, proporção e postura",
    "Limitações da análise",
  ].forEach((bloco) => expect(texto).toContain(bloco));
});

test("pontos fortes e de atencao saem das observacoes, sem inventar", () => {
  const doc = render(COMPLETO);
  const fortes = [...doc.querySelectorAll(".va-forte li")].map((e) => e.textContent);
  const atencao = [...doc.querySelectorAll(".va-atencao li")].map((e) => e.textContent);

  expect(fortes.sort()).toEqual(["Dorsais", "Peitoral"]);
  expect(atencao.sort()).toEqual(["Ombros", "Panturrilhas"]);

  // "proporcional" nao e nem forte nem atencao.
  expect([...fortes, ...atencao]).not.toContain("Abdômen");
  // Confianca baixa fica de fora dos dois grupos: a analise mesma disse que nao viu bem,
  // e promover isso a "ponto fraco" seria dar como certo o que ela marcou como incerto.
  expect([...fortes, ...atencao]).not.toContain("Glúteos");
});

test("deixa claro que sao observacoes visuais, e nao diagnostico", () => {
  const texto = render(COMPLETO).body.textContent;
  expect(texto).toContain("não diagnóstico médico");
});

test("a fala de treinador tem prioridade sobre as etiquetas derivadas", () => {
  const doc = render({
    ...COMPLETO,
    strong_points: ["Dorsais dão largura clara na vista de frente."],
    attention_points: ["Panturrilhas ficam atrás do resto da perna."],
    training_priorities: ["Panturrilhas: dois estímulos semanais, com pausa embaixo."],
    next_cycle: ["Segure a carga do supino e suba volume de posterior de ombro."],
    posture_notes: "Ombro direito levemente à frente na foto de frente.",
  });
  const texto = doc.body.textContent;
  expect(texto).toContain("Dorsais dão largura clara");
  expect(texto).toContain("Panturrilhas: dois estímulos semanais");
  expect(texto).toContain("Segure a carga do supino");
  expect(texto).toContain("Ombro direito levemente à frente");
  // Com a frase do treinador presente, a etiqueta crua nao aparece.
  expect(doc.querySelectorAll(".va-forte li")).toHaveLength(0);
});

test("avaliacao antiga, sem os campos novos, ainda mostra alguma coisa", () => {
  // Perfil gravado antes deste formato nao tem strong_points. Sem o degrau para as
  // etiquetas derivadas de `observations`, o historico dessas pessoas ficaria vazio.
  const doc = render(COMPLETO);
  expect(doc.querySelectorAll(".va-forte li").length).toBeGreaterThan(0);
  expect(doc.body.textContent).toContain("Prioridades de treino");
});

test("aguenta uma analise sem observacoes, sem quebrar", () => {
  const texto = render({ status: "completed" }).body.textContent;
  expect(texto).toContain("Análise visual concluída");
  expect(texto).toContain("As fotos não deixaram nenhum grupo claramente destacado.");
});
