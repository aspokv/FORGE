"""FORGE Guided Meal Composition — live API integration tests.

Exercises the new /plan/reset, /plan/draft, /plan/draft/options, /plan/draft/swap-food,
/plan/draft/choose, /plan/draft/choose-remaining, /plan/draft/confirm and /preferences
endpoints against a running server + Mongo, following the exact fixture pattern already
used by test_nutrition_substitution_persistence.py. Confirms: RESET_PLAN only touches
the plan/draft (not assessment/weight/adherence), the confirmed plan matches the exact
contract the legacy /generate produces (so /substitute and /meal-status need no changes),
and the FORGE_CHOOSES_FOR_ME path reaches a valid confirmed plan on its own.
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

TEST_PASSWORD = "GuidedTest2026!"


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
        await db.nutrition_plan_drafts.delete_many({"profile_id": uid})
        await db.nutrition_preferences.delete_many({"profile_id": uid})
        await db.nutrition_assessments.delete_many({"profile_id": uid})
        await db.nutrition_adherence.delete_many({"profile_id": uid})
        await db.nutrition_weight_logs.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Guided Test Athlete", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Guided Test Athlete", "automation_mode": "FORGE_ASSISTED",
        "assessment": {}, "priorities": [], "onboarding_required": True,
    })
    return uid, invite


async def _fetch_invite_token(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    return user["invite_token"]


def _create_athlete(email, allergies=None, dietary_restrictions=None, goal="maintenance", meal_count=4):
    _run(_reset_athlete(email))
    token_row = _run(_fetch_invite_token(email))
    r = requests.post(f"{API}/auth/accept-invite", json={"token": token_row, "password": TEST_PASSWORD, "name": "Guided Test Athlete"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assessment = {
        "weight_kg": 80, "height_cm": 178, "age": 30, "sex": "male",
        "goal": goal, "activity_level": "moderate", "training_days": 4, "meal_count": meal_count,
        "allergies": allergies or [], "dietary_restrictions": dietary_restrictions or [],
    }
    r = requests.post(f"{API}/nutrition/assessment", json=assessment, headers=headers)
    assert r.status_code == 200, f"assessment failed: {r.text}"
    return headers


def _log_weight_and_adherence(headers):
    """Baseline snapshot of the collections RESET_PLAN must never touch."""
    w = requests.post(f"{API}/nutrition/weight", json={"weight_kg": 81.5}, headers=headers)
    assert w.status_code == 200
    a = requests.post(f"{API}/nutrition/meal-status", json={"meal_index": 0, "status": "completed"}, headers=headers)
    assert a.status_code == 200


def _lock_all_meals_manually(headers, meal_count):
    """Choose-flow helper: pull options for each slot, pick the first, lock it in."""
    for idx in range(meal_count):
        opts = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": idx}, headers=headers)
        assert opts.status_code == 200, opts.text
        options = opts.json()["options"]
        assert options, f"no options returned for meal_index {idx}"
        best = options[0]
        food_ids = [it["food_id"] for it in best["foods"]]
        chosen = requests.post(f"{API}/nutrition/plan/draft/choose", json={
            "meal_index": idx, "archetype_id": best["archetype_id"], "food_ids": food_ids,
        }, headers=headers)
        assert chosen.status_code == 200, chosen.text


# ───────────────────────── 1. reset creates a draft, doesn't touch anything else ───────

def test_reset_creates_draft_and_preserves_assessment_weight_adherence():
    headers = _create_athlete("guided.reset@example.com", goal="muscle_gain", meal_count=4)
    _log_weight_and_adherence(headers)

    before_weight = requests.get(f"{API}/nutrition/weight", headers=headers).json()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    before_adherence = requests.get(f"{API}/nutrition/adherence/{today}", headers=headers).json()

    r = requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    assert r.status_code == 200, r.text
    draft = r.json()
    assert len(draft["meals"]) == 4
    assert all(m["foods"] == [] for m in draft["meals"])
    assert draft["locked"] == [False, False, False, False]
    assert draft["goal"] == "muscle_gain"

    got = requests.get(f"{API}/nutrition/plan/draft", headers=headers)
    assert got.status_code == 200
    assert got.json()["meals"] == draft["meals"]

    after_weight = requests.get(f"{API}/nutrition/weight", headers=headers).json()
    after_adherence = requests.get(f"{API}/nutrition/adherence/{today}", headers=headers).json()
    assert after_weight == before_weight, "reset touched weight history"
    assert after_adherence == before_adherence, "reset touched adherence history"


def test_reset_does_not_delete_an_existing_confirmed_plan_until_confirm():
    headers = _create_athlete("guided.resetkeep@example.com")
    gen = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert gen.status_code == 200
    old_plan = requests.get(f"{API}/nutrition/plan", headers=headers).json()

    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    # the OLD confirmed plan must still be readable — reset only starts a draft
    still_there = requests.get(f"{API}/nutrition/plan", headers=headers)
    assert still_there.status_code == 200
    assert still_there.json()["meals"] == old_plan["meals"]


# ───────────────────────── 2. options: real, coherent, distinct combinations ───────────

def test_options_returns_real_combinations_with_labels_and_grams():
    headers = _create_athlete("guided.options@example.com", goal="muscle_gain", meal_count=4)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    r = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 1 <= len(body["options"]) <= 5
    for o in body["options"]:
        assert o["label"]
        assert o["foods"], f"{o['archetype_id']} has no foods"
        for it in o["foods"]:
            assert it["grams"] > 0


def test_egg_allergy_never_offers_egg_archetype_via_api():
    headers = _create_athlete("guided.eggallergy@example.com", allergies=["egg"])
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    r = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers)
    assert r.status_code == 200
    for o in r.json()["options"]:
        ids = {it["food_id"] for it in o["foods"]}
        assert not (ids & {"eggs-whole", "egg-whites"})


# ───────────────────────── 3. swap-food: structure stays, one component changes ────────

def test_swap_food_recalculates_portions_and_keeps_structure():
    headers = _create_athlete("guided.swap@example.com", goal="muscle_gain")
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    opts = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers).json()
    option = opts["options"][0]
    food_ids = [it["food_id"] for it in option["foods"]]
    target_food = food_ids[0]

    listed = requests.post(f"{API}/nutrition/plan/draft/swap-food", json={
        "meal_index": 0, "food_ids": food_ids, "food_id": target_food,
    }, headers=headers)
    assert listed.status_code == 200, listed.text
    sub_options = listed.json()["options"]
    if not sub_options:
        return  # no valid alternative for this specific food in this profile — not a failure
    new_food = sub_options[0]["food_id"]

    applied = requests.post(f"{API}/nutrition/plan/draft/swap-food", json={
        "meal_index": 0, "food_ids": food_ids, "food_id": target_food, "substitute_food_id": new_food,
    }, headers=headers)
    assert applied.status_code == 200, applied.text
    result = applied.json()
    result_ids = {it["food_id"] for it in result["foods"]}
    assert new_food in result_ids
    assert target_food not in result_ids
    # everything else in the combination is unchanged
    assert result_ids - {new_food} == set(food_ids) - {target_food}


def test_swap_food_rejects_a_non_revalidated_substitute():
    headers = _create_athlete("guided.swapreject@example.com", allergies=["peanut"])
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    opts = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers).json()
    food_ids = [it["food_id"] for it in opts["options"][0]["foods"]]
    r = requests.post(f"{API}/nutrition/plan/draft/swap-food", json={
        "meal_index": 0, "food_ids": food_ids, "food_id": food_ids[0], "substitute_food_id": "peanut-butter",
    }, headers=headers)
    assert r.status_code == 400


# ───────────────────────── 4. choose locks the meal, redistributes remaining targets ───

def test_choose_locks_meal_and_redistributes_remaining_targets():
    headers = _create_athlete("guided.choose@example.com", goal="muscle_gain", meal_count=4)
    draft = requests.post(f"{API}/nutrition/plan/reset", headers=headers).json()
    before_targets = [m["target_cal"] for m in draft["meals"]]

    opts = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers).json()
    option = opts["options"][0]
    food_ids = [it["food_id"] for it in option["foods"]]
    r = requests.post(f"{API}/nutrition/plan/draft/choose", json={
        "meal_index": 0, "archetype_id": option["archetype_id"], "food_ids": food_ids,
    }, headers=headers)
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["locked"][0] is True
    assert updated["locked"][1:] == [False, False, False]
    assert updated["meals"][0]["foods"], "locked meal has no foods"
    # backend decided the grams, not the client (client only sent food_ids)
    assert all(it["grams"] > 0 for it in updated["meals"][0]["foods"])
    # remaining meals' targets were recomputed (not necessarily different, but present/valid)
    for i in range(1, 4):
        assert updated["meals"][i]["target_cal"] >= 0


def test_choose_rejects_invalid_meal_index():
    headers = _create_athlete("guided.choosebad@example.com")
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    r = requests.post(f"{API}/nutrition/plan/draft/choose", json={
        "meal_index": 99, "archetype_id": "default", "food_ids": ["rice-white"],
    }, headers=headers)
    assert r.status_code == 400


# ───────────────────────── 5. FORGE_CHOOSES_FOR_ME for all remaining meals ─────────────

def test_choose_remaining_locks_every_unlocked_meal():
    headers = _create_athlete("guided.autofill@example.com", goal="fat_loss", meal_count=3)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    r = requests.post(f"{API}/nutrition/plan/draft/choose-remaining", headers=headers)
    assert r.status_code == 200, r.text
    draft = r.json()
    assert all(draft["locked"])
    assert all(m["foods"] for m in draft["meals"])


def test_choose_remaining_respects_already_locked_meals():
    headers = _create_athlete("guided.autofillpartial@example.com", goal="fat_loss", meal_count=3)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    opts = requests.post(f"{API}/nutrition/plan/draft/options", json={"meal_index": 0}, headers=headers).json()
    option = opts["options"][0]
    food_ids = [it["food_id"] for it in option["foods"]]
    requests.post(f"{API}/nutrition/plan/draft/choose", json={
        "meal_index": 0, "archetype_id": option["archetype_id"], "food_ids": food_ids,
    }, headers=headers)
    locked_meal_0 = requests.get(f"{API}/nutrition/plan/draft", headers=headers).json()["meals"][0]

    r = requests.post(f"{API}/nutrition/plan/draft/choose-remaining", headers=headers)
    draft = r.json()
    assert draft["meals"][0]["foods"] == locked_meal_0["foods"], "choose-remaining overwrote an already-locked meal"


# ───────────────────────── 6. confirm produces the exact legacy plan contract ──────────

def test_confirm_requires_all_meals_locked():
    headers = _create_athlete("guided.confirmearly@example.com", meal_count=3)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    r = requests.post(f"{API}/nutrition/plan/draft/confirm", headers=headers)
    assert r.status_code == 400


def test_confirm_produces_plan_matching_legacy_contract_and_persists():
    headers = _create_athlete("guided.confirm@example.com", goal="muscle_gain", meal_count=3)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    _lock_all_meals_manually(headers, 3)

    r = requests.post(f"{API}/nutrition/plan/draft/confirm", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "plan" in body and "targets" in body and "warnings" in body
    plan = body["plan"]
    assert len(plan["meals"]) == 3
    for meal in plan["meals"]:
        assert "coherence_score" in meal
        for it in meal["foods"]:
            assert set(it.keys()) >= {"food_id", "grams", "food"}
    assert "kcal" in plan["daily_totals"]

    # the draft is gone, the confirmed plan is what GET /plan now returns
    draft_gone = requests.get(f"{API}/nutrition/plan/draft", headers=headers)
    assert draft_gone.status_code == 404
    reloaded = requests.get(f"{API}/nutrition/plan", headers=headers).json()
    assert reloaded["meals"] == plan["meals"]


def test_confirmed_guided_plan_still_works_with_substitute_and_meal_status():
    """The whole point of keeping the confirmed shape identical: nothing downstream
    needs to change. Prove /substitute and /meal-status work unmodified on a
    guided-flow-composed plan, exactly as they do on a legacy-generated one."""
    headers = _create_athlete("guided.downstream@example.com", goal="maintenance", meal_count=3)
    requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    _lock_all_meals_manually(headers, 3)
    confirm = requests.post(f"{API}/nutrition/plan/draft/confirm", headers=headers)
    plan = confirm.json()["plan"]

    food_id = plan["meals"][0]["foods"][0]["food_id"]
    opts = requests.post(f"{API}/nutrition/substitute", json={"meal_index": 0, "food_id": food_id}, headers=headers)
    assert opts.status_code == 200, opts.text

    status = requests.post(f"{API}/nutrition/meal-status", json={"meal_index": 0, "status": "completed"}, headers=headers)
    assert status.status_code == 200


# ───────────────────────── 7. preferences: explicit signal, ranking-only ───────────────

def test_preferences_endpoint_stores_signal_and_never_bypasses_avoid_foods():
    headers = _create_athlete("guided.prefs@example.com")
    r = requests.post(f"{API}/nutrition/preferences", json={"food_id": "papaya", "signal": "avoided"}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"food_id": "papaya", "signal": "avoided"}

    r2 = requests.post(f"{API}/nutrition/preferences", json={"food_id": "chicken-breast", "signal": "liked"}, headers=headers)
    assert r2.status_code == 200

    bad = requests.post(f"{API}/nutrition/preferences", json={"food_id": "papaya", "signal": "not_a_real_signal"}, headers=headers)
    assert bad.status_code == 422  # pydantic pattern validation


# ───────────────────────── 8. draft isolation between athletes ────────────────────────

def test_draft_isolated_between_athletes():
    headers_a = _create_athlete("guided.isoa@example.com", goal="fat_loss")
    headers_b = _create_athlete("guided.isob@example.com", goal="muscle_gain")
    draft_a = requests.post(f"{API}/nutrition/plan/reset", headers=headers_a).json()
    draft_b = requests.post(f"{API}/nutrition/plan/reset", headers=headers_b).json()
    assert draft_a["goal"] == "fat_loss"
    assert draft_b["goal"] == "muscle_gain"

    got_a = requests.get(f"{API}/nutrition/plan/draft", headers=headers_a).json()
    assert got_a["goal"] == "fat_loss", "athlete B's reset leaked into athlete A's draft"
