import React, { act } from "react";
import { createRoot } from "react-dom/client";
import Cardio from "./Cardio";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

/**
 * A aba de cardio.
 *
 * O que estes testes prendem, além do óbvio:
 *
 * 1. O campo de calorias é OPCIONAL, e o que é enviado quando ele fica vazio é `null` e
 *    não `0`. Um zero entraria na soma como "fez cardio e gastou nada", que é diferente
 *    de "não sei quanto gastou" — e quem corre na rua não tem painel para ler.
 *
 * 2. A tela diz, na cara, que o número da máquina não vira permissão para comer mais.
 *    Esse é o aviso que separa o FORGE de um contador de calorias, e ele não pode sumir
 *    numa refatoração de layout.
 *
 * 3. O número em destaque é a SEMANA CORRENTE. A média de quatro semanas é o que o
 *    Conselho usa e fica na linha de resumo, escrita como média.
 */

const API = "/api";

const LEITURA = {
  sessoes: 3, minutos: 95, kcal_reported: 780, minutos_na_semana: 35, minutos_por_semana: 48,
  janela_dias: 28, modalidades: ["Esteira"], faz_cardio: true, cabe_mais: true,
};

const SESSOES = [
  { client_token: "t1", date: "2026-09-19", modality: "Esteira", minutes: 35,
    kcal_reported: 310, rpe: 5, note: "Inclinação 8" },
  { client_token: "t2", date: "2026-09-17", modality: "Bike", minutes: 60,
    kcal_reported: 470, rpe: null, note: "" },
];

function clienteFalso(overrides = {}) {
  return {
    get: jest.fn(url => {
      if (url.endsWith("/modalities")) {
        return Promise.resolve({ data: { modalities: ["Caminhada", "Esteira", "Bike"] } });
      }
      return Promise.resolve({ data: { sessoes: SESSOES, leitura: LEITURA, janela_dias: 28 } });
    }),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    ...overrides,
  };
}

const click = node => node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));

function digitar(input, valor) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, "value").set;
  setter.call(input, valor);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("aba de cardio", () => {
  let host, root, cliente;

  const montar = async (c = clienteFalso()) => {
    cliente = c;
    await act(async () => root.render(<Cardio API={API} axiosCliente={cliente} />));
  };
  const ver = id => host.querySelector(`[data-testid="${id}"]`);

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("o número em destaque é a semana corrente, e não a média da janela", async () => {
    // Medido no navegador: com 42 minutos registrados hoje, a média de quatro semanas
    // dava 10 e o número grande dizia "10 min / semana". Parecia que o aplicativo tinha
    // perdido a sessão que a pessoa acabou de salvar.
    await montar();
    expect(ver("cardio-semana-atual").textContent).toContain("35");
    expect(ver("cardio-semana-atual").textContent).not.toContain("48");
  });

  test("a média de quatro semanas continua visível, porque é ela que o Conselho usa", async () => {
    await montar();
    expect(ver("cardio-media-semanal").textContent).toContain("48");
    expect(ver("cardio-resumo").textContent).toContain("95 minutos");
  });

  test("lista o que foi registrado, com o que o painel mostrou", async () => {
    await montar();
    const lista = ver("cardio-lista").textContent;
    expect(lista).toContain("Esteira");
    expect(lista).toContain("35 min");
    expect(lista).toContain("310 kcal");
    expect(lista).toContain("Inclinação 8");
  });

  test("registrar manda o dia, o tempo e as calorias", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    await act(async () => {
      digitar(ver("cardio-minutos"), "42");
      digitar(ver("cardio-kcal"), "388");
    });
    await act(async () => ver("cardio-form").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })));

    const corpo = cliente.post.mock.calls[0][1];
    expect(corpo.minutes).toBe(42);
    expect(corpo.kcal_reported).toBe(388);
    expect(corpo.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // O token é a idempotência: repetir a requisição não pode criar uma segunda sessão.
    expect(corpo.client_token).toMatch(/^cardio-/);
  });

  test("sem calorias manda null, e não zero", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    await act(async () => digitar(ver("cardio-minutos"), "30"));
    await act(async () => ver("cardio-form").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })));

    expect(cliente.post.mock.calls[0][1].kcal_reported).toBeNull();
  });

  test("sem tempo não chama a API e cobra o número", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    await act(async () => ver("cardio-form").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })));

    expect(cliente.post).not.toHaveBeenCalled();
    expect(ver("cardio-erro")).toBeTruthy();
  });

  test("a tela diz que a caloria da máquina não vira comida", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    const aviso = host.querySelector(".cardio-aviso").textContent;
    expect(aviso).toMatch(/não como permissão para comer mais/i);
    expect(aviso).toMatch(/balança/i);
  });

  test("remover um registro chama a rota com o token daquele registro", async () => {
    await montar();
    await act(async () => click(ver("cardio-remover-t2")));
    expect(cliente.delete).toHaveBeenCalledWith(`${API}/cardio/t2`);
  });

  test("sem cardio nenhum a tela explica em vez de mostrar uma lista vazia", async () => {
    await montar(clienteFalso({
      get: jest.fn(url => url.endsWith("/modalities")
        ? Promise.resolve({ data: { modalities: ["Esteira"] } })
        : Promise.resolve({ data: { sessoes: [], leitura: { ...LEITURA, sessoes: 0, minutos: 0, minutos_na_semana: 0, minutos_por_semana: 0 }, janela_dias: 28 } })),
    }));
    expect(ver("cardio-vazio")).toBeTruthy();
    expect(ver("cardio-lista")).toBeNull();
  });

  test("as modalidades vêm do servidor, e não de uma segunda lista na tela", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    const opcoes = [...ver("cardio-modalidade").options].map(o => o.value);
    expect(opcoes).toEqual(["Caminhada", "Esteira", "Bike"]);
  });

  test("não dá para registrar um cardio do futuro", async () => {
    await montar();
    await act(async () => click(ver("cardio-abrir")));
    const hoje = new Date().toISOString().slice(0, 10);
    expect(ver("cardio-data").getAttribute("max")).toBe(hoje);
  });
});
