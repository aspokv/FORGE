import React from "react";
import {render,screen,fireEvent,waitFor} from "@testing-library/react";
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
beforeEach(()=>{jest.spyOn(Date,"now").mockReturnValue(now);localStorage.clear();axios.get.mockReset();});
afterEach(()=>jest.restoreAllMocks());
test("groups sessions chronologically and keeps reps attached to the selected load",()=>{
 expect(evolutionPoints(rows,28,now).map(p=>[p.weight,p.reps,p.sets])).toEqual([[30,10,1],[40,10,2]]);
 expect(evolutionPoints([{created_at:"invalid",weight:40,reps:8},{created_at:"2026-01-01",weight:20,reps:8}],28,now)).toEqual([]);
 expect(evolutionPoints([{created_at:"2026-01-01",weight:0,reps:8}],0,now)).toHaveLength(1);
});
test("loads real history, scrubs dates, changes exercise and saves a scoped favorite",async()=>{
 axios.get.mockResolvedValue({data:{history:rows}});
 render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 await screen.findByText("10 repetições na série de maior carga");
 fireEvent.change(screen.getByRole("slider"),{target:{value:"0"}});
 expect(screen.getByText(/1 séries registradas/)).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Favoritar exercício"}));
 expect(localStorage.getItem("forge:evolution:favorite:one")).toBe("row");
 fireEvent.change(screen.getByLabelText("Exercício"),{target:{value:"press"}});
 await waitFor(()=>expect(axios.get).toHaveBeenLastCalledWith("/api/exercise-history/press"));
});
test("displays errors with retry and does not fabricate empty data",async()=>{
 axios.get.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({data:{history:[]}});
 render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 fireEvent.click(await screen.findByText("Tentar novamente"));
 await screen.findByText(/Sem séries registradas/);
 expect(screen.queryByRole("slider")).toBeNull();
});
test("ignores a late response after exercise selection changes",async()=>{
 let resolveFirst;
 axios.get.mockImplementationOnce(()=>new Promise(resolve=>{resolveFirst=resolve;})).mockResolvedValueOnce({data:{history:[]}});
 render(<ExerciseEvolution API="/api" profileId="one" exercises={exercises}/>);
 fireEvent.change(screen.getByLabelText("Exercício"),{target:{value:"press"}});
 await screen.findByText(/Sem séries registradas/);
 resolveFirst({data:{history:rows}});
 await waitFor(()=>expect(screen.queryByRole("slider")).toBeNull());
});
test("renames the visible page and navigation while keeping weight, photos and consistency",()=>{
 const change=jest.fn();
 render(<><AstraBottomNav tab="Progresso" onChange={change}/><AstraProgress analytics={{prs:[],adherence_calendar:[]}} exercises={[]} weightPanel={<p>Registro de peso</p>} photosPanel={<p>Fotos pessoais</p>}/></>);
 expect(screen.getByRole("heading",{name:"Evolução."})).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Evolução"}));expect(change).toHaveBeenCalledWith("Progresso");
 expect(screen.getByText("Consistência")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Peso"}));expect(screen.getByText("Registro de peso")).toBeTruthy();
 fireEvent.click(screen.getByRole("button",{name:"Fotos"}));expect(screen.getByText("Fotos pessoais")).toBeTruthy();
});
