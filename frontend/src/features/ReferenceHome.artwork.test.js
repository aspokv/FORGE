import {planArtworkFor} from "./ReferenceHome";

describe("home plan artwork",()=>{
  it("uses Pull artwork for Pull sessions",()=>expect(planArtworkFor("Pull 2",["Dorsais / largura","Costas / espessura"])).toBe("/images/reference/plan-pull.webp"));
  it("uses Pull artwork when back focus identifies the session",()=>expect(planArtworkFor("Treino B",["Dorsais"])).toBe("/images/reference/plan-pull.webp"));
  it("keeps the default artwork for non-Pull sessions",()=>expect(planArtworkFor("Push 2",["Peitoral","Tríceps"])).toBe("/images/reference/exercise-1.jpg"));
});
