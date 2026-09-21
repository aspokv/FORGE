import React, {act} from "react";
import {createRoot} from "react-dom/client";
import axios from "axios";
import Nutrition from "./Nutrition";

jest.mock("axios", () => ({get: jest.fn()}));
jest.mock("./NutritionImport", () => function Import({onActivated}) {
  return <button data-testid="activate-import-test" onClick={() => onActivated({plan: {
    source: "manual_import", meals: [],
    targets: {goal_calories:2398, protein_g:244, carbs_g:200, fat_g:67},
  }})}>Confirmar</button>;
});
global.IS_REACT_ACT_ENVIRONMENT = true;

const imported = {source:"manual_import", meals:[],
  targets:{goal_calories:2398, protein_g:244, carbs_g:200, fat_g:67}};
const generated = {meals:[], targets:{goal_calories:2870, protein_g:136, carbs_g:428.5, fat_g:68}};
const cycle = {ativo:true, hoje:{goal_calories:3100,protein_g:136,carbs_g:480,fat_g:68}};

function responses(plan, cycleData = cycle) {
  axios.get.mockImplementation(url => {
    if (url.endsWith("/nutrition/plan")) return Promise.resolve({data:plan});
    if (url.endsWith("/carb-cycle")) return Promise.resolve({data:cycleData});
    if (url.includes("/adherence/")) return Promise.resolve({data:{meals:[],extras:[]}});
    return Promise.resolve({data:{}});
  });
}
function expectImported(host) {
  const card = host.querySelector(".a6-gauge-panel");
  expect(card.textContent).toContain("2.398");
  expect([...card.querySelectorAll(".a6-goal")].map(el=>el.textContent))
    .toEqual(["de 244 g", "de 200 g", "de 67 g"]);
  expect(host.querySelector('[data-testid="carbo-do-dia"]')).toBeNull();
}

test("reload of an imported plan ignores automatic cycle targets", async () => {
  responses(imported);
  const host = document.createElement("div"), root = createRoot(host);
  try {
    await act(async()=>root.render(<Nutrition API="/api"/>));
    expectImported(host);
  } finally { await act(async()=>root.unmount()); }
});

test("activation replaces the previous plan and ignores its cached cycle", async () => {
  responses(generated);
  const host = document.createElement("div"), root = createRoot(host);
  try {
    await act(async()=>root.render(<Nutrition API="/api"/>));
    expect(host.querySelector(".a6-gauge-panel").textContent).toContain("3.100");
    await act(async()=>host.querySelector('[data-testid="open-diet-import"]').click());
    await act(async()=>host.querySelector('[data-testid="activate-import-test"]').click());
    expectImported(host);
  } finally { await act(async()=>root.unmount()); }
});
