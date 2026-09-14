import {semanaDaDieta,objetivoDaDieta,numero,textoDosDias} from "./semanaDaDieta";

const dia=(date,kcal,protein_g)=>({date,kcal,protein_g,carbs_g:0,fat_g:0});
const semana=(dias,extra={})=>({days:dias,window_days:7,registered_days:dias.length,
  targets:{goal_calories:2871,protein_g:180},...extra});

describe("objetivoDaDieta",()=>{
  test("reconhece corte pelas palavras que o app usa",()=>{
    expect(objetivoDaDieta("Cutting")).toBe("corte");
    expect(objetivoDaDieta("Emagrecimento")).toBe("corte");
    expect(objetivoDaDieta("Déficit calórico")).toBe("corte");
  });

  test("reconhece ganho, inclusive 'Hipertrofia', que e o que o perfil grava",()=>{
    expect(objetivoDaDieta("Hipertrofia")).toBe("ganho");
    expect(objetivoDaDieta("Bulking")).toBe("ganho");
    expect(objetivoDaDieta("Ganho de massa")).toBe("ganho");
  });

  // Chutar "manutencao" para o desconhecido faria a frase julgar direcao sem base.
  test("objetivo desconhecido vira nulo, e nao manutencao",()=>{
    expect(objetivoDaDieta("")).toBeNull();
    expect(objetivoDaDieta(undefined)).toBeNull();
    expect(objetivoDaDieta("xpto")).toBeNull();
  });
});

describe("semanaDaDieta — a media e por dia REGISTRADO",()=>{
  /*
   * A armadilha central: quem anotou tres dos sete dias nao comeu a menos, esqueceu de
   * anotar. Dividir pelos sete dias da janela inventaria um deficit que nunca existiu.
   */
  test("dia sem registro nao entra no divisor",()=>{
    const r=semanaDaDieta(semana([dia("2026-09-11",3000,180),dia("2026-09-12",3000,180)]));
    expect(r.dias).toBe(2);
    expect(r.kcalPorDia).toBe(3000);
    expect(r.janela).toBe(7);
  });

  test("a contagem de dias anda junto do numero",()=>{
    const r=semanaDaDieta(semana([dia("2026-09-11",3000,180)]));
    expect(textoDosDias(r)).toBe("1 de 7 dias registrados");
  });

  test("semana vazia nao vira zero acusatorio",()=>{
    const r=semanaDaDieta(semana([]));
    expect(r.dias).toBe(0);
    expect(r.frase).toBe("Nenhum dia registrado nos últimos 7 dias.");
    expect(textoDosDias(r)).toBe("nenhum dia registrado");
  });

  test("sem dado nenhum devolve a mesma forma, zerada",()=>{
    const r=semanaDaDieta(undefined);
    expect(r.dias).toBe(0);
    expect(r.kcalPorDia).toBe(0);
    expect(r.metaKcal).toBe(0);
  });

  test("linha sem consumo nenhum e descartada",()=>{
    const r=semanaDaDieta(semana([dia("2026-09-11",3000,180),dia("2026-09-12",0,0)]));
    expect(r.dias).toBe(1);
  });
});

describe("semanaDaDieta — proteina",()=>{
  test("conta os dias em que a proteina ficou no alvo",()=>{
    const r=semanaDaDieta(semana([dia("2026-09-11",2800,185),dia("2026-09-12",2800,120)]));
    expect(r.diasProteinaOk).toBe(1);
  });

  // Proteina acima do alvo nao e falha; e o lado certo de errar.
  test("passar da meta de proteina conta como no alvo",()=>{
    const r=semanaDaDieta(semana([dia("2026-09-11",2800,240)]));
    expect(r.diasProteinaOk).toBe(1);
  });

  test("a frase nomeia quantos dias, quando nem todos bateram",()=>{
    const r=semanaDaDieta(semana([dia("a",2800,185),dia("b",2800,120),dia("c",2800,190)]));
    expect(r.frase).toBe("Proteína no alvo em 2 de 3 dias.");
  });

  test("nenhum dia no alvo e dito sem rodeio",()=>{
    const r=semanaDaDieta(semana([dia("a",2800,90),dia("b",2800,80)]));
    expect(r.frase).toBe("A proteína ficou abaixo da meta em todos os dias registrados.");
  });
});

/*
 * A segunda armadilha: o mesmo desvio calorico muda de sinal conforme o objetivo. Comer
 * abaixo em corte e o plano andando; comer abaixo em ganho e o fracasso.
 */
describe("semanaDaDieta — o objetivo muda o sentido do mesmo numero",()=>{
  const tresDias=(kcal)=>[dia("a",kcal,190),dia("b",kcal,190),dia("c",kcal,190)];

  test("abaixo da meta em corte e progresso",()=>{
    const r=semanaDaDieta(semana(tresDias(2400),{goal:"Cutting"}));
    expect(r.frase).toBe("Proteína em dia e calorias abaixo — o corte está andando.");
  });

  test("o mesmo numero em ganho e falta",()=>{
    const r=semanaDaDieta(semana(tresDias(2400),{goal:"Hipertrofia"}));
    expect(r.frase).toBe("Proteína em dia, mas faltou caloria para o ganho.");
  });

  test("acima da meta em ganho e o esperado",()=>{
    const r=semanaDaDieta(semana(tresDias(3300),{goal:"Hipertrofia"}));
    expect(r.frase).toBe("Proteína em dia e calorias acima — é o que o ganho pede.");
  });

  test("acima da meta em corte e alerta",()=>{
    const r=semanaDaDieta(semana(tresDias(3300),{goal:"Cutting"}));
    expect(r.frase).toBe("Proteína em dia, mas as calorias passaram da meta.");
  });

  test("sem objetivo, descreve sem julgar",()=>{
    const r=semanaDaDieta(semana(tresDias(2400)));
    expect(r.frase).toBe("Proteína em dia, calorias abaixo da meta.");
  });

  test("dentro da margem de 5% nao vira desvio",()=>{
    const r=semanaDaDieta(semana(tresDias(2871),{goal:"Hipertrofia"}));
    expect(r.frase).toBe("Proteína e calorias no lugar.");
  });
});

describe("numero",()=>{
  test("usa separador de milhar brasileiro",()=>{
    expect(numero(2871)).toBe("2.871");
    expect(numero(0)).toBe("0");
  });
});
