/**
 * Comparacao entre duas avaliacoes visuais.
 *
 * Nao existe rota que compare duas datas: a analise le UMA foto por vez. Entao o que muda
 * entre elas so pode sair do que as duas leituras registraram — e nada alem disso.
 *
 * A regra que governa este arquivo: nao afirmar evolucao que a evidencia nao sustenta. Um
 * musculo so "mudou" quando as duas leituras o classificaram com confianca suficiente e os
 * niveis sao diferentes. Confianca baixa de qualquer um dos lados invalida a comparacao
 * daquele grupo — a propria analise disse que nao enxergou direito, e duas incertezas nao
 * viram uma certeza.
 */

/** A escala que a analise usa, do menos ao mais desenvolvido. */
const ESCALA = ["muito fraco", "fraco", "proporcional", "forte", "muito forte"];

const nivel = (dado) => ESCALA.indexOf(String(dado?.development || "").toLowerCase());
const confiavel = (dado) => {
  const c = String(dado?.confidence || "").toLowerCase();
  return c === "alta" || c === "média" || c === "media";
};

/**
 * Compara duas avaliacoes e devolve o que da para afirmar.
 *
 * `confiavel: false` significa que nao ha base para falar de mudanca — e a tela deve dizer
 * isso, e nao mostrar blocos vazios que parecem defeito.
 */
export function compararAvaliacoes(antiga, nova) {
  if (!antiga || !nova || antiga.id === nova.id) {
    return { confiavel: false, motivo: "sem_par", melhoraram: [], pioraram: [], mantiveram: 0 };
  }

  const obsAntiga = antiga.observations || {};
  const obsNova = nova.observations || {};
  const melhoraram = [];
  const pioraram = [];
  let mantiveram = 0;
  let comparados = 0;

  Object.keys(obsNova).forEach((musculo) => {
    const a = obsAntiga[musculo];
    const b = obsNova[musculo];
    if (!a || !b) return;
    // Confianca baixa em qualquer um dos lados: fora da conta.
    if (!confiavel(a) || !confiavel(b)) return;
    const na = nivel(a);
    const nb = nivel(b);
    if (na < 0 || nb < 0) return;
    comparados += 1;
    if (nb > na) melhoraram.push(musculo);
    else if (nb < na) pioraram.push(musculo);
    else mantiveram += 1;
  });

  if (comparados === 0) {
    return { confiavel: false, motivo: "sem_grupos_comparaveis", melhoraram: [], pioraram: [], mantiveram: 0 };
  }

  return { confiavel: true, motivo: "", melhoraram, pioraram, mantiveram, comparados };
}

/** Intervalo entre duas datas, em linguagem de gente. */
export function intervaloEmPalavras(deIso, ateIso) {
  const de = new Date(deIso);
  const ate = new Date(ateIso);
  if (Number.isNaN(de.getTime()) || Number.isNaN(ate.getTime())) return "";
  const dias = Math.round((ate - de) / 86400000);
  if (dias <= 0) return "mesmo dia";
  if (dias === 1) return "1 dia de evolução";
  if (dias < 14) return `${dias} dias de evolução`;
  if (dias < 60) {
    const semanas = Math.round(dias / 7);
    return `${semanas} ${semanas === 1 ? "semana" : "semanas"} de evolução`;
  }
  const meses = Math.round(dias / 30);
  return `${meses} ${meses === 1 ? "mês" : "meses"} de evolução`;
}

/** Data curta, para o rotulo de cada avaliacao. */
export function dataCurta(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

/** Data por extenso, para o cabecalho do grupo. */
export function dataLonga(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
}
