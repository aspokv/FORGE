import fs from "fs";
import path from "path";
import React, {act} from "react";
import {createRoot} from "react-dom/client";
import {renderToStaticMarkup} from "react-dom/server";
import ReferenceWorkoutPreview from "./ReferenceWorkoutPreview";
import ExercisePhoto from "./ExercisePhoto";
import photos from "./exercisePhotoCatalog.json";
import {REVIEWED_EXERCISE_ARTWORK,reviewedArtworkForExercise} from "./reviewedExerciseArtwork";

const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,"../../../backend/exercises.json"),"utf8"));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const render=element=>new DOMParser().parseFromString(renderToStaticMarkup(element),"text/html");

describe("complete exercise photograph coverage",()=>{
  it("updates the photo after substitution and recovers from a failed previous image",async()=>{
    const host=document.createElement('div');
    document.body.appendChild(host);
    const root=createRoot(host);
    try{
      await act(async()=>root.render(<ExercisePhoto exercise={{id:'rdl'}}/>));
      await act(async()=>host.querySelector('img').dispatchEvent(new Event('error')));
      expect(host.querySelector('img')).toBeNull();
      expect(host.querySelector('.fallback')).not.toBeNull();
      await act(async()=>root.render(<ExercisePhoto exercise={{id:'db-rdl'}}/>));
      expect(host.querySelector('img').getAttribute('src')).toBe('/images/exercises/db-rdl-v1.webp');
      expect(host.querySelector('.fallback')).toBeNull();
    }finally{
      await act(async()=>root.unmount());
      host.remove();
    }
  });
  it("covers exactly the entire backend catalog",()=>{
    expect(photos.map(x=>x.id).sort()).toEqual(catalog.map(x=>x.id).sort());
    expect(new Set(photos.map(x=>x.id)).size).toBe(photos.length);
  });

  it.each(catalog)("ships a complete high resolution photo for $id",ex=>{
    const src=reviewedArtworkForExercise(ex);
    expect(src).toMatch(/^\/images\/exercises\/[a-z0-9-]+-v1\.webp$/);
    const bytes=fs.readFileSync(path.join(__dirname,"../../public",src));
    expect(bytes.subarray(0,4).toString()).toBe("RIFF");
    expect(bytes.subarray(8,12).toString()).toBe("WEBP");
    expect(bytes.subarray(12,16).toString()).toBe("VP8 ");
    expect(bytes.readUInt32LE(4)+8).toBe(bytes.length);
    expect(bytes.readUInt16LE(26)&0x3fff).toBe(512);
    expect(bytes.readUInt16LE(28)&0x3fff).toBe(512);
    expect(bytes.length).toBeLessThan(160000);
  });

  it("renders all exercises with full photos and no legacy atlas",()=>{
    const doc=render(<ReferenceWorkoutPreview db={{exercises:catalog}} items={catalog.map(ex=>({exercise_id:ex.id,sets:3,reps:"8–12"}))}/>);
    expect(doc.querySelectorAll(".ref3-ex-art.fallback")).toHaveLength(0);
    const images=[...doc.querySelectorAll(".ref3-ex-art > img")];
    expect(images).toHaveLength(catalog.length);
    images.forEach((img,i)=>{
      expect(img.getAttribute("src")).toBe(reviewedArtworkForExercise(catalog[i]));
      expect(img.classList.contains("ref3-reviewed-art")).toBe(true);
      expect(img.hasAttribute("style")).toBe(false);
      expect(img.getAttribute("loading")).toBe("lazy");
    });
  });

  it.each([
    ["lying-leg-curl","leg-curl"],
    ["rdl","db-rdl"],
    ["hip-thrust","smith-hip-thrust"],
    ["abductor-machine","adductor-machine"],
    ["seated-calf","standing-calf"],
    ["standing-calf","leg-press-calf"],
    ["bb-bench-press","db-bench-press"],
    ["db-incline-press","db-bench-press"],
    ["cable-face-pull","db-rear-fly"],
    ["pullup","neutral-pullup"],
  ])("keeps %s visually distinct from %s",(a,b)=>{
    expect(reviewedArtworkForExercise({id:a})).not.toBe(reviewedArtworkForExercise({id:b}));
  });

  it("resolves full names without fuzzy substring or muscle matching",()=>{
    for(const ex of catalog){
      expect(reviewedArtworkForExercise({name:ex.name.toUpperCase()})).toBe(reviewedArtworkForExercise(ex));
    }
    expect(reviewedArtworkForExercise({id:"standing-calf",name:"Panturrilha sentado"})).toBe(REVIEWED_EXERCISE_ARTWORK["standing-calf"]);
    expect(reviewedArtworkForExercise({name:"FLEXAO DE JOELHO DEITADO"})).toBe(REVIEWED_EXERCISE_ARTWORK["lying-leg-curl"]);
    expect(reviewedArtworkForExercise({id:"unknown",name:"Hip thrust barra"})).toBeNull();
    expect(reviewedArtworkForExercise({name:"Unknown exercise",primary_muscle:"biceps"})).toBeNull();
  });

  it("keeps unknown exercises honest and incomplete payloads safe",()=>{
    const unknown=render(<ExercisePhoto exercise={{id:"external",name:"Movimento externo"}}/>);
    expect(unknown.querySelectorAll("img")).toHaveLength(0);
    expect(unknown.querySelector(".fallback")).not.toBeNull();
    expect(()=>render(<ReferenceWorkoutPreview db={{program:{focus:"Costas"}}} activeSession={{label:"Pull",focus:"Costas"}} items={[{exercise_id:"custom",name:"Custom",equipment:"cable"}]}/>)).not.toThrow();
    expect(()=>render(<ReferenceWorkoutPreview db={{}} items={undefined}/>)).not.toThrow();
  });
});
