import {isPullPlan,planArtworkFor} from "./ReferenceHome";

describe("home plan artwork",()=>{
  it("identifies Pull sessions",()=>expect(isPullPlan("Pull 2",["Dorsais / largura","Costas / espessura"])).toBe(true));
  it("identifies Pull by back focus",()=>expect(isPullPlan("Treino B",["Costas / espessura"])).toBe(true));
  it("does not classify Push as Pull",()=>expect(isPullPlan("Push 2",["Peitoral","Tríceps"])).toBe(false));
  it("keeps the default artwork for non-Pull sessions",()=>expect(planArtworkFor("Push 2",["Peitoral","Tríceps"])).toBe("/images/reference/exercise-1.jpg"));
});
