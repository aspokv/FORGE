import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Check, ChevronRight, Dumbbell, Layers3, Plus, Timer, X } from "lucide-react";
import "./workout-library.css";

export const templateToSession = (template, day) => ({
  day,
  label: template.name,
  demand: template.demand || "MODERATE",
  focus: [...(template.focus || [])],
  exercises: (template.exercises || []).map(exercise => ({ ...exercise })),
  template_id: template.id,
});

export const buildLibraryProgram = templates => ({
  name: "Programa FORGE selecionado",
  week: "Microciclo da biblioteca",
  session_minutes: templates.length ? Math.round(templates.reduce((sum, item) => sum + Number(item.duration || 60), 0) / templates.length) : 60,
  sessions: templates.map((template, index) => templateToSession(template, index + 1)),
});

export default function WorkoutLibrary({ API, exercises = [], onBuild, onClose }) {
  const [catalog, setCatalog] = useState({ categories: [], templates: [] });
  const [category, setCategory] = useState("push");
  const [active, setActive] = useState(null);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    axios.get(`${API}/workout-templates`).then(response => {
      if (!alive) return;
      setCatalog(response.data);
      setActive(response.data.templates?.[0] || null);
    }).catch(() => {
      if (alive) setError("Não foi possível carregar a biblioteca agora.");
    }).finally(() => {
      if (alive) setLoading(false);
    });
    return () => { alive = false; };
  }, [API]);

  const exerciseIndex = useMemo(() => Object.fromEntries(exercises.map(item => [item.id, item])), [exercises]);
  const visible = useMemo(() => catalog.templates.filter(item => item.category === category), [catalog.templates, category]);
  const isSelected = id => selected.some(item => item.id === id);
  const chooseCategory = id => {
    setCategory(id);
    setActive(catalog.templates.find(item => item.category === id) || null);
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

  if (loading) return <div className="content workout-library"><div className="library-loading">Preparando os modelos FORGE...</div></div>;
  if (error) return <div className="content workout-library"><div className="library-error">{error}</div></div>;

  return <div className="content workout-library" data-testid="workout-library">
    <section className="library-intro">
      <div>
        <p className="eyebrow">FORGE / BIBLIOTECA DE SESSÕES</p>
        <h2>Escolha a arquitetura do seu treino.</h2>
        <p className="muted">Três versões profissionais de cada padrão. Selecione as sessões, organize a semana e revise tudo antes de ativar.</p>
      </div>
      <div className="library-intro-actions">
        <div className="library-count"><strong>{catalog.templates.length}</strong><span>modelos<br/>curados</span></div>
        {onClose && <button className="icon-button" onClick={onClose} aria-label="Fechar biblioteca"><X size={19}/></button>}
      </div>
    </section>

    <nav className="library-categories" aria-label="Categorias de treino">
      {catalog.categories.map(item => <button key={item.id} className={category === item.id ? "active" : ""} onClick={() => chooseCategory(item.id)} data-testid={`library-category-${item.id}`}>
        <b>{item.label}</b><span>{item.subtitle}</span>
      </button>)}
    </nav>

    <div className="library-layout">
      <section className="library-variants" aria-label="Variações disponíveis">
        <div className="library-section-head"><div><p className="eyebrow">03 VARIAÇÕES</p><h3>{catalog.categories.find(item => item.id === category)?.label}</h3></div><span>Escolha pelo objetivo da sessão</span></div>
        <div className="library-card-grid">
          {visible.map((template, index) => <article key={template.id} className={`${active?.id === template.id ? "active " : ""}${isSelected(template.id) ? "selected" : ""}`} data-testid={`workout-template-${template.id}`} onClick={() => setActive(template)}>
            <div className="library-card-index">0{index + 1}</div>
            <div className="library-card-top"><span>{template.style}</span><em>{template.level}</em></div>
            <h3>{template.name}</h3>
            <p>{template.description}</p>
            <div className="library-card-stats"><span><Dumbbell size={14}/>{template.exercise_count} exercícios</span><span><Layers3 size={14}/>{template.total_sets} séries</span><span><Timer size={14}/>{template.duration} min</span></div>
            <div className="library-focus">{template.focus.map(item => <span key={item}>{item}</span>)}</div>
            <button className={isSelected(template.id) ? "library-add selected" : "library-add"} onClick={event => { event.stopPropagation(); toggleTemplate(template); }}>
              {isSelected(template.id) ? <><Check size={16}/> Adicionado</> : <><Plus size={16}/> Adicionar à semana</>}
            </button>
          </article>)}
        </div>
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
        <button className={isSelected(active.id) ? "secondary-button" : "primary-button"} onClick={() => toggleTemplate(active)}>
          {isSelected(active.id) ? "Remover da semana" : "Usar esta sessão"}<ChevronRight size={17}/>
        </button>
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
  </div>;
}
