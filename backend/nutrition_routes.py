"""FORGE Nutrition API routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from auth import get_current_user

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, validate_daily_plan,
    find_substitutes, recalculate_substitution_portion, FOOD_INDEX,
    FORGE_COACH_METHODOLOGY, sum_plan_totals,
)


class NutritionAssessmentIn(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    height_cm: float = Field(gt=0, le=280)
    age: int = Field(ge=10, le=120)
    sex: str = "male"
    goal: str = "maintenance"
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


def owned_nutrition_target(user: dict, requested: Optional[str] = None) -> str:
    if user.get("role") == "SUPER_ADMIN":
        return requested or user["id"]
    return user["id"]


@router.get("/assessment")
async def get_assessment(user=Depends(get_current_user)):
    db = user.get("_db") or user.get("request") if False else None
    return {"message": "Use POST /api/nutrition/assessment to submit"}


@router.post("/assessment")
async def save_assessment(payload: NutritionAssessmentIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"] if user.get("role") == "ATHLETE" else user["id"]
    doc = payload.model_dump()
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
    if not na:
        raise HTTPException(400, "Assessment nutricional nÃ£o encontrado. FaÃ§a o questionÃ¡rio primeiro.")
    targets = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"))
    plan = generate_daily_plan(targets, na, na.get("meal_count", 4))
    doc = {"profile_id": target, "user_id": target, "plan": plan, "created_at": datetime.now(timezone.utc).isoformat(),
           "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
           "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"]}
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
    subs = find_substitutes(
        food_id, na, current_foods, max_results=3, orig_grams=original.get("grams", 100),
        goal=na.get("goal", "maintenance"), meal=foods,
        daily_totals=plan.get("daily_totals", {}), targets=plan.get("targets", {}))

    options = []
    matched = None
    for s in subs:
        fid, grams, reason = s[0], s[1], s[2]
        opt = {"food_id": fid, "grams": grams, "food": FOOD_INDEX.get(fid, {}), "reason": reason}
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

    # Backend remains the sole source of truth for grams/macros: the persisted item uses
    # exactly the food_id + grams the engine just recomputed, never anything the client sent.
    new_food_item = {"food_id": matched["food_id"], "grams": matched["grams"], "food": matched["food"]}
    foods[food_pos] = new_food_item
    meal["foods"] = foods
    meals[meal_idx] = meal
    plan["meals"] = meals
    new_totals = sum_plan_totals(meals)
    plan["daily_totals"] = new_totals

    # Targeted, precise field update instead of replacing the whole document — a concurrent
    # request touching a different meal/food never gets clobbered by this write.
    await db.nutrition_plans.update_one(
        {"profile_id": target},
        {"$set": {
            f"plan.meals.{meal_idx}.foods.{food_pos}": new_food_item,
            "plan.daily_totals": new_totals,
        }},
    )

    return {
        "original": food_id, "options": options, "applied": True,
        "meal_index": meal_idx, "food_index": food_pos,
        "food": new_food_item, "daily_totals": new_totals, "plan": plan,
    }


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

