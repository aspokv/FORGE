import {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import {AthleteDetail} from "./AdminPanel";

jest.mock("axios");

/*
 * Conceder plano na ficha do atleta.
 *
 * O defeito que estes testes existem para nunca mais deixar passar: o botao estava ligado
 * como `onClick={concederPlano}`, entao o React entregava o EVENTO DO CLIQUE como primeiro
 * argumento da funcao. O parametro `substituir` virava um SyntheticEvent, o axios tentava
 * serializar um objeto com referencia circular, e a requisicao NUNCA SAIA.
 *
 * Na tela isso aparecia como "nao salva": clicava em "Aplicar plano", o plano continuava o
 * mesmo, e o erro ia para a faixa do topo — que some em quatro segundos e fica longe do
 * botao. Ou seja: nada acontecia e nada explicava por que.
 *
 * Quais destes testes realmente pegam o defeito, medido revertendo o conserto: os dois que
 * olham o CORPO enviado — `substituir_assinatura_paga` exatamente `false` e o corpo ser
 * serializavel. Os outros nove continuam verdes com o codigo quebrado.
 *
 * O motivo vale anotar: aqui o axios e um dublê, e dublê nao serializa nada. O sintoma
 * real ("a requisicao nunca sai") acontece dentro do axios de verdade, quando o
 * `JSON.stringify` topa a referencia circular do evento. Entao "clicar chamou o axios" NAO
 * prova que a requisicao sairia no navegador; quem prova e a assercao explicita de que o
 * corpo e serializavel.
 */

const ATLETA = {id: "atleta-1", name: "Nicolas", email: "n@exemplo.com", status: "ACTIVE"};

function montar(props = {}) {
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  const root = createRoot(alvo);
  const onNotify = jest.fn();
  const onChanged = jest.fn();
  return {alvo, root, onNotify, onChanged, props: {
    data: {athlete: ATLETA}, onClose: jest.fn(), onChanged, onNotify, ...props,
  }};
}

async function abrir(props = {}) {
  const m = montar(props);
  await act(async () => {
    m.root.render(<AthleteDetail {...m.props} />);
  });
  return m;
}

/** Escolhe o plano e escreve o motivo, como uma pessoa faz. */
async function preencher(alvo, code = "elite", motivo = "conta do dono") {
  const select = alvo.querySelector('[data-testid="conceder-plano-code"]');
  const input = alvo.querySelector('[data-testid="conceder-plano-motivo"]');
  await act(async () => {
    const setS = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, "value").set;
    setS.call(select, code);
    select.dispatchEvent(new Event("change", {bubbles: true}));
  });
  await act(async () => {
    const setI = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    setI.call(input, motivo);
    input.dispatchEvent(new Event("input", {bubbles: true}));
  });
}

async function clicar(alvo, testid) {
  await act(async () => {
    alvo.querySelector(`[data-testid="${testid}"]`).click();
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({data: {athlete: ATLETA, profile: {}, workouts: 0,
                                      acesso: {plan_code: "pro", source: "mercadopago"}}});
  axios.post.mockResolvedValue({data: {plan_code: "elite",
                                       acesso: {plan_code: "elite", source: "courtesy"}}});
});

afterEach(() => { document.body.innerHTML = ""; });

test("clicar em aplicar ENVIA a requisicao", async () => {
  // O defeito original: o clique nao produzia requisicao nenhuma.
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");
  expect(axios.post).toHaveBeenCalledTimes(1);
});

test("o corpo enviado tem substituir_assinatura_paga exatamente false", async () => {
  // `onClick={concederPlano}` passava o SyntheticEvent para ca. Alem de quebrar a
  // serializacao, um valor truthy aqui significaria "sobrescreva a assinatura paga".
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");

  const [, corpo] = axios.post.mock.calls[0];
  expect(corpo.substituir_assinatura_paga).toBe(false);
  expect(typeof corpo.substituir_assinatura_paga).toBe("boolean");
  expect(corpo).toEqual({
    plan_code: "elite", motivo: "conta do dono", substituir_assinatura_paga: false,
  });
});

test("o corpo e serializavel, que e o que o axios precisa", async () => {
  // Um SyntheticEvent tem referencia circular e derruba o JSON.stringify antes do envio.
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");
  expect(() => JSON.stringify(axios.post.mock.calls[0][1])).not.toThrow();
});

test("revogar manda plano nulo", async () => {
  const {alvo} = await abrir();
  await preencher(alvo, "__revogar", "fim do teste");
  await clicar(alvo, "conceder-plano-salvar");
  expect(axios.post.mock.calls[0][1].plan_code).toBeNull();
});

test("sem plano escolhido o botao fica desabilitado", async () => {
  const {alvo} = await abrir();
  expect(alvo.querySelector('[data-testid="conceder-plano-salvar"]').disabled).toBe(true);
});

// ── A assinatura paga ────────────────────────────────────────────────────────────────

test("assinatura paga pede confirmacao NA TELA, e nao num alerta do navegador", async () => {
  // Era `window.confirm`, que o navegador pode bloquear e que nenhum teste aciona.
  axios.post.mockRejectedValueOnce({response: {status: 409, data: {detail: {
    reason: "paid_subscription",
    message: "Este atleta tem uma assinatura paga ativa. Confirme que quer substituí-la por cortesia.",
  }}}});
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");

  const caixa = alvo.querySelector('[data-testid="conceder-plano-confirmar"]');
  expect(caixa).not.toBeNull();
  expect(caixa.textContent).toContain("assinatura paga ativa");
  // Enquanto a pergunta esta aberta, o botao de aplicar sai: nao ha duas saidas.
  expect(alvo.querySelector('[data-testid="conceder-plano-salvar"]')).toBeNull();
});

test("confirmar a substituicao reenvia com substituir verdadeiro", async () => {
  axios.post.mockRejectedValueOnce({response: {status: 409, data: {detail: {
    reason: "paid_subscription", message: "assinatura paga ativa",
  }}}});
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");
  await clicar(alvo, "conceder-plano-substituir");

  expect(axios.post).toHaveBeenCalledTimes(2);
  expect(axios.post.mock.calls[1][1].substituir_assinatura_paga).toBe(true);
});

test("cancelar NAO substitui nada", async () => {
  axios.post.mockRejectedValueOnce({response: {status: 409, data: {detail: {
    reason: "paid_subscription", message: "assinatura paga ativa",
  }}}});
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");
  await clicar(alvo, "conceder-plano-cancelar");

  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(alvo.querySelector('[data-testid="conceder-plano-confirmar"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="conceder-plano-salvar"]')).not.toBeNull();
});

// ── O erro fica onde a pessoa esta olhando ───────────────────────────────────────────

test("erro aparece DENTRO do cartao, ao lado do botao", async () => {
  // Ele ia para a faixa do topo, que some em quatro segundos e fica longe da acao.
  axios.post.mockRejectedValueOnce({response: {status: 400, data: {detail: {
    reason: "courtesy_reason_required", message: "Informe o motivo da cortesia.",
  }}}});
  const {alvo} = await abrir();
  await preencher(alvo, "elite", "");
  await clicar(alvo, "conceder-plano-salvar");

  const erro = alvo.querySelector('[data-testid="conceder-plano-erro"]');
  expect(erro).not.toBeNull();
  expect(erro.textContent).toContain("motivo");
});

test("erro de rede nao deixa o botao travado em Aplicando", async () => {
  axios.post.mockRejectedValueOnce(new Error("rede caiu"));
  const {alvo} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");

  const botao = alvo.querySelector('[data-testid="conceder-plano-salvar"]');
  expect(botao.textContent).toContain("Aplicar plano");
  expect(botao.disabled).toBe(false);
});

test("sucesso avisa e limpa o formulario", async () => {
  const {alvo, onNotify, onChanged} = await abrir();
  await preencher(alvo);
  await clicar(alvo, "conceder-plano-salvar");

  expect(onNotify).toHaveBeenCalledWith("success", "Plano concedido.");
  expect(onChanged).toHaveBeenCalled();
  expect(alvo.querySelector('[data-testid="conceder-plano-motivo"]').value).toBe("");
});
