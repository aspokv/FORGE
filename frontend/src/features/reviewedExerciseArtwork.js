// Individually reviewed replacements. Exact identities prevent similar movements
// (seated/standing, barbell/Smith, prone/seated curl) sharing an incorrect image.
export const REVIEWED_EXERCISE_ARTWORK=Object.freeze({
  rdl:"/images/exercises/rdl-v1.webp",
  "lying-leg-curl":"/images/exercises/lying-leg-curl-v1.webp",
  "hip-thrust":"/images/exercises/hip-thrust-v1.webp",
  "db-step-up":"/images/exercises/db-step-up-v1.webp",
  "abductor-machine":"/images/exercises/abductor-machine-v1.webp",
  "seated-calf":"/images/exercises/seated-calf-v1.webp",
});

const normalize=value=>String(value||"").normalize("NFD")
  .replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const aliases=new Map([
  ["Stiff / RDL com barra","rdl"],
  ["Stiff com barra","rdl"],
  ["Levantamento terra romeno com barra","rdl"],
  ["Flexão de joelho deitado","lying-leg-curl"],
  ["Mesa flexora","lying-leg-curl"],
  ["Hip thrust barra","hip-thrust"],
  ["Hip thrust com barra","hip-thrust"],
  ["Step up com halteres","db-step-up"],
  ["Cadeira abdutora","abductor-machine"],
  ["Panturrilha sentado","seated-calf"],
  ["Panturrilha sentada","seated-calf"],
].map(([name,id])=>[normalize(name),id]));

export function reviewedArtworkForExercise(exercise={}){
  const id=exercise.id||exercise.exercise_id;
  // An explicit ID is authoritative. Never let an ambiguous name override it.
  const key=id||aliases.get(normalize(exercise.name));
  return Object.prototype.hasOwnProperty.call(REVIEWED_EXERCISE_ARTWORK,key)
    ?REVIEWED_EXERCISE_ARTWORK[key]:null;
}
