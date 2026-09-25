"""FORGE — rotas de importação de dieta em texto.

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
from nutrition_engine import FOOD_INDEX, compute_macro_targets
from nutrition_import import (
    MAX_ALTERNATIVES, MAX_IMPORT_CHARS, MAX_ITEMS_PER_MEAL, MAX_LABEL_CHARS, MAX_MEALS,
    MAX_GRAMS, MAX_OPTIONS_PER_SUBSTITUTION, MAX_SUBSTITUTIONS, REVIEW_AI_SUGGESTED,
    apply_resolution, draft_to_plan, parse_diet_text, recompute, review_reasons,
    sanitize_substitutions, unmatched_names, validate_draft, restore_import_targets,
)
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
    # "Carne bovina/frango/peixe": as opções que não viraram o item. Sem estes dois campos
    # o Pydantic descartava o que o parser leu no primeiro salvar do rascunho.
    alternativas: List[str] = Field(default_factory=list, max_length=MAX_ALTERNATIVES)
    a_vontade: bool = False


class DietMealIn(BaseModel):
    name: str = "Refeicao"
    items: List[DietItemIn] = []


class OpcaoDeTrocaIn(BaseModel):
    food_id: Optional[str] = None
    raw_name: str = ""
    grams: Optional[float] = Field(default=None, ge=0, le=MAX_GRAMS)
    estimated: bool = False


class SubstituicaoIn(BaseModel):
    titulo: str = ""
    opcoes: List[OpcaoDeTrocaIn] = Field(default_factory=list,
                                        max_length=MAX_OPTIONS_PER_SUBSTITUTION)


class DietDraftIn(BaseModel):
    name: str = "Dieta importada"
    source: str = "manual_import"
    meals: List[DietMealIn] = []
    substituicoes: List[SubstituicaoIn] = Field(default_factory=list,
                                                max_length=MAX_SUBSTITUTIONS)


class DietDraftSaveIn(BaseModel):
    draft: DietDraftIn


class ActivateDietIn(BaseModel):
    draft: Optional[DietDraftIn] = None
    activation_token: str = Field(min_length=8, max_length=64)


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

            a_vontade = bool(raw.get("a_vontade"))
            estimated = bool(raw.get("estimated"))
            alternativas = [a for a in (raw.get("alternativas") or [])
                            if isinstance(a, str) and a in FOOD_INDEX and a != food_id]
            razoes = review_reasons(confidence, food_id, grams, estimated, a_vontade)

            itens.append({
                "food_id": food_id,
                "raw_name": nome or (FOOD_INDEX.get(food_id, {}).get("name", "") if food_id else ""),
                "raw_text": sanitize(raw.get("raw_text") or "", MAX_LABEL_CHARS),
                "match_confidence": confidence,
                "suggestions": suggestions[:5],
                "alternativas": list(dict.fromkeys(alternativas))[:MAX_ALTERNATIVES],
                "a_vontade": a_vontade,
                "quantity": raw.get("quantity"),
                "unit": sanitize(raw.get("unit") or "", 20),
                "grams": grams,
                "estimated": estimated,
                "needs_review": bool(razoes),
                "review_reasons": razoes,
            })
        meals.append({"name": sanitize(meal.get("name") or "Refeicao", MAX_LABEL_CHARS),
                      "items": itens})
    return recompute({
        "name": sanitize(draft.get("name") or "", MAX_LABEL_CHARS) or "Dieta importada",
        "source": "manual_import",
        "meals": meals,
        "substituicoes": sanitize_substitutions(draft.get("substituicoes")),
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
    # Rascunho ja ativado nao e rascunho: reabri-lo prendia a tela na previa da dieta que
    # ja esta no plano, sem a caixa de texto para colar a proxima.
    if not doc or doc.get("status") == "activated":
        return {"draft": None, "blocking_errors": []}
    return {"draft": doc, "blocking_errors": validate_draft(doc)}


@router.delete("/import/draft")
async def discard_diet_draft(request: Request, user=Depends(get_current_user)):
    """Descarta o rascunho para colar outra dieta.

    O caso: um atleta colou a dieta quando o importador ainda perdia as quantidades. O
    rascunho ruim ficou salvo, a tela reabria sempre nele, e nao havia onde colar de novo.
    O plano ativo nao e tocado — so o rascunho.
    """
    db = request.app.state.db
    await db.nutrition_import_drafts.delete_one({"profile_id": _target(user)})
    return {"discarded": True}


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


def _targets_do_questionario(profile: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """
    Meta calculada do atleta, ou None quando o questionario nao da para calcular.

    Mesma chamada que a geracao automatica usa, com os mesmos campos obrigatorios — a
    dieta importada passa a ser medida contra a MESMA necessidade que um plano gerado.
    """
    na = (profile or {}).get("nutrition_assessment") or {}
    if not all(na.get(k) for k in ("weight_kg", "height_cm", "age", "training_days")):
        return None
    try:
        t = compute_macro_targets(
            na["weight_kg"], na["height_cm"], na["age"], na.get("sex") or "male",
            na["training_days"], na.get("goal") or "maintenance",
            na.get("activity_level", "moderate"), na.get("intensity"))
    except Exception:  # noqa: BLE001 — questionario torto nao pode impedir a ativacao
        return None
    return {k: t[k] for k in ("goal_calories", "protein_g", "carbs_g", "fat_g") if k in t}


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
        atual = await restore_import_targets(db, target, atual)
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

    # A dieta confirmada define as metas; o questionario fica apenas como referencia.
    plan = draft_to_plan(draft, _targets_do_questionario(profile))
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

