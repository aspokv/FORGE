from pathlib import Path

path = Path("frontend/src/features/WorkoutLibrary.jsx")
text = path.read_text()

if 'data-testid="library-apply-inline-status"' in text:
    raise SystemExit(0)

text = text.replace(
    'export default function WorkoutLibrary({ API, exercises = [], onBuild, onTemplateAdd, profile, program, onClose }) {',
    'export default function WorkoutLibrary({ API, exercises = [], onBuild, onTemplateAdd, profile, program, onClose, onApplied }) {'
)
text = text.replace(
    '  const [actionMessage, setActionMessage] = useState("");\n  const [expertAccepted, setExpertAccepted] = useState(false);',
    '  const [actionMessage, setActionMessage] = useState("");\n  const [actionTemplateId, setActionTemplateId] = useState("");\n  const [expertAccepted, setExpertAccepted] = useState(false);'
)

old_apply = '''  const applyTemplate = async template => {
    if (!onTemplateAdd) return toggleTemplate(template);
    if (isApplied(template.id) || addingId) return;
    setAddingId(template.id);
    setActionMessage("");
    try {
      await onTemplateAdd(template);
      setAppliedIds(current => new Set([...current, template.id]));
      setActionMessage(`${template.name} agora é o seu treino atual.`);
    } catch (requestError) {
      setActionMessage(requestError?.response?.data?.detail || requestError?.message || "Não foi possível adicionar a sessão ao treino.");
    } finally {
      setAddingId("");
    }
  };'''
new_apply = '''  const applyTemplate = async template => {
    if (!onTemplateAdd) return toggleTemplate(template);
    if (isApplied(template.id) || addingId) return;
    setAddingId(template.id);
    setActionTemplateId(template.id);
    setActionMessage("");
    try {
      const result = await onTemplateAdd(template);
      setAppliedIds(current => new Set([...current, template.id]));
      setActionMessage(`${template.name} agora é o seu treino atual.`);
      setPreviewId("");
      if (onApplied) {
        onApplied(template, result);
      } else if (typeof document !== "undefined") {
        requestAnimationFrame(() => document.querySelector('[data-testid="training-current-tab"]')?.click());
      }
    } catch (requestError) {
      setActionMessage(requestError?.response?.data?.detail || requestError?.message || "Não foi possível usar esta sessão agora. Tente novamente.");
    } finally {
      setAddingId("");
    }
  };'''
if old_apply not in text:
    raise SystemExit("applyTemplate block not found")
text = text.replace(old_apply, new_apply)

old_mobile = '                <button type="button" disabled={addingId === template.id || isApplied(template.id)} className="primary-button library-mobile-apply" onClick={() => applyTemplate(template)}>{addingId === template.id ? "Aplicando…" : isApplied(template.id) ? "Este é o treino atual" : <>Usar como treino atual <ChevronRight size={16}/></>}</button>'
new_mobile = old_mobile + '\n                {actionTemplateId === template.id && actionMessage && <p data-testid="library-apply-inline-status" className={`library-action-message${actionMessage.includes("treino atual") ? " success" : " error"}`} role="status" aria-live="polite">{actionMessage}</p>}'
if old_mobile not in text:
    raise SystemExit("mobile apply button not found")
text = text.replace(old_mobile, new_mobile)

old_desktop = '          <button disabled={addingId === active.id || isApplied(active.id)} className={isSelected(active.id) || isApplied(active.id) ? "secondary-button" : "primary-button"} onClick={() => applyTemplate(active)}>'
new_desktop = '          <button type="button" disabled={addingId === active.id || isApplied(active.id)} className={isSelected(active.id) || isApplied(active.id) ? "secondary-button" : "primary-button"} onClick={() => applyTemplate(active)}>'
if old_desktop not in text:
    raise SystemExit("desktop apply button not found")
text = text.replace(old_desktop, new_desktop)

old_desktop_close = '''          </button>
        </aside>}'''
new_desktop_close = '''          </button>
          {actionTemplateId === active.id && actionMessage && <p className={`library-action-message${actionMessage.includes("treino atual") ? " success" : " error"}`} role="status" aria-live="polite">{actionMessage}</p>}
        </aside>}'''
if old_desktop_close not in text:
    raise SystemExit("desktop status insertion point not found")
text = text.replace(old_desktop_close, new_desktop_close, 1)

path.write_text(text)
