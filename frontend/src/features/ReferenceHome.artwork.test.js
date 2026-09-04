import {isPullPlan,isLegPlan,isPushPlan,planArtworkKindFor,planArtworkFor} from "./ReferenceHome";
import ReferenceHome from "./ReferenceHome";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";

test("Home shows the cinematic FORGE hero above the existing dashboard", () => {
  const html = renderToStaticMarkup(<ReferenceHome db={{profile:{name:"Nicolas"},program:{}}} start={()=>{}} />);
  const doc = new DOMParser().parseFromString(html,"text/html");
  const home = doc.querySelector('[data-testid="reference-home-v3"]');
  const hero = home.querySelector('[data-testid="home-top-hero"]');

  expect(home.firstElementChild).toBe(hero);
  expect(hero).not.toBeNull();
  expect(hero.querySelector(".ref3-top-hero-brand").textContent).toBe("FORGE");
  expect(hero.querySelector("h1").textContent).toContain("Nicolas");
  expect(hero.querySelector(".ref3-top-hero-motto").textContent).toContain("DISCIPLINA");
  expect(hero.querySelector(".ref3-top-hero-motto").textContent).toContain("RESULTADOS");
  expect(hero.querySelector("img").getAttribute("alt")).toBe("Ambiente de treino FORGE");
  [".ref3-week", ".ref3-plan", ".ref3-nutrition", ".ref3-hydration"]
    .forEach(selector => expect(home.querySelector(selector)).not.toBeNull());
});

describe("home plan artwork",()=>{
  it("identifies Pull sessions",()=>expect(isPullPlan("Pull 2",["Dorsais / largura","Costas / espessura"])).toBe(true));
  it("identifies Legs sessions and lower-body focus",()=>{
    expect(isLegPlan("Legs 2",["Quadríceps","Posteriores","Glúteos"])).toBe(true);
    expect(planArtworkKindFor("Legs 2",["Quadríceps","Posteriores","Glúteos"])).toBe("legs");
    expect(String(planArtworkFor("Legs 2",["Quadríceps"]))).toContain("forge-plan-legs-reference");
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
