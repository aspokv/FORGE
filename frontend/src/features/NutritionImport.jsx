import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import {mensagemDeErro} from "./mensagemDeErro";
import {
  AlertTriangle, ChevronDown, ChevronRight, ClipboardPaste,
  Loader2, Plus, Save, Trash2, X, Zap,
} from "lucide-react";

const MAX_CHARS = 20000;

const EXAMPLE_TEXT = `CAFÉ DA MANHÃ
2 ovos inteiros
50g de aveia
200ml de leite desnatado

ALMOÇO
150g de arroz branco
Frango/peixe: 120 g
1 concha de feijão preto
Legumes: à vontade

LANCHE
Whey: 30 g
1 banana

SUBSTITUIÇÕES
200 g batata inglesa → 160 g batata-doce`;

const REVIEW_LABELS = {
  food_unmatched: "alimento fora do catálogo — registramos sua sugestão; escolha um equivalente",
  low_confidence_match: "correspondência incerta — confirme o alimento",
  ambiguous_match: "nome ambíguo — escolha o alimento certo",
  ai_suggested: "identificado automaticamente — confirme se é esse mesmo",
  quantity_missing: "quantidade não informada no texto",
  estimated_portion: "peso estimado a partir da medida caseira — confirme",
  free_portion: "“à vontade” no texto — contamos uma porção de referência; ajuste se quiser",
};

const round = n => Math.round(Number(n) || 0);

export default function NutritionImport({ API, onActivated, onClose }) {
  const [foods, setFoods] = useState([]);
  const [text, setText] = useState("");
  const [showExample, setShowExample] = useState(false);
  const [draft, setDraft] = useState(null);
  const [errors, setErrors] = useState([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [confirming, setConfirming] = useState(false);
  const activationToken = useRef(null);

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
    return () => { alive = false; };
  }, [API]);

  const parse = async () => {
    setMessage(""); setBusy("parse");
    try {
      const r = await axios.post(`${API}/nutrition/import/parse`, { text, name: "Dieta importada" });
      setDraft(r.data.draft);
      setErrors(r.data.blocking_errors || []);
    } catch (e) {
      setMessage(mensagemDeErro(e, "Não foi possível interpretar essa dieta."));
    } finally { setBusy(""); }
  };

  // Volta para a caixa de texto. O rascunho salvo sai tambem, senao ele voltaria na
  // proxima vez que a tela abrisse. O plano ativo nao e tocado.
  const pasteAgain = async () => {
    setBusy("discard");
    try { await axios.delete(`${API}/nutrition/import/draft`); } catch { /* a nova interpretacao sobrescreve */ }
    setDraft(null); setErrors([]); setMessage(""); setBusy("");
  };

  const patchItem = (mealIdx, itemIdx, patch) =>
    setDraft(d => ({
      ...d,
      meals: d.meals.map((m, i) => i !== mealIdx ? m : {
        ...m, items: m.items.map((it, j) => j === itemIdx ? { ...it, ...patch } : it),
      }),
    }));

  const escolherAlternativa = (mealIdx, itemIdx, foodId) =>
    setDraft(d => ({
      ...d,
      meals: d.meals.map((m, i) => i !== mealIdx ? m : {
        ...m, items: m.items.map((it, j) => j !== itemIdx ? it : {
          ...it, food_id: foodId,
          alternativas: [it.food_id, ...(it.alternativas || []).filter(a => a !== foodId)].filter(Boolean),
        }),
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
    if (!saved) return;
    if (saved.blocking_errors?.length) { setMessage("Revise os pontos marcados antes de ativar."); return; }
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
      setMessage(mensagemDeErro(e, "Não foi possível ativar a dieta."));
      setErrors(detail?.errors || []);
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
            <h2>Colar minha dieta</h2>
          </div>
          <button className="icon-button" data-testid="close-diet-import" onClick={onClose}><X size={20} /></button>
        </div>

        {!draft && (
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

        {draft && !confirming && (
          <div className="manual-preview" data-testid="diet-preview">
            {/* Sem este botao, um rascunho salvo prendia a tela na previa: a caixa de texto
                nunca voltava e nao havia onde colar outra dieta. */}
            <button type="button" className="secondary-button diet-paste-again" data-testid="diet-paste-again"
              disabled={!!busy} onClick={pasteAgain}>
              <ClipboardPaste size={15} /> Colar outra dieta
            </button>
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
                            a_vontade: false,
                          })} />
                      </label>
                      <button className="icon-button" data-testid={`diet-item-remove-${mealIdx}-${itemIdx}`}
                        onClick={() => removeItem(mealIdx, itemIdx)}><Trash2 size={14} /></button>
                    </div>

                    {item.raw_text && <p className="manual-raw">texto original: “{item.raw_text}”</p>}
                    {item.food_id && (item.alternativas || []).length > 0 && (
                      <div className="manual-suggestions" data-testid={`diet-alternatives-${mealIdx}-${itemIdx}`}>
                        <span className="manual-raw">ou, na mesma quantidade:</span>
                        {item.alternativas.map(fid => (
                          <button key={fid} type="button" className="manual-chip"
                            data-testid={`diet-alternative-${mealIdx}-${itemIdx}-${fid}`}
                            onClick={() => escolherAlternativa(mealIdx, itemIdx, fid)}>
                            {foodName(fid)}
                          </button>
                        ))}
                      </div>
                    )}
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

            {(draft.substituicoes || []).length > 0 && (
              <section className="manual-day" data-testid="diet-substitutions">
                <div className="manual-day-head"><strong>Trocas da sua dieta</strong></div>
                <ul className="diet-substitutions">
                  {draft.substituicoes.map((troca, k) => (
                    <li key={k}>
                      {troca.opcoes.map((op, n) => (
                        <span key={n} className={op.food_id ? "" : "diet-substitution-unknown"}>
                          {n > 0 && " ou "}
                          {op.grams ? `${round(op.grams)} g ` : ""}{op.food_id ? foodName(op.food_id) : op.raw_name}
                        </span>
                      ))}
                    </li>
                  ))}
                </ul>
                <p className="manual-raw">Ficam junto do plano, para consulta. Não entram na conta do dia.</p>
              </section>
            )}

            {(draft.warnings || []).length > 0 && (
              <ul className="manual-errors" data-testid="diet-warnings">
                {draft.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            )}

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

        {/* A periodizacao antiga (uma tabela que nenhuma tela lia) saiu daqui. A que
            aplica cada semana no plano fica em Nutricao > Meu plano. */}
      </motion.div>
    </div>
  );
}
