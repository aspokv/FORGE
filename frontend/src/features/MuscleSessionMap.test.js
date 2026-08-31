import {buildSessionMuscles,normalizeMuscle} from "./MuscleSessionMap";

describe("dynamic workout muscle map",()=>{
  test("normaliza nomes internos e nomes exibidos",()=>{
    expect(normalizeMuscle("Peitoral superior")).toBe("upper_chest");
    expect(normalizeMuscle("Costas / espessura")).toBe("upper_back");
    expect(normalizeMuscle("Dorsais / largura")).toBe("lats");
    expect(normalizeMuscle("Bíceps")).toBe("biceps");
    expect(normalizeMuscle("Deltóide posterior")).toBe("rear_delts");
    expect(normalizeMuscle("hamstrings")).toBe("hamstrings");
  });

  test("mapa usa os exercícios reais e soma séries por músculo",()=>{
    const catalog=[
      {id:"row",primary_muscle:"upper_back"},
      {id:"pulldown",primary_muscle:"lats"},
      {id:"curl",primary_muscle:"biceps"},
      {id:"rear-delt",primary_muscle:"rear_delts"},
    ];
    const load=buildSessionMuscles([
      {exercise_id:"row",sets:6},
      {exercise_id:"pulldown",sets:4},
      {exercise_id:"curl",sets:3},
      {exercise_id:"rear-delt",sets:2},
    ],catalog,["Costas / espessura"]);
    expect(load.upper_back).toBe(6);
    expect(load.lats).toBe(4);
    expect(load.biceps).toBe(3);
    expect(load.rear_delts).toBe(2);
    expect(load.quads).toBeUndefined();
  });

  test("músculos secundários entram com peso visual menor",()=>{
    const catalog=[{id:"press",muscle:"Peitoral superior",secondary:["Tríceps","Deltóide anterior"]}];
    const load=buildSessionMuscles([{exercise_id:"press",sets:4}],catalog);
    expect(load.upper_chest).toBe(4);
    expect(load.triceps).toBeCloseTo(1.12);
    expect(load.front_delts).toBeCloseTo(1.12);
  });

  test("focus serve apenas como fallback quando catálogo não informa o músculo",()=>{
    const load=buildSessionMuscles([{exercise_id:"unknown",sets:3}],[],["Quadríceps","Glúteos"]);
    expect(load.quads).toBe(.75);
    expect(load.glutes).toBe(.75);
  });
});
