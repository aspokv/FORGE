import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import PeriodizacaoDaDieta from "./PeriodizacaoDaDieta";

jest.mock("axios", () => ({get: jest.fn(), post: jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT = true;

const TABELA = [
  {semana: 1, degrau: 0, kcal: 2416, protein_g: 251, carbs_g: 224, fat_g: 57, travou: null},
  {semana: 2, degrau: 1, kcal: 2271, protein_g: 251, carbs_g: 188, fat_g: 57, travou: null},
  {semana: 3, degrau: 2, kcal: 2126, protein_g: 251, carbs_g: 151, fat_g: 57, travou: null},
  {semana: 4, degrau: 3, kcal: 2016, protein_g: 251, carbs_g: 124, fat_g: 57, travou: "carboidrato no piso de 124 g"},
];
const PREVIA = {passo_kcal: 145, piso_carbo_g: 124, tabela: TABELA,
  no_prato: [{refeicao: "Almoço", alimento: "Batata inglesa cozida", de: 250, para: 110}]};
const ATIVA = {status: "ativa", fase: "corte", ritmo: "moderado", semanas: 4, degrau: 1, tabela: TABELA,
  historico: [{semana: 1, decisao: "inicio", motivo: "Semana 1 é a sua dieta."},
              {semana: 2, decisao: "avancar", motivo: "Seu peso anda a -0,50 kg por semana. Degrau aplicado.",
               mudancas: [{refeicao: "Almoço", alimento: "Batata inglesa cozida", de: 250, para: 205}]}]};
const DESLIGADA = {liberado: true, periodizacao: null, fase_sugerida: "corte"};
const LIGADA = {liberado: true, periodizacao: ATIVA, semana_atual: 2};

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.useRealTimers(); jest.clearAllMocks(); });

async function montar(estado, props = {}) {
  axios.get.mockResolvedValue({data: estado});
  axios.post.mockImplementation(url => url.endsWith("/previa") ? Promise.resolve({data: PREVIA}) : Promise.resolve({data: {}}));
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => root.render(<PeriodizacaoDaDieta API="/api" {...props}/>));
  await act(async () => { jest.advanceTimersByTime(300); });
  return {host, root, $: id => host.querySelector(`[data-testid="${id}"]`)};
}
const chamadas = sufixo => axios.post.mock.calls.filter(([u]) => u.endsWith(sufixo));

test("sem Elite: a chave aparece desligada e não liga", async () => {
  const {root, $} = await montar({liberado: false, periodizacao: null});
  try {
    expect($("pd-chave").getAttribute("aria-checked")).toBe("false");
    expect($("pd-chave").disabled).toBe(true);
    expect($("pd-fase-corte")).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("desligada: escolher o tipo já mostra as semanas e o prato, sem botão de começar", async () => {
  const {host, root, $} = await montar(DESLIGADA);
  try {
    expect($("pd-chave").getAttribute("aria-checked")).toBe("false");
    expect($("pd-fase-corte").getAttribute("aria-checked")).toBe("true");
    expect(chamadas("/previa").at(-1)[1]).toEqual({fase: "corte", semanas: 4, ritmo: "moderado"});
    expect(host.querySelectorAll(".pd-semana")).toHaveLength(4);
    expect($("pd-prato-previa").textContent).toContain("250 g → 110 g");
    expect(host.textContent).not.toMatch(/Começar/);
    // Trocar uma escolha refaz a prévia.
    await act(async () => $("pd-semanas-8").click());
    await act(async () => { jest.advanceTimersByTime(300); });
    expect(chamadas("/previa").at(-1)[1]).toEqual({fase: "corte", semanas: 8, ritmo: "moderado"});
  } finally { await act(async () => root.unmount()); }
});

test("ligar a chave ativa com o tipo escolhido e já sai ligada", async () => {
  const {host, root, $} = await montar(DESLIGADA);
  try {
    await act(async () => $("pd-ritmo-forte").click());
    await act(async () => { jest.advanceTimersByTime(300); });
    axios.get.mockResolvedValue({data: LIGADA});
    await act(async () => $("pd-chave").click());
    expect(chamadas("/ativar")[0][1]).toEqual({fase: "corte", semanas: 4, ritmo: "forte"});
    expect($("pd-chave").getAttribute("aria-checked")).toBe("true");
    expect(host.textContent).toContain("semana 2 de 4");
    expect($("pd-aviso").textContent).toContain("Ligada");
  } finally { await act(async () => root.unmount()); }
});

test("ligada: mostra a semana, o motivo e o prato; desligar é só tocar na chave", async () => {
  const {host, root, $} = await montar(LIGADA);
  try {
    expect($("pd-chave").getAttribute("aria-checked")).toBe("true");
    expect($("pd-motivo").textContent).toContain("Degrau aplicado");
    expect($("pd-prato").textContent).toContain("250 g → 205 g");
    expect(host.querySelector(".pd-semana.atual").textContent).toContain("Semana 2");
    expect($("pd-fase-corte")).toBeNull();   // o tipo não muda com ela ligada
    axios.get.mockResolvedValue({data: {...DESLIGADA, periodizacao: {...ATIVA, status: "encerrada"}}});
    await act(async () => $("pd-chave").click());
    expect(chamadas("/encerrar")).toHaveLength(1);
    expect($("pd-chave").getAttribute("aria-checked")).toBe("false");
    expect($("pd-aviso").textContent).toContain("desligada");
  } finally { await act(async () => root.unmount()); }
});

test("erro ao ligar: a chave continua desligada e diz o motivo", async () => {
  const {host, root, $} = await montar(DESLIGADA);
  try {
    axios.post.mockImplementation(url => url.endsWith("/previa") ? Promise.resolve({data: PREVIA})
      : Promise.reject({response: {status: 409, data: {detail: "Já existe uma periodização em andamento."}}}));
    await act(async () => $("pd-chave").click());
    expect($("pd-chave").getAttribute("aria-checked")).toBe("false");
    expect(host.querySelector('[role="alert"]').textContent).toContain("em andamento");
  } finally { await act(async () => root.unmount()); }
});

test("prévia impossível (ex.: carbo já no piso) não deixa ligar", async () => {
  axios.get.mockResolvedValue({data: DESLIGADA});
  axios.post.mockRejectedValue({response: {status: 422, data: {detail: "Seu carboidrato já está no mínimo seguro."}}});
  const host = document.createElement("div");
  const root = createRoot(host);
  try {
    await act(async () => root.render(<PeriodizacaoDaDieta API="/api"/>));
    await act(async () => { jest.advanceTimersByTime(300); });
    expect(host.querySelector('[data-testid="pd-erro-previa"]').textContent).toContain("mínimo seguro");
    expect(host.querySelector('[data-testid="pd-chave"]').disabled).toBe(true);
  } finally { await act(async () => root.unmount()); }
});

test("versão compacta só aparece ligada", async () => {
  const ligada = await montar(LIGADA, {compacto: true});
  expect(ligada.$("pd-compacto").textContent).toContain("Periodização ligada · semana 2 de 4");
  await act(async () => ligada.root.unmount());
  const desligada = await montar(DESLIGADA, {compacto: true});
  expect(desligada.host.innerHTML).toBe("");
  await act(async () => desligada.root.unmount());
});
