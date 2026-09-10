import fs from "fs";
import path from "path";
import React, {act} from "react";
import {createRoot} from "react-dom/client";
import {renderToStaticMarkup} from "react-dom/server";
import {trainingCategoryFor, trainingProfileFor, resolveTrainingArtwork} from "./trainingCardArtwork";
import TrainingCardImage from "./TrainingCardImage";
import ReferenceHome from "./ReferenceHome";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";

jest.mock("../assets/training-cards/manifest", () => {
  const categories = ["push","pull","legs-quads","legs-posterior","upper","fullbody","chest","back","shoulders","arms","default"];
  return {__esModule:true,default:Object.fromEntries(["male","female","neutral"].map(profile => [
    profile,Object.fromEntries(categories.map(category => [category,"/training-cards/"+profile+"/"+category+".webp"]))
  ]))};
});

test.each([
  ["Push 1","push"],["Push Ombros","push"],["Pull 1","pull"],["Pull Costas","pull"],
  ["Legs Completo","legs-quads"],["Legs Quadríceps","legs-quads"],["Legs Posterior","legs-posterior"],
  ["Upper A","upper"],["Upper B","upper"],["Full Body A","fullbody"],["Full Body B","fullbody"],
  ["Peito","chest"],["Costas","back"],["Ombros","shoulders"],["Braços","arms"],
  ["Peito e ombros","push"],["Peito e tríceps","push"],["Costas e bíceps","pull"],["Custom híbrido","default"],
  ["Upper + Full Body","fullbody"],["OMBROS POSTERIORES","shoulders"],
  ["Legs Posterior e Quadríceps","legs-posterior"],["Legs Quadríceps e Posterior","legs-quads"],
  ["FULL_BODY-B","fullbody"],["Dia 2 — Pull Costas","pull"]
])("%s resolves to %s", (label,expected) => expect(trainingCategoryFor(label)).toBe(expected));

test("focus and metadata cover unnamed and custom sessions without overriding specific labels", () => {
  expect(trainingCategoryFor({label:"Custom híbrido",focus:["Peito","Costas"]})).toBe("upper");
  expect(trainingCategoryFor({label:"Sessão A",category:"legs-posterior"})).toBe("legs-posterior");
  expect(trainingCategoryFor({label:"Legs Posterior",category:"legs",focus:["Quadríceps"]})).toBe("legs-posterior");
  expect(trainingCategoryFor(null)).toBe("default");
  expect(trainingCategoryFor({focus:null})).toBe("default");
  expect(trainingCategoryFor({focus:"Costas e bíceps"})).toBe("pull");
});

test("program audience precedes profile and missing values stay neutral", () => {
  expect(trainingProfileFor({audience_type:"female"},{sex:"male"})).toBe("female");
  expect(trainingProfileFor({},{assessment:{sex:"FEMININO"}})).toBe("female");
  expect(trainingProfileFor({},{sex:" M "})).toBe("male");
  expect(trainingProfileFor({audience:"unisex"},{sex:"male"})).toBe("neutral");
  expect(trainingProfileFor(null,null)).toBe("neutral");
});

test("fallback order is profile category, neutral category, neutral default", () => {
  const catalog={male:{push:"male-push"},neutral:{push:"neutral-push",default:"neutral-default"}};
  const options={session:"Push 1",profile:{sex:"male"}};
  expect(resolveTrainingArtwork(options,catalog).candidates.map(x=>x.src)).toEqual(["male-push","neutral-push","neutral-default"]);
  expect(resolveTrainingArtwork({...options,profile:{sex:"female"}},catalog).src).toBe("neutral-push");
  expect(resolveTrainingArtwork({...options,session:"???"},catalog).src).toBe("neutral-default");
});

const visualFrames=[];

test.each([["male","Push 1","push"],["male","Pull Costas","pull"],["male","Legs Posterior","legs-posterior"],["female","Upper B","upper"],["neutral","Custom híbrido","default"]])("home and current workout agree for %s %s",(sex,label,category)=>{
  const session={day:1,label,focus:[],exercises:[]};
  const db={profile:{sex,name:"Atleta"},program:{active_day:1,sessions:[session]}};
  const home=new DOMParser().parseFromString(renderToStaticMarkup(<ReferenceHome db={db} start={()=>{}}/>),"text/html");
  const preview=new DOMParser().parseFromString(renderToStaticMarkup(<ReferenceWorkoutPreview db={db} activeSession={session}/>),"text/html");
  const first=home.querySelector('[data-testid="home-top-hero"] img');
  const second=preview.querySelector(".a6-session-artwork");
  expect(first.getAttribute("src")).toBe(second.getAttribute("src"));
  expect(first.dataset.trainingCategory).toBe(category);
  expect(first.dataset.trainingProfile).toBe(sex);
  visualFrames.push({name:sex+"-"+category,home:home.body.innerHTML,preview:preview.body.innerHTML});
});

test("completed home artwork stays with the completed session instead of the next active day",()=>{
  const db={profile:{sex:"female"},program:{active_day:2,sessions:[
    {day:1,label:"Push 1",focus:["Peito"],exercises:[{exercise_id:"press",sets:1}]},
    {day:2,label:"Pull 1",focus:["Costas"],exercises:[]}
  ]},recent_sets:[{session_day:1,exercise_id:"press",set_number:1,created_at:new Date().toISOString()}]};
  const doc=new DOMParser().parseFromString(renderToStaticMarkup(<ReferenceHome db={db} start={()=>{}}/>),"text/html");
  expect(doc.querySelector("[data-training-category]").dataset.trainingCategory).toBe("push");
  expect(doc.querySelector('[data-testid="start-workout-button"]').disabled).toBe(true);
  expect(doc.body.textContent).toContain("TREINO CONCLUÍDO HOJE");
});

test("failed images progress through fallbacks, stop safely, and reset when the session changes",()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const container=document.createElement("div");
  const root=createRoot(container);
  try {
    act(()=>root.render(<TrainingCardImage session="Push 1" profile="male"/>));
    expect(container.querySelector("img").getAttribute("src")).toContain("/male/push.webp");
    act(()=>container.querySelector("img").dispatchEvent(new Event("error")));
    expect(container.querySelector("img").getAttribute("src")).toContain("/neutral/push.webp");
    act(()=>container.querySelector("img").dispatchEvent(new Event("error")));
    expect(container.querySelector("img").getAttribute("src")).toContain("/neutral/default.webp");
    act(()=>container.querySelector("img").dispatchEvent(new Event("error")));
    expect(container.querySelector("img")).toBeNull();
    act(()=>root.render(<TrainingCardImage session="Pull 1" profile="female"/>));
    expect(container.querySelector("img").getAttribute("src")).toContain("/female/pull.webp");
  } finally {
    act(()=>root.unmount());
    delete global.IS_REACT_ACT_ENVIRONMENT;
  }
});

afterAll(()=>{
  if (!process.env.FORGE_ARTWORK_VISUAL) return;
  const root=path.join(__dirname,"..");
  const entry=fs.readFileSync(path.join(root,"index.js"),"utf8");
  const indexCss=Array.from(entry.matchAll(/import "@\/([^"]+\.css)";/g),match=>match[1]);
  const cssFiles=["App.css","home-signature.css","features/training-card-artwork.css",...indexCss];
  const css=cssFiles.filter(file=>fs.existsSync(path.join(root,file))).map(file=>fs.readFileSync(path.join(root,file),"utf8")).join("\n");
  const output=path.join(root,"../training-card-visual");
  fs.mkdirSync(output,{recursive:true});
  for (const frame of visualFrames) {
    for (const mode of ["home","preview"]) {
      const markup=frame[mode].replace(/\/training-cards\/(male|female|neutral)\/([a-z-]+)\.webp/g,(_,profile,category)=>{
        return "data:image/webp;base64,"+fs.readFileSync(path.join(root,"assets/training-cards",profile,category+".webp")).toString("base64");
      }).replace(/src="test-file-stub"/g, 'src="data:image/png;base64,'+fs.readFileSync(path.join(root,"assets/logotipo_forge_em_metal_forjado.png")).toString("base64")+'"');
      fs.writeFileSync(path.join(output,frame.name+"-"+mode+".html"),'<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}'+css+'</style><div class="forge-shell"><main class="main">'+markup+'</main></div>');
    }
  }
});
