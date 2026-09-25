import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import LembretePesagem, {motivoDoLembrete} from "./LembretePesagem";

jest.mock("axios", () => ({get: jest.fn(), post: jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT = true;

// 25/09/2026 é sexta-feira.
const SEXTA = new Date(2026, 8, 25, 8, 0);
const SABADO = new Date(2026, 8, 26, 8, 0);
const QUARTA = new Date(2026, 8, 30, 8, 0);

describe("quando o lembrete aparece", () => {
  test("na sexta, até pesar", () => {
    expect(motivoDoLembrete(SEXTA, "2026-09-18")).toBe("sexta");
    expect(motivoDoLembrete(SEXTA, "2026-09-25")).toBeNull();
  });
  test("sexta que passou sem pesagem vira lembrete nos dias seguintes", () => {
    expect(motivoDoLembrete(SABADO, "2026-09-18")).toBe("atrasada");
    expect(motivoDoLembrete(QUARTA, "2026-09-24")).toBe("atrasada");
  });
  test("pesou na sexta (ou depois): some até a próxima", () => {
    expect(motivoDoLembrete(SABADO, "2026-09-25")).toBeNull();
    expect(motivoDoLembrete(QUARTA, "2026-09-27")).toBeNull();
  });
  test("quem nunca pesou também é lembrado", () => {
    expect(motivoDoLembrete(QUARTA, null)).toBe("atrasada");
  });
});

async function montar(hoje, historico) {
  axios.get.mockResolvedValue({data: {history: historico}});
  const host = document.createElement("div");
  document.body.appendChild(host);   // formulario solto nao envia no jsdom
  const root = createRoot(host);
  await act(async () => root.render(<LembretePesagem API="/api" hoje={hoje}/>));
  return {host, root, $: id => host.querySelector(`[data-testid="${id}"]`)};
}

afterEach(() => { jest.clearAllMocks(); document.body.innerHTML = ""; });

test("registrar o peso manda o dia da tela e mostra a confirmação", async () => {
  axios.post.mockResolvedValue({data: {}});
  const {host, root, $} = await montar(SEXTA, [{date: "2026-09-18", weight_kg: 83.4}]);
  try {
    expect(host.textContent).toContain("Hoje é dia de pesagem");
    const campo = $("lembrete-pesagem-peso");
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(campo, "82,9");
      campo.dispatchEvent(new Event("input", {bubbles: true}));
    });
    await act(async () => $("lembrete-pesagem-salvar").click());
    expect(axios.post).toHaveBeenCalledWith("/api/nutrition/weight", {weight_kg: 82.9, date: "2026-09-25"});
    expect($("pesagem-registrada").textContent).toContain("82,9");
  } finally { await act(async () => root.unmount()); }
});

test("já pesou nesta semana: não aparece nada", async () => {
  const {host, root} = await montar(SABADO, [{date: "2026-09-25", weight_kg: 83}]);
  try { expect(host.innerHTML).toBe(""); } finally { await act(async () => root.unmount()); }
});

test("peso absurdo não deixa registrar", async () => {
  const {root, $} = await montar(SEXTA, []);
  try {
    const campo = $("lembrete-pesagem-peso");
    for (const ruim of ["", "8", "900", "abc"]) {
      await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(campo, ruim);
        campo.dispatchEvent(new Event("input", {bubbles: true}));
      });
      expect($("lembrete-pesagem-salvar").disabled).toBe(true);
    }
  } finally { await act(async () => root.unmount()); }
});
