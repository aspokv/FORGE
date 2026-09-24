import {act} from "react";
import {createRoot} from "react-dom/client";
import TrocarDiaDeTreino, {porExtenso} from "./TrocarDiaDeTreino";

/*
 * Trocar o dia de treino.
 *
 * Um atleta ia viajar no fim de semana e quis adiantar o treino de sábado para a quinta,
 * que na agenda dele é descanso. A tela de descanso não tinha sessão, nem exercícios, nem
 * botão de iniciar — e o único caminho oferecido, a Biblioteca, SUBSTITUI a sessão ativa.
 * Resolver uma semana atípica exigia mexer no programa.
 */

const DIAS = [
  {data: "2026-09-24", treino: false, label: null},
  {data: "2026-09-25", treino: true, label: "Sexta · Upper C"},
  {data: "2026-09-26", treino: true, label: "Sábado · Full Body B"},
];

function clienteFalso({dias = DIAS, trocas = [], disponivel = true, motivo = "", falhaPost} = {}) {
  return {
    get: jest.fn(async () => ({data: {disponivel, dias, trocas, motivo}})),
    post: jest.fn(async () => { if (falhaPost) throw falhaPost; return {data: {trocas: [], program: {}}}; }),
    delete: jest.fn(async () => ({data: {trocas: [], program: {}}})),
  };
}

async function montar(opcoes = {}) {
  const cliente = opcoes.cliente || clienteFalso(opcoes);
  const aoTrocar = jest.fn();
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  await act(async () => {
    createRoot(alvo).render(<TrocarDiaDeTreino API="/api" aoTrocar={aoTrocar} axiosCliente={cliente} />);
  });
  const clicar = async sel => {
    await act(async () => {
      alvo.querySelector(sel).dispatchEvent(new MouseEvent("click", {bubbles: true}));
    });
  };
  return {alvo, cliente, aoTrocar, clicar};
}

afterEach(() => { document.body.innerHTML = ""; });

test("oferece só os dias que TÊM treino, e não o de hoje", async () => {
  const {alvo} = await montar();
  // hoje (24) é o descanso: não pode ser oferecido como dia para descansar
  expect(alvo.querySelector('[data-testid="trocar-dia-opcao-2026-09-24"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="trocar-dia-opcao-2026-09-25"]')).not.toBeNull();
  expect(alvo.querySelector('[data-testid="trocar-dia-opcao-2026-09-26"]')).not.toBeNull();
});

// Sem escolher o dia de descanso não há troca: o botão manda "treinar hoje", e o servidor
// precisa saber de onde a sessão sai.
test("não dá para confirmar sem escolher o dia", async () => {
  const {alvo, clicar, cliente} = await montar();
  expect(alvo.querySelector('[data-testid="trocar-dia-confirmar"]').disabled).toBe(true);
  await clicar('[data-testid="trocar-dia-opcao-2026-09-26"]');
  expect(alvo.querySelector('[data-testid="trocar-dia-confirmar"]').disabled).toBe(false);
  expect(cliente.post).not.toHaveBeenCalled();
});

test("envia hoje como o dia de treino e o escolhido como descanso", async () => {
  const {clicar, cliente, aoTrocar} = await montar();
  await clicar('[data-testid="trocar-dia-opcao-2026-09-26"]');
  await clicar('[data-testid="trocar-dia-confirmar"]');
  expect(cliente.post).toHaveBeenCalledWith("/api/workout/trocar-dia",
    {treinar_em: "2026-09-24", descansar_em: "2026-09-26"});
  expect(aoTrocar).toHaveBeenCalled();
});

test("com a troca feita, mostra o que mudou e oferece desfazer", async () => {
  const {alvo, clicar, cliente} = await montar({
    trocas: [{treinar_em: "2026-09-24", descansar_em: "2026-09-26"}]});
  expect(alvo.textContent).toContain("sábado, 26/09");
  expect(alvo.textContent).toContain("quinta, 24/09");
  await clicar('[data-testid="trocar-dia-desfazer"]');
  expect(cliente.delete).toHaveBeenCalledWith("/api/workout/trocar-dia");
});

// Programa sem dia da semana fixo não tem descanso programado: não há o que trocar, e um
// botão que não muda nada seria pior que uma frase explicando.
test("programa sem dias fixos explica em vez de oferecer", async () => {
  const {alvo} = await montar({disponivel: false, motivo: "Seu programa não fixa dias da semana."});
  expect(alvo.querySelector('[data-testid="trocar-dia-indisponivel"]')).not.toBeNull();
  expect(alvo.querySelector('[data-testid="trocar-dia-confirmar"]')).toBeNull();
});

test("semana sem outro dia de treino diz isso", async () => {
  const {alvo} = await montar({dias: [{data: "2026-09-24", treino: false, label: null}]});
  expect(alvo.querySelector('[data-testid="trocar-dia-sem-candidatos"]')).not.toBeNull();
});

test("falha ao trocar aparece na tela e não some com o painel", async () => {
  const erro = new Error("nao"); erro.response = {status: 409, data: {detail: "Esse dia já é de descanso."}};
  const {alvo, clicar} = await montar({falhaPost: erro});
  await clicar('[data-testid="trocar-dia-opcao-2026-09-26"]');
  await clicar('[data-testid="trocar-dia-confirmar"]');
  expect(alvo.querySelector('[data-testid="trocar-dia-erro"]').textContent).toContain("descanso");
  expect(alvo.querySelector('[data-testid="trocar-dia-confirmar"]')).not.toBeNull();
});

/*
 * `new Date("2026-09-24")` é lido como UTC. Num fuso a oeste — o Brasil inteiro — isso
 * volta um dia, e a tela chamaria de "quarta" a data que o servidor chamou de quinta.
 * O atleta trocaria o dia errado sem nada parecer estranho.
 */
describe("a data por extenso", () => {
  test.each([
    ["2026-09-24", "quinta, 24/09"],
    ["2026-09-26", "sábado, 26/09"],
    ["2026-01-01", "quinta, 01/01"],
  ])("%s vira %s", (iso, esperado) => {
    expect(porExtenso(iso)).toBe(esperado);
  });

  test("data ausente não quebra a tela", () => {
    expect(porExtenso("")).toBe("");
    expect(porExtenso(undefined)).toBe("");
    expect(porExtenso("banana")).toBe("banana");
  });
});
