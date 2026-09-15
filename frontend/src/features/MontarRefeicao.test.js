import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import MontarRefeicao from "./MontarRefeicao";
jest.mock("axios");

const alimento=(id,nome,kcal,metodo=false)=>({food_id:id,name:nome,kcal_por_100g:kcal,
  protein_por_100g:0,carb_por_100g:0,fat_por_100g:0,metodo});

const espacos=(escolhidos={})=>[
  {papel:"primary_protein",rotulo:"Proteína",explicacao:"O que ancora o prato.",obrigatorio:true,
   escolhido:escolhidos.primary_protein||null,
   alimentos:[alimento("chicken-breast","Peito de frango grelhado",165,true),
              alimento("tilapia","Filé de tilápia",96,true),
              alimento("tuna-can","Atum em lata",116)]},
  {papel:"primary_carb",rotulo:"Carboidrato",explicacao:"A energia da refeição.",obrigatorio:true,
   escolhido:escolhidos.primary_carb||null,
   alimentos:[alimento("rice-white","Arroz branco cozido",130,true),
              alimento("potato","Batata inglesa cozida",87,true)]},
  {papel:"fat_source",rotulo:"Gordura",explicacao:"Pouca quantidade, muita caloria.",obrigatorio:false,
   escolhido:escolhidos.fat_source||null,
   alimentos:[alimento("olive-oil","Azeite de oliva",884,true)]},
];

function faltando(escolhidos){
  const falta=[];
  if(!escolhidos.primary_protein)falta.push("Proteína");
  if(!escolhidos.primary_carb)falta.push("Carboidrato");
  return falta;
}

function slots(escolhidos={}){
  return {data:{
    meal_index:1,name:"Almoço",target_cal:800,target_protein:55,target_fat:22,
    espacos:espacos(escolhidos),falta:faltando(escolhidos),
  }};
}

// Qual espaco fica com cada alimento, para a previa devolver os espacos como o servidor
// devolveria: o escolhido marcado no seu espaco e ausente dos outros.
function papelDe(id){
  if(id==="rice-white"||id==="potato")return "primary_carb";
  if(id==="olive-oil")return "fat_source";
  return "primary_protein";
}

function compor(ids,kcal,falta){
  const escolhidos={};
  ids.forEach(id=>{escolhidos[papelDe(id)]=id});
  return {data:{
    meal_index:1,
    foods:ids.map(id=>({food_id:id,grams:150,food:{name:id}})),
    totais:{kcal,protein_g:40,carbs_g:60,fat_g:12},
    alvo:800,proporcao:kcal/800,coerencia:78,
    espacos:espacos(escolhidos),falta,
  }};
}

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.get.mockReset();axios.post.mockReset();
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();});

const render=async el=>{await act(async()=>{root.render(el)});};
const montar=async(props={})=>{
  await render(<MontarRefeicao API="/api" mealIndex={1} onPronto={props.onPronto||(()=>{})}
                               onCancelar={props.onCancelar||(()=>{})}/>);
};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const texto=()=>host.textContent;

test("pede os espacos da refeicao certa ao abrir",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/plan/draft/slots",{params:{meal_index:1}});
});

test("mostra o alvo da refeicao e o que falta escolher",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  expect(texto()).toContain("de 800 kcal");
  expect(texto()).toContain("Falta escolher:");
  expect(texto()).toContain("Proteína, Carboidrato");
});

// O primeiro espaco vazio ja abre: fazer a pessoa tocar para descobrir onde agir seria um
// toque cobrado a toa.
test("o primeiro espaco obrigatorio vazio ja abre",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  expect(host.querySelector('[data-testid="espaco-primary_protein"]').getAttribute("aria-expanded")).toBe("true");
  expect(host.querySelector('[data-testid="espaco-primary_carb"]').getAttribute("aria-expanded")).toBe("false");
});

test("escolher um alimento pede a previa ao servidor com o que foi escolhido",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  axios.post.mockResolvedValue(compor(["chicken-breast"],420,["Carboidrato"]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  expect(axios.post).toHaveBeenLastCalledWith("/api/nutrition/plan/draft/compose",
    {meal_index:1,food_ids:["chicken-breast"]});
});

// A grama vem do servidor. Calcular aqui criaria um segundo numero para a mesma pergunta.
test("a grama mostrada e a que o servidor calculou",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  axios.post.mockResolvedValue(compor(["chicken-breast"],420,["Carboidrato"]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  expect(host.querySelector('[data-testid="montar-kcal"]').textContent).toBe("420");
  expect(texto()).toContain("150 g");
});

// Um alimento por espaco: somar dois carboidratos e o caminho mais curto para o prato
// incoerente, que e exatamente o que a separacao por funcao existe para evitar.
test("tocar noutro alimento do mesmo espaco troca, e nao soma",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  axios.post.mockResolvedValue(compor(["chicken-breast"],420,["Carboidrato"]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  axios.post.mockResolvedValue(compor(["tilapia"],300,["Carboidrato"]));
  await tocar('[data-testid="opcao-tilapia"]');
  const ultima=axios.post.mock.calls[axios.post.mock.calls.length-1][1];
  expect(ultima.food_ids).toEqual(["tilapia"]);
});

test("tocar no alimento ja marcado desmarca",async()=>{
  axios.get.mockResolvedValue(slots({primary_protein:"chicken-breast"}));
  axios.post.mockResolvedValue(compor(["chicken-breast"],420,["Carboidrato"]));
  await montar();
  // O componente abre o primeiro espaco VAZIO, entao a proteina ja escolhida vem fechada.
  // Abrir antes de desmarcar e o mesmo caminho que a pessoa faz.
  await tocar('[data-testid="espaco-primary_protein"]');
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  const ultima=axios.post.mock.calls[axios.post.mock.calls.length-1][1];
  expect(ultima.food_ids).toEqual([]);
});

test("o alimento do metodo aparece com selo",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  const marcado=host.querySelector('[data-testid="opcao-chicken-breast"] .fg-selo-metodo');
  expect(marcado).not.toBeNull();
  expect(host.querySelector('[data-testid="opcao-tuna-can"] .fg-selo-metodo')).toBeNull();
});

test("confirmar so liga quando nada mais falta",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  const botao=()=>host.querySelector('[data-testid="confirmar-montagem"]');
  expect(botao().disabled).toBe(true);
  axios.post.mockResolvedValue(compor(["chicken-breast","rice-white"],800,[]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  expect(botao().disabled).toBe(false);
  expect(texto()).toContain("Pronto para confirmar");
});

test("confirmar grava a refeicao e devolve o rascunho",async()=>{
  const pronto=jest.fn();
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar({onPronto:pronto});
  axios.post.mockResolvedValue(compor(["chicken-breast","rice-white"],800,[]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  axios.post.mockResolvedValue({data:{locked:[false,true]}});
  await tocar('[data-testid="confirmar-montagem"]');
  expect(axios.post).toHaveBeenCalledWith("/api/nutrition/plan/draft/choose",
    expect.objectContaining({meal_index:1,archetype_id:"montado"}));
  expect(pronto).toHaveBeenCalledWith({locked:[false,true]});
});

test("falha ao abrir as opcoes avisa em vez de mostrar tela vazia",async()=>{
  axios.get.mockRejectedValue(new Error("rede"));
  await montar();
  expect(texto()).toContain("Não foi possível abrir as opções");
});

test("falha ao gravar mantem a pessoa na tela com o que ela montou",async()=>{
  axios.get.mockResolvedValue(slots());
  axios.post.mockResolvedValue(compor([],0,["Proteína","Carboidrato"]));
  await montar();
  axios.post.mockResolvedValue(compor(["chicken-breast","rice-white"],800,[]));
  await tocar('[data-testid="opcao-chicken-breast"]');
  axios.post.mockRejectedValue(new Error("rede"));
  await tocar('[data-testid="confirmar-montagem"]');
  expect(texto()).toContain("Não foi possível salvar esta refeição");
  expect(host.querySelector('[data-testid="montar-refeicao"]')).not.toBeNull();
});
