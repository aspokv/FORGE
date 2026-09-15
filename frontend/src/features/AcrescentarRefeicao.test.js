import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import AcrescentarRefeicao from "./AcrescentarRefeicao";
jest.mock("axios");

const refeicoes=[{name:"Café da manhã"},{name:"Almoço"},{name:"Jantar"}];

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.post.mockReset();
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();});

const render=async(lista=refeicoes,onAcrescentada)=>{await act(async()=>{
  root.render(<AcrescentarRefeicao API="/api" refeicoes={lista} onAcrescentada={onAcrescentada}/>);
});};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const digitar=async texto=>{
  const campo=host.querySelector('[data-testid="nome-da-refeicao"]');
  const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(campo),"value").set;
  await act(async()=>{setter.call(campo,texto);campo.dispatchEvent(new Event("input",{bubbles:true}))});
};

test("lista uma posicao por fresta entre as refeicoes",async()=>{
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  // Antes da primeira + depois de cada uma das tres = quatro posicoes.
  expect(host.querySelectorAll(".acrescentar-posicao")).toHaveLength(4);
  expect(host.querySelector('[data-testid="posicao-0"]').textContent).toContain("Café da manhã");
});

test("a sugestao preenche o nome",async()=>{
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  await tocar('[data-testid="sugestao-Pré-treino"]');
  expect(host.querySelector('[data-testid="nome-da-refeicao"]').value).toBe("Pré-treino");
});

// Descobrir depois que as outras refeicoes encolheram seria pior que ser avisado antes.
test("avisa que as outras refeicoes encolhem ANTES de acrescentar",async()=>{
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  expect(host.textContent).toContain("as outras refeições ficam menores");
  expect(host.textContent).toContain("porções mudam");
});

test("acrescentar envia nome e posicao",async()=>{
  axios.post.mockResolvedValue({data:{plan:{meals:[]},meal_count:4,posicao:0}});
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  await tocar('[data-testid="sugestao-Pré-treino"]');
  await tocar('[data-testid="posicao-0"]');
  await tocar('[data-testid="salvar-refeicao"]');
  expect(axios.post).toHaveBeenCalledWith("/api/nutrition/plan/add-meal",
    {nome:"Pré-treino",posicao:0});
});

test("nome curto demais nao deixa salvar",async()=>{
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  await digitar("a");
  expect(host.querySelector('[data-testid="salvar-refeicao"]').disabled).toBe(true);
  await digitar("Ceia");
  expect(host.querySelector('[data-testid="salvar-refeicao"]').disabled).toBe(false);
});

test("com seis refeicoes o bloco se desabilita e explica",async()=>{
  await render([1,2,3,4,5,6].map(n=>({name:`Refeição ${n}`})));
  const topo=host.querySelector('[data-testid="abrir-acrescentar"]');
  expect(topo.disabled).toBe(true);
  expect(topo.textContent).toContain("máximo");
});

test("falha ao acrescentar mostra o motivo do servidor",async()=>{
  axios.post.mockRejectedValue({response:{data:{detail:"Plano não encontrado."}}});
  await render();
  await tocar('[data-testid="abrir-acrescentar"]');
  await tocar('[data-testid="sugestao-Ceia"]');
  await tocar('[data-testid="salvar-refeicao"]');
  expect(host.textContent).toContain("Plano não encontrado");
});

test("sucesso devolve o plano novo para a tela",async()=>{
  const pronto=jest.fn();
  axios.post.mockResolvedValue({data:{plan:{meals:[{name:"Pré-treino"}]},meal_count:4,posicao:0}});
  await render(refeicoes,pronto);
  await tocar('[data-testid="abrir-acrescentar"]');
  await tocar('[data-testid="sugestao-Ceia"]');
  await tocar('[data-testid="salvar-refeicao"]');
  expect(pronto).toHaveBeenCalledWith(expect.objectContaining({meal_count:4}));
});
