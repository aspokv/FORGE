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
});
