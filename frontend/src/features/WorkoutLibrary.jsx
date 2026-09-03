import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { BookOpen, Check, ChevronRight, Dumbbell, Layers3, Plus, ShieldAlert, Timer, X } from "lucide-react";
import "./workout-library.css";

export const templateToSession = (template, day) => ({
  day,
  label: template.name,
  demand: template.demand || "MODERATE",
  focus: [...(template.focus || [])],
  exercises: (template.exercises || []).map(exercise => ({ ...exercise })),
  template_id: template.id,
});

export const replaceActiveSessionWithTemplate = (program, template, activeDay) => {
  const sessions = (program?.sessions || []).map(session => ({
    ...session,
    exercises: (session.exercises || []).map(exercise => ({ ...exercise })),
  }));
  const targetDay = Number(activeDay ?? program?.active_day ?? sessions[0]?.day ?? 1);
  if (!sessions.length) return [templateToSession(template, targetDay || 1)];
  const staleTailIndex = sessions.findIndex((session, index) =>
    index === sessions.length - 1 && Number(session.day) !== targetDay && session.template_id === template.id);
  if (staleTailIndex >= 0) sessions.splice(staleTailIndex, 1);
  const targetIndex = sessions.findIndex(session => Number(session.day) === targetDay);
  if (targetIndex < 0) throw new Error("Sessão ativa não encontrada no programa.");
  sessions[targetIndex] = templateToSession(template, targetDay);
  return sessions;
};

export const buildLibraryProgram = templates => ({
  name: "Programa FORGE selecionado",
  week: "Microciclo da biblioteca",
  session_minutes: templates.length ? Math.round(templates.reduce((sum, item) => sum + Number(item.duration || 60), 0) / templates.length) : 60,
  sessions: templates.map((template, index) => templateToSession(template, index + 1)),
});

export const programPhaseToDraft = (program, phase) => ({
  name: `${program.name} · ${phase.label}`,
  week: phase.weeks ? `${phase.label} · ${phase.weeks}` : phase.label,
  session_minutes: phase.sessions.length
    ? Math.round(phase.sessions.reduce((sum, item) => sum + Number(item.duration || 60), 0) / phase.sessions.length)
    : 60,
  source_program_id: program.id,
  source_phase_id: phase.id,
  sessions: phase.sessions.map((workout, index) => ({
    day: index + 1,
    label: workout.label,
    demand: workout.demand || "MODERATE",
    focus: [...(workout.focus || [])],
    exercises: (workout.exercises || []).map(exercise => ({ ...exercise })),
  })),
});

const emptyCatalog = { categories: [], templates: [], program_categories: [], programs: [] };

export const isFemaleProfile = profile => {
  const value = String(profile?.sex || profile?.gender || profile?.assessment?.sex || profile?.assessment?.gender || "").toLowerCase();
  return ["female", "feminino", "f", "mulher"].includes(value);
};

export default function WorkoutLibrary({ API, exercises = [], onBuild, onTemplateAdd, profile, program, onClose, onApplied, initialCategory="push" }) {
  const [catalog, setCatalog] = useState(emptyCatalog);
  const [mode, setMode] = useState("sessions");
  const [category, setCategory] = useState(initialCategory);
  const [programCategory, setProgramCategory] = useState("abc");
  const [active, setActive] = useState(null);
  const [previewId, setPreviewId] = useState("");
  const [activeProgram, setActiveProgram] = useState(null);
  const [activePhaseId, setActivePhaseId] = useState("");
  const [selected, setSelected] = useState([]);
  const [audience, setAudience] = useState(() => isFemaleProfile(profile) ? "female" : "all");
  const [appliedIds, setAppliedIds] = useState(() => new Set((program?.sessions || []).map(item => item.template_id).filter(Boolean)));
  const [addingId, setAddingId] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [actionTemplateId, setActionTemplateId] = useState("");
  const [expertAccepted, setExpertAccepted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    axios.get(`${API}/workout-templates`).then(response => {
      if (!alive) return;
      const next = { ...emptyCatalog, ...response.data };
      setCatalog(next);
      setActive(next.templates?.[0] || null);
      setActiveProgram(next.programs?.[0] || null);
      setActivePhaseId(next.programs?.[0]?.phases?.[0]?.id || "");
    }).catch(() => {
      if (alive) setError("Não foi possível carregar a biblioteca agora.");
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, [API]);

  const exerciseIndex = useMemo(() => Object.fromEntries(exercises.map(item => [item.id, item])), [exercises]);
  useEffect(() => {
    setAppliedIds(new Set((program?.sessions || []).map(item => item.template_id).filter(Boolean)));
  }, [program]);
  const visible = useMemo(() => catalog.templates.filter(item => item.category === category && (audience === "all" || (item.audience || "unisex") === audience)), [catalog.templates, category, audience]);
  const visiblePrograms = useMemo(() => catalog.programs.filter(item => (item.categories || [item.category]).includes(programCategory) && (audience === "all" || (item.audience_type || "unisex") === audience)), [catalog.programs, programCategory, audience]);
  const activePhase = useMemo(() => activeProgram?.phases?.find(item => item.id === activePhaseId) || activeProgram?.phases?.[0] || null, [activeProgram, activePhaseId]);
  useEffect(() => {
    if (visible.length && !visible.some(item => item.id === active?.id)) setActive(visible[0]);
  }, [visible, active?.id]);
  useEffect(() => {
    if (visiblePrograms.length && !visiblePrograms.some(item => item.id === activeProgram?.id)) {
      setActiveProgram(visiblePrograms[0]);
      setActivePhaseId(visiblePrograms[0]?.phases?.[0]?.id || "");
    }
  }, [visiblePrograms, activeProgram?.id]);
  const isSelected = id => selected.some(item => item.id === id);
  const activeTemplateId = useMemo(() => {
  const sessions = program?.sessions || [];
  const activeDay = Number(program?.active_day ?? sessions[0]?.day ?? 1);
  return sessions.find(item => Number(item.day) === activeDay)?.template_id || null;
}, [program]);
  const isApplied = id => activeTemplateId === id;

  const chooseCategory = id => {
    setCategory(id);
    setPreviewId("");
    setActive(catalog.templates.find(item => item.category === id) || null);
  };
  const chooseProgramCategory = id => {
    const next = catalog.programs.find(item => (item.categories || [item.category]).includes(id)) || null;
    setProgramCategory(id);
    setActiveProgram(next);
    setActivePhaseId(next?.phases?.[0]?.id || "");
    setExpertAccepted(false);
  };
  const chooseProgram = item => {
    setActiveProgram(item);
    setActivePhaseId(item.phases?.[0]?.id || "");
    setExpertAccepted(false);
  };
  const toggleTemplate = template => {
    setSelected(list => list.some(item => item.id === template.id)
      ? list.filter(item => item.id !== template.id)
      : [...list, template]);
  };
  const moveSelected = (index, direction) => {
    const target = index + direction;
    if (target < 0 || target >= selected.length) return;
    setSelected(list => {
      const next = [...list];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };
  const applyTemplate = async template => {
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
      const detail=requestError?.response?.data?.detail;
      setActionMessage((typeof detail==="string"?detail:detail?.message) || requestError?.message || "Não foi possível usar esta sessão agora. Tente novamente.");
    } finally {
      setAddingId("");
    }
  };

  if (loading) return <div className="content workout-library"><div className="library-loading">Preparando os modelos FORGE...</div></div>;
  if (error) return <div className="content workout-library"><div className="library-error">{error}</div></div>;

  return <div className="content workout-library" data-testid="workout-library">
    <section className="library-intro">
      <div>
        <p className="eyebrow">FORGE / ARQUITETURAS DE TREINO</p>
        <h2>Escolha uma sessão ou um programa completo.</h2>
        <p className="muted">Modelos profissionais normalizados para o motor do FORGE. Veja todos os exercícios antes de aplicar uma sessão ao treino atual.</p>
      </div>
      <div className="library-intro-actions">
        <div className="library-count"><strong>{catalog.templates.length + catalog.programs.length}</strong><span>arquiteturas<br/>curadas</span></div>
        {onClose && <button className="icon-button" onClick={onClose} aria-label="Fechar biblioteca"><X size={19}/></button>}
      </div>
    </section>

    <div className="library-mode" role="tablist" aria-label="Tipo de modelo">
      <button role="tab" aria-selected={mode === "sessions"} className={mode === "sessions" ? "active" : ""} onClick={() => setMode("sessions")}><Dumbbell size={17}/><span>Sessões avulsas<small>Push, Pull, Legs, Upper, Lower e Full Body</small></span></button>
      <button role="tab" aria-selected={mode === "programs"} className={mode === "programs" ? "active" : ""} onClick={() => setMode("programs")} data-testid="library-programs-tab"><BookOpen size={17}/><span>Programas completos<small>ABC, ABCD, ABCDE, ABCDEF e Upper / Lower</small></span></button>
    </div>

    {mode === "sessions" ? <>
      <div className="library-audience-filter" role="group" aria-label="Curadoria de treinos">
        <span>Curadoria</span>
        <button className={audience === "all" ? "active" : ""} onClick={() => setAudience("all")}>Todos</button>
        <button className={audience === "female" ? "active" : ""} onClick={() => setAudience("female")} data-testid="library-audience-female">Feminino</button>
        <button className={audience === "unisex" ? "active" : ""} onClick={() => setAudience("unisex")}>Unissex</button>
        {isFemaleProfile(profile) && <em>Seleção feminina ativada pelo seu perfil</em>}
      </div>
      <nav className="library-categories" aria-label="Categorias de treino">
        {catalog.categories.map(item => <button key={item.id} className={category === item.id ? "active" : ""} onClick={() => chooseCategory(item.id)} data-testid={`library-category-${item.id}`}>
          <b>{item.label}</b><span>{item.subtitle}</span>
        </button>)}
      </nav>

      <div className="library-layout">
        <section className="library-variants" aria-label="Variações disponíveis">
          <div className="library-section-head"><div><p className="eyebrow">{String(visible.length).padStart(2,"0")} VARIAÇÕES</p><h3>{catalog.categories.find(item => item.id === category)?.label}</h3></div><span>Escolha pelo objetivo da sessão</span></div>
          <div className="library-card-grid">
            {visible.map((template, index) => <article key={template.id} className={`${active?.id === template.id ? "active " : ""}${previewId === template.id ? "preview-open " : ""}${isSelected(template.id) || isApplied(template.id) ? "selected" : ""}`} data-testid={`workout-template-${template.id}`} onClick={() => { setActive(template); setPreviewId(template.id); }}>
              <div className="library-card-index">0{index + 1}</div>
              <div className="library-card-top"><span>{template.style}</span><em>{template.level}</em></div>
              <h3>{template.name}</h3>
              <p>{template.description}</p>
              <div className="library-card-stats"><span><Dumbbell size={14}/>{template.exercise_count} exercícios</span><span><Layers3 size={14}/>{template.total_sets} séries</span><span><Timer size={14}/>{template.duration} min</span></div>
              <div className="library-focus">{template.focus.map(item => <span key={item}>{item}</span>)}</div>
              <button disabled={addingId === template.id} className={isApplied(template.id) ? "library-add selected" : "library-add"} onClick={event => { event.stopPropagation(); setActive(template); setPreviewId(current => current === template.id ? "" : template.id); }}>
                {addingId === template.id ? "Carregando…" : previewId === template.id ? "Ocultar exercícios" : isApplied(template.id) ? <><Check size={16}/> Ver treino atual</> : <><ChevronRight size={16}/> Ver exercícios</>}
              </button>
              {previewId === template.id && <div className="library-mobile-session-preview" data-testid={`template-exercises-${template.id}`} onClick={event => event.stopPropagation()}>
                <div className="library-mobile-preview-head"><span>EXERCÍCIOS DA SESSÃO</span><em>{template.total_sets} séries · {template.duration} min</em></div>
                <div className="library-mobile-exercise-list">{template.exercises.map((item, exerciseIndexNumber) => <div key={`${item.exercise_id}-${exerciseIndexNumber}`}><span>{String(exerciseIndexNumber + 1).padStart(2,"0")}</span><div><b>{exerciseIndex[item.exercise_id]?.name || item.exercise_id}</b><small>{item.sets} séries · {item.reps} reps · RIR {item.rir}</small></div><em>{item.rest}</em></div>)}</div>
                <button type="button" disabled={addingId === template.id || isApplied(template.id)} className="primary-button library-mobile-apply" onClick={() => applyTemplate(template)}>{addingId === template.id ? "Aplicando…" : isApplied(template.id) ? "Este é o treino atual" : <>Usar como treino atual <ChevronRight size={16}/></>}</button>
                {actionTemplateId === template.id && actionMessage && <p data-testid="library-apply-inline-status" className={`library-action-message${actionMessage.includes("treino atual") ? " success" : " error"}`} role="status" aria-live="polite">{actionMessage}</p>}
              </div>}
            </article>)}
            {!visible.length && <div className="library-empty">Nenhuma sessão nesta combinação de filtros.</div>}
          </div>
          {actionMessage && <p className={`library-action-message${actionMessage.includes("treino atual") ? " success" : " error"}`} role="status">{actionMessage}</p>}
        </section>

        {active && <aside className="library-preview" data-testid="library-preview">
          <div className="library-preview-head"><div><p className="eyebrow">PRÉVIA DA SESSÃO</p><h3>{active.name}</h3></div><span>{active.total_sets} séries</span></div>
          <div className="library-exercise-list">
            {active.exercises.map((item, index) => <div key={`${item.exercise_id}-${index}`}>
              <span>0{index + 1}</span>
              <div><b>{exerciseIndex[item.exercise_id]?.name || item.exercise_id}</b><small>{item.sets} séries · {item.reps} reps · RIR {item.rir}</small></div>
              <em>{item.rest}</em>
            </div>)}
          </div>
          <button type="button" disabled={addingId === active.id || isApplied(active.id)} className={isSelected(active.id) || isApplied(active.id) ? "secondary-button" : "primary-button"} onClick={() => applyTemplate(active)}>
            {addingId === active.id ? "Adicionando…" : isApplied(active.id) ? "Esta é a sessão atual" : isSelected(active.id) ? "Remover da semana" : "Usar como treino atual"}<ChevronRight size={17}/>
          </button>
          {actionTemplateId === active.id && actionMessage && <p className={`library-action-message${actionMessage.includes("treino atual") ? " success" : " error"}`} role="status" aria-live="polite">{actionMessage}</p>}
        </aside>}
      </div>

      {selected.length > 0 && <section className="library-draft" data-testid="library-draft">
        <div className="library-draft-head"><div><p className="eyebrow">SUA SEMANA EM CONSTRUÇÃO</p><h3>{selected.length} {selected.length === 1 ? "sessão selecionada" : "sessões selecionadas"}</h3></div><button onClick={() => setSelected([])}>Limpar</button></div>
        <div className="library-draft-list">
          {selected.map((template, index) => <div key={template.id}>
            <span>D{index + 1}</span><b>{template.name}</b><small>{template.total_sets} séries · {template.duration} min</small>
            <div><button disabled={index === 0} onClick={() => moveSelected(index, -1)} aria-label={`Mover ${template.name} para trás`}>←</button><button disabled={index === selected.length - 1} onClick={() => moveSelected(index, 1)} aria-label={`Mover ${template.name} para frente`}>→</button><button onClick={() => toggleTemplate(template)} aria-label={`Remover ${template.name}`}><X size={14}/></button></div>
          </div>)}
        </div>
        <button className="primary-button library-build" data-testid="library-build-program" onClick={() => onBuild(buildLibraryProgram(selected))}>Revisar no Program Builder <ChevronRight size={18}/></button>
      </section>}
    </> : <>
      <div className="library-audience-filter" role="group" aria-label="Curadoria de programas">
        <span>Curadoria</span><button className={audience === "all" ? "active" : ""} onClick={() => setAudience("all")}>Todos</button><button className={audience === "female" ? "active" : ""} onClick={() => setAudience("female")}>Feminino</button><button className={audience === "unisex" ? "active" : ""} onClick={() => setAudience("unisex")}>Unissex</button>
      </div>
      <nav className="library-categories library-program-categories" aria-label="Divisões de programas">
        {catalog.program_categories.map(item => <button key={item.id} className={programCategory === item.id ? "active" : ""} onClick={() => chooseProgramCategory(item.id)} data-testid={`program-category-${item.id}`}>
          <b>{item.label}</b><span>{item.subtitle}</span>
        </button>)}
      </nav>

      <div className="library-layout library-program-layout">
        <section className="library-variants" aria-label="Programas disponíveis">
          <div className="library-section-head"><div><p className="eyebrow">PROGRAMAS COMPLETOS</p><h3>{catalog.program_categories.find(item => item.id === programCategory)?.label}</h3></div><span>{visiblePrograms.length} {visiblePrograms.length === 1 ? "programa" : "programas"} nesta divisão</span></div>
          <div className="program-card-grid">
            {visiblePrograms.map((item, index) => <article key={item.id} className={activeProgram?.id === item.id ? "active" : ""} onClick={() => chooseProgram(item)} data-testid={`training-program-${item.id}`}>
              <div className="library-card-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="library-card-top"><span>{item.category.toUpperCase()}</span><em>{item.level}</em></div>
              <h3>{item.name}</h3>
              <p>{item.description}</p>
              <div className="program-metrics"><span><strong>{item.days_per_week}</strong> dias</span><span><strong>{item.duration_weeks}</strong> semanas</span><span><strong>{item.phase_count}</strong> {item.phase_count === 1 ? "fase" : "fases"}</span></div>
              <div className="program-reference">Base técnica · {item.reference}</div>
              {item.safety !== "standard" && <div className="program-risk"><ShieldAlert size={14}/> {item.safety === "expert" ? "Recuperação excepcional" : "Volume avançado"}</div>}
              <button className="library-add">Ver programa <ChevronRight size={15}/></button>
            </article>)}
            {!visiblePrograms.length && <div className="library-empty">Nenhum programa desta classificação foi importado ainda.</div>}
          </div>
        </section>

        {activeProgram && activePhase && <aside className="library-preview program-preview" data-testid="program-preview">
          <div className="library-preview-head"><div><p className="eyebrow">PROGRAMA COMPLETO</p><h3>{activeProgram.name}</h3></div><span>{activeProgram.duration_weeks} semanas</span></div>
          <p className="program-preview-description">{activeProgram.description}</p>
          {activeProgram.phases.length > 1 && <div className="program-phases">
            <label>Escolha a fase</label>
            {activeProgram.phases.map(item => <button key={item.id} className={activePhase.id === item.id ? "active" : ""} onClick={() => setActivePhaseId(item.id)}>{item.label}<small>{item.weeks}</small></button>)}
          </div>}
          <div className="program-phase-meta"><span>{activePhase.method}</span><small>{activePhase.days_per_week} dias · {activePhase.total_sets} séries no microciclo</small></div>
          {activePhase.note && <p className="program-phase-note">{activePhase.note}</p>}
          {activeProgram.warning && <div className="program-warning"><ShieldAlert size={17}/><span><b>Atenção ao contexto</b>{activeProgram.warning}</span></div>}
          <div className="program-session-list">
            {activePhase.sessions.map((workout, dayIndex) => <details key={`${activePhase.id}-${workout.label}`} open={dayIndex === 0}>
              <summary><span>D{dayIndex + 1}</span><div><b>{workout.label}</b><small>{workout.exercise_count} exercícios · {workout.total_sets} séries · {workout.duration} min</small></div><ChevronRight size={16}/></summary>
              <div className="program-session-exercises">{workout.exercises.map((item, index) => <div key={`${item.exercise_id}-${index}`}><span>{String(index + 1).padStart(2, "0")}</span><div><b>{exerciseIndex[item.exercise_id]?.name || item.exercise_id}</b><small>{item.sets}× {item.reps} · RIR {item.rir}{item.technique_id !== "straight" ? ` · ${item.technique}` : ""}</small></div><em>{item.rest}</em></div>)}</div>
            </details>)}
          </div>
          {activeProgram.safety === "expert" && <label className="expert-confirm"><input type="checkbox" checked={expertAccepted} onChange={event => setExpertAccepted(event.target.checked)}/><span>Confirmo que este modelo será revisado para nível, recuperação e histórico antes de ser salvo.</span></label>}
          <button className="primary-button program-apply" disabled={activeProgram.safety === "expert" && !expertAccepted} onClick={() => onBuild(programPhaseToDraft(activeProgram, activePhase))} data-testid="apply-training-program">Revisar esta fase no Program Builder <ChevronRight size={17}/></button>
        </aside>}
      </div>
    </>}
  </div>;
}
