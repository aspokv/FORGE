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

async function montar(estado, props = {}) {
  axios.get.mockResolvedValue({data: estado});
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => root.render(<PeriodizacaoDaDieta API="/api" {...props}/>));
  return {host, root, $: id => host.querySelector(`[data-testid="${id}"]`)};
}

afterEach(() => jest.clearAllMocks());

test("sem Elite mostra o que é, sem deixar configurar", async () => {
  const {root, $} = await montar({liberado: false, periodizacao: null});
  try {
    expect($("pd-bloqueado")).not.toBeNull();
    expect($("pd-ver-previa")).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("configurar: a fase vem do objetivo, a prévia mostra as semanas e o prato, e aí começa", async () => {
  const {host, root, $} = await montar({liberado: true, periodizacao: null, fase_sugerida: "corte"});
  try {
    expect($("pd-fase-corte").getAttribute("aria-checked")).toBe("true");
    await act(async () => $("pd-semanas-4").click());
    await act(async () => $("pd-ritmo-moderado").click());
    axios.post.mockResolvedValueOnce({data: PREVIA});
    await act(async () => $("pd-ver-previa").click());
    expect(axios.post).toHaveBeenCalledWith("/api/nutrition/periodizacao/previa", {fase: "corte", semanas: 4, ritmo: "moderado"});
    expect(host.querySelectorAll(".pd-semana")).toHaveLength(4);
    expect(host.textContent).toContain("Batata inglesa cozida 250 g → 110 g");
    axios.post.mockResolvedValueOnce({data: {}});
    axios.get.mockResolvedValue({data: {liberado: true, periodizacao: ATIVA, semana_atual: 2}});
    await act(async () => $("pd-comecar").click());
    expect(axios.post).toHaveBeenLastCalledWith("/api/nutrition/periodizacao/ativar", {fase: "corte", semanas: 4, ritmo: "moderado"});
    expect($("pd-ativa")).not.toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("mudar uma escolha apaga a prévia velha", async () => {
  const {root, $} = await montar({liberado: true, periodizacao: null, fase_sugerida: "corte"});
  try {
    axios.post.mockResolvedValueOnce({data: PREVIA});
    await act(async () => $("pd-ver-previa").click());
    expect($("pd-previa")).not.toBeNull();
    await act(async () => $("pd-ritmo-forte").click());
    expect($("pd-previa")).toBeNull();
  } finally { await act(async () => root.unmount()); }
});

test("ativa: semana atual, o motivo da semana e o que mudou no prato", async () => {
  const {host, root, $} = await montar({liberado: true, periodizacao: ATIVA, semana_atual: 2});
  try {
    expect(host.textContent).toContain("Semana 2 de 4");
    expect($("pd-motivo").textContent).toContain("Degrau aplicado");
    expect($("pd-prato").textContent).toContain("250 g → 205 g");
    expect(host.querySelector(".pd-semana.atual").textContent).toContain("Semana 2");
  } finally { await act(async () => root.unmount()); }
});

test("encerrar pede confirmação antes", async () => {
  const {root, $} = await montar({liberado: true, periodizacao: ATIVA, semana_atual: 2});
  try {
    await act(async () => $("pd-encerrar").click());
    expect(axios.post).not.toHaveBeenCalled();
    axios.post.mockResolvedValueOnce({data: {status: "encerrada"}});
    await act(async () => $("pd-encerrar-confirmar").click());
    expect(axios.post).toHaveBeenCalledWith("/api/nutrition/periodizacao/encerrar");
  } finally { await act(async () => root.unmount()); }
});

test("versão compacta só aparece com a fase em andamento", async () => {
  const ativa = await montar({liberado: true, periodizacao: ATIVA, semana_atual: 2}, {compacto: true});
  expect(ativa.$("pd-compacto").textContent).toContain("semana 2 de 4");
  await act(async () => ativa.root.unmount());
  const nada = await montar({liberado: true, periodizacao: null}, {compacto: true});
  expect(nada.host.innerHTML).toBe("");
  await act(async () => nada.root.unmount());
});
