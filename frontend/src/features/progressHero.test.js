import {buildProgressHero} from "./progressHero";

describe("progress hero",()=>{
  it("shows current body weight when weight history exists",()=>{
    const hero=buildProgressHero({bodyTrend:[{date:"2026-08-01",weight:80},{date:"2026-09-01",weight:82.5}]});
    expect(hero.value).toContain("82,5");
    expect(hero.copy).toContain("+2,5 kg");
  });

  it("does not expose the ambiguous consolidated-marks copy",()=>{
    const hero=buildProgressHero({prs:[{weight:80,value:"80 kg x 8"}]});
    expect(hero.value).toBe("Evolução em construção");
    expect(`${hero.value} ${hero.copy}`).not.toContain("marcas consolidadas");
  });
});
