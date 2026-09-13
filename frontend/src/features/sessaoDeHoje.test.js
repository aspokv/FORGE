import {linhasDaSessao,idsDaSessao,quantosComHistorico,cargaEmTexto,dataCurta} from "./sessaoDeHoje";

const catalogo=[{id:"supino",name:"Supino reto"},{id:"remada",name:"Remada curvada"},{id:"rosca",name:"Rosca direta"}];
const exercicios=[{exercise_id:"supino",sets:4,reps:"6-8"},{exercise_id:"remada",sets:3,reps:"10"},{exercise_id:"rosca",sets:3,reps:"12"}];
const desempenhos={supino:{weight:80,reps:8,date:"2026-09-03",sets:4},remada:{weight:100,reps:10,date:"2026-09-03",sets:3}};

describe("linhasDaSessao",()=>{
  test("junta o prescrito de hoje com o levantado da ultima vez",()=>{
    const [primeira]=linhasDaSessao({exercicios,catalogo,desempenhos});
    expect(primeira).toEqual({id:"supino",nome:"Supino reto",prescrito:{series:4,reps:"6-8"},carga:"80",reps:8,data:"03/09",estreia:false});
  });

  // Omitir o exercicio sem historico faria a lista ficar menor que o treino, e a pessoa
  // pensaria que faltou exercicio.
  test("exercicio sem historico entra como estreia, nao some",()=>{
    const linhas=linhasDaSessao({exercicios,catalogo,desempenhos});
    expect(linhas).toHaveLength(3);
    const rosca=linhas[2];
    expect(rosca.estreia).toBe(true);
    expect(rosca.carga).toBeNull();
    expect(rosca.data).toBe("");
  });

  test("sem catalogo mostra o id em vez de deixar a linha em branco",()=>{
    expect(linhasDaSessao({exercicios,catalogo:[],desempenhos})[0].nome).toBe("supino");
  });

  test("item sem exercise_id e descartado",()=>{
    const linhas=linhasDaSessao({exercicios:[{sets:3},...exercicios],catalogo,desempenhos});
    expect(linhas).toHaveLength(3);
  });

  test("sem nada devolve lista vazia em vez de quebrar",()=>{
    expect(linhasDaSessao()).toEqual([]);
    expect(linhasDaSessao({exercicios:undefined})).toEqual([]);
  });
});

describe("idsDaSessao",()=>{
  test("lista os ids na ordem do treino",()=>{
    expect(idsDaSessao(exercicios)).toEqual(["supino","remada","rosca"]);
  });

  // Bi-set ou segunda passagem mais leve repetem o id; pedir duas vezes so gasta banda.
  test("nao repete id que aparece duas vezes na sessao",()=>{
    expect(idsDaSessao([{exercise_id:"supino"},{exercise_id:"remada"},{exercise_id:"supino"}]))
      .toEqual(["supino","remada"]);
  });

  test("sem exercicios devolve vazio",()=>{
    expect(idsDaSessao()).toEqual([]);
  });
});

describe("quantosComHistorico",()=>{
  test("conta so os que tem o que superar",()=>{
    expect(quantosComHistorico(linhasDaSessao({exercicios,catalogo,desempenhos}))).toBe(2);
  });

  test("treino inteiramente novo nao promete superacao",()=>{
    expect(quantosComHistorico(linhasDaSessao({exercicios,catalogo,desempenhos:{}}))).toBe(0);
  });
});

describe("formatacao",()=>{
  test("carga inteira nao ganha casa decimal",()=>{
    expect(cargaEmTexto(80)).toBe("80");
  });

  test("carga quebrada usa virgula",()=>{
    expect(cargaEmTexto(62.5)).toBe("62,5");
  });

  test("peso do corpo nao vira 0 kg na tela",()=>{
    expect(cargaEmTexto(0)).toBeNull();
    expect(cargaEmTexto(null)).toBeNull();
  });

  test("a data curta situa sem poluir com o ano",()=>{
    expect(dataCurta("2026-09-03")).toBe("03/09");
    expect(dataCurta("2026-09-03T10:00:00")).toBe("03/09");
    expect(dataCurta("")).toBe("");
  });
});
