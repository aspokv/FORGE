import {act} from "react";
import {createRoot} from "react-dom/client";
import DiarioLivre from "./DiarioLivre";

jest.mock("./FoodDiaryEditor", () => () => <div data-testid="editor-falso" />);

/*
 * O diário livre.
 *
 * O FORGE já guardava consumo fora do plano, mas o registro não dizia de QUE refeição
 * era: voltava para a tela como "Extra · 320 kcal", empilhado embaixo do plano, e o botão
 * se chamava "Adicionar um extra", perdido no fim da página entre outras ações.
 *
 * São duas perguntas diferentes: o plano responde "o que eu como hoje", o diário responde
 * "o que eu comi". Estes testes prendem o que a tela precisa fazer para não voltar a
 * misturar as duas.
 */

const REFEICOES = [
  {id: "breakfast", nome: "Café da manhã"},
  {id: "lunch", nome: "Almoço"},
  {id: "dinner", nome: "Jantar"},
];

const DIARIO_COM_REGISTROS = {
  extras: [
    {entry_id: "a", refeicao: "breakfast", refeicao_nome: "Café da manhã",
     actual: {totals: {kcal: 418}, foods: [{name: "Ovo mexido", grams: 150}]}},
    {entry_id: "b", refeicao: "lunch", refeicao_nome: "Almoço",
     actual: {totals: {kcal: 702}, foods: [{name: "Patinho", grams: 180}]}},
    // Um extra ANÔNIMO, do tempo anterior: ele não é do diário e não pode aparecer aqui.
    {entry_id: "c", actual: {totals: {kcal: 200}, foods: [{name: "Pão", grams: 50}]}},
  ],
};

function clienteFalso({status = 200} = {}) {
  return {
    get: jest.fn(async () => {
      if (status !== 200) {
        const erro = new Error("bloqueado");
        erro.response = {status, data: {detail: {capability: "free_food_log"}}};
        throw erro;
      }
      return {data: {refeicoes: REFEICOES}};
    }),
    delete: jest.fn(async () => ({data: {status: "removed"}})),
  };
}

async function montar({diario = {extras: []}, cliente = clienteFalso(),
                       onFoodCard} = {}) {
  const alvo = document.createElement("div");
  document.body.appendChild(alvo);
  const root = createRoot(alvo);
  const aoMudar = jest.fn();
  await act(async () => {
    root.render(<DiarioLivre API="/api" dia="2026-09-18" diario={diario}
                             aoMudar={aoMudar} axiosCliente={cliente}
                             onFoodCard={onFoodCard} />);
  });
  return {alvo, aoMudar, cliente};
}

afterEach(() => { document.body.innerHTML = ""; });

test("oferece uma refeição por vez, com nome", async () => {
  const {alvo} = await montar();
  expect(alvo.querySelector('[data-testid="diario-refeicao-breakfast"]').textContent)
    .toContain("Café da manhã");
  expect(alvo.querySelectorAll('[data-testid^="diario-refeicao-"]')).toHaveLength(3);
});

test("a lista de refeições vem do servidor, e não de uma cópia na tela", async () => {
  // Duas taxonomias de refeição no mesmo produto viram dois relatórios que não batem.
  const {cliente} = await montar();
  expect(cliente.get).toHaveBeenCalledWith("/api/nutrition/refeicoes-do-diario");
});

test("mostra o que já foi registrado, por refeição", async () => {
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS});
  expect(alvo.querySelector('[data-testid="diario-refeicao-breakfast"]').textContent)
    .toContain("418 kcal");
  expect(alvo.querySelector('[data-testid="diario-refeicao-dinner"]').textContent)
    .not.toContain("kcal");
});

test("soma só o que é do diário, ignorando o extra anônimo antigo", async () => {
  // 418 + 702 = 1120. O extra sem refeição (200) é do fluxo antigo e conta no dia, mas
  // não pertence a este cartão: somá-lo aqui faria o número do cartão brigar com ele mesmo.
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS});
  expect(alvo.querySelector('[data-testid="diario-total"]').textContent).toContain("1120");
});

test("a lista de registros não mistura o extra anônimo", async () => {
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS});
  const linhas = alvo.querySelectorAll('[data-testid="diario-registros"] li');
  expect(linhas).toHaveLength(2);
  expect(alvo.textContent).not.toContain("Pão");
});

test("tocar numa refeição abre o registro dela", async () => {
  const {alvo} = await montar();
  await act(async () => {
    alvo.querySelector('[data-testid="diario-refeicao-lunch"]').click();
  });
  expect(alvo.querySelector('[data-testid="diario-editor"]').textContent).toContain("Almoço");
  expect(alvo.querySelector('[data-testid="editor-falso"]')).not.toBeNull();
});

test("remover um registro avisa a tela para recarregar", async () => {
  const {alvo, cliente, aoMudar} = await montar({diario: DIARIO_COM_REGISTROS});
  await act(async () => {
    alvo.querySelector('[data-testid="diario-remover-a"]').click();
  });
  expect(cliente.delete).toHaveBeenCalledWith("/api/nutrition/consumed-extra/a");
  expect(aoMudar).toHaveBeenCalled();
});

test("sem o plano Elite, vira convite e não erro", async () => {
  const {alvo} = await montar({cliente: clienteFalso({status: 402})});
  expect(alvo.querySelector('[data-testid="diario-bloqueado"]')).not.toBeNull();
  expect(alvo.textContent).toContain("FORGE Elite");
  // Nunca o detalhe cru: em 402 ele é um objeto, e renderizar objeto derruba a tela.
  expect(alvo.textContent).not.toContain("free_food_log");
});

test("dia sem nada registrado não mostra total nem lista vazia", async () => {
  const {alvo} = await montar();
  expect(alvo.querySelector('[data-testid="diario-total"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="diario-registros"]')).toBeNull();
});


/*
 * A porta de entrada do Food Card.
 *
 * O Nicolas abriu o aplicativo e disse que não tinha achado o Food Card. Ele estava lá e
 * funcionava inteiro — o que havia era um ícone mudo de 34×34 encostado na lixeira, com o
 * mesmo contorno e a mesma cor dela. Ninguém adivinha que aquilo abre uma peça de Story, e
 * errar o toque apagava a refeição registrada.
 *
 * A aposta anterior estava escrita no código: "quem quiser transformar a refeição numa
 * peça vai procurar". Não se sustentou nem com quem construiu a funcionalidade.
 */
const click = node => node.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true}));

test("o botão do Food Card diz o próprio nome", async () => {
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS, onFoodCard: jest.fn()});
  const botao = alvo.querySelector('[data-testid="diario-food-card-a"]');
  expect(botao).not.toBeNull();
  // Rótulo VISÍVEL, e não só `aria-label`: quem está olhando a tela precisa ler a palavra.
  expect(botao.textContent).toContain("Food Card");
});

// Os dois eram DOIS ÍCONES MUDOS de 34px, com o mesmo contorno, separados por 12px. Era
// isso que tornava um indistinguível do outro, e num celular tocar em "apagar" achando que
// era "gerar a peça" apaga a refeição registrada.
//
// O que se pode medir aqui é a diferença de natureza: um tem texto, o outro é só ícone.
// A distância entre eles é layout, e jsdom não faz layout — foi medida no navegador
// (390×844: o botão passou de 34×34 para 324×44 e ficou a 298px da lixeira).
test("o Food Card deixou de ser um ícone mudo como a lixeira", async () => {
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS, onFoodCard: jest.fn()});
  const card = alvo.querySelector('[data-testid="diario-food-card-a"]');
  const lixeira = alvo.querySelector('[data-testid="diario-remover-a"]');
  expect(card.textContent.trim()).not.toBe("");
  expect(lixeira.textContent.trim()).toBe("");
  // A classe é por onde o CSS o tira da linha dos ícones e o põe em linha própria.
  expect(card.className).toContain("diario-food-card");
  expect(lixeira.className).not.toContain("diario-food-card");
});

test("abre o Food Card daquele registro, e não de outro", async () => {
  const onFoodCard = jest.fn();
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS, onFoodCard});
  await act(async () => { click(alvo.querySelector('[data-testid="diario-food-card-b"]')); });
  expect(onFoodCard).toHaveBeenCalledWith("b");
});

// Sem `onFoodCard` a tela que hospeda o diário não sabe abrir a peça. Mostrar o botão ali
// seria prometer uma coisa que não acontece ao tocar.
test("sem quem abra o Food Card, o botão não aparece", async () => {
  const {alvo} = await montar({diario: DIARIO_COM_REGISTROS});
  expect(alvo.querySelector('[data-testid="diario-food-card-a"]')).toBeNull();
  // E a lixeira continua onde estava: tirar o Food Card não pode levar o apagar junto.
  expect(alvo.querySelector('[data-testid="diario-remover-a"]')).not.toBeNull();
});
