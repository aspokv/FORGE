import {splitOptions, validSplitPreference, TRAINING_METHODS} from "./trainingSplits";

describe("divisões compatíveis", () => {
  it("não oferece ABCDE para quem treina três dias", () => {
    expect(splitOptions(3, "Avançado").map(x => x.id)).not.toContain("abcde");
  });

  it("oferece ABCDE e combinação UL/PPL em cinco dias", () => {
    const ids = splitOptions(5, "Bodybuilder").map(x => x.id);
    expect(ids).toContain("abcde");
    expect(ids).toContain("ul_ppl");
  });

  it("descarta uma preferência incompatível", () => {
    expect(validSplitPreference(4, "Intermediário", "abcde")).toBe("");
    expect(validSplitPreference(4, "Intermediário", "upper_lower")).toBe("upper_lower");
  });

  it("expõe os quatro métodos FORGE sem nomes de terceiros", () => {
    expect(TRAINING_METHODS.map(x => x.id)).toEqual([
      "balanced_hypertrophy", "high_intensity", "progressive_volume", "specialization",
    ]);
  });
});
