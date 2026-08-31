import {buildSessionMuscles,normalizeMuscle} from "./MuscleSessionMap";

test("normaliza nomes internos e nomes exibidos",()=>{
  expect(normalizeMuscle("Peitoral superior")).toBe("upper_chest");
  expect(normalizeMuscle("Costas / espessura")).toBe("upper_back");
  expect(normalizeMuscle("Bíceps")).toBe("biceps");
  expect(normalizeMuscle("hamstrings")).toBe("hamstrings");
});

test("mapa usa os exercícios reais e soma séries por músculo",()=>{
  const catalog=[
    {id:"row",primary_muscle:"upper_back"},
    {id:"pulldown",primary_muscle:"lats"},
    {id:"curl",primary_muscle:"biceps"},
  ];
  const load=buildSessionMuscles([
    {exercise_id:"row",sets:3},
    {exercise_id:"pulldown",sets:3},
    {exercise_id:"curl",sets:2},
  ],catalog,["Costas / espessura"]);
  expect(load.upper_back).toBe(3);
  expect(load.lats).toBe(3);
  expect(load.biceps).toBe(2);
  expect(load.quads).toBeUndefined();
});

test("focus serve apenas como fallback quando catálogo não informa o músculo",()=>{
  const load=buildSessionMuscles([{exercise_id:"unknown",sets:3}],[],["Quadríceps","Glúteos"]);
  expect(load.quads).toBe(.75);
  expect(load.glutes).toBe(.75);
});
