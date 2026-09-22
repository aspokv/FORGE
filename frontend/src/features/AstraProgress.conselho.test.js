import {act} from "react";
import {createRoot} from "react-dom/client";
import AstraProgress from "./AstraProgress";

// Os filhos pesados nao interessam aqui: o que este arquivo mede e ONDE o Conselho
// aparece, e nao o que os outros cartoes desenham.
jest.mock("./ExerciseEvolution", () => () => <div data-testid="falso-exercicio" />);
jest.mock("./SessaoEvolucao", () => () => <div data-testid="falso-sessao" />);
jest.mock("./DietaEvolucao", () => () => <div data-testid="falso-dieta" />);
jest.mock("./workoutCalendar", () => ({useScheduledProgram: () => ({sessions: [], active_day: 1})}));

/*
 * O lugar do Conselho na tela de Evolucao.
 *
 * Ele nasceu montado FORA do `AstraProgress`, como irmao dele:
 *
 *     <><Conselho/><Progress/></>
 *
 * Parecia inofensivo e quebrou a tela de duas formas ao mesmo tempo. Medido num 390x844:
 * o cartao tinha 677px, empurrava o `.a6` para comecar em y=699, e o documento virava
 * 1480px numa janela de 844. Isso criava um SEGUNDO eixo de rolagem numa tela desenhada
 * para ter um so — e o ultimo cartao, "Um exercicio de cada vez", so aparecia rolando o
 * documento ate o fim E o container interno. Com o dedo isso nao acontece: o cartao
 * simplesmente nao era alcancavel.
 *
 * Alem disso ele aparecia ACIMA do cabecalho e das abas, solto, antes do titulo da
 * propria tela.
 *
 * Dentro do `AstraProgress` ele e um cartao como os outros, dentro do unico scroller. Os
 * testes abaixo prendem isso: que ele esta DENTRO da tela, na aba certa, e na abertura.
 */

const ANALYTICS = {prs: [], adherence_calendar: [], milestones: [], body_trend: []};

async function montar(props = {}) {
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  const root = createRoot(alvo);
  await act(async () => {
    root.render(<AstraProgress
      analytics={ANALYTICS}
      conselho={<div data-testid="conselho-falso">O Conselho</div>}
      weightPanel={<div />} photosPanel={<div />} details={<div />}
      API="/api" profileId="p1" exercises={[]} program={{}} {...props} />);
  });
  return {alvo, root};
}

async function abrirAba(alvo, rotulo) {
  await act(async () => {
    [...alvo.querySelectorAll("button")].find(b => b.textContent === rotulo).click();
  });
}

afterEach(() => { document.body.innerHTML = ""; });

test("o Conselho aparece DENTRO da tela de Evolucao", async () => {
  const {alvo} = await montar();
  const conselho = alvo.querySelector('[data-testid="conselho-falso"]');
  expect(conselho).not.toBeNull();
  // Montado por fora, ele nao teria a tela como ancestral — e foi assim que a rolagem
  // quebrou. O `closest` e exatamente a diferenca entre "irmao" e "filho".
  expect(conselho.closest('[data-testid="astra-progress"]')).not.toBeNull();
});

test("ele fica dentro do unico container de rolagem, junto dos outros cartoes", async () => {
  const {alvo} = await montar();
  const conselho = alvo.querySelector('[data-testid="conselho-falso"]');
  const sessao = alvo.querySelector('[data-testid="falso-sessao"]');
  // Mesmo pai: se um sair do scroller, a tela ganha um segundo eixo de rolagem.
  expect(conselho.closest(".a6-scroll")).toBe(sessao.closest(".a6-scroll"));
  expect(conselho.closest("details").open).toBe(false);
});

test("a recomendação fica após o resumo e antes da sessão do dia", async () => {
  // O Conselho e o unico bloco que DECIDE: ele pede uma resposta, entao vem primeiro.
  const {alvo} = await montar();
  const conselho = alvo.querySelector('[data-testid="conselho-falso"]');
  const sessao = alvo.querySelector('[data-testid="falso-sessao"]');
  const ordem = conselho.compareDocumentPosition(sessao);
  expect(ordem & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  const resumo=alvo.querySelector("[data-testid=evolucao-resumo]");
  expect(resumo.compareDocumentPosition(conselho) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("ele vem depois do titulo e das abas, e nao antes", async () => {
  const {alvo} = await montar();
  const titulo = [...alvo.querySelectorAll("h1,h2")].find(h => /Evolu/i.test(h.textContent));
  const conselho = alvo.querySelector('[data-testid="conselho-falso"]');
  expect(titulo).toBeTruthy();
  expect(titulo.compareDocumentPosition(conselho) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test.each([["Dieta"], ["Peso"], ["Fotos"]])("some na aba %s", async (aba) => {
  // Ele e o veredito do DESEMPENHO. Repetido nas outras abas viraria mobilia.
  const {alvo} = await montar();
  await abrirAba(alvo, aba);
  expect(alvo.querySelector('[data-testid="conselho-falso"]')).toBeNull();
});

test("volta ao trocar de volta para Desempenho", async () => {
  const {alvo} = await montar();
  await abrirAba(alvo, "Peso");
  await abrirAba(alvo, "Desempenho");
  expect(alvo.querySelector('[data-testid="conselho-falso"]')).not.toBeNull();
});

test("sem analytics a tela nao quebra nem mostra o Conselho pela metade", async () => {
  const {alvo} = await montar({analytics: null});
  expect(alvo.textContent).toContain("Carregando");
  expect(alvo.querySelector('[data-testid="conselho-falso"]')).toBeNull();
});
