import {
  PASSOS,
  PASSO_AVALIACAO,
  PASSO_PLANO,
  PASSO_DADOS,
  PASSO_PAGAMENTO,
  PASSO_PREVIA,
  PASSO_SENHA,
  avaliarSenha,
  emailParece,
  explicarErro,
  montarRetomada,
  passoAnterior,
  proximoPasso,
  resumoDaPrevia,
  ritmoPadrao,
  ritmosDoObjetivo,
  validarCodigo,
  validarDados,
  validarPreAvaliacao,
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


// ── Pre-avaliacao ──────────────────────────────────────────────────────────────────

const CATALOGO_PRO = {
  max_priorities: 3,
  includes_nutrition: true,
  body_goals: [
    {
      id: "fat_loss",
      default_intensity: "moderado",
      intensities: [
        { id: "leve", locked: false },
        { id: "moderado", locked: false, recommended: true },
        { id: "agressivo", locked: true },
      ],
    },
    { id: "maintenance", default_intensity: null, intensities: [] },
  ],
};

const CATALOGO_ESSENCIAL = { max_priorities: 3, includes_nutrition: false, body_goals: [] };

const RESPOSTAS = {
  sex: "female",
  experience: "Intermediário",
  goal: "Hipertrofia",
  days: 4,
  priorities: ["Glúteos"],
  body_goal: "fat_loss",
  goal_intensity: "moderado",
};

describe("ordem com a pre-avaliacao", () => {
  test("a pre-avaliacao e a previa ficam entre a senha e o pagamento", () => {
    const i = (p) => PASSOS.indexOf(p);
    expect(i(PASSO_SENHA)).toBeLessThan(i(PASSO_AVALIACAO));
    expect(i(PASSO_AVALIACAO)).toBeLessThan(i(PASSO_PREVIA));
    expect(i(PASSO_PREVIA)).toBeLessThan(i(PASSO_PAGAMENTO));
  });

  test("o pagamento continua sendo o ultimo passo", () => {
    expect(PASSOS[PASSOS.length - 1]).toBe(PASSO_PAGAMENTO);
    expect(proximoPasso(PASSO_SENHA)).toBe(PASSO_AVALIACAO);
    expect(passoAnterior(PASSO_PAGAMENTO)).toBe(PASSO_PREVIA);
  });

  test("o plano ainda vem primeiro", () => {
    expect(PASSOS[0]).toBe(PASSO_PLANO);
    expect(PASSOS.indexOf(PASSO_DADOS)).toBe(1);
  });
});

describe("validacao da pre-avaliacao", () => {
  test("respostas completas passam", () => {
    expect(validarPreAvaliacao(RESPOSTAS, CATALOGO_PRO).ok).toBe(true);
  });

  test.each(["sex", "experience", "goal", "days"])("falta %s reprova", (campo) => {
    const r = validarPreAvaliacao({ ...RESPOSTAS, [campo]: undefined }, CATALOGO_PRO);
    expect(r.ok).toBe(false);
    expect(r.erros[campo]).toBeTruthy();
  });

  test("nenhuma prioridade e uma resposta valida", () => {
    expect(validarPreAvaliacao({ ...RESPOSTAS, priorities: [] }, CATALOGO_PRO).ok).toBe(true);
  });

  test("mais prioridades que o maximo reprova", () => {
    const r = validarPreAvaliacao(
      { ...RESPOSTAS, priorities: ["a", "b", "c", "d"] }, CATALOGO_PRO);
    expect(r.ok).toBe(false);
    expect(r.erros.priorities).toMatch(/3/);
  });

  test("o Essencial nao exige resposta de alimentacao", () => {
    const semAlimentacao = { ...RESPOSTAS, body_goal: undefined, goal_intensity: undefined };
    expect(validarPreAvaliacao(semAlimentacao, CATALOGO_ESSENCIAL).ok).toBe(true);
  });

  test("o Pro exige objetivo alimentar", () => {
    const r = validarPreAvaliacao({ ...RESPOSTAS, body_goal: undefined }, CATALOGO_PRO);
    expect(r.ok).toBe(false);
    expect(r.erros.body_goal).toBeTruthy();
  });

  test("ritmo bloqueado pelo plano e recusado antes de enviar", () => {
    const r = validarPreAvaliacao(
      { ...RESPOSTAS, goal_intensity: "agressivo" }, CATALOGO_PRO);
    expect(r.ok).toBe(false);
    expect(r.erros.goal_intensity).toMatch(/Elite/);
  });

  test("objetivo sem ritmo nao exige ritmo", () => {
    const r = validarPreAvaliacao(
      { ...RESPOSTAS, body_goal: "maintenance", goal_intensity: undefined }, CATALOGO_PRO);
    expect(r.ok).toBe(true);
  });

  test("catalogo ausente nao quebra a validacao", () => {
    expect(validarPreAvaliacao(RESPOSTAS).ok).toBe(true);
    expect(validarPreAvaliacao().ok).toBe(false);
  });
});

describe("ritmos por objetivo", () => {
  test("devolve os ritmos do objetivo escolhido", () => {
    expect(ritmosDoObjetivo(CATALOGO_PRO, "fat_loss").map((i) => i.id))
      .toEqual(["leve", "moderado", "agressivo"]);
  });

  test("manutencao nao tem ritmo", () => {
    expect(ritmosDoObjetivo(CATALOGO_PRO, "maintenance")).toEqual([]);
  });

  test("objetivo desconhecido devolve lista vazia", () => {
    expect(ritmosDoObjetivo(CATALOGO_PRO, "inventado")).toEqual([]);
    expect(ritmosDoObjetivo(undefined, "fat_loss")).toEqual([]);
  });

  test("o ritmo padrao nunca cai num bloqueado", () => {
    expect(ritmoPadrao(CATALOGO_PRO, "fat_loss")).toBe("moderado");
    const soBloqueado = {
      body_goals: [{ id: "x", default_intensity: "agressivo",
                     intensities: [{ id: "agressivo", locked: true }] }],
    };
    expect(ritmoPadrao(soBloqueado, "x")).toBe("");
  });

  test("manutencao nao recebe ritmo padrao", () => {
    expect(ritmoPadrao(CATALOGO_PRO, "maintenance")).toBe("");
  });
});

describe("resumo da previa", () => {
  const previa = {
    training: { days: 4, split_label: "Superior / Inferior",
                sessions: [{}, {}, {}, {}] },
    focus: { declared: true, regions: [{}, {}] },
    nutrition: { included: true },
  };

  test("conta o que a tela mostra sem revelar conteudo", () => {
    const r = resumoDaPrevia(previa);
    expect(r).toEqual({ dias: 4, split: "Superior / Inferior", sessoes: 4,
                        temAlimentacao: true, prioridades: 2, declarou: true });
  });

  test("previa ausente nao quebra", () => {
    expect(resumoDaPrevia().sessoes).toBe(0);
    expect(resumoDaPrevia(null).temAlimentacao).toBe(false);
  });

  test("sem alimentacao o resumo diz que nao ha", () => {
    expect(resumoDaPrevia({ ...previa, nutrition: { included: false } }).temAlimentacao)
      .toBe(false);
  });
});
