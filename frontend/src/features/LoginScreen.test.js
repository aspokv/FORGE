import React, { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { LoginScreen } from "./AuthScreens";

jest.mock("axios");

// O Jest so deixa a fabrica do mock tocar variaveis com prefixo `mock`.
const mockSignIn = jest.fn();
const mockNavigate = jest.fn();
jest.mock("./AuthContext", () => ({
  API: "/api",
  useAuth: () => ({ signIn: mockSignIn, navigate: mockNavigate }),
}));

let host, root;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  axios.post.mockReset(); mockSignIn.mockReset(); mockNavigate.mockReset();
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); });

const render = async () => { await act(async () => { root.render(<LoginScreen />); }); };
const click = async el => { await act(async () => { el.click(); }); };
const digitar = async (el, valor) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, valor);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
};
const teste = s => host.querySelector(`[data-testid="${s}"]`);

test("a tela traz a chamada, os dois campos e as duas saidas", async () => {
  await render();
  expect(host.textContent).toContain("Seu programa.");
  expect(host.textContent).toContain("Sua evolução.");
  expect(host.textContent).toContain("Seu próximo nível começa aqui.");
  expect(host.textContent).toContain("Entre para continuar seu plano.");
  expect(teste("login-email")).not.toBeNull();
  expect(teste("login-password")).not.toBeNull();
  expect(teste("login-submit")).not.toBeNull();
  expect(teste("login-signup-link")).not.toBeNull();
});

/*
 * O letreiro FORGE e a regua sao placa iluminada dentro da foto, nao interface. Se alguem
 * acrescentar um wordmark em HTML, a marca aparece duas vezes na mesma tela.
 */
test("a marca vem da foto, e nao e desenhada de novo em HTML", async () => {
  await render();
  expect(host.textContent).not.toMatch(/FORGE/);
});

test("entrar envia o e-mail normalizado e guarda a sessao", async () => {
  axios.post.mockResolvedValue({ data: { token: "t", user: { role: "ATHLETE" } } });
  await render();
  await digitar(teste("login-email"), "  Joao.Silva@Example.COM ");
  await digitar(teste("login-password"), "senha123");
  await act(async () => { host.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  expect(axios.post).toHaveBeenCalledWith("/api/auth/login", { email: "joao.silva@example.com", password: "senha123" });
  expect(mockSignIn).toHaveBeenCalledWith("t", { role: "ATHLETE" });
  expect(mockNavigate).toHaveBeenCalledWith("/app", true);
});

test("administrador cai no painel, e nao no aplicativo", async () => {
  axios.post.mockResolvedValue({ data: { token: "t", user: { role: "SUPER_ADMIN" } } });
  await render();
  await act(async () => { host.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  expect(mockNavigate).toHaveBeenCalledWith("/admin", true);
});

test("falha mostra o motivo e nao autentica ninguem", async () => {
  axios.post.mockRejectedValue({ response: { data: { detail: "Credenciais inválidas." } } });
  await render();
  await act(async () => { host.querySelector("form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  expect(teste("login-error").textContent).toBe("Credenciais inválidas.");
  expect(mockSignIn).not.toHaveBeenCalled();
});

// O olho existe para a pessoa conferir o que digitou antes de errar a senha de novo.
test("o olho alterna entre esconder e mostrar a senha", async () => {
  await render();
  const campo = teste("login-password"), olho = teste("login-toggle-password");
  expect(campo.type).toBe("password");
  expect(olho.getAttribute("aria-label")).toBe("Mostrar senha");
  await click(olho);
  expect(teste("login-password").type).toBe("text");
  expect(teste("login-toggle-password").getAttribute("aria-label")).toBe("Ocultar senha");
  await click(teste("login-toggle-password"));
  expect(teste("login-password").type).toBe("password");
});

test("as duas saidas levam para as rotas que existem", async () => {
  await render();
  await click(teste("forgot-password-link"));
  expect(mockNavigate).toHaveBeenCalledWith("/recuperar");
  await click(teste("login-signup-link"));
  expect(mockNavigate).toHaveBeenCalledWith("/assinar");
});

// Cada rotulo precisa apontar para o campo: o rotulo encaixado na borda nao envolve o input.
test("os rotulos estao ligados aos campos", async () => {
  await render();
  for (const id of ["forge-login-email", "forge-login-senha"]) {
    const rotulo = host.querySelector(`label[for="${id}"]`);
    expect(rotulo).not.toBeNull();
    expect(document.getElementById(id) || host.querySelector(`#${id}`)).not.toBeNull();
  }
});
