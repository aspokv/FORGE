/**
 * Interpreta a altura que a pessoa digitou.
 *
 * O campo pede centimetros e a pessoa escreve como fala: "1,80". Guardar isso como
 * 1,80 CENTIMETRO nao gera erro nenhum — gera um plano inteiro errado. Aconteceu em
 * producao: uma atleta de 65 kg com a altura em metros recebeu uma meta de 427 kcal por
 * dia, com carboidrato zerado, porque a TMB calculada deu 348 kcal.
 *
 * Um seletor de unidade ao lado do campo resolveria, mas ao custo de mais uma decisao e
 * mais uma forma de errar — quem digita "1,80" e esquece de trocar para metros erra
 * igual. Aqui o campo entende sozinho e DIZ o que entendeu: ninguem tem 1,80 cm nem
 * 180 metros, entao a leitura e inequivoca e a confirmacao dispensa o seletor.
 *
 * Espelha `normalizar_altura_cm` do backend de proposito. A tela confirma na hora; o
 * servidor nao confia na tela.
 */

/** Altura minima e maxima que uma pessoa tem, depois de interpretada. */
export const ALTURA_MIN_CM = 90;
export const ALTURA_MAX_CM = 250;

/**
 * Texto digitado -> `{ cm, interpretado, forade }`.
 *
 *  `cm`           centimetros, ou null quando nao da para ler
 *  `interpretado` true quando veio em metros e foi convertido
 *  `foraDeFaixa`  true quando o numero e legivel mas ninguem tem essa altura
 */
export function lerAltura(texto) {
  if (texto === null || texto === undefined || String(texto).trim() === "") {
    return { cm: null, interpretado: false, foraDeFaixa: false };
  }
  // Virgula e o separador decimal de quem escreve em portugues.
  const bruto = Number(String(texto).trim().replace(",", "."));
  if (!Number.isFinite(bruto) || bruto <= 0) {
    return { cm: null, interpretado: false, foraDeFaixa: false };
  }
  const interpretado = bruto < 3;
  const cm = interpretado ? Math.round(bruto * 100) : Math.round(bruto);
  return {
    cm,
    interpretado,
    foraDeFaixa: cm < ALTURA_MIN_CM || cm > ALTURA_MAX_CM,
  };
}

/** "1,80 m" — como a pessoa escreveu, para ecoar de volta. */
export function emMetros(cm) {
  if (!Number.isFinite(cm)) return "";
  return `${(cm / 100).toFixed(2).replace(".", ",")} m`;
}
