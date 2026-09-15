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

/*
 * Ritmo fora do plano: a oferta tem que bater com o que a gravacao aceita.
 *
 * O card "Agressivo/Atleta" era escolhivel como qualquer outro. A pessoa escolhia,
 * clicava em salvar, esperava, e so entao levava um 402 dizendo que o plano dela nao
 * inclui o recurso. Oferecer e depois recusar e pior do que deixar claro desde o inicio.
 */
const catalogoBloqueado={data:{
  plan_for_advanced:"FORGE PRO",
  current_plan:"FORGE ESSENCIAL",
  goals:catalogo.data.goals.map(g=>({...g,
    intensities:(g.intensities||[]).map(i=>({...i,locked:Boolean(i.advanced)}))})),
}};

test("ritmo bloqueado nao e clicavel",async()=>{
  axios.get.mockResolvedValue(catalogoBloqueado);
  await render();
  await abrir();
  const card=host.querySelector('[data-testid="ritmo-agressivo"]');
  expect(card).not.toBeNull();
  expect(card.disabled).toBe(true);
});

test("clicar no bloqueado nao muda a escolha nem habilita o salvar",async()=>{
  axios.get.mockResolvedValue(catalogoBloqueado);
  await render();
  await abrir();
  await tocar('[data-testid="ritmo-agressivo"]');
  expect(host.querySelector('[data-testid="ritmo-agressivo"]').getAttribute("aria-pressed")).toBe("false");
  expect(host.querySelector('[data-testid="ritmo-moderado"]').getAttribute("aria-pressed")).toBe("true");
  // Nada mudou, entao salvar continua desligado: nao ha como chegar no 402 por aqui.
  expect(host.querySelector('[data-testid="salvar-objetivo"]').disabled).toBe(true);
  expect(axios.put).not.toHaveBeenCalled();
});

test("bloqueado aparece em vez de sumir, e diz onde o recurso esta",async()=>{
  axios.get.mockResolvedValue(catalogoBloqueado);
  await render();
  await abrir();
  const card=host.querySelector('[data-testid="ritmo-agressivo"]');
  // Esconder faria parecer que o FORGE nao tem o recurso, quando quem nao tem e o plano.
  expect(card.textContent).toContain("Agressivo");
  expect(host.querySelector('[data-testid="ritmo-bloqueado-agressivo"]').textContent)
    .toContain("FORGE PRO");
  expect(card.textContent).toContain("FORGE ESSENCIAL");
});

test("sem bloqueio, o avancado continua escolhivel como antes",async()=>{
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  const card=host.querySelector('[data-testid="ritmo-agressivo"]');
  expect(card.disabled).toBe(false);
  await tocar('[data-testid="ritmo-agressivo"]');
  expect(host.querySelector('[data-testid="ritmo-agressivo"]').getAttribute("aria-pressed")).toBe("true");
});

test("o servidor manda locked: a tela nunca decide isso sozinha",async()=>{
  // Se a tela inferisse "advanced => bloqueado", o Pro perderia o recurso que ele TEM.
  axios.get.mockResolvedValue(catalogo);
  await render();
  await abrir();
  expect(host.querySelector('[data-testid="ritmo-bloqueado-agressivo"]')).toBeNull();
});
