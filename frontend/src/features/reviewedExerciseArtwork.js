import catalog from "./exercisePhotoCatalog.json";

// One exact identity -> photo mapping for every catalog exercise and plan.
export const REVIEWED_EXERCISE_ARTWORK=Object.freeze(Object.fromEntries(
  catalog.map(({id,src})=>[id,src]),
));
const normalize=value=>String(value||"").normalize("NFD")
  .replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
const aliases=new Map(catalog.map(({name,id})=>[normalize(name),id]));
for(const [name,id] of [
  ["Stiff com barra","rdl"],
  ["Levantamento terra romeno com barra","rdl"],
  ["Mesa flexora","lying-leg-curl"],
  ["Hip thrust com barra","hip-thrust"],
  ["Panturrilha sentada","seated-calf"],
]) aliases.set(normalize(name),id);

export function reviewedArtworkForExercise(exercise={}){
  const id=exercise?.id||exercise?.exercise_id;
  const key=id||aliases.get(normalize(exercise?.name));
  return Object.prototype.hasOwnProperty.call(REVIEWED_EXERCISE_ARTWORK,key)
    ?REVIEWED_EXERCISE_ARTWORK[key]:null;
}
