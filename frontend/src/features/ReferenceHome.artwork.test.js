import {isPullPlan,planArtworkFor} from "./ReferenceHome";
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
  it("identifies Pull by back focus",()=>expect(isPullPlan("Treino B",["Costas / espessura"])).toBe(true));
  it("does not classify Push as Pull",()=>expect(isPullPlan("Push 2",["Peitoral","Tríceps"])).toBe(false));
  it("keeps the default artwork for non-Pull sessions",()=>expect(planArtworkFor("Push 2",["Peitoral","Tríceps"])).toBe("/images/reference/exercise-1.jpg"));
});
