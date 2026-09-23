import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import ReferenceHome from "./ReferenceHome";
import Nutrition from "./Nutrition";
import AstraProgress from "./AstraProgress";
import useAppSection from "./useAppSection";

jest.mock("axios",()=>({get:jest.fn(),post:jest.fn(),delete:jest.fn()}));
jest.mock("./workoutCalendar",()=>({useScheduledProgram:p=>p}));
jest.mock("./workoutCompletionState",()=>({useWorkoutCompletion:()=>({completion:null}),completionForToday:()=>null,sessionStatus:()=>""}));
jest.mock("./ExerciseEvolution",()=>()=>null);
jest.mock("./SessaoEvolucao",()=>()=>null);
jest.mock("./DietaEvolucao",()=>()=> <p>Histórico alimentar</p>);
global.IS_REACT_ACT_ENVIRONMENT=true;

let host,root;
const db={profile:{id:"test-user",name:"Atleta"},program:{sessions:[]},recent_sets:[]};
const plan={source:"manual_import",meals:[],targets:{}};
const failure=status=>({response:{status},message:"network failure"});
const dataFor=url=>url.endsWith("/nutrition/plan")?plan:url.includes("/hydration/")?{total_ml:500,goal_ml:2000}:url.includes("/adherence/")?{meals:[],extras:[]}:{checkin:null};
beforeEach(()=>{
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
  axios.get.mockReset();axios.post.mockReset();axios.delete.mockReset();
  axios.get.mockImplementation(async url=>({data:dataFor(url)}));
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();window.history.replaceState({},"","/")});
const render=component=>act(async()=>root.render(component));
const click=button=>act(async()=>button.click());

test("Home distinguishes a failed plan request from having no plan, and recovers",async()=>{
  axios.get.mockRejectedValue(failure(503));
  await render(<ReferenceHome db={db} start={()=>{}}/>);
  expect(host.textContent).toContain("Alimentação indisponível");
  expect(host.textContent).not.toContain("Sem plano");
  expect(host.querySelector('[data-testid="hydration-add-250"]')).toBeNull();
  axios.get.mockImplementation(async url=>({data:dataFor(url)}));
  await click(host.querySelector('[data-testid="home-nutrition-progress"] button'));
  expect(host.textContent).not.toContain("Alimentação indisponível");
  expect(host.querySelector('[role="progressbar"][aria-label="Progresso de hidratação"]').getAttribute("aria-valuenow")).toBe("25");
  expect(host.querySelector('[data-testid="hydration-add-250"]')).not.toBeNull();
});

test("a failed check-in keeps the dialog and answers until a successful save",async()=>{
  await render(<ReferenceHome db={db} start={()=>{}}/>);
  await click(host.querySelector('[data-testid="home-prontidao"]'));
  axios.post.mockRejectedValueOnce(failure(503));
  await click(document.querySelector('[data-testid="save-today-checkin"]'));
  const dialog=document.querySelector('[role="dialog"]');
  expect(dialog.textContent).toContain("Suas respostas continuam aqui");
  expect(dialog.querySelector('input').value).toBe("4");
  axios.post.mockResolvedValueOnce({data:{checkin:{sleep:4,energy:4}}});
  await click(dialog.querySelector('[data-testid="save-today-checkin"]'));
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(axios.post.mock.calls[1][1].sleep).toBe(4);
});

test("hydration failure preserves the confirmed value and announces an error",async()=>{
  await render(<ReferenceHome db={db} start={()=>{}}/>);
  axios.post.mockRejectedValueOnce(failure(503));
  await click(host.querySelector('[data-testid="hydration-add-250"]'));
  expect(host.querySelector('[data-testid="home-hydration"]').textContent).toContain("0,5 L");
  expect(host.querySelector('[role="alert"]').textContent).toContain("Não foi possível");
});

test("Nutrition never opens onboarding for a server failure and retry preserves the existing plan",async()=>{
  axios.get.mockImplementation(async url=>{if(url.endsWith("/nutrition/plan"))throw failure(503);return {data:{}}});
  await render(<Nutrition API="/api"/>);
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="astra-nutrition"]')).toBeNull();
  axios.get.mockImplementation(async url=>({data:dataFor(url)}));
  await click(host.querySelector('[role="alert"] button'));
  expect(host.querySelector('[data-testid="nutrition-plan-origin"]').textContent).toContain("Dieta importada");
  expect(axios.post).not.toHaveBeenCalled();
});

test("a diary read error does not render an empty consumption summary",async()=>{
  axios.get.mockImplementation(async url=>{if(url.includes("/adherence/"))throw failure(503);return {data:dataFor(url)}});
  await render(<Nutrition API="/api"/>);
  expect(host.textContent).toContain("Não foi possível atualizar os registros");
  expect(host.querySelector('.a6-gauge-panel')).toBeNull();
  axios.get.mockImplementation(async url=>({data:dataFor(url)}));
  await click(host.querySelector('[role="alert"] button'));
  expect(host.querySelector('.a6-gauge-panel')).not.toBeNull();
});

test("Evolution offers retry while independent tabs remain accessible",async()=>{
  const retry=jest.fn();
  await render(<AstraProgress analytics={null} error="Falha na evolução" onRetry={retry} exercises={[]}/>);
  await click(host.querySelector('[role="alert"] button'));
  expect(retry).toHaveBeenCalledTimes(1);
  await click([...host.querySelectorAll('button')].find(x=>x.textContent==="Dieta"));
  expect(host.textContent).toContain("Histórico alimentar");
  expect(host.textContent).not.toContain("Carregando");
});

test("main navigation restores a linked section and handles browser navigation",async()=>{
  function Navigation(){const [section,navigate]=useAppSection();return <><p>{section}</p><button onClick={()=>navigate("Progresso")}>Avançar</button></>}
  window.history.replaceState({},"","/app?view=nutricao");
  await render(<Navigation/>);expect(host.querySelector('p').textContent).toBe("Alimentação");
  await click(host.querySelector('button'));expect(window.location.search).toBe("?view=evolucao");
  await act(async()=>{window.history.replaceState({},"","/app?view=treino");window.dispatchEvent(new PopStateEvent("popstate"))});
  expect(host.querySelector('p').textContent).toBe("Treino");
});
