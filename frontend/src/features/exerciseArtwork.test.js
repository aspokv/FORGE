import {reviewedArtworkForExercise} from "./reviewedExerciseArtwork";

describe("exercise artwork mapping",()=>{
  test.each([
    ["Remada apoiada no peito","row"],
    ["Puxada unilateral na polia","lat-pulldown"],
    ["Remada curvada com barra","bb-row"],
    ["Pullover com halter","db-pullover"],
    ["Crucifixo inverso com halteres","db-rear-fly"],
    ["Rosca direta com barra","bb-curl"],
  ])("maps %s to its catalog photo",(name,id)=>expect(reviewedArtworkForExercise({name})).toBe(`/images/exercises/${id}-v1.webp`));
  test("does not invent an association",()=>expect(reviewedArtworkForExercise({name:"Exercício desconhecido"})).toBeNull());
});
