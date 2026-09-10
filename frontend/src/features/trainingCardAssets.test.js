import fs from "fs";
import path from "path";

test("all 33 training card images are non-empty WebP assets within the size budget", () => {
  const base=path.join(__dirname,"../assets/training-cards");
  for (const profile of ["male","female","neutral"]) {
    for (const category of ["push","pull","legs-quads","legs-posterior","upper","fullbody","chest","back","shoulders","arms","default"]) {
      const data=fs.readFileSync(path.join(base,profile,category+".webp"));
      expect(data.toString("ascii",0,4)).toBe("RIFF");
      expect(data.toString("ascii",8,12)).toBe("WEBP");
      expect(data.length).toBeGreaterThan(1000);
      expect(data.length).toBeLessThan(180000);
    }
  }
});
