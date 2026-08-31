import {buildSessionMuscles,getSessionZone,normalizeMuscle} from "./MuscleSessionMap";

describe("dynamic workout zone map",()=>{
  test("normaliza nomes internos e nomes exibidos",()=>{
    expect(normalizeMuscle("Peitoral superior")).toBe("upper_chest");
    expect(normalizeMuscle("Costas / espessura")).toBe("upper_back");
    expect(normalizeMuscle("Dorsais / largura")).toBe("lats");
    expect(normalizeMuscle("Bíceps")).toBe("biceps");
    expect(normalizeMuscle("Deltóide posterior")).toBe("rear_delts");
    expect(normalizeMuscle("hamstrings")).toBe("hamstrings");
  });

  test("mapa usa exercícios reais e mantém chips detalhados",()=>{
    const catalog=[{id:"row",primary_muscle:"upper_back"},{id:"pulldown",primary_muscle:"lats"},{id:"curl",primary_muscle:"biceps"}];
    const load=buildSessionMuscles([{exercise_id:"row",sets:6},{exercise_id:"pulldown",sets:4},{exercise_id:"curl",sets:3}],catalog);
    expect(load.upper_back).toBe(6);
    expect(load.lats).toBe(4);
    expect(load.biceps).toBe(3);
    expect(getSessionZone(load)).toBe("upper");
  });

  test("sessão de pernas vira INFERIOR",()=>{
    expect(getSessionZone({quads:6,hamstrings:4,glutes:3,calves:3})).toBe("lower");
  });

  test("sessão equilibrada de corpo inteiro vira FULL BODY",()=>{
    expect(getSessionZone({upper_back:4,upper_chest:3,quads:4,hamstrings:3})).toBe("full");
  });

  test("músculos secundários entram com peso menor sem mudar arbitrariamente a zona",()=>{
    const catalog=[{id:"press",muscle:"Peitoral superior",secondary:["Tríceps","Deltóide anterior"]}];
    const load=buildSessionMuscles([{exercise_id:"press",sets:4}],catalog);
    expect(load.upper_chest).toBe(4);
    expect(load.triceps).toBeCloseTo(1.12);
    expect(load.front_delts).toBeCloseTo(1.12);
    expect(getSessionZone(load)).toBe("upper");
  });

  test("focus continua servindo como fallback",()=>{
    const load=buildSessionMuscles([{exercise_id:"unknown",sets:3}],[],["Quadríceps","Glúteos"]);
    expect(load.quads).toBe(.75);
    expect(load.glutes).toBe(.75);
    expect(getSessionZone(load)).toBe("lower");
  });
});
