import React, { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { CardioFinisher, cardioRecommendation } from "./CardioFinisher";

jest.mock("axios");
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const click = node => node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));

describe("CardioFinisher", () => {
  let host;
  let root;

  beforeEach(() => {
    jest.clearAllMocks();
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("sessão de pernas recebe finalização leve por padrão", () => {
    expect(cardioRecommendation("Legs Quadríceps")).toMatchObject({
      kind: "recovery",
      modality: "Bike",
      minutes: 10,
      rpe: 3,
    });
  });

  test("cardio é opcional e registra tempo, modalidade e RPE", async () => {
    axios.post.mockResolvedValue({ data: { completed: true } });
    await act(async () => {
      root.render(<CardioFinisher api="/api" sessionLabel="Push 1" />);
    });

    expect(host.textContent).toContain("CARDIO / FINALIZAÇÃO");
    expect(host.textContent).toContain("Opcional. Não bloqueia a conclusão do treino.");

    await act(async () => {
      click(host.querySelector('[data-testid="cardio-save"]'));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post).toHaveBeenCalledWith("/api/cardio", expect.objectContaining({
      kind: "moderate",
      modality: "Caminhada",
      minutes: 15,
      rpe: 4,
      session_label: "Push 1",
      completed: true,
    }));
    expect(host.textContent).toContain("Cardio registrado");
  });
});
