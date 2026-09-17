import {PLANOS, NOME_DO_PLANO, ROTULO_DE_STATUS, ROTULO_DA_ORIGEM} from "./AdminPanel";

/*
 * Os planos do painel administrativo.
 *
 * O defeito: a tela oferecia FORGE_ACCESS, FORGE_PRO e LIFETIME, nomes de antes de
 * existir cobranca, e o Elite nem aparecia — justamente o plano onde mora o Conselho. A
 * escolha era gravada em `users.plan`, um campo que o backend nunca consulta para decidir
 * acesso: a tela dizia "atualizado" e nada mudava.
 *
 * Estes testes prendem o contrato entre as duas pontas. O que o painel OFERECE tem que
 * ser exatamente o que `billing_plans.py` reconhece; qualquer divergencia volta a
 * produzir uma tela que promete o que nao entrega.
 */

test("o painel oferece os tres planos que existem, na ordem de preco", () => {
  expect(PLANOS.map(p => p.code)).toEqual(["essential", "pro", "elite"]);
});

test("o Elite esta la, que e onde mora o Conselho", () => {
  const elite = PLANOS.find(p => p.code === "elite");
  expect(elite).toBeTruthy();
  expect(elite.nome).toBe("FORGE Elite");
  expect(elite.preco).toBe("R$ 99,90/mês");
});

test("os precos batem com os do backend", () => {
  // Os mesmos numeros de `billing_plans.py`. Um preco errado no painel administrativo
  // vira um preco errado dito para o cliente no WhatsApp.
  expect(PLANOS.map(p => p.preco)).toEqual([
    "R$ 39,90/mês", "R$ 69,90/mês", "R$ 99,90/mês",
  ]);
});

test("nenhum nome antigo sobrou na tela", () => {
  const texto = JSON.stringify(PLANOS);
  for (const antigo of ["FORGE_ACCESS", "FORGE_PRO", "LIFETIME"]) {
    expect(texto).not.toContain(antigo);
  }
});

test("todo plano tem um nome legivel para mostrar", () => {
  for (const p of PLANOS) {
    expect(NOME_DO_PLANO[p.code]).toBe(p.nome);
  }
});

test("o status vira palavra, e nao enum do banco", () => {
  // "PENDING_PAYMENT" nao cabia na pilula e vazava por cima da borda.
  expect(ROTULO_DE_STATUS.PENDING_PAYMENT).toBe("Aguardando");
  expect(ROTULO_DE_STATUS.ACTIVE).toBe("Ativo");
  expect(ROTULO_DE_STATUS.SUSPENDED).toBe("Suspenso");
  for (const rotulo of Object.values(ROTULO_DE_STATUS)) {
    expect(rotulo.length).toBeLessThanOrEqual(11);
    expect(rotulo).not.toMatch(/_/);
  }
});

test("a origem do acesso distingue cortesia de venda", () => {
  // Confundir as duas faria o dono achar que vendeu o que ele mesmo deu.
  expect(ROTULO_DA_ORIGEM.courtesy).toBe("cortesia");
  expect(ROTULO_DA_ORIGEM.mercadopago).toBe("assinatura");
  expect(ROTULO_DA_ORIGEM.admin).toBe("administrador");
});
