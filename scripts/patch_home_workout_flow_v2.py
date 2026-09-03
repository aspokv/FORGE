from pathlib import Path
import re

# ---------- frontend App.js ----------
app_path = Path('frontend/src/App.js')
app = app_path.read_text()

app = app.replace(
    'import WorkoutLibrary,{replaceActiveSessionWithTemplate} from "./features/WorkoutLibrary";',
    'import WorkoutLibrary from "./features/WorkoutLibrary";'
)

pattern = re.compile(r'const addLibraryTemplate=async template=>\{.*?\};const openManual=', re.S)
replacement = '''const addLibraryTemplate=async template=>{const response=await axios.post(`${API}/workout-templates/apply`,{template_id:template.id});setDb(state=>({...state,program:response.data.program,profile:{...state.profile,custom_program:response.data.custom,automation_mode:"FORGE_PRO"}}));return response.data};const openManual='''
app, count = pattern.subn(replacement, app, count=1)
if count != 1:
    raise SystemExit(f'addLibraryTemplate replacement count={count}')

old_library = '<WorkoutLibrary API={API}exercises={db.exercises||[]}profile={db.profile}program={db.program}onBuild={onLibraryBuild}onTemplateAdd={onLibraryTemplateAdd}/>'
new_library = '<WorkoutLibrary API={API}exercises={db.exercises||[]}profile={db.profile}program={db.program}onBuild={onLibraryBuild}onTemplateAdd={onLibraryTemplateAdd}onApplied={()=>setView("session")}/>'
if old_library not in app:
    raise SystemExit('WorkoutLibrary render target not found')
app = app.replace(old_library, new_library, 1)

if 'const activeSet=useMemo' not in app:
    avg_pattern = re.compile(r'(  const averageRest=.*?;\n)(  const viewTabs=)', re.S)
    active_code = '''  const activeSet=useMemo(()=>{for(const exercise of items){for(let setIndex=0;setIndex<Number(exercise.sets||0);setIndex+=1){if(!done[exercise.exercise_id+setIndex])return {exerciseId:exercise.exercise_id,setIndex};}}return null;},[items,done]);\n'''
    app, count = avg_pattern.subn(lambda m: m.group(1) + active_code + m.group(2), app, count=1)
    if count != 1:
        raise SystemExit(f'activeSet insertion count={count}')

app, removed_current = re.subn(r'\n\s*const currentSet=Array\.from\(\{length:x\.sets\},\(_,n\)=>n\)\.find\(n=>!done\[x\.exercise_id\+n\]\);', '', app, count=1)
if removed_current != 1 and 'currentSet=Array.from' in app:
    raise SystemExit('failed removing per-exercise currentSet')

old_class = 'done[x.exercise_id+n]?"completed":n===currentSet?"current":"upcoming"'
new_class = 'done[x.exercise_id+n]?"completed":activeSet?.exerciseId===x.exercise_id&&activeSet?.setIndex===n?"current":"upcoming"'
if old_class in app:
    app = app.replace(old_class, new_class, 1)
elif new_class not in app:
    raise SystemExit('set-row active class target not found')

app_path.write_text(app)

# ---------- Magic V2 CSS ----------
css_path = Path('frontend/src/magic-patterns-v2.css')
css = css_path.read_text()
old_order = '''.ledger-home .forge-mobile-mast{order:0}
.ledger-home .ledger-context{order:1}
.ledger-home .ledger-macros{order:2}
.ledger-home .ledger-hydration{order:3}
.ledger-home .ledger-week{order:4}
.ledger-home .today-action-card{order:5}
.ledger-home .home-cycle-status{order:6}
.ledger-home .forge-home-tools{order:7}'''
new_order = '''.ledger-home .forge-mobile-mast{order:0}
.ledger-home .ledger-context{order:1}
.ledger-home .ledger-macros{order:2}
.ledger-home .ledger-hydration{order:3}
.ledger-home .home-workout-hero{order:4}
.ledger-home .ledger-week{order:5}
.ledger-home .ledger-milestone{order:6}
.ledger-home .home-cycle-status{order:7}
.ledger-home .forge-home-tools{order:8}'''
if old_order not in css:
    raise SystemExit('home order block not found')
css = css.replace(old_order, new_order, 1)

cleanup = r'''

/* HOME + WORKOUT FLOW V2: hierarchy and collision cleanup */
.ledger-home .home-workout-hero{margin:0 0 20px!important}
.ledger-home .ledger-milestone{margin:0 0 20px!important;position:static!important}

.workout-page .workout-overview{
  position:relative!important;
  display:grid!important;
  grid-template-columns:minmax(0,1fr)!important;
  gap:16px!important;
  align-items:stretch!important;
  overflow:visible!important;
}
.workout-page .muscle-session-map{order:2!important;position:static!important;width:100%!important;min-width:0!important}
.workout-page .workout-overview-copy{
  order:1!important;
  position:static!important;
  inset:auto!important;
  width:100%!important;
  display:grid!important;
  grid-template-columns:minmax(0,1fr) auto!important;
  gap:6px 16px!important;
  align-items:end!important;
  min-width:0!important;
}
.workout-page .workout-overview-copy>span{grid-column:1/-1!important}
.workout-page .workout-overview-copy>b{grid-column:1!important;min-width:0!important}
.workout-page .workout-overview-copy>small{grid-column:2!important;text-align:right!important;white-space:normal!important;max-width:150px!important}
.workout-page .workout-kpis{
  order:3!important;
  position:static!important;
  inset:auto!important;
  width:100%!important;
  min-width:0!important;
  display:grid!important;
  grid-template-columns:repeat(4,minmax(0,1fr))!important;
}
.workout-page .workout-kpis>div{position:static!important;min-width:0!important;align-content:start!important}
.workout-page .workout-kpis span,.workout-page .workout-kpis b,.workout-page .workout-kpis em{position:static!important;display:block!important;min-width:0!important}

.workout-page .set-row{position:relative!important}
.workout-page .set-row.current{
  border-left:0!important;
  padding-left:8px!important;
  background:rgba(224,182,133,.055)!important;
  opacity:1!important;
}
.workout-page .set-row.current::before{
  content:"";
  position:absolute;
  left:0;
  top:7px;
  bottom:7px;
  width:2px;
  border-radius:2px;
  background:var(--forge-champagne);
}
.workout-page .set-row.upcoming{opacity:.66!important}
.workout-page .set-row.completed{opacity:.72!important}

@media(max-width:800px){
  .workout-page .workout-overview{grid-template-columns:1fr!important;gap:13px!important;padding:14px!important}
  .workout-page .workout-overview-copy{grid-template-columns:1fr!important;gap:4px!important}
  .workout-page .workout-overview-copy>span,.workout-page .workout-overview-copy>b,.workout-page .workout-overview-copy>small{grid-column:1!important;text-align:left!important;max-width:none!important}
  .workout-page .workout-kpis{grid-template-columns:repeat(2,minmax(0,1fr))!important;border-radius:var(--forge-radius)!important}
  .workout-page .workout-kpis>div{min-height:80px!important;padding:11px 12px!important;border-right:1px solid var(--forge-line)!important;border-bottom:1px solid var(--forge-line)!important}
  .workout-page .workout-kpis>div:nth-child(even){border-right:0!important}
  .workout-page .workout-kpis>div:nth-child(n+3){border-bottom:0!important}
  .workout-page .workout-kpis span{font-size:8px!important;line-height:1.35!important;white-space:normal!important}
  .workout-page .workout-kpis b{margin-top:5px!important;font-size:18px!important;line-height:1!important}
  .workout-page .workout-kpis em{margin-top:5px!important;font-size:8px!important;line-height:1.35!important;white-space:normal!important}
  .workout-page .set-row.current{padding-left:5px!important}
  .workout-page .set-row.upcoming{opacity:.62!important}
}
'''
if 'HOME + WORKOUT FLOW V2' not in css:
    css += cleanup
css_path.write_text(css)

# ---------- backend atomic template apply ----------
server_path = Path('backend/server.py')
server = server_path.read_text()
server = server.replace('from workout_templates import public_catalog', 'from workout_templates import WORKOUT_TEMPLATES, public_catalog')

if 'class WorkoutTemplateApplyIn' not in server:
    anchor = '''class HydrationAddIn(BaseModel):
    amount_ml: int = Field(..., ge=50, le=1000)
'''
    addition = anchor + '''\n\nclass WorkoutTemplateApplyIn(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=80)
    profile_id: Optional[str] = None
'''
    if anchor not in server:
        raise SystemExit('HydrationAddIn anchor not found')
    server = server.replace(anchor, addition, 1)

if '@api.post("/workout-templates/apply")' not in server:
    get_route = '''@api.get("/workout-templates")
async def workout_templates(_user=Depends(get_current_user)):
    """Curated sessions for the athlete-controlled Program Builder.

    Returning templates is read-only. Applying one still goes through the existing
    /custom-program endpoint, ownership checks and explicit athlete confirmation.
    """
    return public_catalog()
'''
    apply_route = get_route + '''\n\n@api.post("/workout-templates/apply")
async def apply_workout_template(payload: WorkoutTemplateApplyIn, user=Depends(get_current_user)):
    """Atomically replace the athlete's active session with one curated template.

    The client sends only a stable template id. The server owns the active-day pointer,
    current program snapshot and persistence so a stale browser cannot append or replace
    the wrong day.
    """
    target = owned_profile_id(user, payload.profile_id)
    template = next((item for item in WORKOUT_TEMPLATES if item.get("id") == payload.template_id), None)
    if not template:
        raise HTTPException(404, "Modelo de treino não encontrado")

    profile = await load_profile(target)
    current = await build_program(profile)
    raw_sessions = current.get("sessions") or []
    active_day = current.get("active_day")
    if active_day is None or not raw_sessions:
        raise HTTPException(409, "Não há uma sessão ativa para substituir")

    sessions = []
    target_found = False
    for raw in raw_sessions:
        day = int(raw.get("day") or 0)
        if day == int(active_day):
            target_found = True
            sessions.append({
                "day": day,
                "label": template.get("name") or "Sessão",
                "demand": template.get("demand") or "MODERATE",
                "focus": list(template.get("focus") or []),
                "template_id": template.get("id"),
                "exercises": [dict(item) for item in template.get("exercises") or []],
            })
            continue
        # Remove only stale duplicate copies left by the historical append behavior.
        if raw.get("template_id") == template.get("id"):
            continue
        sessions.append({
            "day": day,
            "label": raw.get("label") or f"Sessão {day}",
            "demand": raw.get("demand") or "MODERATE",
            "focus": list(raw.get("focus") or []),
            "template_id": raw.get("template_id"),
            "exercises": [dict(item) for item in raw.get("exercises") or []],
        })

    if not target_found:
        raise HTTPException(409, "A sessão ativa não existe mais no programa")

    custom_before = profile.get("custom_program") or {}
    doc = {
        "profile_id": target,
        "name": custom_before.get("name") or current.get("name") or "Programa FORGE personalizado",
        "week": custom_before.get("week") or current.get("week") or "Microciclo personalizado",
        "session_minutes": int(custom_before.get("session_minutes") or profile.get("session_minutes") or 60),
        "sessions": sessions,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.profiles.update_one(
        {"id": target},
        {"$set": {"custom_program": doc, "automation_mode": "FORGE_PRO",
                  "user_id": target, "onboarding_required": False},
         "$setOnInsert": {"name": "Novo atleta", "goal": "Hipertrofia", "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    refreshed = await load_profile(target)
    return {"program": await build_program(refreshed), "custom": doc, "applied_template_id": template.get("id")}
'''
    if get_route not in server:
        raise SystemExit('workout_templates GET route anchor not found')
    server = server.replace(get_route, apply_route, 1)

server_path.write_text(server)

print('Patched App.js, magic-patterns-v2.css and backend/server.py')
