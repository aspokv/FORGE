import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import NutritionImport from "./NutritionImport";

jest.mock("axios", () => ({get: jest.fn(), post: jest.fn(), put: jest.fn()}));
jest.mock("framer-motion", () => ({motion: {div: ({children, initial, animate, ...p}) => <div {...p}>{children}</div>}}));
global.IS_REACT_ACT_ENVIRONMENT = true;

const CATALOGO = [
  {id: "beef-grill", name: "Carne bovina grelhada (patinho)"},
  {id: "chicken-breast", name: "Peito de frango grelhado"},
  {id: "tilapia", name: "Filé de tilápia"},
  {id: "mixed-vegetables", name: "Legumes e verduras variados"},
  {id: "potato", name: "Batata inglesa cozida"},
  {id: "sweet-potato", name: "Batata doce cozida"},
  {id: "cassava", name: "Mandioca cozida"},
];

// O rascunho como o servidor devolve para "Carne bovina/frango/peixe: 200 g" e
// "Legumes/verduras: à vontade", com a tabela de trocas da mesma dieta.
function rascunho() {
  return {
    name: "DIETA — 83 KG | RECOMPOSIÇÃO",
    meals: [{name: "Almoço", totals: {kcal: 470}, items: [
      {food_id: "beef-grill", raw_name: "Carne bovina/frango/peixe", raw_text: "Carne bovina/frango/peixe: 200 g",
       grams: 200, estimated: false, alternativas: ["chicken-breast", "tilapia"], a_vontade: false,
       needs_review: false, review_reasons: [], macros: {kcal: 440, protein_g: 64, carbs_g: 0, fat_g: 18}},
      {food_id: "mixed-vegetables", raw_name: "Legumes/verduras", raw_text: "Legumes/verduras: à vontade",
       grams: 100, estimated: true, alternativas: [], a_vontade: true,
       needs_review: true, review_reasons: ["free_portion"], macros: {kcal: 28, protein_g: 1.4, carbs_g: 5.6, fat_g: 0.2}},
    ]}],
    substituicoes: [{titulo: "Substituições do carboidrato", opcoes: [
      {food_id: "potato", raw_name: "batata inglesa", grams: 250},
      {food_id: "sweet-potato", raw_name: "batata-doce", grams: 200},
      {food_id: "cassava", raw_name: "aipim", grams: 150},
    ]}],
    warnings: ["Linha ignorada por nao parecer alimento: Ômega 3"],
    daily_totals: {kcal: 470, protein_g: 65, carbs_g: 6, fat_g: 18},
    stats: {meals: 1, items: 2, needs_review: 1},
  };
}

function digitar(el, valor) {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, valor);
  el.dispatchEvent(new Event("input", {bubbles: true}));
}

async function abrirComDietaColada() {
  axios.get.mockImplementation(url => {
    if (url.endsWith("/nutrition/import/draft")) return Promise.resolve({data: {draft: null}});
    if (url.endsWith("/nutrition/foods")) return Promise.resolve({data: {foods: CATALOGO}});
    return Promise.resolve({data: {}});
  });
  axios.post.mockResolvedValue({data: {draft: rascunho(), blocking_errors: []}});
  axios.put.mockImplementation((url, body) => Promise.resolve({data: {draft: body.draft, blocking_errors: []}}));
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<NutritionImport API="/api" onActivated={() => {}} onClose={() => {}}/>));
  await act(async () => digitar(host.querySelector('[data-testid="diet-textarea"]'), "texto colado"));
  await act(async () => host.querySelector('[data-testid="diet-parse-button"]').click());
  return {host, root};
}

afterEach(() => { jest.clearAllMocks(); document.body.innerHTML = ""; });

test("as opções da dieta aparecem e trocar por uma devolve a anterior para a lista", async () => {
  const {host, root} = await abrirComDietaColada();
  try {
    const chips = () => [...host.querySelectorAll('[data-testid="diet-alternatives-0-0"] button')].map(b => b.textContent);
    expect(chips()).toEqual(["Peito de frango grelhado", "Filé de tilápia"]);

    await act(async () => host.querySelector('[data-testid="diet-alternative-0-0-chicken-breast"]').click());
    expect(host.querySelector('[data-testid="diet-food-select-0-0"]').value).toBe("chicken-breast");
    // A carne não some: volta como opção, e a tilápia continua lá.
    expect(chips()).toEqual(["Carne bovina grelhada (patinho)", "Filé de tilápia"]);
  } finally { await act(async () => root.unmount()); }
});

test("a vontade é explicado, e não confundido com medida caseira", async () => {
  const {host, root} = await abrirComDietaColada();
  try {
    const legumes = host.querySelector('[data-testid="diet-item-0-1"]');
    expect(legumes.textContent).toContain("à vontade");
    expect(legumes.textContent).toContain("porção de referência");
    expect(legumes.textContent).not.toContain("medida caseira");
  } finally { await act(async () => root.unmount()); }
});

test("a tabela de trocas e as linhas que ficaram de fora ficam visíveis", async () => {
  const {host, root} = await abrirComDietaColada();
  try {
    const trocas = host.querySelector('[data-testid="diet-substitutions"]');
    expect(trocas.textContent.replace(/\s+/g, " ")).toContain(
      "250 g Batata inglesa cozida ou 200 g Batata doce cozida ou 150 g Mandioca cozida");
    // Antes, o aviso virava um pedaço de frase emendado na mensagem de erro.
    const avisos = [...host.querySelectorAll('[data-testid="diet-warnings"] li')].map(li => li.textContent);
    expect(avisos).toEqual(["Linha ignorada por nao parecer alimento: Ômega 3"]);
    expect(host.querySelector('[data-testid="diet-message"]')).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("um rascunho salvo não prende a tela: dá para colar outra dieta", async () => {
  // O vídeo do atleta: a tela abria direto no rascunho antigo e a caixa de texto sumia.
  axios.get.mockImplementation(url => {
    if (url.endsWith("/nutrition/import/draft")) return Promise.resolve({data: {draft: rascunho(), blocking_errors: []}});
    if (url.endsWith("/nutrition/foods")) return Promise.resolve({data: {foods: CATALOGO}});
    return Promise.resolve({data: {}});
  });
  axios.delete = jest.fn().mockResolvedValue({data: {discarded: true}});
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<NutritionImport API="/api" onActivated={() => {}} onClose={() => {}}/>));
    expect(host.querySelector('[data-testid="diet-textarea"]')).toBeNull();
    await act(async () => host.querySelector('[data-testid="diet-paste-again"]').click());
    expect(axios.delete).toHaveBeenCalledWith("/api/nutrition/import/draft");
    expect(host.querySelector('[data-testid="diet-textarea"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="diet-preview"]')).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("digitar os gramas assume o número: deixa de ser à vontade ao salvar", async () => {
  const {host, root} = await abrirComDietaColada();
  try {
    await act(async () => digitar(host.querySelector('[data-testid="diet-grams-0-1"]'), "150"));
    await act(async () => host.querySelector('[data-testid="diet-save-draft"]').click());
    const enviado = axios.put.mock.calls[0][1].draft.meals[0].items[1];
    expect(enviado).toMatchObject({grams: 150, estimated: false, a_vontade: false});
    // O que não foi tocado segue como veio.
    expect(axios.put.mock.calls[0][1].draft.meals[0].items[0].alternativas).toEqual(["chicken-breast", "tilapia"]);
    expect(axios.put.mock.calls[0][1].draft.substituicoes).toHaveLength(1);
  } finally { await act(async () => root.unmount()); }
});
