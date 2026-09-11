import {isPullPlan,isLegPlan,isPushPlan,planArtworkKindFor,planArtworkFor} from "./ReferenceHome";
import ReferenceHome from "./ReferenceHome";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";

const casa=(extra={})=>{
  const html=renderToStaticMarkup(<ReferenceHome db={{profile:{name:"Nicolas"},program:{},...extra}} start={()=>{}}/>);
  return new DOMParser().parseFromString(html,"text/html").querySelector('[data-testid="reference-home-v3"]');
};

test("a abertura apresenta a hierarquia premium e reúne foto, texto e ação no card",()=>{
  const home=casa();
  expect(home.querySelector("h1").textContent).toBe("Seu treino está pronto.");
  const hero=home.querySelector('[data-testid="home-top-hero"]');
  expect(hero).not.toBeNull();
  expect(hero.querySelector("img").getAttribute("src")).toBeTruthy();
  expect(hero.querySelector("img").getAttribute("alt")).toBeTruthy();
  expect(hero.closest(".a6-signature")).not.toBeNull();
  expect(home.querySelector(".a6-signature-footer [data-testid=\"start-workout-button\"]")).not.toBeNull();
  expect(home.querySelector('[data-testid="daily-briefing"]')).not.toBeNull();
});

test("header usa wordmark FORGE limpo e hero continua inclusivo",()=>{
  const home=casa();
  const logo=home.querySelector('.a6-logo[aria-label="FORGE"] img');
  expect(logo).not.toBeNull();
  expect(logo.getAttribute("src")).toBeTruthy();
  const hero=home.querySelector('[data-testid="home-top-hero"] img');
  expect(hero.getAttribute("alt")).toContain("Homem e mulher");
});

test("ritmo, nutricao e hidratacao continuam no Inicio",()=>{
  const home=casa();
  ["home-training-week","home-acoes-rapidas","home-nutrition-progress","home-hydration"]
    .forEach(id=>expect(home.querySelector(`[data-testid="${id}"]`)).not.toBeNull());
});

test("comecar treino continua uma acao visivel",()=>{
  const botao=casa().querySelector('[data-testid="start-workout-button"]');
  expect(botao).not.toBeNull();
  expect(botao.tagName).toBe("BUTTON");
  expect(botao.textContent).toContain("Começar treino");
});

test("nutricao e hidratacao expõem indicadores de progresso acessíveis",()=>{
  const home=casa();
  const nutrition=home.querySelector('[role="progressbar"][aria-label="Progresso de nutrição"]');
  const hydration=home.querySelector('[role="progressbar"][aria-label="Progresso de hidratação"]');
  expect(nutrition).not.toBeNull();
  expect(hydration).not.toBeNull();
  expect(nutrition.getAttribute("aria-valuenow")).toBe("0");
  expect(hydration.getAttribute("aria-valuenow")).toBe("0");
});

test("nenhum valor interno aparece na tela",()=>{
  const texto=casa({profile:{name:"Nicolas",automation_mode:"FORGE_AUTO"}}).textContent;
  ["FORGE_AUTO","FORGE_PRO","ACTIVE","ELITE","undefined","NaN"].forEach(termo=>expect(texto).not.toContain(termo));
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
    expect(planArtworkFor("Pull 2",["Costas"])).toBe("/images/anatomy/pull-back.webp");
  });
});

test("completed home does not borrow focus, duration or sets from a newly saved program",()=>{
 const key="forge_workout_completion:history-check";
 localStorage.setItem(key,JSON.stringify({day:1,label:"Push antigo",completed_at:new Date().toISOString(),summary:{completed_sets:4,duration_seconds:600}}));
 try{
  const home=casa({profile:{id:"history-check",name:"Atleta"},program:{active_day:1,focus:["Foco novo"],duration:"99 min",sessions:[{day:1,label:"Upper novo",focus:["Foco novo"],exercises:[{sets:99}]}]}});
  const card=home.querySelector(".a6-signature");
  expect(card.textContent).toContain("Push antigo");
  expect(card.textContent).toContain("4 séries");
  expect(card.textContent).toContain("10 min");
  expect(card.textContent).not.toContain("Foco novo");
  expect(card.textContent).not.toContain("99");
 }finally{localStorage.removeItem(key);}
});
