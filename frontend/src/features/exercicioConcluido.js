/**
 * Quando um exercicio acaba, ele deixa de ocupar a tela.
 *
 * Durante a sessao a pessoa olha o telefone com o celular na mao, entre series, muitas
 * vezes suando. O que importa naquele instante e o que FALTA. Um exercicio com todas as
 * series marcadas continuava ocupando a mesma altura de um que ainda nem comecou, e numa
 * sessao de sete exercicios isso vira muito polegar para achar a proxima carga.
 *
 * Aqui fica so a REGRA — quando esta concluido e o que resumir. A tela decide como mostrar.
 */

/** Todas as series marcadas? Exercicio sem serie nenhuma nunca conta como concluido. */
export function exercicioConcluido(done, exerciseId, totalSeries) {
  const n = Number(totalSeries);
  if (!done || !exerciseId || !Number.isFinite(n) || n <= 0) return false;
  for (let i = 0; i < n; i += 1) {
    if (!done[exerciseId + i]) return false;
  }
  return true;
}

/**
 * Le um numero digitado pela pessoa.
 *
 * O campo e de texto e aceita virgula: quem escreve "62,5" quer 62,5 kg, e `Number("62,5")`
 * devolve NaN. O mesmo cuidado do campo de altura.
 */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return null;
  const limpo = String(valor).trim().replace(",", ".");
  const n = Number(limpo);
  return Number.isFinite(n) ? n : null;
}

/**
 * A carga que resume o exercicio e a MAIOR das series, nao a ultima.
 *
 * Numa progressao normal a pessoa sobe a carga ao longo das series, e a ultima costuma cair
 * quando a fadiga chega. Mostrar a ultima daria a impressao de ter feito menos do que fez;
 * a maior e o numero que ela reconhece como "o que levantei hoje".
 */
export function resumoDoExercicio(setInputs, exerciseId, totalSeries, cargaPadrao) {
  const n = Math.max(0, Number(totalSeries) || 0);
  let maior = null;
  for (let i = 0; i < n; i += 1) {
    const registro = (setInputs || {})[`${exerciseId}-${i}`];
    const carga = numero(registro?.weight ?? cargaPadrao);
    if (carga !== null && carga > 0 && (maior === null || carga > maior)) maior = carga;
  }
  return { series: n, carga: maior };
}

/** "3 series · 65 kg", ou so "3 series" quando ninguem registrou carga (peso do corpo). */
export function textoDoResumo(resumo) {
  const { series, carga } = resumo || {};
  if (!series) return "";
  const plural = series === 1 ? "série" : "séries";
  if (carga === null || carga === undefined) return `${series} ${plural}`;
  const carregado = Number.isInteger(carga) ? String(carga) : String(carga).replace(".", ",");
  return `${series} ${plural} · ${carregado} kg`;
}
