import {act} from "react";
import {createRoot} from "react-dom/client";
import EscolherSessao from "./EscolherSessao";

/*
 * Escolher qual sessão treinar hoje.
 *
 * Um atleta adiantou o treino do fim de semana e, no dia seguinte, o FORGE ofereceu de
 * novo a sessão que ele acabara de fazer. Ele quis fazer a seguinte e não teve como: a
 * tela mostra UMA sessão, a do ponteiro, e não havia onde escolher outra. Sem escolher,
 * não dá para registrar carga — e sem registro o treino não existe para o motor.
 */

const SESSOES = [
  {day: 1, label: "Push", exercicios: 5, demand: "HIGH"},
  {day: 2, label: "Pull", exercicios: 5, demand: "HIGH"},
  {day: 3, label: "Legs", exercicios: 4, demand: "MODERATE"},
];

function clienteFalso({escolhida = null, ativa = 1, falhaPost, falhaGet} = {}) {
  return {
    get: jest.fn(async () => { if (falhaGet) throw falhaGet; return {data: {sessoes: SESSOES, escolhida, ativa}}; }),
    post: jest.fn(async () => { if (falhaPost) throw falhaPost; return {data: {escolhida: 3, program: {}}}; }),
    delete: jest.fn(async () => ({data: {escolhida: null, program: {}}})),
  };
}

async function montar(opcoes = {}) {
  const cliente = opcoes.cliente || clienteFalso(opcoes);
  const aoEscolher = jest.fn();
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  await act(async () => {
    createRoot(alvo).render(<EscolherSessao API="/api" aoEscolher={aoEscolher} axiosCliente={cliente} />);
  });
  const clicar = async sel => {
    await act(async () => {
      alvo.querySelector(sel).dispatchEvent(new MouseEvent("click", {bubbles: true}));
    });
  };
  return {alvo, cliente, aoEscolher, clicar};
}

afterEach(() => { document.body.innerHTML = ""; });

// Fechado por padrão: o programa acerta na maioria dos dias, e um seletor sempre aberto
// convidaria a improvisar a rotação todo dia.
test("começa fechado, e só busca as sessões ao abrir", async () => {
  const {alvo, cliente, clicar} = await montar();
  expect(alvo.querySelector('[data-testid="escolher-sessao"]')).toBeNull();
  expect(cliente.get).not.toHaveBeenCalled();
  await clicar('[data-testid="escolher-sessao-abrir"]');
  expect(cliente.get).toHaveBeenCalledWith("/api/workout/sessoes-do-dia");
  expect(alvo.querySelector('[data-testid="escolher-sessao"]')).not.toBeNull();
});

test("lista todas as sessões do programa", async () => {
  const {alvo, clicar} = await montar();
  await clicar('[data-testid="escolher-sessao-abrir"]');
  for (const s of SESSOES) {
    const b = alvo.querySelector(`[data-testid="escolher-sessao-${s.day}"]`);
    expect(b).not.toBeNull();
    expect(b.textContent).toContain(s.label);
  }
});

test("escolher envia o dia e avisa quem hospeda", async () => {
  const {cliente, aoEscolher, clicar} = await montar();
  await clicar('[data-testid="escolher-sessao-abrir"]');
  await clicar('[data-testid="escolher-sessao-3"]');
  expect(cliente.post).toHaveBeenCalledWith("/api/workout/escolher-sessao", {day: 3});
  expect(aoEscolher).toHaveBeenCalled();
});

test("a sessão ativa aparece marcada", async () => {
  const {alvo, clicar} = await montar({ativa: 2});
  await clicar('[data-testid="escolher-sessao-abrir"]');
  expect(alvo.querySelector('[data-testid="escolher-sessao-2"]').className).toContain("escolhida");
  expect(alvo.querySelector('[data-testid="escolher-sessao-1"]').className).not.toContain("escolhida");
});

// Um botão de voltar sem escolha feita não volta para lugar nenhum.
test("desfazer só aparece quando há escolha feita", async () => {
  const semEscolha = await montar({escolhida: null});
  await semEscolha.clicar('[data-testid="escolher-sessao-abrir"]');
  expect(semEscolha.alvo.querySelector('[data-testid="escolher-sessao-desfazer"]')).toBeNull();
  document.body.innerHTML = "";

  const comEscolha = await montar({escolhida: 3, ativa: 3});
  await comEscolha.clicar('[data-testid="escolher-sessao-abrir"]');
  await comEscolha.clicar('[data-testid="escolher-sessao-desfazer"]');
  expect(comEscolha.cliente.delete).toHaveBeenCalledWith("/api/workout/escolher-sessao");
});

test("falha ao escolher aparece na tela e o painel não some", async () => {
  const erro = new Error("nao");
  erro.response = {status: 422, data: {detail: "Essa sessão não está no seu programa."}};
  const {alvo, clicar} = await montar({falhaPost: erro});
  await clicar('[data-testid="escolher-sessao-abrir"]');
  await clicar('[data-testid="escolher-sessao-3"]');
  expect(alvo.querySelector('[data-testid="escolher-sessao-erro"]').textContent).toContain("programa");
  expect(alvo.querySelector('[data-testid="escolher-sessao"]')).not.toBeNull();
});

test("falha ao carregar oferece tentar de novo", async () => {
  const erro = new Error("rede"); erro.response = {status: 500};
  const {alvo, clicar} = await montar({falhaGet: erro});
  await clicar('[data-testid="escolher-sessao-abrir"]');
  expect(alvo.textContent).toContain("Tentar de novo");
  expect(alvo.querySelector('[data-testid="escolher-sessao-1"]')).toBeNull();
});

/*
 * Um endereço errado não devolve erro: o servidor entrega o `index.html` para qualquer
 * caminho desconhecido, com status 200. Sem guarda, a tela mostrava um painel vazio como
 * se o programa não tivesse sessão nenhuma — e foi assim que a prop `API` faltando passou
 * despercebida pelos testes, que injetam o endereço certo.
 */
test("resposta que não traz a lista vira erro, e não lista vazia", async () => {
  const cliente = {
    get: jest.fn(async () => ({data: "<!doctype html><html><body>app</body></html>"})),
    post: jest.fn(), delete: jest.fn(),
  };
  const {alvo, clicar} = await montar({cliente});
  await clicar('[data-testid="escolher-sessao-abrir"]');
  expect(alvo.textContent).toContain("Tentar de novo");
  expect(alvo.querySelector('[data-testid="escolher-sessao-1"]')).toBeNull();
});
