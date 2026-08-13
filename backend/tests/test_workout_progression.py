"""FORGE Training Engine — workout completion / program sequence progression.

Reproduces the production bug: in a sequential program (Push -> Pull -> Legs), the
athlete finishes "Push" and clicks "Concluir treino", but the app keeps showing "Push"
as active after refresh/reopen instead of advancing to "Pull" — because no backend
mechanism existed for tracking "which session in the sequence is next." sessions[0]
(what the frontend always rendered) was a pure, stateless function of the profile's
static config (days/split/experience), never influenced by what was actually completed.

Fix: a new persisted profile.current_session_day pointer, advanced by the new
POST /workout/complete (day-sequence order, never calendar date), consumed by
engine.build_program_v2 via _resolve_active_day() to select program["active_day"] on
every bootstrap — completely independent of session count per day or the wall clock.
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

TEST_PASSWORD = "WorkoutProgTest2026!"


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
        await db.recovery.delete_many({"profile_id": uid})
        await db.workout_completions.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Workout Prog Test", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Workout Prog Test", "automation_mode": "FORGE_ASSISTED",
        "assessment": {"Peitoral superior": {"development": "proporcional", "priority": "normal"}},
        "priorities": ["Peitoral superior"], "onboarding_required": False,
        "goal": "Hipertrofia", "experience": "Intermediário", "days": 3, "session_minutes": 60,
    })
    return uid, invite


async def _fetch_invite_token(email):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": email})
    return user["invite_token"]


def _create_athlete_with_ppl(email):
    """A deterministic 3-day Push/Pull/Legs custom_program — avoids depending on which
    split the algorithmic engine happens to choose for a given profile."""
    _run(_reset_athlete(email))
    token_row = _run(_fetch_invite_token(email))
    r = requests.post(f"{API}/auth/accept-invite", json={"token": token_row, "password": TEST_PASSWORD, "name": "Workout Prog Test"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    custom_program = {
        "profile_id": email, "name": "PPL de teste", "week": "Semana de teste", "session_minutes": 60,
        "sessions": [
            {"day": 1, "label": "Push", "demand": "MODERATE", "focus": ["Peitoral superior"],
             "exercises": [{"exercise_id": "db-ohp", "sets": 4, "reps": "6-8", "rir": "1-2", "rest": "3 min",
                            "load": 42.5, "technique": "Straight Sets", "technique_id": "straight", "note": ""}]},
            {"day": 2, "label": "Pull", "demand": "MODERATE", "focus": ["Costas / espessura"],
             "exercises": [{"exercise_id": "lat-pulldown", "sets": 3, "reps": "8-10", "rir": "1-2", "rest": "2 min",
                            "load": 62, "technique": "Straight Sets", "technique_id": "straight", "note": ""}]},
            {"day": 3, "label": "Legs", "demand": "HIGH", "focus": ["Quadríceps"],
             "exercises": [{"exercise_id": "leg-press", "sets": 4, "reps": "10-12", "rir": "1-2", "rest": "2 min",
                            "load": 120, "technique": "Straight Sets", "technique_id": "straight", "note": ""}]},
        ],
    }
    r = requests.post(f"{API}/custom-program", json=custom_program, headers=headers)
    assert r.status_code == 200, f"custom-program save failed: {r.text}"
    return headers, token


def _active_label(program):
    active = next((s for s in program["sessions"] if s["day"] == program["active_day"]), None)
    return active["label"] if active else None


# ───────────────────────── CASE 1: Push active -> complete -> Pull active ──────────────

def test_case1_completing_push_advances_to_pull():
    headers, _ = _create_athlete_with_ppl("wprog.case1@example.com")
    boot = requests.get(f"{API}/bootstrap", headers=headers).json()
    assert _active_label(boot["program"]) == "Push"

    r = requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["completed_day"] == 1
    assert body["next_day"] == 2
    assert _active_label(body["program"]) == "Pull"


# ───────────────────────── CASE 2: refresh keeps Pull active ───────────────────────────

def test_case2_refresh_after_completing_push_still_shows_pull():
    headers, _ = _create_athlete_with_ppl("wprog.case2@example.com")
    requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)

    reloaded = requests.get(f"{API}/bootstrap", headers=headers).json()
    assert _active_label(reloaded["program"]) == "Pull", "refresh reverted to Push instead of keeping Pull active"


# ───────────────────────── CASE 3: logout/login keeps Pull active ──────────────────────

def test_case3_logout_login_after_completing_push_still_shows_pull():
    headers, _ = _create_athlete_with_ppl("wprog.case3@example.com")
    requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)

    # "logout" (discard the old token) + "login" (fresh auth) — a real re-authentication,
    # not just reusing the same in-memory token.
    login = requests.post(f"{API}/auth/login", json={"email": "wprog.case3@example.com", "password": TEST_PASSWORD})
    assert login.status_code == 200, login.text
    new_headers = {"Authorization": f"Bearer {login.json()['token']}"}

    reloaded = requests.get(f"{API}/bootstrap", headers=new_headers).json()
    assert _active_label(reloaded["program"]) == "Pull", "relogin reverted to Push instead of keeping Pull active"


# ───────────────────────── CASE 4: two workouts same day, no date blocking ─────────────

def test_case4_two_workouts_same_day_no_date_blocking():
    headers, _ = _create_athlete_with_ppl("wprog.case4@example.com")

    r1 = requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)
    assert r1.status_code == 200
    assert _active_label(r1.json()["program"]) == "Pull"

    # Immediately complete Pull too — same request, same moment, no artificial 1/day gate.
    r2 = requests.post(f"{API}/workout/complete", json={"day": 2}, headers=headers)
    assert r2.status_code == 200, r2.text
    assert _active_label(r2.json()["program"]) == "Legs"

    reloaded = requests.get(f"{API}/bootstrap", headers=headers).json()
    assert _active_label(reloaded["program"]) == "Legs"

    # cycle wraps back to Push after Legs
    r3 = requests.post(f"{API}/workout/complete", json={"day": 3}, headers=headers)
    assert r3.status_code == 200
    assert _active_label(r3.json()["program"]) == "Push"


# ───────────────────────── CASE 5: substitution inside Push doesn't affect progression ─

def test_case5_exercise_substitution_inside_push_does_not_interfere_with_progression():
    headers, _ = _create_athlete_with_ppl("wprog.case5@example.com")

    sub = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": "db-ohp", "new_exercise_id": "smith-ohp",
    }, headers=headers)
    assert sub.status_code == 200, sub.text
    push_session = next(s for s in sub.json()["program"]["sessions"] if s["day"] == 1)
    assert push_session["exercises"][0]["exercise_id"] == "smith-ohp"

    complete = requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)
    assert complete.status_code == 200, complete.text
    assert _active_label(complete.json()["program"]) == "Pull", "substitution interfered with normal progression"

    # the substitution itself must still be in effect (Push, whenever it comes back
    # around the cycle) — completing a workout must not revert an unrelated persisted choice
    push_after = next(s for s in complete.json()["program"]["sessions"] if s["day"] == 1)
    assert push_after["exercises"][0]["exercise_id"] == "smith-ohp"


# ───────────────────────── CASE 6: completion never erases history ─────────────────────

def test_case6_completing_workout_does_not_erase_history_or_substitutions():
    headers, _ = _create_athlete_with_ppl("wprog.case6@example.com")

    # real history that must survive: a logged set, a substitution
    set_log = requests.post(f"{API}/sets", json={
        "profile_id": "wprog.case6@example.com", "exercise_id": "db-ohp",
        "set_number": 1, "weight": 40, "reps": 8, "rir": 2,
    }, headers=headers)
    assert set_log.status_code == 200

    alts = requests.get(f"{API}/exercises/lat-pulldown/alternatives", headers=headers).json()["alternatives"]
    assert alts, "expected at least one alternative for lat-pulldown"
    sub = requests.post(f"{API}/exercises/substitute", json={
        "original_exercise_id": "lat-pulldown", "new_exercise_id": alts[0]["id"],
    }, headers=headers)
    assert sub.status_code == 200, sub.text

    complete = requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers)
    assert complete.status_code == 200, complete.text

    reloaded = requests.get(f"{API}/bootstrap", headers=headers).json()
    # set history intact
    assert any(s["exercise_id"] == "db-ohp" and s["weight"] == 40 for s in reloaded["recent_sets"]), \
        "logged set history was lost after completing the workout"
    # substitution on the OTHER (not-yet-completed) day still applied
    pull_session = next(s for s in reloaded["program"]["sessions"] if s["day"] == 2)
    assert pull_session["exercises"][0]["exercise_id"] == alts[0]["id"], \
        "persisted substitution was lost/reverted after completing an unrelated workout"
    # program correctly advanced too
    assert _active_label(reloaded["program"]) == "Pull"


# ───────────────────────── cross-athlete isolation (sanity) ────────────────────────────

def test_completion_isolated_between_athletes():
    headers_a, _ = _create_athlete_with_ppl("wprog.isoa@example.com")
    headers_b, _ = _create_athlete_with_ppl("wprog.isob@example.com")

    requests.post(f"{API}/workout/complete", json={"day": 1}, headers=headers_b)

    boot_a = requests.get(f"{API}/bootstrap", headers=headers_a).json()
    assert _active_label(boot_a["program"]) == "Push", "athlete A's progression changed as a side effect of athlete B completing a workout"
