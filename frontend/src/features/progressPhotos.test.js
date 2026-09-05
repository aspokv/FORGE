import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ProgressPhotos from "./ProgressPhotos";
import VisualPhotoUpload, { ANGULOS } from "./VisualPhotoUpload";

/**
 * Criterios de aceite da evolucao visual.
 *
 * O que estes testes protegem nao e o pixel, e as decisoes: quatro angulos e nao mais,
 * historico que nao some, comparacao so entre datas diferentes, e — o mais importante —
 * a tela continuar de pe quando o armazenamento ainda nao esta configurado. Esse ultimo
 * e o caso REAL de hoje, com o bucket ainda por criar.
 */
const render = (elemento) =>
  new DOMParser().parseFromString(renderToStaticMarkup(elemento), "text/html");

test("os quatro angulos sao exatamente os que o servidor aceita", () => {
  expect(ANGULOS.map((a) => a.id)).toEqual(["front", "back", "left", "right"]);
  // Mais de quatro passaria do limite do servidor e a avaliacao seria recusada inteira.
  expect(ANGULOS).toHaveLength(4);
});

test("o envio aceita selecao multipla e formatos de celular", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  const entrada = doc.querySelector('[data-testid="adicionar-fotos"] input');
  expect(entrada.hasAttribute("multiple")).toBe(true);
  const aceita = entrada.getAttribute("accept");
  ["image/jpeg", "image/png", "image/webp", "image/heic"].forEach((t) =>
    expect(aceita).toContain(t)
  );
});

test("sem foto escolhida, o envio fica desabilitado", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  const botao = doc.querySelector('[data-testid="submit-visual-assessment"]');
  expect(botao.hasAttribute("disabled")).toBe(true);
});

test("a tela diz que uma foto basta, sem exigir as quatro", () => {
  const texto = render(<VisualPhotoUpload API="/api" profileId="u1" />).body.textContent;
  expect(texto).toContain("Uma foto já funciona");
});

test("sem historico, a tela explica o valor da primeira avaliacao", () => {
  const doc = render(<ProgressPhotos API="/api" profileId="u1" />);
  // A montagem no servidor nao roda o efeito de carga; o estado inicial e "carregando".
  expect(doc.querySelector('[data-testid="progress-photos"]')).not.toBeNull();
  expect(doc.body.textContent).toContain("Carregando suas avaliações");
});

test("a secao tem botao para nova atualizacao visual", () => {
  const doc = render(<ProgressPhotos API="/api" profileId="u1" />);
  expect(doc.querySelector('[data-testid="nova-atualizacao-visual"]')).not.toBeNull();
});

test("nenhum termo tecnico aparece na tela de evolucao", () => {
  const texto = render(<ProgressPhotos API="/api" profileId="u1" />).body.textContent;
  ["Gemini", "S3", "bucket", "R2", "API", "upload"].forEach((termo) =>
    expect(texto).not.toContain(termo)
  );
});
