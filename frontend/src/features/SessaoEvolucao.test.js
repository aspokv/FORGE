import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import SessaoEvolucao from "./SessaoEvolucao";
jest.mock("axios");

const catalogo=[{id:"supino",name:"Supino reto"},{id:"remada",name:"Remada curvada"},{id:"rosca",name:"Rosca direta"}];
const sessao={label:"Peito dominante",exercises:[{exercise_id:"supino",sets:4,reps:"6-8"},{exercise_id:"remada",sets:3,reps:"10"},{exercise_id:"rosca",sets:3,reps:"12"}]};
const performances={supino:{weight:80,reps:8,date:"2026-09-03",sets:4},remada:{weight:100,reps:10,date:"2026-09-03",sets:3}};

let host,root;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;axios.get.mockReset();host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
const render=async element=>{await act(async()=>{root.render(element);});};
const linhas=()=>[...host.querySelectorAll(".sessao-evolucao-lista li")];

test("pede so os exercicios da sessao, numa requisicao",async()=>{
  axios.get.mockResolvedValue({data:{performances}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(axios.get).toHaveBeenCalledTimes(1);
  expect(axios.get).toHaveBeenCalledWith("/api/session-last-performance",{params:{ids:"supino,remada,rosca"}});
});

test("mostra o treino do dia com a ultima carga de cada exercicio",async()=>{
  axios.get.mockResolvedValue({data:{performances}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(host.querySelector("h2").textContent).toBe("Peito dominante");
  expect(linhas()).toHaveLength(3);
  expect(linhas()[0].textContent).toContain("Supino reto");
  expect(linhas()[0].textContent).toContain("80 kg");
  expect(linhas()[0].textContent).toContain("× 8 · 03/09");
});

// Sumir com o exercicio faria a lista ficar menor que o treino de verdade.
test("exercicio sem historico aparece como estreia",async()=>{
  axios.get.mockResolvedValue({data:{performances}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(linhas()[2].textContent).toContain("Rosca direta");
  expect(linhas()[2].textContent).toContain("Estreia");
});

test("sem historico nenhum nao promete superacao",async()=>{
  axios.get.mockResolvedValue({data:{performances:{}}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(host.querySelector(".sessao-evolucao-guia").textContent).toBe("Primeira vez neste treino. Estes números viram sua base.");
});

test("com historico, convida a superar",async()=>{
  axios.get.mockResolvedValue({data:{performances}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(host.querySelector(".sessao-evolucao-guia").textContent).toBe("Suas últimas cargas. Supere o que der.");
});

// No descanso a pergunta continua valendo: e quando a pessoa planeja o dia seguinte.
test("no descanso o cabecalho diz que a sessao e a proxima",async()=>{
  axios.get.mockResolvedValue({data:{performances}});
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo} descanso/>);
  expect(host.querySelector(".a6-eyebrow").textContent).toBe("Próximo treino");
});

test("falha na carga nao apaga o treino da tela",async()=>{
  axios.get.mockRejectedValue(new Error("offline"));
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={sessao} catalogo={catalogo}/>);
  expect(linhas()).toHaveLength(3);
  expect(host.textContent).toContain("Não foi possível carregar suas cargas anteriores");
});

test("sem sessao o bloco nao ocupa espaco nem chama a rota",async()=>{
  await render(<SessaoEvolucao API="/api" profileId="um" sessao={null} catalogo={catalogo}/>);
  expect(host.querySelector('[data-testid="sessao-evolucao"]')).toBeNull();
  expect(axios.get).not.toHaveBeenCalled();
});
