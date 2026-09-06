/**
 * Macros reais de uma refeicao, somados a partir dos alimentos.
 *
 * A refeicao traz `target_cal`, `target_protein` e `target_fat` — mas NAO traz
 * carboidrato. Mostrar so o que vem pronto deixaria um buraco no cartao, e inventar o
 * valor que falta seria pior que o buraco.
 *
 * Cada alimento, porem, traz os macros completos junto da gramagem de referencia
 * (`food.grams`) e a quantidade que a refeicao usa (`grams`). Somando na proporcao, sai o
 * valor real da refeicao — que e o que a pessoa esta comendo, e nao a meta que o plano
 * calculou.
 *
 * Quando um alimento nao tem um macro, ele nao entra na soma e o campo e marcado como
 * incompleto. A tela mostra "não informado" em vez de um numero menor que o verdadeiro:
 * um total que ignora ingredientes em silencio e pior que a ausencia, porque parece certo.
 */

const numero = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/**
 * Soma os alimentos da refeicao.
 *
 * Devolve `{ kcal, protein, carbs, fat, completo }`. Cada macro e `null` quando algum
 * alimento nao informou aquele campo.
 */
export function macrosDaRefeicao(refeicao) {
  const alimentos = refeicao?.foods || [];
  if (!alimentos.length) {
    return { kcal: null, protein: null, carbs: null, fat: null, completo: false };
  }

  const soma = { kcal: 0, protein: 0, carbs: 0, fat: 0 };
  const faltou = { kcal: false, protein: false, carbs: false, fat: false };

  alimentos.forEach((item) => {
    const base = item?.food || {};
    const gramasDaBase = numero(base.grams);
    const gramasUsados = numero(item?.grams);
    // Sem as duas gramagens nao da para escalar: o alimento inteiro fica de fora, e todos
    // os macros ficam marcados como incompletos.
    if (!gramasDaBase || !gramasUsados) {
      Object.keys(faltou).forEach((k) => (faltou[k] = true));
      return;
    }
    const fator = gramasUsados / gramasDaBase;
    const campos = {
      kcal: numero(base.kcal),
      protein: numero(base.protein_g),
      carbs: numero(base.carbs_g),
      fat: numero(base.fat_g),
    };
    Object.entries(campos).forEach(([chave, valor]) => {
      if (valor === null) faltou[chave] = true;
      else soma[chave] += valor * fator;
    });
  });

  const saida = {};
  Object.keys(soma).forEach((k) => {
    saida[k] = faltou[k] ? null : Math.round(soma[k]);
  });
  saida.completo = !Object.values(faltou).some(Boolean);
  return saida;
}

/** Formata um macro para a tela. Ausencia e dita, e nao escondida com zero. */
export function textoDoMacro(valor, unidade = "g") {
  return valor === null || valor === undefined ? "não informado" : `${valor} ${unidade}`;
}
