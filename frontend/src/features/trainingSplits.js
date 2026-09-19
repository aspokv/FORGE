/**
 * As divisões que a tela oferece.
 *
 * Esta lista é uma CÓPIA de `engine.compatible_splits` e `engine.SPLIT_LABELS`, e isso é
 * um risco conhecido: duas listas no mesmo produto divergem no dia em que alguém mexe só
 * numa. O backend recusa com 422 uma preferência fora da lista dele, então divergir aqui
 * não produz programa errado — produz uma opção que o atleta escolhe e que volta erro.
 *
 * `trainingSplits.test.js` compara as duas, lendo o Python. É o que transforma a
 * divergência em teste vermelho no CI em vez de num relato de suporte.
 *
 * A ordem também é contrato: a primeira é a recomendada, e é ela que `determine_split`
 * usa para quem não tem preferência gravada. As híbridas ficam DEPOIS das clássicas de
 * propósito — pondo-as antes, todo atleta de seis dias abriria o aplicativo no dia
 * seguinte com outro programa, no meio do ciclo, sem ter pedido.
 */
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
  hybrid_01: "Híbrido · Full / Upper / Lower rotacional",
  hybrid_02: "Híbrido · Peito + Quadríceps / Costas + Posterior",
  hybrid_03: "Híbrido · Upper / Lower com microdoses",
  hybrid_04: "Híbrido · 7x Full / Upper / Lower",
  hybrid_05: "Híbrido · High Frequency Wave",
};

/** As híbridas de seis e de sete dias, na mesma ordem do backend. */
export const HYBRID_SIX = ["hybrid_01", "hybrid_02", "hybrid_03"];
export const HYBRID_SEVEN = ["hybrid_04", "hybrid_05"];

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
  else if (d === 6) ids = ["ppl", "abc", ...HYBRID_SIX];
  else ids = ["ppl", "abc", ...HYBRID_SEVEN, ...HYBRID_SIX];
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
