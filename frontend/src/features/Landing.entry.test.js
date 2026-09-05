import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import Landing from "./Landing";

/**
 * O que a entrada publica precisa manter.
 *
 * As afirmacoes sobre a maquete antiga sairam junto com ela: a pagina remontava a Home em
 * marcacao, com calorias e cargas ilustrativas, e por isso precisava da legenda "Dados
 * ilustrativos" e de um `alt` falando de costas. Agora sao capturas reais do produto, que
 * nao pedem ressalva. O que ficou — e o que este arquivo protege — e o contrato de
 * integracao: o titulo, o caminho ate os planos e o acesso de quem ja tem conta.
 */
function render() {
  const html = renderToStaticMarkup(
    <Landing API="/api" onComecar={() => {}} onEntrar={() => {}} />
  );
  return new DOMParser().parseFromString(html, "text/html");
}

test("a entrada publica preserva catalogo e login", () => {
  const doc = render();
  // O titulo do hero saiu junto com o bloco de abertura: a capa e so o filme. O que a
  // entrada publica ainda precisa garantir e o caminho ate os planos e ate o login.
  expect(doc.querySelector('[data-testid="landing-primary-cta"]').getAttribute("href"))
    .toBe("#planos");
  expect(doc.querySelector("#planos")).not.toBeNull();
  expect(doc.querySelector('[data-testid="landing-login"]')).not.toBeNull();
  expect(doc.querySelector(".landing-instrument")).toBeNull();
});

/**
 * A capa nao tem nada por cima nem por baixo do filme.
 *
 * Foi o pedido explicito: sem titulo, sem CTA, sem cartao em volta. Este teste existe
 * para a abertura nao voltar a ganhar um bloco de texto sem que alguem perceba.
 */
test("a capa e so o filme, sem texto nem botao sobreposto", () => {
  const capa = render().querySelector(".lp-capa");
  expect(capa).not.toBeNull();
  expect(capa.querySelector("h1")).toBeNull();
  expect(capa.querySelector("button")).toBeNull();
  expect(capa.querySelector("a")).toBeNull();
  // O unico conteudo e o quadro do filme.
  expect(capa.querySelector(".lp-filme-quadro")).not.toBeNull();
  expect(capa.textContent.trim()).toBe("");
});

test("os botoes de integracao existem com rotulo e identificador estaveis", () => {
  const doc = render();
  const rotulo = (sel) =>
    doc.querySelector(sel).textContent.replace(/\s+/g, " ").trim();

  // "Conhecer os planos" deixou de ser botao do hero e passou a ser o link do menu:
  // mesmo destino e mesmo identificador, para a integracao nao perder o gancho.
  expect(rotulo("#landing-conhecer-os-planos")).toBe("Conhecer os planos");
  expect(doc.querySelector("#landing-conhecer-os-planos").getAttribute("href")).toBe("#planos");
  expect(rotulo("#landing-comecar-agora")).toBe("Começar agora");

  // O topo e o rodape levam para o login, com id proprio para nao duplicar.
  expect(rotulo("#landing-ja-tenho-conta-topo")).toBe("Já tenho conta");
  expect(rotulo("#landing-ja-tenho-conta-rodape")).toBe("Já tenho conta");
});

test("o hero abre com o filme, e nao com dado inventado", () => {
  const doc = render();
  const quadro = doc.querySelector(".lp-filme-quadro");
  expect(quadro).not.toBeNull();

  // Poster e video no mesmo quadro: a altura ja esta reservada antes de o video chegar.
  const poster = quadro.querySelector(".lp-filme-poster");
  const video = quadro.querySelector("video");
  expect(poster.getAttribute("src")).toBeTruthy();
  expect(video.getAttribute("poster")).toBe(poster.getAttribute("src"));
  expect(video.querySelector("source").getAttribute("type")).toBe("video/mp4");
  expect(video.querySelector("source").getAttribute("src")).toBeTruthy();

  // A maquete remontada continua fora da pagina.
  expect(doc.querySelector(".entry-screen")).toBeNull();
  expect(doc.body.textContent).not.toContain("Dados ilustrativos");
});

/**
 * O contrato do video.
 *
 * Autoplay so e permitido sem som, e sem `playsinline` o iPhone abre em tela cheia no
 * lugar de tocar embutido. Sao os quatro atributos que fazem a peca funcionar como cena
 * em vez de player — e `controls` nao pode aparecer.
 */
test("o video toca sozinho, mudo, em loop e sem controles", () => {
  const video = render().querySelector(".lp-filme-quadro video");
  ["autoplay", "muted", "loop", "playsinline"].forEach((attr) =>
    expect(video.hasAttribute(attr)).toBe(true)
  );
  expect(video.hasAttribute("controls")).toBe(false);
});

/**
 * A regressao que motivou o refino anterior, agora so no storytelling.
 *
 * Duas telas ja foram trocadas por recortes que traziam a moldura dentro do arquivo, e o
 * fundo retangular virava uma caixa preta sobre o cenario. O contrato que impede a volta
 * disso: toda tela e uma <img> dentro de um `.lp-fone`, todas na mesma medida.
 */
test("toda tela vive dentro da moldura desenhada, e nao dentro do arquivo", () => {
  const doc = render();
  const imagens = [...doc.querySelectorAll(".lp-fone img")];
  const soltas = [...doc.querySelectorAll(".lp-story-palco img")]
    .filter((i) => !i.closest(".lp-fone"));

  expect(imagens).toHaveLength(4); // as quatro telas do storytelling
  expect(soltas).toEqual([]);

  const medidas = new Set(
    imagens.map((i) => `${i.getAttribute("width")}x${i.getAttribute("height")}`)
  );
  expect([...medidas]).toEqual(["648x1404"]);
});

test("o storytelling separa as quatro telas, incluindo a inicial", () => {
  const doc = render();
  const fones = doc.querySelectorAll(".lp-story-fone img");
  expect(fones).toHaveLength(4);
  const alts = [...fones].map((f) => f.getAttribute("alt").toLowerCase());
  ["treino", "nutrição", "inicial", "progresso"].forEach((area) =>
    expect(alts.some((a) => a.includes(area))).toBe(true)
  );
});

test("o preco nunca e escrito na pagina, so o que a API devolver", () => {
  // O catalogo chega por /api/billing/plans. Sem resposta, a pagina nao inventa valor —
  // e a garantia de que nao existe um segundo lugar onde o preco possa divergir.
  const doc = render();
  expect(doc.querySelector(".lp-planos").children).toHaveLength(0);
  expect(doc.body.textContent).not.toMatch(/R\$\s*\d/);
});

test("o nome do plano vira caixa de frase no botao de assinatura", () => {
  // O catalogo devolve "FORGE ESSENCIAL"; o botao pedido e "Assinar Essencial".
  const { nomeCurto } = require("./Landing");
  expect(nomeCurto("FORGE ESSENCIAL")).toBe("Essencial");
  expect(nomeCurto("FORGE PRO")).toBe("Pro");
  expect(nomeCurto("FORGE ELITE")).toBe("Elite");
});
