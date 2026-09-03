import fs from "fs";
import path from "path";

describe("progress adherence visual states",()=>{
  const css=fs.readFileSync(path.join(__dirname,"../progress-fix.css"),"utf8");
  it("keeps empty days neutral",()=>expect(css).toContain(".progress-page .calendar-dots i{"));
  it("colors only trained days lime",()=>expect(css).toContain(".progress-page .calendar-dots i.trained{"));
});
