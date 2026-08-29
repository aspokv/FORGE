import {
  PASSO_NOVA_SENHA,
  PASSO_PEDIR,
  SENHA_MINIMA,
  emailParece,
  explicarErro,
  passoInicial,
  problemaDaSenha,
  senhasConferem,
  tokenDaRota,
} from "./passwordResetRules";

const erroDe = (status, detail) => ({ response: { status, data: { detail } } });

describe("token na rota", () => {
  test("extrai o token de /recuperar/<token>", () => {
    expect(tokenDaRota("/recuperar/abc123")).toBe("abc123");
    expect(tokenDaRota("/recuperar/abc-123_XY")).toBe("abc-123_XY");
  });

  test("ignora query e fragmento", () => {
    expect(tokenDaRota("/recuperar/abc?x=1")).toBe("abc");
    expect(tokenDaRota("/recuperar/abc#y")).toBe("abc");
  });

  test("sem token devolve null", () => {
    expect(tokenDaRota("/recuperar")).toBeNull();
    expect(tokenDaRota("/recuperar/")).toBeNull();
    expect(tokenDaRota("/login")).toBeNull();
    expect(tokenDaRota(null)).toBeNull();
  });

  test("o passo inicial segue o token", () => {
    expect(passoInicial("/recuperar")).toBe(PASSO_PEDIR);
    expect(passoInicial("/recuperar/abc")).toBe(PASSO_NOVA_SENHA);
  });
});

describe("politica de senha", () => {
  test("senha boa passa", () => {
    expect(problemaDaSenha("Treino2026")).toBeNull();
  });

  test("curta demais diz o tamanho exigido", () => {
    const p = problemaDaSenha("Ab1");
    expect(p).toContain(String(SENHA_MINIMA));
  });

  test("sem letra e sem numero sao recusadas com motivo proprio", () => {
    expect(problemaDaSenha("12345678")).toMatch(/letra/i);
    expect(problemaDaSenha("abcdefgh")).toMatch(/número/i);
  });

  test("um caractere repetido nao passa", () => {
    expect(problemaDaSenha("aaaaaaaa")).toMatch(/variados/i);
  });

  test("senha que contem o e-mail nao passa", () => {
    expect(problemaDaSenha("anasouza1", "anasouza@example.com")).toMatch(/e-mail/i);
  });

  test("e-mail curto nao gera falso positivo", () => {
    expect(problemaDaSenha("abTreino1", "ab@example.com")).toBeNull();
  });

  test("entrada vazia nao explode", () => {
    expect(problemaDaSenha()).toBeTruthy();
    expect(problemaDaSenha(null, null)).toBeTruthy();
  });

  test("confirmacao precisa bater", () => {
    expect(senhasConferem("Treino2026", "Treino2026")).toBe(true);
    expect(senhasConferem("Treino2026", "Treino2027")).toBe(false);
    expect(senhasConferem("", "")).toBe(true);
  });
});

describe("e-mail", () => {
  test("aceita os validos e recusa os invalidos", () => {
    ["a.b@c.com.br", "x+y@d.io"].forEach((e) => expect(emailParece(e)).toBe(true));
    ["", "sem-arroba", "a@b", null].forEach((e) => expect(emailParece(e)).toBe(false));
  });
});

describe("traducao de erro", () => {
  test("link invalido tem frase propria", () => {
    expect(explicarErro(erroDe(410, { reason: "reset_token_invalid" })))
      .toMatch(/expirou ou já foi usado/i);
  });

  test("410 sem motivo cai na mesma frase", () => {
    expect(explicarErro(erroDe(410, null))).toMatch(/expirou ou já foi usado/i);
  });

  test("senha fraca devolve a mensagem do servidor", () => {
    const msg = "A senha precisa de pelo menos um número.";
    expect(explicarErro(erroDe(400, { reason: "weak_password", message: msg }))).toBe(msg);
  });

  test("limite de taxa orienta a esperar", () => {
    expect(explicarErro(erroDe(429, { reason: "rate_limited" }))).toMatch(/aguarde/i);
    expect(explicarErro(erroDe(429, null))).toMatch(/aguarde/i);
  });

  test("erro sem resposta nao quebra e nunca devolve vazio", () => {
    [new Error("rede"), undefined, {}, erroDe(500, {})].forEach((e) =>
      expect(explicarErro(e).length).toBeGreaterThan(0)
    );
  });

  test("nao inventa mensagem sobre existencia da conta", () => {
    // Nenhuma traducao pode sugerir que o e-mail existe ou nao.
    const todas = [
      explicarErro(erroDe(410, { reason: "reset_token_invalid" })),
      explicarErro(erroDe(429, { reason: "rate_limited" })),
      explicarErro(new Error("x")),
    ].join(" ").toLowerCase();
    expect(todas).not.toMatch(/não encontrad|não existe|conta inexistente/);
  });
});

describe("a politica bate com a do servidor", () => {
  // Os mesmos casos existem em backend/tests/test_recuperacao_de_senha.py. Divergir
  // significaria a tela aprovar o que o servidor recusa, ou o contrario.
  test.each([
    ["curta1", true],
    ["semnumeros", true],
    ["12345678", true],
    ["aaaaaaaa", true],
    ["Treino2026", false],
    ["SenhaNova#2026", false],
  ])("%s -> recusada=%s", (senha, recusada) => {
    expect(Boolean(problemaDaSenha(senha, "alguem@example.com"))).toBe(recusada);
  });
});
