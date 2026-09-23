/**
 * A geometria do Forge Food Card, em coordenadas lógicas de 1080 x 1920.
 *
 * Por que UM arquivo manda em tudo
 * --------------------------------
 * A peça existe em dois lugares: a prévia, que é DOM e CSS, e a exportação, que é canvas.
 * Se cada um tivesse suas medidas, eles divergiriam na primeira mudança de layout — e a
 * divergência apareceria só no PNG que o atleta já publicou.
 *
 * Então a prévia é desenhada em 1080 x 1920 DE VERDADE e encolhida por
 * `transform: scale()`. Não é um layout parecido em escala menor: é o mesmo layout, com
 * os mesmos números, visto de longe. A exportação lê estas mesmas constantes.
 *
 * Tudo o que posiciona conteúdo do atleta (cards e âncoras) vive NORMALIZADO, de 0 a 1,
 * e só vira pixel na hora de desenhar. É o que faz a mesma composição valer no celular,
 * no desktop e no PNG final.
 */

export const LARGURA = 1080;
export const ALTURA = 1920;
export const PROPORCAO = LARGURA / ALTURA;

/** Cores. Saem do tema do FORGE, e não de uma segunda paleta criada para esta peça. */
export const CORES = {
  vidro: "rgba(12, 12, 13, 0.72)",
  vidroBorda: "rgba(255, 255, 255, 0.16)",
  texto: "#ffffff",
  textoFraco: "rgba(255, 255, 255, 0.66)",
  textoMuitoFraco: "rgba(255, 255, 255, 0.42)",
  linha: "#ffffff",
  divisor: "rgba(255, 255, 255, 0.14)",
};

/**
 * Tipografia, em pixels lógicos.
 *
 * A pilha de fontes é a mesma do aplicativo. Ela importa para a exportação: o canvas
 * desenha com a fonte que o documento já carregou, então uma família diferente aqui
 * produziria um PNG com tipografia que a prévia não mostrou.
 */
export const FONTE = '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif';

export const TIPO = {
  marca: { tamanho: 54, peso: 800, espaco: 2 },
  assinatura: { tamanho: 21, peso: 500, espaco: 7 },
  nomeDoAlimento: { tamanho: 30, peso: 700, espaco: 1.2 },
  quantidade: { tamanho: 46, peso: 700, espaco: 0 },
  descricao: { tamanho: 21, peso: 400, espaco: 0, entrelinha: 29 },
  rotuloDoMacro: { tamanho: 19, peso: 600, espaco: 2.2 },
  valorDoMacro: { tamanho: 34, peso: 700, espaco: 0 },
  porcao: { tamanho: 18, peso: 400, espaco: 0 },
  rotuloDoResumo: { tamanho: 18, peso: 600, espaco: 2 },
  valorDoResumo: { tamanho: 32, peso: 700, espaco: 0 },
};

/** A marca. Fixa no canto superior esquerdo, e o atleta não move nem remove na V1. */
export const MARCA = {
  x: 60,
  y: 72,
  assinatura: ["DISCIPLINA", "GERA", "RESULTADOS"],
  assinaturaY: 148,
  entrelinhaDaAssinatura: 30,
  // A altura total que o logo mais a assinatura ocupam. É o que o posicionamento
  // automático usa para não nascer um card em cima da marca.
  altura: 250,
};

/** O card de alimento. */
export const CARTAO = {
  largura: 392,
  raio: 26,
  padding: 26,
  // O ícone fica à esquerda do nome, num círculo de traço fino.
  icone: { tamanho: 74, raio: 37, traco: 2 },
  espacoDepoisDoIcone: 20,
  // A linha que separa o bloco do alimento do bloco do macro.
  divisorY: 14,
  alturaDoBlocoDoMacro: 104,
};

/** O resumo inferior. */
export const RESUMO = {
  margem: 44,
  alturaDoBloco: 128,
  distanciaDaBase: 60,
  raio: 26,
  icone: 40,
};

/** O conector: linha fina do card até o ponto na foto. */
export const CONECTOR = {
  traco: 2.5,
  raioDoPonto: 9,
  raioDoHalo: 16,
};

/**
 * Áreas em que um card NÃO pode nascer, normalizadas.
 *
 * O topo é da marca e a base é do resumo. Um card nascendo ali cobriria a identidade ou
 * os totais, que são as duas coisas que a peça sempre mostra.
 */
export const ZONAS_PROIBIDAS = {
  topo: MARCA.altura / ALTURA,
  base: (RESUMO.alturaDoBloco + RESUMO.distanciaDaBase + 24) / ALTURA,
};

/** De normalizado (0 a 1) para pixel lógico. */
export function paraPixel(x, y) {
  return { x: x * LARGURA, y: y * ALTURA };
}

/** De pixel lógico para normalizado, preso dentro do quadro. */
export function paraNormalizado(x, y) {
  return { x: prender(x / LARGURA), y: prender(y / ALTURA) };
}

export function prender(valor, minimo = 0, maximo = 1) {
  return Math.min(maximo, Math.max(minimo, valor));
}

/**
 * A altura que um card ocupa, que depende de ter descrição ou não.
 *
 * Calculada, e não medida no DOM: a exportação em canvas não tem DOM para medir, e as
 * duas precisam chegar ao mesmo número.
 */
export function alturaDoCartao(item) {
  const topo = CARTAO.padding
    + TIPO.nomeDoAlimento.tamanho + 12
    + TIPO.quantidade.tamanho + 14;
  const descricao = item?.descriptionKey
    ? TIPO.descricao.entrelinha * 2 + 14
    : 0;
  return topo + descricao + CARTAO.divisorY + CARTAO.alturaDoBlocoDoMacro + CARTAO.padding;
}

/**
 * O canto do card em pixels, já garantindo que ele não sai do quadro.
 *
 * Um card com `cardX` alto ficaria metade fora da peça; prender aqui é mais barato do que
 * impedir o arrasto de chegar lá, e cobre também posição vinda do banco.
 */
export function caixaDoCartao(item) {
  const altura = alturaDoCartao(item);
  const x = prender(item.cardX * LARGURA, 0, LARGURA - CARTAO.largura);
  const y = prender(item.cardY * ALTURA, 0, ALTURA - altura);
  return { x, y, largura: CARTAO.largura, altura };
}

/**
 * De onde a linha sai do card: o ponto da borda mais próximo do âncora.
 *
 * Sair sempre do mesmo canto faria a linha atravessar o próprio card quando o âncora
 * ficasse do outro lado.
 */
export function saidaDoConector(caixa, ancora) {
  const centroX = caixa.x + caixa.largura / 2;
  const centroY = caixa.y + caixa.altura / 2;
  const dx = ancora.x - centroX;
  const dy = ancora.y - centroY;
  // Sai pela lateral quando o âncora está mais para os lados; senão, por cima ou baixo.
  if (Math.abs(dx) * caixa.altura > Math.abs(dy) * caixa.largura) {
    return { x: dx > 0 ? caixa.x + caixa.largura : caixa.x, y: centroY };
  }
  return { x: centroX, y: dy > 0 ? caixa.y + caixa.altura : caixa.y };
}

/**
 * Quanto a peça precisa encolher para caber no espaço disponível.
 *
 * Mede as DUAS dimensões, e não só a largura. A peça é 9:16, e a versão que media só a
 * largura fazia ela reivindicar 733px de altura num celular de 412px — as abas e o painel
 * de controles iam para fora da tela. Em navegador de celular, com barra de endereço e
 * barra de navegação, sobram por volta de 680px, e o painel inteiro ficava invisível sem
 * nenhum indício de que havia algo abaixo. Foi assim que o botão de escolher a foto da
 * galeria desapareceu para quem estava usando: ele existia, só nunca esteve na tela.
 *
 * Devolver a menor das duas razões é o que garante que a peça CABE inteira, em vez de
 * caber na largura e transbordar na altura.
 */
export function escalaQueCabe(largura, altura) {
  const l = Number(largura) > 0 ? Number(largura) : LARGURA;
  const a = Number(altura) > 0 ? Number(altura) : ALTURA;
  return Math.min(l / LARGURA, a / ALTURA);
}
