import {resumoDaEvolucao,textoDoSalto,exercicioPadrao,opcoesDoSeletor} from "./evolucaoResumo";

const calendario=(treinados,total=28)=>Array.from({length:total},(_,i)=>({date:`d${i}`,trained:i<treinados}));
const marca=(exercise,weight,delta)=>({exercise,weight,delta_weight:delta});

describe("resumoDaEvolucao",()=>{
  test("conta treinos e exercicios que subiram de carga",()=>{
    const r=resumoDaEvolucao({adherence_calendar:calendario(14),prs:[marca("Puxada",137,82),marca("Remada",100,66),marca("Rosca",30,0)]});
    expect(r.treinos).toBe(14);
    expect(r.dias).toBe(28);
    expect(r.evolucoes).toBe(2);
  });

  test("o maior salto traz o exercicio que o produziu",()=>{
    const r=resumoDaEvolucao({adherence_calendar:calendario(10),prs:[marca("Puxada",137,82),marca("Remada",100,66)]});
    expect(r.salto).toEqual({exercicio:"Puxada",kg:82});
  });

  // Marca sem carga nao e marca: entra no catalogo mas nao conta como evolucao.
  test("ignora marcas sem carga",()=>{
    const r=resumoDaEvolucao({adherence_calendar:calendario(5),prs:[marca("Abdominal",0,10)]});
    expect(r.evolucoes).toBe(0);
    expect(r.salto).toBeNull();
  });

  test("sem analytics devolve a mesma forma, zerada",()=>{
    const r=resumoDaEvolucao(undefined);
    expect(r).toEqual({treinos:0,dias:28,evolucoes:0,salto:null,frase:"Sem treinos registrados nas últimas 4 semanas."});
  });

  describe("a frase separa constancia de carga",()=>{
    test("treinou muito e subiu carga",()=>{
      expect(resumoDaEvolucao({adherence_calendar:calendario(14),prs:[marca("Puxada",137,82)]}).frase)
        .toBe("Você está subindo carga com constância.");
    });

    // Treinar muito sem subir carga e diagnostico util, nao fracasso a esconder.
    test("treinou muito sem subir carga",()=>{
      expect(resumoDaEvolucao({adherence_calendar:calendario(14),prs:[marca("Puxada",137,0)]}).frase)
        .toBe("Constância firme. As cargas ainda não subiram.");
    });

    test("subiu carga treinando pouco",()=>{
      expect(resumoDaEvolucao({adherence_calendar:calendario(3),prs:[marca("Puxada",137,82)]}).frase)
        .toBe("Você está subindo carga.");
    });

    test("poucos treinos e nenhuma carga nova",()=>{
      expect(resumoDaEvolucao({adherence_calendar:calendario(3),prs:[marca("Puxada",137,0)]}).frase)
        .toBe("Poucos treinos no período.");
    });
  });
});

describe("textoDoSalto",()=>{
  test("mostra o sinal, porque o numero sozinho nao diz que subiu",()=>{
    expect(textoDoSalto({exercicio:"Puxada",kg:82})).toBe("+82 kg");
  });

  test("quebra decimal usa virgula",()=>{
    expect(textoDoSalto({exercicio:"Puxada",kg:2.5})).toBe("+2,5 kg");
  });

  test("sem salto nao inventa texto",()=>{
    expect(textoDoSalto(null)).toBeNull();
    expect(textoDoSalto({exercicio:"Puxada",kg:0})).toBeNull();
  });
});

describe("exercicioPadrao",()=>{
  const opcoes=[{id:"a",name:"Cadeira extensora"},{id:"b",name:"Puxada alta na polia"},{id:"c",name:"Remada curvada"}];
  const milestones=[{title:"Puxada alta na polia"},{title:"Remada curvada"}];

  // O defeito que isto corrige: cair no primeiro alfabetico faz quem puxa 137 kg abrir a
  // tela vendo cadeira extensora de 30 kg.
  test("sem escolha nem favorito, abre no recorde mais recente",()=>{
    expect(exercicioPadrao({milestones,opcoes})).toBe("b");
  });

  test("a escolha da pessoa vence tudo",()=>{
    expect(exercicioPadrao({escolhido:"c",favorito:"a",milestones,opcoes})).toBe("c");
  });

  test("o favorito vence o recorde recente",()=>{
    expect(exercicioPadrao({favorito:"a",milestones,opcoes})).toBe("a");
  });

  test("escolha que nao existe mais no catalogo e descartada",()=>{
    expect(exercicioPadrao({escolhido:"sumiu",milestones,opcoes})).toBe("b");
  });

  test("sem marco nenhum cai no primeiro da lista",()=>{
    expect(exercicioPadrao({milestones:[],opcoes})).toBe("a");
  });

  test("sem catalogo devolve vazio em vez de quebrar",()=>{
    expect(exercicioPadrao({milestones,opcoes:[]})).toBe("");
  });
});

describe("opcoesDoSeletor",()=>{
  const opcoes=[{id:"a",name:"Cadeira extensora"},{id:"b",name:"Puxada alta na polia"},{id:"c",name:"Agachamento"}];

  test("separa os exercicios treinados do resto do catalogo",()=>{
    const {seus,demais}=opcoesDoSeletor(opcoes,[{title:"Puxada alta na polia"}],[{exercise:"Cadeira extensora"}]);
    expect(seus.map(e=>e.id)).toEqual(["a","b"]);
    expect(demais.map(e=>e.id)).toEqual(["c"]);
  });

  test("sem historico nenhum, tudo continua no catalogo",()=>{
    const {seus,demais}=opcoesDoSeletor(opcoes,[],[]);
    expect(seus).toEqual([]);
    expect(demais).toHaveLength(3);
  });

  // Nada pode sumir do seletor: a soma dos dois grupos e sempre o catalogo inteiro.
  test("nenhum exercicio se perde na separacao",()=>{
    const {seus,demais}=opcoesDoSeletor(opcoes,[{title:"Agachamento"}],[]);
    expect(seus.length+demais.length).toBe(opcoes.length);
  });
});
