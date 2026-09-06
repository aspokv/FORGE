import { macrosDaRefeicao, textoDoMacro } from "./macrosDaRefeicao";

/**
 * Os macros do cartao vem da soma dos alimentos, e nao das metas da refeicao.
 *
 * A refeicao traz `target_cal`, `target_protein` e `target_fat`, mas NAO traz
 * carboidrato. O risco aqui nao e o cartao ficar feio: e mostrar um numero que parece
 * certo e nao e. Um total que ignora um ingrediente em silencio engana mais do que a
 * ausencia do valor.
 */

/** Alimento no formato que a API devolve: macros para `grams` de referencia. */
const alimento = (grams, base) => ({ grams, food: base });

const CLARA = { grams: 132, kcal: 68, protein_g: 14, carbs_g: 1, fat_g: 0.2 };
const AVEIA = { grams: 100, kcal: 389, protein_g: 17, carbs_g: 66, fat_g: 7 };

test("soma os alimentos na proporcao da gramagem usada", () => {
  // 180g de clara sobre uma base de 132g = fator 1,3636.
  const m = macrosDaRefeicao({ foods: [alimento(180, CLARA)] });
  expect(m.kcal).toBe(93); // 68 * 1,3636
  expect(m.protein).toBe(19); // 14 * 1,3636
  expect(m.carbs).toBe(1);
  expect(m.completo).toBe(true);
});

test("soma mais de um alimento", () => {
  const m = macrosDaRefeicao({ foods: [alimento(132, CLARA), alimento(50, AVEIA)] });
  expect(m.kcal).toBe(68 + Math.round(389 * 0.5) - 0 + 0 - 0 + 0); // 68 + 194,5
  expect(m.protein).toBe(Math.round(14 + 17 * 0.5));
  expect(m.carbs).toBe(Math.round(1 + 66 * 0.5));
  expect(m.fat).toBe(Math.round(0.2 + 7 * 0.5));
});

test("o carboidrato aparece mesmo sem a refeicao trazer a meta dele", () => {
  // `target_carbs` nao existe na resposta da API. Sem a soma, o cartao ficaria com um
  // macro faltando — e foi por isso que a soma existe.
  const refeicao = { target_cal: 700, target_protein: 33, target_fat: 16, foods: [alimento(100, AVEIA)] };
  expect(refeicao.target_carbs).toBeUndefined();
  expect(macrosDaRefeicao(refeicao).carbs).toBe(66);
});

test("alimento sem um macro marca aquele campo como nao informado", () => {
  const semCarbo = { grams: 100, kcal: 200, protein_g: 20, fat_g: 5 };
  const m = macrosDaRefeicao({ foods: [alimento(100, AVEIA), alimento(100, semCarbo)] });
  // Os que todos informaram continuam somados...
  expect(m.protein).toBe(37);
  // ...e o que faltou vira ausencia, e nao um total menor que o verdadeiro.
  expect(m.carbs).toBeNull();
  expect(m.completo).toBe(false);
});

test("alimento sem gramagem de referencia nao entra na conta", () => {
  const semBase = { kcal: 100, protein_g: 10, carbs_g: 10, fat_g: 1 };
  const m = macrosDaRefeicao({ foods: [alimento(100, semBase)] });
  expect(m.kcal).toBeNull();
  expect(m.completo).toBe(false);
});

test("refeicao sem alimentos nao inventa zero", () => {
  const m = macrosDaRefeicao({ foods: [] });
  expect(m.protein).toBeNull();
  expect(m.carbs).toBeNull();
  // Zero seria uma afirmacao: "esta refeicao nao tem proteina". Ausencia e o correto.
  expect(m.completo).toBe(false);
});

test("refeicao indefinida nao quebra", () => {
  expect(() => macrosDaRefeicao(undefined)).not.toThrow();
  expect(macrosDaRefeicao(undefined).kcal).toBeNull();
});

test("o texto do macro diz quando nao ha valor", () => {
  expect(textoDoMacro(32)).toBe("32 g");
  expect(textoDoMacro(null)).toBe("não informado");
  expect(textoDoMacro(undefined)).toBe("não informado");
  expect(textoDoMacro(0)).toBe("0 g");
});
