import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight, Plus, Trash2, X, Save, RotateCcw, Info, GripVertical } from "lucide-react";
import axios from "axios";
import { TECHNIQUE_FALLBACK, findTechnique } from "./techniques";

const REP_PRESETS = ["4–6", "6–8", "8–12", "10–15", "12–20"];
const RIR_PRESETS = ["0", "1", "1–2", "2", "2–3", "3"];
const REST_PRESETS = ["60 s", "90 s", "2 min", "3 min", "4 min"];
const DEMAND = ["HIGH", "MODERATE", "LOW"];

const cloneSessions = (sessions = []) => sessions.map(s => ({
  day: s.day,
  label: s.label || `Sessão ${s.day}`,
  demand: s.demand || "MODERATE",
  focus: [...(s.focus || [])],
  exercises: (s.exercises || []).map(x => ({
    exercise_id: x.exercise_id,
    sets: Number(x.sets) || 3,
    reps: x.reps || "8–12",
    rir: x.rir || "1–2",
    rest: x.rest || "2 min",
    load: Number(x.load) || 0,
    technique: x.technique || "Straight Sets",
    technique_id: x.technique_id || "straight",
    note: x.note || "",
  })),
}));

export default function ProgramBuilder({ API, profile, exercises, techniques, program, onSaved, onClose }) {
  const [name, setName] = useState(program?.name || "Programa personalizado");
  const [duration, setDuration] = useState(profile?.session_minutes || 60);
  const [sessions, setSessions] = useState(() => {
    const base = cloneSessions(program?.sessions);
    return base.length ? base : [{ day: 1, label: "Sessão 1", demand: "MODERATE", focus: [], exercises: [] }];
  });
  const [activeDay, setActiveDay] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dragEx, setDragEx] = useState(null);
  const [dragDay, setDragDay] = useState(null);
  const [techniqueDetail, setTechniqueDetail] = useState(null);

  const catalog = useMemo(() => (techniques && techniques.length ? techniques : TECHNIQUE_FALLBACK), [techniques]);
  const exerciseList = useMemo(() => exercises || [], [exercises]);

  const updateDay = (idx, patch) => setSessions(list => list.map((s, i) => (i === idx ? { ...s, ...patch } : s)));

  const addDay = () => {
    setSessions(list => {
      const next = [...list, { day: list.length + 1, label: `Sessão ${list.length + 1}`, demand: "MODERATE", focus: [], exercises: [] }];
      setActiveDay(next.length - 1);
      return next;
    });
  };

  const removeDay = idx => {
    setSessions(list => {
      if (list.length <= 1) return list;
      const next = list.filter((_, i) => i !== idx).map((s, i) => ({ ...s, day: i + 1, label: s.label.startsWith("Sessão ") ? `Sessão ${i + 1}` : s.label }));
      setActiveDay(Math.min(activeDay, next.length - 1));
      return next;
    });
  };

  const addExercise = () => {
    if (!exerciseList.length) return;
    updateDay(activeDay, {
      exercises: [
        ...sessions[activeDay].exercises,
        { exercise_id: exerciseList[0].id, sets: 3, reps: "8–12", rir: "1–2", rest: "2 min", load: 0, technique: "Straight Sets", technique_id: "straight", note: "" },
      ],
    });
  };

  const updateExercise = (exIdx, patch) => {
    const list = [...sessions[activeDay].exercises];
    list[exIdx] = { ...list[exIdx], ...patch };
    updateDay(activeDay, { exercises: list });
  };

  const removeExercise = exIdx => {
    updateDay(activeDay, { exercises: sessions[activeDay].exercises.filter((_, i) => i !== exIdx) });
  };

  const moveExercise = (from, to) => {
    if (from === to || from < 0 || to < 0) return;
    const list = [...sessions[activeDay].exercises];
    if (from >= list.length || to >= list.length) return;
    const [item] = list.splice(from, 1);
    list.splice(to, 0, item);
    updateDay(activeDay, { exercises: list });
  };

  const applyTechnique = (exIdx, techId) => {
    const t = findTechnique(catalog, techId);
    updateExercise(exIdx, { technique_id: t.id, technique: t.name });
  };

  const save = async () => {
    setError("");
    const empty = sessions.find(s => !s.exercises.length);
    if (empty) { setError(`A ${empty.label} está sem exercícios.`); return; }
    setSaving(true);
    try {
      const payload = {
        profile_id: profile.id,
        name: name.trim() || "Programa personalizado",
        week: "Microciclo manual",
        session_minutes: Number(duration) || 60,
        sessions,
      };
      const r = await axios.post(`${API}/custom-program`, payload);
      onSaved(r.data);
    } catch (e) {
      setError("Não foi possível salvar. Tente novamente.");
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    setSaving(true);
    try {
      const r = await axios.delete(`${API}/custom-program/${profile.id}`);
      onSaved(r.data);
    } catch {
      setError("Falha ao restaurar o motor automático.");
    } finally {
      setSaving(false);
    }
  };

  const day = sessions[activeDay];

  return (
    <div className="coach-overlay" data-testid="program-builder-overlay">
      <motion.div className="builder-panel" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}>
        <div className="coach-header">
          <div>
            <p className="eyebrow">PROGRAM BUILDER PRO · MANUAL</p>
            <h2>Construa a sua semana</h2>
          </div>
          <button className="icon-button" data-testid="close-builder-button" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="builder-meta">
          <label className="deep-field">
            <span>Nome do programa</span>
            <input data-testid="builder-name" value={name} onChange={e => setName(e.target.value)} />
          </label>
          <label className="deep-field">
            <span>Duração média (min)</span>
            <input data-testid="builder-duration" type="number" value={duration} onChange={e => setDuration(e.target.value)} />
          </label>
        </div>

        <div className="builder-days">
          <div className="builder-day-tabs">
            {sessions.map((s, i) => (
              <button key={i} className={i === activeDay ? "day-tab active" : i === dragDay ? "day-tab dragging" : "day-tab"} data-testid={`builder-day-${i + 1}`} draggable onClick={() => setActiveDay(i)} onDragStart={e => { e.dataTransfer.setData("text/plain", `day-${i}`); e.dataTransfer.effectAllowed = "move"; setDragDay(i); }} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDragEnd={() => setDragDay(null)} onDrop={e => { e.preventDefault(); const raw = e.dataTransfer.getData("text/plain"); if (raw.startsWith("day-")) { const from = parseInt(raw.split("-")[1], 10); if (from !== i && !isNaN(from)) { const list = [...sessions]; const [item] = list.splice(from, 1); list.splice(i, 0, item); setSessions(list.map((s, idx) => ({ ...s, day: idx + 1, label: s.label.startsWith("Sess\u00e3o ") ? `Sess\u00e3o ${idx + 1}` : s.label }))); setActiveDay(from < i ? i - 1 : i); } } setDragDay(null); }}>
                <b>D{i + 1}</b>
                <span>{s.label}</span>
              </button>
            ))}
            {sessions.length < 10 && (
              <button className="day-tab add" data-testid="add-day-button" onClick={addDay}>
                <Plus size={16} /> dia
              </button>
            )}
          </div>

          <div className="builder-day-body">
            <div className="builder-day-header">
              <label className="deep-field grow">
                <span>Nome da sessão</span>
                <input data-testid="builder-day-label" value={day.label} onChange={e => updateDay(activeDay, { label: e.target.value })} />
              </label>
              <label className="deep-field">
                <span>Demanda</span>
                <select data-testid="builder-day-demand" value={day.demand} onChange={e => updateDay(activeDay, { demand: e.target.value })}>
                  {DEMAND.map(d => <option key={d}>{d}</option>)}
                </select>
              </label>
              {sessions.length > 1 && (
                <button className="ghost-button" data-testid="remove-day-button" onClick={() => removeDay(activeDay)}>
                  <Trash2 size={15} /> remover dia
                </button>
              )}
            </div>

            <div className="builder-exercises">
              {day.exercises.length === 0 && (
                <p className="muted builder-empty">Sem exercícios ainda. Adicione o primeiro para começar.</p>
              )}
              {day.exercises.map((x, i) => {
                const ex = exerciseList.find(e => e.id === x.exercise_id) || { name: x.exercise_id };
                const tech = findTechnique(catalog, x.technique_id, x.technique);
                return (
                  <div className={dragEx === i ? "builder-exercise dragging" : "builder-exercise"} key={i} draggable onDragStart={e => { e.dataTransfer.setData("text/plain", i); e.dataTransfer.effectAllowed = "move"; setDragEx(i); }} onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDragEnd={() => setDragEx(null)} onDrop={e => { e.preventDefault(); const from = parseInt(e.dataTransfer.getData("text/plain"), 10); if (from !== i && !isNaN(from)) moveExercise(from, i); setDragEx(null); }}>
                    <div className="builder-exercise-head">
                      <GripVertical size={16} className="grip" />
                      <span className="exercise-index">0{i + 1}</span>
                      <select data-testid={`builder-exercise-${i}`} value={x.exercise_id} onChange={e => updateExercise(i, { exercise_id: e.target.value })}>
                        {exerciseList.map(e => <option key={e.id} value={e.id}>{e.name} · {e.muscle}</option>)}
                      </select>
                      <button className="ghost-button" data-testid={`builder-remove-exercise-${i}`} onClick={() => removeExercise(i)}>
                        <Trash2 size={14} />
                      </button>
                    </div>

                    <div className="builder-exercise-grid">
                      <label className="deep-field">
                        <span>Séries</span>
                        <input data-testid={`builder-sets-${i}`} type="number" min="1" max="8" value={x.sets} onChange={e => updateExercise(i, { sets: Number(e.target.value) || 1 })} />
                      </label>
                      <label className="deep-field">
                        <span>Reps</span>
                        <select data-testid={`builder-reps-${i}`} value={x.reps} onChange={e => updateExercise(i, { reps: e.target.value })}>
                          {REP_PRESETS.map(r => <option key={r}>{r}</option>)}
                        </select>
                      </label>
                      <label className="deep-field">
                        <span>RIR</span>
                        <select data-testid={`builder-rir-${i}`} value={x.rir} onChange={e => updateExercise(i, { rir: e.target.value })}>
                          {RIR_PRESETS.map(r => <option key={r}>{r}</option>)}
                        </select>
                      </label>
                      <label className="deep-field">
                        <span>Descanso</span>
                        <select data-testid={`builder-rest-${i}`} value={x.rest} onChange={e => updateExercise(i, { rest: e.target.value })}>
                          {REST_PRESETS.map(r => <option key={r}>{r}</option>)}
                        </select>
                      </label>
                      <label className="deep-field">
                        <span>Carga (kg)</span>
                        <input data-testid={`builder-load-${i}`} type="number" step="0.5" value={x.load} onChange={e => updateExercise(i, { load: Number(e.target.value) || 0 })} />
                      </label>
                    </div>

                    <div className="builder-technique">
                      <label className="deep-field grow">
                        <span>Técnica avançada</span>
                        <select data-testid={`builder-technique-${i}`} value={x.technique_id} onChange={e => applyTechnique(i, e.target.value)}>
                          {catalog.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                        </select>
                      </label>
                      <button className="ghost-button" data-testid={`technique-info-${i}`} onClick={() => setTechniqueDetail(tech)}>
                        <Info size={14} /> como executar
                      </button>
                    </div>
                    <p className="muted technique-hint">{tech.short} · fadiga {tech.fatigue}</p>

                    <label className="deep-field">
                      <span>Observação técnica</span>
                      <input data-testid={`builder-note-${i}`} value={x.note} placeholder="Ex.: cadência 2-0-2, foco no alongamento" onChange={e => updateExercise(i, { note: e.target.value })} />
                    </label>
                  </div>
                );
              })}
              <button className="secondary-button" data-testid="add-exercise-button" onClick={addExercise}>
                <Plus size={16} /> Adicionar exercício
              </button>
            </div>
          </div>
        </div>

        {error && <p className="builder-error" data-testid="builder-error">{error}</p>}

        <div className="builder-actions">
          <button className="secondary-button" data-testid="reset-program-button" onClick={reset} disabled={saving}>
            <RotateCcw size={15} /> Voltar ao motor automático
          </button>
          <button className="primary-button" data-testid="save-program-button" onClick={save} disabled={saving}>
            <Save size={16} /> {saving ? "Salvando..." : "Salvar programa"} <ChevronRight size={16} />
          </button>
        </div>

        {techniqueDetail && (
          <div className="technique-modal" data-testid="technique-detail">
            <div className="coach-panel technique-card">
              <div className="coach-header">
                <div>
                  <p className="eyebrow">TÉCNICA · {techniqueDetail.name.toUpperCase()}</p>
                  <h2>{techniqueDetail.short}</h2>
                </div>
                <button className="icon-button" data-testid="close-technique-detail" onClick={() => setTechniqueDetail(null)}><X size={20} /></button>
              </div>
              <p className="muted">Fadiga estimada: {techniqueDetail.fatigue}</p>
              <p className="technique-block"><b>Como funciona.</b> {techniqueDetail.description}</p>
              <p className="technique-block"><b>Protocolo.</b> {techniqueDetail.protocol}</p>
              <p className="technique-block"><b>Quando usar.</b> {techniqueDetail.when}</p>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
