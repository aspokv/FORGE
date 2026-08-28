import fs from "fs";
import path from "path";

/**
 * Responsividade da aquisicao, verificada na folha de estilo.
 *
 * Nao ha biblioteca de renderizacao neste projeto, entao nao da para medir o layout de
 * verdade. O que da para verificar — e o que costuma quebrar em celular — sao as regras
 * em si: grade de tres colunas sem queda para uma, alvo de toque pequeno demais, largura
 * fixa maior que a tela. Sao exatamente os erros que passam despercebidos no desktop.
 */

const CSS = fs.readFileSync(path.join(__dirname, "acquisition.css"), "utf8");

/** Extrai regras como {seletor, corpo}, incluindo as de dentro de media queries. */
function regras(css) {
  const semComentario = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const achadas = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(semComentario)) !== null) {
    const seletor = m[1].trim();
    if (seletor.startsWith("@")) continue; // abertura de media query, sem corpo proprio
    achadas.push({ seletor, corpo: m[2] });
  }
  return achadas;
}

/**
 * Corpo das media queries de uma largura, concatenado.
 *
 * Concatena porque a folha declara mais de um bloco para a mesma largura, um por secao —
 * o que e CSS valido e mantem cada regra perto do que ela ajusta. Ler so o primeiro faria
 * o teste reprovar por causa da organizacao do arquivo, e nao de um defeito.
 */
function blocoDaMedia(css, largura) {
  const alvo = `@media (max-width: ${largura}px)`;
  let corpo = "";
  let de = 0;
  for (;;) {
    const i = css.indexOf(alvo, de);
    if (i < 0) return corpo;
    const inicio = css.indexOf("{", i);
    let nivel = 0;
    for (let j = inicio; j < css.length; j += 1) {
      if (css[j] === "{") nivel += 1;
      if (css[j] === "}") {
        nivel -= 1;
        if (nivel === 0) {
          corpo += css.slice(inicio + 1, j);
          de = j;
          break;
        }
      }
    }
    if (de <= i) return corpo;
  }
}

const TODAS = regras(CSS);
const MOBILE_560 = blocoDaMedia(CSS, 560);
const MOBILE_900 = blocoDaMedia(CSS, 900);

describe("pontos de quebra", () => {
  test("existem regras para tablet e para celular", () => {
    expect(MOBILE_900.length).toBeGreaterThan(0);
    expect(MOBILE_560.length).toBeGreaterThan(0);
  });
});

describe("grades de varias colunas caem para uma no celular", () => {
  test.each([
    ["landing-audience", MOBILE_900],
    ["landing-benefits", MOBILE_900],
    ["previa-numeros", MOBILE_560],
  ])("%s colapsa", (classe, bloco) => {
    const desktop = TODAS.find((r) => r.seletor.includes(`.${classe}`) &&
      r.corpo.includes("grid-template-columns"));
    expect(desktop).toBeDefined();
    expect(desktop.corpo).toMatch(/repeat\(\s*3/);
    expect(bloco).toMatch(new RegExp(`\\.${classe}[^{]*\\{[^}]*(1fr|flex)`));
  });

  test("a grade de planos herda o colapso que ja existia em App.css", () => {
    // .plan-grid e definida em App.css e ja tem media query propria; aqui so garantimos
    // que a folha da aquisicao nao a redefine com tres colunas fixas.
    const redefinida = TODAS.filter((r) => r.seletor.includes(".plan-grid"));
    expect(redefinida).toHaveLength(0);
  });
});

describe("alvos de toque", () => {
  const MINIMO = 42;

  test.each([".btn", ".pa-opcao", ".pa-regiao", ".signup-card input"])(
    "%s tem altura suficiente para o dedo",
    (seletor) => {
      const regra = TODAS.find((r) => r.seletor.split(",").some(
        (s) => s.trim() === seletor || s.trim().startsWith(`${seletor}:not`)));
      expect(regra).toBeDefined();
      const alt = regra.corpo.match(/min-height:\s*(\d+)px/);
      expect(alt).not.toBeNull();
      expect(Number(alt[1])).toBeGreaterThanOrEqual(MINIMO);
    }
  );

  test("o seletor de dias e quadrado e grande o bastante", () => {
    const regra = TODAS.find((r) => r.seletor === ".pa-dia");
    const largura = Number(regra.corpo.match(/width:\s*(\d+)px/)[1]);
    const altura = Number(regra.corpo.match(/height:\s*(\d+)px/)[1]);
    expect(largura).toBe(altura);
    expect(altura).toBeGreaterThanOrEqual(MINIMO);
  });
});

describe("nada força rolagem horizontal", () => {
  test("nenhuma largura fixa maior que a tela de celular", () => {
    const grandes = [];
    TODAS.forEach((r) => {
      const m = r.corpo.match(/(?<!min-|max-)\bwidth:\s*(\d+)px/g) || [];
      m.forEach((decl) => {
        const px = Number(decl.match(/(\d+)px/)[1]);
        if (px > 320) grandes.push(`${r.seletor} -> ${decl}`);
      });
    });
    expect(grandes).toEqual([]);
  });

  test("os cartoes usam max-width, e nao largura fixa", () => {
    const cartao = TODAS.find((r) => r.seletor === ".signup-card");
    expect(cartao.corpo).toMatch(/max-width:/);
    expect(cartao.corpo).toMatch(/width:\s*100%/);
  });

  test("conteudo longo pode quebrar em vez de esticar a caixa", () => {
    const numeros = TODAS.find((r) => r.seletor === ".previa-numeros b");
    expect(numeros.corpo).toMatch(/overflow-wrap:\s*anywhere/);
  });

  test("grades que se adaptam usam minmax com minimo pequeno", () => {
    const protocolo = TODAS.find((r) => r.seletor === ".previa-protocolo");
    const minimo = Number(protocolo.corpo.match(/minmax\((\d+)px/)[1]);
    expect(minimo).toBeLessThanOrEqual(160);
  });
});

describe("o bloqueio da previa e visual, nao apenas semantico", () => {
  test("o conteudo bloqueado e borrado e nao selecionavel", () => {
    const borrado = TODAS.find((r) => r.seletor === ".previa-borrado");
    expect(borrado.corpo).toMatch(/filter:\s*blur/);
    expect(borrado.corpo).toMatch(/user-select:\s*none/);
  });

  test("a opcao bloqueada nao parece clicavel", () => {
    const locked = TODAS.find((r) => r.seletor === ".pa-opcao.locked");
    expect(locked.corpo).toMatch(/cursor:\s*not-allowed/);
    expect(locked.corpo).toMatch(/opacity/);
  });
});
