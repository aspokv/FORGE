import {mensagemDeErro, ehFaltaDePlano} from "./mensagemDeErro";

/*
 * Este modulo e o unico caminho entre um erro de rede e a tela. O contrato e curto e
 * absoluto: SEMPRE devolve string. Um objeto escapando daqui vira tela preta — foi
 * exatamente isso que aconteceu na troca de objetivo para Agressivo.
 */

const erro = (detail, status = 400) => ({response: {status, data: {detail}}});

test("detalhe em texto passa direto", () => {
  expect(mensagemDeErro(erro("Faltam dados do peso."))).toBe("Faltam dados do peso.");
});

test("o 402 do plano: o texto sai de dentro do objeto", () => {
  const e = erro({message: "Seu plano não inclui protocolos agressivos.",
                  capability: "protocolos_agressivos", current_plan: "essencial",
                  upgrade: {plan: "pro"}}, 402);
  expect(mensagemDeErro(e)).toBe("Seu plano não inclui protocolos agressivos.");
});

test("objeto SEM mensagem cai na reserva — nunca no objeto", () => {
  const saida = mensagemDeErro(erro({capability: "alimentacao", upgrade: {plan: "pro"}}, 402),
                               "Não deu certo.");
  expect(typeof saida).toBe("string");
  expect(saida).toBe("Não deu certo.");
});

test("erro de validacao do FastAPI: mostra o primeiro problema, nao a lista crua", () => {
  const e = erro([{loc: ["body", "peso"], msg: "field required", type: "value_error"}], 422);
  expect(mensagemDeErro(e)).toBe("field required");
});

test("mensagem solta fora de detail ainda e aproveitada", () => {
  expect(mensagemDeErro({response: {status: 500, data: {message: "Servidor fora do ar."}}}))
    .toBe("Servidor fora do ar.");
});

test.each([
  ["sem resposta nenhuma", {}],
  ["erro de rede puro", new Error("Network Error")],
  ["indefinido", undefined],
  ["detalhe vazio", erro("   ")],
  ["detalhe nulo", erro(null)],
  ["lista vazia", erro([])],
])("%s devolve a reserva, e sempre uma string", (_, e) => {
  const saida = mensagemDeErro(e, "Reserva.");
  expect(typeof saida).toBe("string");
  expect(saida).toBe("Reserva.");
});

test("falta de plano se reconhece pelo 402", () => {
  expect(ehFaltaDePlano(erro({message: "x"}, 402))).toBe(true);
  expect(ehFaltaDePlano(erro("qualquer coisa", 400))).toBe(false);
  expect(ehFaltaDePlano(erro({upgrade: {plan: "pro"}}, 400))).toBe(true);
  expect(ehFaltaDePlano(undefined)).toBe(false);
});
