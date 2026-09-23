import {reviewedArtworkForExercise} from "./reviewedExerciseArtwork";

describe("exercise artwork mapping",()=>{
  test.each([
    ["Remada apoiada no peito","row"],
    ["Puxada unilateral na polia","lat-pulldown"],
    ["Remada curvada com barra","bb-row"],
    ["Pullover com halter","db-pullover"],
    ["Crucifixo inverso com halteres","db-rear-fly"],
    ["Rosca direta com barra","bb-curl"],
  // A versao vem do proprio catalogo: travar `-v1` aqui fazia toda nova leva de arte
  // quebrar um teste que nao tem nada a ver com o apelido que ele verifica.
  ])("maps %s to its catalog photo",(name,id)=>expect(reviewedArtworkForExercise({name})).toBe(reviewedArtworkForExercise({id})));
  test("does not invent an association",()=>expect(reviewedArtworkForExercise({name:"Exercício desconhecido"})).toBeNull());
});
