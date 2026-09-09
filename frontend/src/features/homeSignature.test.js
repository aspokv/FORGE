import {sessionStatus} from "./ReferenceHome";

const now=new Date("2026-09-09T18:00:00Z");
test("recovery takes precedence over recent training",()=>{
  expect(sessionStatus({energy:4},[{created_at:now.toISOString()}],now)).toBe("RECUPERAÇÃO REGISTRADA");
});
test("only valid training records in the last seven days activate the rhythm",()=>{
  expect(sessionStatus(null,[{created_at:"2026-09-08T18:00:00Z"}],now)).toBe("RITMO ATIVO");
  expect(sessionStatus(null,[{created_at:"2026-08-01"},{created_at:"invalid"},{created_at:"2026-09-10"}],now)).toBe("PRONTO PARA INICIAR");
  expect(sessionStatus(null,undefined,now)).toBe("PRONTO PARA INICIAR");
});
