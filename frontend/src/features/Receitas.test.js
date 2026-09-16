import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import Receitas from "./Receitas";
jest.mock("axios");

/*
 * O que separa esta tela de um livro de receitas e o ENCAIXE: cada receita diz se cabe na
 * refeicao DAQUELA pessoa, com a mesma margem que o resto do produto usa.
 *
 * E a tela nao calcula nada. Caloria, macro e encaixe vem prontos do servidor — se a tela
 * fizesse a conta, existiriam dois numeros para a mesma pergunta, que foi exatamente o
 * defeito ja corrigido na meta do carboidrato.
 */

const classes = {data: {classes: [
  {chave: "cafe_da_manha", rotulo: "Café da manhã", quantas: 4},
  {chave: "lanche", rotulo: "Lanche da tarde", quantas: 4},
  {chave: "sobremesa", rotulo: "Sobremesa", quantas: 5},
]}};

const mingau = {
  id: "mingau-forge", nome: "Mingau FORGE", classe: "cafe_da_manha",
  classe_rotulo: "Café da manhã", classe_frase: "no seu café da manhã", resumo: "O café da manhã do método.",
  tempo_min: 5, rendimento: 1, refeicao_livre: false,
  kcal: 489, protein_g: 36, carbs_g: 67, fat_g: 11,
  ingredientes: [
    {food_id: "oats", nome: "Aveia em flocos", gramas: 60},
    {food_id: "whey-protein", nome: "Whey protein concentrado", gramas: 30},
  ],
  extras: ["Canela a gosto"],
  preparo: ["Cozinhe a aveia.", "Misture o whey fora do fogo."],
  por_que: "Aveia com whey é a base do café da manhã do método.",
  tags: ["rapida"],
  encaixe: {receita: "mingau-forge", kcal: 489, alvo: 500, diferenca: -11,
            margem: 150, cabe: true, sobra: 11, excedeu: 0},
};

const bolinha = {
  id: "bolinha-energetica", nome: "Bolinhas de aveia", classe: "sobremesa",
  classe_rotulo: "Sobremesa", classe_frase: "na sua sobremesa", resumo: "Faz uma vez, come a semana.",
  tempo_min: 10, rendimento: 4, refeicao_livre: true,
  kcal: 170, protein_g: 11, carbs_g: 21, fat_g: 6,
  ingredientes: [{food_id: "oats", nome: "Aveia em flocos", gramas: 80}],
  extras: [], preparo: ["Amasse a banana."], por_que: "É o doce que cabe na bolsa.",
  tags: ["doce"],
  encaixe: {receita: "bolinha-energetica", kcal: 170, alvo: 350, diferenca: -180,
            margem: 150, cabe: true, sobra: 180, excedeu: 0},
};

const grande = {
  ...mingau, id: "prato-completo", nome: "Prato completo", classe_rotulo: "Almoço e jantar", classe_frase: "no seu almoço",
  kcal: 703, refeicao_livre: false,
  encaixe: {receita: "prato-completo", kcal: 703, alvo: 300, diferenca: 403,
            margem: 150, cabe: false, sobra: 0, excedeu: 253},
};

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.get.mockReset();
  host=document.createElement("div"); document.body.appendChild(host); root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount()); host.remove();});

const responder=(receitas)=>{
  axios.get.mockImplementation(url =>
    url.endsWith("/classes") ? Promise.resolve(classes)
                             : Promise.resolve({data:{receitas, quantas:receitas.length}}));
};
const render=async()=>{await act(async()=>{root.render(<Receitas API="/api"/>);});};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const abrir=async()=>{await tocar('[data-testid="abrir-receitas"]')};
const texto=sel=>host.querySelector(sel)?.textContent||"";

// -- Fechada por padrão ---------------------------------------------------------------

test("comeca fechada: quem abre a Nutricao vem ver o plano do dia",async()=>{
  responder([mingau]);
  await render();
  expect(host.querySelector('[data-testid="abrir-receitas"]').getAttribute("aria-expanded")).toBe("false");
  expect(axios.get).not.toHaveBeenCalled();
});

test("abrir busca as classes e as receitas",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/receitas/classes");
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/receitas",{params:{}});
});

// -- As abas ---------------------------------------------------------------------------

test("lista uma aba por classe, com a contagem",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  expect(texto('[data-testid="aba-cafe_da_manha"]')).toContain("Café da manhã");
  expect(texto('[data-testid="aba-cafe_da_manha"]')).toContain("4");
  expect(host.querySelector('[data-testid="aba-todas"]').getAttribute("aria-selected")).toBe("true");
});

test("escolher uma classe filtra no servidor, e nao na tela",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  axios.get.mockClear();
  await tocar('[data-testid="aba-sobremesa"]');
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/receitas",{params:{classe:"sobremesa"}});
});

test("refeicao livre e aba propria, e nao filtro escondido",async()=>{
  responder([bolinha]);
  await render();
  await abrir();
  axios.get.mockClear();
  await tocar('[data-testid="aba-refeicao-livre"]');
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/receitas",{params:{livres:true}});
  expect(host.querySelector('[data-testid="aba-refeicao-livre"]').getAttribute("aria-selected")).toBe("true");
});

test("escolher classe desmarca refeicao livre",async()=>{
  responder([bolinha]);
  await render();
  await abrir();
  await tocar('[data-testid="aba-refeicao-livre"]');
  await tocar('[data-testid="aba-lanche"]');
  expect(host.querySelector('[data-testid="aba-refeicao-livre"]').getAttribute("aria-selected")).toBe("false");
});

// -- O cartão fechado responde sem abrir ------------------------------------------------

test("o cartao fechado ja mostra caloria, macro e tempo",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  // Quem precisa abrir para saber se a receita serve nao vai abrir vinte.
  const cartao=texto('[data-testid="receita-mingau-forge"]');
  expect(cartao).toContain("489");
  expect(cartao).toContain("P 36");
  expect(cartao).toContain("5 min");
});

test("o encaixe diz se cabe na refeicao DAQUELA pessoa",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  const encaixe=texto('[data-testid="encaixe-mingau-forge"]');
  expect(encaixe).toContain("Cabe");
  expect(encaixe).toContain("500");
  expect(encaixe).toContain("sobram 11");
});

test("a frase concorda em genero: sobremesa e feminino",async()=>{
  // "Cabe no seu sobremesa" saiu na tela de verdade. A frase vem pronta do servidor
  // justamente porque a tela nao tem como saber o genero de um rotulo.
  responder([bolinha]);
  await render();
  await abrir();
  expect(texto('[data-testid="encaixe-bolinha-energetica"]')).toContain("na sua sobremesa");
  expect(texto('[data-testid="encaixe-bolinha-energetica"]')).not.toContain("no seu sobremesa");
});

test("quando nao cabe, diz quanto passa",async()=>{
  responder([grande]);
  await render();
  await abrir();
  const encaixe=host.querySelector('[data-testid="encaixe-prato-completo"]');
  expect(encaixe.textContent).toContain("Passa 253");
  expect(encaixe.className).toContain("nao");
});

test("sem encaixe do servidor, a tela nao inventa numero",async()=>{
  // Sem plano montado nao ha alvo. Inventar um seria pior do que nao dizer nada.
  const semEncaixe={...mingau}; delete semEncaixe.encaixe;
  responder([semEncaixe]);
  await render();
  await abrir();
  expect(host.querySelector('[data-testid="encaixe-mingau-forge"]')).toBeNull();
});

test("a receita livre vem marcada com o selo",async()=>{
  responder([bolinha]);
  await render();
  await abrir();
  expect(texto('[data-testid="receita-bolinha-energetica"]')).toContain("refeição livre");
  expect(texto('[data-testid="receita-mingau-forge"]')).toBe("");
});

// -- Aberta ------------------------------------------------------------------------------

test("abrir a receita mostra ingredientes com grama, preparo e o porque",async()=>{
  responder([mingau]);
  await render();
  await abrir();
  await tocar('[data-testid="abrir-mingau-forge"]');
  const corpo=texto('[data-testid="receita-mingau-forge"]');
  expect(corpo).toContain("Aveia em flocos");
  expect(corpo).toContain("60 g");
  expect(corpo).toContain("Canela a gosto");
  expect(corpo).toContain("Misture o whey fora do fogo.");
  expect(corpo).toContain("base do café da manhã do método");
});

test("receita que rende mais de uma porcao avisa que o macro e de UMA",async()=>{
  responder([bolinha]);
  await render();
  await abrir();
  await tocar('[data-testid="abrir-bolinha-energetica"]');
  const corpo=texto('[data-testid="receita-bolinha-energetica"]');
  // Sem este aviso, a pessoa pesa 80 g de aveia e come tudo achando que foram 170 kcal.
  expect(corpo).toContain("rende 4");
  expect(corpo).toMatch(/receita inteira/i);
});

test("abrir uma fecha a outra: so uma aberta por vez",async()=>{
  responder([mingau, bolinha]);
  await render();
  await abrir();
  await tocar('[data-testid="abrir-mingau-forge"]');
  await tocar('[data-testid="abrir-bolinha-energetica"]');
  expect(host.querySelector('[data-testid="abrir-mingau-forge"]').getAttribute("aria-expanded")).toBe("false");
  expect(host.querySelector('[data-testid="abrir-bolinha-energetica"]').getAttribute("aria-expanded")).toBe("true");
});

// -- Erro ---------------------------------------------------------------------------------

test("erro do servidor aparece com motivo e nao derruba a tela",async()=>{
  axios.get.mockRejectedValue({response:{status:402,data:{detail:{message:"Seu plano não inclui alimentação.",upgrade:true}}}});
  await render();
  await abrir();
  expect(texto('[role="alert"]')).toBe("Seu plano não inclui alimentação.");
  expect(host.querySelector('[data-testid="receitas"]')).not.toBeNull();
});

test("aba sem receita diz isso em vez de ficar vazia",async()=>{
  responder([]);
  await render();
  await abrir();
  expect(host.querySelector(".receitas-corpo").textContent).toMatch(/Nenhuma receita/i);
});
