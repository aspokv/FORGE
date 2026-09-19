import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ObservacaoDoExercicio from "./ObservacaoDoExercicio";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
jest.useFakeTimers();

/**
 * A observação embaixo do exercício.
 *
 * O que estes testes prendem:
 *
 * 1. A nota da ÚLTIMA vez aparece. É ela que faz alguém escrever a próxima: sem isso a
 *    observação é um diário, e diário a pessoa abandona na segunda semana.
 *
 * 2. Digitar não vira uma requisição por tecla. O campo espera a pessoa parar.
 *
 * 3. Sair do campo salva na hora, sem esperar o atraso. Em celular, tocar em "concluir
 *    treino" tira o foco do campo — se só o atraso salvasse, a última frase digitada se
 *    perderia exatamente no momento em que a pessoa fecha a sessão.
 *
 * 4. Falhar ao salvar não põe um erro grande no meio de uma série. A observação é
 *    acessória e não pode roubar a atenção de quem está treinando.
 */

const API = "/api";

function cliente(post = jest.fn(() => Promise.resolve({ data: {} }))) {
  return { post };
}

const click = node => node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));

function digitar(area, valor) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, "value").set;
  setter.call(area, valor);
  area.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("observação do exercício", () => {
  let host, root;

  const montar = async props => act(async () => root.render(
    <ObservacaoDoExercicio API={API} exerciseId="triceps-pushdown" dia="2026-09-19" {...props} />));
  const ver = id => host.querySelector(`[data-testid="${id}"]`);

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    host.remove();
  });

  test("sem nota nenhuma o campo fica fechado, para não competir com carga e reps", async () => {
    await montar({ axiosCliente: cliente() });
    expect(ver("obs-abrir-triceps-pushdown")).toBeTruthy();
    expect(ver("obs-campo-triceps-pushdown")).toBeNull();
  });

  test("com nota de hoje o campo já abre com o texto", async () => {
    await montar({ axiosCliente: cliente(), inicial: "Usei a polia alta" });
    expect(ver("obs-campo-triceps-pushdown").value).toBe("Usei a polia alta");
  });

  test("a observação da última vez aparece acima do campo", async () => {
    await montar({
      axiosCliente: cliente(), inicial: "hoje",
      anterior: { texto: "A máquina estava ocupada", date: "2026-09-12" },
    });
    expect(ver("obs-anterior-triceps-pushdown").textContent)
      .toContain("A máquina estava ocupada");
  });

  test("digitar não manda uma requisição por tecla", async () => {
    const c = cliente();
    await montar({ axiosCliente: c, inicial: "a" });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => {
      digitar(campo, "ab");
      digitar(campo, "abc");
      digitar(campo, "abcd");
    });
    expect(c.post).not.toHaveBeenCalled();

    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(c.post).toHaveBeenCalledTimes(1);
    expect(c.post.mock.calls[0][1].texto).toBe("abcd");
  });

  test("sair do campo salva na hora, sem esperar o atraso", async () => {
    const c = cliente();
    await montar({ axiosCliente: c, inicial: "a" });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => digitar(campo, "usei outra máquina"));
    await act(async () => campo.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));

    expect(c.post).toHaveBeenCalledTimes(1);
    expect(c.post.mock.calls[0][1]).toMatchObject({
      exercise_id: "triceps-pushdown", date: "2026-09-19", texto: "usei outra máquina",
    });
  });

  test("salvar o mesmo texto de novo não chama a API", async () => {
    const c = cliente();
    await montar({ axiosCliente: c, inicial: "igual" });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => campo.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));
    expect(c.post).not.toHaveBeenCalled();
  });

  test("apagar o texto é uma mudança, e é salva", async () => {
    const c = cliente();
    await montar({ axiosCliente: c, inicial: "vai sumir" });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => digitar(campo, ""));
    await act(async () => campo.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));
    expect(c.post.mock.calls[0][1].texto).toBe("");
  });

  test("o dia da sessão vai junto, para a nota cair no dia certo", async () => {
    const c = cliente();
    await montar({ axiosCliente: c, inicial: "x", sessionDay: 3 });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => digitar(campo, "y"));
    await act(async () => campo.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));
    expect(c.post.mock.calls[0][1].session_day).toBe(3);
  });

  test("falhar ao salvar não joga erro na cara de quem está treinando", async () => {
    const c = cliente(jest.fn(() => Promise.reject(new Error("sem rede"))));
    await montar({ axiosCliente: c, inicial: "x" });
    const campo = ver("obs-campo-triceps-pushdown");
    await act(async () => digitar(campo, "y"));
    await act(async () => campo.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));

    expect(host.querySelector('[role="alert"]')).toBeNull();
    expect(ver("obs-estado-triceps-pushdown").textContent).toBe("não salvou");
    // O texto continua na tela: perder o que a pessoa escreveu seria pior que o erro.
    expect(ver("obs-campo-triceps-pushdown").value).toBe("y");
  });

  test("abrir pelo botão mostra o campo vazio pronto para escrever", async () => {
    await montar({ axiosCliente: cliente() });
    await act(async () => click(ver("obs-abrir-triceps-pushdown")));
    expect(ver("obs-campo-triceps-pushdown")).toBeTruthy();
    expect(ver("obs-campo-triceps-pushdown").value).toBe("");
  });
});
