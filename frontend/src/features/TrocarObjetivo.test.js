import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import TrocarObjetivo from "./TrocarObjetivo";
jest.mock("axios");

const catalogo={data:{goals:[
  {id:"fat_loss",label:"Emagrecimento",description:"Perder gordura",default_intensity:"moderado",
   intensities:[
     {id:"leve",label:"Leve",description:"Gradual"},
     {id:"moderado",label:"Moderado",description:"Equilibrado",recommended:true},
     {id:"agressivo",label:"Agressivo/Atleta",description:"Extremo",advanced:true,
      warning:"Protocolo extremo e temporário."},
   ]},
  {id:"muscle_gain",label:"Ganho de massa",description:"Construir músculo",default_intensity:"controlado",
   intensities:[{id:"controlado",label:"Controlado",description:"Gradual",recommended:true}]},
  {id:"maintenance",label:"Manutenção",description:"Manter",default_intensity:null,intensities:[]},
]}};

let host,root;
beforeEach(()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  axios.get.mockReset();axios.put.mockReset();
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
});
afterEach(()=>{act(()=>root.unmount());host.remove();});

const render=async(props={})=>{await act(async()=>{
  root.render(<TrocarObjetivo API="/api" objetivoAtual={props.objetivo||"fat_loss"}
                              intensidadeAtual={props.intensidade||"moderado"}
                              onTrocado={props.onTrocado}/>);
});};
const tocar=async sel=>{await act(async()=>{host.querySelector(sel).click()})};
const abrir=async()=>{await tocar('[data-testid="abrir-objetivo"]')};

test("comeca fechado: o plano do dia e o que a pessoa abre todo dia",async()=>{
  await render();
  expect(host.querySelector('[data-testid="abrir-objetivo"]').getAttribute("aria-expanded")).toBe("false");
  expect(axios.get).not.toHaveBeenCalled();
});

test("abrir busca o catalogo e lista os objetivos",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  expect(axios.get).toHaveBeenCalledWith("/api/nutrition/goal-catalog");
  expect(host.querySelector('[data-testid="objetivo-muscle_gain"]')).not.toBeNull();
});

// "Manutencao agressiva" nao existe: cada objetivo tem os ritmos dele.
test("trocar de objetivo troca o ritmo para o padrao do novo",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  await tocar('[data-testid="objetivo-muscle_gain"]');
  expect(host.querySelector('[data-testid="ritmo-controlado"]').getAttribute("aria-pressed")).toBe("true");
  expect(host.querySelector('[data-testid="ritmo-moderado"]')).toBeNull();
});

test("manutencao nao mostra ritmo nenhum",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  await tocar('[data-testid="objetivo-maintenance"]');
  expect(host.querySelectorAll(".objetivo-ritmo")).toHaveLength(0);
});

// O aviso do protocolo extremo e o que separa escolha informada de surpresa.
test("o ritmo avancado mostra o aviso ao ser escolhido",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  await tocar('[data-testid="ritmo-agressivo"]');
  expect(host.textContent).toContain("Protocolo extremo");
});

test("salvar so liga quando algo mudou",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  expect(host.querySelector('[data-testid="salvar-objetivo"]').disabled).toBe(true);
  await tocar('[data-testid="objetivo-muscle_gain"]');
  expect(host.querySelector('[data-testid="salvar-objetivo"]').disabled).toBe(false);
});

test("salvar envia objetivo e ritmo",async()=>{
  axios.get.mockResolvedValue(catalogo);
  axios.put.mockResolvedValue({data:{goal:"muscle_gain",intensity:"controlado",
    targets:{goal_calories:3039,protein_g:167,carbs_g:434,fat_g:70},plano_atualizado:true}});
  await render();
  await abrir();
  await tocar('[data-testid="objetivo-muscle_gain"]');
  await tocar('[data-testid="salvar-objetivo"]');
  expect(axios.put).toHaveBeenCalledWith("/api/nutrition/goal",
    {goal:"muscle_gain",intensity:"controlado"});
});

test("mostra a meta nova e avisa que o cardapio nao mudou",async()=>{
  axios.get.mockResolvedValue(catalogo);
  axios.put.mockResolvedValue({data:{goal:"muscle_gain",intensity:"controlado",
    targets:{goal_calories:3039,protein_g:167,carbs_g:434,fat_g:70},plano_atualizado:true}});
  await render();
  await abrir();
  await tocar('[data-testid="objetivo-muscle_gain"]');
  await tocar('[data-testid="salvar-objetivo"]');
  const res=host.querySelector('[data-testid="objetivo-resultado"]').textContent;
  expect(res).toContain("3039 kcal");
  expect(res).toContain("continuam as mesmas");
});

test("recusa do servidor aparece com o motivo",async()=>{
  axios.get.mockResolvedValue(catalogo);
  axios.put.mockRejectedValue({response:{data:{detail:"Seu plano não inclui protocolos agressivos."}}});
  await render();
  await abrir();
  await tocar('[data-testid="ritmo-agressivo"]');
  await tocar('[data-testid="salvar-objetivo"]');
  expect(host.textContent).toContain("não inclui protocolos agressivos");
});

// O DEFEITO QUE DEIXOU A TELA PRETA.
//
// `exigir_capacidade` levanta 402 com o detalhe sendo um OBJETO, e nao texto:
//   {message, capability, current_plan, upgrade}
// Renderizar um objeto como filho de JSX derruba a arvore inteira do React — a tela fica
// preta e nada mais responde. Era o unico caminho que devolvia 402, por isso so acontecia
// ao escolher o ritmo Agressivo.
test("recusa do plano com detalhe em OBJETO nao pode derrubar a tela",async()=>{
  axios.get.mockResolvedValue(catalogo);
  axios.put.mockRejectedValue({response:{status:402,data:{detail:{
    message:"Seu plano atual não inclui este recurso.",
    capability:"aggressive_protocols",current_plan:"FORGE PRO",upgrade:true}}}});
  await render();
  await abrir();
  await tocar('[data-testid="ritmo-agressivo"]');
  await tocar('[data-testid="salvar-objetivo"]');
  expect(host.querySelector('[data-testid="trocar-objetivo"]')).not.toBeNull();
  expect(host.textContent).toContain("não inclui este recurso");
});

test("detalhe em objeto sem mensagem ainda mostra algo legivel",async()=>{
  axios.get.mockResolvedValue(catalogo);
  axios.put.mockRejectedValue({response:{status:402,data:{detail:{upgrade:true}}}});
  await render();
  await abrir();
  await tocar('[data-testid="ritmo-agressivo"]');
  await tocar('[data-testid="salvar-objetivo"]');
  expect(host.querySelector('[data-testid="trocar-objetivo"]')).not.toBeNull();
  expect(host.textContent).toContain("Não foi possível");
});
