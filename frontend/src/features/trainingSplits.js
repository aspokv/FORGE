export const SPLIT_LABELS = {
  auto: "FORGE recomenda",
  full_body: "Full Body",
  upper_lower: "Upper / Lower",
  ppl: "Push / Pull / Legs",
  ul_ppl: "Upper / Lower + PPL",
  upper_lower_ppl: "Upper / Lower + PPL",
  abc: "ABC clássico",
  abcd: "ABCD",
  abcde: "ABCDE",
};

export function splitOptions(days, experience = "Intermediário") {
  const d = Math.max(1, Math.min(7, Number(days) || 3));
  const advanced = ["avançado", "avancado", "bodybuilder"].includes(
    String(experience).toLowerCase()
  );
  let ids;
  if (d === 1) ids = ["full_body"];
  else if (d === 2) ids = ["full_body", "upper_lower"];
  else if (d === 3) ids = advanced
    ? ["ppl", "full_body", "abc"]
    : ["full_body", "ppl", "abc"];
  else if (d === 4) ids = ["upper_lower", "abcd"];
  else if (d === 5) ids = advanced
    ? ["ul_ppl", "abcde", "upper_lower_ppl"]
    : ["upper_lower_ppl", "ul_ppl", "abcde"];
  else ids = ["ppl", "abc"];
  return ids.map((id, index) => ({id, label: SPLIT_LABELS[id], recommended: index === 0}));
}

export function validSplitPreference(days, experience, preference) {
  return splitOptions(days, experience).some(x => x.id === preference) ? preference : "";
}

export const TRAINING_METHODS = [
  {id: "balanced_hypertrophy", label: "FORGE Performance", description: "Equilíbrio entre volume, esforço e recuperação."},
  {id: "high_intensity", label: "Alta intensidade controlada", description: "Menos volume e séries mais próximas da falha."},
  {id: "progressive_volume", label: "Volume progressivo", description: "Volume maior, construído gradualmente conforme a resposta."},
  {id: "specialization", label: "Especialização", description: "Mais recursos para até três regiões prioritárias."},
];
