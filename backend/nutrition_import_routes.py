"""FORGE — rotas de importação de dieta em texto e de periodização calórica.

Mesmas convenções de nutrition_routes: prefixo /api/nutrition, db em
request.app.state.db, auth por get_current_user, sem importar server.

A dieta ativada é gravada em `nutrition_plans` no MESMO formato que
generate_daily_plan produz, então /plan, /substitute e /meal-status continuam
funcionando sobre um plano importado sem nenhuma mudança neles.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import get_current_user
from catalog_ai_match import (
    ai_matching_available, load_learned_aliases, record_missing_item,
    resolve_names_with_ai, save_learned_alias,
)
from nutrition_engine import FOOD_INDEX
from nutrition_import import (
    MAX_IMPORT_CHARS, MAX_ITEMS_PER_MEAL, MAX_LABEL_CHARS, MAX_MEALS, MAX_GRAMS,
    REVIEW_AI_SUGGESTED, apply_resolution, draft_to_plan, parse_diet_text, recompute,
    unmatched_names, validate_draft,
)
from nutrition_periodization import build_periodization, sanitize_edited_table
from text_match import sanitize

router = APIRouter(prefix="/api/nutrition", tags=["nutrition-import"])

FOOD_ALIASES_COLLECTION = "food_aliases"
FOOD_SUGGESTIONS_COLLECTION = "food_suggestions"


class ParseDietIn(BaseModel):
    text: str
    name: str = ""


class DietItemIn(BaseModel):
    food_id: Optional[str] = None
    raw_name: str = ""
    raw_text: str = ""
    quantity: Optional[float] = None
    unit: str = ""
    grams: Optional[float] = Field(default=None, ge=0, le=MAX_GRAMS)
    estimated: bool = False


class DietMealIn(BaseModel):
    name: str = "Refeicao"
    items: List[DietItemIn] = []


class DietDraftIn(BaseModel):
    name: str = "Dieta importada"
    source: str = "manual_import"
    meals: List[DietMealIn] = []


class DietDraftSaveIn(BaseModel):
    draft: DietDraftIn


class ActivateDietIn(BaseModel):
    draft: Optional[DietDraftIn] = None
    activation_token: str = Field(min_length=8, max_length=64)


class PeriodizationIn(BaseModel):
    target_kcal: Optional[float] = Field(default=None, ge=800, le=8000)
    pct: Optional[float] = Field(default=None, ge=-60, le=60)
    weeks: int = Field(ge=1, le=52)


class PeriodizationSaveIn(BaseModel):
    table: List[Dict[str, Any]]
    target_kcal: Optional[float] = None
    weeks: int = Field(ge=1, le=52)


def _target(user: dict) -> str:
    """Atleta so alcanca o proprio plano — id no corpo nunca e considerado."""
    return user["id"]


def _valid_ids():
    return set(FOOD_INDEX)


async def _profile(db, profile_id: str) -> Dict[str, Any]:
    return await db.profiles.find_one({"id": profile_id}, {"_id": 0}) or {}


def _rehydrate(draft: Dict[str, Any], matcher) -> Dict[str, Any]:
    """Revalida no servidor tudo que veio do cliente: alimento tem que existir no
    catálogo, gramas dentro do limite, e as flags de revisão são recalculadas — não dá
    para desbloquear a ativação mentindo pelo navegador."""
    from nutrition_import import (
        REVIEW_AMBIGUOUS, REVIEW_ESTIMATED_PORTION, REVIEW_FOOD_UNMATCHED,
        REVIEW_LOW_CONFIDENCE, REVIEW_QUANTITY_MISSING,
    )
    meals = []
    for meal in (draft.get("meals") or [])[:MAX_MEALS]:
        itens = []
        for raw in (meal.get("items") or [])[:MAX_ITEMS_PER_MEAL]:
            food_id = raw.get("food_id") or None
            nome = sanitize(raw.get("raw_name") or "", MAX_LABEL_CHARS)
            confidence = "manual" if food_id else "none"
            suggestions: List[str] = []
            if food_id and food_id not in FOOD_INDEX:
                food_id = None
            if not food_id and nome:
                food_id, confidence, suggestions = matcher.match(nome)

            grams = raw.get("grams")
            try:
                grams = float(grams) if grams is not None else None
            except (TypeError, ValueError):
                grams = None
            if grams is not None and not (0 < grams <= MAX_GRAMS):
                grams = None

            razoes: List[str] = []
            if confidence == "ambiguous":
                razoes.append(REVIEW_AMBIGUOUS)
            elif not food_id:
                razoes.append(REVIEW_FOOD_UNMATCHED)
            elif confidence == "fuzzy":
                razoes.append(REVIEW_LOW_CONFIDENCE)
            if grams is None:
                razoes.append(REVIEW_QUANTITY_MISSING)
            elif raw.get("estimated"):
                razoes.append(REVIEW_ESTIMATED_PORTION)

            itens.append({
                "food_id": food_id,
                "raw_name": nome or (FOOD_INDEX.get(food_id, {}).get("name", "") if food_id else ""),
                "raw_text": sanitize(raw.get("raw_text") or "", MAX_LABEL_CHARS),
                "match_confidence": confidence,
                "suggestions": suggestions[:5],
                "quantity": raw.get("quantity"),
                "unit": sanitize(raw.get("unit") or "", 20),
                "grams": grams,
                "estimated": bool(raw.get("estimated")),
                "needs_review": bool(razoes),
                "review_reasons": razoes,
            })
        meals.append({"name": sanitize(meal.get("name") or "Refeicao", MAX_LABEL_CHARS),
                      "items": itens})
    return recompute({
        "name": sanitize(draft.get("name") or "", MAX_LABEL_CHARS) or "Dieta importada",
        "source": "manual_import",
        "meals": meals,
        "warnings": [sanitize(w, 200) for w in (draft.get("warnings") or [])][:20],
    })


async def _matcher_for(db):
    from nutrition_import import build_matcher
    learned = await load_learned_aliases(db, FOOD_ALIASES_COLLECTION, _valid_ids())
    return build_matcher(learned)


async def _resolve_layers(db, profile_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    """Camada 2 só para o que sobrou: alimento resolvido nas camadas determinísticas
    nunca chega à IA. Falha de IA nunca derruba a importação."""
    pendentes = unmatched_names(draft)
    if pendentes and ai_matching_available():
        entries = {f["id"]: f["name"] for f in FOOD_INDEX.values()}
        resolvidos = await resolve_names_with_ai(pendentes, entries, dominio="alimentos")
        if resolvidos:
            draft = apply_resolution(draft, resolvidos, "ai", REVIEW_AI_SUGGESTED)
            for nome, food_id in resolvidos.items():
                await save_learned_alias(db, FOOD_ALIASES_COLLECTION, nome, food_id,
                                         _valid_ids(), source="ai", profile_id=profile_id)
    for nome in unmatched_names(draft):
        await record_missing_item(db, FOOD_SUGGESTIONS_COLLECTION, nome, profile_id)
    return draft


@router.get("/foods")
async def list_foods(_user=Depends(get_current_user)):
    """Catálogo de alimentos para os seletores da tela de importação."""
    return {"foods": sorted(
        ({"id": f["id"], "name": f["name"], "category": f.get("category", "")}
         for f in FOOD_INDEX.values()),
        key=lambda f: f["name"])}


# --- importação -----------------------------------------------------------------------

@router.post("/import/parse")
async def parse_diet(payload: ParseDietIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = _target(user)
    if len(payload.text or "") > MAX_IMPORT_CHARS:
        raise HTTPException(413, f"Texto muito grande: máximo de {MAX_IMPORT_CHARS} caracteres.")
    try:
        draft = parse_diet_text(payload.text, await _matcher_for(db), payload.name)
    except ValueError as e:
        raise HTTPException(400, str(e))

    draft = await _resolve_layers(db, target, draft)
    stored = await _save_draft(db, target, draft)
    return {"draft": {k: v for k, v in stored.items() if k != "_id"},
            "blocking_errors": validate_draft(stored)}


async def _save_draft(db, profile_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    doc = {**draft, "profile_id": profile_id, "status": "draft",
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_import_drafts.update_one({"profile_id": profile_id}, {"$set": doc}, upsert=True)
    return doc


@router.get("/import/draft")
async def get_diet_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    doc = await db.nutrition_import_drafts.find_one({"profile_id": _target(user)}, {"_id": 0})
    if not doc:
        return {"draft": None, "blocking_errors": []}
    return {"draft": doc, "blocking_errors": validate_draft(doc)}


@router.put("/import/draft")
async def save_diet_draft(payload: DietDraftSaveIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = _target(user)
    draft = _rehydrate(payload.draft.model_dump(), await _matcher_for(db))
    if not draft["meals"]:
        raise HTTPException(400, "O rascunho precisa de pelo menos uma refeição.")
    stored = await _save_draft(db, target, draft)
    return {"draft": {k: v for k, v in stored.items() if k != "_id"},
            "blocking_errors": validate_draft(stored)}


@router.post("/import/activate")
async def activate_diet(payload: ActivateDietIn, request: Request, user=Depends(get_current_user)):
    """Ativa a dieta importada como plano base. Arquiva o plano anterior (recuperável)
    e não toca em aderência, peso nem histórico."""
    db = request.app.state.db
    target = _target(user)
    profile = await _profile(db, target)

    anterior = profile.get("nutrition_import_activation") or {}
    if anterior.get("token") and anterior["token"] == payload.activation_token:
        atual = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
        return {"plan": (atual or {}).get("plan"), "already_applied": True,
                "archived_version_id": anterior.get("archived_version_id")}

    if payload.draft is not None:
        draft = _rehydrate(payload.draft.model_dump(), await _matcher_for(db))
    else:
        draft = await db.nutrition_import_drafts.find_one({"profile_id": target}, {"_id": 0})
        if not draft:
            raise HTTPException(404, "Nenhum rascunho de dieta para ativar.")

    erros = validate_draft(draft)
    if erros:
        raise HTTPException(422, {"message": "Revise a dieta antes de ativar.", "errors": erros})

    plan = draft_to_plan(draft)
    agora = datetime.now(timezone.utc).isoformat()

    archived_version_id = None
    anterior_doc = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if anterior_doc:
        archived_version_id = str(uuid.uuid4())
        await db.nutrition_plan_versions.insert_one({
            "id": archived_version_id, "profile_id": target, "archived_at": agora,
            "reason": "manual_import_activation", "plan": anterior_doc.get("plan"),
        })

    await db.nutrition_plans.replace_one(
        {"profile_id": target},
        {"profile_id": target, "user_id": target, "plan": plan, "created_at": agora,
         "source": "manual_import"},
        upsert=True)
    await db.profiles.update_one(
        {"id": target},
        {"$set": {"nutrition_import_activation": {
            "token": payload.activation_token, "activated_at": agora,
            "archived_version_id": archived_version_id}}},
        upsert=True)
    await db.nutrition_import_drafts.update_one(
        {"profile_id": target}, {"$set": {"status": "activated", "activated_at": agora}})

    return {"plan": plan, "already_applied": False,
            "archived_version_id": archived_version_id,
            "daily_totals": draft.get("daily_totals")}


# --- periodização ---------------------------------------------------------------------

async def _base_for_periodization(db, target: str) -> Dict[str, float]:
    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if not stored or not stored.get("plan"):
        raise HTTPException(404, "Nenhum plano alimentar ativo. Importe ou gere a dieta primeiro.")
    plan = stored["plan"]
    totais = plan.get("daily_totals") or {}
    if not totais:
        alvos = plan.get("targets") or {}
        totais = {"kcal": alvos.get("goal_calories", 0), "protein_g": alvos.get("protein_g", 0),
                  "carbs_g": alvos.get("carbs_g", 0), "fat_g": alvos.get("fat_g", 0)}
    return {"kcal": float(totais.get("kcal") or 0), "protein_g": float(totais.get("protein_g") or 0),
            "carbs_g": float(totais.get("carbs_g") or 0), "fat_g": float(totais.get("fat_g") or 0)}


async def _weight_and_goal(db, target: str):
    profile = await _profile(db, target)
    na = profile.get("nutrition_assessment") or {}
    peso = na.get("weight_kg")
    if not peso:
        ultimo = await db.nutrition_weight_logs.find_one({"profile_id": target}, {"_id": 0},
                                                         sort=[("created_at", -1)])
        peso = (ultimo or {}).get("weight_kg")
    if not peso:
        raise HTTPException(400, "Peso corporal necessário para o piso de gordura. "
                                 "Faça o assessment nutricional ou registre seu peso.")
    return float(peso), na.get("goal", "fat_loss")


@router.post("/periodization/preview")
async def preview_periodization(payload: PeriodizationIn, request: Request,
                                user=Depends(get_current_user)):
    """Gera a tabela semanal sem salvar nada."""
    db = request.app.state.db
    target = _target(user)
    base = await _base_for_periodization(db, target)
    peso, goal = await _weight_and_goal(db, target)
    try:
        return build_periodization(base, peso, payload.weeks,
                                   target_kcal=payload.target_kcal, pct=payload.pct, goal=goal)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/periodization/save")
async def save_periodization(payload: PeriodizationSaveIn, request: Request,
                             user=Depends(get_current_user)):
    """Salva a tabela — inclusive editada à mão. As kcal são recalculadas a partir dos
    macros no servidor e o piso de gordura continua valendo na edição manual."""
    db = request.app.state.db
    target = _target(user)
    peso, goal = await _weight_and_goal(db, target)
    tabela = sanitize_edited_table(payload.table, peso, goal)
    if not tabela:
        raise HTTPException(400, "Tabela vazia.")
    doc = {"profile_id": target, "weeks": len(tabela), "target_kcal": payload.target_kcal,
           "weight_kg": peso, "goal": goal, "table": tabela,
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_periodization.replace_one({"profile_id": target}, doc, upsert=True)
    return {"periodization": doc,
            "infeasible_weeks": [w["week"] for w in tabela if not w["feasible"]]}


@router.get("/periodization")
async def get_periodization(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    doc = await db.nutrition_periodization.find_one({"profile_id": _target(user)}, {"_id": 0})
    return {"periodization": doc}
