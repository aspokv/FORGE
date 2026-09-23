import fs from "fs";
import path from "path";
import React, {act} from "react";
import {createRoot} from "react-dom/client";

import {
  ALTURA, CARTAO, LARGURA, MARCA, RESUMO, ZONAS_PROIBIDAS,
  alturaDoCartao, caixaDoCartao, paraNormalizado, paraPixel, prender, saidaDoConector,
} from "./lib/layout";
import {DESCRICOES, MACROS, ROTULO_DO_MACRO, descricaoDe, quantidadeDe, valorDoMacro} from "./lib/conteudo";
import {ICONES_DE_ALIMENTO, ICONES_DE_MACRO, QUADRO, TRACO, caminhosDoAlimento} from "./lib/icones";
import {nomeDoArquivo} from "./lib/exportar";
import FoodCardCanvas from "./components/FoodCardCanvas";
import MacroSummary from "./components/MacroSummary";
import FoodSelector from "./components/FoodSelector";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const BACKEND = path.join(__dirname, "..", "..", "..", "..", "backend");
const lerPython = arquivo => fs.readFileSync(path.join(BACKEND, arquivo), "utf8");

const ITEM = {
  foodId: "carne", name: "Carne moída", quantity: 180, unit: "g",
  calories: 350, protein: 38, carbs: 0, fat: 22,
  iconKey: "beef", descriptionKey: "protein_source", primaryMacro: "protein",
  cardX: 0.06, cardY: 0.16, anchorX: 0.44, anchorY: 0.38,
};
const RESUMO_DA_REFEICAO = {protein: 47, carbs: 43, fat: 32, calories: 648};

/* ─────────────────────────────────────────────────────────────────────────────────
 * O contrato com o backend
 *
 * O servidor grava a CHAVE da descrição (`protein_source`), não a frase. Isso permite
 * corrigir o texto sem reescrever os Food Cards já salvos — e exige que os dois lados
 * concordem sobre quais chaves existem. Se divergirem, o card sai sem descrição e
 * ninguém percebe até ver a peça publicada.
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("o texto da peça contra o backend", () => {
  test("toda chave de descrição do Python existe aqui", () => {
    const python = lerPython("food_card.py");
    const bloco = python.split("DESCRICOES: Dict[str, str] = {")[1].split("}")[0];
    const chaves = [...bloco.matchAll(/"([a-z_]+)":/g)].map(m => m[1]);

    expect(chaves.length).toBeGreaterThan(3);
    for (const chave of chaves) expect(DESCRICOES[chave]).toBeTruthy();
    expect(Object.keys(DESCRICOES).sort()).toEqual(chaves.sort());
  });

  test("as frases são idênticas dos dois lados", () => {
    const python = lerPython("food_card.py");
    for (const [chave, frase] of Object.entries(DESCRICOES)) {
      expect(python).toContain(`"${chave}": "${frase}"`);
    }
  });

  test("nenhuma frase promete efeito, cura ou resultado", () => {
    // A peça vai para o Instagram com o nome do FORGE. "Fonte de proteína" é fato de
    // composição; "acelera o metabolismo" é alegação, e não sai daqui.
    const proibido = /acelera|queima|emagrece|cura|previne|combate|detox|turbina|milagr/i;
    for (const frase of Object.values(DESCRICOES)) {
      expect(frase).not.toMatch(proibido);
    }
  });

  test("todo ícone que o Python deriva existe na biblioteca da tela", () => {
    const python = lerPython("food_card.py");
    const bloco = python.split("ICONES = (")[1].split(")")[0];
    const chaves = [...bloco.matchAll(/"([a-z-]+)"/g)].map(m => m[1]);
    expect(chaves.length).toBeGreaterThan(10);
    for (const chave of chaves) {
      expect(ICONES_DE_ALIMENTO[chave]).toBeTruthy();
    }
  });

  test("os três macros têm ícone e rótulo", () => {
    for (const macro of MACROS) {
      expect(ICONES_DE_MACRO[macro]).toBeTruthy();
      expect(ROTULO_DO_MACRO[macro]).toBeTruthy();
    }
    // O resumo mostra energia junto dos três macros.
    expect(ICONES_DE_MACRO.calories).toBeTruthy();
  });
});

/* ─────────────────────────────────────────────────────────────────────────────────
 * Geometria
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("a geometria da peça", () => {
  test("o quadro é 1080 x 1920", () => {
    expect(LARGURA).toBe(1080);
    expect(ALTURA).toBe(1920);
  });

  test("normalizado e pixel são a mesma coisa nos dois sentidos", () => {
    const pixel = paraPixel(0.25, 0.5);
    expect(pixel).toEqual({x: 270, y: 960});
    expect(paraNormalizado(270, 960)).toEqual({x: 0.25, y: 0.5});
  });

  test("posição fora do quadro é presa, e não descartada", () => {
    // Prender é mais barato do que impedir o arrasto de chegar lá, e cobre também
    // posição vinda do banco de uma versão anterior do layout.
    expect(prender(1.8)).toBe(1);
    expect(prender(-0.4)).toBe(0);
  });

  test("nenhum card cabe fora do quadro, nem com posição absurda", () => {
    const caixa = caixaDoCartao({...ITEM, cardX: 0.99, cardY: 0.99});
    expect(caixa.x + caixa.largura).toBeLessThanOrEqual(LARGURA);
    expect(caixa.y + caixa.altura).toBeLessThanOrEqual(ALTURA);
  });

  test("o card sem descrição é mais baixo que o card com descrição", () => {
    const com = alturaDoCartao(ITEM);
    const sem = alturaDoCartao({...ITEM, descriptionKey: null});
    expect(sem).toBeLessThan(com);
    // E os dois cabem na peça com folga para a marca e o resumo.
    expect(com).toBeLessThan(ALTURA * 0.4);
  });

  test("a linha sai da borda mais próxima do âncora, e não de um canto fixo", () => {
    const caixa = {x: 100, y: 400, largura: CARTAO.largura, altura: 400};
    const aDireita = saidaDoConector(caixa, {x: 900, y: 600});
    const abaixo = saidaDoConector(caixa, {x: 300, y: 1500});
    expect(aDireita.x).toBe(caixa.x + caixa.largura);
    expect(abaixo.y).toBe(caixa.y + caixa.altura);
    // Saindo sempre do mesmo canto, a linha atravessaria o próprio card.
    expect(aDireita).not.toEqual(abaixo);
  });

  test("as zonas proibidas cobrem a marca e o resumo", () => {
    expect(ZONAS_PROIBIDAS.topo * ALTURA).toBeGreaterThanOrEqual(MARCA.altura * 0.9);
    expect(ZONAS_PROIBIDAS.base * ALTURA)
      .toBeGreaterThanOrEqual(RESUMO.alturaDoBloco + RESUMO.distanciaDaBase);
  });
});

/* ─────────────────────────────────────────────────────────────────────────────────
 * Conteúdo
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("o conteúdo de cada card", () => {
  test("o valor mostrado é o do macro principal", () => {
    expect(valorDoMacro(ITEM)).toBe(38);
    expect(valorDoMacro({...ITEM, primaryMacro: "fat"})).toBe(22);
    expect(valorDoMacro({...ITEM, primaryMacro: "carbs"})).toBe(0);
  });

  test("a quantidade usa vírgula, como o resto do aplicativo", () => {
    expect(quantidadeDe({quantity: 180, unit: "g"})).toBe("180 g");
    expect(quantidadeDe({quantity: 37.5, unit: "g"})).toBe("37,5 g");
  });

  test("alimento sem descrição segura não recebe texto inventado", () => {
    expect(descricaoDe({descriptionKey: null})).toBe("");
    expect(descricaoDe({descriptionKey: "frase_que_nao_existe"})).toBe("");
  });

  test("todo ícone de alimento tem pelo menos um traço desenhável", () => {
    for (const [chave, caminhos] of Object.entries(ICONES_DE_ALIMENTO)) {
      expect(caminhos.length).toBeGreaterThan(0);
      for (const d of caminhos) expect(d).toMatch(/^M/);
    }
  });

  test("a espessura do traço é a do pacote aprovado, e uma só", () => {
    // 0,85 é o valor do pacote do Nicolas. Desenhar com a espessura antiga (1,6 a 2)
    // engrossaria o traço ao dobro do projetado e quebraria a família — o traço fino é
    // parte da identidade destes ícones, não um detalhe de implementação.
    expect(TRACO).toBe(0.85);
    expect(QUADRO).toBe(24);
  });

  test("todo caminho cabe dentro do quadro de 24", () => {
    // Um número acima de 24 num caminho significa desenho saindo pela borda: aparece
    // cortado no círculo do card e no resumo.
    const todos = [...Object.values(ICONES_DE_ALIMENTO), ...Object.values(ICONES_DE_MACRO)];
    for (const caminhos of todos) {
      for (const d of caminhos) {
        const numeros = (d.match(/-?\d+\.?\d*/g) || []).map(Number);
        const fora = numeros.filter(n => n < -1 || n > 25);
        expect(fora).toEqual([]);
      }
    }
  });

  test("ícone desconhecido cai no genérico em vez de sumir", () => {
    // Falta de ícone não pode impedir a criação do card.
    expect(caminhosDoAlimento("comida-marciana")).toEqual(ICONES_DE_ALIMENTO["generic-food"]);
  });
});

/* ─────────────────────────────────────────────────────────────────────────────────
 * Renderização
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("a peça renderizada", () => {
  let host, root;

  const montar = async elemento => act(async () => root.render(elemento));
  const ver = id => host.querySelector(`[data-testid="${id}"]`);

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("o canvas é desenhado em 1080 x 1920 e encolhido por transform", async () => {
    // É isto que faz a prévia e a exportação terem a mesma composição: elas são o mesmo
    // layout, com os mesmos números, visto de longe.
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO} />);
    const canvas = ver("fc-canvas");
    expect(canvas.style.width).toBe("1080px");
    expect(canvas.style.height).toBe("1920px");
    expect(canvas.style.transform).toMatch(/^scale\(/);
  });

  test("a peça mostra a marca e a assinatura", async () => {
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO} />);
    expect(host.textContent).toContain("FORGE");
    expect(host.textContent).toContain("DISCIPLINA");
    expect(host.textContent).toContain("RESULTADOS");
  });

  test("cada alimento vira um card com nome, quantidade, descrição e macro", async () => {
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO} />);
    const card = ver("fc-card-0");
    expect(card.textContent).toContain("CARNE MOÍDA");
    expect(card.textContent).toContain("180 g");
    expect(card.textContent).toContain("Fonte de proteína de alto valor biológico");
    expect(card.textContent).toContain("PROTEÍNA");
    expect(card.textContent).toContain("38 g");
  });

  test("cada card tem um conector com ponto de âncora", async () => {
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO}
                                 onPointerDownAncora={() => {}} />);
    expect(ver("fc-conector-0")).toBeTruthy();
    expect(ver("fc-ancora-0")).toBeTruthy();
  });

  test("o resumo mostra os quatro totais da refeição", async () => {
    await montar(<MacroSummary summary={RESUMO_DA_REFEICAO} />);
    const texto = ver("fc-resumo").textContent;
    expect(texto).toContain("47 g");
    expect(texto).toContain("43 g");
    expect(texto).toContain("32 g");
    expect(texto).toContain("648 kcal");
  });

  test("sem foto, a peça pede a foto em vez de mostrar um buraco", async () => {
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO} />);
    expect(ver("fc-foto-vazia")).toBeTruthy();
  });

  test("no modo prévia não há alça nem alvo de arrasto", async () => {
    // A prévia precisa mostrar EXATAMENTE o que a exportação vai ter.
    await montar(<FoodCardCanvas items={[ITEM]} summary={RESUMO_DA_REFEICAO}
                                 modoPreview selecionado={0}
                                 onPointerDownAncora={() => {}} />);
    expect(ver("fc-ancora-0")).toBeFalsy();
    expect(host.querySelector(".fc-callout-selecionado")).toBeFalsy();
  });

  test("quatro alimentos nascem em cantos diferentes, sem se cobrir", async () => {
    const quatro = [
      {...ITEM, foodId: "a", cardX: 0.06, cardY: 0.16},
      {...ITEM, foodId: "b", cardX: 0.52, cardY: 0.16},
      {...ITEM, foodId: "c", cardX: 0.06, cardY: 0.60},
      {...ITEM, foodId: "d", cardX: 0.52, cardY: 0.60},
    ];
    await montar(<FoodCardCanvas items={quatro} summary={RESUMO_DA_REFEICAO} />);
    const posicoes = quatro.map((_, i) => {
      const el = ver(`fc-card-${i}`);
      return `${el.style.left}/${el.style.top}`;
    });
    expect(new Set(posicoes).size).toBe(4);
  });
});

/* ─────────────────────────────────────────────────────────────────────────────────
 * A escolha dos alimentos
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("escolher quais alimentos destacar", () => {
  let host, root;
  const ver = id => host.querySelector(`[data-testid="${id}"]`);
  const clicar = el => el.dispatchEvent(new MouseEvent("click", {bubbles: true}));

  const CINCO = ["carne", "moranga", "codorna", "azeite", "arroz"].map((id, i) => ({
    foodId: id, name: id, quantity: 100 + i, unit: "g", iconKey: "generic-food",
  }));

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("começa com os quatro primeiros marcados", async () => {
    await act(async () => root.render(
      <FoodSelector alimentos={CINCO} maximo={4} onConfirmar={() => {}} />));
    const marcados = host.querySelectorAll('[role="checkbox"][aria-checked="true"]');
    expect(marcados.length).toBe(4);
  });

  test("o quinto fica bloqueado enquanto quatro estiverem marcados", async () => {
    await act(async () => root.render(
      <FoodSelector alimentos={CINCO} maximo={4} onConfirmar={() => {}} />));
    // Cinco cards numa peça de 1080x1920 ou se sobrepõem ou ficam pequenos demais para
    // ler no Story. O limite é de composição, e não arbitrário.
    expect(ver("fc-selector-arroz").disabled).toBe(true);
  });

  test("desmarcar um libera o bloqueado", async () => {
    await act(async () => root.render(
      <FoodSelector alimentos={CINCO} maximo={4} onConfirmar={() => {}} />));
    await act(async () => clicar(ver("fc-selector-carne")));
    expect(ver("fc-selector-arroz").disabled).toBe(false);
  });

  test("confirmar entrega exatamente os escolhidos", async () => {
    const recebido = jest.fn();
    await act(async () => root.render(
      <FoodSelector alimentos={CINCO} maximo={4} onConfirmar={recebido} />));
    await act(async () => clicar(ver("fc-selector-azeite")));
    await act(async () => clicar(ver("fc-selector-confirmar")));
    expect(recebido).toHaveBeenCalledWith(["carne", "moranga", "codorna"]);
  });

  test("a tela diz que o resumo continua somando a refeição inteira", async () => {
    await act(async () => root.render(
      <FoodSelector alimentos={CINCO} maximo={4} onConfirmar={() => {}} />));
    expect(ver("fc-selector").textContent).toMatch(/refeição inteira/i);
  });
});

/* ─────────────────────────────────────────────────────────────────────────────────
 * Exportação
 * ───────────────────────────────────────────────────────────────────────────────── */

describe("a exportação", () => {
  test("o nome do arquivo tem carimbo de tempo, para não sobrescrever o anterior", () => {
    const nome = nomeDoArquivo();
    expect(nome).toMatch(/^forge-food-card-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.png$/);
  });
});
