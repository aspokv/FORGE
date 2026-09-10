import React,{act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import ExerciseEvolution,{evolutionPoints} from "./ExerciseEvolution";
import AstraProgress from "./AstraProgress";
import {AstraBottomNav} from "./AstraUI";
jest.mock("axios");
const now=Date.parse("2026-09-10T12:00:00Z");
const rows=[
 {created_at:"2026-09-09T10:00:00Z",weight:40,reps:8,session_id:"b"},
 {created_at:"2026-09-01T10:00:00Z",weight:30,reps:10,session_id:"a"},
 {created_at:"2026-09-09T10:02:00Z",weight:40,reps:10,session_id:"b"}
];
const exercises=[{id:"row",name:"Remada"},{id:"press",name:"Supino"}];
let host,root;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;jest.spyOn(Date,"now").mockReturnValue(now);localStorage.clear();axios.get.mockReset();host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();jest.restoreAllMocks();});
const render=async element=>{await act(async()=>{root.render(element);});};
const click=async element=>{await act(async()=>{element.click();});};
const change=async(element,value)=>{await act(async()=>{const proto=element.tagName==="SELECT"?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,"value").set.call(element,value);element.dispatchEvent(new Event(element.tagName==="SELECT"?"change":"input",{bubbles:true}));});};
const button=text=>[...host.querySelectorAll("button")].find(b=>b.textContent===text);
test("groups sessions chronologically, filters dates and retains associated reps",()=>{
 expect(evolutionPoints(rows,28,now).map(p=>[p.weight,p.reps,p.sets])).toEqual([[30,10,1],[40,10,2]]);
 expect(evolutionPoints([{created_at:"invalid",weight:40,reps:8},{created_at:"2026-01-01",weight:20,reps:8}],28,now)).toEqual([]);
 expect(evolutionPoints([{created_at:"2026-01-01",weight:0,reps:8}],0,now)).toHaveLength(1);
});
test("loads history, scrubs sessions, changes exercise and saves a scoped favorite",async()=>{
 axios.get.mockResolvedValue({data:{history:rows}});
 await render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 expect(host.querySelector(".evolution-reading").textContent).toContain("40 kg");
 await change(host.querySelector('input[type="range"]'),"0");
 expect(host.querySelector(".evolution-reading").textContent).toContain("30 kg");
 expect(host.querySelector(".evolution-reading").textContent).toContain("01/09/2026");
 await click(host.querySelector('[aria-label="Favoritar exercício"]'));
 expect(localStorage.getItem("forge:evolution:favorite:one")).toBe("row");
 await change(host.querySelector("select"),"press");
 expect(axios.get).toHaveBeenLastCalledWith("/api/exercise-history/press");
});
test("retries failed requests and renders empty state without fabricated points",async()=>{
 axios.get.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({data:{history:[]}});
 await render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 expect(host.querySelector('[role="alert"]')).not.toBeNull();
 await click(button("Tentar novamente"));
 expect(host.textContent).toContain("Sem séries registradas");
 expect(host.querySelector('input[type="range"]')).toBeNull();
});
test("ignores late responses for previously selected exercises",async()=>{
 let resolveFirst;
 axios.get.mockImplementationOnce(()=>new Promise(resolve=>{resolveFirst=resolve;})).mockResolvedValueOnce({data:{history:[]}});
 await render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 await change(host.querySelector("select"),"press");
 await act(async()=>{resolveFirst({data:{history:rows}});});
 expect(host.textContent).toContain("Sem séries registradas");
 expect(host.querySelector(".evolution-reading")).toBeNull();
});
test("period filters include older available records only when selected",async()=>{
 axios.get.mockResolvedValue({data:{history:[...rows,{created_at:"2026-06-01T10:00:00Z",weight:20,reps:8}]}});
 await render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 expect(host.querySelector('input[type="range"]').max).toBe("1");
 await click(button("Disponível"));
 expect(host.querySelector('input[type="range"]').max).toBe("2");
});
test("renames visible page and navigation and retains weight, photos and consistency",async()=>{
 const onChange=jest.fn();
 await render(<><AstraBottomNav tab="Progresso" onChange={onChange}/><AstraProgress analytics={{prs:[],adherence_calendar:[]}} exercises={[]} weightPanel={<p>Registro de peso</p>} photosPanel={<p>Fotos pessoais</p>}/></>);
 expect(host.querySelector("h1").textContent).toBe("Evolução.");
 await click(button("Evolução"));expect(onChange).toHaveBeenCalledWith("Progresso");
 expect(host.textContent).toContain("Consistência");
 await click(button("Peso"));expect(host.textContent).toContain("Registro de peso");
 await click(button("Fotos"));expect(host.textContent).toContain("Fotos pessoais");
});
