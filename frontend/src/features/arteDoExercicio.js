/**
 * Quando a arte do exercício aparece em faixa, e quando volta a ser miniatura.
 *
 * Por que isto é uma decisão, e não um detalhe de estilo
 * ------------------------------------------------------
 * As 134 fotos têm 512×512 e eram desenhadas a 64px na sessão: foto escura, sobre fundo
 * escuro, reduzida oito vezes. Não dava para ver a execução — que é a única coisa para
 * que a foto serve no meio de um treino. O Nicolas abriu a sessão e disse que não tinha
 * visto a arte nova; ela estava lá, do tamanho de um selo.
 *
 * Em faixa ela mede 262px de altura. Mantida o treino inteiro, empurraria a tabela de
 * séries para baixo da dobra em cada um dos seis exercícios — e a tabela é o que se toca
 * DURANTE a série, repetidas vezes, com o cronômetro correndo.
 *
 * As duas coisas não competem porque não são usadas ao mesmo tempo:
 *
 *   antes da primeira série  →  olha-se a EXECUÇÃO. A faixa.
 *   depois da primeira série →  olha-se a CARGA. A tabela, e a foto volta a ser miniatura
 *                               ao lado do nome, que é o bastante para confirmar o aparelho.
 *
 * Esta função mora fora do `App.js` por um motivo prático: lá dentro ela seria uma
 * expressão no meio de um componente de 187 linhas que nenhum teste monta, e sumiria numa
 * refatoração sem ninguém perceber. Aqui ela tem nome e tem teste.
 */

/**
 * @param {Object} done      mapa `exercise_id + índice da série` → verdadeiro quando registrada
 * @param {string} exerciseId
 * @param {number} sets      quantas séries o exercício tem
 * @returns {boolean} verdadeiro enquanto NENHUMA série deste exercício foi registrada
 */
export function arteEmFaixa(done, exerciseId, sets) {
  const total = Number(sets) || 0;
  // Sem id não há como consultar o mapa, e devolver `true` encheria a tela de faixas de um
  // exercício que não existe. Sem séries também não há o que começar.
  if (!exerciseId || total <= 0) return false;
  const registros = done || {};
  for (let n = 0; n < total; n += 1) {
    // Percorre TODAS as séries, e não só a primeira: quem reabre um exercício concluído
    // para revisar não pode ver a faixa voltar como se ele nunca tivesse sido feito.
    if (registros[exerciseId + n]) return false;
  }
  return true;
}
