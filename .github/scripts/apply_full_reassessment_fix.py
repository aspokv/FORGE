from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "frontend/src/App.js"
RESUME = ROOT / "frontend/src/features/onboardingResume.js"
HELPER = ROOT / "frontend/src/features/reassessmentMode.js"
TEST = ROOT / "frontend/src/features/reassessmentMode.test.js"
CSS = ROOT / "frontend/src/features/performance-os.css"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, got {count}")
    return text.replace(old, new, 1)


app = APP.read_text(encoding="utf-8-sig")

app = replace_once(
    app,
    'import {anteriorNaLista,passosPendentes,proximoNaLista,respostasIniciais} from "./features/onboardingResume";',
    'import {anteriorNaLista,proximoNaLista,respostasIniciais} from "./features/onboardingResume";\nimport {ASSESSMENT_MODE_FULL,ASSESSMENT_MODE_RESUME,passosDoAssessment,deveAbrirBuilderDepois,deveMostrarPreview} from "./features/reassessmentMode";',
    "assessment helper import",
)

app = replace_once(
    app,
    'const GROUPS={PEITORAL:["Peitoral superior","Peitoral esternal"],OMBROS:["Deltóide anterior","Deltóide lateral","Deltóide posterior"],COSTAS:["Dorsais / largura","Costas / espessura","Trapézio"],BRAÇOS:["Bíceps","Braquial","Tríceps"],PERNAS:["Quadríceps","Posteriores","Glúteos","Adutores","Panturrilhas"],CORE:["Abdômen","Oblíquos"]};',
    'const GROUPS={PEITORAL:["Peitoral superior","Peitoral esternal"],OMBROS:["Deltóide anterior","Deltóide lateral","Deltóide posterior"],COSTAS:["Dorsais / largura","Costas / espessura","Trapézio"],BRAÇOS:["Bíceps","Braquial","Tríceps"],PERNAS:["Quadríceps","Posteriores","Glúteos","Adutores","Panturrilhas"],CORE:["Abdômen","Oblíquos"]};\nconst AUTOMATION_MODE_COPY={FORGE_AUTO:"O FORGE monta e aplica o programa automaticamente.",FORGE_ASSISTED:"O FORGE monta o programa e você revisa antes de aplicar.",FORGE_PRO:"Salva sua avaliação e abre o Program Builder para você controlar a estrutura."};\nconst AUTOMATION_CONFIRM_COPY={FORGE_AUTO:"Ao concluir, o novo programa será aplicado automaticamente.",FORGE_ASSISTED:"Você verá o programa completo e aprovará antes de ele entrar em vigor.",FORGE_PRO:"Ao concluir, o Program Builder será aberto com seu novo perfil e prioridades."};',
    "automation copy",
)

app = replace_once(
    app,
    '[assessment,setAssessment]=useState(false),[analytics',
    '[assessment,setAssessment]=useState(false),[assessmentMode,setAssessmentMode]=useState(ASSESSMENT_MODE_RESUME),[analytics',
    "assessment mode state",
)

app = replace_once(
    app,
    'if(data.profile?.onboarding_required&&user?.role==="ATHLETE")setAssessment(true)',
    'if(data.profile?.onboarding_required&&user?.role==="ATHLETE"){setAssessmentMode(ASSESSMENT_MODE_RESUME);setAssessment(true)}',
    "bootstrap resume mode",
)

finish_pattern = re.compile(r'const finish=async form=>\{.*?\};const approve=async\(\)=>\{', re.S)
finish_replacement = '''const finish=async form=>{if(deveMostrarPreview(form.automation_mode)){try{const r=await axios.post(`${API}/program/preview`,form);setPreviewData({form,program:r.data.program});setAssessment(false)}catch{setDb(x=>({...x,profile:{...x.profile,...form}}));setAssessment(false);setPreviewData(null)}return}try{const payload={...form,profile_id:user?.id||form.profile_id};const r=await axios.post(`${API}/assessment`,payload);setDb(x=>({...x,profile:r.data.profile,program:r.data.program}))}catch{setDb(x=>({...x,profile:{...x.profile,...form}}))}setAssessment(false);setAssessmentMode(ASSESSMENT_MODE_RESUME);if(deveAbrirBuilderDepois(form.automation_mode))setBuilder(true)};const approve=async()=>{'''
app, n = finish_pattern.subn(finish_replacement, app, count=1)
if n != 1:
    raise RuntimeError(f"finish flow: expected 1 replacement, got {n}")

app = replace_once(
    app,
    '}setPreviewData(null)};if(!db&&!loading)',
    '}setAssessmentMode(ASSESSMENT_MODE_RESUME);setPreviewData(null)};if(!db&&!loading)',
    "assisted approval resets mode",
)

app = replace_once(
    app,
    'passos={passosPendentes(db?.profile)}',
    'passos={passosDoAssessment(db?.profile,assessmentMode)}',
    "assessment step selection",
)

app = replace_once(
    app,
    'redo={()=>setAssessment(true)}',
    'redo={()=>{setAssessmentMode(ASSESSMENT_MODE_FULL);setAssessment(true)}}',
    "full reassessment button",
)

app = replace_once(
    app,
    'const set=(k,v)=>setForm(x=>({...x,[k]:v})),setNested=(k,v)=>setForm(x=>({...x,[k]:{...x[k],[k.includes(".")?k.split(".")[1]:k]:v}}));',
    'const set=(k,v)=>setForm(x=>({...x,[k]:v})),setNested=(k,v)=>{const[root,child]=k.split(".");setForm(x=>({...x,[root]:{...(x[root]||{}),[child]:v}}))};',
    "nested recovery setter",
)

mode_old = '<Choice label="Modo de automação"value={form.automation_mode}options={form.experience==="Bodybuilder"?["FORGE_ASSISTED","FORGE_PRO","FORGE_AUTO"]:["FORGE_AUTO","FORGE_ASSISTED","FORGE_PRO"]}onChange={v=>set("automation_mode",v)}/>'
mode_new = '<div className="choice automation-choice"><p className="eyebrow">Modo de automação</p><div className="automation-mode-grid">{(form.experience==="Bodybuilder"?["FORGE_ASSISTED","FORGE_PRO","FORGE_AUTO"]:["FORGE_AUTO","FORGE_ASSISTED","FORGE_PRO"]).map(x=><button key={x}type="button"className={form.automation_mode===x?"automation-mode-card selected":"automation-mode-card"}data-testid={`choice-${x}`}onClick={()=>set("automation_mode",x)}><b>{x}</b><small>{AUTOMATION_MODE_COPY[x]}</small></button>)}</div></div>'
app = replace_once(app, mode_old, mode_new, "automation mode cards")

numbering = {
    '<p className="eyebrow">01 / PERFIL DO ATLETA</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / PERFIL DO ATLETA</p>',
    '<p className="eyebrow">02 / HISTÓRICO DE TREINO</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / HISTÓRICO DE TREINO</p>',
    '<p className="eyebrow">03 / REGIÕES PRIORITÁRIAS</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / REGIÕES PRIORITÁRIAS</p>',
    '<p className="eyebrow">04 / PREFERÊNCIAS E RECOVERY</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / PREFERÊNCIAS E RECOVERY</p>',
    '<p className="eyebrow">05 / VISUAL ASSESSMENT · OPCIONAL</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / VISUAL ASSESSMENT · OPCIONAL</p>',
    '<p className="eyebrow">06 / PROGRAM ASSISTED</p>': '<p className="eyebrow">{String(step).padStart(2,"0")} / {form.automation_mode.replace("FORGE_","PROGRAM ")}</p>',
}
for old, new in numbering.items():
    app = replace_once(app, old, new, f"dynamic numbering {old}")

app = replace_once(app, '<h1>Seu mapa está pronto para revisão.</h1>', '<h1>Seu mapa está pronto.</h1>', "generic confirm title")
app = replace_once(app, '<p className="muted">No modo Assisted, você aprova antes de aplicar.</p>', '<p className="muted">{AUTOMATION_CONFIRM_COPY[form.automation_mode]}</p>', "dynamic mode confirmation")

APP.write_text(app, encoding="utf-8")

resume = RESUME.read_text(encoding="utf-8-sig")
resume = replace_once(
    resume,
    '["sex", "experience", "goal", "days", "name", "age", "height_cm", "weight_kg"]',
    '["sex", "experience", "goal", "days", "name", "age", "height_cm", "weight_kg",\n   "training_years", "consistency_years", "secondary_goal", "session_minutes", "split",\n   "split_preference", "training_method", "trains_near_failure", "uses_rir", "tracks_loads",\n   "gym_complete", "automation_mode", "microcycle_days"]',
    "resume scalar fields",
)
resume = replace_once(
    resume,
    '  if (respondido(p.priorities)) inicial.priorities = [...p.priorities];\n  else if (prioridadesRespondidas(p)) inicial.priorities = [];',
    '  if (respondido(p.priorities)) inicial.priorities = [...p.priorities];\n  else if (prioridadesRespondidas(p)) inicial.priorities = [];\n\n  if (p.recovery && typeof p.recovery === "object") inicial.recovery = { ...p.recovery };\n  if (Array.isArray(p.equipment)) inicial.equipment = [...p.equipment];\n  if (Array.isArray(p.baseline)) inicial.baseline = [...p.baseline];\n  if (Array.isArray(p.limitations)) inicial.limitations = [...p.limitations];\n  if (p.assessment && typeof p.assessment === "object") inicial.assessment = { ...p.assessment };',
    "resume structured fields",
)
RESUME.write_text(resume, encoding="utf-8")

HELPER.write_text('''import { ONBOARDING_STEPS } from "./musclePriorities";\nimport { passosPendentes } from "./onboardingResume";\n\nexport const ASSESSMENT_MODE_RESUME = "resume";\nexport const ASSESSMENT_MODE_FULL = "full";\n\n/** Retomada evita repeticao; refazer avaliacao reabre absolutamente todas as etapas. */\nexport function passosDoAssessment(perfil, mode = ASSESSMENT_MODE_RESUME) {\n  return mode === ASSESSMENT_MODE_FULL\n    ? [...ONBOARDING_STEPS]\n    : passosPendentes(perfil);\n}\n\nexport function deveAbrirBuilderDepois(automationMode) {\n  return automationMode === "FORGE_PRO";\n}\n\nexport function deveMostrarPreview(automationMode) {\n  return automationMode === "FORGE_ASSISTED";\n}\n''', encoding="utf-8")

TEST.write_text('''import {\n  ASSESSMENT_MODE_FULL,\n  ASSESSMENT_MODE_RESUME,\n  passosDoAssessment,\n  deveAbrirBuilderDepois,\n  deveMostrarPreview,\n} from "./reassessmentMode";\nimport { ONBOARDING_STEPS } from "./musclePriorities";\n\ndescribe("reassessment mode", () => {\n  const perfilRespondido = {\n    priorities: ["Peitoral superior"],\n    preassessment_applied_at: "2026-08-31T00:00:00Z",\n  };\n\n  test("resume pode pular prioridades ja respondidas", () => {\n    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_RESUME)).not.toContain("priorities");\n  });\n\n  test("refazer avaliacao sempre reabre todas as etapas", () => {\n    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_FULL)).toEqual(ONBOARDING_STEPS);\n    expect(passosDoAssessment(perfilRespondido, ASSESSMENT_MODE_FULL)).toContain("priorities");\n  });\n\n  test("cada modo de automacao segue um destino diferente", () => {\n    expect(deveMostrarPreview("FORGE_ASSISTED")).toBe(true);\n    expect(deveMostrarPreview("FORGE_AUTO")).toBe(false);\n    expect(deveAbrirBuilderDepois("FORGE_PRO")).toBe(true);\n    expect(deveAbrirBuilderDepois("FORGE_AUTO")).toBe(false);\n  });\n});\n''', encoding="utf-8")

css = CSS.read_text(encoding="utf-8-sig")
marker = "/* full-reassessment automation mode cards */"
if marker not in css:
    css += '''\n\n/* full-reassessment automation mode cards */\n.automation-mode-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}\n.automation-mode-card{min-height:92px;padding:14px;border:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.025);color:inherit;text-align:left;display:flex;flex-direction:column;gap:8px;justify-content:flex-start}\n.automation-mode-card b{font-size:12px;letter-spacing:.04em}\n.automation-mode-card small{font-size:11px;line-height:1.45;color:var(--muted,#8f8f8f);font-weight:400}\n.automation-mode-card.selected{border-color:rgba(207,151,111,.72);background:rgba(207,151,111,.09);box-shadow:inset 0 0 0 1px rgba(207,151,111,.12)}\n@media(max-width:640px){.automation-mode-grid{grid-template-columns:1fr}.automation-mode-card{min-height:74px}}\n'''
CSS.write_text(css, encoding="utf-8")

# Static guards: fail before tests if a future edit makes this patch partial.
final_app = APP.read_text(encoding="utf-8")
for required in [
    "ASSESSMENT_MODE_FULL",
    "passosDoAssessment(db?.profile,assessmentMode)",
    "setAssessmentMode(ASSESSMENT_MODE_FULL)",
    "deveAbrirBuilderDepois(form.automation_mode)",
    "AUTOMATION_MODE_COPY",
    'const[root,child]=k.split(".")',
]:
    if required not in final_app:
        raise RuntimeError(f"missing post-patch guard: {required}")

print("Full reassessment patch applied successfully.")
