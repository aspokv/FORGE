import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import {
  AlertTriangle, ChevronDown, ChevronRight, ChevronUp, ClipboardPaste, Loader2, Plus,
  Save, Sliders, Trash2, X, Zap,
} from "lucide-react";

const REP_PRESETS = ["4–6", "6–8", "8–12", "10–15", "12–20"];
const RIR_PRESETS = ["0", "1", "1–2", "2", "2–3", "3"];
const REST_PRESETS = ["60 s", "90 s", "2 min", "3 min", "4 min"];
const MAX_CHARS = 20000;

const EXAMPLE_TEXT = `SEGUNDA — PUSH
Supino reto — 4x8-10 — 90s — RIR 2
Supino inclinado com halteres — 3x10
Elevação lateral — 4x12-15

TERÇA — PULL
Puxada aberta — 4x8-10
Remada curvada — 4x8
Rosca direta — 3x10`;

const REVIEW_LABELS = {
  exercise_unmatched: "exercício não reconhecido — escolha no catálogo",
  low_confidence_match: "correspondência incerta — confirme o exercício",
  multiple_options: "o texto ofereceu duas opções — escolha qual você faz",
  ambiguous_match: "nome ambíguo — escolha o exercício certo no catálogo",
  sets_missing: "séries não informadas no texto",
  reps_missing: "repetições não informadas no texto",
};

const move = (list, from, to) => {
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
};

export default function ManualWorkout({ API, profile, exercises, onActivated, onOpenBuilder, onClose }) {
  const [tab, setTab] = useState("import");
  const [text, setText] = useState("");
  const [showExample, setShowExample] = useState(false);
  const [draft, setDraft] = useState(null);
  const [errors, setErrors] = useState([]);
  const [replaces, setReplaces] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [confirming, setConfirming] = useState(false);
  const activationToken = useRef(null);

  const catalog = useMemo(() => exercises || [], [exercises]);
  const exerciseName = useCallback(
    id => catalog.find(e => e.id === id)?.name || id || "",
    [catalog],
  );

  // A draft already saved server-side survives a refresh — pick it back up on open.
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/workouts/manual/draft`)
      .then(r => {
        if (!alive || !r.data?.draft) return;
        setDraft(r.data.draft);
        setErrors(r.data.blocking_errors || []);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [API]);

  const parse = async () => {
    setMessage(""); setBusy("parse");
    try {
      const r = await axios.post(`${API}/workouts/manual/parse`, { text, name: "Treino importado" });
      setDraft(r.data.draft);
      setErrors(r.data.blocking_errors || []);
      if (r.data.draft?.warnings?.length) setMessage(r.data.draft.warnings.join(" · "));
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Não foi possível interpretar esse texto.");
    } finally {
      setBusy("");
    }
  };

  const patchDay = (dayIdx, patch) =>
    setDraft(d => ({ ...d, sessions: d.sessions.map((s, i) => (i === dayIdx ? { ...s, ...patch } : s)) }));

  const patchExercise = (dayIdx, exIdx, patch) =>
    patchDay(dayIdx, {
      exercises: draft.sessions[dayIdx].exercises.map((x, i) => (i === exIdx ? { ...x, ...patch } : x)),
    });

  const removeExercise = (dayIdx, exIdx) =>
    patchDay(dayIdx, { exercises: draft.sessions[dayIdx].exercises.filter((_, i) => i !== exIdx) });

  const moveExercise = (dayIdx, from, to) =>
    patchDay(dayIdx, { exercises: move(draft.sessions[dayIdx].exercises, from, to) });

  const addExercise = dayIdx =>
    patchDay(dayIdx, {
      exercises: [...draft.sessions[dayIdx].exercises, {
        exercise_id: catalog[0]?.id || null, raw_name: "", sets: 3, reps: "8–12", rir: "1–2",
        rest: "2 min", load: 0, technique: "Straight Sets", technique_id: "straight", note: "",
        needs_review: false, review_reasons: [], suggestions: [],
      }],
    });

  const moveDay = (from, to) => setDraft(d => ({ ...d, sessions: move(d.sessions, from, to) }));
  const removeDay = idx => setDraft(d => ({ ...d, sessions: d.sessions.filter((_, i) => i !== idx) }));
  const addDay = () => setDraft(d => ({
    ...d,
    sessions: [...d.sessions, { day: d.sessions.length + 1, label: `Sessão ${d.sessions.length + 1}`, demand: "MODERATE", focus: [], exercises: [] }],
  }));

  const saveDraft = async (silent = false) => {
    if (!draft) return null;
    if (!silent) setBusy("save");
    try {
      const r = await axios.put(`${API}/workouts/manual/draft`, { draft });
      setDraft(r.data.draft);
      setErrors(r.data.blocking_errors || []);
      if (!silent) setMessage("Rascunho salvo. Você pode voltar depois sem perder nada.");
      return r.data;
    } catch {
      setMessage("Não foi possível salvar o rascunho.");
      return null;
    } finally {
      if (!silent) setBusy("");
    }
  };

  const openConfirm = async () => {
    setMessage(""); setBusy("preview");
    const saved = await saveDraft(true);
    if (saved?.blocking_errors?.length) {
      setBusy("");
      setMessage("Revise os pontos marcados antes de ativar.");
      return;
    }
    try {
      const r = await axios.post(`${API}/workouts/manual/preview`, {});
      setReplaces(r.data.replaces);
      // One token per confirmation: a double click on "Ativar" reuses it and the
      // server applies the activation exactly once.
      activationToken.current = `act-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
      setConfirming(true);
    } catch {
      setMessage("Não foi possível montar a prévia.");
    } finally {
      setBusy("");
    }
  };

  const activate = async () => {
    setBusy("activate");
    try {
      const r = await axios.post(`${API}/workouts/manual/activate`, {
        activation_token: activationToken.current,
        session_minutes: profile?.session_minutes || 60,
      });
      onActivated(r.data);
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setConfirming(false);
      setMessage(detail?.message || detail || "Não foi possível ativar o treino.");
      setErrors(detail?.errors || []);
    } finally {
      setBusy("");
    }
  };

  const reviewCount = draft?.stats?.needs_review || 0;

  return (
    <div className="coach-overlay" data-testid="manual-workout-overlay">
      <motion.div className="builder-panel manual-panel" initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
        <div className="coach-header">
          <div>
            <p className="eyebrow">TREINO PRÓPRIO · MANUAL</p>
            <h2>Criar meu próprio treino</h2>
          </div>
          <button className="icon-button" data-testid="close-manual-button" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="manual-tabs">
          <button className={tab === "build" ? "manual-tab active" : "manual-tab"} data-testid="manual-tab-build" onClick={() => setTab("build")}>
            <Sliders size={15} /> Montar manualmente
          </button>
          <button className={tab === "import" ? "manual-tab active" : "manual-tab"} data-testid="manual-tab-import" onClick={() => setTab("import")}>
            <ClipboardPaste size={15} /> Colar treino pronto
          </button>
        </div>

        {tab === "build" && (
          <div className="manual-build" data-testid="manual-build-pane">
            <p className="muted">
              Monte a semana exercício por exercício no Program Builder Pro: criar e reordenar dias,
              adicionar exercícios do catálogo e definir séries, repetições, descanso, carga, RIR e observações.
            </p>
            <button className="primary-button" data-testid="open-builder-from-manual" onClick={onOpenBuilder}>
              Abrir o editor visual <ChevronRight size={16} />
            </button>
          </div>
        )}

        {tab === "import" && !draft && (
          <div className="manual-import" data-testid="manual-import-pane">
            <label className="deep-field">
              <span>Cole o treino completo</span>
              <textarea
                className="manual-textarea"
                data-testid="manual-import-textarea"
                value={text}
                maxLength={MAX_CHARS}
                rows={14}
                placeholder={"SEGUNDA — PUSH\nSupino reto — 4x8-10 — 90s — RIR 2\n..."}
                onChange={e => setText(e.target.value)}
              />
            </label>
            <div className="manual-import-meta">
              <button className="text-button" data-testid="manual-example-toggle" onClick={() => setShowExample(v => !v)}>
                {showExample ? <ChevronDown size={13} /> : <ChevronRight size={13} />} ver um exemplo
              </button>
              <span className={text.length > MAX_CHARS - 500 ? "manual-counter warn" : "manual-counter"} data-testid="manual-char-counter">
                {text.length} / {MAX_CHARS}
              </span>
            </div>
            {showExample && <pre className="manual-example" data-testid="manual-example">{EXAMPLE_TEXT}</pre>}
            {message && <p className="builder-error" data-testid="manual-error">{message}</p>}
            <button className="primary-button" data-testid="manual-parse-button" onClick={parse} disabled={!text.trim() || busy === "parse"}>
              {busy === "parse" ? <><Loader2 size={16} className="spin" /> Interpretando...</> : <>Interpretar treino <ChevronRight size={16} /></>}
            </button>
          </div>
        )}

        {tab === "import" && draft && !confirming && (
          <div className="manual-preview" data-testid="manual-preview">
            <div className="manual-summary">
              <p><b>{draft.stats?.days}</b> dias · <b>{draft.stats?.exercises}</b> exercícios</p>
              {reviewCount > 0
                ? <p className="manual-review-warning" data-testid="manual-review-count"><AlertTriangle size={14} /> {reviewCount} item(ns) precisam da sua confirmação</p>
                : <p className="muted">Tudo reconhecido. Revise e ative quando quiser.</p>}
            </div>

            <label className="deep-field">
              <span>Nome do treino</span>
              <input data-testid="manual-plan-name" value={draft.name || ""} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} />
            </label>

            {draft.sessions.map((day, dayIdx) => (
              <section className="manual-day" key={dayIdx} data-testid={`manual-day-${dayIdx}`}>
                <div className="manual-day-head">
                  <input
                    className="manual-day-label"
                    data-testid={`manual-day-label-${dayIdx}`}
                    value={day.label}
                    onChange={e => patchDay(dayIdx, { label: e.target.value })}
                  />
                  <div className="manual-day-actions">
                    <button className="icon-button" data-testid={`manual-day-up-${dayIdx}`} disabled={dayIdx === 0} onClick={() => moveDay(dayIdx, dayIdx - 1)}><ChevronUp size={15} /></button>
                    <button className="icon-button" data-testid={`manual-day-down-${dayIdx}`} disabled={dayIdx === draft.sessions.length - 1} onClick={() => moveDay(dayIdx, dayIdx + 1)}><ChevronDown size={15} /></button>
                    <button className="icon-button" data-testid={`manual-day-remove-${dayIdx}`} disabled={draft.sessions.length <= 1} onClick={() => removeDay(dayIdx)}><Trash2 size={15} /></button>
                  </div>
                </div>

                {day.exercises.map((x, exIdx) => (
                  <div className={x.needs_review ? "manual-exercise review" : "manual-exercise"} key={exIdx} data-testid={`manual-exercise-${dayIdx}-${exIdx}`}>
                    <div className="manual-exercise-head">
                      <span className="exercise-index">{String(exIdx + 1).padStart(2, "0")}</span>
                      <select
                        data-testid={`manual-exercise-select-${dayIdx}-${exIdx}`}
                        value={x.exercise_id || ""}
                        onChange={e => patchExercise(dayIdx, exIdx, { exercise_id: e.target.value || null })}
                      >
                        <option value="">— escolher exercício —</option>
                        {catalog.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                      </select>
                      <div className="manual-day-actions">
                        <button className="icon-button" data-testid={`manual-ex-up-${dayIdx}-${exIdx}`} disabled={exIdx === 0} onClick={() => moveExercise(dayIdx, exIdx, exIdx - 1)}><ChevronUp size={14} /></button>
                        <button className="icon-button" data-testid={`manual-ex-down-${dayIdx}-${exIdx}`} disabled={exIdx === day.exercises.length - 1} onClick={() => moveExercise(dayIdx, exIdx, exIdx + 1)}><ChevronDown size={14} /></button>
                        <button className="icon-button" data-testid={`manual-ex-remove-${dayIdx}-${exIdx}`} onClick={() => removeExercise(dayIdx, exIdx)}><Trash2 size={14} /></button>
                      </div>
                    </div>

                    {x.raw_name && x.raw_name !== exerciseName(x.exercise_id) && (
                      <p className="manual-raw" data-testid={`manual-raw-${dayIdx}-${exIdx}`}>texto original: “{x.raw_name}”</p>
                    )}
                    {x.needs_review && (
                      <p className="manual-review-warning">
                        <AlertTriangle size={13} /> {(x.review_reasons || []).map(r => REVIEW_LABELS[r] || r).join(" · ")}
                      </p>
                    )}
                    {!x.exercise_id && (x.suggestions || []).length > 0 && (
                      <div className="manual-suggestions" data-testid={`manual-suggestions-${dayIdx}-${exIdx}`}>
                        {x.suggestions.map(sid => (
                          <button key={sid} className="manual-chip"
                            data-testid={`manual-suggestion-${dayIdx}-${exIdx}-${sid}`}
                            onClick={() => patchExercise(dayIdx, exIdx, { exercise_id: sid })}>
                            {exerciseName(sid)}
                          </button>
                        ))}
                      </div>
                    )}

                    <div className="builder-exercise-grid">
                      <label className="deep-field">
                        <span>Séries</span>
                        <input type="number" min="1" max="12" data-testid={`manual-sets-${dayIdx}-${exIdx}`}
                          value={x.sets ?? ""} placeholder="—"
                          onChange={e => patchExercise(dayIdx, exIdx, { sets: e.target.value === "" ? null : Number(e.target.value) })} />
                      </label>
                      <label className="deep-field">
                        <span>Reps</span>
                        <input list="manual-rep-presets" data-testid={`manual-reps-${dayIdx}-${exIdx}`}
                          value={x.reps || ""} placeholder="—"
                          onChange={e => patchExercise(dayIdx, exIdx, { reps: e.target.value })} />
                      </label>
                      <label className="deep-field">
                        <span>RIR</span>
                        <input list="manual-rir-presets" data-testid={`manual-rir-${dayIdx}-${exIdx}`}
                          value={x.rir || ""} onChange={e => patchExercise(dayIdx, exIdx, { rir: e.target.value })} />
                      </label>
                      <label className="deep-field">
                        <span>Descanso</span>
                        <input list="manual-rest-presets" data-testid={`manual-rest-${dayIdx}-${exIdx}`}
                          value={x.rest || ""} onChange={e => patchExercise(dayIdx, exIdx, { rest: e.target.value })} />
                      </label>
                      <label className="deep-field">
                        <span>Carga (kg)</span>
                        <input type="number" step="0.5" data-testid={`manual-load-${dayIdx}-${exIdx}`}
                          value={x.load || 0} onChange={e => patchExercise(dayIdx, exIdx, { load: Number(e.target.value) || 0 })} />
                      </label>
                    </div>

                    <label className="deep-field">
                      <span>Observação</span>
                      <input data-testid={`manual-note-${dayIdx}-${exIdx}`} value={x.note || ""}
                        placeholder="Ex.: drop-set na última série"
                        onChange={e => patchExercise(dayIdx, exIdx, { note: e.target.value })} />
                    </label>
                  </div>
                ))}

                <button className="secondary-button" data-testid={`manual-add-exercise-${dayIdx}`} onClick={() => addExercise(dayIdx)}>
                  <Plus size={15} /> Adicionar exercício
                </button>
              </section>
            ))}

            <button className="secondary-button" data-testid="manual-add-day" onClick={addDay}>
              <Plus size={15} /> Adicionar dia
            </button>

            {errors.length > 0 && (
              <ul className="manual-errors" data-testid="manual-blocking-errors">
                {errors.slice(0, 8).map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
            {message && <p className="builder-error" data-testid="manual-message">{message}</p>}

            <div className="builder-actions">
              <button className="secondary-button" data-testid="manual-save-draft" onClick={() => saveDraft(false)} disabled={!!busy}>
                <Save size={15} /> {busy === "save" ? "Salvando..." : "Salvar como rascunho"}
              </button>
              <button className="primary-button" data-testid="manual-activate-button" onClick={openConfirm} disabled={!!busy}>
                <Zap size={16} /> {busy === "preview" ? "Preparando..." : "Ativar este treino"}
              </button>
            </div>
          </div>
        )}

        {confirming && (
          <div className="manual-confirm" data-testid="manual-confirm">
            <h3>Substituir o treino ativo?</h3>
            <p className="muted">
              Programa atual: <b>{replaces?.name}</b> · {replaces?.days} dia(s)
              {replaces?.manual ? " (manual)" : " (motor automático)"}.
            </p>
            <p>
              Ele será arquivado e continua recuperável. Seu histórico de treinos concluídos,
              cargas e evolução <b>não</b> é apagado. O próximo treino passa a ser o
              primeiro dia de <b>{draft?.name}</b>.
            </p>
            <div className="builder-actions">
              <button className="secondary-button" data-testid="manual-cancel-activation" onClick={() => setConfirming(false)} disabled={busy === "activate"}>
                Cancelar
              </button>
              <button className="primary-button" data-testid="manual-confirm-activation" onClick={activate} disabled={busy === "activate"}>
                {busy === "activate" ? <><Loader2 size={16} className="spin" /> Ativando...</> : <>Confirmar e ativar <ChevronRight size={16} /></>}
              </button>
            </div>
          </div>
        )}

        <datalist id="manual-rep-presets">{REP_PRESETS.map(r => <option key={r} value={r} />)}</datalist>
        <datalist id="manual-rir-presets">{RIR_PRESETS.map(r => <option key={r} value={r} />)}</datalist>
        <datalist id="manual-rest-presets">{REST_PRESETS.map(r => <option key={r} value={r} />)}</datalist>
      </motion.div>
    </div>
  );
}
