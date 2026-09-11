import React,{act} from "react";
import {createRoot} from "react-dom/client";
import {renderToStaticMarkup} from "react-dom/server";
import axios from "axios";
import {completionForToday,nextSessionAfter,useWorkoutCompletion} from "./workoutCompletionState";
import CompletedWorkout from "./CompletedWorkout";
import {completionStorageKey} from "./completeWorkout";
jest.mock("axios");
const today=new Date(2026,8,10,12),completed={day:1,label:"Push 1",completed_at:today.toISOString(),summary:{completed_sets:12,total_sets:12,duration_seconds:1800}};
const program={active_day:2,sessions:[{day:1,label:"Push 1",exercises:[{exercise_id:"bench",sets:3,reps:"8"}]},{day:2,label:"Pull 1",exercises:[{exercise_id:"row",sets:3,reps:"8"}]}]};
beforeEach(()=>{jest.useFakeTimers().setSystemTime(today);localStorage.clear();axios.get.mockReset();global.IS_REACT_ACT_ENVIRONMENT=true;});
afterEach(()=>{jest.useRealTimers();});
test("completion expires on the next local day and next preview follows program sequence",()=>{
 expect(completionForToday(completed,today)).toEqual(completed);
 expect(completionForToday(completed,new Date(2026,8,11,0,1))).toBeNull();
 expect(nextSessionAfter(program,{...completed,next_session_status:"confirmed",next_session:program.sessions[1]}).label).toBe("Pull 1");
 expect(nextSessionAfter(program,{day:2})).toBeNull();
 expect(nextSessionAfter({sessions:[program.sessions[0]]},completed)).toBeNull();
 expect(nextSessionAfter({},completed)).toBeNull();
});
test("completed screen has collapsed summaries and no start action",()=>{
 const html=renderToStaticMarkup(<CompletedWorkout db={{program,profile:{id:"u"},exercises:[]}} completion={{...completed,next_session_status:"confirmed",next_session:program.sessions[1]}}/>);
 const doc=new DOMParser().parseFromString(html,"text/html");
 expect(doc.body.textContent).toContain("CONCLUÍDO HOJE");
 expect(doc.body.textContent).toContain("Pull 1");
 expect(doc.body.textContent).toContain("12 séries registradas");
 expect(doc.querySelectorAll("details")).toHaveLength(3);
 expect(doc.querySelector("details[open]")).toBeNull();
 expect(doc.body.textContent).not.toContain("Iniciar");
});
test("server completion restores state after fresh login and expires without reload",async()=>{
 axios.get.mockResolvedValue({data:{completion:completed}});
 const host=document.createElement("div"),root=createRoot(host);
 function Probe(){const r=useWorkoutCompletion({userId:"u",program,API:"/api"});return <p>{r.completion?.label||r.status}</p>;}
 await act(async()=>root.render(<Probe/>));
 expect(host.textContent).toBe("Push 1");
 expect(axios.get).toHaveBeenCalledWith("/api/workout/completion",{params:{profile_id:"u"}});
 await act(async()=>{jest.setSystemTime(new Date(2026,8,11,0,1));jest.advanceTimersByTime(60000);});
 expect(host.textContent).toBe("ready");
 act(()=>root.unmount());
});
test("completion event updates both mounted consumers and errors remain explicit",async()=>{
 axios.get.mockResolvedValueOnce({data:{completion:null}}).mockResolvedValueOnce({data:{completion:null}});
 const host=document.createElement("div"),root=createRoot(host);
 function Probe(){const r=useWorkoutCompletion({userId:"u",program,API:"/api"});return <p>{r.completion?.label||r.status}</p>;}
 await act(async()=>root.render(<><Probe/><Probe/></>));
 localStorage.setItem(completionStorageKey("u"),JSON.stringify(completed));
 axios.get.mockResolvedValue({data:{completion:completed}});
 await act(async()=>window.dispatchEvent(new Event("forge:workout-complete")));
 expect(host.textContent).toBe("Push 1Push 1");
 act(()=>root.unmount());
 const root2=createRoot(host);localStorage.clear();axios.get.mockRejectedValue(new Error("offline"));
 await act(async()=>root2.render(<Probe/>));
 expect(host.textContent).toBe("error");
 act(()=>root2.unmount());
});

test("does not rotate stale day numbers or guess a category after a program edit",()=>{
 const stale={...completed,day:3,label:"Push Ombros",next_session_status:"program_changed"};
 expect(nextSessionAfter(program,stale)).toBeNull();
 const doc=new DOMParser().parseFromString(renderToStaticMarkup(<CompletedWorkout db={{program,profile:{},exercises:[]}} completion={stale}/>),"text/html");
 expect(doc.querySelector(".completed-next-card").textContent).toContain("PROGRAMA ATUAL");
 expect(doc.querySelector(".completed-next-card").textContent).toContain("Pull 1");
 expect(doc.querySelector(".completed-workout-card").textContent).toContain("Push Ombros");
});
test("server next session overrides a stale browser program",()=>{
 const serverPull={day:2,label:"Pull 1",exercises:[]};
 expect(nextSessionAfter({active_day:1,sessions:[{day:1,label:"Push 1"}]},{
 ...completed,next_session_status:"confirmed",next_session:serverPull})).toBe(serverPull);
});

test("saved program changes immediately without replacing completion or enabling another workout",async()=>{
 const host=document.createElement("div"),root=createRoot(host),db={program,profile:{},exercises:[]};
 await act(async()=>root.render(<CompletedWorkout db={db} completion={completed}/>));
 const updated={name:"Upper + Full Body",active_day:1,sessions:[{day:1,label:"Upper A",exercises:[]},{day:2,label:"Full Body A",exercises:[]},{day:3,label:"Upper B",exercises:[]}]};
 await act(async()=>root.render(<CompletedWorkout db={{...db,program:updated}} completion={completed}/>));
 const preview=host.querySelector('[data-testid="saved-program-preview"]');
 expect(preview.textContent).toContain("Upper + Full Body");
 expect(preview.textContent).toContain("Full Body A");
 expect(preview.textContent).toContain("Upper B");
 expect(preview.textContent).not.toContain("Push 1");
 expect(host.querySelector(".completed-workout-card").textContent).toContain("Push 1");
 expect(host.textContent).not.toContain("Iniciar");
 act(()=>root.unmount());
});
