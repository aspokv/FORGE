import {semanaDaDieta,objetivoDaDieta,numero,textoDosDias,totaisDaSemana,larguraDaBarra,textoDaDiferenca,semanaDoCalendario,diasDecorridos,dataLocal} from "./semanaDaDieta";

const dia=(date,kcal,protein_g)=>({date,kcal,protein_g,carbs_g:0,fat_g:0});
const semana=(dias,extra={})=>({days:dias,window_days:7,registered_days:dias.length,
  targets:{goal_calories:2871,protein_g:180,carbs_g:400,fat_g:70},...extra});
const diaCheio=(date,kcal,p,c,g)=>({date,kcal,protein_g:p,carbs_g:c,fat_g:g});

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

describe("totaisDaSemana",()=>{
  /*
   * A meta da semana e a meta diaria vezes os dias REGISTRADOS. Multiplicar pelos sete da
   * janela recriaria o deficit falso que este modulo existe para evitar.
   */
  /*
   * A meta e o ORCAMENTO da semana inteira: sete dias. Ficar atras na quarta e o esperado,
   * porque a semana ainda nao acabou. A protecao contra o dia esquecido mora na media, em
   * `semanaDaDieta`, que e outra pergunta.
   */
  test("a meta e a semana inteira, nao os dias registrados",()=>{
    const linhas=totaisDaSemana(semana([diaCheio("a",2871,180,400,70),diaCheio("b",2871,180,400,70)]));
    const kcal=linhas.find(l=>l.chave==="kcal");
    expect(kcal.meta).toBe(2871*7);
    expect(kcal.consumido).toBe(2871*2);
    expect(kcal.fracao).toBeCloseTo(2/7,3);
  });

  test("devolve os quatro macros, na ordem de leitura",()=>{
    const linhas=totaisDaSemana(semana([diaCheio("a",2871,180,400,70)]));
    expect(linhas.map(l=>l.chave)).toEqual(["kcal","protein_g","carbs_g","fat_g"]);
    expect(linhas.map(l=>l.nome)).toEqual(["Calorias","Proteína","Carboidrato","Gordura"]);
  });

  test("metade da meta da semana da metade da barra",()=>{
    const dias=Array.from({length:7},(_,i)=>diaCheio(String(i),1435,90,200,35));
    expect(totaisDaSemana(semana(dias)).find(l=>l.chave==="protein_g").fracao).toBeCloseTo(.5,2);
  });

  test("comer acima passa de 1, e isso e informacao",()=>{
    const dias=Array.from({length:7},(_,i)=>diaCheio(String(i),4000,260,400,70));
    const linhas=totaisDaSemana(semana(dias));
    expect(linhas.find(l=>l.chave==="protein_g").fracao).toBeGreaterThan(1);
    expect(linhas.find(l=>l.chave==="protein_g").diferenca).toBeGreaterThan(0);
  });

  test("sem dia registrado a meta continua existindo, so o consumo e zero",()=>{
    const linhas=totaisDaSemana(semana([]));
    expect(linhas.find(l=>l.chave==="kcal").meta).toBe(2871*7);
    expect(linhas.every(l=>l.consumido===0&&l.fracao===0)).toBe(true);
  });

  test("sem nada devolve as quatro linhas zeradas em vez de quebrar",()=>{
    expect(totaisDaSemana(undefined)).toHaveLength(4);
  });
});

describe("larguraDaBarra",()=>{
  test("traduz a fracao em porcentagem",()=>{
    expect(larguraDaBarra(.5)).toBe("50%");
    expect(larguraDaBarra(0)).toBe("0%");
  });

  // Barra passando de 100% vazaria da caixa; o numero ao lado e que conta a verdade.
  test("para em 100% mesmo quando a pessoa comeu acima",()=>{
    expect(larguraDaBarra(1.8)).toBe("100%");
  });

  test("valor invalido nao vira NaN%",()=>{
    expect(larguraDaBarra(undefined)).toBe("0%");
  });
});

describe("textoDaDiferenca",()=>{
  /*
   * Na quarta-feira "faltam 14.000 kcal" soa como divida; e o que ainda ha para comer ate
   * domingo. Depois de domingo, ai sim faltou.
   */
  test("com a semana correndo, o que falta ainda e seu para comer",()=>{
    expect(textoDaDiferenca({consumido:1000,meta:2000,diferenca:-1000,unidade:"kcal"},false)).toBe("restam 1.000 kcal");
  });

  test("com a semana fechada, o que falta virou falta",()=>{
    expect(textoDaDiferenca({consumido:1000,meta:2000,diferenca:-1000,unidade:"kcal"},true)).toBe("faltaram 1.000 kcal");
  });

  test("diz quanto passou",()=>{
    expect(textoDaDiferenca({consumido:3000,meta:2000,diferenca:1000,unidade:"kcal"},false)).toBe("passou 1.000 kcal");
    expect(textoDaDiferenca({consumido:3000,meta:2000,diferenca:1000,unidade:"kcal"},true)).toBe("passou 1.000 kcal");
  });

  test("dentro da margem de 5% nao vira cobranca",()=>{
    expect(textoDaDiferenca({consumido:2020,meta:2000,diferenca:20,unidade:"kcal"})).toBe("na meta");
  });

  test("sem meta nao inventa texto",()=>{
    expect(textoDaDiferenca({consumido:0,meta:0,diferenca:0,unidade:"g"})).toBe("");
  });
});

describe("semanaDoCalendario",()=>{
  test("quarta-feira aponta para a segunda daquela semana",()=>{
    const r=semanaDoCalendario(new Date(2026,8,16));           // 16/09/2026, quarta
    expect(r.inicio).toBe("2026-09-14");
    expect(r.fim).toBe("2026-09-20");
  });

  test("a propria segunda e o inicio",()=>{
    expect(semanaDoCalendario(new Date(2026,8,14)).inicio).toBe("2026-09-14");
  });

  /*
   * `getDay()` devolve 0 para domingo. Sem tratar, domingo recuaria zero dia e a semana
   * comecaria no proprio domingo — quebrando a unica regra que o atleta pediu.
   */
  test("domingo fecha a semana que comecou na segunda anterior",()=>{
    const r=semanaDoCalendario(new Date(2026,8,20));           // 20/09/2026, domingo
    expect(r.inicio).toBe("2026-09-14");
    expect(r.fim).toBe("2026-09-20");
  });

  test("a semana atravessa a virada do mes sem se perder",()=>{
    const r=semanaDoCalendario(new Date(2026,9,1));            // 01/10/2026, quinta
    expect(r.inicio).toBe("2026-09-28");
    expect(r.fim).toBe("2026-10-04");
  });

  test("a virada do ano tambem",()=>{
    const r=semanaDoCalendario(new Date(2027,0,1));            // 01/01/2027, sexta
    expect(r.inicio).toBe("2026-12-28");
    expect(r.fim).toBe("2027-01-03");
  });

  // Se usasse UTC, as 21h no Brasil ja seria o dia seguinte e a semana viraria antes.
  test("usa a data local, e nao UTC",()=>{
    const tardeDeDomingo=new Date(2026,8,20,21,30);
    expect(semanaDoCalendario(tardeDeDomingo).hoje).toBe("2026-09-20");
  });
});

describe("diasDecorridos",()=>{
  test("segunda e o primeiro dia, domingo o setimo",()=>{
    expect(diasDecorridos(new Date(2026,8,14))).toBe(1);
    expect(diasDecorridos(new Date(2026,8,20))).toBe(7);
  });
});

describe("dataLocal",()=>{
  test("formata no mesmo padrao que o diario do dia grava",()=>{
    expect(dataLocal(new Date(2026,8,4))).toBe("2026-09-04");
  });
});
