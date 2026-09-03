import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import axios from "axios";
import WorkoutLibrary from "./WorkoutLibrary";

jest.mock("axios");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const template = {
  id: "push-pectoral-test",
  category: "push",
  audience: "unisex",
  style: "Especialização",
  level: "Avançado",
  name: "Push Peitoral",
  description: "Sessão de teste",
  demand: "MODERATE",
  duration: 70,
  exercise_count: 1,
  total_sets: 4,
  focus: ["Peitoral superior"],
  exercises: [
    { exercise_id: "incline-db", sets: 4, reps: "6–10", rir: "1", rest: "3 min" },
  ],
};

const catalog = {
  categories: [{ id: "push", label: "Push", subtitle: "Empurrar" }],
  templates: [template],
  program_categories: [],
  programs: [],
};

const program = {
  active_day: 1,
  sessions: [{ day: 1, label: "Treino anterior", exercises: [] }],
};

function click(node) {
  node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

describe("WorkoutLibrary mobile apply interaction", () => {
  let host;
  let root;

  beforeEach(() => {
    jest.clearAllMocks();
    axios.get.mockResolvedValue({ data: catalog });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("tap em Usar como treino atual chama a aplicação da sessão", async () => {
    const onTemplateAdd = jest.fn().mockResolvedValue({ program: { ...program, sessions: [{ day: 1, template_id: template.id }] } });
    const onApplied = jest.fn();

    await act(async () => {
      root.render(
        <WorkoutLibrary
          API="/api"
          exercises={[{ id: "incline-db", name: "Supino inclinado com halteres" }]}
          profile={{}}
          program={program}
          onTemplateAdd={onTemplateAdd}
          onApplied={onApplied}
        />
      );
      await Promise.resolve();
    });

    const card = host.querySelector(`[data-testid="workout-template-${template.id}"]`);
    expect(card).not.toBeNull();

    await act(async () => {
      click(card.querySelector(".library-add"));
    });

    const applyButton = host.querySelector(".library-mobile-apply");
    expect(applyButton).not.toBeNull();
    expect(applyButton.disabled).toBe(false);

    await act(async () => {
      click(applyButton);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(onTemplateAdd).toHaveBeenCalledTimes(1);
    expect(onTemplateAdd).toHaveBeenCalledWith(expect.objectContaining({ id: template.id }));
    expect(onApplied).toHaveBeenCalledTimes(1);
  });

  test("camadas decorativas não podem capturar toques sobre o CTA mobile", () => {
    const css = fs.readFileSync(path.join(__dirname, "..", "index.css"), "utf8");
    expect(css).toMatch(/\.library-card-grid article::before[^{}]*\{[^{}]*pointer-events:none/);
    expect(css).toMatch(/\.library-mobile-session-preview\{[^{}]*position:relative;z-index:2;pointer-events:auto/);
    expect(css).toMatch(/\.library-mobile-apply\{[^{}]*position:relative;z-index:3;pointer-events:auto;touch-action:manipulation/);
  });

  test("Masculino abre programas e filtra sem exibir a curadoria feminina", async () => {
    const makeProgram = (id, audience_type, name) => ({ id, audience_type, name,
      category: "abc", categories: ["abc"], description: "Ficha", level: "Avançado",
      days_per_week: 3, duration_weeks: 0, phase_count: 1, phases: [] });
    axios.get.mockResolvedValue({ data: { ...catalog,
      program_categories: [{ id: "abc", label: "ABC" }], programs: [
        makeProgram("male-test", "male", "ABC Masculino Teste"),
        makeProgram("female-test", "female", "ABC Feminino Teste"),
      ] } });
    await act(async () => {
      root.render(<WorkoutLibrary API="/api" profile={{}} exercises={[]} program={program}/>);
      await Promise.resolve();
    });
    await act(async () => click(host.querySelector('[data-testid="library-audience-male"]')));
    expect(host.textContent).toContain("ABC Masculino Teste");
    expect(host.textContent).not.toContain("ABC Feminino Teste");
    expect(host.textContent).toContain("3 sessões");
    expect(host.textContent).toContain("Duração a definir");
  });
});
