/**
 * Recolher um exercicio e esconder informacao. So pode acontecer quando ele esta MESMO
 * terminado — e o resumo que fica no lugar precisa dizer a verdade sobre o que foi feito.
 */
import {exercicioConcluido, resumoDoExercicio, textoDoResumo} from "./exercicioConcluido";

const feitas = (id, quantas) => {
  const d = {};
  for (let i = 0; i < quantas; i += 1) d[id + i] = true;
  return d;
};

// ── Quando conta como concluido ──────────────────────────────────────────────────────

test("todas as series marcadas concluem o exercicio", () => {
  expect(exercicioConcluido(feitas("supino", 3), "supino", 3)).toBe(true);
});

test("uma serie faltando mantem o exercicio aberto", () => {
  expect(exercicioConcluido(feitas("supino", 2), "supino", 3)).toBe(false);
});

test("marcar a ultima sem as anteriores nao conclui", () => {
  // Da para tocar fora de ordem; recolher aqui esconderia series que faltam de verdade.
  expect(exercicioConcluido({supino2: true}, "supino", 3)).toBe(false);
});

test("series de OUTRO exercicio nao concluem este", () => {
  expect(exercicioConcluido(feitas("remada", 3), "supino", 3)).toBe(false);
});

test("exercicio sem series nunca aparece como concluido", () => {
  for (const vazio of [0, null, undefined, NaN, -2]) {
    expect(exercicioConcluido(feitas("supino", 3), "supino", vazio)).toBe(false);
  }
});

test("ausencia de registro nao quebra", () => {
  expect(exercicioConcluido(null, "supino", 3)).toBe(false);
  expect(exercicioConcluido({}, "", 3)).toBe(false);
});

// ── O resumo que fica no lugar ───────────────────────────────────────────────────────

test("a carga do resumo e a MAIOR das series, nao a ultima", () => {
  // Progressao normal: sobe, e a ultima cai com a fadiga. Mostrar 50 diria menos do que
  // a pessoa levantou.
  const inputs = {"supino-0": {weight: "50"}, "supino-1": {weight: "65"}, "supino-2": {weight: "60"}};
  expect(resumoDoExercicio(inputs, "supino", 3).carga).toBe(65);
});

test("virgula decimal e lida como o brasileiro escreve", () => {
  const inputs = {"supino-0": {weight: "62,5"}};
  expect(resumoDoExercicio(inputs, "supino", 1).carga).toBe(62.5);
});

test("sem registro, cai na carga prescrita", () => {
  expect(resumoDoExercicio({}, "supino", 3, 40).carga).toBe(40);
});

test("peso do corpo nao inventa carga", () => {
  const r = resumoDoExercicio({"barra-0": {weight: "0"}}, "barra", 1, 0);
  expect(r.carga).toBeNull();
  expect(textoDoResumo(r)).toBe("1 série");
});

test("texto sai como a pessoa le", () => {
  expect(textoDoResumo({series: 3, carga: 65})).toBe("3 séries · 65 kg");
  expect(textoDoResumo({series: 1, carga: 20})).toBe("1 série · 20 kg");
  expect(textoDoResumo({series: 4, carga: 62.5})).toBe("4 séries · 62,5 kg");
});

test("resumo vazio nao vira texto solto", () => {
  expect(textoDoResumo(null)).toBe("");
  expect(textoDoResumo({series: 0})).toBe("");
});

test("valor impossivel no campo nao vira carga", () => {
  // O campo e de texto: da para digitar qualquer coisa.
  const r = resumoDoExercicio({"supino-0": {weight: "muito"}}, "supino", 1);
  expect(r.carga).toBeNull();
});
