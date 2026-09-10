import assets from "../assets/training-cards/manifest";

export const TRAINING_CATEGORIES = ["push", "pull", "legs-quads", "legs-posterior", "upper", "fullbody", "chest", "back", "shoulders", "arms", "default"];
const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
const normalize = value => list(value).filter(v => typeof v === "string").join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[_/+-]/g, " ").replace(/\s+/g, " ").trim();

function profileValue(value) {
  const key = normalize(value);
  if (["male", "masculino", "masculina", "m", "homem"].includes(key)) return "male";
  if (["female", "feminino", "feminina", "f", "mulher"].includes(key)) return "female";
  if (["neutral", "neutro", "unisex", "unissex", "all", "todos", "nao binario", "non binary"].includes(key)) return "neutral";
  return null;
}

// Explicit program audience takes precedence over the user's profile.
export function trainingProfileFor(program = {}, profile = {}) {
  for (const source of [program, profile]) {
    if (typeof source === "string") {
      const result = profileValue(source);
      if (result) return result;
      continue;
    }
    for (const value of [source?.audience_type, source?.audience, source?.sex, source?.gender, source?.profile, source?.assessment?.sex, source?.assessment?.gender]) {
      const result = profileValue(value);
      if (result) return result;
    }
  }
  return "neutral";
}

function classify(value) {
  const key = normalize(value);
  if (!key) return null;
  const full = /\bfull\s*body\b|\bcorpo (todo|inteiro)\b/.test(key);
  const upper = /\bupper\b|\bsuperiores\b|\btronco\b/.test(key);
  const lower = /\blegs?\b|\blower\b|\bpernas?\b|\binferiores\b/.test(key);
  const quads = /\bquad(?:s|riceps)?\b|\banterior(?:es)?\b/.test(key);
  const posterior = /\bposterior(?:es)?\b|\bhamstrings?\b|\bglute\w*|\bhinge\b/.test(key);
  const push = /\bpush\b/.test(key), pull = /\bpull\b/.test(key);
  const chest = /\bpeito\b|\bpeitoral\b|\bpeitorais\b|\bchest\b/.test(key);
  const back = /\bcostas\b|\bdorsal\b|\bdorsais\b|\bback\b|\blargura\b|\bespessura\b/.test(key);
  const shoulders = /\bombros?\b|\bdeltoides?\b|\bshoulders?\b/.test(key);
  const biceps = /\bbiceps\b/.test(key), triceps = /\btriceps\b/.test(key);
  if (full || (upper && lower) || ((lower || quads) && (chest || back))) return "fullbody";
  if (upper || (push && pull) || (chest && back)) return "upper";
  if (push) return "push";
  if (pull) return "pull";
  // Posterior deltoid is an upper-body session, not a leg session.
  if (shoulders && !chest && !back && !lower && !quads && !/\bglute\w*|\bhamstrings?\b/.test(key)) return "shoulders";
  if (lower || quads || posterior) {
    if (posterior && quads) {
      return key.search(/\bposterior|\bhamstring|\bglute|\bhinge/) < key.search(/\bquad|\banterior/) ? "legs-posterior" : "legs-quads";
    }
    return posterior ? "legs-posterior" : "legs-quads";
  }
  if (chest && (triceps || shoulders)) return "push";
  if (back && biceps) return "pull";
  if (chest) return "chest";
  if (back) return "back";
  if (shoulders) return "shoulders";
  if (biceps || triceps || /\bbracos?\b|\barms?\b/.test(key)) return "arms";
  return null;
}

export function trainingCategoryFor(session = {}, focus = []) {
  if (typeof session === "string") return classify(session) || classify(focus) || "default";
  // Session label is more specific than broad category "legs"/"upper".
  const label = session?.label || session?.name || session?.session;
  const kind = classify(label);
  const detail = classify(session?.focus || focus);
  if (kind === "legs-quads" && !/quad|anterior/.test(normalize(label)) && detail === "legs-posterior") return detail;
  return kind
    || classify(session?.category)
    || classify(session?.focus || focus)
    || "default";
}

export function resolveTrainingArtwork({session = {}, program = {}, profile = {}, focus = []} = {}, catalog = assets) {
  const category = trainingCategoryFor(session, focus);
  const audience = trainingProfileFor(program, profile);
  const candidates = [
    {src: catalog[audience]?.[category], profile: audience, category},
    {src: catalog.neutral?.[category], profile: "neutral", category},
    {src: catalog.neutral?.default, profile: "neutral", category: "default"},
  ].filter((item, index, items) => item.src && items.findIndex(other => other.src === item.src) === index);
  return {category, profile: audience, candidates, src: candidates[0]?.src || ""};
}

export function trainingArtworkAlt({profile, category}) {
  const subject = profile === "male" ? "Atleta homem" : profile === "female" ? "Atleta mulher" : "Homem e mulher atletas";
  const labels = {push:"push", pull:"pull", "legs-quads":"quadríceps", "legs-posterior":"posterior de pernas", upper:"superiores", fullbody:"corpo inteiro", chest:"peito", back:"costas", shoulders:"ombros", arms:"braços", default:"treino"};
  return subject + " em ambiente FORGE · " + labels[category];
}
