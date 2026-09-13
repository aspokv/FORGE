/**
 * Os numeros que o Inicio mostra sobre a semana e sobre a prontidao.
 *
 * Tudo aqui sai de dado que a tela JA tem em maos: `recent_sets`, que chega no bootstrap
 * com carga, repeticoes e data, e o nivel de recuperacao que o motor calculou. Nenhuma
 * chamada nova, nenhuma conta inventada.
 *
 * A separacao importa por um motivo: o nivel de prontidao NAO e recalculado aqui. O motor
 * usa a media dos tres ultimos check-ins (`_get_recent_recovery`), e a tela so tem o de
 * hoje. Recalcular com um registro so daria um rotulo diferente do que o motor de fato
 * aplicou no treino — a tela diria "normal" enquanto o treino veio aliviado. Entao o nivel
 * vem pronto do backend e aqui so vira texto.
 */

const DIA = 86400000;

/** "2026-09-13" no fuso do aparelho — a mesma chave que a faixa da semana ja usa. */
const chaveDoDia = (data) =>
  data instanceof Date && !Number.isNaN(data.getTime())
    ? new Intl.DateTimeFormat("sv-SE").format(data)
    : "";

/**
 * Le um numero que pode vir como texto com virgula.
 *
 * A carga e digitada pela pessoa num campo de texto: "62,5" precisa virar 62.5, e
 * `Number("62,5")` devolve NaN. Mesmo cuidado de `exercicioConcluido.js`.
 */
function numero(valor) {
  if (valor === null || valor === undefined || valor === "") return 0;
  const n = Number(String(valor).trim().replace(",", "."));
  return Number.isFinite(n) ? n : 0;
}

/** As datas distintas em que existe serie registrada. */
function diasTreinados(recentSets) {
  const dias = new Set();
  for (const linha of recentSets || []) {
    const chave = chaveDoDia(new Date(linha?.created_at));
    if (chave) dias.add(chave);
  }
  return dias;
}

/**
 * Dias seguidos de treino.
 *
 * A contagem comeca em HOJE se hoje ja tem treino, senao em ONTEM. Sem isso a sequencia de
 * quem treina de manha zeraria toda madrugada e voltaria ao abrir o aplicativo — o numero
 * pareceria quebrado justamente para quem esta sendo constante. Quem nao treina ha dois
 * dias tem sequencia zero, que e a verdade.
 */
export function sequenciaDeDias(recentSets, hoje = new Date()) {
  const dias = diasTreinados(recentSets);
  if (!dias.size) return 0;
  const base = hoje instanceof Date && !Number.isNaN(hoje.getTime()) ? hoje : new Date();
  let cursor = new Date(base.getTime());
  if (!dias.has(chaveDoDia(cursor))) {
    cursor = new Date(base.getTime() - DIA);
    if (!dias.has(chaveDoDia(cursor))) return 0;
  }
  let total = 0;
  while (dias.has(chaveDoDia(cursor))) {
    total += 1;
    cursor = new Date(cursor.getTime() - DIA);
  }
  return total;
}

/**
 * Series e carga levantada desde a segunda-feira da semana corrente.
 *
 * Carga da serie = peso x repeticoes. Serie de peso do corpo entra como serie e nao soma
 * quilo nenhum, que e o comportamento honesto: ela aconteceu, mas ninguem sabe quanto pesa
 * a pessoa naquele movimento.
 */
export function volumeDaSemana(recentSets, segunda) {
  const inicio = segunda instanceof Date && !Number.isNaN(segunda.getTime()) ? chaveDoDia(segunda) : "";
  let series = 0;
  let kg = 0;
  for (const linha of recentSets || []) {
    const chave = chaveDoDia(new Date(linha?.created_at));
    if (!chave || (inicio && chave < inicio)) continue;
    series += 1;
    kg += numero(linha?.weight) * numero(linha?.reps);
  }
  return { series, kg: Math.round(kg) };
}

/** "8,4 t" acima de mil quilos, "840 kg" abaixo. Tonelada e o numero que impressiona. */
export function textoDaCarga(kg) {
  const n = Number(kg) || 0;
  if (n <= 0) return "—";
  if (n < 1000) return `${Math.round(n).toLocaleString("pt-BR")} kg`;
  return `${(n / 1000).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} t`;
}

/**
 * O nivel do motor virado em texto de gente.
 *
 * `efeito` e o ponto: em LOW e VERY_LOW o motor ja cortou serie e subiu o RIR
 * (`_apply_recovery_adjustment`). Dizer isso transforma um rotulo numa explicacao — a
 * pessoa entende por que o treino de hoje veio menor em vez de achar que faltou algo.
 */
export function textoDeProntidao(nivel) {
  const chave = String(nivel || "").toUpperCase();
  if (chave === "HIGH") return { rotulo: "Alta", tom: "alta", efeito: "Volume liberado para hoje." };
  if (chave === "LOW") return { rotulo: "Baixa", tom: "baixa", efeito: "O motor aliviou séries e subiu o RIR." };
  if (chave === "VERY_LOW") return { rotulo: "Muito baixa", tom: "baixa", efeito: "O motor reduziu bem o volume de hoje." };
  return { rotulo: "Normal", tom: "normal", efeito: "Volume do plano mantido." };
}
