import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import ReferenceHome from "./ReferenceHome";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";
import Nutrition from "./Nutrition";
import NutritionDailyFooter from "./NutritionDailyFooter";
import AstraProgress from "./AstraProgress";
import {AstraBottomNav} from "./AstraUI";
import {Profile} from "../App";

jest.mock("axios");
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Fixtures exist only in the test bundle. Production receives these contracts from the API.
const db={profile:{id:"athlete-test",name:"Ana Teste",days:4,session_minutes:55,
  experience:"Intermediário",goal:"Hipertrofia",priorities:["Peitoral superior"],automation_mode:"FORGE_AUTO"},
  exercises:[],program:{active_day:2,week:"Semana 2 de 6",sessions:[
    {day:1,label:"Sessão anterior",exercises:[]},
    {day:2,label:"B — Costas",duration:"55 min",focus:["Costas"],exercises:[{exercise_id:"lat-pulldown",sets:4,reps:"8–10",rir:1}]},
  ]},recent_sets:[]};

let root,host;
beforeEach(()=>{
  jest.resetAllMocks();
  axios.get.mockResolvedValue({data:{}});
  host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);
});
afterEach(async()=>{await act(async()=>root.unmount());host.remove()});
const mount=async node=>act(async()=>{root.render(node)});
const click=async node=>{expect(node).not.toBeNull();await act(async()=>node.click())};
const button=text=>Array.from(host.querySelectorAll("button")).find(x=>x.textContent===text);

test("Home uses the active session, real week and saved recovery check-in",async()=>{
  axios.get.mockImplementation(url=>Promise.resolve({data:url.includes("/recovery/")?{checkin:{energy:3}}:{}}));
  const start=jest.fn();await mount(<ReferenceHome db={db} start={start}/>);
  expect(host.querySelector("h1").textContent).toBe("Seu treino está pronto.");
  expect(host.querySelector('[data-testid="daily-briefing"]').textContent).toContain("Costas");
  expect(host.querySelector('[data-testid="home-training-week"]').textContent).toContain("Semana 2 de 6");
  await click(host.querySelector('[data-testid="start-workout-button"]'));
  expect(start).toHaveBeenCalledTimes(1);
  expect(host.querySelector('[data-testid="today-checkin-modal"]')).toBeNull();
});

test("Home preserves check-in submission and direct session entry",async()=>{
  const start=jest.fn(),updated=jest.fn();
  axios.post.mockResolvedValue({data:{checkin:{energy:4}}});
  await mount(<ReferenceHome db={db} start={start} onRecoveryCheckin={updated}/>);
  await click(host.querySelector('[data-testid="start-workout-button"]'));
  expect(host.querySelector('[data-testid="today-checkin-modal"]')).not.toBeNull();
  await click(host.querySelector('[data-testid="save-today-checkin"]'));
  expect(axios.post).toHaveBeenCalledWith("/api/recovery",expect.objectContaining({profile_id:"athlete-test",energy:4}));
  expect(updated).toHaveBeenCalledWith({checkin:{energy:4}});
  await click(host.querySelector('[data-testid="start-workout-button"]'));
  expect(start).toHaveBeenCalledTimes(1);
});

test("compact workout keeps start, library, warm-up and prescribed RIR",async()=>{
  const start=jest.fn(),library=jest.fn(),session=db.program.sessions[1];
  await mount(<ReferenceWorkoutPreview db={db} activeSession={session} items={session.exercises} onStart={start} onLibrary={library}/>);
  expect(host.querySelector("article").textContent).toContain("4 × 8–10 · RIR 1");
  expect(host.querySelector("article img").getAttribute("src")).toContain("lat-pulldown");
  await click(button("Biblioteca"));expect(library).toHaveBeenCalledTimes(1);
  await click(host.querySelector('[data-testid="workout-preview-start"]'));expect(start).toHaveBeenCalledTimes(1);
  await click(host.querySelector('button[aria-expanded]'));
  expect(host.querySelector('button[aria-expanded]').getAttribute("aria-expanded")).toBe("true");
});

test("nutrition summary refreshes from saved meal data and preserves every meal",async()=>{
  const meals=[{name:"Café da manhã",target_cal:350,foods:[]},{name:"Almoço",target_cal:600,foods:[]},{name:"Lanche",target_cal:200,foods:[]}];
  let logs=[];
  axios.get.mockImplementation(url=>Promise.resolve({data:url.endsWith("/nutrition/plan")?
    {meals,targets:{goal_calories:1900,protein_g:120,carbs_g:210,fat_g:65}}:
    url.includes("/adherence/")?{meals:logs,extras:[]}:
    url.includes("/hydration/")?{total_ml:500,goal_ml:2000}:{}}));
  axios.post.mockImplementation(()=>{logs=[{meal_index:0,status:"completed",actual:{foods:[{name:"Alimento de teste",grams:100}],totals:{kcal:377,protein_g:23,carbs_g:40,fat_g:14}}}];return Promise.resolve({data:{}})});
  await mount(<Nutrition API="/api"/>);
  expect(host.querySelectorAll(".a6-meal-details")).toHaveLength(3);
  await click(host.querySelector(".a6-meal-details summary"));
  await click(host.querySelector('[data-testid="meal-complete-0"]'));
  expect(axios.post).toHaveBeenCalledWith("/api/nutrition/meal-status",expect.objectContaining({meal_index:0,status:"completed"}));
  expect(host.querySelector(".a6-gauge-label strong").textContent).toBe("377");
  expect(host.querySelector(".a6-next h3").textContent).toBe("Almoço");
  expect(host.querySelector(".a6-meal-details summary").textContent).toContain("377 kcal");
  expect(host.querySelectorAll(".a6-meal img")).toHaveLength(3);
});

test("compact hydration uses server totals, undo and errors without optimistic fake totals",async()=>{
  axios.get.mockResolvedValue({data:{total_ml:500,goal_ml:2100}});
  axios.post.mockResolvedValue({data:{total_ml:750,goal_ml:2100}});
  axios.delete.mockResolvedValue({data:{total_ml:500,goal_ml:2100}});
  await mount(<NutritionDailyFooter API="/api" compact consumed={{kcal:0}}/>);
  await click(button("+250 ml"));expect(host.textContent).toContain("0,75 L");
  await click(host.querySelector("summary"));await click(button("Desfazer último registro"));
  expect(axios.delete).toHaveBeenCalledWith(expect.stringMatching(/\/hydration\/.*\/last$/));
  expect(host.textContent).toContain("0,5 L");
  axios.post.mockRejectedValue(new Error("offline"));await click(button("+500 ml"));
  expect(host.querySelector('[role="alert"]').textContent).toContain("Não foi possível confirmar");
  expect(host.querySelector(".a6-water-strip").textContent).toContain("0,5 L");
});

test("progress reflects the real exercise history and opens existing weight and photo controls",async()=>{
  const recent=new Date(Date.now()-86400000).toISOString(),today=new Date().toISOString();
  axios.get.mockResolvedValue({data:{history:[
    {session_id:"s1",created_at:recent,weight:80,reps:8},
    {session_id:"s2",created_at:today,weight:40,reps:10},
  ]}});
  const analytics={prs:[{exercise:"Supino",weight:80}],adherence_calendar:[],body_trend:[]};
  await mount(<AstraProgress API="/api" profileId="athlete-test" exercises={[{id:"supino",name:"Supino"}]} analytics={analytics} weightPanel={<button>Registrar peso real</button>} photosPanel={<button>Adicionar fotos</button>}/>);
  expect(host.querySelector('[data-testid="progress-hero"]').textContent).toContain("40 kg");
  expect(host.querySelector('svg[aria-label="Histórico de cargas por sessão"]')).not.toBeNull();
  await click(button("Peso"));expect(button("Registrar peso real")).toBeDefined();
  await click(button("Fotos"));expect(button("Adicionar fotos")).toBeDefined();
  axios.get.mockResolvedValue({data:{history:[]}});
  await mount(<AstraProgress key="empty" API="/api" profileId="athlete-test" exercises={[{id:"supino",name:"Supino"}]} analytics={{prs:[]}}/>);
  expect(host.textContent).toContain("Sem séries registradas neste período");
  expect(host.textContent).not.toContain("NaN");
});

test("profile keeps editors behind the approved rows and preserves account actions",async()=>{
  const builder=jest.fn(),manual=jest.fn(),redo=jest.fn(),plans=jest.fn(),analysis=jest.fn();
  await mount(<Profile db={db} user={{plan:"PRO",status:"ACTIVE"}} openBuilder={builder} openManual={manual} redo={redo} openPlans={plans} openAnalysis={analysis}/>);
  expect(host.querySelector('[data-testid="training-preferences"]')).toBeNull();
  await click(host.querySelector('[data-testid="profile-training-preferences"]'));
  expect(host.querySelector('[data-testid="training-preferences"]')).not.toBeNull();
  await click(Array.from(host.querySelectorAll("button")).find(x=>x.querySelector("h3")?.textContent==="Meu programa"));
  await click(host.querySelector('[data-testid="open-builder-button"]'));expect(builder).toHaveBeenCalledTimes(1);
  await click(host.querySelector('[data-testid="open-manual-button"]'));expect(manual).toHaveBeenCalledTimes(1);
  await click(Array.from(host.querySelectorAll("button")).find(x=>x.querySelector("h3")?.textContent==="Avaliação física"));
  await click(host.querySelector('[data-testid="redo-assessment-button"]'));expect(redo).toHaveBeenCalledTimes(1);
  await click(host.querySelector('[data-testid="open-plans-button"]'));expect(plans).toHaveBeenCalledTimes(1);
  await click(host.querySelector('[data-testid="open-analysis-button"]'));expect(analysis).toHaveBeenCalledTimes(1);
});

test("all five bottom navigation destinations use the existing route keys",async()=>{
  const change=jest.fn();await mount(<AstraBottomNav tab="Hoje" onChange={change}/>);
  expect(host.querySelector('[aria-current="page"]').textContent).toBe("Início");
  for(const node of host.querySelectorAll("button"))await click(node);
  expect(change.mock.calls.map(x=>x[0])).toEqual(["Hoje","Treino","Alimentação","Progresso","Perfil"]);
});
