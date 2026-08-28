import {
  PASSOS,
  PASSO_PLANO,
  PASSO_DADOS,
  PASSO_PAGAMENTO,
  avaliarSenha,
  emailParece,
  explicarErro,
  montarRetomada,
  passoAnterior,
  proximoPasso,
  validarCodigo,
  validarDados,
} from "./signupSteps";

const erroDe = (status, detail) => ({ response: { status, data: { detail } } });

describe("ordem dos passos", () => {
  test("o plano vem antes dos dados: a escolha precede a conta", () => {
    expect(PASSOS[0]).toBe(PASSO_PLANO);
    expect(PASSOS.indexOf(PASSO_PLANO)).toBeLessThan(PASSOS.indexOf(PASSO_DADOS));
  });

  test("avanca um passo por vez e para no fim", () => {
    expect(proximoPasso(PASSO_PLANO)).toBe(PASSO_DADOS);
    expect(proximoPasso(PASSO_PAGAMENTO)).toBe(PASSO_PAGAMENTO);
  });

  test("volta um passo e para no comeco", () => {
    expect(passoAnterior(PASSO_DADOS)).toBe(PASSO_PLANO);
    expect(passoAnterior(PASSO_PLANO)).toBe(PASSO_PLANO);
  });

  test("passo desconhecido nao quebra a navegacao", () => {
    expect(proximoPasso("inventado")).toBe("inventado");
  });
});

describe("dados da pessoa", () => {
  const bom = { name: "Ana Souza", email: "ana@example.com", acceptTerms: true };

  test("aceita dados completos", () => {
    expect(validarDados(bom).ok).toBe(true);
  });

  test("sem aceite dos termos nao passa", () => {
    const r = validarDados({ ...bom, acceptTerms: false });
    expect(r.ok).toBe(false);
    expect(r.erros.acceptTerms).toBeTruthy();
  });

  test("nome de uma letra nao passa", () => {
    expect(validarDados({ ...bom, name: "A" }).ok).toBe(false);
  });

  test("nome so com espacos nao passa", () => {
    expect(validarDados({ ...bom, name: "   " }).ok).toBe(false);
  });

  test("e-mail sem dominio nao passa", () => {
    expect(validarDados({ ...bom, email: "ana@" }).ok).toBe(false);
  });

  test("chamada sem argumento nenhum nao explode", () => {
    expect(validarDados().ok).toBe(false);
  });

  test("e-mails validos comuns sao aceitos", () => {
    ["a.b@c.com.br", "nome+tag@dominio.io", "x_y@sub.dominio.org"].forEach((e) =>
      expect(emailParece(e)).toBe(true)
    );
  });

  test("e-mails invalidos sao recusados", () => {
    ["", "sem-arroba", "a@b", "a b@c.com", null].forEach((e) =>
      expect(emailParece(e)).toBe(false)
    );
  });
});

describe("codigo de seis digitos", () => {
  test("aceita exatamente seis digitos", () => {
    expect(validarCodigo("123456")).toBe(true);
    expect(validarCodigo(" 123456 ")).toBe(true);
  });

  test("recusa tamanho errado ou letras", () => {
    ["12345", "1234567", "12345a", "", null].forEach((c) =>
      expect(validarCodigo(c)).toBe(false)
    );
  });
});

describe("forca da senha", () => {
  test("senha completa e aceita", () => {
    expect(avaliarSenha("Treino2026").ok).toBe(true);
  });

  test("senha longa e classificada como forte", () => {
    expect(avaliarSenha("Treino2026Forge").nivel).toBe("forte");
  });

  test("curta demais e recusada e diz o porque", () => {
    const r = avaliarSenha("Ab1");
    expect(r.ok).toBe(false);
    expect(r.problemas).toContain("pelo menos 8 caracteres");
  });

  test("so numeros nao passa", () => {
    expect(avaliarSenha("12345678").problemas).toContain("pelo menos uma letra");
  });

  test("so letras nao passa", () => {
    expect(avaliarSenha("abcdefgh").problemas).toContain("pelo menos um número");
  });

  test("caractere repetido nao passa", () => {
    expect(avaliarSenha("aaaaaaaa").ok).toBe(false);
  });

  test("senha que contem o e-mail nao passa", () => {
    const r = avaliarSenha("anasouza123", { email: "anasouza@example.com" });
    expect(r.ok).toBe(false);
    expect(r.problemas.join(" ")).toContain("diferente do seu e-mail");
  });

  test("e-mail curto nao gera falso positivo", () => {
    expect(avaliarSenha("abTreino1", { email: "ab@example.com" }).ok).toBe(true);
  });

  test("senha vazia nao explode", () => {
    expect(avaliarSenha().ok).toBe(false);
  });
});

describe("traducao de erro", () => {
  test("usa o motivo, nao o texto da mensagem", () => {
    expect(explicarErro(erroDe(429, { reason: "too_many_attempts" }))).toMatch(/novo código/i);
    expect(explicarErro(erroDe(429, { reason: "too_many_resends" }))).toMatch(/mais tarde/i);
  });

  test("cadastro fechado tem frase propria", () => {
    expect(explicarErro(erroDe(503, { reason: "public_signup_disabled" }))).toMatch(
      /ainda não está aberto/i
    );
  });

  test("problema de configuracao nao vira mensagem tecnica", () => {
    const msg = explicarErro(erroDe(503, { reason: "plan_not_configured" }));
    expect(msg).toMatch(/indisponível/i);
    expect(msg).not.toMatch(/plan_not_configured/);
  });

  test("cadastro expirado orienta a recomecar", () => {
    expect(explicarErro(erroDe(410, { reason: "expired" }))).toMatch(/comece novamente/i);
  });

  test("detalhe em texto simples e aproveitado", () => {
    expect(explicarErro(erroDe(400, "Código inválido ou expirado"))).toBe(
      "Código inválido ou expirado"
    );
  });

  test("erro sem resposta cai numa frase generica e nao quebra", () => {
    expect(explicarErro(new Error("network"))).toMatch(/tente novamente/i);
    expect(explicarErro(undefined)).toMatch(/tente novamente/i);
  });

  test("nunca devolve vazio", () => {
    [erroDe(500, null), erroDe(502, {}), {}, null].forEach((e) =>
      expect(explicarErro(e).length).toBeGreaterThan(0)
    );
  });
});

describe("retomada de quem nao pagou", () => {
  const planos = [
    { code: "essential", nome: "FORGE ESSENCIAL" },
    { code: "pro", nome: "FORGE PRO" },
    { code: "elite", nome: "FORGE ELITE" },
  ];

  test("destaca o escolhido e mantem os outros para troca", () => {
    const r = montarRetomada(planos, "pro");
    expect(r.escolhido.code).toBe("pro");
    expect(r.alternativas.map((p) => p.code)).toEqual(["essential", "elite"]);
  });

  test("plano desconhecido nao esconde as alternativas", () => {
    const r = montarRetomada(planos, "inexistente");
    expect(r.escolhido).toBeNull();
    expect(r.alternativas).toHaveLength(3);
  });

  test("lista ausente nao quebra", () => {
    expect(montarRetomada(undefined, "pro").alternativas).toEqual([]);
  });
});
