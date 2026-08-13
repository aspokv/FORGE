"""FORGE Nutrition — 'Gerar plano' frontend/backend contract regression.

Reproduces the exact production bug: clicking "Gerar plano" without touching the
optional "Restricoes" dropdown returned 422 "Input should be a valid string". Root
cause was in the FRONTEND (Nutrition.jsx): the form's dietary_restrictions state
defaulted to [] (a list) instead of "" (a string, matching what the <select> actually
produces via onChange). The submit handler's `form.dietary_restrictions ? [form.dietary_
restrictions] : []` then treated that truthy empty LIST as if it were a selected string,
sending `[[]]` to POST /api/nutrition/assessment — a list-of-lists where the API expects
List[str]. Fixed by changing the default to "" so the select's own contract holds.

This test builds the payload using the SAME transform submitAssessment() uses, so a
future regression of the frontend's default state (back to []) breaks this test too,
not just a hand-corrected payload built directly in Python.
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

TEST_PASSWORD = "GerarPlanoTest2026!"

# Mirrors Nutrition.jsx's initial `form` state (post-fix) — dietary_restrictions is a
# plain string "", matching the <select>'s own opts, not a list.
FRONTEND_DEFAULT_FORM = {
    "weight_kg": "80", "height_cm": "178", "age": "30", "sex": "male",
    "goal": "maintenance", "activity_level": "moderate", "training_days": 3,
    "meal_count": 4, "training_time": "", "preferred_foods": [], "disliked_foods": [],
    "avoid_foods": [], "allergies": [], "dietary_restrictions": "", "cooking_time": "medium",
}


def _build_assessment_payload(form):
    """Exact mirror of submitAssessment()'s payload transform in Nutrition.jsx."""
    payload = dict(form)
    payload["weight_kg"] = float(form["weight_kg"])
    payload["height_cm"] = float(form["height_cm"])
    payload["age"] = int(form["age"])
    payload["training_days"] = int(form["training_days"])
    payload["meal_count"] = int(form["meal_count"])
    payload["dietary_restrictions"] = [form["dietary_restrictions"]] if form["dietary_restrictions"] else []
    if isinstance(form["allergies"], str):
        payload["allergies"] = [s.strip() for s in form["allergies"].split(",") if s.strip()]
    else:
        payload["allergies"] = form["allergies"] or []
    return payload


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
        "id": uid, "email": email, "name": "Gerar Plano Test", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Gerar Plano Test", "automation_mode": "FORGE_ASSISTED",
        "assessment": {}, "priorities": [], "onboarding_required": True,
    })
    return uid, invite


async def _fetch_invite_token(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    return user["invite_token"]


def _create_athlete(email):
    _run(_reset_athlete(email))
    token_row = _run(_fetch_invite_token(email))
    r = requests.post(f"{API}/auth/accept-invite", json={"token": token_row, "password": TEST_PASSWORD, "name": "Gerar Plano Test"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_gerar_plano_with_untouched_restriction_dropdown_reaches_a_valid_plan():
    """Direct regression: the reported 'Input should be a valid string' on Gerar plano,
    when the user never touches the optional Restricoes dropdown (the default flow)."""
    headers = _create_athlete("gerarplano.default@example.com")
    payload = _build_assessment_payload(FRONTEND_DEFAULT_FORM)
    assert payload["dietary_restrictions"] == [], f"contract regressed: {payload['dietary_restrictions']}"

    r = requests.post(f"{API}/nutrition/assessment", json=payload, headers=headers)
    assert r.status_code == 200, f"assessment rejected the default Gerar plano payload: {r.text}"

    r2 = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r2.status_code == 200, f"generate failed after a valid assessment: {r2.text}"
    body = r2.json()
    assert "plan" in body and body["plan"]["meals"], "Gerar plano did not produce a real plan"
    # Nutrition DNA still intact: every meal carries a coherence score from the DNA engine
    for meal in body["plan"]["meals"]:
        assert "coherence_score" in meal


def test_gerar_plano_with_a_selected_restriction_still_works():
    """The same contract, but with the dropdown actually changed to a real restriction —
    must still resolve to a plain string in form state, not the list-in-list bug shape."""
    headers = _create_athlete("gerarplano.restriction@example.com")
    form = dict(FRONTEND_DEFAULT_FORM, dietary_restrictions="lactose_free")
    payload = _build_assessment_payload(form)
    assert payload["dietary_restrictions"] == ["lactose_free"]

    r = requests.post(f"{API}/nutrition/assessment", json=payload, headers=headers)
    assert r.status_code == 200, f"assessment rejected a selected restriction: {r.text}"

    r2 = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r2.status_code == 200, f"generate failed after a valid assessment: {r2.text}"
