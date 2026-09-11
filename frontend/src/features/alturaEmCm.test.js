import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { lerAltura, emMetros, ALTURA_MIN_CM, ALTURA_MAX_CM } from "./alturaEmCm";
import CampoAltura from "./CampoAltura";

/**
 * O campo pede centimetros e a pessoa escreve como fala: "1,80".
 *
 * Guardar isso como 1,80 CENTIMETRO nao gerava erro nenhum — gerava um plano inteiro
 * errado. Em producao, uma atleta de 65 kg com a altura em metros recebeu uma meta de
 * 427 kcal por dia, com carboidrato zerado, porque a TMB calculada deu 348 kcal.
 *
 * A escolha de projeto que estes testes guardam: o campo INTERPRETA e MOSTRA o que
 * entendeu, em vez de oferecer um seletor "m / cm". O seletor adicionaria uma decisao sem
 * eliminar o erro — quem digita "1,80" com o seletor em "cm" erra igual, e a interface
 * ainda concorda com ele.
 */
const render = (el) =>
  new DOMParser().parseFromString(renderToStaticMarkup(el), "text/html");

/* ── A leitura ────────────────────────────────────────────────────────────── */

test("metros viram centimetros", () => {
  expect(lerAltura("1,80").cm).toBe(180);
  expect(lerAltura("1.80").cm).toBe(180);
  expect(lerAltura("1,63").cm).toBe(163);
  expect(lerAltura("2").cm).toBe(200);
});

test("centimetros passam intactos", () => {
  expect(lerAltura("180").cm).toBe(180);
  expect(lerAltura("163").cm).toBe(163);
  expect(lerAltura(178).cm).toBe(178);
});

test("a leitura diz QUANDO converteu", () => {
  // E o que decide se o eco aparece: aviso que sempre aparece vira moldura e para de ser lido.
  expect(lerAltura("1,80").interpretado).toBe(true);
  expect(lerAltura("180").interpretado).toBe(false);
});

test("virgula e ponto sao a mesma coisa", () => {
  expect(lerAltura("1,75").cm).toBe(lerAltura("1.75").cm);
});

test("campo vazio ou ilegivel nao vira numero", () => {
  // Zero seria pior que nada: entraria no calculo como uma altura de verdade.
  expect(lerAltura("").cm).toBeNull();
  expect(lerAltura("   ").cm).toBeNull();
  expect(lerAltura("abc").cm).toBeNull();
  expect(lerAltura(null).cm).toBeNull();
  expect(lerAltura(undefined).cm).toBeNull();
  expect(lerAltura("-170").cm).toBeNull();
});

test("altura que ninguem tem e sinalizada", () => {
  expect(lerAltura("300").foraDeFaixa).toBe(true);
  expect(lerAltura("40").foraDeFaixa).toBe(true);
  expect(lerAltura("1,80").foraDeFaixa).toBe(false);
  expect(lerAltura(String(ALTURA_MIN_CM)).foraDeFaixa).toBe(false);
  expect(lerAltura(String(ALTURA_MAX_CM)).foraDeFaixa).toBe(false);
});

test("o eco em metros usa virgula, como se escreve em portugues", () => {
  expect(emMetros(180)).toBe("1,80 m");
  expect(emMetros(163)).toBe("1,63 m");
});

/* ── O campo ──────────────────────────────────────────────────────────────── */

test("digitar em metros mostra a conversao", () => {
  const doc = render(<CampoAltura valor="1,80" aoMudar={() => {}} />);
  const eco = doc.querySelector('[data-testid="altura-convertida"]');
  expect(eco).not.toBeNull();
  expect(eco.textContent).toContain("1,80 m");
  expect(eco.textContent).toContain("180 cm");
});

test("digitar em centimetros confirma sem alardear conversao", () => {
  const doc = render(<CampoAltura valor="180" aoMudar={() => {}} />);
  expect(doc.querySelector('[data-testid="altura-convertida"]')).toBeNull();
  expect(doc.querySelector('[data-testid="altura-confirmada"]').textContent).toContain("1,80 m");
});

test("a unidade dentro do campo acompanha o que foi digitado", () => {
  // E a confirmacao mais rapida que existe: vem antes de a pessoa ler o eco.
  expect(render(<CampoAltura valor="1,80" aoMudar={() => {}} />)
    .querySelector(".fg-altura-unidade").textContent).toBe("m");
  expect(render(<CampoAltura valor="180" aoMudar={() => {}} />)
    .querySelector(".fg-altura-unidade").textContent).toBe("cm");
});

test("altura impossivel avisa em vez de aceitar calada", () => {
  const doc = render(<CampoAltura valor="300" aoMudar={() => {}} />);
  expect(doc.querySelector('[data-testid="altura-fora-de-faixa"]')).not.toBeNull();
});

test("campo vazio nao mostra eco nenhum", () => {
  const doc = render(<CampoAltura valor="" aoMudar={() => {}} />);
  expect(doc.querySelector(".fg-altura-eco").textContent.trim()).toBe("");
});

test("o campo aceita virgula no teclado do celular", () => {
  // `type="number"` esconderia a virgula em parte dos aparelhos — justamente como a
  // pessoa escreve 1,80.
  const input = render(<CampoAltura valor="" aoMudar={() => {}} />).querySelector("input");
  expect(input.getAttribute("inputmode")).toBe("decimal");
  expect(input.getAttribute("type")).toBe("text");
});

test("o eco e anunciado por leitor de tela", () => {
  const doc = render(<CampoAltura valor="1,80" aoMudar={() => {}} />);
  const eco = doc.querySelector(".fg-altura-eco");
  expect(eco.getAttribute("aria-live")).toBe("polite");
  expect(doc.querySelector("input").getAttribute("aria-describedby")).toBe(eco.getAttribute("id"));
});

test("a leitura da tela concorda com a do servidor", () => {
  // O backend normaliza abaixo de 3; a tela precisa usar o MESMO limite, senao a
  // confirmacao mostraria uma coisa e o plano sairia com outra.
  expect(lerAltura("2,99").cm).toBe(299);
  expect(lerAltura("3").cm).toBe(3);
  expect(lerAltura("3").foraDeFaixa).toBe(true);
});
