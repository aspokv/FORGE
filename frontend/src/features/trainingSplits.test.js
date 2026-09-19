import fs from "fs";
import path from "path";
import {HYBRID_SEVEN, HYBRID_SIX, SPLIT_LABELS, splitOptions, validSplitPreference} from "./trainingSplits";

/**
 * A lista de divisões da tela contra a do motor.
 *
 * `trainingSplits.js` é uma cópia de `engine.compatible_splits` e `engine.SPLIT_LABELS`.
 * Duas listas no mesmo produto divergem no dia em que alguém mexe só numa, e a divergência
 * não aparece em lugar nenhum até um atleta escolher uma opção que o backend recusa com
 * 422 — ou, pior, não enxergar uma divisão que já existe no motor.
 *
 * Então estes testes leem o Python e comparam. Não é elegante; é o que transforma a
 * divergência em teste vermelho no CI em vez de num relato de suporte.
 */

const BACKEND = path.join(__dirname, "..", "..", "..", "backend");

function lerPython(arquivo) {
  return fs.readFileSync(path.join(BACKEND, arquivo), "utf8");
}

describe("as divisões da tela e as do motor", () => {
  test("toda arquitetura híbrida do motor está na lista da tela", () => {
    const motor = lerPython("training_engine_hybrid.py");
    const chaves = [...motor.matchAll(/^(HYBRID_\d+) = "(hybrid_\d+)"$/gm)].map(m => m[2]);

    expect(chaves.length).toBeGreaterThan(0);
    for (const chave of chaves) {
      expect(SPLIT_LABELS[chave]).toBeTruthy();
    }
    expect([...HYBRID_SIX, ...HYBRID_SEVEN].sort()).toEqual(chaves.sort());
  });

  test("os rótulos são os mesmos dos dois lados", () => {
    const motor = lerPython("training_engine_hybrid.py");
    for (const chave of [...HYBRID_SIX, ...HYBRID_SEVEN]) {
      // No Python o rótulo vem logo depois da chave, em `"label": "..."`.
      const bloco = motor.split(`${chave.toUpperCase()}: {`)[1];
      expect(bloco).toBeTruthy();
      const rotulo = bloco.match(/"label": "([^"]+)"/)[1];
      expect(SPLIT_LABELS[chave]).toBe(rotulo);
    }
  });

  test("as híbridas de seis e de sete dias estão separadas como no motor", () => {
    const motor = lerPython("training_engine_hybrid.py");
    for (const chave of HYBRID_SIX) {
      const bloco = motor.split(`${chave.toUpperCase()}: {`)[1];
      expect(bloco.match(/"dias": (\d)/)[1]).toBe("6");
    }
    for (const chave of HYBRID_SEVEN) {
      const bloco = motor.split(`${chave.toUpperCase()}: {`)[1];
      expect(bloco.match(/"dias": (\d)/)[1]).toBe("7");
    }
  });
});

describe("o que a tela oferece por frequência", () => {
  test("quem treina seis dias vê as três híbridas de seis", () => {
    const ids = splitOptions(6, "Avançado").map(x => x.id);
    for (const chave of HYBRID_SIX) expect(ids).toContain(chave);
    expect(ids).not.toContain("hybrid_04");
  });

  test("quem treina sete dias vê as de sete primeiro", () => {
    const ids = splitOptions(7, "Avançado").map(x => x.id);
    for (const chave of HYBRID_SEVEN) expect(ids).toContain(chave);
    expect(ids.indexOf("hybrid_04")).toBeLessThan(ids.indexOf("hybrid_01"));
  });

  test("o híbrido NÃO é a recomendação padrão de seis ou sete dias", () => {
    // A recomendada é a primeira da lista, e é ela que o motor usa para quem não tem
    // preferência gravada. Se uma híbrida assumisse esse lugar, todo atleta de seis dias
    // abriria o aplicativo com outro programa, no meio do ciclo, sem ter pedido.
    for (const dias of [6, 7]) {
      const recomendada = splitOptions(dias, "Avançado").find(x => x.recommended);
      expect(recomendada.id.startsWith("hybrid")).toBe(false);
    }
  });

  test("quem treina cinco dias ou menos não vê híbrido nenhum", () => {
    for (const dias of [1, 2, 3, 4, 5]) {
      const ids = splitOptions(dias, "Avançado").map(x => x.id);
      expect(ids.filter(x => x.startsWith("hybrid"))).toEqual([]);
    }
  });

  test("toda opção oferecida tem rótulo legível", () => {
    for (const dias of [1, 2, 3, 4, 5, 6, 7]) {
      for (const opcao of splitOptions(dias, "Avançado")) {
        expect(opcao.label).toBeTruthy();
        expect(opcao.label).not.toMatch(/^hybrid_/);
      }
    }
  });

  test("uma preferência de híbrido só é válida na frequência certa", () => {
    expect(validSplitPreference(6, "Avançado", "hybrid_01")).toBe("hybrid_01");
    // Pedir um híbrido de sete treinando seis não é preferência, é um programa que
    // faltaria um dia inteiro.
    expect(validSplitPreference(6, "Avançado", "hybrid_04")).toBe("");
  });
});
