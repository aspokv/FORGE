"""FORGE Training Engine — exercise substitution (Substituir) live API tests.

Reproduces the exact production bug: the Exercise Matching Engine correctly listed
alternatives for "Desenvolvimento com halteres" (Melhor substituicao: "Desenvolvimento
maquina Smith", Alternativa 2: "Arnold Press"), but tapping an alternative never
replaced the exercise in the workout. Root cause: the frontend's alternative button
only closed the modal (onClick={close}) — it never called any API, and the backend had
no mutating endpoint at all to persist a swap (only the read-only GET .../alternatives).

Fix: GET /exercises/{id}/alternatives now includes each alternative's id; a new
POST /exercises/substitute persists {original_exercise_id: new_exercise_id} on the
profile and returns the rebuilt program; engine.build_program_v2 applies persisted
substitutions to every session (both custom_program and algorithmic paths) via
_apply_exercise_substitutions, preserving sets/reps/rest/rir/technique/load/note exactly.
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

TEST_PASSWORD = "ExSubTest2026!"

ORIGINAL_EXERCISE_ID = "db-ohp"          # Desenvolvimento com halteres
BEST_ALTERNATIVE_ID = "smith-ohp"        # Desenvolvimento maquina Smith
SECOND_ALTERNATIVE_ID = "db-arnold-press"  # Arnold Press


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
        await db.set_logs.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Ex Sub Test Athlete", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    # onboarding_required=False + a minimal assessment/priorities: build_program_v2
    # checks onboarding_required BEFORE it even looks at custom_program, so a fresh
    # (still-onboarding) profile would return the onboarding placeholder regardless of
    # what custom_program holds — this fixture represents an athlete who already
    # completed onboarding and is now on the workout screen, same as the real bug report.
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Ex Sub Test Athlete", "automation_mode": "FORGE_ASSISTED",
        "assessment": {"Deltóide anterior": {"development": "proporcional", "priority": "normal"}},
        "priorities": ["Deltóide anterior"], "onboarding_required": False,
        "goal": "Hipertrofia", "experience": "Intermediário", "days": 3, "session_minutes": 60,
    })
    return uid, invite


async def _fetch_invite_token(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    return user["invite_token"]


def _create_athlete_with_ohp_session(email):
    """A deterministic custom_program (Program Builder) containing the exact reported
    exercise with a distinctive, checkable prescription — avoids depending on which
    exercise the algorithmic engine happens to pick for a given profile."""
    _run(_reset_athlete(email))
    token_row = _run(_fetch_invite_token(email))
    r = requests.post(f"{API}/auth/accept-invite", json={"token": token_row, "password": TEST_PASSWORD, "name": "Ex Sub Test Athlete"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    custom_program = {
        "profile_id": email,  # ignored server-side for ATHLETE callers, forced to caller's own id
        "name": "Programa de teste",
        "week": "Semana de teste",
        "session_minutes": 60,
        "sessions": [{
            "day": 1, "label": "Upper A", "demand": "MODERATE", "focus": ["Deltóide anterior"],
            "exercises": [{
                "exercise_id": ORIGINAL_EXERCISE_ID, "sets": 4, "reps": "6-8", "rir": "1-2",
                "rest": "3 min", "load": 42.5, "technique": "Straight Sets",
                "technique_id": "straight", "note": "nota de teste",
            }],
        }],
    }
    r = requests.post(f"{API}/custom-program", json=custom_program, headers=headers)
    assert r.status_code == 200, f"custom-program save failed: {r.text}"
    return headers


def _exercise_item(program):
    return program["sessions"][0]["exercises"][0]


# ───────────────────────── 1. matching lists real, id-bearing alternatives ─────────────

def test_alternatives_endpoint_includes_ids_for_the_reported_exercise():
    headers = _create_athlete_with_ohp_session("exsub.list@example.com")
    r = requests.get(f"{API}/exercises/{ORIGINAL_EXERCISE_ID}/alternatives", headers=headers)
    assert r.status_code == 200, r.text
    alts = r.json()["alternatives"]
    assert len(alts) >= 2
    assert alts[0]["id"] == BEST_ALTERNATIVE_ID and alts[0]["name"]
    assert alts[1]["id"] == SECOND_ALTERNATIVE_ID and alts[1]["name"]


# ───────────────────────── 2/3. production case: best alternative applies + persists ───

def test_production_case_smith_ohp_substitution_applies_preserves_prescription_and_persists():
    headers = _create_athlete_with_ohp_session("exsub.smith@example.com")

    apply = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": ORIGINAL_EXERCISE_ID, "new_exercise_id": BEST_ALTERNATIVE_ID,
    }, headers=headers)
    assert apply.status_code == 200, apply.text
    body = apply.json()
    assert body["exercise_substitutions"][ORIGINAL_EXERCISE_ID] == BEST_ALTERNATIVE_ID

    item = _exercise_item(body["program"])
    assert item["exercise_id"] == BEST_ALTERNATIVE_ID, "exercise was not actually replaced in the returned program"
    # sets/reps/rest/rir/technique/load/note preserved exactly (same role/pattern swap)
    assert item["sets"] == 4
    assert item["reps"] == "6-8"
    assert item["rir"] == "1-2"
    assert item["rest"] == "3 min"
    assert item["load"] == 42.5
    assert item["technique_id"] == "straight"
    assert item["note"] == "nota de teste"

    # RELOAD (simulates logout/login — a fresh bootstrap call): substitution survives
    reloaded = requests.get(f"{API}/bootstrap", headers=headers)
    assert reloaded.status_code == 200
    reloaded_item = _exercise_item(reloaded.json()["program"])
    assert reloaded_item["exercise_id"] == BEST_ALTERNATIVE_ID, "substitution did not survive reload"
    assert reloaded_item["sets"] == 4 and reloaded_item["rest"] == "3 min"


# ───────────────────────── 4. second alternative also applies correctly ────────────────

def test_second_alternative_arnold_press_substitution_also_applies_and_persists():
    headers = _create_athlete_with_ohp_session("exsub.arnold@example.com")

    apply = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": ORIGINAL_EXERCISE_ID, "new_exercise_id": SECOND_ALTERNATIVE_ID,
    }, headers=headers)
    assert apply.status_code == 200, apply.text
    item = _exercise_item(apply.json()["program"])
    assert item["exercise_id"] == SECOND_ALTERNATIVE_ID
    assert item["sets"] == 4 and item["reps"] == "6-8" and item["load"] == 42.5

    reloaded = requests.get(f"{API}/bootstrap", headers=headers)
    reloaded_item = _exercise_item(reloaded.json()["program"])
    assert reloaded_item["exercise_id"] == SECOND_ALTERNATIVE_ID, "second alternative did not survive reload"


# ───────────────────────── 5. arbitrary/incompatible swap is rejected ──────────────────

def test_substitution_rejects_an_exercise_that_was_never_offered_as_an_alternative():
    """Never an arbitrary swap — only a real candidate from the matching engine's own
    alternative_ids for that exact exercise (guarantees same muscle/pattern, so the
    existing prescription stays valid without a separate adaptation step)."""
    headers = _create_athlete_with_ohp_session("exsub.reject@example.com")
    r = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": ORIGINAL_EXERCISE_ID, "new_exercise_id": "leg-press",
    }, headers=headers)
    assert r.status_code == 400


# ───────────────────────── 6. cross-athlete isolation ───────────────────────────────────

def test_other_athlete_cannot_alter_or_see_effects_on_my_program():
    headers_a = _create_athlete_with_ohp_session("exsub.isoa@example.com")
    headers_b = _create_athlete_with_ohp_session("exsub.isob@example.com")

    apply_b = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": ORIGINAL_EXERCISE_ID, "new_exercise_id": BEST_ALTERNATIVE_ID,
    }, headers=headers_b)
    assert apply_b.status_code == 200

    boot_a = requests.get(f"{API}/bootstrap", headers=headers_a)
    item_a = _exercise_item(boot_a.json()["program"])
    assert item_a["exercise_id"] == ORIGINAL_EXERCISE_ID, "athlete A's program changed as a side effect of athlete B's substitution"
