import fs from "fs";
import path from "path";

describe("progress visual states",()=>{
  const progressCss=fs.readFileSync(path.join(__dirname,"../progress-fix.css"),"utf8");
  const layoutCss=fs.readFileSync(path.join(__dirname,"product-layout.css"),"utf8");

  it("keeps empty days neutral",()=>expect(progressCss).toContain(".progress-page .calendar-dots i{"));
  it("colors only trained days lime",()=>expect(progressCss).toContain(".progress-page .calendar-dots i.trained{"));
  it("removes the ambiguous consolidated-marks hero from the visible progress UI",()=>{
    expect(layoutCss).toContain(".progress-page>.progress-hero{display:none!important}");
  });
  it("promotes best results as the premium primary card",()=>{
    expect(layoutCss).toContain(".progress-page>.progress-results{");
    expect(layoutCss).toContain("border-color:rgba(201,162,126,.30)");
  });
});