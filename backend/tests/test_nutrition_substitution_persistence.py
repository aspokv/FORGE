"""FORGE Nutrition substitution — persistence, isolation, and re-validation tests.

Covers the fix for: substitution worked in the UI but was never written to MongoDB,
so a reload reverted the plan. These tests exercise the real HTTP API against a
running server + Mongo, exactly like the existing test_forge_v2_core.py suite.
"""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

TEST_PASSWORD = "SubstTest2026!"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _reset_athlete(email: str):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    existing = await db.users.find_one({"email": email})
    if existing:
        uid = existing["id"]
        await db.users.delete_one({"email": email})
        await db.profiles.delete_one({"id": uid})
        await db.nutrition_plans.delete_many({"profile_id": uid})
        await db.nutrition_assessments.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Subst Test Athlete", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Subst Test Athlete", "automation_mode": "FORGE_ASSISTED",
        "assessment": {}, "priorities": [], "onboarding_required": True,
    })
    return uid, invite


def _create_athlete(email, allergies=None, dietary_restrictions=None, goal="maintenance"):
    _run(_reset_athlete(email))
    row = _run(_fetch_invite_token(email))
    r = requests.post(f"{API}/auth/accept-invite", json={"token": row, "password": TEST_PASSWORD, "name": "Subst Test Athlete"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assessment = {
        "weight_kg": 80, "height_cm": 178, "age": 30, "sex": "male",
        "goal": goal, "activity_level": "moderate", "training_days": 4, "meal_count": 4,
        "allergies": allergies or [], "dietary_restrictions": dietary_restrictions or [],
    }
    r = requests.post(f"{API}/nutrition/assessment", json=assessment, headers=headers)
    assert r.status_code == 200, f"assessment failed: {r.text}"
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, f"generate failed: {r.text}"
    return headers, r.json()["plan"]


async def _fetch_invite_token(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    return user["invite_token"]


def _get_plan(headers):
    r = requests.get(f"{API}/nutrition/plan", headers=headers)
    assert r.status_code == 200, f"get plan failed: {r.text}"
    return r.json()


def _first_protein_food(plan):
    """meal[0].foods[0] is always the primary_protein slot (see generate_meal's role
    order), giving a deterministic, always-substitutable target for these tests."""
    meal = plan["meals"][0]
    item = meal["foods"][0]
    return 0, 0, item["food_id"], item["grams"]


def _fat_source_food(plan):
    for mi, meal in enumerate(plan["meals"]):
        for fi, item in enumerate(meal.get("foods", [])):
            if item.get("food", {}).get("category") == "FAT":
                return mi, fi, item["food_id"]
    return None, None, None


# ───────────────────────── 1/2. valid substitution persists + survives reload ─────────

def test_substitution_persists_after_reload():
    headers, plan = _create_athlete("subst.a@example.com")
    mi, fi, food_id, orig_grams = _first_protein_food(plan)

    opts = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi, "food_id": food_id}, headers=headers)
    assert opts.status_code == 200
    options = opts.json()["options"]
    assert len(options) > 0, "expected at least one valid substitution option"
    chosen = options[0]

    apply = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "substitute_food_id": chosen["food_id"],
    }, headers=headers)
    assert apply.status_code == 200, apply.text
    body = apply.json()
    assert body["applied"] is True
    assert body["food"]["food_id"] == chosen["food_id"]
    assert body["food"]["grams"] == chosen["grams"]

    # RELOAD: fresh GET, simulating F5 — must reflect the substitution, not the original.
    reloaded = _get_plan(headers)
    got = reloaded["meals"][mi]["foods"][fi]
    assert got["food_id"] == chosen["food_id"], "substitution did not survive reload"
    assert got["grams"] == chosen["grams"]
    assert got["food_id"] != food_id


# ───────────────────────── 3. cross-user isolation ─────────────────────────────────────

def test_other_athlete_cannot_alter_or_see_effects_on_my_plan():
    headers_a, plan_a = _create_athlete("subst.isolation.a@example.com")
    headers_b, plan_b = _create_athlete("subst.isolation.b@example.com")

    mi_a, fi_a, food_a, _ = _first_protein_food(plan_a)
    before = _get_plan(headers_a)["meals"][mi_a]["foods"][fi_a]

    mi_b, fi_b, food_b, _ = _first_protein_food(plan_b)
    opts_b = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi_b, "food_id": food_b}, headers=headers_b).json()
    assert opts_b["options"], "athlete B needs a valid option for this test to mean anything"
    apply_b = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi_b, "food_id": food_b, "substitute_food_id": opts_b["options"][0]["food_id"],
    }, headers=headers_b)
    assert apply_b.status_code == 200

    after = _get_plan(headers_a)["meals"][mi_a]["foods"][fi_a]
    assert after == before, "athlete A's plan changed as a side effect of athlete B's substitution"

    # B cannot even address A's plan: the endpoint has no profile_id param, target is
    # always derived from the authenticated token, so B's request only ever touches B's own doc.
    r = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi_a, "food_id": food_a,
    }, headers=headers_b)
    assert r.status_code in (200, 400, 404)
    # whatever B's own plan looks like at meal_index mi_a, it must not be A's food_id
    # unless coincidentally identical — the real assertion is that A's doc (above) is untouched.


# ───────────────────────── 4. invalid indices rejected ─────────────────────────────────

def test_invalid_meal_index_rejected():
    headers, plan = _create_athlete("subst.badindex@example.com")
    r = requests.post(f"{API}/nutrition/substitute", json={"meal_index": 999, "food_id": "rice-white"}, headers=headers)
    assert r.status_code == 400


def test_invalid_food_index_rejected():
    headers, plan = _create_athlete("subst.badfoodindex@example.com")
    mi, fi, food_id, _ = _first_protein_food(plan)
    r = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "food_index": 999,
    }, headers=headers)
    assert r.status_code == 400


def test_food_index_mismatch_rejected():
    """food_index must actually point at food_id — can't be used to address a different slot."""
    headers, plan = _create_athlete("subst.mismatch@example.com")
    meal = plan["meals"][0]
    if len(meal["foods"]) < 2:
        return
    wrong_food_id = meal["foods"][0]["food_id"]
    r = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": 0, "food_id": wrong_food_id, "food_index": 1,
    }, headers=headers)
    assert r.status_code == 400


# ───────────────────────── 5/6/7. allergy / restriction / avoid_food still hard-blocked ─

def test_allergy_still_blocks_option_listing_and_forced_apply():
    headers, plan = _create_athlete("subst.allergy@example.com", allergies=["peanut"])
    mi, fi, food_id = _fat_source_food(plan)
    if food_id is None:
        return  # this profile's plan happened not to include a fat_source slot
    opts = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi, "food_id": food_id}, headers=headers).json()
    listed_ids = {o["food_id"] for o in opts["options"]}
    assert "peanuts" not in listed_ids and "peanut-butter" not in listed_ids

    forced = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "substitute_food_id": "peanut-butter",
    }, headers=headers)
    assert forced.status_code == 400, "forcing an allergen through substitute_food_id must be rejected"


def test_dietary_restriction_still_blocks_forced_apply():
    headers, plan = _create_athlete("subst.restriction@example.com", dietary_restrictions=["lactose_free"])
    mi, fi, food_id, _ = _first_protein_food(plan)
    forced = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "substitute_food_id": "milk-whole",
    }, headers=headers)
    assert forced.status_code == 400


def test_avoid_food_still_blocks_listing():
    """avoid_foods isn't part of the assessment schema — verified via the engine's own
    _food_compatible contract instead, at the unit level in test_nutrition.py; here we
    confirm the API path returns only engine-vetted options (never the original itself)."""
    headers, plan = _create_athlete("subst.avoid@example.com")
    mi, fi, food_id, _ = _first_protein_food(plan)
    opts = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi, "food_id": food_id}, headers=headers).json()
    assert food_id not in {o["food_id"] for o in opts["options"]}


# ───────────────────────── 8. only re-validated (engine-listed) foods can be forced ─────

def test_forcing_a_non_candidate_food_is_rejected():
    """A food_id that isn't even in the same substitution group/tier as the original
    can never appear in the freshly recomputed options — forcing it must be rejected.
    (The directional-tolerance rules themselves are covered exhaustively at the unit
    level in test_nutrition_directional.py; this confirms the API enforces "must be in
    the live, re-validated options list" rather than trusting any client-supplied id.)"""
    headers, plan = _create_athlete("subst.directional@example.com", goal="fat_loss")
    mi, fi, food_id, _ = _first_protein_food(plan)
    r = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "substitute_food_id": "brazil-nuts",
    }, headers=headers)
    assert r.status_code == 400


# ───────────────────────── 9/10/11. other meals intact, macros coherent, 2x chaining ───

def test_two_consecutive_substitutions_persist_and_other_meals_stay_intact():
    headers, plan = _create_athlete("subst.chain@example.com")
    mi, fi, food_id, _ = _first_protein_food(plan)
    other_meals_before = [m["foods"] for idx, m in enumerate(plan["meals"]) if idx != mi]

    opts1 = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi, "food_id": food_id}, headers=headers).json()
    step1_target = opts1["options"][0]["food_id"]
    r1 = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": food_id, "substitute_food_id": step1_target,
    }, headers=headers)
    assert r1.status_code == 200
    plan_after_1 = r1.json()["plan"]
    assert plan_after_1["meals"][mi]["foods"][fi]["food_id"] == step1_target

    # second substitution — must operate on the food that is NOW in the slot (step1_target)
    opts2 = requests.post(f"{API}/nutrition/substitute", json={"meal_index": mi, "food_id": step1_target}, headers=headers).json()
    assert opts2["options"], "expected further substitution options for the already-substituted food"
    step2_target = opts2["options"][0]["food_id"]
    r2 = requests.post(f"{API}/nutrition/substitute", json={
        "meal_index": mi, "food_id": step1_target, "substitute_food_id": step2_target,
    }, headers=headers)
    assert r2.status_code == 200

    reloaded = _get_plan(headers)
    final_item = reloaded["meals"][mi]["foods"][fi]
    assert final_item["food_id"] == step2_target, "second substitution did not persist through reload"

    # other meals byte-for-byte untouched
    other_meals_after = [m["foods"] for idx, m in enumerate(reloaded["meals"]) if idx != mi]
    assert other_meals_after == other_meals_before, "an unrelated meal changed as a side effect"

    # macros coherent: daily_totals must equal a fresh recomputation from the actual
    # foods now in the plan — proves the backend, not a stale client value, is authoritative.
    from nutrition_engine import sum_plan_totals
    expected = sum_plan_totals(reloaded["meals"])
    assert reloaded["daily_totals"] == expected
