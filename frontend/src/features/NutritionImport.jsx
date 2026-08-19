import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import {
  AlertTriangle, CalendarRange, ChevronDown, ChevronRight, ClipboardPaste,
  Loader2, Plus, Save, Trash2, X, Zap,
} from "lucide-react";

const MAX_CHARS = 20000;

const EXAMPLE_TEXT = `CAFÉ DA MANHÃ
2 ovos inteiros
50g de aveia
200ml de leite desnatado

ALMOÇO
150g de arroz branco
120g de peito de frango
1 concha de feijão preto
salada de alface e tomate

LANCHE
1 scoop de whey
1 banana`;

const REVIEW_LABELS = {
  food_unmatched: "alimento fora do catálogo — registramos sua sugestão; escolha um equivalente",
  low_confidence_match: "correspondência incerta — confirme o alimento",
  ambiguous_match: "nome ambíguo — escolha o alimento certo",
  ai_suggested: "identificado automaticamente — confirme se é esse mesmo",
  quantity_missing: "quantidade não informada no texto",
  estimated_portion: "peso estimado a partir da medida caseira — confirme",
};

const round = n => Math.round(Number(n) || 0);

export default function NutritionImport({ API, onActivated, onClose }) {
  const [foods, setFoods] = useState([]);
  const [tab, setTab] = useState("import");
  const [text, setText] = useState("");
  const [showExample, setShowExample] = useState(false);
  const [draft, setDraft] = useState(null);
  const [errors, setErrors] = useState([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [confirming, setConfirming] = useState(false);
  const activationToken = useRef(null);

  // periodização
  const [mode, setMode] = useState("kcal");
  const [targetKcal, setTargetKcal] = useState("");
  const [pct, setPct] = useState("-15");
  const [weeks, setWeeks] = useState(8);
  const [table, setTable] = useState(null);
  const [periodMeta, setPeriodMeta] = useState(null);

  const catalog = useMemo(() => foods || [], [foods]);
  const foodName = useCallback(id => catalog.find(f => f.id === id)?.name || id || "", [catalog]);

  useEffect(() => {
    let alive = true;
    axios.get(`${API}/nutrition/import/draft`)
      .then(r => { if (alive && r.data?.draft) { setDraft(r.data.draft); setErrors(r.data.blocking_errors || []); } })
      .catch(() => {});
    axios.get(`${API}/nutrition/foods`)
      .then(r => { if (alive) setFoods(r.data?.foods || []); })
      .catch(() => {});
    axios.get(`${API}/nutrition/periodization`)
      .then(r => { if (alive && r.data?.periodization) { setTable(r.data.periodization.table); setPeriodMeta(r.data.periodization); } })
      .catch(() => {});
    return () => { alive = false; };
  }, [API]);

  const parse = async () => {
    setMessage(""); setBusy("parse");
    try {
      const r = await axios.post(`${API}/nutrition/import/parse`, { text, name: "Dieta importada" });
      setDraft(r.data.draft);
      setErrors(r.data.blocking_errors || []);
      if (r.data.draft?.warnings?.length) setMessage(r.data.draft.warnings.join(" · "));
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Não foi possível interpretar essa dieta.");
    } finally { setBusy(""); }
  };

  const patchItem = (mealIdx, itemIdx, patch) =>
    setDraft(d => ({
      ...d,
      meals: d.meals.map((m, i) => i !== mealIdx ? m : {
        ...m, items: m.items.map((it, j) => j === itemIdx ? { ...it, ...patch } : it),
      }),
    }));

  const removeItem = (mealIdx, itemIdx) =>
    setDraft(d => ({
      ...d,
      meals: d.meals.map((m, i) => i !== mealIdx ? m : { ...m, items: m.items.filter((_, j) => j !== itemIdx) }),
    }));

  const addItem = mealIdx =>
    setDraft(d => ({
      ...d,
      meals: d.meals.map((m, i) => i !== mealIdx ? m : {
        ...m, items: [...m.items, { food_id: catalog[0]?.id || null, raw_name: "", grams: 100, estimated: false, needs_review: false, review_reasons: [] }],
      }),
    }));

  const patchMeal = (mealIdx, patch) =>
    setDraft(d => ({ ...d, meals: d.meals.map((m, i) => i === mealIdx ? { ...m, ...patch } : m) }));

  const removeMeal = mealIdx =>
    setDraft(d => ({ ...d, meals: d.meals.filter((_, i) => i !== mealIdx) }));

  const saveDraft = async (silent = false) => {
    if (!draft) return null;
    if (!silent) setBusy("save");
    try {
      const r = await axios.put(`${API}/nutrition/import/draft`, { draft });
      setDraft(r.data.draft);
      setErrors(r.data.blocking_errors || []);
      if (!silent) setMessage("Rascunho salvo.");
      return r.data;
    } catch {
      setMessage("Não foi possível salvar o rascunho.");
      return null;
    } finally { if (!silent) setBusy(""); }
  };

  const openConfirm = async () => {
    setMessage(""); setBusy("check");
    const saved = await saveDraft(true);
    setBusy("");
    if (saved?.blocking_errors?.length) { setMessage("Revise os pontos marcados antes de ativar."); return; }
    activationToken.current = `diet-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
    setConfirming(true);
  };

  const activate = async () => {
    setBusy("activate");
    try {
      const r = await axios.post(`${API}/nutrition/import/activate`, {
        activation_token: activationToken.current,
      });
      onActivated(r.data);
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setConfirming(false);
      setMessage(detail?.message || detail || "Não foi possível ativar a dieta.");
      setErrors(detail?.errors || []);
    } finally { setBusy(""); }
  };

  const generateTable = async () => {
    setMessage(""); setBusy("period");
    try {
      const body = { weeks: Number(weeks) };
      if (mode === "kcal") body.target_kcal = Number(targetKcal);
      else body.pct = Number(pct);
      const r = await axios.post(`${API}/nutrition/periodization/preview`, body);
      setTable(r.data.table);
      setPeriodMeta(r.data);
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Não foi possível gerar a periodização.");
    } finally { setBusy(""); }
  };

  const patchWeek = (idx, patch) =>
    setTable(t => t.map((w, i) => i === idx ? { ...w, ...patch } : w));

  const savePeriodization = async () => {
    setBusy("period-save");
    try {
      const r = await axios.post(`${API}/nutrition/periodization/save`, {
        table, weeks: table.length,
        target_kcal: periodMeta?.target_kcal ?? null,
      });
      setTable(r.data.periodization.table);
      setMessage("Periodização salva.");
    } catch (e) {
      setMessage(e?.response?.data?.detail || "Não foi possível salvar a periodização.");
    } finally { setBusy(""); }
  };

  const totals = draft?.daily_totals || {};
  const reviewCount = draft?.stats?.needs_review || 0;

  return (
    <div className="coach-overlay" data-testid="nutrition-import-overlay">
      <motion.div className="builder-panel manual-panel" initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }}>
        <div className="coach-header">
          <div>
            <p className="eyebrow">DIETA PRÓPRIA · MANUAL</p>
            <h2>Colar dieta e periodizar</h2>
          </div>
          <button className="icon-button" data-testid="close-diet-import" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="manual-tabs">
          <button className={tab === "import" ? "manual-tab active" : "manual-tab"} data-testid="diet-tab-import" onClick={() => setTab("import")}>
            <ClipboardPaste size={15} /> Colar dieta
          </button>
          <button className={tab === "period" ? "manual-tab active" : "manual-tab"} data-testid="diet-tab-period" onClick={() => setTab("period")}>
            <CalendarRange size={15} /> Periodização
          </button>
        </div>

        {tab === "import" && !draft && (
          <div className="manual-import" data-testid="diet-import-pane">
            <label className="deep-field">
              <span>Cole a dieta completa</span>
              <textarea className="manual-textarea" data-testid="diet-textarea" rows={14}
                value={text} maxLength={MAX_CHARS}
                placeholder={"CAFÉ DA MANHÃ\n2 ovos\n50g de aveia\n..."}
                onChange={e => setText(e.target.value)} />
            </label>
            <div className="manual-import-meta">
              <button className="text-button" data-testid="diet-example-toggle" onClick={() => setShowExample(v => !v)}>
                {showExample ? <ChevronDown size={13} /> : <ChevronRight size={13} />} ver um exemplo
              </button>
              <span className={text.length > MAX_CHARS - 500 ? "manual-counter warn" : "manual-counter"} data-testid="diet-char-counter">
                {text.length} / {MAX_CHARS}
              </span>
            </div>
            {showExample && <pre className="manual-example">{EXAMPLE_TEXT}</pre>}
            {message && <p className="builder-error" data-testid="diet-error">{message}</p>}
            <button className="primary-button" data-testid="diet-parse-button" onClick={parse} disabled={!text.trim() || busy === "parse"}>
              {busy === "parse" ? <><Loader2 size={16} className="spin" /> Interpretando...</> : <>Interpretar dieta <ChevronRight size={16} /></>}
            </button>
          </div>
        )}

        {tab === "import" && draft && !confirming && (
          <div className="manual-preview" data-testid="diet-preview">
            <div className="macro-strip diet-totals" data-testid="diet-totals">
              <div><span>Calorias</span><b>{round(totals.kcal)}<small>kcal</small></b></div>
              <div><span>Proteína</span><b>{round(totals.protein_g)}<small>g</small></b></div>
              <div><span>Carbo</span><b>{round(totals.carbs_g)}<small>g</small></b></div>
              <div><span>Gordura</span><b>{round(totals.fat_g)}<small>g</small></b></div>
            </div>

            {reviewCount > 0 && (
              <p className="manual-review-warning" data-testid="diet-review-count">
                <AlertTriangle size={14} /> {reviewCount} item(ns) precisam da sua confirmação
              </p>
            )}

            {draft.meals.map((meal, mealIdx) => (
              <section className="manual-day" key={mealIdx} data-testid={`diet-meal-${mealIdx}`}>
                <div className="manual-day-head">
                  <input className="manual-day-label" data-testid={`diet-meal-name-${mealIdx}`}
                    value={meal.name} onChange={e => patchMeal(mealIdx, { name: e.target.value })} />
                  <span className="diet-meal-kcal">{round(meal.totals?.kcal)} kcal</span>
                  <div className="manual-day-actions">
                    <button className="icon-button" data-testid={`diet-meal-remove-${mealIdx}`}
                      disabled={draft.meals.length <= 1} onClick={() => removeMeal(mealIdx)}><Trash2 size={15} /></button>
                  </div>
                </div>

                {meal.items.map((item, itemIdx) => (
                  <div className={item.needs_review ? "manual-exercise review" : "manual-exercise"}
                    key={itemIdx} data-testid={`diet-item-${mealIdx}-${itemIdx}`}>
                    <div className="manual-exercise-head">
                      <select data-testid={`diet-food-select-${mealIdx}-${itemIdx}`}
                        value={item.food_id || ""}
                        onChange={e => patchItem(mealIdx, itemIdx, { food_id: e.target.value || null })}>
                        <option value="">— escolher alimento —</option>
                        {catalog.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                      </select>
                      <label className="deep-field diet-grams">
                        <span>Gramas</span>
                        <input type="number" min="0" max="3000" data-testid={`diet-grams-${mealIdx}-${itemIdx}`}
                          value={item.grams ?? ""} placeholder="—"
                          onChange={e => patchItem(mealIdx, itemIdx, {
                            grams: e.target.value === "" ? null : Number(e.target.value), estimated: false,
                          })} />
                      </label>
                      <button className="icon-button" data-testid={`diet-item-remove-${mealIdx}-${itemIdx}`}
                        onClick={() => removeItem(mealIdx, itemIdx)}><Trash2 size={14} /></button>
                    </div>

                    {item.raw_text && <p className="manual-raw">texto original: “{item.raw_text}”</p>}
                    {item.macros && (
                      <p className="diet-item-macros" data-testid={`diet-item-macros-${mealIdx}-${itemIdx}`}>
                        {round(item.macros.kcal)} kcal · P {item.macros.protein_g}g · C {item.macros.carbs_g}g · G {item.macros.fat_g}g
                      </p>
                    )}
                    {item.needs_review && (
                      <p className="manual-review-warning">
                        <AlertTriangle size={13} /> {(item.review_reasons || []).map(r => REVIEW_LABELS[r] || r).join(" · ")}
                      </p>
                    )}
                    {!item.food_id && (item.suggestions || []).length > 0 && (
                      <div className="manual-suggestions">
                        {item.suggestions.map(fid => (
                          <button key={fid} className="manual-chip"
                            data-testid={`diet-suggestion-${mealIdx}-${itemIdx}-${fid}`}
                            onClick={() => patchItem(mealIdx, itemIdx, { food_id: fid })}>
                            {foodName(fid)}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                <button className="secondary-button" data-testid={`diet-add-item-${mealIdx}`} onClick={() => addItem(mealIdx)}>
                  <Plus size={15} /> Adicionar alimento
                </button>
              </section>
            ))}

            {errors.length > 0 && (
              <ul className="manual-errors" data-testid="diet-blocking-errors">
                {errors.slice(0, 8).map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
            {message && <p className="builder-error" data-testid="diet-message">{message}</p>}

            <div className="builder-actions">
              <button className="secondary-button" data-testid="diet-save-draft" onClick={() => saveDraft(false)} disabled={!!busy}>
                <Save size={15} /> {busy === "save" ? "Salvando..." : "Salvar como rascunho"}
              </button>
              <button className="primary-button" data-testid="diet-activate-button" onClick={openConfirm} disabled={!!busy}>
                <Zap size={16} /> Ativar esta dieta
              </button>
            </div>
          </div>
        )}

        {confirming && (
          <div className="manual-confirm" data-testid="diet-confirm">
            <h3>Substituir o plano alimentar ativo?</h3>
            <p className="muted">
              A dieta importada passa a ser seu plano base: <b>{round(totals.kcal)} kcal</b> ·
              P {round(totals.protein_g)}g · C {round(totals.carbs_g)}g · G {round(totals.fat_g)}g.
            </p>
            <p>
              O plano anterior é arquivado e continua recuperável. Seu histórico de peso e
              de aderência <b>não</b> é apagado.
            </p>
            <div className="builder-actions">
              <button className="secondary-button" data-testid="diet-cancel-activation" onClick={() => setConfirming(false)} disabled={busy === "activate"}>
                Cancelar
              </button>
              <button className="primary-button" data-testid="diet-confirm-activation" onClick={activate} disabled={busy === "activate"}>
                {busy === "activate" ? <><Loader2 size={16} className="spin" /> Ativando...</> : <>Confirmar e ativar <ChevronRight size={16} /></>}
              </button>
            </div>
          </div>
        )}

        {tab === "period" && (
          <div className="manual-preview" data-testid="diet-period-pane">
            <p className="muted">
              A partir do seu plano ativo, gera uma progressão semanal até a meta calórica.
              A proteína fica fixa; a gordura respeita o piso de segurança e o que sobra vai
              para o carboidrato.
            </p>

            <div className="period-form">
              <label className="deep-field">
                <span>Meta por</span>
                <select data-testid="period-mode" value={mode} onChange={e => setMode(e.target.value)}>
                  <option value="kcal">Calorias finais</option>
                  <option value="pct">Porcentagem</option>
                </select>
              </label>
              {mode === "kcal" ? (
                <label className="deep-field">
                  <span>Kcal finais</span>
                  <input type="number" data-testid="period-target-kcal" value={targetKcal}
                    placeholder="2200" onChange={e => setTargetKcal(e.target.value)} />
                </label>
              ) : (
                <label className="deep-field">
                  <span>Ajuste (%)</span>
                  <input type="number" data-testid="period-pct" value={pct}
                    onChange={e => setPct(e.target.value)} />
                </label>
              )}
              <label className="deep-field">
                <span>Semanas</span>
                <input type="number" min="1" max="52" data-testid="period-weeks" value={weeks}
                  onChange={e => setWeeks(e.target.value)} />
              </label>
              <button className="primary-button" data-testid="period-generate" onClick={generateTable} disabled={busy === "period"}>
                {busy === "period" ? <><Loader2 size={15} className="spin" /> Gerando...</> : "Gerar tabela"}
              </button>
            </div>

            {message && <p className="builder-error" data-testid="period-message">{message}</p>}

            {table && (
              <>
                {periodMeta?.fat_floor_g != null && (
                  <p className="muted period-floor">
                    Piso de gordura: <b>{periodMeta.fat_floor_g} g/dia</b>
                    {periodMeta.weight_kg ? ` (0,8 g/kg · ${periodMeta.weight_kg} kg)` : ""}.
                  </p>
                )}
                <div className="period-table-wrap">
                  <table className="period-table" data-testid="period-table">
                    <thead>
                      <tr><th>Semana</th><th>Kcal</th><th>Proteína</th><th>Carbo</th><th>Gordura</th></tr>
                    </thead>
                    <tbody>
                      {table.map((w, i) => (
                        <tr key={i} className={w.feasible ? "" : "infeasible"} data-testid={`period-week-${w.week}`}>
                          <td>{w.week}</td>
                          <td><b>{w.kcal}</b></td>
                          <td><input type="number" data-testid={`period-protein-${w.week}`} value={w.protein_g}
                            onChange={e => patchWeek(i, { protein_g: Number(e.target.value) })} /></td>
                          <td><input type="number" data-testid={`period-carbs-${w.week}`} value={w.carbs_g}
                            onChange={e => patchWeek(i, { carbs_g: Number(e.target.value) })} /></td>
                          <td><input type="number" data-testid={`period-fat-${w.week}`} value={w.fat_g}
                            onChange={e => patchWeek(i, { fat_g: Number(e.target.value) })} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {table.some(w => w.warnings?.length) && (
                  <ul className="manual-errors" data-testid="period-warnings">
                    {table.filter(w => w.warnings?.length).map(w => (
                      <li key={w.week}>Semana {w.week}: {w.warnings.join(" ")}</li>
                    ))}
                  </ul>
                )}

                <div className="builder-actions">
                  <button className="primary-button" data-testid="period-save" onClick={savePeriodization} disabled={!!busy}>
                    <Save size={15} /> {busy === "period-save" ? "Salvando..." : "Salvar periodização"}
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
