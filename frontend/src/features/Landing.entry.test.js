import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import Landing, { nomeCurto } from "./Landing";

function render() {
  const html = renderToStaticMarkup(
    <Landing API="/api" onComecar={() => {}} onEntrar={() => {}} />
  );
  return new DOMParser().parseFromString(html, "text/html");
}

test("a entrada publica preserva planos, login e checkout", () => {
  const doc = render();
  expect(doc.querySelector('[data-testid="landing-primary-cta"]').getAttribute("href"))
    .toBe("#planos");
  expect(doc.querySelector("#planos")).not.toBeNull();
  expect(doc.querySelector('[data-testid="landing-login"]')).not.toBeNull();
  expect(doc.querySelector("#landing-comecar-agora")).not.toBeNull();
});

test("a abertura cinematografica usa o telefone como protagonista", () => {
  const doc = render();
  const experience = doc.querySelector(".cinematic");
  expect(experience).not.toBeNull();
  expect(experience.querySelector(".cinematic-product")).not.toBeNull();
  expect(experience.querySelector(".cinematic-fallback-phone img").getAttribute("src"))
    .toBeTruthy();
  expect(experience.textContent).toContain("Um programa.");
  expect(experience.textContent).toContain("O seu perfil.");
});

test("a narrativa cobre treino, nutricao e evolucao sem inventar produto", () => {
  const text = render().querySelector(".cinematic-copy").textContent;
  expect(text).toContain("TREINO");
  expect(text).toContain("NUTRIÇÃO");
  expect(text).toContain("EVOLUÇÃO");
  expect(text).toContain("Cada registro decide");
});

test("a experiencia oferece os dois perfis e alternativa sem WebGL", () => {
  const doc = render();
  const profile = doc.querySelector(".cinematic-profile");
  expect(profile.textContent).toContain("Feminino");
  expect(profile.textContent).toContain("Masculino");
  expect(doc.querySelector(".cinematic-fallback-phone")).not.toBeNull();
});

test("preco vem somente da API e o nome do plano e normalizado", () => {
  const doc = render();
  expect(doc.querySelector(".lp-planos").children).toHaveLength(0);
  expect(doc.body.textContent).not.toMatch(/R\$\s*\d/);
  expect(nomeCurto("FORGE ESSENCIAL")).toBe("Essencial");
  expect(nomeCurto("FORGE PRO")).toBe("Pro");
  expect(nomeCurto("FORGE ELITE")).toBe("Elite");
});
