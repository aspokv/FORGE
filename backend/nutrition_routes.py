"""FORGE Nutrition API routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid, random

from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])

# Tentativas de regeneracao antes de desistir e devolver erro claro ao usuario.
GENERATION_ATTEMPTS = 6

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, validate_daily_plan, check_plan_hard_limits,
    find_substitutes, recalculate_substitution_portion, FOOD_INDEX,
    FORGE_COACH_METHODOLOGY, sum_plan_totals,
    get_meal_archetype_options, redistribute_remaining_targets,
    calculate_meal_portions, calculate_meal_coherence_score, _infer_meal_type,
    build_food_item,
)


class NutritionAssessmentIn(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    height_cm: float = Field(gt=0, le=280)
    age: int = Field(ge=10, le=120)
    sex: str = "male"
    goal: str = "maintenance"
    # Intensidade do emagrecimento: "leve" | "moderado" | "agressivo". Opcional de
    # proposito — perfil antigo, sem escolha, segue no calculo legado (resolve_cut_protocol
    # devolve None) e nao tem o alvo calorico alterado por esta feature.
    intensity: Optional[str] = None
    activity_level: str = "moderate"
    training_days: int = Field(ge=1, le=7)
    meal_count: int = Field(ge=3, le=6)
    training_time: Optional[str] = None
    preferred_foods: List[str] = []
    disliked_foods: List[str] = []
    avoid_foods: List[str] = []
    allergies: List[str] = []
    dietary_restrictions: List[str] = []
    cooking_time: str = "medium"


class MealStatusIn(BaseModel):
    meal_index: int = Field(ge=0, le=5)
    status: str = "completed"


class SubstituteFoodIn(BaseModel):
    meal_index: int = Field(ge=0)
    food_id: str
    food_index: Optional[int] = Field(default=None, ge=0)
    substitute_food_id: Optional[str] = None


class WeightLogIn(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    date: Optional[str] = None


class MealOptionsIn(BaseModel):
    meal_index: int = Field(ge=0)
    variety_seed: Optional[int] = None


class SwapFoodIn(BaseModel):
    meal_index: int = Field(ge=0)
    food_ids: List[str]
    food_id: str
    substitute_food_id: Optional[str] = None


class ChooseMealIn(BaseModel):
    meal_index: int = Field(ge=0)
    archetype_id: str = "default"
    food_ids: List[str]


class PreferenceIn(BaseModel):
    food_id: str
    signal: str = Field(pattern="^(liked|avoided|neutral)$")


def _build_empty_draft(targets, meal_count, goal):
    m = FORGE_COACH_METHODOLOGY
    dist = m["meal_distribution"].get(meal_count, m["meal_distribution"][4])
    names = m["meal_names"].get(meal_count, m["meal_names"][4])
    gc, gp, gf = targets["goal_calories"], targets["protein_g"], targets["fat_g"]
    meals = [{"name": names[i], "target_cal": round(gc * dist[i]), "target_protein": round(gp * dist[i]),
              "target_fat": round(gf * dist[i], 1), "foods": [], "archetype_id": None}
             for i in range(meal_count)]
    return {"meals": meals, "locked": [False] * meal_count, "targets": targets, "goal": goal, "meal_count": meal_count}


def _locked_used_ids(draft):
    used = set()
    for i, locked in enumerate(draft["locked"]):
        if locked:
            for it in draft["meals"][i]["foods"]:
                used.add(it["food_id"])
    return used


async def _load_preferences(db, profile_id):
    rows = await db.nutrition_preferences.find({"profile_id": profile_id}, {"_id": 0}).to_list(500)
    return {r["food_id"]: {"signal": r.get("signal", "neutral"), "chosen_count": r.get("chosen_count", 0)} for r in rows}


async def _record_choice_preferences(db, profile_id, food_ids):
    now = datetime.now(timezone.utc).isoformat()
    for fid in food_ids:
        await db.nutrition_preferences.update_one(
            {"profile_id": profile_id, "food_id": fid},
            {"$inc": {"chosen_count": 1}, "$set": {"updated_at": now},
             "$setOnInsert": {"signal": "neutral"}},
            upsert=True)


def owned_nutrition_target(user: dict, requested: Optional[str] = None) -> str:
    if user.get("role") == "SUPER_ADMIN":
        return requested or user["id"]
    return user["id"]


# Campos sem os quais compute_macro_targets nao roda. O onboarding de treino pode
# semear nutrition_assessment so com objetivo/intensidade; esse documento parcial nao
# pode passar por completo, senao a geracao quebraria com KeyError em vez de pedir o
# questionario.
CAMPOS_OBRIGATORIOS = ("weight_kg", "height_cm", "age", "training_days")


def _assessment_completo(na) -> bool:
    return bool(na) and all(na.get(k) for k in CAMPOS_OBRIGATORIOS)


def _exigir_assessment(na, target, operacao):
    """400 com o motivo REAL no log do servidor.

    O perfil pode ter plano e nao ter questionario: ate a correcao do carry-forward em
    save_assessment, "Refazer avaliacao" fazia replace_one do perfil inteiro e levava o
    nutrition_assessment junto. Quem passou por isso ficava com o plano visivel e a
    regeneracao recusada."""
    if _assessment_completo(na):
        return
    faltando = [k for k in CAMPOS_OBRIGATORIOS if not (na or {}).get(k)]
    logger.warning("%s bloqueado para profile_id=%s: nutrition_assessment %s (faltando: %s)",
                   operacao, target, "ausente" if not na else "incompleto",
                   ", ".join(faltando) or "-")
    raise HTTPException(400, "Assessment nutricional nao encontrado. Faca o questionario primeiro.")


def _com_protocolo(na, targets):
    """Injeta no assessment o teto de carboidrato por alimento quando o protocolo tem um.

    Mesmo mecanismo que generate_daily_plan usa — _food_compatible e o portao unico de
    elegibilidade. Sem isto, o fluxo guiado ofereceria arroz e pao a quem escolheu o
    protocolo agressivo, e a tela diria "Agressivo" sobre um plano que nao e."""
    protocolo = (targets or {}).get("cut_protocol") or {}
    if protocolo.get("carb_mode") != "capped":
        return na
    cfg = FORGE_COACH_METHODOLOGY["cutting_intensity"][protocolo["intensity"]]
    return {**(na or {}), "_max_food_carb_g_per_100g": cfg["max_food_carb_g_per_100g"]}


@router.get("/assessment")
async def get_assessment(request: Request, user=Depends(get_current_user)):
    """Devolve o questionario salvo para a tela abrir com as escolhas ja feitas —
    inclusive a intensidade vinda do onboarding. Antes isto era um stub que so devolvia
    uma mensagem, entao a area de Alimentacao sempre reabria em branco."""
    db = request.app.state.db
    profile = await db.profiles.find_one({"id": user["id"]}, {"_id": 0, "nutrition_assessment": 1})
    na = (profile or {}).get("nutrition_assessment")
    return {"assessment": na or None, "complete": _assessment_completo(na)}


def _opcoes_de_intensidade(nome_do_conjunto):
    cfg = FORGE_COACH_METHODOLOGY[nome_do_conjunto]
    return [
        {"id": k, "label": v["label"], "description": v["description"],
         "recommended": bool(v.get("recommended")), "advanced": bool(v.get("advanced")),
         "warning": v.get("warning"),
         # negativo = deficit, positivo = superavit; a interface so precisa do numero
         "delta_pct": round((v["kcal_pct"] - 1) * 100),
         "protein_g_per_kg": v["protein_g_per_kg"],
         "carb_range_g": ([v["carb_min_g"], v["carb_max_g"]]
                          if v.get("carb_mode") == "capped" else None)}
        for k, v in cfg.items()
    ]


@router.get("/goal-catalog")
async def goal_catalog(_user=Depends(get_current_user)):
    """Objetivos corporais e os ritmos de cada um, numa chamada so.

    A secao "Objetivo" do onboarding trata apenas do objetivo corporal/alimentar:
    desempenho e prioridade muscular sao outras etapas. Manutencao nao tem ritmo."""
    conjuntos = {"muscle_gain": "bulking_intensity", "fat_loss": "cutting_intensity"}
    padroes = {"muscle_gain": FORGE_COACH_METHODOLOGY["bulking_intensity_default"],
               "fat_loss": FORGE_COACH_METHODOLOGY["cutting_intensity_default"]}
    return {
        "protocol_version": FORGE_COACH_METHODOLOGY["cut_protocol_version"],
        "goals": [
            {**g,
             "default_intensity": padroes.get(g["id"]),
             "intensities": _opcoes_de_intensidade(conjuntos[g["id"]]) if g["id"] in conjuntos else []}
            for g in FORGE_COACH_METHODOLOGY["body_goals"]
        ],
    }


@router.get("/cutting-intensities")
async def cutting_intensities(_user=Depends(get_current_user)):
    """Catalogo das intensidades de emagrecimento. A UI monta os cards a partir daqui em
    vez de repetir rotulo, descricao e aviso — a metodologia continua com uma fonte so."""
    opcoes = _opcoes_de_intensidade("cutting_intensity")
    return {
        "default": FORGE_COACH_METHODOLOGY["cutting_intensity_default"],
        "protocol_version": FORGE_COACH_METHODOLOGY["cut_protocol_version"],
        # deficit_pct e mantido (positivo) para nao quebrar quem ja consome este endpoint
        "options": [{**o, "deficit_pct": -o["delta_pct"]} for o in opcoes],
    }


@router.post("/assessment")
async def save_assessment(payload: NutritionAssessmentIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"] if user.get("role") == "ATHLETE" else user["id"]
    doc = payload.model_dump()
    if not (doc.get("intensity") or "").strip():
        # O formulario manda intensity:"" quando o campo nao foi tocado. Isso apagaria em
        # silencio a escolha feita no onboarding, entao o valor anterior e carregado
        # adiante. Uma escolha explicita (string preenchida) continua vencendo.
        anterior = await db.profiles.find_one({"id": target}, {"_id": 0, "nutrition_assessment": 1})
        doc["intensity"] = ((anterior or {}).get("nutrition_assessment") or {}).get("intensity")
    doc["profile_id"] = target
    doc["user_id"] = target
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["assessment_version"] = 1
    await db.nutrition_assessments.insert_one(doc)
    doc.pop("_id", None)  # insert_one mutates doc in place, adding a non-JSON-serializable ObjectId
    await db.profiles.update_one({"id": target}, {"$set": {"nutrition_assessment": doc}}, upsert=True)
    return {"assessment": doc, "assessment_version": 1}


@router.post("/generate")
async def generate_plan(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment")
    _exigir_assessment(na, target, "gerar plano")
    targets = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))

    # Gera -> valida -> so entao persiste. Antes, o plano era salvo primeiro e
    # validate_daily_plan devolvia avisos que ninguem bloqueava: um plano fora dos limites
    # do protocolo substituia um plano valido e ainda era apresentado como correto. Uma
    # nova semente por tentativa e o proprio mecanismo de regeneracao do motor.
    plan, errors = None, []
    for _ in range(GENERATION_ATTEMPTS):
        candidate = generate_daily_plan(targets, na, na.get("meal_count", 4), na["goal"],
                                        random.randint(0, 999))
        errors = check_plan_hard_limits(candidate, targets)
        if not errors:
            plan = candidate
            break
    if plan is None:
        # Nada e gravado: o plano anterior, valido, continua de pe.
        raise HTTPException(422, {
            "message": "Nao foi possivel gerar um plano dentro dos limites do protocolo escolhido.",
            "errors": errors})

    doc = {"profile_id": target, "user_id": target, "plan": plan, "created_at": datetime.now(timezone.utc).isoformat(),
           "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
           "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"],
           "intensity": (targets.get("cut_protocol") or {}).get("intensity"),
           "cut_protocol": targets.get("cut_protocol")}
    await db.nutrition_plans.replace_one({"profile_id": target}, doc, upsert=True)
    warnings = validate_daily_plan(plan, targets, na)
    return {"plan": plan, "targets": targets, "warnings": warnings}


@router.get("/plan")
async def get_plan(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if not stored:
        raise HTTPException(404, "Plano nÃ£o encontrado. Gere primeiro via POST /api/nutrition/generate.")
    return stored["plan"]


@router.post("/substitute")
async def substitute_food(payload: SubstituteFoodIn, request: Request, user=Depends(get_current_user)):
    # target is always derived from the authenticated identity, never from client input —
    # this endpoint can only ever read/write the caller's own plan (no profile_id in the
    # payload at all), which is what makes cross-athlete IDOR structurally impossible here.
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    meal_idx = payload.meal_index
    food_id = payload.food_id

    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if not stored or not stored.get("plan", {}).get("meals"):
        raise HTTPException(404, "Plano nao encontrado")
    plan = stored["plan"]
    meals = plan.get("meals", [])
    if meal_idx >= len(meals):
        raise HTTPException(400, "Indice de refeicao invalido")
    meal = meals[meal_idx]
    foods = meal.get("foods", [])

    if payload.food_index is not None:
        if payload.food_index >= len(foods) or foods[payload.food_index].get("food_id") != food_id:
            raise HTTPException(400, "Indice de alimento invalido")
        food_pos = payload.food_index
    else:
        food_pos = next((idx for idx, f in enumerate(foods) if f.get("food_id") == food_id), None)
        if food_pos is None:
            raise HTTPException(404, "Alimento nao encontrado na refeicao")

    original = foods[food_pos]
    current_foods = [f["food_id"] for f in foods]

    # find_substitutes() re-runs the full engine pipeline (allergies, avoid_foods,
    # dietary_restrictions, goal-directional tolerance, daily guardrails) against the
    # CURRENT persisted plan state — recomputed fresh on every call, list or apply, so a
    # stale client can never smuggle through a food that isn't valid right now.
    # meal_type/meal_target_* enable role-aware DNA-family candidates and simulation-based
    # portion equivalence (item 1/2); meals persisted before this field existed simply
    # fall back to the older calorie-equivalence sizing (has_meal_target=False upstream).
    subs = find_substitutes(
        food_id, na, current_foods, max_results=3, orig_grams=original.get("grams", 100),
        goal=na.get("goal", "maintenance"), meal=foods,
        daily_totals=plan.get("daily_totals", {}), targets=plan.get("targets", {}),
        meal_type=_infer_meal_type(meal.get("name", "")),
        meal_target_cal=meal.get("target_cal"), meal_target_protein=meal.get("target_protein"),
        meal_target_fat=meal.get("target_fat"))

    options = []
    matched = None
    for s in subs:
        fid, grams, reason = s[0], s[1], s[2]
        opt = {**build_food_item(fid, grams), "reason": reason}
        if len(s) >= 4:
            evald = s[3]
            opt.update({
                "direction": evald.get("direction"), "goal_compatible": evald.get("goal_compatible"),
                "local_delta_kcal": evald.get("local_delta_kcal"), "daily_delta_kcal": evald.get("daily_delta_kcal"),
                "valid": evald.get("valid"),
            })
        options.append(opt)
        if payload.substitute_food_id and fid == payload.substitute_food_id:
            matched = opt

    if not payload.substitute_food_id:
        return {"original": food_id, "options": options}

    if not matched:
        raise HTTPException(400, "Substituicao nao permitida para este alimento e objetivo atual")

    # Backend remains the sole source of truth for grams/macros. When the meal carries a
    # real target (role-aware equivalence was used to find this candidate), every item in
    # the meal must be re-persisted at its simulated portion — not just the swapped slot —
    # since calculate_meal_portions resized the WHOLE meal around the swap (item 2:
    # "reconcilie os demais componentes da refeicao"). Leaving the other items at their
    # pre-swap grams would silently drift the persisted meal away from its own target.
    if meal.get("target_cal") is not None and meal.get("target_protein") is not None:
        new_food_ids = [matched["food_id"] if i == food_pos else f["food_id"] for i, f in enumerate(foods)]
        portions = calculate_meal_portions(new_food_ids, meal["target_cal"], meal["target_protein"],
                                            meal.get("target_fat", 0), na.get("goal", "maintenance"))
        new_foods = [build_food_item(fid, portions.get(fid, foods[i].get("grams", 100)))
                     for i, fid in enumerate(new_food_ids)]
    else:
        new_foods = list(foods)
        new_foods[food_pos] = {"food_id": matched["food_id"], "grams": matched["grams"], "food": matched["food"]}

    meal["foods"] = new_foods
    meals[meal_idx] = meal
    plan["meals"] = meals
    new_totals = sum_plan_totals(meals)
    plan["daily_totals"] = new_totals

    # Targeted, precise field update instead of replacing the whole document — a concurrent
    # request touching a different meal/food never gets clobbered by this write.
    await db.nutrition_plans.update_one(
        {"profile_id": target},
        {"$set": {
            f"plan.meals.{meal_idx}.foods": new_foods,
            "plan.daily_totals": new_totals,
        }},
    )

    return {
        "original": food_id, "options": options, "applied": True,
        "meal_index": meal_idx, "food_index": food_pos,
        "food": new_foods[food_pos], "daily_totals": new_totals, "plan": plan,
    }


# ─── Guided flow (RESET_PLAN / MEAL_ARCHETYPES / FORGE_CHOOSES_FOR_ME) ─────────────
# "Refazer plano" replaces the old one-shot Regenerar. It only ever touches the plan
# draft below and, on confirm, the single nutrition_plans document — never the
# assessment, weight history, adherence, or the Training Engine. Legacy POST /generate
# is untouched and remains the fallback ("FORGE monta tudo de uma vez").

@router.post("/plan/reset")
async def reset_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment")
    _exigir_assessment(na, target, "refazer plano")
    # A intensidade faltava aqui: refazer o plano recalculava com o caminho legado e
    # descartava o protocolo escolhido, enquanto /generate ja o respeitava.
    targets = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))
    meal_count = na.get("meal_count", 4)
    draft = _build_empty_draft(targets, meal_count, na["goal"])
    doc = {"profile_id": target, "user_id": target, "created_at": datetime.now(timezone.utc).isoformat(), **draft}
    await db.nutrition_plan_drafts.replace_one({"profile_id": target}, doc, upsert=True)
    doc.pop("_id", None)
    return doc


@router.get("/plan/draft")
async def get_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    return draft


@router.post("/plan/draft/options")
async def draft_meal_options(payload: MealOptionsIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    na = _com_protocolo(na, draft.get("targets"))
    meal = draft["meals"][idx]
    preferences = await _load_preferences(db, target)
    # "Mostrar outras opcoes": a fresh seed shifts which concrete foods each archetype
    # resolves to (existing rotation mechanism), without touching any guardrail.
    seed = payload.variety_seed if payload.variety_seed is not None else random.randint(0, 999)
    options = get_meal_archetype_options(
        meal["name"], meal["target_cal"], meal["target_protein"], meal.get("target_fat", 0),
        na, _locked_used_ids(draft), goal, None, idx, preferences, 5, seed)
    return {"meal_index": idx, "target_cal": meal["target_cal"], "target_protein": meal["target_protein"],
            "options": [{
                "archetype_id": o["archetype_id"], "label": o["label"], "coherence_score": o["coherence_score"],
                "foods": [build_food_item(it["food_id"], it["grams"]) for it in o["meal"]["foods"]],
            } for o in options]}


@router.post("/plan/draft/swap-food")
async def draft_swap_food(payload: SwapFoodIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    if payload.food_id not in payload.food_ids:
        raise HTTPException(400, "food_id nao esta na combinacao atual")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    meal_target = draft["meals"][idx]

    # The structure the athlete picked stays put — only this one food's slot changes,
    # and portions are recalculated for the whole combination afterward.
    current_portions = calculate_meal_portions(
        payload.food_ids, meal_target["target_cal"], meal_target["target_protein"],
        meal_target.get("target_fat", 0), goal)
    orig_grams = current_portions.get(payload.food_id, 100)
    current_foods = [build_food_item(fid, current_portions.get(fid, 100)) for fid in payload.food_ids]
    locked_totals = sum_plan_totals([draft["meals"][i] for i, l in enumerate(draft["locked"]) if l])

    # validate_daily=False: the draft day is still in progress (locked_totals only covers
    # meals confirmed so far), so the whole-day guardrail would reject every substitution.
    # meal_type/meal_target_* give role-aware DNA-family candidates sized by simulating
    # THIS meal — the fix for "Nenhuma alternativa disponivel agora" (item 1/2).
    subs = find_substitutes(
        payload.food_id, na, payload.food_ids, max_results=3, orig_grams=orig_grams,
        goal=goal, meal=current_foods, daily_totals=locked_totals, targets=draft["targets"],
        meal_type=_infer_meal_type(meal_target.get("name", "")),
        meal_target_cal=meal_target["target_cal"], meal_target_protein=meal_target["target_protein"],
        meal_target_fat=meal_target.get("target_fat", 0), validate_daily=False)
    options = [{**build_food_item(s[0], s[1]), "reason": s[2]} for s in subs]

    if not payload.substitute_food_id:
        return {"meal_index": idx, "food_id": payload.food_id, "options": options}

    matched = next((o for o in options if o["food_id"] == payload.substitute_food_id), None)
    if not matched:
        raise HTTPException(400, "Substituicao nao permitida para este alimento e objetivo atual")

    new_food_ids = [matched["food_id"] if fid == payload.food_id else fid for fid in payload.food_ids]
    portions = calculate_meal_portions(
        new_food_ids, meal_target["target_cal"], meal_target["target_protein"],
        meal_target.get("target_fat", 0), goal)
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in new_food_ids]
    return {"meal_index": idx, "foods": foods, "applied": True}


@router.post("/plan/draft/choose")
async def draft_choose_meal(payload: ChooseMealIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    if not payload.food_ids:
        raise HTTPException(400, "Selecione ao menos um alimento")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    meal_target = draft["meals"][idx]

    # Backend remains the source of truth for grams: the client selects WHICH foods,
    # the engine — never the client — decides HOW MUCH, exactly like /substitute.
    portions = calculate_meal_portions(
        payload.food_ids, meal_target["target_cal"], meal_target["target_protein"],
        meal_target.get("target_fat", 0), goal)
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in payload.food_ids]
    draft["meals"][idx]["foods"] = foods
    draft["meals"][idx]["archetype_id"] = payload.archetype_id
    draft["locked"][idx] = True
    redistribute_remaining_targets(draft["meals"], draft["locked"], draft["targets"], goal)

    await db.nutrition_plan_drafts.update_one(
        {"profile_id": target}, {"$set": {"meals": draft["meals"], "locked": draft["locked"]}})
    await _record_choice_preferences(db, target, payload.food_ids)
    draft.pop("_id", None)
    return draft


@router.post("/plan/draft/choose-remaining")
async def draft_choose_remaining(request: Request, user=Depends(get_current_user)):
    """FORGE_CHOOSES_FOR_ME across every meal that isn't locked in yet."""
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    preferences = await _load_preferences(db, target)
    chosen_food_ids = []
    for idx in range(len(draft["meals"])):
        if draft["locked"][idx]:
            continue
        meal_target = draft["meals"][idx]
        options = get_meal_archetype_options(
            meal_target["name"], meal_target["target_cal"], meal_target["target_protein"],
            meal_target.get("target_fat", 0), na, _locked_used_ids(draft), goal, None, idx,
            preferences, 1, random.randint(0, 999))
        best = options[0]
        draft["meals"][idx]["foods"] = best["meal"]["foods"]
        draft["meals"][idx]["archetype_id"] = best["archetype_id"]
        draft["locked"][idx] = True
        chosen_food_ids.extend(it["food_id"] for it in best["meal"]["foods"])
        redistribute_remaining_targets(draft["meals"], draft["locked"], draft["targets"], goal)

    await db.nutrition_plan_drafts.update_one(
        {"profile_id": target}, {"$set": {"meals": draft["meals"], "locked": draft["locked"]}})
    if chosen_food_ids:
        await _record_choice_preferences(db, target, chosen_food_ids)
    draft.pop("_id", None)
    return draft


@router.post("/plan/draft/confirm")
async def confirm_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    if not all(draft["locked"]):
        raise HTTPException(400, "Existem refeicoes ainda nao escolhidas. Use /choose ou /choose-remaining antes de confirmar.")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    totals = sum_plan_totals(draft["meals"])
    for i, meal in enumerate(draft["meals"]):
        # Cross-meal repetition check (item 10) against every OTHER meal in the final
        # plan — a true adjacent/daily view, not just what was known when this meal's
        # options were first generated.
        used_elsewhere = {it["food_id"] for j, m in enumerate(draft["meals"]) if j != i for it in m.get("foods", [])}
        meal["coherence_score"] = calculate_meal_coherence_score(meal, _infer_meal_type(meal["name"]), goal, used_elsewhere)
    plan = {"meals": draft["meals"], "daily_totals": totals, "pre_reconciliation_totals": totals,
            "targets": draft["targets"], "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
            "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"], "composed_by": "guided"}
    # Same validator the legacy /generate uses — this IS the "porcoes, restricoes e
    # regras do coach foram respeitadas" confirmation surfaced to the review screen.
    warnings = validate_daily_plan(plan, draft["targets"], na)
    # Mesmo limite duro do /generate: um plano fora do teto do protocolo nao pode ser
    # gravado e apresentado como "Agressivo". O rascunho NAO e apagado aqui, entao o
    # atleta ajusta as refeicoes e confirma de novo — nada do trabalho guiado se perde,
    # e o plano anterior continua intacto ate um confirm valido.
    erros = check_plan_hard_limits(plan, draft["targets"])
    if erros:
        logger.warning("confirmacao bloqueada para profile_id=%s: %s", target, "; ".join(erros))
        raise HTTPException(422, {
            "message": "O plano montado ficou fora dos limites do protocolo escolhido.",
            "errors": erros})

    doc = {"profile_id": target, "user_id": target, "plan": plan, "created_at": datetime.now(timezone.utc).isoformat(),
           "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
           "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"]}
    await db.nutrition_plans.replace_one({"profile_id": target}, doc, upsert=True)
    await db.nutrition_plan_drafts.delete_one({"profile_id": target})
    return {"plan": plan, "targets": draft["targets"], "warnings": warnings}


@router.post("/preferences")
async def set_food_preference(payload: PreferenceIn, request: Request, user=Depends(get_current_user)):
    """Explicit USER_PREFERENCES signal ('prefiro evitar' etc.) — a preference, never an
    allergy or restriction. Only ever nudges ranking inside get_meal_archetype_options;
    it can never widen what's offered past allergies/restrictions/avoid_foods/hard_max."""
    db = request.app.state.db
    target = user["id"]
    await db.nutrition_preferences.update_one(
        {"profile_id": target, "food_id": payload.food_id},
        {"$set": {"signal": payload.signal, "updated_at": datetime.now(timezone.utc).isoformat()},
         "$setOnInsert": {"chosen_count": 0}},
        upsert=True)
    return {"food_id": payload.food_id, "signal": payload.signal}


@router.post("/meal-status")
async def update_meal_status(payload: MealStatusIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    doc = {"profile_id": target, "user_id": target, "meal_index": payload.meal_index,
           "status": payload.status, "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_adherence.insert_one(doc)
    return {"status": "registered"}


@router.get("/adherence/{date}")
async def get_adherence(date: str, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    rows = await db.nutrition_adherence.find({"profile_id": target, "date": date}, {"_id": 0}).to_list(10)
    return {"date": date, "meals": rows}


@router.post("/weight")
async def log_weight(payload: WeightLogIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    doc = {"profile_id": target, "user_id": target, "weight_kg": payload.weight_kg,
           "date": payload.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_weight_logs.insert_one(doc)
    await db.profiles.update_one({"id": target}, {"$set": {"latest_weight": payload.weight_kg,
                                  "latest_weight_date": doc["date"]}}, upsert=True)
    return {"weight": payload.weight_kg, "date": doc["date"]}


@router.get("/weight")
async def get_weight_history(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    rows = await db.nutrition_weight_logs.find({"profile_id": target}, {"_id": 0}).sort("date", -1).to_list(30)
    return {"history": rows}

