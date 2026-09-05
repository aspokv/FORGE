import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import Landing from "./Landing";

/**
 * O que a entrada publica precisa manter.
 *
 * As afirmacoes sobre a maquete antiga sairam junto com ela: a pagina remontava a Home em
 * marcacao, com calorias e cargas ilustrativas, e por isso precisava da legenda "Dados
 * ilustrativos" e de um `alt` falando de costas. Agora sao capturas reais do produto, que
 * nao pedem ressalva. O que ficou — e o que este arquivo protege — e o contrato de
 * integracao: o titulo, o caminho ate os planos e o acesso de quem ja tem conta.
 */
function render() {
  const html = renderToStaticMarkup(
    <Landing API="/api" onComecar={() => {}} onEntrar={() => {}} />
  );
  return new DOMParser().parseFromString(html, "text/html");
}

test("a entrada publica preserva titulo, catalogo e login", () => {
  const doc = render();
  expect(doc.querySelector("h1").textContent).toContain("Seu próximo nível");
  expect(doc.querySelector('[data-testid="landing-primary-cta"]').getAttribute("href"))
    .toBe("#planos");
  expect(doc.querySelector("#planos")).not.toBeNull();
  expect(doc.querySelector('[data-testid="landing-login"]')).not.toBeNull();
  expect(doc.querySelector(".landing-instrument")).toBeNull();
});

test("os botoes de integracao existem com rotulo e identificador estaveis", () => {
  const doc = render();
  const rotulo = (sel) =>
    doc.querySelector(sel).textContent.replace(/\s+/g, " ").trim();

  expect(rotulo("#landing-conhecer-os-planos")).toBe("Conhecer os planos");
  expect(rotulo("#landing-ja-tenho-conta")).toBe("Já tenho conta");
  expect(rotulo("#landing-comecar-agora")).toBe("Começar agora");

  // O topo e o rodape tambem levam para o login, com id proprio para nao duplicar.
  expect(doc.querySelector("#landing-ja-tenho-conta-topo")).not.toBeNull();
  expect(doc.querySelector("#landing-ja-tenho-conta-rodape")).not.toBeNull();
});

test("o hero mostra tres telas reais e nenhum dado inventado", () => {
  const doc = render();
  const telas = doc.querySelectorAll(".lp-palco img");
  expect(telas).toHaveLength(3);

  // Treino no centro; nutricao e progresso recuadas de cada lado.
  expect(doc.querySelector(".lp-tela-centro").getAttribute("alt")).toContain("treino");
  expect(doc.querySelector(".lp-tela-esquerda").getAttribute("alt")).toContain("nutrição");
  expect(doc.querySelector(".lp-tela-direita").getAttribute("alt")).toContain("progresso");

  // A tela inicial nao entra no hero: ela aparece sozinha no storytelling logo abaixo.
  telas.forEach((t) => expect(t.getAttribute("src")).not.toContain("inicio"));

  // Toda imagem do hero e um arquivo real, nao marcacao remontada.
  telas.forEach((t) => expect(t.getAttribute("src")).toBeTruthy());
  expect(doc.querySelector(".entry-screen")).toBeNull();
  expect(doc.body.textContent).not.toContain("Dados ilustrativos");
});

test("a linha tecnica anuncia os tres pilares", () => {
  const texto = render().querySelector(".lp-hero-linha").textContent;
  expect(texto).toContain("Treino personalizado");
  expect(texto).toContain("Nutrição");
  expect(texto).toContain("Progressão");
});

test("o storytelling separa as quatro telas, incluindo a inicial", () => {
  const doc = render();
  const fones = doc.querySelectorAll(".lp-story-fone img");
  expect(fones).toHaveLength(4);
  const alts = [...fones].map((f) => f.getAttribute("alt").toLowerCase());
  ["treino", "nutrição", "inicial", "progresso"].forEach((area) =>
    expect(alts.some((a) => a.includes(area))).toBe(true)
  );
});

test("o preco nunca e escrito na pagina, so o que a API devolver", () => {
  // O catalogo chega por /api/billing/plans. Sem resposta, a pagina nao inventa valor —
  // e a garantia de que nao existe um segundo lugar onde o preco possa divergir.
  const doc = render();
  expect(doc.querySelector(".lp-planos").children).toHaveLength(0);
  expect(doc.body.textContent).not.toMatch(/R\$\s*\d/);
});

test("o nome do plano vira caixa de frase no botao de assinatura", () => {
  // O catalogo devolve "FORGE ESSENCIAL"; o botao pedido e "Assinar Essencial".
  const { nomeCurto } = require("./Landing");
  expect(nomeCurto("FORGE ESSENCIAL")).toBe("Essencial");
  expect(nomeCurto("FORGE PRO")).toBe("Pro");
  expect(nomeCurto("FORGE ELITE")).toBe("Elite");
});
