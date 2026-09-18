import {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import {Swap} from "../App";

jest.mock("axios");

/*
 * O painel de substituir exercicio.
 *
 * O que estes testes prendem e o que a tela faz quando NAO ha o que oferecer. Doze dos
 * 134 exercicios do catalogo nao tem substituto equivalente — nenhum outro trabalha o
 * mesmo musculo com o mesmo padrao de movimento. Antes o motor inventava um (sempre
 * "Supino inclinado Smith", inclusive para a Cadeira abdutora); agora ele devolve lista
 * vazia, que e a resposta honesta. Sem um estado proprio, a tela abriria em branco e
 * pareceria quebrada.
 */

const ALTERNATIVAS = [
  {id: "cable-pushdown", name: "Tríceps corda na polia",
   reason: "Mantém Tríceps: troca máquina por polia."},
  {id: "ez-skullcrusher", name: "Tríceps testa com barra EZ",
   reason: "Mantém Tríceps: troca máquina por barra EZ, custo de fadiga alto no lugar de médio."},
];

const EXERCICIO = {id: "dip-machine", name: "Tríceps máquina"};

async function montar({alternativas = ALTERNATIVAS, erroNaBusca = false} = {}) {
  if (erroNaBusca) axios.get.mockRejectedValue(new Error("rede"));
  else axios.get.mockResolvedValue({data: {alternatives: alternativas}});
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  const root = createRoot(alvo);
  const close = jest.fn();
  const onSubstituted = jest.fn();
  await act(async () => {
    root.render(<Swap ex={EXERCICIO} close={close} onSubstituted={onSubstituted} />);
  });
  return {alvo, close, onSubstituted};
}

beforeEach(() => {
  jest.clearAllMocks();
  axios.post.mockResolvedValue({data: {program: {}, exercise_substitutions: {}}});
});

afterEach(() => { document.body.innerHTML = ""; });

test("lista as alternativas com o motivo de cada uma", async () => {
  const {alvo} = await montar();
  expect(alvo.querySelectorAll('[data-testid^="alternative-"]')).toHaveLength(2);
  expect(alvo.textContent).toContain("Tríceps corda na polia");
  expect(alvo.textContent).toContain("troca máquina por polia");
});

test("cada opção tem um motivo DIFERENTE, senão não ajudam a escolher", async () => {
  const {alvo} = await montar();
  const motivos = [...alvo.querySelectorAll('[data-testid^="alternative-"] small')]
    .map(e => e.textContent);
  expect(new Set(motivos).size).toBe(motivos.length);
});

test("sem alternativa, explica o motivo em vez de abrir em branco", async () => {
  const {alvo} = await montar({alternativas: []});
  const vazio = alvo.querySelector('[data-testid="swap-vazio"]');
  expect(vazio).not.toBeNull();
  expect(vazio.textContent).toContain("mesmo músculo");
  expect(alvo.querySelector('[data-testid="alternative-1"]')).toBeNull();
});

test("erro ao buscar também não deixa a tela em branco", async () => {
  const {alvo} = await montar({erroNaBusca: true});
  expect(alvo.querySelector('[data-testid="swap-vazio"]')).not.toBeNull();
});

test("escolher envia a troca e fecha o painel", async () => {
  const {alvo, close, onSubstituted} = await montar();
  await act(async () => { alvo.querySelector('[data-testid="alternative-1"]').click(); });
  expect(axios.post.mock.calls[0][1]).toEqual({
    original_exercise_id: "dip-machine", new_exercise_id: "cable-pushdown",
  });
  expect(onSubstituted).toHaveBeenCalled();
  expect(close).toHaveBeenCalled();
});

test("recusa do servidor mostra a mensagem e NÃO fecha o painel", async () => {
  // 409 quando o exercicio ja esta na sessao: fechar sem avisar seria o mesmo "nao salva"
  // silencioso que motivou este conserto.
  axios.post.mockRejectedValueOnce({response: {status: 409, data: {detail: {
    reason: "duplicate_in_session", message: "Esse exercício já está nesta sessão.",
  }}}});
  const {alvo, close} = await montar();
  await act(async () => { alvo.querySelector('[data-testid="alternative-1"]').click(); });
  expect(alvo.querySelector('[data-testid="swap-error"]')).not.toBeNull();
  expect(close).not.toHaveBeenCalled();
});
