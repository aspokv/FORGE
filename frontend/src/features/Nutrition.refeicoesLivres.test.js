import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import Nutrition from "./Nutrition";

jest.mock("axios", () => ({get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT = true;

const refeicao = (name, food_id, grams) => ({name, target_cal: 400, target_protein: 30, target_fat: 10,
  foods: [{food_id, grams, food: {name: food_id, grams: 100, kcal: 150, protein_g: 10, carbs_g: 15, fat_g: 5}}]});
const PLANO = {targets: {goal_calories: 2000, protein_g: 150, carbs_g: 200, fat_g: 60},
  meals: [refeicao("Café da manhã", "eggs-whole", 100), refeicao("Almoço", "rice-white", 150)]};

function respostas(capacidades) {
  axios.get.mockImplementation(url => {
    if (url.endsWith("/nutrition/plan")) return Promise.resolve({data: PLANO});
    if (url.includes("/adherence/")) return Promise.resolve({data: {meals: [], extras: []}});
    if (url.includes("/billing/") || url.includes("access") || url.includes("entitlement"))
      return Promise.resolve({data: {capabilities: capacidades}});
    if (url.endsWith("/nutrition/consumed-foods")) return Promise.resolve({data: {foods: []}});
    return Promise.resolve({data: {capabilities: capacidades}});
  });
}

async function montar(capacidades) {
  respostas(capacidades);
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<Nutrition API="/api"/>));
  return {host, root, $: id => document.querySelector(`[data-testid="${id}"]`)};
}

afterEach(() => { jest.clearAllMocks(); document.body.innerHTML = ""; });

test("Elite vê nova refeição, montar do seu jeito e excluir em cada refeição", async () => {
  const {root, $} = await montar(["nutrition", "food_plan_search"]);
  try {
    expect($("nova-refeicao")).not.toBeNull();
    expect($("montar-refeicao-0")).not.toBeNull();
    expect($("excluir-refeicao-1")).not.toBeNull();
    // O que existia continua: trocar um alimento pelo motor.
    expect($("edit-meal-foods-0").textContent).toBe("Trocar um alimento");
    // "+ Adicionar" era lido como "adicionar refeição"; agora diz o que faz.
    expect($("registrar-extra").textContent).toBe("+ Registrar extra");
  } finally { await act(async () => root.unmount()); }
});

test("sem Elite nada disso aparece, e o registro de extra continua", async () => {
  const {root, $} = await montar(["nutrition"]);
  try {
    expect($("nova-refeicao")).toBeNull();
    expect($("montar-refeicao-0")).toBeNull();
    expect($("excluir-refeicao-0")).toBeNull();
    expect($("registrar-extra")).not.toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("excluir confirma antes, e depois a tela mostra o plano novo e relê o dia", async () => {
  const {root, $} = await montar(["nutrition", "food_plan_search"]);
  try {
    axios.delete.mockResolvedValue({data: {plan: {...PLANO, meals: [PLANO.meals[1]]}, removida: "Café da manhã"}});
    await act(async () => $("excluir-refeicao-0").click());
    expect(axios.delete).not.toHaveBeenCalled();
    const lidasAntes = axios.get.mock.calls.filter(([u]) => u.includes("/adherence/")).length;
    await act(async () => $("confirmar-exclusao").click());
    expect(axios.delete).toHaveBeenCalledWith("/api/nutrition/plan/meals/0",
      {params: {nome: "Café da manhã", dia: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/)}});
    expect($("excluir-refeicao-1")).toBeNull();
    expect(document.body.textContent).toContain("Café da manhã saiu do plano.");
    // Os registros de hoje mudaram de lugar no servidor: a tela precisa relê-los.
    expect(axios.get.mock.calls.filter(([u]) => u.includes("/adherence/")).length).toBeGreaterThan(lidasAntes);
  } finally { await act(async () => root.unmount()); }
});
