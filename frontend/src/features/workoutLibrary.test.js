import { buildLibraryProgram, programPhaseToDraft, templateToSession } from "./WorkoutLibrary";

const makeTemplate = (id, name, duration = 60) => ({
  id,
  name,
  duration,
  demand: "MODERATE",
  focus: ["Peitoral"],
  exercises: [{ exercise_id: "bb-bench-press", sets: 3, reps: "6–8", rir: "1–2", rest: "3 min", load: 0 }],
});

test("converts a library template into the existing custom-program session shape", () => {
  const session = templateToSession(makeTemplate("push-base", "Push Base"), 2);
  expect(session.day).toBe(2);
  expect(session.label).toBe("Push Base");
  expect(session.template_id).toBe("push-base");
  expect(session.exercises[0].exercise_id).toBe("bb-bench-press");
});

test("builds the selected weekly order and average duration for Program Builder", () => {
  const program = buildLibraryProgram([
    makeTemplate("push-base", "Push Base", 60),
    makeTemplate("pull-width", "Pull Largura", 70),
  ]);
  expect(program.sessions.map(item => item.label)).toEqual(["Push Base", "Pull Largura"]);
  expect(program.sessions.map(item => item.day)).toEqual([1, 2]);
  expect(program.session_minutes).toBe(65);
  expect(program.week).toBe("Microciclo da biblioteca");
});

test("converts one selected phase of a complete program into a reviewable draft", () => {
  const phase = {
    id: "phase-2",
    label: "Fase 2 · Cadência",
    weeks: "2, 6 e 10",
    sessions: [
      { label: "Upper A", duration: 60, demand: "MODERATE", focus: ["Tronco"], exercises: makeTemplate("upper", "Upper").exercises },
      { label: "Lower A", duration: 70, demand: "HIGH", focus: ["Pernas"], exercises: makeTemplate("lower", "Lower").exercises },
    ],
  };
  const draft = programPhaseToDraft({ id: "upper-lower", name: "Upper / Lower" }, phase);
  expect(draft.name).toBe("Upper / Lower · Fase 2 · Cadência");
  expect(draft.week).toBe("Fase 2 · Cadência · 2, 6 e 10");
  expect(draft.session_minutes).toBe(65);
  expect(draft.sessions.map(item => item.day)).toEqual([1, 2]);
  expect(draft.sessions[1].label).toBe("Lower A");
  expect(draft.source_program_id).toBe("upper-lower");
});
