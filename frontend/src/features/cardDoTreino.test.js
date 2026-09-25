import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import ReferenceHome from "./ReferenceHome";
import {fraseDoCard, mapaDoCard, tituloEmDuasCores} from "./cardDoTreino";
import {TRAINING_CATEGORIES} from "./trainingCardArtwork";

describe("título em duas cores", () => {
  test("a parte depois da vírgula é a que ganha a cor", () => {
    expect(tituloEmDuasCores("Peito dominante, costas e braços")).toEqual(["Peito dominante,", " costas e braços"]);
  });
  test("sem vírgula, a última palavra", () => {
    expect(tituloEmDuasCores("Upper C")).toEqual(["Upper", " C"]);
  });
  test("uma palavra só fica inteira clara", () => {
    expect(tituloEmDuasCores("Push")).toEqual(["Push", ""]);
  });
  test("o texto nunca muda, só a cor", () => {
    for (const t of ["Peito dominante, costas e braços", "A · Quadríceps", "Full Body 45", "Treino de hoje", ""]) {
      expect(tituloEmDuasCores(t).join("")).toBe(t);
    }
  });
});

test("toda categoria de arte tem frase", () => {
  for (const c of TRAINING_CATEGORIES) expect(fraseDoCard(c).length).toBeGreaterThan(10);
  expect(fraseDoCard("inexistente")).toBe(fraseDoCard("default"));
});

describe("o mapa mostra o lado que trabalha", () => {
  test("sessão de glúteos e posterior mostra frente e costas", () => {
    expect(mapaDoCard([], [], ["Glúteos", "Posteriores"], "Glúteos dominante, posterior e core").lados).toEqual(["front", "back"]);
  });
  test("sessão de puxada mostra as costas", () => {
    expect(mapaDoCard([], [], ["Dorsais"], "Pull 1")).toEqual({chave: "pull", lados: ["back"]});
  });
  test("sessão de empurrar mostra a frente", () => {
    expect(mapaDoCard([], [], ["Peitoral"], "Push 1")).toEqual({chave: "push", lados: ["front"]});
  });
});

test("o card da tela inicial traz marca, mapa e frase, escondidos do leitor de tela", () => {
  const html = renderToStaticMarkup(<ReferenceHome db={{profile: {name: "Rafael", sex: "male"}, program: {
    active_day: 1, sessions: [{day: 1, label: "Peito dominante, costas e braços", focus: ["Peitoral", "Dorsais"], exercises: [{sets: 4}]}],
  }}} start={() => {}}/>);
  const home = new DOMParser().parseFromString(html, "text/html");
  const titulo = home.querySelector("#home-session-title");
  expect(titulo.textContent).toBe("Peito dominante, costas e braços");
  expect(titulo.querySelector(".forge-card-titulo-destaque").textContent).toBe(" costas e braços");
  const assinatura = home.querySelector('[data-testid="home-card-assinatura"]');
  expect(assinatura.getAttribute("aria-hidden")).toBe("true");
  expect(assinatura.querySelector(".forge-card-marca")).not.toBeNull();
  expect(assinatura.querySelectorAll(".forge-card-mapa img").length).toBeGreaterThan(0);
  expect(assinatura.querySelector(".forge-card-mapa img").getAttribute("src")).toMatch(/^\/?images\/anatomy\/[a-z-]+-(front|back)\.webp$|\/images\/anatomy\//);
  expect(assinatura.querySelector(".forge-card-frase").textContent.length).toBeGreaterThan(10);
});
