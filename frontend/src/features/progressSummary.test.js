import {buildProgressSummary} from "./progressSummary";

describe("progress summary",()=>{
  it("uses clear exercise wording instead of consolidated marks",()=>{
    const summary=buildProgressSummary({resultCount:5});
    expect(summary.eyebrow).toBe("VISÃO GERAL");
    expect(summary.value).toBe("5 exercícios acompanhados");
    expect(`${summary.value} ${summary.copy}`).not.toContain("marcas consolidadas");
  });

  it("keeps a clear four-week load comparison when trend data exists",()=>{
    const summary=buildProgressSummary({trendChange:7.25,resultCount:5});
    expect(summary.value).toBe("+7,3% na carga média");
    expect(summary.copy).toContain("últimas quatro semanas");
  });

  it("uses a universal empty state",()=>{
    const summary=buildProgressSummary({});
    expect(summary.value).toBe("Seu progresso começa aqui");
  });
});
