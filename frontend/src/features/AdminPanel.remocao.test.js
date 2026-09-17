import {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import {AthleteDetail} from "./AdminPanel";

jest.mock("axios");

/*
 * Excluir atleta na ficha.
 *
 * Arquivar e o caminho normal e vive na lista, a um clique. Excluir mora aqui, depois de
 * tudo, atras de um passo e de uma confirmacao digitada — porque numa lista de 1.600
 * linhas a linha errada esta sempre a um clique de distancia, e aqui nao ha desfazer.
 *
 * A comparacao do e-mail acontece NO SERVIDOR. A tela poderia comparar sozinha e evitar a
 * viagem, mas ai a trava viveria no lugar errado: quem chamasse a API direto passaria por
 * cima dela. A tela so nao deixa clicar a toa.
 */

const ATLETA = {id: "atleta-9", name: "Fulano", email: "fulano@exemplo.com", status: "ACTIVE"};

async function abrir() {
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  const root = createRoot(alvo);
  const onNotify = jest.fn();
  const onChanged = jest.fn();
  const onClose = jest.fn();
  await act(async () => {
    root.render(<AthleteDetail data={{athlete: ATLETA}} onClose={onClose}
                               onChanged={onChanged} onNotify={onNotify} />);
  });
  return {alvo, onNotify, onChanged, onClose};
}

async function clicar(alvo, testid) {
  await act(async () => { alvo.querySelector(`[data-testid="${testid}"]`).click(); });
}

async function escrever(alvo, testid, valor) {
  await act(async () => {
    const campo = alvo.querySelector(`[data-testid="${testid}"]`);
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    set.call(campo, valor);
    campo.dispatchEvent(new Event("input", {bubbles: true}));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({data: {athlete: ATLETA, profile: {}, workouts: 0,
                                      acesso: {plan_code: null}}});
  axios.delete.mockResolvedValue({data: {deleted: true, total: 42, removidos: {}}});
});

afterEach(() => { document.body.innerHTML = ""; });

test("excluir nao aparece de cara: e preciso abrir a area de risco", async () => {
  const {alvo} = await abrir();
  expect(alvo.querySelector('[data-testid="exclusao-confirmar"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="abrir-exclusao"]')).not.toBeNull();
});

test("a tela diz o que sera perdido e oferece arquivar no lugar", async () => {
  const {alvo} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  const texto = alvo.querySelector('[data-testid="area-de-risco"]').textContent;
  expect(texto).toContain("Não tem volta");
  expect(texto).toContain("Arquivar");
  expect(texto).toContain("fulano@exemplo.com");
});

test("sem digitar o e-mail o botao fica desabilitado", async () => {
  const {alvo} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  expect(alvo.querySelector('[data-testid="exclusao-confirmar"]').disabled).toBe(true);
  expect(axios.delete).not.toHaveBeenCalled();
});

test("com o e-mail digitado, o DELETE sai com e-mail e motivo", async () => {
  const {alvo} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "fulano@exemplo.com");
  await escrever(alvo, "exclusao-motivo", "conta de teste");
  await clicar(alvo, "exclusao-confirmar");

  expect(axios.delete).toHaveBeenCalledTimes(1);
  const [url, config] = axios.delete.mock.calls[0];
  expect(url).toContain("/admin/athletes/atleta-9");
  expect(config.data).toEqual({confirmar_email: "fulano@exemplo.com", motivo: "conta de teste"});
});

test("sucesso avisa quantos registros sairam e fecha a ficha", async () => {
  const {alvo, onNotify, onChanged, onClose} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "fulano@exemplo.com");
  await clicar(alvo, "exclusao-confirmar");

  expect(onNotify).toHaveBeenCalledWith("success", "Atleta excluído. 42 registros removidos.");
  expect(onChanged).toHaveBeenCalled();
  expect(onClose).toHaveBeenCalled();
});

test("e-mail errado: o servidor recusa e o erro fica na tela", async () => {
  axios.delete.mockRejectedValueOnce({response: {status: 400, data: {detail: {
    reason: "email_mismatch",
    message: "Digite o e-mail exato do atleta para confirmar a exclusão.",
  }}}});
  const {alvo, onClose} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "errado@exemplo.com");
  await clicar(alvo, "exclusao-confirmar");

  expect(alvo.querySelector('[data-testid="exclusao-erro"]').textContent).toContain("e-mail exato");
  expect(onClose).not.toHaveBeenCalled();
});

test("assinatura paga: a tela mostra o motivo em vez de sumir com a pessoa", async () => {
  axios.delete.mockRejectedValueOnce({response: {status: 409, data: {detail: {
    reason: "paid_subscription",
    message: "Este atleta tem uma assinatura paga ativa. Cancele a cobrança no Mercado Pago antes de excluir.",
  }}}});
  const {alvo, onClose} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "fulano@exemplo.com");
  await clicar(alvo, "exclusao-confirmar");

  expect(alvo.querySelector('[data-testid="exclusao-erro"]').textContent).toContain("Mercado Pago");
  expect(onClose).not.toHaveBeenCalled();
});

test("cancelar fecha a area de risco e nao exclui nada", async () => {
  const {alvo} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "fulano@exemplo.com");
  await clicar(alvo, "exclusao-cancelar");

  expect(alvo.querySelector('[data-testid="exclusao-confirmar"]')).toBeNull();
  expect(axios.delete).not.toHaveBeenCalled();
});

test("erro nao deixa o botao travado em Excluindo", async () => {
  axios.delete.mockRejectedValueOnce(new Error("rede caiu"));
  const {alvo} = await abrir();
  await clicar(alvo, "abrir-exclusao");
  await escrever(alvo, "exclusao-email", "fulano@exemplo.com");
  await clicar(alvo, "exclusao-confirmar");

  const botao = alvo.querySelector('[data-testid="exclusao-confirmar"]');
  expect(botao.textContent).toContain("Excluir para sempre");
  expect(botao.disabled).toBe(false);
});
