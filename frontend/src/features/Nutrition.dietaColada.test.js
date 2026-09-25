import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import Nutrition from "./Nutrition";

jest.mock("axios", () => ({get: jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT = true;

// O plano ativado a partir da dieta colada pelo atleta: carne com duas opções, legumes
// "à vontade" e a tabela de trocas do carboidrato.
const PLANO = {
  source: "manual_import", name: "DIETA — 83 KG | RECOMPOSIÇÃO",
  targets: {goal_calories: 2416, protein_g: 251, carbs_g: 224, fat_g: 57.5},
  meals: [{name: "Almoço", target_cal: 609, target_protein: 70, target_fat: 20, foods: [
    {food_id: "beef-grill", grams: 200, food: {name: "Carne bovina grelhada (patinho)"},
     alternativas: [{food_id: "chicken-breast", name: "Peito de frango grelhado"},
                    {food_id: "tilapia", name: "Filé de tilápia"}]},
    {food_id: "potato", grams: 250, food: {name: "Batata inglesa cozida"}},
    {food_id: "mixed-vegetables", grams: 100, a_vontade: true, food: {name: "Legumes e verduras variados"}},
  ]}],
  substituicoes: [{titulo: "Substituições do carboidrato", opcoes: [
    {food_id: "potato", name: "Batata inglesa cozida", grams: 250},
    {food_id: "sweet-potato", name: "Batata doce cozida", grams: 200},
    {food_id: "cassava", name: "Mandioca cozida", grams: 150},
  ]}],
};

function respostas(plano) {
  axios.get.mockImplementation(url => {
    if (url.endsWith("/nutrition/plan")) return Promise.resolve({data: plano});
    if (url.includes("/adherence/")) return Promise.resolve({data: {meals: [], extras: []}});
    return Promise.resolve({data: {}});
  });
}

async function montar(plano) {
  respostas(plano);
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => root.render(<Nutrition API="/api"/>));
  return {host, root};
}

test("as opções da dieta aparecem debaixo do alimento, na mesma quantidade", async () => {
  const {host, root} = await montar(PLANO);
  try {
    expect(host.querySelector('[data-testid="alternativas-0-0"]').textContent).toBe(
      "Pode trocar por Peito de frango grelhado ou Filé de tilápia, na mesma quantidade");
    expect(host.querySelector('[data-testid="alternativas-0-1"]')).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("legumes à vontade não aparecem como um limite de 100 g", async () => {
  const {host, root} = await montar(PLANO);
  try {
    const porcoes = [...host.querySelectorAll(".fg-alimento-porcao")].map(p => p.textContent);
    expect(porcoes.find(t => t.includes("à vontade"))).toContain("à vontade (~100g na conta)");
    expect(porcoes.some(t => t.startsWith("250g"))).toBe(true);
  } finally { await act(async () => root.unmount()); }
});

test("a tabela de trocas da dieta fica na aba de hoje", async () => {
  const {host, root} = await montar(PLANO);
  try {
    const trocas = host.querySelector('[data-testid="trocas-da-dieta"]');
    expect(trocas).not.toBeNull();
    expect(trocas.textContent.replace(/\s+/g, " ")).toContain(
      "250 g Batata inglesa cozida ou 200 g Batata doce cozida ou 150 g Mandioca cozida");
  } finally { await act(async () => root.unmount()); }
});

test("plano gerado pelo FORGE, sem trocas nem opções, continua igual", async () => {
  const gerado = {...PLANO, source: undefined, substituicoes: undefined,
    meals: [{...PLANO.meals[0], foods: [{food_id: "potato", grams: 250, food: {name: "Batata inglesa cozida"}}]}]};
  const {host, root} = await montar(gerado);
  try {
    expect(host.querySelector('[data-testid="trocas-da-dieta"]')).toBeNull();
    expect(host.querySelector(".fg-alimento-alternativas")).toBeNull();
    expect(host.querySelector(".fg-alimento-porcao").textContent.startsWith("250g")).toBe(true);
  } finally { await act(async () => root.unmount()); }
});
