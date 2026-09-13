/**
 * O treino de hoje, com o que a pessoa levantou da ultima vez em cada exercicio.
 *
 * A Evolucao respondia "como voce esta indo?" pedindo que a pessoa escolhesse um exercicio
 * entre 175. A pergunta que ela faz de verdade, antes de treinar, e outra: "quanto eu peguei
 * da ultima vez nisso aqui?". Essa resposta e por SESSAO, nao por exercicio avulso — se hoje
 * e peito dominante, o que interessa sao os exercicios de peito dominante.
 *
 * Aqui fica so a juncao. Quem mede e o backend (`/session-last-performance`), que devolve a
 * sessao mais recente de cada exercicio; quem desenha e a tela.
 */

/** O nome legivel do exercicio; sem catalogo, o id e melhor que um espaco em branco. */
function nomeDoExercicio(catalogo, id) {
  const achado = (catalogo || []).find((e) => e && e.id === id);
  return (achado && achado.name) || id || "";
}

/** Numero de exibicao: inteiro sem casa, quebrado com virgula. */
export function cargaEmTexto(kg) {
  const n = Number(kg);
  if (!Number.isFinite(n) || n <= 0) return null;
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

/** "12/09" — a data curta basta para situar; o ano polui a linha. */
export function dataCurta(iso) {
  const partes = String(iso || "").slice(0, 10).split("-");
  return partes.length === 3 ? `${partes[2]}/${partes[1]}` : "";
}

/**
 * Uma linha por exercicio prescrito hoje.
 *
 * Exercicio sem historico entra na lista assim mesmo, marcado como estreia. Omitir seria
 * pior: a pessoa veria uma lista menor que o treino e pensaria que faltou exercicio.
 */
export function linhasDaSessao({ exercicios = [], catalogo = [], desempenhos = {} } = {}) {
  return exercicios
    .filter((x) => x && x.exercise_id)
    .map((x) => {
      const anterior = desempenhos[x.exercise_id] || null;
      return {
        id: x.exercise_id,
        nome: nomeDoExercicio(catalogo, x.exercise_id),
        prescrito: { series: Number(x.sets) || 0, reps: String(x.reps || "") },
        carga: anterior ? cargaEmTexto(anterior.weight) : null,
        reps: anterior ? Number(anterior.reps) || 0 : 0,
        data: anterior ? dataCurta(anterior.date) : "",
        estreia: !anterior,
      };
    });
}

/**
 * Os ids que a tela precisa pedir ao backend.
 *
 * Sem repetidos: um exercicio pode aparecer duas vezes na mesma sessao (bi-set, ou uma
 * segunda passagem mais leve) e pedir o mesmo id duas vezes so gasta banda.
 */
export function idsDaSessao(exercicios = []) {
  const vistos = [];
  for (const x of exercicios) {
    if (x && x.exercise_id && !vistos.includes(x.exercise_id)) vistos.push(x.exercise_id);
  }
  return vistos;
}

/**
 * Quantos exercicios de hoje ja tem historico.
 *
 * Serve para a tela escolher entre "supere estes numeros" e "primeira vez neste treino", sem
 * prometer superacao a quem nao tem o que superar.
 */
export function quantosComHistorico(linhas = []) {
  return linhas.filter((l) => l && !l.estreia).length;
}
