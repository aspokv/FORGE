import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {scheduledProgram} from "./workoutCalendar";
import ReferenceHome from "./ReferenceHome";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";
import CompletedWorkout from "./CompletedWorkout";

const program={active_day:1,name:"Upper + Full Body",calendar:{weekdays:{"1":0,"2":1,"3":2,"4":4,"5":5,"6":6}},
 sessions:["Segunda · Upper A","Terça · Full Body A","Quarta · Upper B","Sexta · Upper C","Sábado · Full Body B","Domingo · Upper D"].map((label,i)=>({day:i+1,label,exercises:[]}))};
const html=element=>new DOMParser().parseFromString(renderToStaticMarkup(element),"text/html");
beforeEach(()=>{jest.useFakeTimers("modern");jest.setSystemTime(new Date(2026,8,11,5,10));localStorage.clear();});
afterEach(()=>{jest.useRealTimers();localStorage.clear();});

test("Friday selects Upper C without overwriting the saved pointer",()=>{
 const p=scheduledProgram(program,new Date(2026,8,11));
 expect(p.active_day).toBe(4);
 expect(p.session).toBe("Sexta · Upper C");
 expect(program.active_day).toBe(1);
});
test("Thursday is rest and Sunday wraps to Monday",()=>{
 const p=scheduledProgram(program,new Date(2026,8,10));
 expect(p.rest_day).toBe(true);
 expect(p.active_day).toBeNull();
 expect(p.calendar.next.day).toBe(4);
 expect(scheduledProgram(program,new Date(2026,8,13),true).calendar.next.day).toBe(1);
});
test("unlabelled programs retain sequential progression",()=>{
 const p={active_day:2,sessions:[{day:1,label:"Push"},{day:2,label:"Pull"}]};
 expect(scheduledProgram(p)).toBe(p);
});
test("Home and workout preview show Friday, not Monday",()=>{
 const db={profile:{id:"calendar-athlete"},program};
 const home=html(<ReferenceHome db={db} start={()=>{}}/>);
 expect(home.querySelector("#home-session-title").textContent).toBe("Sexta · Upper C");
 const p=scheduledProgram(program),session=p.sessions.find(s=>s.day===p.active_day);
 const preview=html(<ReferenceWorkoutPreview db={{...db,program:p}} activeSession={session}/>);
 expect(preview.querySelector("h2").textContent).toBe("Sexta · Upper C");
 expect(home.querySelector('[data-testid="start-workout-button"]').disabled).toBe(false);
});
test("rest day has no start action on Home or workout preview",()=>{
 jest.setSystemTime(new Date(2026,8,10,5,10));
 const p=scheduledProgram(program),db={profile:{id:"calendar-athlete"},program:p};
 const home=html(<ReferenceHome db={db}/>);
 expect(home.querySelector('[data-testid="start-workout-button"]').disabled).toBe(true);
 expect(home.body.textContent).toContain("DESCANSO HOJE");
 const preview=html(<ReferenceWorkoutPreview db={db}/>);
 expect(preview.querySelector('[data-testid="workout-rest-day"]')).not.toBeNull();
 expect(preview.querySelector('[data-testid="workout-preview-start"]')).toBeNull();
});
test("completed Friday preserves history and previews Saturday",()=>{
 const doc=html(<CompletedWorkout db={{program}} completion={{label:"Sexta · Upper C",completed_at:"2026-09-11T10:00:00Z"}}/>);
 expect(doc.querySelector(".completed-workout-card h2").textContent).toBe("Sexta · Upper C");
 expect(doc.querySelector('[data-testid="saved-program-preview"] h2').textContent).toBe("Sábado · Full Body B");
});
