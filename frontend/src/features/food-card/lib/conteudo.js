/**
 * O texto que aparece na peça: descrições e rótulos de macro.
 *
 * Estas frases são uma CÓPIA de `backend/food_card.py`, e a cópia é deliberada: o
 * servidor grava a CHAVE (`protein_source`), não a frase. Guardar a chave permite
 * corrigir o texto depois sem reescrever os Food Cards já salvos — mas exige que os dois
 * lados concordem sobre quais chaves existem.
 *
 * `conteudo.test.js` lê o Python e compara. É o que transforma uma divergência em teste
 * vermelho no CI, em vez de num card publicado sem descrição.
 *
 * A biblioteca é FECHADA de propósito. Deixar um modelo escrever "rico em antioxidantes
 * que combatem o envelhecimento" numa peça que o atleta publica é alegação nutricional
 * inventada, com o nome do FORGE em cima. Sem frase segura, o card sai sem descrição —
 * o que é diferente de inventar uma.
 */

export const DESCRICOES = {
  protein_source: "Fonte de proteína de alto valor biológico",
  lean_protein: "Fonte de proteína com baixo teor de gordura",
  complex_carb: "Fonte de carboidratos complexos e fibras",
  simple_carb: "Fonte de carboidratos de rápida absorção",
  fat_source: "Fonte de gorduras",
  vegetable: "Fonte de fibras e micronutrientes",
  dairy: "Fonte de proteína e cálcio",
};

export const ROTULO_DO_MACRO = {
  protein: "PROTEÍNA",
  carbs: "CARBOIDRATOS",
  fat: "GORDURA",
};

export const CAMPO_DO_MACRO = {
  protein: "protein",
  carbs: "carbs",
  fat: "fat",
};

export const MACROS = ["protein", "carbs", "fat"];

/** A frase do alimento, ou string vazia. Nunca inventa. */
export function descricaoDe(item) {
  return DESCRICOES[item?.descriptionKey] || "";
}

/** Quantas gramas do macro principal este alimento traz. */
export function valorDoMacro(item) {
  const macro = CAMPO_DO_MACRO[item?.primaryMacro] || "protein";
  return Math.round(Number(item?.[macro] || 0));
}

/**
 * A quantidade como ela aparece no card: "180 g", "4 unidades".
 *
 * O backend guarda sempre em gramas porque é assim que a refeição foi pesada. Unidade
 * diferente exigiria uma segunda conversão, e uma segunda conversão é uma segunda
 * chance de o card discordar do diário.
 */
export function quantidadeDe(item) {
  const valor = Number(item?.quantity || 0);
  const unidade = item?.unit || "g";
  const numero = Number.isInteger(valor) ? valor : Math.round(valor * 10) / 10;
  return `${String(numero).replace(".", ",")} ${unidade}`;
}
