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
 expect(home.querySelector("#home-session-title").textContent).toBe("Upper C");
 const p=scheduledProgram(program),session=p.sessions.find(s=>s.day===p.active_day);
 const preview=html(<ReferenceWorkoutPreview db={{...db,program:p}} activeSession={session}/>);
 expect(preview.querySelector("h2").textContent).toBe("Sexta · Upper C");
 expect(home.querySelector('[data-testid="start-workout-button"]').disabled).toBe(false);
});
test("rest day offers consultation without a session start action",()=>{
 jest.setSystemTime(new Date(2026,8,10,5,10));
 const p=scheduledProgram(program),db={profile:{id:"calendar-athlete"},program:p};
 const home=html(<ReferenceHome db={db}/>);
 expect(home.querySelector('[data-testid="start-workout-button"]').textContent).toContain("Consultar próximo treino");
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

/*
 * As trocas de dia, no recálculo do cliente.
 *
 * Este recálculo existe para o aplicativo aberto atravessar a meia-noite e virar o dia
 * sozinho — e é por isso que é ELE, e não o servidor, quem decide `rest_day` na tela.
 *
 * Quando a troca de dia foi implementada, isso virou uma armadilha silenciosa: o servidor
 * respondia `rest_day:false` com a sessão adiantada, e esta função escrevia "descanso" por
 * cima, porque decidia pelo dia da SEMANA e a troca fala de DATA. Medido no navegador: a
 * troca ficava gravada, a tela escrevia "Dia trocado", e o treino não aparecia.
 */
describe("trocar o dia de treino", () => {
  // Quinta 24/09/2026 é descanso neste programa; sábado 26/09 tem a Full Body B.
  const comTroca = {...program, calendar: {...program.calendar,
    trocas: [{treinar_em: "2026-09-24", descansar_em: "2026-09-26"}]}};
  const quinta = new Date(2026, 8, 24, 9, 0);
  const sabado = new Date(2026, 8, 26, 9, 0);

  test("sem troca, a quinta continua sendo descanso", () => {
    expect(scheduledProgram(program, quinta).rest_day).toBe(true);
  });

  test("a quinta recebe a sessão do sábado", () => {
    const r = scheduledProgram(comTroca, quinta);
    expect(r.rest_day).toBe(false);
    expect(r.session).toBe("Sábado · Full Body B");
    expect(r.active_day).toBe(5);
  });

  // A outra ponta. Sem ela o atleta faria a mesma sessão duas vezes na semana.
  test("e o sábado vira descanso", () => {
    const r = scheduledProgram(comTroca, sabado);
    expect(r.rest_day).toBe(true);
    expect(r.session).toBe("Descanso");
  });

  test("os outros dias não se mexem", () => {
    expect(scheduledProgram(comTroca, new Date(2026, 8, 25, 9, 0)).session)
      .toBe("Sexta · Upper C");
    expect(scheduledProgram(comTroca, new Date(2026, 8, 27, 9, 0)).session)
      .toBe("Domingo · Upper D");
  });

  // Uma troca vale para as duas datas dela e mais nada: a quinta da semana seguinte
  // continua sendo descanso, senão a exceção viraria um programa paralelo.
  test("a troca não se repete na semana seguinte", () => {
    expect(scheduledProgram(comTroca, new Date(2026, 9, 1, 9, 0)).rest_day).toBe(true);
  });

  // A próxima sessão precisa pular o dia que cedeu o treino, senão a tela de descanso
  // anuncia um treino que não vai acontecer naquele dia.
  test("a próxima sessão pula o dia que virou descanso", () => {
    const r = scheduledProgram(comTroca, sabado);
    expect(r.calendar.next.label).toBe("Domingo · Upper D");
    expect(r.calendar.next_date).toBe("2026-09-27");
  });

  test.each([
    ["ausente", undefined], ["vazia", []], ["com lixo", [null, {}, {treinar_em: "2026-09-24"}]],
  ])("lista de trocas %s não quebra o programa", (_r, trocas) => {
    const p = {...program, calendar: {...program.calendar, trocas}};
    expect(scheduledProgram(p, quinta).rest_day).toBe(true);
  });
});
