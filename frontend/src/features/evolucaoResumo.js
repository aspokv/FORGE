/**
 * A resposta que a tela de Evolucao devia dar antes de qualquer controle.
 *
 * Quem abre essa tela tem UMA pergunta: "estou evoluindo?". Hoje a tela responde com um
 * seletor de 175 exercicios, tres botoes de periodo e um cursor de sessoes — trabalho antes
 * da resposta. Aqui fica o veredito, montado so com numero exato.
 *
 * O que NAO entra: media de carga por serie (`analytics.trend[].load`). Ela cai quando a
 * pessoa acrescenta acessorio leve, entao "media caiu" leria como piora onde houve mais
 * trabalho. Numero que engana e pior que numero ausente.
 */

/** Treinos registrados no calendario de adesao, que ja vem com 28 dias fechados. */
function contarTreinos(calendario) {
  return (calendario || []).filter((dia) => dia && dia.trained).length;
}

/**
 * Quantos exercicios estao mais pesados hoje do que na primeira vez registrada.
 *
 * `delta_weight` e calculado no backend como peso atual menos `start_weight`. Vem so para os
 * cinco maiores pesos, entao isto e "entre as suas cinco maiores cargas", nao o catalogo
 * inteiro — e o texto da tela precisa dizer isso sem prometer mais do que mede.
 */
function contarEvolucoes(marcas) {
  return (marcas || []).filter((m) => Number(m?.delta_weight) > 0).length;
}

/** A maior evolucao em quilos, com o exercicio que a produziu. */
function maiorSalto(marcas) {
  let melhor = null;
  for (const m of marcas || []) {
    const kg = Number(m?.delta_weight);
    if (!Number.isFinite(kg) || kg <= 0) continue;
    if (!melhor || kg > melhor.kg) melhor = { exercicio: String(m.exercise || ""), kg };
  }
  return melhor;
}

/**
 * Uma frase que resume o periodo.
 *
 * Sem elogio inventado: cada ramo descreve o que os numeros mostram. Constancia e carga sao
 * coisas diferentes e a frase separa as duas, porque treinar muito sem subir carga e um
 * diagnostico util, nao um fracasso a ser escondido.
 */
function veredito(treinos, evolucoes) {
  if (!treinos) return "Sem treinos registrados nas últimas 4 semanas.";
  if (evolucoes && treinos >= 8) return "Você está subindo carga com constância.";
  if (evolucoes) return "Você está subindo carga.";
  if (treinos >= 8) return "Constância firme. As cargas ainda não subiram.";
  return "Poucos treinos no período.";
}

/**
 * O bloco de abertura da Evolucao.
 *
 * Devolve sempre a mesma forma, inclusive sem dado nenhum, para a tela nao precisar tratar
 * ausencia em cinco lugares diferentes.
 */
export function resumoDaEvolucao(analytics) {
  const calendario = analytics?.adherence_calendar || [];
  const marcas = (analytics?.prs || []).filter((m) => Number(m?.weight) > 0);
  const treinos = contarTreinos(calendario);
  const evolucoes = contarEvolucoes(marcas);
  return {
    treinos,
    dias: calendario.length || 28,
    evolucoes,
    salto: maiorSalto(marcas),
    frase: veredito(treinos, evolucoes),
  };
}

/** "+82 kg" — o sinal importa, porque o numero sozinho nao diz que subiu. */
export function textoDoSalto(salto) {
  if (!salto || !(salto.kg > 0)) return null;
  const kg = Number.isInteger(salto.kg) ? String(salto.kg) : String(salto.kg).replace(".", ",");
  return `+${kg} kg`;
}

/**
 * Qual exercicio abrir no grafico.
 *
 * A ordem: o que a pessoa escolheu agora, o que ela favoritou, o do recorde mais RECENTE, e
 * so entao o primeiro da lista. O terceiro degrau e o que muda a tela na pratica: hoje ela
 * cai no primeiro exercicio em ordem alfabetica que tenha registro, o que faz alguem com
 * puxada de 137 kg abrir a tela vendo cadeira extensora de 30 kg.
 */
export function exercicioPadrao({ escolhido, favorito, milestones = [], opcoes = [] }) {
  const existe = (id) => opcoes.some((e) => e.id === id);
  if (escolhido && existe(escolhido)) return escolhido;
  if (favorito && existe(favorito)) return favorito;
  for (const marco of milestones) {
    const achado = opcoes.find((e) => e.name === marco?.title);
    if (achado) return achado.id;
  }
  return opcoes[0]?.id || "";
}

/**
 * As opcoes do seletor, com os exercicios da pessoa no topo.
 *
 * Um catalogo de 175 itens em ordem alfabetica trata por igual o que ela treina toda semana
 * e o que ela nunca fez. Os treinados sobem para um grupo proprio; o resto continua em ordem
 * alfabetica logo abaixo, entao nada some.
 */
export function opcoesDoSeletor(opcoes = [], milestones = [], marcas = []) {
  const treinados = new Set();
  for (const m of milestones) if (m?.title) treinados.add(m.title);
  for (const m of marcas) if (m?.exercise) treinados.add(m.exercise);
  const seus = opcoes.filter((e) => treinados.has(e.name));
  const demais = opcoes.filter((e) => !treinados.has(e.name));
  return { seus, demais };
}
