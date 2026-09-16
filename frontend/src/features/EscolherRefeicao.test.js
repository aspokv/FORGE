import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import EscolherRefeicao from "./EscolherRefeicao";
jest.mock("axios");

/*
 * A tela existe para fazer a pergunta que um treinador faz, e nao para mostrar macros.
 *
 *   "Pre-treino: ou farinha de arroz e whey, ou farinha de arroz e aveia."
 *   "Pos-treino: escolha a sua carne. Quando a pessoa nao tem frango, ela tem um patinho."
 *   "Se passar um pouquinho das calorias nao tem problema. 150 pra mais ou pra menos."
 *
 * Tres coisas nao podem se perder, e sao o que estes testes prendem: a porcao ao lado de
 * cada alternativa, a margem visivel junto do alvo, e a grama vindo do SERVIDOR.
 */

const resposta = {data: {
  meal_index: 0,
  refeicao: "Almoço",
  tipo: "lunch",
  pergunta: "O que você quer no almoço?",
  alvo: {kcal: 650, protein_g: 45, fat_g: 18, tolerancia: 150},
  escolhida: "metodo_almoco",
  combinacoes: [
    {id: "metodo_almoco", titulo: "Almoço do método", do_metodo: true, kcal: 650,
     resumo: "Peito de frango grelhado + Batata inglesa cozida + Alface",
     itens: [
       {food_id: "chicken-breast", nome: "Peito de frango grelhado", gramas: 150, papel: "primary_protein", kcal: 248},
       {food_id: "potato", nome: "Batata inglesa cozida", gramas: 380, papel: "primary_carb", kcal: 293},
       {food_id: "lettuce", nome: "Alface", gramas: 150, papel: "vegetable", kcal: 22},
     ]},
    {id: "prato_completo", titulo: "Prato completo", do_metodo: false, kcal: 647,
     resumo: "Peito de frango grelhado + Arroz branco + Feijão carioca",
     itens: [
       {food_id: "chicken-breast", nome: "Peito de frango grelhado", gramas: 150, papel: "primary_protein", kcal: 248},
       {food_id: "rice-white", nome: "Arroz branco cozido", gramas: 226, papel: "primary_carb", kcal: 294},
     ]},
  ],
  trocas: [
    {papel: "primary_protein", rotulo: "Escolha sua proteína", explicacao: "É ela que manda no prato.",
     atual: "chicken-breast", opcoes: [
       {food_id: "chicken-breast", nome: "Peito de frango grelhado", gramas: 150, atual: true, kcal: 248},
       {food_id: "beef-ground", nome: "Carne moída (acém)", gramas: 101, atual: false, kcal: 212},
       {food_id: "beef-grill", nome: "Carne bovina grelhada (patinho)", gramas: 128, atual: false, kcal: 240},
       {food_id: "tilapia", nome: "Filé de tilápia", gramas: 193, atual: false, kcal: 252},
     ]},
    {papel: "primary_carb", rotulo: "Escolha seu carboidrato", explicacao: "O que vai junto.",
     atual: "potato", opcoes: [
       {food_id: "potato", nome: "Batata inglesa cozida", gramas: 380, atual: true, kcal: 293},
       {food_id: "rice-white", nome: "Arroz branco cozido", gramas: 226, atual: false, kcal: 294},
     ]},
  ],
}};

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.get.mockReset(); axios.post.mockReset();
  host=document.createElement("div"); document.body.appendChild(host); root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount()); host.remove();});

const render=async(props={})=>{await act(async()=>{
  root.render(<EscolherRefeicao API="/api" mealIndex={0}
                                onPronto={props.onPronto||(()=>{})}
                                onMontarDoZero={props.onMontarDoZero}/>);
});};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const texto=sel=>host.querySelector(sel)?.textContent||"";

// -- A pergunta ----------------------------------------------------------------------

test("abre fazendo a pergunta, e nao mostrando uma tabela",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(texto('[data-testid="escolher-refeicao"] h3')).toBe("O que você quer no almoço?");
});

test("o alvo aparece com a margem do lado, nunca sozinho",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  // O numero sozinho vira meta a perseguir; com a margem ele vira faixa.
  const alvo=texto('[data-testid="escolher-alvo"]');
  expect(alvo).toContain("650 kcal");
  expect(alvo).toContain("150");
  expect(alvo).toMatch(/mais|menos/);
});

// -- Primeira pergunta: qual montagem ------------------------------------------------

test("lista as montagens com o resumo dos alimentos, e nao o id",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  const combo=texto('[data-testid="combinacao-metodo_almoco"]');
  expect(combo).toContain("Almoço do método");
  expect(combo).toContain("Peito de frango grelhado");
  expect(combo).not.toContain("metodo_almoco");
});

test("a do metodo vem marcada com o selo",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(host.querySelector('[data-testid="selo-metodo_almoco"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="selo-prato_completo"]')).toBeNull();
});

test("a montagem que o servidor escolheu ja vem marcada",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(host.querySelector('[data-testid="combinacao-metodo_almoco"]').getAttribute("aria-checked")).toBe("true");
});

test("escolher outra montagem pergunta de novo ao servidor",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  axios.get.mockClear();
  await tocar('[data-testid="combinacao-prato_completo"]');
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/plan/draft/escolhas",
    {params:{meal_index:0, combinacao:"prato_completo"}});
});

// -- Segunda pergunta: qual alimento -------------------------------------------------

test("pergunta pela carne, com todas as opcoes",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  const bloco=host.querySelector('[data-testid="troca-primary_protein"]');
  expect(bloco.textContent).toContain("Escolha sua proteína");
  expect(bloco.querySelectorAll(".escolher-chip").length).toBe(4);
});

test("cada alternativa mostra a PORCAO dela, e nao a do alimento que estava la",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  // Foi a reclamacao do "ninguem vai usar 100 g de whey": escolher sem ver quanto e
  // escolher no escuro. E as gramas sao diferentes entre si, porque vem do motor.
  expect(texto('[data-testid="opcao-primary_protein-chicken-breast"]')).toContain("150 g");
  expect(texto('[data-testid="opcao-primary_protein-beef-ground"]')).toContain("101 g");
  expect(texto('[data-testid="opcao-primary_protein-beef-grill"]')).toContain("128 g");
});

test("o alimento atual ja vem marcado",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(host.querySelector('[data-testid="opcao-primary_protein-chicken-breast"]').getAttribute("aria-checked")).toBe("true");
  expect(host.querySelector('[data-testid="opcao-primary_protein-beef-ground"]').getAttribute("aria-checked")).toBe("false");
});

test("trocar a carne marca a nova e desmarca a anterior",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  await tocar('[data-testid="opcao-primary_protein-beef-grill"]');
  expect(host.querySelector('[data-testid="opcao-primary_protein-beef-grill"]').getAttribute("aria-checked")).toBe("true");
  expect(host.querySelector('[data-testid="opcao-primary_protein-chicken-breast"]').getAttribute("aria-checked")).toBe("false");
});

test("trocar a carne NAO dispara pedido ao servidor: so grava ao confirmar",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  axios.get.mockClear(); axios.post.mockClear();
  await tocar('[data-testid="opcao-primary_protein-tilapia"]');
  expect(axios.get).not.toHaveBeenCalled();
  expect(axios.post).not.toHaveBeenCalled();
});

// -- A conta -------------------------------------------------------------------------

test("dentro da faixa, a conta nao acusa erro",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  const conta=host.querySelector('[data-testid="escolher-conta"]');
  expect(conta.className).not.toContain("fora");
  expect(conta.textContent).toContain("dentro da faixa");
});

test("a troca recalcula a conta na tela",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  // frango 248 -> carne moida 212, entao o total cai 36.
  const antes=parseInt(texto('[data-testid="escolher-conta"]'),10);
  await tocar('[data-testid="opcao-primary_protein-beef-ground"]');
  const depois=parseInt(texto('[data-testid="escolher-conta"]'),10);
  expect(depois).toBe(antes-36);
});

test("passar da faixa avisa, e nao impede",async()=>{
  const apertado={data:{...resposta.data, alvo:{...resposta.data.alvo, kcal:400, tolerancia:150}}};
  axios.get.mockResolvedValue(apertado);
  await render();
  const conta=host.querySelector('[data-testid="escolher-conta"]');
  expect(conta.className).toContain("fora");
  // Continua dando para confirmar: a faixa avisa, nao tranca.
  expect(host.querySelector('[data-testid="confirmar-refeicao"]').disabled).toBe(false);
});

// -- Confirmar -----------------------------------------------------------------------

test("confirmar grava a montagem com a troca por cima",async()=>{
  axios.get.mockResolvedValue(resposta);
  axios.post.mockResolvedValue({data:{ok:true}});
  const onPronto=jest.fn();
  await render({onPronto});
  await tocar('[data-testid="opcao-primary_protein-beef-grill"]');
  await tocar('[data-testid="confirmar-refeicao"]');
  expect(axios.post).toHaveBeenCalledWith("/api/nutrition/plan/draft/choose",
    {meal_index:0, archetype_id:"metodo_almoco",
     food_ids:["beef-grill","potato","lettuce"]});
  expect(onPronto).toHaveBeenCalledWith({ok:true});
});

test("sem trocar nada, grava a montagem como ela veio",async()=>{
  axios.get.mockResolvedValue(resposta);
  axios.post.mockResolvedValue({data:{ok:true}});
  await render();
  await tocar('[data-testid="confirmar-refeicao"]');
  expect(axios.post.mock.calls[0][1].food_ids).toEqual(["chicken-breast","potato","lettuce"]);
});

test("a tela nunca manda grama para o servidor",async()=>{
  axios.get.mockResolvedValue(resposta);
  axios.post.mockResolvedValue({data:{ok:true}});
  await render();
  await tocar('[data-testid="confirmar-refeicao"]');
  // Quem decide a porcao e o motor. Mandar grama daqui criaria um segundo numero para a
  // mesma pergunta.
  expect(JSON.stringify(axios.post.mock.calls[0][1])).not.toMatch(/gram/i);
});

test("erro ao gravar aparece e nao derruba a tela",async()=>{
  axios.get.mockResolvedValue(resposta);
  axios.post.mockRejectedValue({response:{status:402,data:{detail:{message:"Seu plano não inclui isso.",upgrade:true}}}});
  await render();
  await tocar('[data-testid="confirmar-refeicao"]');
  // Detalhe em objeto: renderizar objeto derruba a arvore inteira do React.
  expect(texto('[role="alert"]')).toBe("Seu plano não inclui isso.");
  expect(host.querySelector('[data-testid="escolher-refeicao"]')).not.toBeNull();
});

test("falha ao carregar mostra motivo em vez de tela vazia",async()=>{
  axios.get.mockRejectedValue({response:{status:500,data:{}}});
  await render();
  expect(texto('[role="alert"]')).toContain("Não foi possível");
});

// -- A saida para quem quer montar do zero -------------------------------------------

test("oferece montar do zero quando ha para onde ir",async()=>{
  axios.get.mockResolvedValue(resposta);
  const onMontarDoZero=jest.fn();
  await render({onMontarDoZero});
  await tocar('[data-testid="ir-montar-do-zero"]');
  expect(onMontarDoZero).toHaveBeenCalled();
});

test("sem a saida, o botao nao aparece",async()=>{
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(host.querySelector('[data-testid="ir-montar-do-zero"]')).toBeNull();
});

/*
 * A parede de fichas.
 *
 * As opcoes eram pilulas com quebra de linha, cada uma da largura do proprio nome: "Tofu
 * firme" pequenininho ao lado de "Carne bovina grelhada (patinho)" ocupando a linha
 * inteira. Treze delas viravam uma parede irregular que tomava a tela antes de a pessoa
 * chegar no botao de confirmar. Agora e grade de cartoes iguais, e a lista longa fica
 * atras de um "ver todas".
 */
const treze = {data: {...resposta.data, trocas: [{
  papel: "primary_protein", rotulo: "Escolha sua proteína", explicacao: "",
  atual: "chicken-breast",
  opcoes: ["chicken-breast","eggs-whole","beef-ground","beef-grill","whey-protein",
           "tuna-can","tilapia","chicken-thigh","pork-loin","tofu","salmon",
           "egg-whites","soy-protein"].map((id,i)=>(
    {food_id:id, nome:"Proteína "+id, gramas:100+i, atual:i===0, kcal:200}
  )),
}]}};

test("lista longa mostra so as seis primeiras",async()=>{
  axios.get.mockResolvedValue(treze);
  await render();
  const bloco=host.querySelector('[data-testid="troca-primary_protein"]');
  expect(bloco.querySelectorAll(".escolher-chip").length).toBe(6);
  expect(texto('[data-testid="mais-primary_protein"]')).toContain("13");
});

test("a escolhida esta entre as visiveis, sempre",async()=>{
  // O servidor manda o alimento atual em primeiro lugar. Se o corte o escondesse, a
  // pessoa nao veria o que ja esta selecionado.
  axios.get.mockResolvedValue(treze);
  await render();
  expect(host.querySelector('[data-testid="opcao-primary_protein-chicken-breast"]')).not.toBeNull();
});

test("ver todas abre a lista inteira, e fecha de novo",async()=>{
  axios.get.mockResolvedValue(treze);
  await render();
  await tocar('[data-testid="mais-primary_protein"]');
  expect(host.querySelectorAll(".escolher-chip").length).toBe(13);
  expect(texto('[data-testid="mais-primary_protein"]')).toContain("menos");
  await tocar('[data-testid="mais-primary_protein"]');
  expect(host.querySelectorAll(".escolher-chip").length).toBe(6);
});

test("lista curta nao ganha botao",async()=>{
  // Quatro opcoes cabem: um "ver todas" ali seria obstaculo sem motivo.
  axios.get.mockResolvedValue(resposta);
  await render();
  expect(host.querySelector('[data-testid="mais-primary_protein"]')).toBeNull();
});

test("trocar de montagem recolhe as listas abertas",async()=>{
  axios.get.mockResolvedValue(treze);
  await render();
  await tocar('[data-testid="mais-primary_protein"]');
  await tocar('[data-testid="combinacao-prato_completo"]');
  expect(host.querySelectorAll(".escolher-chip").length).toBe(6);
});
