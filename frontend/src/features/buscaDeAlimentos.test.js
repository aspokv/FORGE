import {normalizar,distancia,tolerancia,casaExato,casaAproximado,buscarNoCatalogo} from "./buscaDeAlimentos";

const catalogo=[
  {id:"alb",name:"Albumina (clara de ovo desidratada)",aliases:["albumina","clara em po"]},
  {id:"arr",name:"Arroz branco cozido",aliases:["arroz","arroz branco"]},
  {id:"ban",name:"Banana prata",aliases:["banana"]},
  {id:"mac",name:"Maçã com casca",aliases:["maca","maçã"]},
  {id:"mal",name:"Maltodextrina",aliases:["maltodextrina","malto"]},
  {id:"uva",name:"Uva itália",aliases:["uva"]},
  {id:"ovo",name:"Ovo de galinha cozido",aliases:["ovo","ovo cozido"]},
];

describe("normalizar",()=>{
  test("tira acento e caixa, para 'Maçã' e 'maca' serem a mesma coisa",()=>{
    expect(normalizar("Maçã")).toBe("maca");
    expect(normalizar("  ALBUMINA  ")).toBe("albumina");
  });
});

describe("distancia",()=>{
  test("palavra igual custa zero",()=>{
    expect(distancia("albumina","albumina")).toBe(0);
  });

  // A razao de ser Damerau e nao Levenshtein: trocar duas letras de lugar e o erro mais
  // comum de quem digita rapido, e no Levenshtein puro ele custa o dobro.
  test("letras trocadas de lugar custam um, nao dois",()=>{
    expect(distancia("ovo","voo",2)).toBe(1);
    expect(distancia("arroz","arorz",2)).toBe(1);
  });

  test("o caso que originou tudo: abulmina e albumina",()=>{
    expect(distancia("abulmina","albumina",2)).toBeLessThanOrEqual(2);
  });

  test("palavras sem parentesco estouram o limite",()=>{
    expect(distancia("banana","albumina",2)).toBeGreaterThan(2);
  });

  test("o corte devolve limite+1 em vez de gastar a matriz",()=>{
    expect(distancia("a","abcdefghij",2)).toBe(3);
  });
});

describe("tolerancia",()=>{
  // Com tres letras, distancia 1 ligaria "uva" a "ova", "iva" e meio catalogo.
  test("palavra curta nao ganha tolerancia",()=>{
    expect(tolerancia("uva")).toBe(0);
    expect(tolerancia("ovo")).toBe(0);
  });

  test("palavra media tolera um erro",()=>{
    expect(tolerancia("arroz")).toBe(1);
  });

  test("palavra longa tolera dois",()=>{
    expect(tolerancia("albumina")).toBe(2);
    expect(tolerancia("maltodextrina")).toBe(2);
  });
});

describe("casaExato",()=>{
  test("acha pelo nome e pelo apelido",()=>{
    expect(casaExato(catalogo[0],"albumina")).toBe(true);
    expect(casaExato(catalogo[0],"clara")).toBe(true);
  });

  test("todos os termos precisam aparecer",()=>{
    expect(casaExato(catalogo[1],"arroz branco")).toBe(true);
    expect(casaExato(catalogo[1],"arroz integral")).toBe(false);
  });

  test("erro de digitacao nao passa no exato",()=>{
    expect(casaExato(catalogo[0],"abulmina")).toBe(false);
  });

  test("busca vazia nao filtra nada",()=>{
    expect(casaExato(catalogo[0],"")).toBe(true);
  });
});

describe("casaAproximado",()=>{
  test("aceita o erro que o atleta cometeu",()=>{
    expect(casaAproximado(catalogo[0],"abulmina")).toBe(true);
  });

  test("aceita letra faltando e letra sobrando",()=>{
    expect(casaAproximado(catalogo[4],"maltodextrna")).toBe(true);
    expect(casaAproximado(catalogo[4],"maltodextrinna")).toBe(true);
  });

  test("nao liga alimentos que nao tem nada a ver",()=>{
    expect(casaAproximado(catalogo[2],"albumina")).toBe(false);
    expect(casaAproximado(catalogo[0],"banana")).toBe(false);
  });

  // Uma palavra bem maior que o termo nao e erro de digitacao, e outra palavra.
  test("nao casa termo curto com palavra comprida",()=>{
    expect(casaAproximado(catalogo[4],"mal")).toBe(true); // substring, legitimo
    expect(casaAproximado(catalogo[0],"ovo")).toBe(true); // "ovo" esta no nome
    expect(casaAproximado(catalogo[5],"uvaitalianas")).toBe(false);
  });
});

describe("buscarNoCatalogo",()=>{
  test("com acerto exato, so o exato aparece",()=>{
    const r=buscarNoCatalogo(catalogo,"arroz");
    expect(r.aproximado).toBe(false);
    expect(r.itens.map(f=>f.id)).toEqual(["arr"]);
  });

  /*
   * A regra que protege a precisao: enquanto houver resultado exato, a rede fica fechada.
   * Se ela abrisse sempre, "arroz" traria "arroz" e vizinhos parecidos na mesma lista.
   */
  test("a rede so abre quando o exato vem vazio",()=>{
    const r=buscarNoCatalogo(catalogo,"abulmina");
    expect(r.aproximado).toBe(true);
    expect(r.itens.map(f=>f.id)).toEqual(["alb"]);
  });

  test("digitacao certa continua encontrando",()=>{
    expect(buscarNoCatalogo(catalogo,"albumina").itens.map(f=>f.id)).toEqual(["alb"]);
    expect(buscarNoCatalogo(catalogo,"maca").itens.map(f=>f.id)).toEqual(["mac"]);
  });

  test("termo sem nenhum parentesco continua devolvendo vazio",()=>{
    const r=buscarNoCatalogo(catalogo,"xilofone");
    expect(r.itens).toEqual([]);
    expect(r.aproximado).toBe(false);
  });

  // Com o campo vazio o editor lista o catalogo para navegar; devolver vazio aqui apagaria
  // a lista inicial, que e como quem nao sabe o nome exato acha o alimento.
  test("busca vazia devolve o catalogo para navegar",()=>{
    expect(buscarNoCatalogo(catalogo,"").itens).toHaveLength(catalogo.length);
    expect(buscarNoCatalogo(catalogo,"   ").itens).toHaveLength(catalogo.length);
  });

  test("catalogo ausente nao quebra",()=>{
    expect(buscarNoCatalogo(undefined,"arroz").itens).toEqual([]);
    expect(buscarNoCatalogo(undefined,"").itens).toEqual([]);
  });
});
