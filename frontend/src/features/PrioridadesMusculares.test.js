import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import PrioridadesMusculares from "./PrioridadesMusculares";
jest.mock("axios");

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.put.mockReset();
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();});

const render=async(props={})=>{await act(async()=>{
  root.render(<PrioridadesMusculares API="/api" profileId="atleta-1"
                                     iniciais={props.iniciais||[]} onSalvo={props.onSalvo}/>);
});};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const chip=nome=>host.querySelector(`[data-testid="prioridade-${nome}"]`);
const salvar=()=>host.querySelector('[data-testid="salvar-prioridades"]');
const foco=()=>host.querySelector('[data-testid="prioridades-foco"]').textContent;

const resposta=(extra={})=>({data:{profile:{},program:{},priorities:[],anteriores:[],
  recalculou:true,aviso:"",...extra}});

test("abre com as prioridades que a pessoa ja tinha",async()=>{
  await render({iniciais:["Glúteos","Bíceps"]});
  expect(foco()).toContain("Glúteos");
  expect(foco()).toContain("Bíceps");
  expect(chip("Glúteos").getAttribute("aria-pressed")).toBe("true");
});

test("sem nenhuma, diz que o treino fica equilibrado",async()=>{
  await render();
  expect(foco()).toContain("Treino equilibrado");
});

// A ORDEM e o dado: a primeira recebe mais atencao no plano.
test("a primeira escolhida e a principal, e as outras sao secundarias",async()=>{
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="prioridade-Glúteos"]');
  const texto=foco();
  expect(texto.indexOf("Tríceps")).toBeLessThan(texto.indexOf("Glúteos"));
  expect(texto).toContain("principal");
  expect(texto).toContain("secundária");
});

test("tocar de novo na mesma regiao desmarca",async()=>{
  await render();
  await tocar('[data-testid="prioridade-Glúteos"]');
  expect(foco()).toContain("Glúteos");
  await tocar('[data-testid="prioridade-Glúteos"]');
  expect(foco()).toContain("Treino equilibrado");
});

// Dizer o limite e melhor que ignorar o toque em silencio.
test("a quarta regiao e recusada com explicacao",async()=>{
  await render({iniciais:["Bíceps","Tríceps","Glúteos"]});
  await tocar('[data-testid="prioridade-Quadríceps"]');
  expect(host.textContent).toContain("máximo 3 regiões");
  expect(foco()).not.toContain("Quadríceps");
});

test("salvar so liga quando algo mudou",async()=>{
  await render({iniciais:["Glúteos"]});
  expect(salvar().disabled).toBe(true);
  await tocar('[data-testid="prioridade-Tríceps"]');
  expect(salvar().disabled).toBe(false);
});

test("salvar envia as prioridades na ordem escolhida",async()=>{
  axios.put.mockResolvedValue(resposta());
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="prioridade-Glúteos"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(axios.put).toHaveBeenCalledWith("/api/training/priorities",
    {priorities:["Tríceps","Glúteos"],profile_id:"atleta-1"});
});

test("lista vazia pode ser salva: treino equilibrado e escolha valida",async()=>{
  axios.put.mockResolvedValue(resposta());
  await render({iniciais:["Glúteos"]});
  await tocar('[data-testid="prioridade-Glúteos"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(axios.put.mock.calls[0][1].priorities).toEqual([]);
});

// Dizer "salvo" e deixar o treino igual sem explicacao seria pior que nao deixar trocar.
test("quando o treino nao recalcula, mostra o motivo em vez de comemorar",async()=>{
  axios.put.mockResolvedValue(resposta({recalculou:false,
    aviso:"Seu treino hoje é um programa completo da biblioteca, que não se recalcula sozinho."}));
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(host.querySelector('[data-testid="prioridades-aviso"]')).not.toBeNull();
  expect(host.textContent).toContain("não se recalcula sozinho");
  expect(host.textContent).not.toContain("treino recalculado");
});

test("quando recalcula de verdade, confirma",async()=>{
  axios.put.mockResolvedValue(resposta({recalculou:true,aviso:""}));
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(host.textContent).toContain("treino recalculado");
  expect(host.querySelector('[data-testid="prioridades-aviso"]')).toBeNull();
});

test("erro do servidor aparece com o motivo dele",async()=>{
  axios.put.mockRejectedValue({response:{data:{detail:"Região desconhecida: Xyz."}}});
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(host.textContent).toContain("Região desconhecida");
});

test("falha sem detalhe ainda avisa a pessoa",async()=>{
  axios.put.mockRejectedValue(new Error("rede"));
  await render();
  await tocar('[data-testid="prioridade-Tríceps"]');
  await tocar('[data-testid="salvar-prioridades"]');
  expect(host.textContent).toContain("Não foi possível salvar");
});
