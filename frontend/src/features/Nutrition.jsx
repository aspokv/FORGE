import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { ChevronRight, RefreshCw, Check, X, Utensils, ClipboardPaste } from "lucide-react";
import NutritionImport from "./NutritionImport";

// Humanized display for naturally-countable foods (eggs, whites): the backend computes
// display_quantity/display_unit from the real grams (e.g. "3 ovos"); grams stay the
// source of truth for every calorie/macro calculation, this only changes what's shown.
function formatQty(item) {
  if (item?.display_quantity != null && item?.display_unit) {
    const qty = item.display_quantity;
    const qtyStr = Number.isInteger(qty) ? String(qty) : qty.toFixed(1).replace(/\.0$/, "");
    return `${qtyStr} ${item.display_unit}`;
  }
  return `${item?.grams ?? 0}g`;
}

export default function Nutrition({ API, profileId, db }) {
  const [step, setStep] = useState("loading");
  const [plan, setPlan] = useState(null);
  const [targets, setTargets] = useState(null);
  const [form, setForm] = useState({
    weight_kg: "", height_cm: "", age: "", sex: "male",
    goal: "maintenance", intensity: "", activity_level: "moderate", training_days: 3,
    meal_count: 4, training_time: "", preferred_foods: [], disliked_foods: [],
    avoid_foods: [], allergies: [], dietary_restrictions: "", cooking_time: "medium"
  });
  const [genStep, setGenStep] = useState(1);
  // Catalogo das intensidades servido pelo backend: rotulo, descricao, aviso e faixa de
  // carbo saem da metodologia, nao de texto repetido aqui.
  const [intensities, setIntensities] = useState([]);
  const [importOpen, setImportOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [mealStatus, setMealStatus] = useState({});
  const [subResult, setSubResult] = useState(null);

  // Guided flow ("Refazer plano"): meal-by-meal composition — the athlete picks a real
  // combination the coach already vetted, instead of the engine deciding everything at
  // once. See backend /plan/draft/* — the confirmed plan this produces is byte-for-byte
  // the same shape the legacy generate() flow produces, so the rest of this component
  // (plan view, Substituir, meal-status) needs no changes at all.
  const [guidedDraft, setGuidedDraft] = useState(null);
  const [guidedIdx, setGuidedIdx] = useState(0);
  const [guidedOptions, setGuidedOptions] = useState([]);
  const [guidedLoadingOptions, setGuidedLoadingOptions] = useState(false);
  const [guidedSwap, setGuidedSwap] = useState(null);
  const [guidedPhase, setGuidedPhase] = useState("choosing");

  // O questionario salvo reabre preenchido — inclusive com o objetivo e a intensidade
  // escolhidos no onboarding, que gravam no MESMO nutrition_assessment. Sem isto a tela
  // reabria em branco e a escolha do onboarding parecia ter sido ignorada.
  useEffect(() => {
    axios.get(`${API}/nutrition/assessment`).then(r => {
      const na = r.data?.assessment;
      if (!na) return;
      setForm(f => ({
        ...f,
        ...Object.fromEntries(Object.entries(na).filter(([k, v]) =>
          k in f && v !== null && v !== undefined && v !== "")),
        // o formulario usa texto/select simples onde o backend guarda lista
        dietary_restrictions: (na.dietary_restrictions || [])[0] || "",
        allergies: Array.isArray(na.allergies) ? na.allergies.join(", ") : (na.allergies || ""),
      }));
    }).catch(() => {});
  }, [API]);

  useEffect(() => {
    axios.get(`${API}/nutrition/plan`).then(r => {
      setPlan(r.data); setTargets(r.data.targets || r.data.daily_totals); setStep("plan");
      axios.get(`${API}/nutrition/adherence/${new Date().toISOString().slice(0,10)}`).then(r2 => {
        const m = {}; r2.data.meals.forEach(x => m[x.meal_index] = x.status);
        setMealStatus(m);
      }).catch(() => {});
    }).catch(() => {
      axios.get(`${API}/nutrition/assessment`).catch(() => setStep("assessment")).finally(() => {
        if (step === "loading") setStep("assessment");
      });
    });
  }, []);

  useEffect(() => {
    let vivo = true;
    axios.get(`${API}/nutrition/cutting-intensities`)
      .then(r => { if (vivo) setIntensities(r.data.options || []); })
      .catch(() => {});
    return () => { vivo = false; };
  }, [API]);

  const submitAssessment = async () => {
    setBusy(true); setError("");
    try {
      await axios.post(`${API}/nutrition/assessment`, {
        ...form,
        weight_kg: Number(form.weight_kg), height_cm: Number(form.height_cm),
        age: Number(form.age), training_days: Number(form.training_days),
        meal_count: Number(form.meal_count),
        // backend expects lists: the restriction select yields a single string, and the
        // allergies field is free text meant to be split on commas.
        dietary_restrictions: form.dietary_restrictions ? [form.dietary_restrictions] : [],
        allergies: typeof form.allergies === "string"
          ? form.allergies.split(",").map(s => s.trim()).filter(Boolean)
          : (form.allergies || [])
      });
      const r = await axios.post(`${API}/nutrition/generate`);
      setPlan(r.data.plan); setTargets(r.data.targets); setStep("plan");
    } catch (e) {
      // FastAPI validation errors (422) return detail as an array of error objects,
      // not a string — rendering that array directly crashes React.
      const detail = e.response?.data?.detail;
      const message = typeof detail === "string" ? detail
        : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join("; ")
        // limites do protocolo: o backend recusa o plano em vez de salvar fora da faixa
        : detail?.message ? [detail.message, ...(detail.errors || [])].join(" ")
        : "Erro ao salvar";
      setError(message);
    } finally { setBusy(false); }
  };

  const sumDraftMacros = (draft) => {
    let kcal = 0, protein_g = 0, carbs_g = 0, fat_g = 0;
    (draft?.meals || []).forEach(m => (m.foods || []).forEach(it => {
      const f = it.food || {}; const fac = it.grams / (f.grams || 100);
      kcal += (f.kcal || 0) * fac; protein_g += (f.protein_g || 0) * fac;
      carbs_g += (f.carbs_g || 0) * fac; fat_g += (f.fat_g || 0) * fac;
    }));
    return { kcal, protein_g, carbs_g, fat_g };
  };

  const nextUnlockedIndex = (draft) => draft.locked.findIndex(l => !l);

  const loadMealOptions = async (idx, seed) => {
    setGuidedLoadingOptions(true); setGuidedSwap(null);
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/options`, {
        meal_index: idx, ...(seed != null ? { variety_seed: seed } : {}),
      });
      setGuidedOptions(r.data.options || []);
    } catch (e) { setError("Não foi possível carregar opções para esta refeição."); }
    finally { setGuidedLoadingOptions(false); }
  };

  /**
   * Preserva o motivo REAL no console e devolve texto util para a tela.
   * Um catch generico escondia, por exemplo, "faca o questionario primeiro" atras de
   * "Nao foi possivel refazer o plano agora." — o usuario nao tinha como saber o que
   * fazer, e o plano antigo continuava na tela.
   */
  const explicarErro = (e, contexto, fallback) => {
    const status = e?.response?.status;
    const detail = e?.response?.data?.detail;
    console.error(`[FORGE nutrition] ${contexto} falhou (HTTP ${status ?? "?"}):`, detail ?? e);
    if (typeof detail === "string" && detail) return detail;
    if (detail?.message) return [detail.message, ...(detail.errors || [])].join(" ");
    return fallback;
  };

  /** Volta para o questionario em vez de deixar o usuario preso na tela do plano. */
  const pedirQuestionario = (mensagem) => {
    setGuidedDraft(null); setGenStep(1); setStep("assessment"); setError(mensagem);
  };

  // "Refazer plano": only replaces the plan itself — assessment, peso, histórico,
  // alergias e restrições continuam intactos (o backend nem toca nessas coleções).
  const refazerPlano = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/reset`);
      setGuidedDraft(r.data); setGuidedIdx(0); setGuidedPhase("choosing"); setStep("guided");
      await loadMealOptions(0);
    } catch (e) {
      const motivo = explicarErro(e, "refazer plano", "Não foi possível refazer o plano agora.");
      // 400 aqui significa questionario ausente ou incompleto. O plano antigo continua
      // na tela e a tela do plano nunca oferece o questionario, entao sem este desvio o
      // usuario ficaria sem saida nenhuma.
      if (e?.response?.status === 400) {
        pedirQuestionario("Precisamos atualizar seu questionário alimentar antes de refazer o plano.");
      } else {
        setError(motivo);
      }
    }
    finally { setBusy(false); }
  };

  const outrasOpcoes = () => loadMealOptions(guidedIdx, Math.floor(Math.random() * 1000));

  const escolherOpcao = async (option) => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/choose`, {
        meal_index: guidedIdx, archetype_id: option.archetype_id,
        food_ids: option.foods.map(f => f.food_id),
      });
      const draft = r.data;
      setGuidedDraft(draft);
      const next = nextUnlockedIndex(draft);
      if (next === -1) { setGuidedPhase("review"); }
      else { setGuidedIdx(next); await loadMealOptions(next); }
    } catch (e) { setError("Não foi possível escolher esta combinação agora."); }
    finally { setBusy(false); }
  };

  // FORGE_CHOOSES_FOR_ME — for this one meal, or for every meal still unlocked.
  const forgeEscolheEsta = () => { if (guidedOptions.length) escolherOpcao(guidedOptions[0]); };

  const forgeEscolheResto = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/choose-remaining`);
      setGuidedDraft(r.data); setGuidedPhase("review");
    } catch (e) { setError("Não foi possível concluir automaticamente agora."); }
    finally { setBusy(false); }
  };

  // Trocar um alimento dentro da combinação sugerida: a estrutura escolhida permanece,
  // só esse componente muda, e as porções da combinação inteira são recalculadas.
  const abrirSwapNaOpcao = async (optIdx, foodId) => {
    if (guidedSwap?.optIdx === optIdx && guidedSwap?.foodId === foodId) { setGuidedSwap(null); return; }
    const option = guidedOptions[optIdx];
    setGuidedSwap({ optIdx, foodId, options: [], loading: true });
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/swap-food`, {
        meal_index: guidedIdx, food_ids: option.foods.map(f => f.food_id), food_id: foodId,
      });
      setGuidedSwap({ optIdx, foodId, options: r.data.options || [] });
    } catch (e) { setGuidedSwap(null); setError("Substituição indisponível agora."); }
  };

  const aplicarSwapNaOpcao = async (optIdx, foodId, subId) => {
    const option = guidedOptions[optIdx];
    setBusy(true);
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/swap-food`, {
        meal_index: guidedIdx, food_ids: option.foods.map(f => f.food_id),
        food_id: foodId, substitute_food_id: subId,
      });
      setGuidedOptions(opts => opts.map((o, i) => i === optIdx ? { ...o, foods: r.data.foods } : o));
      setGuidedSwap(null);
    } catch (e) { setError("Não foi possível aplicar a troca agora."); }
    finally { setBusy(false); }
  };

  const confirmarPlanoGuiado = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/nutrition/plan/draft/confirm`);
      setPlan(r.data.plan); setTargets(r.data.targets);
      setGuidedDraft(null); setStep("plan");
    } catch (e) { setError(explicarErro(e, "confirmar plano", "Não foi possível confirmar o plano agora.")); }
    finally { setBusy(false); }
  };

  const markMeal = async (idx, status) => {
    try {
      await axios.post(`${API}/nutrition/meal-status`, { meal_index: idx, status });
      setMealStatus(s => ({ ...s, [idx]: status }));
    } catch { setError("Não foi possível registrar a refeição."); }
  };

  const doSubstitute = async (mealIdx, foodId) => {
    setBusy(true); setError("");
    setSubResult(subResult?.mealIdx === mealIdx && subResult?.foodId === foodId ? null : { mealIdx, foodId, options: [], loading: true });
    if (subResult?.mealIdx === mealIdx && subResult?.foodId === foodId) { setBusy(false); return; }
    try {
      const r = await axios.post(`${API}/nutrition/substitute`, { meal_index: mealIdx, food_id: foodId });
      setSubResult({ mealIdx, foodId, options: r.data.options || [], original: r.data.original_macros });
    } catch (e) {
      // Falha tecnica NAO pode virar "nenhuma substituicao disponivel": sao coisas
      // diferentes e exigem acoes diferentes do usuario.
      setSubResult({ mealIdx, foodId, options: [], falhou: explicarErro(e, "buscar substitutos", "Não foi possível carregar as opções agora.") });
    }
    finally { setBusy(false); }
  };

  const applySub = async (mi, oid, sid) => {
    setBusy(true); setError("");
    try {
      // Backend re-validates and persists the substitution; it returns the updated plan
      // as the source of truth — the frontend never computes macros/equivalence itself.
      const r = await axios.post(`${API}/nutrition/substitute`, { meal_index: mi, food_id: oid, substitute_food_id: sid });
      setPlan(r.data.plan);
      setSubResult(null);
    } catch (e) {
      setError("Não foi possível aplicar a substituição agora.");
    } finally { setBusy(false); }
  };

  const formRef = useRef(form);
  formRef.current = form;
  const F = useMemo(() => ({ label, k, type = "text", opts }) => (
    <label className="deep-field">
      <span>{label}</span>
      {opts ? <select value={formRef.current[k]} onChange={e => setForm(s => ({ ...s, [k]: e.target.value }))}>
        {opts.map(o => <option key={o.v ?? o} value={o.v ?? o}>{o.l ?? o.v ?? o}</option>)}
      </select> : <input type={type} inputMode={type === "number" ? "decimal" : undefined} value={formRef.current[k]} onChange={e => setForm(s => ({ ...s, [k]: e.target.value }))} />}
    </label>
  ), []);

  if (step === "loading") return (
    <div className="content">
      <div className="skeleton-block" style={{ height: 88 }} />
      <div className="skeleton-grid">
        <div className="skeleton-block" /><div className="skeleton-block" />
      </div>
      <div className="skeleton-block" style={{ height: 160, marginTop: 16 }} />
    </div>
  );

  if (step === "assessment") {
    return (
      <div className="content">
        <div className="onboarding deep-scene" style={{ maxWidth: 760 }}>
          <p className="eyebrow">NUTRIÇÃO / AVALIAÇÃO</p>
          <h2>Conhecer sua alimentação</h2>
          <p className="muted">Etapa {genStep} de 5</p>
          <div className="onboard-progress" style={{ margin: "10px 0 20px" }}><b style={{ width: `${genStep / 5 * 100}%` }} /></div>

          {genStep === 1 && <>
            <div className="field-grid">
              <F label="Peso (kg)" k="weight_kg" type="number" />
              <F label="Altura (cm)" k="height_cm" type="number" />
              <F label="Idade" k="age" type="number" />
              <F label="Sexo" k="sex" opts={[{ v: "male", l: "Masculino" }, { v: "female", l: "Feminino" }]} />
            </div>
            <F label="Objetivo" k="goal" opts={[
              { v: "fat_loss", l: "Perda de gordura" },
              { v: "maintenance", l: "Manutenção" },
              { v: "muscle_gain", l: "Ganho de massa" }
            ]} />
            {form.goal === "fat_loss" && intensities.length > 0 && (
              <div className="intensity-block">
                <p className="eyebrow">INTENSIDADE DO EMAGRECIMENTO</p>
                <div className="intensity-cards">
                  {intensities.map(op => (
                    <button
                      key={op.id}
                      type="button"
                      data-testid={`intensity-${op.id}`}
                      aria-pressed={form.intensity === op.id}
                      className={`intensity-card${form.intensity === op.id ? " active" : ""}${op.advanced ? " advanced" : ""}`}
                      onClick={() => setForm(s2 => ({ ...s2, intensity: op.id }))}
                    >
                      <span className="intensity-head">
                        <b>{op.label}</b>
                        {op.recommended && <em className="intensity-tag">recomendado</em>}
                        {op.advanced && <em className="intensity-tag adv">avançado</em>}
                      </span>
                      <small>{op.description}</small>
                      <span className="intensity-meta">
                        {`-${op.deficit_pct}% do gasto`}
                        {op.carb_range_g ? ` · ${op.carb_range_g[0]}–${op.carb_range_g[1]}g de carboidrato/dia` : ""}
                      </span>
                    </button>
                  ))}
                </div>
                {intensities.find(o => o.id === form.intensity)?.warning && (
                  <p className="intensity-warning" data-testid="intensity-warning">
                    {intensities.find(o => o.id === form.intensity).warning}
                  </p>
                )}
              </div>
            )}
          </>}
          {genStep === 2 && <>
            <F label="Nível de atividade" k="activity_level" opts={[
              { v: "sedentary", l: "Sedentário" }, { v: "light", l: "Leve" },
              { v: "moderate", l: "Moderado" }, { v: "active", l: "Ativo" }, { v: "very_active", l: "Muito ativo" }
            ]} />
            <F label="Dias de treino" k="training_days" type="number" />
            <F label="Horário de treino" k="training_time" opts={[
              { v: "", l: "Sem horário fixo" }, { v: "morning", l: "Manhã" },
              { v: "afternoon", l: "Tarde" }, { v: "evening", l: "Noite" }
            ]} />
          </>}
          {genStep === 3 && <>
            <F label="Tempo para cozinhar" k="cooking_time" opts={[
              { v: "low", l: "Pouco" }, { v: "medium", l: "Médio" }, { v: "high", l: "Bastante" }
            ]} />
            <F label="Número de refeições" k="meal_count" opts={[{v:3},{v:4},{v:5},{v:6}]} />
          </>}
          {genStep === 4 && <>
            <p className="muted">Preferências alimentares (opcional)</p>
            <F label="Alergias (separar por vírgula)" k="allergies" />
            <F label="Restrições" k="dietary_restrictions" opts={[
              { v: "", l: "Nenhuma" }, { v: "vegetarian", l: "Vegetariano" },
              { v: "lactose_free", l: "Sem lactose" }, { v: "gluten_free", l: "Sem glúten" }
            ]} />
          </>}
          {genStep === 5 && <div className="review-summary">
            <div><b>{form.weight_kg || "?"}</b><span>kg</span></div>
            <div><b>{form.goal === "fat_loss" ? "Déficit" : form.goal === "muscle_gain" ? "Superávit" : "Manutenção"}</b><span>objetivo</span></div>
            <div><b>{form.meal_count}</b><span>refeições</span></div>
          </div>}

          {error && <div className="auth-error">{error}</div>}
          <div className="deep-actions" style={{ marginTop: 24 }}>
            {genStep > 1 && <button className="secondary-button" onClick={() => setGenStep(s => s - 1)}>Voltar</button>}
            {genStep < 5 ? <button className="primary-button" onClick={() => setGenStep(s => s + 1)}>Continuar <ChevronRight size={18} /></button>
              : <button className="primary-button" onClick={submitAssessment} disabled={busy}>
                {busy ? "Gerando..." : "Gerar plano"} <ChevronRight size={18} />
              </button>}
          </div>
        </div>
      </div>
    );
  }

  if (step === "guided" && guidedPhase === "review") {
    const sums = sumDraftMacros(guidedDraft);
    return (
      <div className="content">
        <div className="onboarding deep-scene" style={{ maxWidth: 760 }}>
          <p className="eyebrow">REFAZER PLANO / REVISÃO</p>
          <h2>Confira sua estratégia de hoje</h2>
          <div className="review-summary">
            <div><b>{Math.round(sums.kcal)}</b><span>kcal</span></div>
            <div><b>{Math.round(sums.protein_g)}g</b><span>proteína</span></div>
            <div><b>{guidedDraft.meals.length}</b><span>refeições</span></div>
          </div>
          <div className="notice" style={{ marginTop: 16 }}>
            <b>✓ Porções dentro dos limites confortáveis do coach</b>
            <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
              Cada combinação veio pré-validada pelo motor nutricional: nenhuma porção passa do limite
              seguro, e alergias/restrições já foram respeitadas antes de qualquer opção chegar até você.
            </p>
          </div>
          {guidedDraft.meals.map((m, i) => {
            const mealKcal = (m.foods || []).reduce((s, f) => s + (f.food?.kcal || 0) * f.grams / (f.food?.grams || 100), 0);
            return (
            <section className="meal-card" key={i} style={{ marginTop: 12 }}>
              <div className="meal-head">
                <div><p className="eyebrow">{m.name}</p><h3>{Math.round(mealKcal)} kcal</h3></div>
              </div>
              <div className="food-list">
                {(m.foods || []).map((it, j) => (
                  <div className="food-row" key={j}>
                    <div className="food-row-main">
                      <div className="food-row-info">
                        <b>{it.food?.name || it.food_id}</b>
                        <span className="muted">{formatQty(it)} · {Math.round(it.food?.kcal || 0)} kcal</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
            );
          })}
          {error && <div className="auth-error" style={{ marginTop: 14 }}>{error}</div>}
          <div className="deep-actions" style={{ marginTop: 24 }}>
            <button className="secondary-button" onClick={() => setStep("plan")} disabled={busy}>Cancelar</button>
            <button className="primary-button" onClick={confirmarPlanoGuiado} disabled={busy}>
              {busy ? "Confirmando..." : "Confirmar plano"} <Check size={18} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === "guided") {
    const meal = guidedDraft?.meals?.[guidedIdx];
    const totalMeals = guidedDraft?.meals?.length || 0;
    const lockedCount = guidedDraft?.locked?.filter(Boolean).length || 0;
    return (
      <div className="content">
        <div className="onboarding deep-scene" style={{ maxWidth: 760 }}>
          <p className="eyebrow">REFAZER PLANO</p>
          <h2>{meal?.name}</h2>
          <p className="muted">Refeição {guidedIdx + 1} de {totalMeals} · {lockedCount} já escolhidas</p>
          <div className="onboard-progress" style={{ margin: "10px 0 20px" }}>
            <b style={{ width: `${totalMeals ? (lockedCount / totalMeals) * 100 : 0}%` }} />
          </div>

          {guidedLoadingOptions ? (
            <p className="muted">Buscando combinações...</p>
          ) : guidedOptions.map((opt, i) => {
            const optKcal = opt.foods.reduce((s, f) => s + (f.food?.kcal || 0) * f.grams / (f.food?.grams || 100), 0);
            return (
              <section className="meal-card" key={opt.archetype_id} style={{ marginBottom: 12 }}>
                <div className="meal-head">
                  <div><p className="eyebrow">{opt.label}</p><h3>{Math.round(optKcal)} kcal</h3></div>
                </div>
                <div className="food-list">
                  {opt.foods.map((it, j) => {
                    const swapOpen = guidedSwap?.optIdx === i && guidedSwap?.foodId === it.food_id;
                    return (
                      <div className="food-row" key={j}>
                        <div className="food-row-main">
                          <div className="food-row-info">
                            <b>{it.food?.name || it.food_id}</b>
                            <span className="muted">{formatQty(it)} · {Math.round(it.food?.kcal || 0)} kcal</span>
                          </div>
                          <button className="food-sub-btn" onClick={() => abrirSwapNaOpcao(i, it.food_id)}>
                            <RefreshCw size={13} /> Trocar
                          </button>
                        </div>
                        {swapOpen && (
                          <div className="substitute-panel">
                            {guidedSwap.loading ? (
                              <p className="muted" style={{ fontSize: 12 }}>Buscando alternativas...</p>
                            ) : (guidedSwap.options || []).length > 0 ? (
                              <div className="substitute-options">
                                {guidedSwap.options.map((s, k) => (
                                  <button key={k} className="substitute-option" disabled={busy}
                                    onClick={() => aplicarSwapNaOpcao(i, it.food_id, s.food_id)}>
                                    <span>{s.food?.name || s.food_id}</span><b>{formatQty(s)}</b>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <p className="muted" style={{ fontSize: 12 }}>Nenhuma alternativa disponível agora.</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="action-row" style={{ marginTop: 12 }}>
                  <button className="primary-button" onClick={() => escolherOpcao(opt)} disabled={busy}>
                    Escolher esta combinação <ChevronRight size={18} />
                  </button>
                </div>
              </section>
            );
          })}

          {error && <div className="auth-error" style={{ marginTop: 14 }}>{error}</div>}

          <div className="deep-actions" style={{ marginTop: 20, flexWrap: "wrap" }}>
            <button className="secondary-button" onClick={outrasOpcoes} disabled={busy || guidedLoadingOptions}>
              <RefreshCw size={15} /> Mostrar outras opções
            </button>
            <button className="secondary-button" onClick={forgeEscolheEsta} disabled={busy || guidedLoadingOptions}>
              FORGE escolhe esta
            </button>
            <button className="secondary-button" onClick={forgeEscolheResto} disabled={busy}>
              FORGE escolhe o resto
            </button>
            <button className="text-button" onClick={() => setStep("plan")}>Cancelar</button>
          </div>
        </div>
      </div>
    );
  }

  // Plan view
  const t = targets || {};
  const meals = plan?.meals || [];
  return (
    <div className="content nutrition-page">
      <div className="section-intro">
        <p className="eyebrow">NUTRIÇÃO</p>
        <h2>Seu plano alimentar</h2>
      </div>

      <section className="macro-strip">
        <div><span>Calorias</span><b>{Math.round(t.goal_calories || 0)}<small>kcal</small></b></div>
        <div><span>Proteína</span><b>{Math.round(t.protein_g || 0)}<small>g</small></b></div>
        <div><span>Carbo</span><b>{Math.round(t.carbs_g || 0)}<small>g</small></b></div>
        <div><span>Gordura</span><b>{Math.round(t.fat_g || 0)}<small>g</small></b></div>
      </section>

      <button className="secondary-button" data-testid="open-diet-import"
        style={{ marginTop: 14 }} onClick={() => setImportOpen(true)}>
        <ClipboardPaste size={16} /> Colar minha dieta / periodizar
      </button>

      {importOpen && (
        <NutritionImport
          API={API}
          onActivated={res => { if (res?.plan) setPlan(res.plan); }}
          onClose={() => setImportOpen(false)}
        />
      )}

      {error && <div className="auth-error" style={{ marginTop: 14 }}>{error}</div>}

      {meals.length === 0 && (
        <div className="empty-state" data-testid="nutrition-empty-state">
          <Utensils size={22} />
          <h3>Nenhuma refeição no plano</h3>
          <p className="muted">Refaça o plano para montar suas refeições de hoje.</p>
        </div>
      )}

      {meals.map((meal, i) => {
        const status = mealStatus[i];
        return (
          <section className={status === "completed" ? "meal-card done" : "meal-card"} key={i}>
            <div className="meal-head">
              <div>
                <p className="eyebrow">{meal.name}</p>
                <h3>{Math.round(meal.target_cal || 0)} kcal</h3>
              </div>
              <div className="meal-status">
                <button
                  className={status === "completed" ? "meal-status-btn active-ok" : "meal-status-btn"}
                  aria-label={`Concluir ${meal.name}`}
                  data-testid={`meal-complete-${i}`}
                  onClick={() => markMeal(i, "completed")}>
                  <Check size={16} />
                </button>
                <button
                  className={status === "skipped" ? "meal-status-btn active-skip" : "meal-status-btn"}
                  aria-label={`Pular ${meal.name}`}
                  data-testid={`meal-skip-${i}`}
                  onClick={() => markMeal(i, "skipped")}>
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="food-list">
              {meal.foods?.map((item, j) => {
                const f = item.food || {};
                const open = subResult?.mealIdx === i && subResult?.foodId === item.food_id;
                return (
                  <div className="food-row" key={j}>
                    <div className="food-row-main">
                      <div className="food-row-info">
                        <b>{f.name || item.food_id}</b>
                        <span className="muted">{formatQty(item)} · {Math.round(f.kcal || 0)} kcal</span>
                      </div>
                      <button className="food-sub-btn" data-testid={`substitute-${i}-${item.food_id}`} onClick={() => doSubstitute(i, item.food_id)}>
                        <RefreshCw size={13} /> Substituir
                      </button>
                    </div>
                    {open && (
                      <div className="substitute-panel" data-testid={`substitute-panel-${i}-${item.food_id}`}>
                        <p className="eyebrow">SUBSTITUIR · {f.name || item.food_id} — {formatQty(item)}</p>
                        {subResult.loading ? (
                          <p className="muted" style={{ fontSize: 12 }}>Buscando opções...</p>
                        ) : (subResult.options || []).length > 0 ? (
                          <div className="substitute-options">
                            {subResult.options.map((opt, k) => (
                              <button key={k} className="substitute-option rich" disabled={busy}
                                data-testid={`substitute-option-${opt.food_id}`}
                                onClick={() => applySub(i, item.food_id, opt.food_id)}>
                                <span className="sub-head">
                                  <span className="sub-name">{opt.food?.name || opt.food_id}</span>
                                  {opt.badge && <em className="sub-badge">{opt.badge}</em>}
                                </span>
                                <b className="sub-qty">{formatQty(opt)}</b>
                                {opt.macros && (
                                  <span className="sub-macros">
                                    {opt.macros.kcal} kcal · P {opt.macros.protein_g}g · C {opt.macros.carbs_g}g · G {opt.macros.fat_g}g
                                    {typeof opt.delta_kcal === "number" && (
                                      <em className="sub-delta">{opt.delta_kcal === 0 ? "mesmas calorias" : `${opt.delta_kcal > 0 ? "+" : ""}${opt.delta_kcal} kcal`}</em>
                                    )}
                                  </span>
                                )}
                              </button>
                            ))}
                          </div>
                        ) : subResult.falhou ? (
                          <p className="substitute-error" data-testid="substitute-error">{subResult.falhou}</p>
                        ) : (
                          <p className="muted" style={{ fontSize: 12 }} data-testid="substitute-empty">Não encontramos uma alternativa compatível com suas restrições e metas atuais.</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      <div className="action-row" style={{ marginTop: 24 }}>
        <button className="secondary-button" onClick={refazerPlano} disabled={busy}>
          <RefreshCw size={15} /> {busy ? "Iniciando..." : "Refazer plano"}
        </button>
      </div>
    </div>
  );
}
