import {completionForToday,inferredCompletionForToday,sessionStatus} from "./ReferenceHome";

const now=new Date("2026-09-09T18:00:00Z");
test("recovery takes precedence over recent training",()=>{
  expect(sessionStatus({energy:4},[{created_at:now.toISOString()}],now)).toBe("RECUPERAÇÃO REGISTRADA");
});
test("only valid training records in the last seven days activate the rhythm",()=>{
  expect(sessionStatus(null,[{created_at:"2026-09-08T18:00:00Z"}],now)).toBe("RITMO ATIVO");
  expect(sessionStatus(null,[{created_at:"2026-08-01"},{created_at:"invalid"},{created_at:"2026-09-10"}],now)).toBe("PRONTO PARA INICIAR");
  expect(sessionStatus(null,undefined,now)).toBe("PRONTO PARA INICIAR");
});
test("a conclusao de hoje tem prioridade sobre recovery e ritmo",()=>{
  const completion={completed_at:"2026-09-09T17:45:00Z",day:1,label:"Push 1"};
  expect(completionForToday(completion,now)).toBe(completion);
  expect(sessionStatus({energy:4},[{created_at:now.toISOString()}],now,completion)).toBe("TREINO CONCLUÍDO HOJE");
});
test("conclusao antiga nao bloqueia a sessao de hoje",()=>{
  expect(completionForToday({completed_at:"2026-09-08T17:45:00Z",day:1},now)).toBeNull();
});
test("detecta conclusao ja persistida antes deste release pelo avanco da sessao",()=>{
  const program={active_day:2,sessions:[{day:1,label:"Push 1",exercises:[{exercise_id:"a",sets:2}]},{day:2,label:"Pull 1",exercises:[{exercise_id:"b",sets:2}]}]};
  const rows=[{created_at:"2026-09-09T17:40:00Z",session_day:1,exercise_id:"a",set_number:1}];
  expect(inferredCompletionForToday(program,rows,now)).toMatchObject({day:1,label:"Push 1",inferred:true});
});
test("nao confunde treino em andamento com treino concluido",()=>{
  const program={active_day:1,sessions:[{day:1,label:"Push 1",exercises:[{exercise_id:"a",sets:2}]}]};
  const partial=[{created_at:"2026-09-09T17:40:00Z",session_day:1,exercise_id:"a",set_number:1}];
  expect(inferredCompletionForToday(program,partial,now)).toBeNull();
  const complete=[...partial,{created_at:"2026-09-09T17:50:00Z",session_day:1,exercise_id:"a",set_number:2}];
  expect(inferredCompletionForToday(program,complete,now)).toMatchObject({day:1,inferred:true});
});
