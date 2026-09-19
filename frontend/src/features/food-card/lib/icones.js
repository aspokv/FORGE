/**
 * Os ícones da peça: categorias de alimento e macros.
 *
 * Todos em traço (outline), monocromáticos, num quadro de 24 x 24, com a mesma espessura
 * e os mesmos cantos. A consistência é o que faz quatro cards diferentes parecerem parte
 * da mesma fotografia em vez de quatro widgets colados por cima dela.
 *
 * São caminhos SVG e não uma fonte de ícones: a exportação desenha em canvas com
 * `Path2D`, que aceita o mesmo `d` que o SVG usa. Um pacote de ícones exigiria rasterizar
 * antes, e aí a prévia e o PNG poderiam divergir.
 *
 * Todo caminho é desenhado com `stroke`, nunca `fill`. Quem desenha define espessura e
 * cor, o que permite o mesmo ícone servir ao círculo do card e ao resumo inferior.
 */

/** Quadro de referência de todo caminho. */
export const QUADRO = 24;

/** Os caminhos de alimento, pela mesma chave que o backend deriva. */
export const ICONES_DE_ALIMENTO = {
  // Cabeça de boi. A primeira versão tinha chifres curtos colados na cabeça e, vista a
  // 40 px no PNG exportado, lia como um ursinho: os chifres viravam orelhas. Agora eles
  // saem para FORA e para CIMA, que é o que separa as duas silhuetas nesse tamanho.
  beef: [
    "M6 9.5c0-2 1.6-3.5 3.6-3.5h4.8c2 0 3.6 1.5 3.6 3.5v2c0 3.3-2.7 6-6 6s-6-2.7-6-6v-2z",
    "M6.2 8C4.6 7 3.2 5.2 2.8 3.2c2 .1 3.9.9 5.2 2.2",
    "M17.8 8c1.6-1 3-2.8 3.4-4.8-2 .1-3.9.9-5.2 2.2",
    "M9.8 11h.02", "M14.2 11h.02",
    "M9.8 14.2c.7.6 1.4.9 2.2.9s1.5-.3 2.2-.9",
  ],
  // Coxa de frango: carne acima, osso abaixo.
  chicken: [
    "M14.5 3.5c3 0 5.5 2.5 5.5 5.5 0 2.4-1.6 4.5-3.8 5.2l-5.6 5.6a3 3 0 1 1-4.2-4.2l5.6-5.6C12.7 7.8 12.1 6 13 4.6",
    "M7.5 16.5l-2 2", "M5 14l-1.5 1.5",
  ],
  // Peixe: corpo em amêndoa e cauda.
  fish: [
    "M3 12c3-4.5 6.5-6.5 10-6.5S19.5 8 21 12c-1.5 4-4.5 6.5-8 6.5S6 16.5 3 12z",
    "M21 12l2.2-3v6L21 12", "M16 10.5h.01",
  ],
  // Ovo: oval mais estreito em cima.
  egg: ["M12 3c3.3 0 6 4.3 6 8.6S15.3 20 12 20s-6-3.1-6-8.4S8.7 3 12 3z"],
  // Tigela de arroz com grãos.
  rice: [
    "M3.5 11h17c0 4.4-3.6 8-8 8h-1c-4.4 0-8-3.6-8-8z",
    "M9 7.5c0-1.1.9-2 2-2", "M13 7.5c0-1.1.9-2 2-2", "M11 4.5c0-1.1.9-2 2-2",
  ],
  // Tigela de aveia com colher.
  oats: [
    "M3.5 11h17c0 4.4-3.6 8-8 8h-1c-4.4 0-8-3.6-8-8z",
    "M8 8c1.5-1 2.5-2.5 2.5-4.5", "M12 8c1.5-1 2.5-2.5 2.5-4.5",
    "M16 8c1.5-1 2.5-2.5 2.5-4.5",
  ],
  // Pão: forma de fatia com corte em cima.
  bread: [
    "M4 10c0-3 3.6-5 8-5s8 2 8 5v6.5c0 1.4-1.1 2.5-2.5 2.5h-11C5.1 19 4 17.9 4 16.5V10z",
    "M8 8.5c1-1 2.5-1.5 4-1.5s3 .5 4 1.5",
  ],
  // Massa: tigela com fios.
  pasta: [
    "M3.5 12h17c0 3.9-3.1 7-7 7h-3c-3.9 0-7-3.1-7-7z",
    "M7 12c0-2.8 2.2-5 5-5s5 2.2 5 5", "M10 12c0-1.1.9-2 2-2s2 .9 2 2",
  ],
  // Batata: bolota irregular com dois olhos.
  potato: [
    "M6.5 8.5c1.5-3 5-4.5 8.5-3.5S20 9.5 19 13.5s-4.5 6-8 5.5-6.5-3-6.5-6c0-1.8.5-3.2 2-4.5z",
    "M10 11h.01", "M14 14h.01",
  ],
  // Batata doce: bolota alongada na diagonal.
  "sweet-potato": [
    "M4.5 15.5c-1.5-2.5 0-6 3.5-8.5s7.5-3 9.5-1 1 5.5-2 8.5-9.5 3.5-11 1z",
    "M9 12h.01", "M13 10h.01",
  ],
  // Moranga: gomos e cabinho.
  pumpkin: [
    "M12 6.5c4 0 7 2.8 7 6.3S16 19.5 12 19.5s-7-2.8-7-6.7S8 6.5 12 6.5z",
    "M12 6.5v13", "M8.5 7.4c-1 1.6-1.5 3.6-1.5 5.7s.5 4.1 1.5 5.6",
    "M15.5 7.4c1 1.6 1.5 3.6 1.5 5.7s-.5 4.1-1.5 5.6",
    "M12 6.5c0-2 1.2-3.5 3-3.5",
  ],
  // Fruta: maçã com folha.
  fruit: [
    "M12 7.5c-1-1-2.2-1.5-3.5-1.5C6 6 4 8.3 4 11.5c0 4 3 8 5.5 8 .9 0 1.7-.4 2.5-.4s1.6.4 2.5.4c2.5 0 5.5-4 5.5-8 0-3.2-2-5.5-4.5-5.5-1.3 0-2.5.5-3.5 1.5z",
    "M12 7.5V5", "M12 5c1.8 0 3-1.2 3-3-1.8 0-3 1.2-3 3z",
  ],
  // Folha: nervura central e borda.
  vegetables: [
    "M4 20c0-8 5-15 16-16 0 11-6 15-12 15-1.5 0-2.7-.3-4-1z",
    "M4 20c3-6 7-9 12-11",
  ],
  // Laticínio: copo com leite.
  dairy: [
    "M6.5 4h11l-1 15.2c-.1 1-.9 1.8-2 1.8h-5c-1.1 0-1.9-.8-2-1.8L6.5 4z",
    "M6.9 10h10.2",
  ],
  // Whey: coqueteleira com tampa.
  whey: [
    "M7 8h10l-.8 11.2c-.1 1-.9 1.8-2 1.8H9.8c-1.1 0-1.9-.8-2-1.8L7 8z",
    "M6.5 4.5h11v3.5h-11z", "M10 12h4",
  ],
  // Amendoim: duas bolas ligadas.
  nuts: [
    "M8.5 4.5c2.2 0 4 1.6 4 3.6 0 1.1.5 1.7 1.4 2.6 1.3 1.3 2.1 2.6 2.1 4.3 0 2.5-2.1 4.5-4.7 4.5S6.5 17.5 6.5 15c0-1.7.8-3 2.1-4.3.9-.9 1.4-1.5 1.4-2.6",
    "M9.5 8.5h.01", "M13 15h.01",
  ],
  // Genérico: prato com garfo. Nunca bloqueia a criação do card.
  "generic-food": [
    "M4.5 12a7.5 7.5 0 0 1 15 0", "M3 15h18", "M5.5 18h13",
    "M12 4.5V9",
  ],
};

/**
 * Os ícones de macro.
 *
 * São os da referência visual: braço para proteína, folha para carboidrato, gota para
 * gordura e raio para energia.
 */
export const ICONES_DE_MACRO = {
  // Braço flexionado, como na referência.
  //
  // Duas versões anteriores falharam por motivos diferentes, as duas vistas no PNG
  // exportado a 40 px: a primeira eram duas bolas ligadas e saía idêntica ao ícone de
  // amendoim; a segunda virava uma mancha arredondada sem silhueta de braço.
  //
  // O que resolve nesse tamanho é a QUEBRA do cotovelo: antebraço na vertical, braço na
  // horizontal e o volume do bíceps por cima da dobra. É a leitura que sobrevive quando
  // o detalhe some.
  protein: [
    "M3 10.5h7.5c.9 0 1.7.4 2.2 1.1l1.3 1.8",
    "M3 10.5v3.2c0 1 .8 1.8 1.8 1.8h5.4",
    "M14 12.5c0-2.5 1.4-4.5 3.2-4.5 1.6 0 2.8 1.4 2.8 3.2 0 1.3-.6 2.4-1.6 3.2l.6 3.1a1 1 0 0 1-1 1.2h-3.5a1 1 0 0 1-1-1.2l.5-2.6",
    "M10.5 11.6c1.6-.6 3-.2 4 1",
  ],
  carbs: [
    "M4 20c0-8 5-15 16-16 0 11-6 15-12 15-1.5 0-2.7-.3-4-1z",
    "M4 20c3-6 7-9 12-11",
  ],
  fat: [
    "M12 3.5c3.5 4 6.5 7.2 6.5 10.5A6.5 6.5 0 0 1 5.5 14c0-3.3 3-6.5 6.5-10.5z",
    "M9 14.5a3 3 0 0 0 3 3",
  ],
  calories: ["M13.5 2.5L5 13.5h6l-1.5 8L18 10.5h-6l1.5-8z"],
};

export function caminhosDoAlimento(chave) {
  return ICONES_DE_ALIMENTO[chave] || ICONES_DE_ALIMENTO["generic-food"];
}

export function caminhosDoMacro(chave) {
  return ICONES_DE_MACRO[chave] || ICONES_DE_MACRO.protein;
}
