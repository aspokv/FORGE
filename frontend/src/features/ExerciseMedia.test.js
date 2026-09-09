import fs from "fs";
import path from "path";
import React,{act} from "react";
import {createRoot} from "react-dom/client";
import {renderToStaticMarkup} from "react-dom/server";
import {
  EXERCISE_MEDIA_MAP,
  EXTERNAL_EXERCISE_MEDIA_ENABLED,
  exerciseMediaFor,
} from "../data/exerciseMediaMap";
import ExerciseMedia from "./ExerciseMedia";

const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,"../../../backend/exercises.json"),"utf8"));
const click=node=>node.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true}));
globalThis.IS_REACT_ACT_ENVIRONMENT=true;

describe("ExerciseMedia",()=>{
  let host;
  let root;

  beforeEach(()=>{
    host=document.createElement("div");
    document.body.appendChild(host);
    root=createRoot(host);
  });

  afterEach(async()=>{
    await act(async()=>root.unmount());
    host.remove();
  });

  it("maps the complete FORGE catalog with stable FORGE IDs",()=>{
    expect(Object.keys(EXERCISE_MEDIA_MAP).sort()).toEqual(catalog.map(exercise=>exercise.id).sort());
    expect(Object.values(EXERCISE_MEDIA_MAP).filter(entry=>entry.match==="exact")).toHaveLength(106);
    expect(Object.values(EXERCISE_MEDIA_MAP).filter(entry=>entry.match==="equivalent")).toHaveLength(13);
    expect(Object.values(EXERCISE_MEDIA_MAP).filter(entry=>entry.match==="unmatched")).toHaveLength(15);
    expect(exerciseMediaFor({id:"bb-bench-press",name:"Unknown"}).datasetId).toBe("0025");
    expect(exerciseMediaFor({id:"bb-bench-press",exercise_id:"db-bench-press"}).datasetId).toBe("0289");
    expect(exerciseMediaFor({name:"Supino reto com barra"})).toBeNull();
  });

  it("keeps external media disabled in production until FORGE has a license",()=>{
    expect(EXTERNAL_EXERCISE_MEDIA_ENABLED).toBe(false);
    const markup=renderToStaticMarkup(<ExerciseMedia exercise={{id:"bb-bench-press",name:"Supino reto"}}/>);
    expect(markup).toContain("/images/exercises/bb-bench-press-v1.webp");
    expect(markup).not.toContain("Gym visual");
    expect(markup).not.toContain(".gif");
  });

  it("uses the mapped exact thumbnail when the licensed source is explicitly enabled",async()=>{
    await act(async()=>root.render(
      <ExerciseMedia
        exercise={{id:"bb-bench-press",name:"Supino reto"}}
        externalMediaEnabled
        mediaBaseUrl="https://media.example.test"
      />,
    ));
    expect(host.querySelector("img").getAttribute("src")).toBe("https://media.example.test/images/0025-EIeI8Vf.jpg");
    expect(host.querySelector("[data-media-source='gymvisual-dataset']")).not.toBeNull();
  });

  it("does not load a GIF before interaction, loads it on demand, and removes it on close",async()=>{
    await act(async()=>root.render(
      <ExerciseMedia
        exercise={{id:"bb-bench-press",name:"Supino reto"}}
        externalMediaEnabled
        mediaBaseUrl="https://media.example.test/"
      />,
    ));
    expect(document.querySelector('img[src$=".gif"]')).toBeNull();

    await act(async()=>click(host.querySelector(".exercise-media-trigger")));
    expect(document.querySelector('[role="dialog"] img').getAttribute("src")).toBe("https://media.example.test/videos/0025-EIeI8Vf.gif");
    expect(document.querySelector('[role="dialog"]').textContent).toContain("© Gym visual");

    await act(async()=>click(document.querySelector(".exercise-media-close")));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('img[src$=".gif"]')).toBeNull();
    expect(host.querySelector('img[src$=".jpg"]')).not.toBeNull();
  });

  it("uses the current FORGE asset for unmatched exercises",async()=>{
    await act(async()=>root.render(
      <ExerciseMedia
        exercise={{id:"cable-face-pull",name:"Face pull"}}
        externalMediaEnabled
        mediaBaseUrl="https://media.example.test"
      />,
    ));
    expect(host.querySelector("img").getAttribute("src")).toBe("/images/exercises/cable-face-pull-v1.webp");
    expect(host.querySelector("[data-media-source='forge']")).not.toBeNull();
    expect(host.querySelector(".exercise-media-trigger")).toBeNull();
  });

  it("falls back from failed mapped media to FORGE and never leaves a blank card",async()=>{
    await act(async()=>root.render(
      <ExerciseMedia
        exercise={{id:"bb-bench-press",name:"Supino reto"}}
        externalMediaEnabled
        mediaBaseUrl="https://media.example.test"
      />,
    ));
    await act(async()=>host.querySelector("img").dispatchEvent(new Event("error")));
    expect(host.querySelector("img").getAttribute("src")).toBe("/images/exercises/bb-bench-press-v1.webp");

    await act(async()=>host.querySelector("img").dispatchEvent(new Event("error")));
    expect(host.querySelector("img")).toBeNull();
    expect(host.querySelector("svg")).not.toBeNull();
    expect(host.querySelector(".fallback")).not.toBeNull();
  });

  it("does not activate equivalent matches without explicit human approval",async()=>{
    await act(async()=>root.render(
      <ExerciseMedia
        exercise={{id:"row",name:"Remada apoiada"}}
        externalMediaEnabled
        mediaBaseUrl="https://media.example.test"
      />,
    ));
    expect(host.querySelector("img").getAttribute("src")).toBe("/images/exercises/row-v1.webp");
    expect(host.querySelector(".exercise-media-trigger")).toBeNull();
  });
});
