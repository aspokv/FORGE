import {artworkSlotFor} from "./ReferenceWorkoutPreview";

describe("exercise artwork mapping",()=>{
  test.each([
    ["Remada apoiada no peito",0],
    ["Puxada unilateral na polia",1],
    ["Remada curvada com barra",2],
    ["Pullover com halter",3],
    ["Crucifixo inverso com halteres",4],
    ["Rosca direta com barra",5],
  ])("maps %s to its approved artwork",(name,slot)=>expect(artworkSlotFor(name)).toBe(slot));
  test("does not lie with a random exercise image",()=>expect(artworkSlotFor("Agachamento livre")).toBe(-1));
});
