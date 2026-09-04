import fs from "fs";
import path from "path";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";
import {EXERCISE_ARTWORK_TILE_COUNT,artworkSlotForExercise} from "./exerciseArtworkLibrary";

const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,"../../../backend/exercises.json"),"utf8"));

describe("premium exercise artwork library",()=>{
  it("covers every exercise in the FORGE catalog",()=>{
    const uncovered=catalog.filter(ex=>artworkSlotForExercise(ex)<0);
    expect(uncovered.map(ex=>`${ex.id}: ${ex.name}`)).toEqual([]);
  });

  it("always resolves to a valid premium atlas tile",()=>{
    catalog.forEach(ex=>{
      const slot=artworkSlotForExercise(ex);
      expect(slot).toBeGreaterThanOrEqual(0);
      expect(slot).toBeLessThan(EXERCISE_ARTWORK_TILE_COUNT);
    });
  });

  it("renders catalog exercises without generic dumbbell fallback",()=>{
    const sample=catalog.slice(0,Math.min(catalog.length,40));
    const items=sample.map(ex=>({exercise_id:ex.id,sets:3,reps:"8–12",rir:2}));
    const html=renderToStaticMarkup(<ReferenceWorkoutPreview db={{exercises:catalog,program:{}}} activeSession={{label:"Treino completo",duration:"60 min",focus:["Força","Hipertrofia"]}} items={items} onStart={()=>{}} onLibrary={()=>{}}/>);
    const doc=new DOMParser().parseFromString(html,"text/html");
    expect(doc.querySelectorAll(".ref3-ex-art.fallback")).toHaveLength(0);
    expect(doc.querySelectorAll(".ref3-ex-art[data-art-slot]")).toHaveLength(sample.length);
  });

  it("positions every tile on the 12-column premium atlas",()=>{
    const target=catalog.find(ex=>ex.id==="hack-squat")||catalog[0];
    const slot=artworkSlotForExercise(target);
    const html=renderToStaticMarkup(<ReferenceWorkoutPreview db={{exercises:catalog,program:{}}} activeSession={{label:"Legs"}} items={[{exercise_id:target.id,sets:3,reps:"8–12",rir:2}]} onStart={()=>{}} onLibrary={()=>{}}/>);
    const doc=new DOMParser().parseFromString(html,"text/html");
    const art=doc.querySelector(".ref3-ex-art");
    expect(Number(art.getAttribute("data-art-col"))).toBe(slot%12);
    expect(Number(art.getAttribute("data-art-row"))).toBe(Math.floor(slot/12));
    expect(art.getAttribute("style")).toContain(`--art-x:${(slot%12)*-82}px`);
    expect(art.getAttribute("style")).toContain(`--art-y:${Math.floor(slot/12)*-82}px`);
  });

  it("does not crash on partial runtime payloads",()=>{
    expect(()=>renderToStaticMarkup(<ReferenceWorkoutPreview db={{program:{focus:"Costas"}}} activeSession={{label:"Pull 2",focus:"Costas"}} items={[{exercise_id:"custom-row",name:"Remada custom",equipment:"cable",sets:3,reps:"10",rir:2}]} onStart={()=>{}} onLibrary={()=>{}}/>)).not.toThrow();
    expect(()=>renderToStaticMarkup(<ReferenceWorkoutPreview db={{}} items={undefined} onStart={()=>{}} onLibrary={()=>{}}/>)).not.toThrow();
  });
});
