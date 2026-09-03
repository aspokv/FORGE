import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import Landing from "./Landing";

test("public entry preserves login and catalog with a clearly labelled product demo",()=>{
  const html=renderToStaticMarkup(<Landing API="/api" onComecar={()=>{}} onEntrar={()=>{}}/>);
  const doc=new DOMParser().parseFromString(html,"text/html");
  expect(doc.querySelector("h1").textContent).toContain("Seu próximo nível");
  expect(doc.querySelector('[data-testid="landing-primary-cta"]').getAttribute("href")).toBe("#planos");
  expect(doc.querySelector("#planos")).not.toBeNull();
  expect(doc.querySelector('[data-testid="landing-login"]')).not.toBeNull();
  expect(doc.querySelector(".landing-instrument")).toBeNull();
  expect(doc.querySelector("figcaption").textContent).toContain("Dados ilustrativos");
  expect(doc.querySelector(".entry-phone img").getAttribute("alt")).toContain("costas");
});
