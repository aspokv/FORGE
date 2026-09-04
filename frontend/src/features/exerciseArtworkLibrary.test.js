import fs from "fs";
import path from "path";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";
import {EXERCISE_ARTWORK_TILE_COUNT,artworkSlotForExercise} from "./exerciseArtworkLibrary";

const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,"../../../backend/exercises.json"),"utf8"));
const spritePath=path.join(__dirname,"../../public/images/reference/exercise-premium-sprite.webp");

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

  it("ships a valid 84-frame vertical WebP sprite",()=>{
    const sprite=fs.readFileSync(spritePath);
    expect(sprite.subarray(0,4).toString()).toBe("RIFF");
    expect(sprite.subarray(8,12).toString()).toBe("WEBP");
    expect(sprite.subarray(12,16).toString()).toBe("VP8 ");
    expect(Array.from(sprite.subarray(23,26))).toEqual([0x9d,0x01,0x2a]);
    const width=sprite.readUInt16LE(26)&0x3fff;
    const height=sprite.readUInt16LE(28)&0x3fff;
    expect(width).toBe(192);
    expect(height).toBe(192*EXERCISE_ARTWORK_TILE_COUNT);
    expect(sprite.readUInt32LE(4)+8).toBe(sprite.length);
    expect(sprite.length).toBeLessThan(512000);
  });

  it("renders catalog exercises with actual sprite image elements",()=>{
    const sample=catalog.slice(0,Math.min(catalog.length,40));
    const items=sample.map(ex=>({exercise_id:ex.id,sets:3,reps:"8–12",rir:2}));
    const html=renderToStaticMarkup(<ReferenceWorkoutPreview db={{exercises:catalog,program:{}}} activeSession={{label:"Treino completo",duration:"60 min",focus:["Força","Hipertrofia"]}} items={items} onStart={()=>{}} onLibrary={()=>{}}/>);
    const doc=new DOMParser().parseFromString(html,"text/html");
    expect(doc.querySelectorAll(".ref3-ex-art.fallback")).toHaveLength(0);
    const images=doc.querySelectorAll(".ref3-ex-art > img");
    expect(images).toHaveLength(sample.length);
    images.forEach(img=>expect(img.getAttribute("src")).toContain("exercise-premium-sprite.webp?v=20260904d"));
  });

  it("uses vertical frame offsets for each exercise slot",()=>{
    const target=catalog.find(ex=>ex.id==="hack-squat")||catalog[0];
    const slot=artworkSlotForExercise(target);
    const html=renderToStaticMarkup(<ReferenceWorkoutPreview db={{exercises:catalog,program:{}}} activeSession={{label:"Legs"}} items={[{exercise_id:target.id,sets:3,reps:"8–12",rir:2}]} onStart={()=>{}} onLibrary={()=>{}}/>);
    const doc=new DOMParser().parseFromString(html,"text/html");
    const img=doc.querySelector(".ref3-ex-art > img");
    expect(img.getAttribute("style")).toContain(`--art-y:${slot*-82}px`);
    expect(img.getAttribute("style")).toContain(`--art-y-small:${slot*-72}px`);
  });

  it("does not crash on partial runtime payloads",()=>{
    expect(()=>renderToStaticMarkup(<ReferenceWorkoutPreview db={{program:{focus:"Costas"}}} activeSession={{label:"Pull 2",focus:"Costas"}} items={[{exercise_id:"custom-row",name:"Remada custom",equipment:"cable",sets:3,reps:"10",rir:2}]} onStart={()=>{}} onLibrary={()=>{}}/>)).not.toThrow();
    expect(()=>renderToStaticMarkup(<ReferenceWorkoutPreview db={{}} items={undefined} onStart={()=>{}} onLibrary={()=>{}}/>)).not.toThrow();
  });
});
