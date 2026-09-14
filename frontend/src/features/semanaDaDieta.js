/**
 * A semana de alimentacao, do jeito que pode ser dita sem mentir.
 *
 * Duas armadilhas decidem o desenho deste modulo, e as duas produzem numero falso se
 * ignoradas.
 *
 * DIA SEM REGISTRO NAO E DIA DE JEJUM. Quem anotou tres dos sete dias nao comeu 8.000 kcal
 * a menos: esqueceu de anotar. Somar a meta dos sete e subtrair o que foi registrado
 * acusaria um deficit que nunca existiu, e um aplicativo que acusa a pessoa de algo que ela
 * nao fez perde a confianca na primeira semana. Por isso tudo aqui e MEDIA POR DIA
 * REGISTRADO, e a contagem de dias anda junto do numero, sempre visivel.
 *
 * COMER MENOS NAO E SEMPRE BOM. Em corte, ficar abaixo parece vitoria e custa musculo; em
 * ganho, e o fracasso direto. O mesmo desvio muda de sinal conforme o objetivo, entao a
 * frase precisa saber se a pessoa esta em ganho, corte ou manutencao — e, quando nao sabe,
 * descreve sem julgar em vez de chutar.
 */

const MARGEM = 0.05; // 5% para cada lado conta como "em cima da meta".

/** Media por dia REGISTRADO. Dia sem registro nao entra no divisor. */
function mediaPorDia(dias, campo) {
  if (!dias.length) return 0;
  const soma = dias.reduce((total, dia) => total + (Number(dia?.[campo]) || 0), 0);
  return soma / dias.length;
}

/** Normaliza o objetivo vindo do plano; qualquer coisa desconhecida vira null, nao "manter". */
export function objetivoDaDieta(bruto) {
  const chave = String(bruto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  if (/cut|corte|emagrec|perda|defici|seca/.test(chave)) return "corte";
  if (/bulk|ganho|massa|hipertrof|superavit/.test(chave)) return "ganho";
  if (/manut|recomp|mantem|maintain/.test(chave)) return "manutencao";
  return null;
}

/**
 * A frase da semana.
 *
 * A proteina vem primeiro porque e ela que decide hipertrofia: bater 2.871 kcal com 120 g de
 * proteina e pior que errar 200 kcal com 180 g. So quando a proteina esta no lugar a frase
 * passa a falar de caloria.
 */
function veredito({ diasProteinaOk, dias, desvioCalorico, objetivo }) {
  if (!dias) return "Nenhum dia registrado nos últimos 7 dias.";
  if (diasProteinaOk === dias && dias > 1) {
    if (Math.abs(desvioCalorico) <= MARGEM) return "Proteína e calorias no lugar.";
    if (desvioCalorico > MARGEM) {
      if (objetivo === "corte") return "Proteína em dia, mas as calorias passaram da meta.";
      if (objetivo === "ganho") return "Proteína em dia e calorias acima — é o que o ganho pede.";
      return "Proteína em dia, calorias acima da meta.";
    }
    if (objetivo === "ganho") return "Proteína em dia, mas faltou caloria para o ganho.";
    if (objetivo === "corte") return "Proteína em dia e calorias abaixo — o corte está andando.";
    return "Proteína em dia, calorias abaixo da meta.";
  }
  if (!diasProteinaOk) return "A proteína ficou abaixo da meta em todos os dias registrados.";
  return `Proteína no alvo em ${diasProteinaOk} de ${dias} ${dias === 1 ? "dia" : "dias"}.`;
}

/**
 * O bloco de alimentacao da Evolucao.
 *
 * Devolve sempre a mesma forma, inclusive sem dado nenhum, para a tela nao tratar ausencia
 * em cinco lugares diferentes.
 */
export function semanaDaDieta(dados) {
  const dias = (dados?.days || []).filter((dia) => dia && (dia.kcal || dia.protein_g));
  const alvos = dados?.targets || {};
  const metaKcal = Number(alvos.goal_calories) || 0;
  const metaProteina = Number(alvos.protein_g) || 0;
  const objetivo = objetivoDaDieta(dados?.goal);

  const kcalPorDia = Math.round(mediaPorDia(dias, "kcal"));
  const proteinaPorDia = Math.round(mediaPorDia(dias, "protein_g"));
  // "No alvo" e bater a meta ou passar: proteina acima do alvo nao e falha.
  const diasProteinaOk = metaProteina
    ? dias.filter((dia) => Number(dia.protein_g) >= metaProteina * (1 - MARGEM)).length
    : 0;
  const desvioCalorico = metaKcal ? (kcalPorDia - metaKcal) / metaKcal : 0;

  return {
    dias: dias.length,
    janela: Number(dados?.window_days) || 7,
    kcalPorDia,
    proteinaPorDia,
    metaKcal: Math.round(metaKcal),
    metaProteina: Math.round(metaProteina),
    diasProteinaOk,
    objetivo,
    frase: veredito({ diasProteinaOk, dias: dias.length, desvioCalorico, objetivo }),
  };
}

/** "1.780" — separador de milhar brasileiro, sem casa decimal. */
export function numero(valor) {
  return Math.round(Number(valor) || 0).toLocaleString("pt-BR");
}

/**
 * "6 de 7 dias registrados" — a legenda que impede o numero de mentir.
 *
 * Ela anda colada a media justamente para ninguem ler "2.740 kcal por dia" como se fossem
 * os sete dias da semana.
 */
export function textoDosDias(resumo) {
  if (!resumo?.dias) return "nenhum dia registrado";
  return `${resumo.dias} de ${resumo.janela} dias registrados`;
}

/**
 * O total da semana, macro a macro, com a fracao ja cumprida.
 *
 * A meta da semana e a meta diaria vezes os dias REGISTRADOS, nunca vezes os sete da janela.
 * Comparar o que foi comido em tres dias contra a meta de sete recriaria exatamente o
 * deficit falso que este modulo inteiro existe para evitar.
 *
 * `fracao` passa de 1 quando a pessoa come acima da meta, e isso e informacao, nao erro: a
 * barra e que decide parar em 100% para nao vazar da caixa.
 */
export function totaisDaSemana(dados) {
  const dias = (dados?.days || []).filter((dia) => dia && (dia.kcal || dia.protein_g));
  const alvos = dados?.targets || {};
  const metaDiaria = {
    kcal: Number(alvos.goal_calories) || 0,
    protein_g: Number(alvos.protein_g) || 0,
    carbs_g: Number(alvos.carbs_g) || 0,
    fat_g: Number(alvos.fat_g) || 0,
  };
  const rotulos = {
    kcal: { nome: "Calorias", unidade: "kcal" },
    protein_g: { nome: "Proteína", unidade: "g" },
    carbs_g: { nome: "Carboidrato", unidade: "g" },
    fat_g: { nome: "Gordura", unidade: "g" },
  };
  return Object.keys(rotulos).map((chave) => {
    const consumido = dias.reduce((soma, dia) => soma + (Number(dia[chave]) || 0), 0);
    const meta = metaDiaria[chave] * dias.length;
    return {
      chave,
      ...rotulos[chave],
      consumido: Math.round(consumido),
      meta: Math.round(meta),
      fracao: meta > 0 ? consumido / meta : 0,
      // O que falta para fechar a meta dos dias registrados; negativo vira "passou".
      diferenca: Math.round(consumido - meta),
    };
  });
}

/** A largura da barra: nunca passa de 100%, senao vaza da caixa. */
export function larguraDaBarra(fracao) {
  const n = Number(fracao) || 0;
  return `${Math.max(0, Math.min(1, n)) * 100}%`;
}

/** "faltam 320 g", "passou 180 kcal", ou "na meta" dentro da margem. */
export function textoDaDiferenca(linha) {
  if (!linha?.meta) return "";
  const desvio = linha.consumido / linha.meta - 1;
  if (Math.abs(desvio) <= MARGEM) return "na meta";
  const valor = Math.abs(linha.diferenca).toLocaleString("pt-BR");
  return linha.diferenca < 0 ? `faltam ${valor} ${linha.unidade}` : `passou ${valor} ${linha.unidade}`;
}
