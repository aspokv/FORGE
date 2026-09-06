import {isPullPlan,isLegPlan,isPushPlan,planArtworkKindFor,planArtworkFor} from "./ReferenceHome";
import ReferenceHome from "./ReferenceHome";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";

/**
 * O teste anterior travava o desenho antigo: o lema de tres linhas e as sete gotas de
 * hidratacao. As duas coisas eram ornamento — a auditoria contou quinze circulos vazios
 * nesta tela — e sairam de proposito. O que este teste protege agora e o que importa: a
 * foto de abertura, o nome de quem entrou, as quatro secoes, e sobretudo a ACAO VISIVEL,
 * que antes era um botao escondido para leitor de tela.
 */
const casa = (extra = {}) => {
  const html = renderToStaticMarkup(
    <ReferenceHome db={{profile:{name:"Nicolas"},program:{},...extra}} start={()=>{}} />
  );
  return new DOMParser().parseFromString(html,"text/html")
    .querySelector('[data-testid="reference-home-v3"]');
};

test("a abertura mantem foto, marca e o nome de quem entrou", () => {
  const home = casa();
  const hero = home.querySelector('[data-testid="home-top-hero"]');
  expect(home.firstElementChild).toBe(hero);
  expect(hero.querySelector(".ref3-top-hero-brand").textContent).toBe("FORGE");
  expect(hero.querySelector("h1").textContent).toContain("Nicolas");
  expect(hero.querySelector("img").getAttribute("alt")).toBe("Ambiente de treino FORGE");
});

test("as quatro secoes continuam de pe", () => {
  const home = casa();
  [".ref3-week", ".ref3-plan", ".ref3-nutrition", ".ref3-hydration"]
    .forEach(seletor => expect(home.querySelector(seletor)).not.toBeNull());
});

test("comecar treino e um botao visivel, e nao so para leitor de tela", () => {
  // Era `ref3-a11y` — invisivel. Quem olhava precisava adivinhar que o cartao inteiro
  // era clicavel. Numa tela cujo proposito e levar ao treino, esse era o pior defeito.
  const botao = casa().querySelector('[data-testid="start-workout-button"]');
  expect(botao).not.toBeNull();
  expect(botao.className).toContain("fg-btn");
  expect(botao.className).not.toContain("ref3-a11y");
  expect(botao.textContent).toContain("Começar treino");
});

test("as acoes de hidratacao ficam sempre visiveis", () => {
  // Antes so apareciam depois de tocar no cartao inteiro. Descoberta por acidente nao e
  // navegacao.
  const home = casa();
  ["hydration-add-250", "hydration-add-500", "hydration-undo"]
    .forEach(id => expect(home.querySelector(`[data-testid="${id}"]`)).not.toBeNull());
});

test("os circulos vazios sairam da tela", () => {
  // A auditoria contou quinze: sete da semana, um anel de nutricao e sete gotas. Circulo
  // vazio nao e dado, e ruido.
  const home = casa();
  expect(home.querySelector(".ref3-drops")).toBeNull();
  expect(home.querySelector(".ref3-calorie-ring")).toBeNull();
  expect(home.innerHTML).not.toContain("conic-gradient");
});

test("nenhum valor interno aparece na tela", () => {
  const texto = casa({profile:{name:"Nicolas",automation_mode:"FORGE_AUTO"}}).textContent;
  ["FORGE_AUTO","FORGE_PRO","ACTIVE","ELITE","undefined","NaN"]
    .forEach(termo => expect(texto).not.toContain(termo));
});

describe("home plan artwork",()=>{
  it("identifies Pull sessions",()=>expect(isPullPlan("Pull 2",["Dorsais / largura","Costas / espessura"])).toBe(true));
  it("identifies Legs sessions and lower-body focus",()=>{
    expect(isLegPlan("Legs 2",["Quadríceps","Posteriores","Glúteos"])).toBe(true);
    expect(planArtworkKindFor("Legs 2",["Quadríceps","Posteriores","Glúteos"])).toBe("legs");
    expect(planArtworkFor("Legs 2",["Quadríceps"])).toBe("/images/anatomy/legs-quads-front.webp");
  });
  it("identifies Push sessions",()=>{
    expect(isPushPlan("Push 2",["Peitoral","Tríceps"])).toBe(true);
    expect(planArtworkKindFor("Push 2",["Peitoral","Tríceps"])).toBe("push");
    expect(planArtworkFor("Push 2",["Peitoral"])).toBe("/images/anatomy/push-front.webp");
  });
  it("keeps Pull separate from Push",()=>{
    expect(isPullPlan("Push 2",["Peitoral","Tríceps"])).toBe(false);
    expect(planArtworkKindFor("Pull 2",["Costas"])).toBe("pull");
  });
  it("never uses the old public placeholder path",()=>{
    expect(planArtworkFor("Legs 2",["Quadríceps"])).not.toBe("/images/reference/exercise-1.jpg");
    expect(planArtworkFor("Push 2",["Peitoral"])).not.toBe("/images/reference/exercise-1.jpg");
  });
});
