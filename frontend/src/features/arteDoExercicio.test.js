import {arteEmFaixa} from "./arteDoExercicio";

/**
 * A faixa aparece antes de começar, e some quando o trabalho começa.
 *
 * O defeito que originou isto: a arte de 512×512 era desenhada a 64px na sessão, e o
 * Nicolas abriu o treino e disse que não tinha visto a arte nova. Ela estava lá, do
 * tamanho de um selo, sobre fundo escuro.
 *
 * O que estes testes prendem é o equilíbrio entre as duas coisas que disputam o topo do
 * card: a foto (262px de altura) e a tabela de séries. Elas não competem porque não são
 * usadas ao mesmo tempo — e é isso que pode se perder numa refatoração.
 */
describe("arteEmFaixa", () => {
  test("nenhuma série registrada: a faixa aparece", () => {
    expect(arteEmFaixa({}, "bb-bench-press", 4)).toBe(true);
  });

  // O caso central: a tabela é o que se toca durante a série, repetidas vezes e com o
  // cronômetro correndo. 262px de foto acima dela a empurrariam para fora da dobra.
  test("a primeira série registrada já recolhe a faixa", () => {
    expect(arteEmFaixa({"bb-bench-press0": true}, "bb-bench-press", 4)).toBe(false);
  });

  // Quem reabre um exercício concluído para revisar não pode ver a faixa voltar como se
  // ele nunca tivesse sido feito. Por isso percorre TODAS as séries, e não só a primeira.
  test("série registrada fora de ordem também recolhe", () => {
    expect(arteEmFaixa({"bb-bench-press2": true}, "bb-bench-press", 4)).toBe(false);
  });

  test("exercício concluído não mostra faixa", () => {
    const done = {"bb-bench-press0": true, "bb-bench-press1": true,
                  "bb-bench-press2": true, "bb-bench-press3": true};
    expect(arteEmFaixa(done, "bb-bench-press", 4)).toBe(false);
  });

  // A série do vizinho não conta: cada exercício decide sozinho.
  test("série de outro exercício não recolhe esta faixa", () => {
    expect(arteEmFaixa({"squat0": true}, "bb-bench-press", 4)).toBe(true);
  });

  // Devolver `true` aqui encheria a tela de faixas de um exercício que não existe.
  test.each([
    ["sem id", {}, "", 4],
    ["id indefinido", {}, undefined, 4],
    ["sem séries", {}, "bb-bench-press", 0],
    ["séries inválidas", {}, "bb-bench-press", "abc"],
  ])("%s não mostra faixa", (_rotulo, done, id, sets) => {
    expect(arteEmFaixa(done, id, sets)).toBe(false);
  });

  test("mapa ausente não quebra", () => {
    expect(arteEmFaixa(undefined, "bb-bench-press", 4)).toBe(true);
    expect(arteEmFaixa(null, "bb-bench-press", 4)).toBe(true);
  });
});
