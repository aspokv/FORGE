/**
 * Quem aparece na tela de evolucao: uma foto ou duas.
 *
 * A tela mostrava duas molduras assim que existiam dois REGISTROS do mesmo angulo. So que
 * dois registros nao sao duas avaliacoes: o fluxo antigo, de quatro angulos por envio,
 * gravava um documento por angulo, e dois envios no mesmo dia tambem viram dois
 * documentos. O resultado era a tela oferecendo "antes e agora" com a MESMA data nos dois
 * lados — uma comparacao que nao existe.
 *
 * A regra aqui e por DIA de calendario, e nao por documento: so ha o que comparar quando a
 * segunda foto do mesmo angulo foi tirada em outra data. Enquanto isso nao acontece, a
 * tela mostra uma foto so, e diz que e a primeira.
 */

/** Dia local no formato AAAA-MM-DD. Local de proposito: o dia e o de quem tirou a foto. */
export function diaLocal(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/**
 * Decide o par a partir das avaliacoes de UM angulo, da mais antiga para a mais nova.
 *
 * Devolve `{ primeira, atual, unica, comparando }`:
 *  - `comparando` falso  -> `unica` e a leitura a mostrar, sozinha;
 *  - `comparando` certo  -> `primeira` e o "Antes" e `atual` e o "Agora".
 *
 * `atual` e a mais recente de um dia diferente do da primeira — e nao simplesmente a
 * ultima da lista. Sem data valida nos dois lados nao ha comparacao: preferimos uma foto
 * so a um "antes e agora" que pode estar errado.
 */
export function parDeAvaliacoes(doAngulo) {
  const lista = doAngulo || [];
  if (!lista.length) {
    return { primeira: null, atual: null, unica: null, comparando: false };
  }

  const primeira = lista[0];
  const diaBase = diaLocal(primeira.created_at);

  let atual = null;
  for (let i = lista.length - 1; i > 0; i -= 1) {
    const dia = diaLocal(lista[i].created_at);
    if (diaBase && dia && dia !== diaBase) {
      atual = lista[i];
      break;
    }
  }

  return {
    primeira,
    atual,
    // Sem par, mostramos a leitura mais recente — e nao a mais antiga. Varios envios no
    // mesmo dia ainda sao a primeira avaliacao, mas a analise que vale e a ultima.
    unica: atual ? null : lista[lista.length - 1],
    comparando: Boolean(atual),
  };
}
