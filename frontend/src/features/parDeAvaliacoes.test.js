import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { diaLocal, parDeAvaliacoes } from "./parDeAvaliacoes";
import { Foto } from "./ProgressPhotos";

/**
 * O defeito que estes testes travam foi visto em producao: com UMA avaliacao a tela
 * mostrava DOIS quadros grandes e vazios, com a MESMA data nos dois, como se houvesse um
 * "antes e agora" para comparar.
 *
 * Numa tela cujo proposito e mostrar evolucao, oferecer comparacao que nao existe e o pior
 * defeito possivel — pior que nao mostrar nada.
 */
const render = (elemento) =>
  new DOMParser().parseFromString(renderToStaticMarkup(elemento), "text/html");

const av = (id, iso) => ({ id, created_at: iso, views: ["front"] });

/* ── Quando ha o que comparar ─────────────────────────────────────────────── */

test("uma avaliacao nao produz comparacao", () => {
  const r = parDeAvaliacoes([av("a", "2025-08-31T10:00:00Z")]);
  expect(r.comparando).toBe(false);
  expect(r.atual).toBeNull();
  expect(r.unica.id).toBe("a");
});

test("dois registros do MESMO dia ainda sao uma avaliacao so", () => {
  // O fluxo antigo gravava um documento por angulo, e dois envios no mesmo dia tambem
  // viram dois documentos. Nenhum dos casos e "antes e agora".
  const r = parDeAvaliacoes([
    av("a", "2025-08-31T10:00:00Z"),
    av("b", "2025-08-31T18:30:00Z"),
  ]);
  expect(r.comparando).toBe(false);
  expect(r.atual).toBeNull();
  // Mostra a leitura mais recente do dia, e nao a primeira.
  expect(r.unica.id).toBe("b");
});

test("uma segunda foto em outra data liga a comparacao", () => {
  const r = parDeAvaliacoes([
    av("a", "2025-08-31T10:00:00Z"),
    av("b", "2025-09-21T10:00:00Z"),
  ]);
  expect(r.comparando).toBe(true);
  expect(r.primeira.id).toBe("a");
  expect(r.atual.id).toBe("b");
});

test("compara com a mais recente de outro dia, ignorando repeticoes do primeiro dia", () => {
  const r = parDeAvaliacoes([
    av("a", "2025-08-31T09:00:00Z"),
    av("b", "2025-08-31T20:00:00Z"),
    av("c", "2025-09-10T09:00:00Z"),
    av("d", "2025-09-21T09:00:00Z"),
  ]);
  expect(r.primeira.id).toBe("a");
  expect(r.atual.id).toBe("d");
});

test("sem data valida nao ha comparacao", () => {
  // Preferimos uma foto so a um "antes e agora" que pode estar errado.
  const r = parDeAvaliacoes([av("a", "2025-08-31T10:00:00Z"), av("b", "nao e data")]);
  expect(r.comparando).toBe(false);
});

test("lista vazia nao quebra", () => {
  expect(parDeAvaliacoes([]).comparando).toBe(false);
  expect(parDeAvaliacoes(undefined).unica).toBeNull();
  expect(diaLocal("nao e data")).toBeNull();
});

/* ── Os finais da moldura ─────────────────────────────────────────────────── */

test("foto registrada que nao carrega mostra aviso compacto e nova tentativa", () => {
  const doc = render(
    <Foto angulo="front" data="31 de ago." registrada aoTentarNovamente={() => {}} />
  );
  expect(doc.body.textContent).toContain("Não foi possível carregar esta foto");
  expect(doc.querySelector('[data-testid="tentar-novamente-foto"]')).not.toBeNull();
  // Compacta: a moldura perde a proporcao 3/4 para nao virar um retangulo alto e vazio.
  expect(doc.querySelector(".pf-quadro-falhou")).not.toBeNull();
  // E nao volta ao texto antigo, que nao dizia nem o que houve nem o que fazer.
  expect(doc.body.textContent).not.toContain("Imagem indisponível");
});

test("angulo nunca enviado nao e tratado como falha", () => {
  const doc = render(<Foto angulo="back" data="31 de ago." registrada={false} />);
  expect(doc.body.textContent).toContain("Sem foto de costas");
  expect(doc.body.textContent).not.toContain("Não foi possível carregar");
  expect(doc.querySelector('[data-testid="tentar-novamente-foto"]')).toBeNull();
  expect(doc.querySelector(".pf-quadro-falhou")).toBeNull();
});

test("sem armazenamento a tela explica, e nao oferece tentativa que nao resolveria", () => {
  const doc = render(
    <Foto angulo="front" data="hoje" registrada semArmazenamento aoTentarNovamente={() => {}} />
  );
  expect(doc.body.textContent).toContain("armazenamento permanente");
  expect(doc.querySelector('[data-testid="tentar-novamente-foto"]')).toBeNull();
});

test("com URL a foto comeca carregando, e escondida ate terminar", () => {
  const doc = render(<Foto foto={{ url: "https://x/y.jpg" }} angulo="front" data="hoje" registrada />);
  const img = doc.querySelector("img");
  expect(img).not.toBeNull();
  // Escondida: um endereco quebrado mostraria o proprio `alt` como texto na tela.
  expect(img.hasAttribute("hidden")).toBe(true);
  expect(doc.querySelector(".pf-brilho")).not.toBeNull();
});

test("os rotulos do par sao Antes e Agora, e o solo e Primeira avaliacao", () => {
  expect(render(<Foto rotulo="Antes" angulo="front" data="1" />).body.textContent).toContain("Antes");
  expect(render(<Foto rotulo="Agora" angulo="front" data="2" />).body.textContent).toContain("Agora");
  const solo = render(<Foto rotulo="Primeira avaliação" angulo="front" data="1" />);
  expect(solo.body.textContent).toContain("Primeira avaliação");
});

test("a foto recem-enviada aparece mesmo sem URL do servidor", () => {
  // Enquanto o bucket nao devolve assinatura, a copia local da sessao sustenta a tela: a
  // pessoa acabou de tirar a foto e nao pode terminar o envio olhando um vazio.
  const doc = render(
    <Foto reserva="blob:local-1" angulo="front" data="hoje" registrada rotulo="Primeira avaliação" />
  );
  const img = doc.querySelector("img");
  expect(img).not.toBeNull();
  expect(img.getAttribute("src")).toBe("blob:local-1");
  expect(doc.body.textContent).not.toContain("Não foi possível carregar");
});

test("a URL do servidor tem preferencia sobre a copia local", () => {
  const doc = render(
    <Foto foto={{ url: "https://assinada/x.jpg" }} reserva="blob:local-1" angulo="front" data="hoje" registrada />
  );
  expect(doc.querySelector("img").getAttribute("src")).toBe("https://assinada/x.jpg");
});
