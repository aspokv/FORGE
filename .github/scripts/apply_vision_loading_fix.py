from pathlib import Path

app_path = Path("frontend/src/App.js")
css_path = Path("frontend/src/features/performance-os.css")
app = app_path.read_text(encoding="utf-8-sig")
css = css_path.read_text(encoding="utf-8")

old_state = '  const[visual,setVisual]=useState(false),[file,setFile]=useState(null),[notice,setNotice]=useState(false),[visionResult,setVisionResult]=useState(null);'
new_state = '  const[visual,setVisual]=useState(false),[file,setFile]=useState(null),[notice,setNotice]=useState(false),[visionResult,setVisionResult]=useState(null),[visionLoading,setVisionLoading]=useState(false);'
assert old_state in app, "Profile vision state signature not found"
app = app.replace(old_state, new_state, 1)

old_send = '  const send=async()=>{const f=new FormData();f.append("profile_id",db.profile.id);f.append("consent","true");f.append("views",JSON.stringify(["frente"]));if(file)f.append("photos",file);try{const r=await fetch(`${API}/visual-assessment`,{method:"POST",body:f,headers:{Authorization:`Bearer ${localStorage.getItem("forge_token")||""}`}});const data=await r.json();setNotice(true);setVisionResult(data)}catch{setNotice(true);setVisionResult(null)}};'
new_send = '''  const send=async()=>{\n    if(!file||visionLoading)return;\n    setVisionLoading(true);setNotice(false);setVisionResult(null);\n    const f=new FormData();f.append("profile_id",db.profile.id);f.append("consent","true");f.append("views",JSON.stringify(["frente"]));f.append("photos",file);\n    try{\n      const r=await fetch(`${API}/visual-assessment`,{method:"POST",body:f,headers:{Authorization:`Bearer ${localStorage.getItem("forge_token")||""}`}});\n      const data=await r.json();setNotice(true);setVisionResult(data);\n    }catch{setNotice(true);setVisionResult(null)}finally{setVisionLoading(false)}\n  };'''
assert old_send in app, "send() signature not found"
app = app.replace(old_send, new_send, 1)

old_visual = '<label className="upload-box"data-testid="photo-upload-label"><FileUp size={20}/>{file?file.name:"Adicionar foto"}<input data-testid="photo-upload-input"type="file"accept="image/*"onChange={e=>setFile(e.target.files[0])}/></label><button className="primary-button"data-testid="submit-visual-assessment"onClick={send}>Enviar com consentimento</button>{notice&&'
new_visual = '<label className={`upload-box${visionLoading?" is-loading":""}`}data-testid="photo-upload-label"><FileUp size={20}/>{file?file.name:"Adicionar foto"}<input data-testid="photo-upload-input"type="file"accept="image/*"disabled={visionLoading}onChange={e=>{setFile(e.target.files[0]);setNotice(false);setVisionResult(null)}}/></label><button className="primary-button vision-submit-button"data-testid="submit-visual-assessment"disabled={!file||visionLoading}aria-busy={visionLoading}onClick={send}>{visionLoading?<><span className="vision-spinner"aria-hidden="true"/> Analisando seu físico…</>:"Enviar com consentimento"}</button>{visionLoading&&<div className="vision-loading-card"data-testid="visual-loading-state"role="status"aria-live="polite"><span className="vision-spinner large"aria-hidden="true"/><div><b>Analisando seu físico…</b><span>Enviando a imagem e processando com o Forge Vision. Isso pode levar alguns segundos.</span></div></div>}{notice&&'
assert old_visual in app, "visual upload controls signature not found"
app = app.replace(old_visual, new_visual, 1)

css_block = '''\n\n/* Visual assessment loading feedback */\n.vision-submit-button{display:flex;align-items:center;justify-content:center;gap:9px}\n.vision-submit-button:disabled{cursor:not-allowed;opacity:.72}\n.vision-spinner{width:15px;height:15px;border-radius:50%;border:2px solid rgba(20,16,14,.28);border-top-color:currentColor;display:inline-block;animation:forgeVisionSpin .8s linear infinite;flex:0 0 auto}\n.vision-spinner.large{width:22px;height:22px;border-color:rgba(207,151,111,.25);border-top-color:rgba(225,174,133,.95)}\n.vision-loading-card{margin-top:12px;padding:14px 15px;border:1px solid rgba(207,151,111,.28);background:rgba(207,151,111,.055);display:flex;align-items:center;gap:12px;border-radius:12px}\n.vision-loading-card div{display:flex;flex-direction:column;gap:3px}\n.vision-loading-card b{font-size:12px;letter-spacing:.02em}\n.vision-loading-card span:not(.vision-spinner){font-size:10px;line-height:1.45;color:var(--muted,#8f8f8f)}\n.upload-box.is-loading{opacity:.62;pointer-events:none}\n@keyframes forgeVisionSpin{to{transform:rotate(360deg)}}\n'''
if "@keyframes forgeVisionSpin" not in css:
    css += css_block

# Regression assertions: request lifecycle must always expose and reset loading.
assert "setVisionLoading(true)" in app
assert "finally{setVisionLoading(false)}" in app
assert 'data-testid="visual-loading-state"' in app
assert 'disabled={!file||visionLoading}' in app

app_path.write_text(app, encoding="utf-8")
css_path.write_text(css, encoding="utf-8")
print("Vision loading UX patch applied.")
