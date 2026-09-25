import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import EditorDeRefeicao, {totaisDosItens} from "./EditorDeRefeicao";

jest.mock("axios", () => ({get: jest.fn(), post: jest.fn(), put: jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT = true;

const CATALOGO = [
  {id: "rice-white", name: "Arroz branco cozido", grams: 100, kcal: 128, protein_g: 2.5, carbs_g: 28, fat_g: 0.2},
  {id: "chicken-breast", name: "Peito de frango grelhado", grams: 100, kcal: 165, protein_g: 31, carbs_g: 0, fat_g: 3.6},
  {id: "eggs-whole", name: "Ovo inteiro", grams: 100, kcal: 143, protein_g: 13, carbs_g: 1, fat_g: 10},
];
const REFEICOES = [{name: "Café da manhã", foods: []}, {name: "Almoço", foods: []}];
const PLANO = {meals: [{name: "Nova", foods: []}]};

function digitar(el, valor) {
  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(el, valor);
  el.dispatchEvent(new Event("input", {bubbles: true}));
}

async function montar(props) {
  axios.get.mockResolvedValue({data: {foods: CATALOGO}});
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  const onSalvo = jest.fn();
  await act(async () => root.render(
    <EditorDeRefeicao API="/api" refeicoes={REFEICOES} dia="2026-09-24" onSalvo={onSalvo} onFechar={() => {}} {...props}/>));
  const $ = id => host.querySelector(`[data-testid="${id}"]`);
  return {host, root, onSalvo, $};
}

afterEach(() => { jest.clearAllMocks(); document.body.innerHTML = ""; });

test("criar: nome, posição, alimentos e gramas vão exatamente como escolhidos", async () => {
  axios.post.mockResolvedValue({data: {plan: PLANO}});
  const {root, onSalvo, $} = await montar({modo: "criar"});
  try {
    expect($("editor-salvar").disabled).toBe(true);   // sem nome e sem alimento
    await act(async () => digitar($("editor-nome"), "Almoço livre"));
    await act(async () => digitar($("editor-busca"), "arroz"));
    await act(async () => $("editor-resultado-rice-white").click());
    await act(async () => digitar($("editor-busca"), "frango"));
    await act(async () => $("editor-resultado-chicken-breast").click());
    await act(async () => digitar($("editor-gramas-0"), "220"));
    await act(async () => $("editor-posicao-1").click());
    // O total aparece antes de salvar: 220 g de arroz + 100 g de frango.
    expect($("editor-totais").textContent).toContain(`${Math.round(128 * 2.2 + 165)} kcal`);
    await act(async () => $("editor-salvar").click());
    expect(axios.post).toHaveBeenCalledWith("/api/nutrition/plan/meals", {
      nome: "Almoço livre", dia: "2026-09-24", posicao: 1,
      itens: [{food_id: "rice-white", grams: 220}, {food_id: "chicken-breast", grams: 100}]});
    expect(onSalvo).toHaveBeenCalledWith(PLANO);
  } finally { await act(async () => root.unmount()); }
});

test("editar: parte da refeição atual e manda o nome antigo como trava", async () => {
  axios.put.mockResolvedValue({data: {plan: PLANO}});
  const refeicao = {name: "Almoço", foods: [{food_id: "rice-white", grams: 150, food: CATALOGO[0]},
                                            {food_id: "chicken-breast", grams: 120, food: CATALOGO[1]}]};
  const {root, $} = await montar({modo: "editar", refeicao, indice: 1});
  try {
    expect($("editor-nome").value).toBe("Almoço");
    await act(async () => $("editor-tirar-0").click());          // tira o arroz
    await act(async () => digitar($("editor-nome"), "Almoço sem arroz"));
    await act(async () => $("editor-salvar").click());
    expect(axios.put).toHaveBeenCalledWith("/api/nutrition/plan/meals/1", {
      nome: "Almoço sem arroz", dia: "2026-09-24", nome_atual: "Almoço",
      itens: [{food_id: "chicken-breast", grams: 120}]});
  } finally { await act(async () => root.unmount()); }
});

test("alimento já escolhido não aparece de novo na busca", async () => {
  const {root, $} = await montar({modo: "criar"});
  try {
    await act(async () => digitar($("editor-busca"), "arroz"));
    await act(async () => $("editor-resultado-rice-white").click());
    await act(async () => digitar($("editor-busca"), "arroz"));
    expect($("editor-resultado-rice-white")).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("erro do servidor fica na tela e as escolhas continuam", async () => {
  axios.post.mockRejectedValue({response: {status: 400, data: {detail: "O plano já tem 6 refeições, que é o máximo. Exclua uma antes de criar outra."}}});
  const {host, root, onSalvo, $} = await montar({modo: "criar"});
  try {
    await act(async () => digitar($("editor-nome"), "Ceia"));
    await act(async () => digitar($("editor-busca"), "ovo"));
    await act(async () => $("editor-resultado-eggs-whole").click());
    await act(async () => $("editor-salvar").click());
    expect(host.querySelector('[role="alert"]').textContent).toContain("Exclua uma");
    expect(onSalvo).not.toHaveBeenCalled();
    expect($("editor-item-0")).not.toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("gramas inválidas não deixam salvar", async () => {
  const {root, $} = await montar({modo: "criar"});
  try {
    await act(async () => digitar($("editor-nome"), "Ceia"));
    await act(async () => digitar($("editor-busca"), "ovo"));
    await act(async () => $("editor-resultado-eggs-whole").click());
    for (const ruim of ["0", "-5", "2500", ""]) {
      await act(async () => digitar($("editor-gramas-0"), ruim));
      expect($("editor-salvar").disabled).toBe(true);
    }
  } finally { await act(async () => root.unmount()); }
});

test("os totais escalam pela porção de referência", () => {
  const t = totaisDosItens([{gramas: 50, base: {grams: 100, kcal: 200, protein_g: 10, carbs_g: 0, fat_g: 4}}]);
  expect(t).toEqual({kcal: 100, protein_g: 5, carbs_g: 0, fat_g: 2});
});
