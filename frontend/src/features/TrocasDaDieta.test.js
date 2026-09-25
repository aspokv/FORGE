import React, {act} from "react";
import {createRoot} from "react-dom/client";
import TrocasDaDieta, {agruparTrocas} from "./TrocasDaDieta";

global.IS_REACT_ACT_ENVIRONMENT = true;

// A tabela exatamente como o plano guarda depois de colar a dieta do atleta.
const TROCAS = [
  {titulo: "Substituições do carboidrato", opcoes: [
    {food_id: "potato", name: "Batata inglesa cozida", grams: 250},
    {food_id: "sweet-potato", name: "Batata doce cozida", grams: 200},
    {food_id: "cassava", name: "Mandioca cozida", grams: 150},
  ]},
  {titulo: "Substituições do carboidrato", opcoes: [
    {food_id: "potato", name: "Batata inglesa cozida", grams: 200},
    {food_id: "sweet-potato", name: "Batata doce cozida", grams: 160},
    {food_id: "cassava", name: "Mandioca cozida", grams: 120},
  ]},
];

async function render(trocas) {
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => root.render(<TrocasDaDieta trocas={trocas}/>));
  return {host, root};
}

test("mostra cada troca com o peso que a dieta escreveu", async () => {
  const {host, root} = await render(TROCAS);
  try {
    const linhas = [...host.querySelectorAll("li")].map(li => li.textContent.replace(/\s+/g, " ").trim());
    expect(linhas).toEqual([
      "250 g Batata inglesa cozida ou 200 g Batata doce cozida ou 150 g Mandioca cozida",
      "200 g Batata inglesa cozida ou 160 g Batata doce cozida ou 120 g Mandioca cozida",
    ]);
    // Um título por grupo, e não um por linha.
    expect(host.querySelectorAll(".fg-trocas-grupo")).toHaveLength(1);
    expect(host.textContent).toContain("Substituições do carboidrato");
  } finally { await act(async () => root.unmount()); }
});

test("sem trocas não ocupa espaço nenhum na tela", async () => {
  for (const vazio of [undefined, null, [], [{titulo: "x", opcoes: [{name: "só uma"}]}]]) {
    const {host, root} = await render(vazio);
    try { expect(host.innerHTML).toBe(""); }
    finally { await act(async () => root.unmount()); }
  }
});

test("opção fora do catálogo continua aparecendo com o texto da dieta", () => {
  const grupos = agruparTrocas([{titulo: "Trocas", opcoes: [
    {food_id: "rice-white", name: "Arroz branco cozido", grams: 100},
    {food_id: null, name: "cuscuz nordestino", grams: 120},
  ]}]);
  expect(grupos[0].linhas[0].map(o => o.name)).toEqual(["Arroz branco cozido", "cuscuz nordestino"]);
});
