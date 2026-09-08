import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";

describe("compact workout preview preserves content", () => {
  test.each([0, 6, 12])("keeps every exercise for a session with %i entries", count => {
    const items = Array.from({length: count}, (_, i) => ({
      exercise_id: `exercise-${i}`, name: `Exercício completo com nome longo ${i}`,
      sets: 3, reps: "8–12", rir: 2,
    }));
    const html = renderToStaticMarkup(<ReferenceWorkoutPreview
      db={{exercises: [], program: {}}}
      activeSession={{label: "Treino completo", duration: "70 min", focus: ["Quadríceps", "Glúteos", "Posteriores"]}}
      items={items} onStart={() => {}} onLibrary={() => {}}
    />);
    const doc = new DOMParser().parseFromString(html, "text/html");
    expect(doc.querySelectorAll("article")).toHaveLength(count);
    items.forEach((item, i) => {
      const row = doc.querySelectorAll("article")[i];
      expect(row.textContent).toContain(item.name);
      expect(row.textContent).toContain("3 × 8–12");
      expect(row.textContent).toContain("RIR 2");
      expect(row.querySelector('[role="img"]')).not.toBeNull();
    });
    expect(doc.querySelector('[aria-label="FORGE, marca original com chama"]')).not.toBeNull();
    ["Treino completo", "70 min", "Quadríceps", "Glúteos", "Posteriores", "Mobilidade e ativação", "8 min", "Iniciar sessão"]
      .forEach(text => expect(doc.body.textContent).toContain(text));
  });
});
