from pathlib import Path

app_path=Path('frontend/src/App.js')
idx_path=Path('frontend/src/index.js')
home_path=Path('frontend/src/features/ReferenceHome.jsx')
css_path=Path('frontend/src/reference-exact-v3.css')

app=app_path.read_text()

def replace_once(old,new,label):
    global app
    if new in app:
        return
    if old not in app:
        raise SystemExit(f'missing marker: {label}')
    app=app.replace(old,new,1)

# Componentes dedicados: a referência não é mais uma skin do Today/Workout antigos.
replace_once(
    'import WorkoutLibrary from "./features/WorkoutLibrary";\n',
    'import WorkoutLibrary from "./features/WorkoutLibrary";\nimport ReferenceHome from "./features/ReferenceHome";\nimport ReferenceWorkoutPreview from "./features/ReferenceWorkoutPreview";\n',
    'reference imports',
)
old_home='return <Today db={db}analytics={analytics}report={report}start={start}openAnalysis={openAnalysis}openBuilder={openBuilder}openManual={openManual}onRecoveryCheckin={onRecoveryCheckin}/>'
new_home='return <ReferenceHome db={db}start={start}onRecoveryCheckin={onRecoveryCheckin}/>'
replace_once(old_home,new_home,'Home route')
replace_once(
    'const[view,setView]=useState("session");\n  const[done,setDone]=useState({});',
    'const[view,setView]=useState("session");\n  const[sessionStarted,setSessionStarted]=useState(false);\n  const[done,setDone]=useState({});',
    'sessionStarted state',
)
replace_once(
    'const[startedAt,setStartedAt]=useState(()=>Date.now());\n  useEffect(()=>{const init={};',
    'const[startedAt,setStartedAt]=useState(()=>Date.now());\n  useEffect(()=>setSessionStarted(false),[activeSession?.day,activeSession?.label]);\n  useEffect(()=>{const init={};',
    'session reset effect',
)
replace_once(
    'onApplied={()=>setView("session")}/>',
    'onApplied={()=>{setView("session");setSessionStarted(false)}}/>',
    'library return',
)
replace_once(
    'setStartedAt(Date.now());finishLock.current=false};\n  const recLevel=',
    'setStartedAt(Date.now());finishLock.current=false;setSessionStarted(false)};\n  const recLevel=',
    'next workout preview reset',
)
replace_once(
    '  return <div className="content workout-page">\n    {viewTabs}\n    <div className="workout-head">',
    '  if(!sessionStarted)return <ReferenceWorkoutPreview db={db}activeSession={activeSession}items={items}onStart={()=>{setStartedAt(Date.now());setSessionStarted(true)}}onLibrary={()=>setView("library")}/>;\n  return <div className="content workout-page workout-live-reference">\n    <div className="workout-head">',
    'workout preview gate',
)
old_nav='<span>{name==="Hoje"?"Início":name==="Alimentação"?"Nutrição":name}</span>'
new_nav='<span>{name==="Hoje"?"Início":name==="Treino"&&tab==="Hoje"?"Treinos":name==="Alimentação"?"Nutrição":name}</span>'
replace_once(old_nav,new_nav,'navigation labels')
app_path.write_text(app)

idx=idx_path.read_text()
idx=idx.replace('import "@/ad-reference-home-workout.css";\n','')
if 'import "@/reference-exact-v3.css";' not in idx:
    marker='import "@/magic-patterns-v2.css";\n'
    if marker not in idx: raise SystemExit('missing index css marker')
    idx=idx.replace(marker,marker+'import "@/reference-exact-v3.css";\n',1)
idx_path.write_text(idx)

# Endpoints de hidratação reais do backend atual.
home=home_path.read_text()
home=home.replace('axios.post(`${API}/hydration`,{local_date:localDateKey(),amount_ml:amount})','axios.post(`${API}/hydration/${localDateKey()}`,{amount_ml:amount})')
home=home.replace('axios.post(`${API}/hydration/undo`,{local_date:localDateKey()})','axios.delete(`${API}/hydration/${localDateKey()}/last`)')
home_path.write_text(home)

# Header do Workout: a referência aprovada mostra FORGE + um único sino.
css=css_path.read_text()
css=css.replace('.ref3-workout-head>div{display:flex;gap:8px;align-items:center}.ref3-workout-head button,.ref3-workout-head>div>span{width:40px;height:40px;display:grid;place-items:center;border:0;background:transparent;color:#bdbbb7}', '.ref3-workout-head button{width:40px;height:40px;display:grid;place-items:center;border:0;background:transparent;color:#bdbbb7}')
css_path.write_text(css)

# Assertions para evitar um CI verde em cima da tela velha.
app=app_path.read_text();idx=idx_path.read_text();home=home_path.read_text();css=css_path.read_text()
checks={
 'ReferenceHome route':'return <ReferenceHome db={db}start={start}onRecoveryCheckin={onRecoveryCheckin}/>' in app,
 'ReferenceWorkoutPreview gate':'if(!sessionStarted)return <ReferenceWorkoutPreview' in app,
 'live class':'workout-page workout-live-reference' in app,
 'exact css':'reference-exact-v3.css' in idx,
 'old rejected css removed':'ad-reference-home-workout.css' not in idx,
 'hydration add endpoint':'axios.post(`${API}/hydration/${localDateKey()}`' in home,
 'hydration delete':'axios.delete(`${API}/hydration/${localDateKey()}/last`)' in home,
 'single workout header button':'.ref3-workout-head>div' not in css,
}
missing=[k for k,v in checks.items() if not v]
if missing: raise SystemExit('failed assertions: '+', '.join(missing))
print('reference exact v3 wiring applied')
