import {isPullPlan,planArtworkFor} from "./ReferenceHome";
import ReferenceHome from "./ReferenceHome";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";

test("Home shows one FORGE masthead above the existing greeting", () => {
  const html = renderToStaticMarkup(<ReferenceHome db={{profile:{name:"Nicolas"},program:{}}} start={()=>{}} />);
  const doc = new DOMParser().parseFromString(html,"text/html");
  const home = doc.querySelector('[data-testid="reference-home-v3"]');
  expect(home.firstElementChild.getAttribute("data-testid")).toBe("home-forge-brand");
  expect(home.querySelectorAll('[data-testid="home-forge-brand"]')).toHaveLength(1);
  expect(home.firstElementChild.textContent).toBe("FORGE");
  expect(home.querySelector(".ref3-home-head h1").textContent).toContain("Nicolas");
  [".ref3-week", ".ref3-plan", ".ref3-nutrition", ".ref3-hydration"]
    .forEach(selector => expect(home.querySelector(selector)).not.toBeNull());
});

describe("home plan artwork",()=>{
  it("identifies Pull sessions",()=>expect(isPullPlan("Pull 2",["Dorsais / largura","Costas / espessura"])).toBe(true));
  it("identifies Pull by back focus",()=>expect(isPullPlan("Treino B",["Costas / espessura"])).toBe(true));
  it("does not classify Push as Pull",()=>expect(isPullPlan("Push 2",["Peitoral","Tríceps"])).toBe(false));
  it("keeps the default artwork for non-Pull sessions",()=>expect(planArtworkFor("Push 2",["Peitoral","Tríceps"])).toBe("/images/reference/exercise-1.jpg"));
});
