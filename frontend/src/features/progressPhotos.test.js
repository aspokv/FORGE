import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ProgressPhotos from "./ProgressPhotos";
import VisualPhotoUpload, { ANGULOS } from "./VisualPhotoUpload";
import {
  compararAvaliacoes,
  intervaloEmPalavras,
} from "./compararAvaliacoes";

/**
 * Criterios de aceite da evolucao visual.
 *
 * O que estes testes protegem nao e o pixel, e as decisoes: quatro angulos e nao mais,
 * historico que nao some, e — o mais importante — nao afirmar evolucao que a evidencia
 * nao sustenta. Numa tela cujo proposito e mostrar evolucao, inventar mudanca seria o
 * pior defeito possivel.
 */
const render = (elemento) =>
  new DOMParser().parseFromString(renderToStaticMarkup(elemento), "text/html");

/* ── Envio ─────────────────────────────────────────────────────────────────── */

test("os quatro angulos sao exatamente os que o servidor aceita", () => {
  expect(ANGULOS.map((a) => a.id)).toEqual(["front", "back", "left", "right"]);
  expect(ANGULOS).toHaveLength(4);
});

test("o envio e de UMA foto, e nao de quatro espacos ao mesmo tempo", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  const entrada = doc.querySelector('[data-testid="adicionar-fotos"] input');
  // Quatro molduras vazias de uma vez lem como formulario a preencher.
  expect(entrada.hasAttribute("multiple")).toBe(false);
  const aceita = entrada.getAttribute("accept");
  ["image/jpeg", "image/png", "image/webp", "image/heic"].forEach((t) =>
    expect(aceita).toContain(t)
  );
});

test("o angulo comeca em Frente, que e o que quase todo mundo manda", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  const sel = doc.querySelector('[data-testid="angulo-foto"]');
  const selecionada = sel.querySelector("option[selected]") || sel.querySelector("option");
  expect(selecionada.getAttribute("value")).toBe("front");
});

test("a tela de envio nao mostra quatro espacos de angulo", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  expect(doc.querySelectorAll('[data-testid="adicionar-fotos"]')).toHaveLength(1);
  expect(doc.querySelectorAll(".vp-previa")).toHaveLength(0);
});

test("sem foto escolhida, o envio fica desabilitado", () => {
  const doc = render(<VisualPhotoUpload API="/api" profileId="u1" />);
  expect(
    doc.querySelector('[data-testid="submit-visual-assessment"]').hasAttribute("disabled")
  ).toBe(true);
});

test("o envio orienta o enquadramento em vez de pedir montagem", () => {
  const texto = render(<VisualPhotoUpload API="/api" profileId="u1" />).body.textContent;
  expect(texto).toContain("Corpo inteiro");
  expect(texto).not.toContain("colagem");
});

/* ── Estados da tela ───────────────────────────────────────────────────────── */

test("carregando mostra esqueleto, e nao texto de espera nem cara de erro", () => {
  const doc = render(<ProgressPhotos API="/api" profileId="u1" />);
  // Um quadro so: o padrao e uma foto por atualizacao.
  expect(doc.querySelectorAll(".pf-brilho").length).toBe(1);
  expect(doc.body.textContent).not.toContain("Erro");
  expect(doc.body.textContent).not.toContain("Carregando");
});

test("a secao existe e oferece nova atualizacao", () => {
  const doc = render(<ProgressPhotos API="/api" profileId="u1" />);
  expect(doc.querySelector('[data-testid="progress-photos"]')).not.toBeNull();
  expect(doc.querySelector('[data-testid="nova-atualizacao-visual"]')).not.toBeNull();
});

test("nenhum termo tecnico aparece na tela de evolucao", () => {
  const texto = render(<ProgressPhotos API="/api" profileId="u1" />).body.textContent;
  ["Gemini", "S3", "bucket", "R2", "upload"].forEach((termo) =>
    expect(texto).not.toContain(termo)
  );
});

/* ── Comparacao: o que pode e o que nao pode ser afirmado ──────────────────── */

const obs = (nivel, confianca = "alta") => ({ development: nivel, confidence: confianca });

test("um grupo so conta como evolucao quando as duas leituras sao confiaveis", () => {
  const r = compararAvaliacoes(
    { id: "a", observations: { Peitoral: obs("fraco"), Ombros: obs("fraco", "baixa") } },
    { id: "b", observations: { Peitoral: obs("proporcional"), Ombros: obs("forte") } }
  );
  expect(r.confiavel).toBe(true);
  expect(r.melhoraram).toEqual(["Peitoral"]);
  // Ombros tinha confianca BAIXA na primeira leitura: duas incertezas nao viram certeza.
  expect(r.melhoraram).not.toContain("Ombros");
});

test("sem grupos em comum, nao ha o que afirmar", () => {
  const r = compararAvaliacoes(
    { id: "a", observations: { Peitoral: obs("fraco") } },
    { id: "b", observations: { Panturrilhas: obs("forte") } }
  );
  expect(r.confiavel).toBe(false);
  expect(r.motivo).toBe("sem_grupos_comparaveis");
});

test("a mesma avaliacao comparada consigo mesma nao produz evolucao", () => {
  const um = { id: "a", observations: { Peitoral: obs("fraco") } };
  const r = compararAvaliacoes(um, um);
  expect(r.confiavel).toBe(false);
  expect(r.motivo).toBe("sem_par");
});

test("queda tambem e registrada, e nao so melhora", () => {
  const r = compararAvaliacoes(
    { id: "a", observations: { Peitoral: obs("forte") } },
    { id: "b", observations: { Peitoral: obs("proporcional") } }
  );
  expect(r.pioraram).toEqual(["Peitoral"]);
  expect(r.melhoraram).toEqual([]);
});

test("sem mudanca de nivel, o resultado diz que seguiu igual", () => {
  const r = compararAvaliacoes(
    { id: "a", observations: { Peitoral: obs("forte"), Dorsais: obs("forte") } },
    { id: "b", observations: { Peitoral: obs("forte"), Dorsais: obs("forte") } }
  );
  expect(r.confiavel).toBe(true);
  expect(r.mantiveram).toBe(2);
  expect(r.melhoraram).toEqual([]);
});

/* ── Intervalo em linguagem natural ────────────────────────────────────────── */

test.each([
  ["2026-01-01", "2026-01-01", "mesmo dia"],
  ["2026-01-01", "2026-01-02", "1 dia de evolução"],
  ["2026-01-01", "2026-01-06", "5 dias de evolução"],
  ["2026-01-01", "2026-01-22", "3 semanas de evolução"],
  ["2026-01-01", "2026-03-02", "2 meses de evolução"],
])("intervalo entre %s e %s vira %s", (de, ate, esperado) => {
  expect(intervaloEmPalavras(de, ate)).toBe(esperado);
});

test("data invalida nao quebra o intervalo", () => {
  expect(intervaloEmPalavras("", "2026-01-01")).toBe("");
});

/* ── Concordancia e contagem ───────────────────────────────────────────────── */

test("a frase da mudanca concorda em numero", () => {
  // "3 grupos subiu de nivel" era o texto anterior. Erro de concordancia numa tela que
  // se apresenta como leitura de treinador derruba a credibilidade do resto.
  const doc = new DOMParser().parseFromString(
    renderToStaticMarkup(
      <ProgressPhotos API="/api" profileId="u1" />
    ),
    "text/html"
  );
  expect(doc.body.textContent).not.toContain("grupos subiu");
});
