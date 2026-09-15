import React,{act} from "react";
import {createRoot} from "react-dom/client";
import RedeDeProtecao from "./RedeDeProtecao";

/*
 * O que estes testes protegem: o atleta trocou o objetivo para Agressivo, o backend recusou
 * com 402, o erro chegou como OBJETO, alguem tentou renderizar o objeto e o aplicativo
 * INTEIRO sumiu — tela preta, sem mensagem, sem botao.
 *
 * A causa daquele caso esta corrigida na origem (mensagemDeErro). Esta rede existe para o
 * proximo caso, e o teste que importa e o segundo: quebrar embaixo dela nao pode mais
 * apagar a tela.
 */

function Bomba({explodir}){
  if(explodir) throw new Error("Objects are not valid as a React child");
  return <p>tela inteira</p>;
}

let host,root,erroDoConsole;
beforeEach(()=>{
  host=document.createElement("div");document.body.appendChild(host);
  root=createRoot(host);
  // React registra a excecao no console de proposito. Silenciar aqui mantem a saida dos
  // testes legivel sem esconder erro de verdade: cada teste falha pelo que ele afirma.
  erroDoConsole=jest.spyOn(console,"error").mockImplementation(()=>{});
});
afterEach(()=>{act(()=>root.unmount());host.remove();erroDoConsole.mockRestore()});

const montar=explodir=>act(()=>{root.render(<RedeDeProtecao><Bomba explodir={explodir}/></RedeDeProtecao>)});
const rede=()=>host.querySelector('[data-testid="rede-de-protecao"]');

test("sem quebra, a rede e invisivel: mostra o que esta dentro dela",()=>{
  montar(false);
  expect(host.textContent).toContain("tela inteira");
  expect(rede()).toBeNull();
});

test("quebrou embaixo dela: a tela NAO fica preta",()=>{
  montar(true);
  expect(rede()).not.toBeNull();
  // O que separa "incidente" de "usuario perdido": ter texto e uma saida na tela.
  expect(rede().textContent.trim().length).toBeGreaterThan(20);
  const botoes=[...host.querySelectorAll("button")].map(b=>b.textContent);
  expect(botoes.some(t=>/recarregar/i.test(t))).toBe(true);
});

test("diz que os dados estao salvos — e o que a pessoa quer saber primeiro",()=>{
  montar(true);
  expect(rede().textContent).toMatch(/salvos/i);
});

test("a excecao vai para o console, com a pilha, para quem for investigar",()=>{
  montar(true);
  const nossa=erroDoConsole.mock.calls.find(c=>String(c[0]).includes("[FORGE]"));
  expect(nossa).toBeTruthy();
  expect(String(nossa[1]?.message)).toMatch(/Objects are not valid/);
});

test("o erro e anunciado como alerta, para leitor de tela",()=>{
  montar(true);
  expect(rede().getAttribute("role")).toBe("alert");
});
