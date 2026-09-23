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

/*
 * A ORDEM do resultado, que e o que a pessoa toca.
 *
 * A lista saia na ordem do catalogo, que nao tem relacao nenhuma com o que foi digitado.
 * Medido contra o catalogo real de 314 alimentos, "arroz" devolvia "Biscoito de arroz",
 * "Marmita de frango, arroz e brocolis" e "Proteina vegetal" — sem arroz nos tres
 * primeiros. "leite" nao trazia leite. "frango" trazia coxa, asa e strogonoff antes do
 * peito. Achar o alimento nao serve para nada se ele estiver em decimo numa coluna de
 * celular.
 *
 * Cada caso abaixo e um que estava errado de verdade.
 */
describe("a ordem do resultado",()=>{
  // `dimensionavel` e o campo que separa alimento-base de prato pronto e de marca. Vem do
  // endpoint do catalogo; a tela nao tem como deduzir isso do id, porque as marcas de
  // suplemento tambem nao levam o prefixo `diary-`.
  const real=[
    {id:"rice-white",name:"Arroz branco cozido",aliases:["arroz","arroz branco"],dimensionavel:true},
    {id:"diary-rice-cracker",name:"Biscoito de arroz",aliases:["biscoito de arroz"],dimensionavel:false},
    {id:"diary-marmita",name:"Marmita de frango, arroz e brócolis",aliases:["marmita"],dimensionavel:false},
    {id:"milk-whole",name:"Leite integral",aliases:["leite"],dimensionavel:true},
    {id:"diary-milk-powder",name:"Leite em pó integral",aliases:["leite em po"],dimensionavel:false},
    {id:"chicken-breast",name:"Peito de frango grelhado",aliases:["frango","peito de frango"],dimensionavel:true},
    {id:"diary-chicken-parm",name:"Frango à parmegiana",aliases:["parmegiana"],dimensionavel:false},
    {id:"banana",name:"Banana",aliases:["banana"],dimensionavel:true},
    {id:"diary-banana-prata",name:"Banana prata",aliases:["banana prata"],dimensionavel:false},
    {id:"tomato",name:"Tomate",aliases:["tomate"],dimensionavel:true},
    {id:"diary-tomato-sauce",name:"Molho de tomate",aliases:["molho de tomate"],dimensionavel:false},
    {id:"pumpkin",name:"Abóbora cozida",aliases:["abobora","moranga","jerimum"],dimensionavel:true},
    {id:"diary-pumpkin-puree",name:"Purê de abóbora",aliases:["pure de moranga"],dimensionavel:false},
    {id:"diary-alcatra",name:"Alcatra grelhada",aliases:["alcatra"],dimensionavel:false},
    {id:"beef-lean",name:"Carne bovina grelhada (patinho)",aliases:["patinho","alcatra"],dimensionavel:true},
    {id:"diary-albumina",name:"Albumina (clara de ovo desidratada)",aliases:["albumina"],dimensionavel:false},
    {id:"diary-albumina-marca",name:"Albumina — Naturovos",aliases:["albumina naturovos"],dimensionavel:false},
  ];
  // Cada caso roda com o catalogo NA ORDEM e INVERTIDO. Sem isso o teste passa de graca:
  // se o alimento certo estiver listado antes do errado, a ordem de chegada ja da a resposta
  // e a ordenacao nunca e exercitada. No catalogo real de producao "Biscoito de arroz" vem
  // ANTES de "Arroz branco cozido", e era por isso que a tela devolvia biscoito.
  const primeiros=termo=>[buscarNoCatalogo(real,termo).itens[0]?.name,
                          buscarNoCatalogo([...real].reverse(),termo).itens[0]?.name];

  test.each([
    // O termo e o nome da coisa, nao uma palavra que aparece nela.
    ["arroz","Arroz branco cozido"],
    ["leite","Leite integral"],
    ["tomate","Tomate"],
    // Alimento-base antes de prato pronto: quem digita "frango" quer peito de frango.
    ["frango","Peito de frango grelhado"],
    // O nome exato ganha da variedade: quem digita "banana" nao esta escolhendo cultivar.
    ["banana","Banana"],
    // O caso que originou tudo: o Nicolas procurou "moranga" e nao achava nada.
    ["moranga","Abóbora cozida"],
    // O nome vale mais que o apelido — mesmo quando o outro e dimensionavel.
    ["alcatra","Alcatra grelhada"],
    // O generico antes da marca, apesar de a marca ter nome mais curto.
    ["albumina","Albumina (clara de ovo desidratada)"],
  ])("'%s' devolve '%s' em primeiro, em qualquer ordem de catalogo",(termo,esperado)=>{
    expect(primeiros(termo)).toEqual([esperado,esperado]);
  });

  // Sem termo digitado nao existe "mais relevante": a lista inicial fica na ordem do
  // catalogo, que e como a pessoa navega procurando algo que nao sabe nomear.
  test("a lista sem busca nao e reordenada",()=>{
    expect(buscarNoCatalogo(real,"").itens.map(f=>f.id)).toEqual(real.map(f=>f.id));
  });

  // Catalogo antigo em cache no navegador nao traz `dimensionavel`. A ordem piora, mas a
  // busca nao pode quebrar nem devolver lista vazia.
  test("catalogo sem dimensionavel continua funcionando",()=>{
    const sem=real.map(({dimensionavel,...resto})=>resto);
    expect(buscarNoCatalogo(sem,"arroz").itens[0].name).toBe("Arroz branco cozido");
    expect(buscarNoCatalogo(sem,"tomate").itens[0].name).toBe("Tomate");
  });

  // Empate completo cai no alfabeto, e nao na ordem de chegada: a lista nao pode mudar de
  // ordem entre duas renderizacoes do mesmo resultado.
  test("a ordem e estavel",()=>{
    const a=buscarNoCatalogo(real,"albumina").itens.map(f=>f.id);
    const b=buscarNoCatalogo([...real].reverse(),"albumina").itens.map(f=>f.id);
    expect(a).toEqual(b);
  });
});
