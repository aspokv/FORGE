import { dataDoCabecalho, dataPorExtenso, rotuloDoModo, rotuloDoPlano, rotuloDaSituacao } from "./rotulos";

/**
 * Dois defeitos que estes testes travam, os dois vistos em producao.
 *
 * O cabecalho trazia `06 JUN 2026` escrito no codigo — uma data falsa em toda aba, todo
 * dia. Num produto de acompanhamento, isso e pior que feio: faz o resto parecer maquete.
 *
 * E o Perfil mostrava `FORGE_AUTO` como titulo. Constante de banco na tela denuncia que
 * ninguem traduziu o sistema para a lingua de quem usa.
 */

test("a data do cabecalho e a de hoje, e nao uma constante", () => {
  const hoje = new Date();
  const texto = dataDoCabecalho(hoje);
  expect(texto).toContain(String(hoje.getDate()).padStart(2, "0"));
  // A data que estava cravada no codigo nao pode voltar por nenhum caminho.
  expect(texto).not.toContain("2026");
  expect(texto.toUpperCase()).not.toContain("06 JUN 2026");
});

test("datas diferentes produzem textos diferentes", () => {
  expect(dataDoCabecalho(new Date(2025, 0, 15))).not.toBe(dataDoCabecalho(new Date(2025, 5, 20)));
});

test("a versao por extenso comeca com maiuscula e sem 'feira'", () => {
  const t = dataPorExtenso(new Date(2025, 8, 3)); // uma quarta-feira
  expect(t[0]).toBe(t[0].toUpperCase());
  expect(t).not.toContain("feira");
});

test("data invalida devolve vazio em vez de 'Invalid Date'", () => {
  expect(dataDoCabecalho("nao e data")).toBe("");
  expect(dataPorExtenso(undefined && "x")).not.toContain("Invalid");
});

test("os modos de programacao viram portugues", () => {
  expect(rotuloDoModo("FORGE_AUTO")).toBe("Programação automática");
  expect(rotuloDoModo("FORGE_PRO")).toBe("Programação manual");
  expect(rotuloDoModo("FORGE_ASSISTED")).toBe("Programação assistida");
});

test("plano e situacao viram portugues", () => {
  expect(rotuloDoPlano("ELITE")).toBe("Elite");
  expect(rotuloDaSituacao("ACTIVE")).toBe("Ativo");
  expect(rotuloDaSituacao("PENDING_PAYMENT")).toBe("Pagamento pendente");
});

test("chave desconhecida sai legivel, e nao gritando nem vazia", () => {
  // Uma chave nova no backend nao pode abrir um buraco na interface — nem exibir
  // `MODO_EXPERIMENTAL` em caixa alta no meio da tela.
  expect(rotuloDoModo("MODO_EXPERIMENTAL")).toBe("Modo experimental");
  expect(rotuloDaSituacao("")).toBe("");
  expect(rotuloDoModo(null)).toBe("");
});

test("nenhum rotulo conhecido devolve sublinhado", () => {
  ["FORGE_AUTO", "FORGE_PRO", "FORGE_ASSISTED"].forEach((k) =>
    expect(rotuloDoModo(k)).not.toContain("_")
  );
  ["ACTIVE", "PENDING_PAYMENT", "SUSPENDED"].forEach((k) =>
    expect(rotuloDaSituacao(k)).not.toContain("_")
  );
});
