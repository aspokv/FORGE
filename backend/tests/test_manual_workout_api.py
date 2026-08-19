"""FORGE manual workout — live API integration tests.

Exercises /api/workouts/manual/{parse,draft,preview,activate,versions} against a running
server + Mongo, using the same self-seeding fixture pattern as
test_nutrition_guided_flow_api.py. What these tests are really defending:

  - an athlete can only ever touch their own draft and their own plan;
  - activation replaces the plan but never the history (set_logs, workout_completions);
  - the sequence pointer restarts at day 1 of the imported plan, and /workout/complete
    then advances through the imported days like any other program;
  - a double click on "Ativar este treino" activates once, archives once.
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
MANUAL = f"{API}/workouts/manual"

TEST_PASSWORD = "ManualWorkout2026!"

EXAMPLE_1 = """SEGUNDA — PUSH
Supino reto — 4x8-10 — 90s — RIR 2
Supino inclinado com halteres — 3x10
Elevação lateral — 4x12-15

TERÇA — PULL
Puxada aberta — 4x8-10
Remada curvada — 4x8
Rosca direta — 3x10"""

EXAMPLE_LEGS = """PERNAS
Agachamento | 4 | 6-8 | descanso 2 min | RPE 8
Leg press | 4 | 10-12 | 90s"""


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
        await db.manual_workout_drafts.delete_many({"profile_id": uid})
        await db.program_versions.delete_many({"profile_id": uid})
        await db.workout_completions.delete_many({"profile_id": uid})
        await db.set_logs.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Manual Test Athlete", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "admin_note": "test fixture", "created_by": "test-suite",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Manual Test Athlete", "automation_mode": "FORGE_ASSISTED",
        "assessment": {}, "priorities": [], "days": 3, "session_minutes": 60,
        "experience": "Intermediário", "goal": "Hipertrofia", "onboarding_required": False,
    })
    return uid, invite


def _create_athlete(email):
    uid, invite = _run(_reset_athlete(email))
    r = requests.post(f"{API}/auth/accept-invite",
                      json={"token": invite, "password": TEST_PASSWORD, "name": "Manual Test Athlete"})
    assert r.status_code == 200, f"accept-invite failed: {r.text}"
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


async def _count(collection: str, profile_id: str) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    return await db[collection].count_documents({"profile_id": profile_id})


async def _profile(profile_id: str):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    return await db.profiles.find_one({"id": profile_id}, {"_id": 0})


def _parse(headers, text=EXAMPLE_1, name="Treino importado"):
    r = requests.post(f"{MANUAL}/parse", json={"text": text, "name": name}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _activate(headers, token=None, draft=None):
    body = {"activation_token": token or uuid.uuid4().hex}
    if draft is not None:
        body["draft"] = draft
    return requests.post(f"{MANUAL}/activate", json=body, headers=headers)


# --- parse + draft persistence -------------------------------------------------------

def test_parse_returns_structured_draft_and_persists_it():
    _, headers = _create_athlete("manual.parse@forge.test")
    data = _parse(headers)
    assert data["draft"]["stats"] == {"days": 2, "exercises": 6, "needs_review": 0}
    assert data["blocking_errors"] == []

    # refreshing the page must not lose the interpretation
    again = requests.get(f"{MANUAL}/draft", headers=headers)
    assert again.status_code == 200
    assert again.json()["draft"]["stats"]["exercises"] == 6


def test_parse_rejects_empty_and_unstructured_text():
    _, headers = _create_athlete("manual.reject@forge.test")
    for bad in ["", "   ", "oi, quanto custa a consultoria?"]:
        r = requests.post(f"{MANUAL}/parse", json={"text": bad}, headers=headers)
        assert r.status_code == 400, f"expected 400 for {bad!r}, got {r.status_code}"


def test_parse_rejects_oversized_text():
    _, headers = _create_athlete("manual.big@forge.test")
    r = requests.post(f"{MANUAL}/parse", json={"text": "Supino reto 4x10\n" * 3000}, headers=headers)
    assert r.status_code in (400, 413)


def test_draft_edits_are_saved_and_review_flags_recomputed_server_side():
    _, headers = _create_athlete("manual.edit@forge.test")
    data = _parse(headers, "PEITO\nZercher squat com corrente — 4x10")
    draft = data["draft"]
    assert draft["sessions"][0]["exercises"][0]["needs_review"] is True
    assert data["blocking_errors"]

    # athlete resolves it by picking a real exercise; the client also lies about the flag
    draft["sessions"][0]["exercises"][0]["exercise_id"] = "bb-squat"
    draft["sessions"][0]["exercises"][0]["needs_review"] = False
    r = requests.put(f"{MANUAL}/draft", json={"draft": draft}, headers=headers)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["draft"]["sessions"][0]["exercises"][0]["exercise_id"] == "bb-squat"
    assert saved["draft"]["sessions"][0]["exercises"][0]["needs_review"] is False
    assert saved["blocking_errors"] == []


def test_spoofed_review_flag_cannot_bypass_validation():
    _, headers = _create_athlete("manual.spoof@forge.test")
    draft = _parse(headers, "PEITO\nZercher squat com corrente — 4x10")["draft"]
    draft["sessions"][0]["exercises"][0]["needs_review"] = False  # lie, without fixing it
    r = requests.put(f"{MANUAL}/draft", json={"draft": draft}, headers=headers)
    assert r.status_code == 200
    assert r.json()["draft"]["sessions"][0]["exercises"][0]["needs_review"] is True
    assert r.json()["blocking_errors"]


# --- preview -------------------------------------------------------------------------

def test_preview_renders_program_without_activating_anything():
    uid, headers = _create_athlete("manual.preview@forge.test")
    _parse(headers)
    r = requests.post(f"{MANUAL}/preview", json={}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["program"]["sessions"][0]["label"] == "SEGUNDA — PUSH"
    assert body["replaces"]["source"] == "engine"

    # nothing was written to the profile
    profile = _run(_profile(uid))
    assert not profile.get("custom_program")
    assert profile.get("automation_mode") == "FORGE_ASSISTED"


# --- activation ----------------------------------------------------------------------

def test_activation_is_blocked_while_the_draft_has_open_questions():
    _, headers = _create_athlete("manual.blocked@forge.test")
    _parse(headers, "PEITO\nZercher squat com corrente — 4x10")
    r = _activate(headers)
    assert r.status_code == 422, r.text


def test_activation_applies_the_imported_plan_and_resets_the_pointer():
    uid, headers = _create_athlete("manual.activate@forge.test")
    _parse(headers)
    r = _activate(headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["already_applied"] is False
    assert body["program"]["logic"]["manual"] is True
    assert body["program"]["active_day"] == 1
    assert body["program"]["session"] == "SEGUNDA — PUSH"

    profile = _run(_profile(uid))
    assert profile["automation_mode"] == "FORGE_PRO"
    assert profile["current_session_day"] == 1
    assert profile["custom_program"]["source"] == "manual_import"


def test_imported_plan_shows_up_on_bootstrap_like_any_other_program():
    _, headers = _create_athlete("manual.bootstrap@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200
    r = requests.get(f"{API}/bootstrap", headers=headers)
    assert r.status_code == 200
    program = r.json()["program"]
    assert [s["label"] for s in program["sessions"]] == ["SEGUNDA — PUSH", "TERÇA — PULL"]
    assert program["active_day"] == 1


def test_completing_a_workout_advances_through_the_imported_days():
    _, headers = _create_athlete("manual.advance@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200

    r = requests.post(f"{API}/workout/complete", json={}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["completed_day"] == 1
    assert r.json()["next_day"] == 2
    assert r.json()["program"]["session"] == "TERÇA — PULL"


def test_activation_preserves_history_and_archives_the_previous_plan():
    uid, headers = _create_athlete("manual.history@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200

    # real training history against the first imported plan
    log = requests.post(f"{API}/sets", json={"exercise_id": "bb-bench-press", "set_number": 1,
                                             "weight": 80, "reps": 8, "rir": 2}, headers=headers)
    assert log.status_code == 200
    assert requests.post(f"{API}/workout/complete", json={}, headers=headers).status_code == 200
    sets_before = _run(_count("set_logs", uid))
    completions_before = _run(_count("workout_completions", uid))
    assert sets_before == 1 and completions_before == 1

    # second import replaces the plan
    _parse(headers, EXAMPLE_LEGS, "Treino de pernas")
    r = _activate(headers)
    assert r.status_code == 200, r.text
    assert r.json()["archived_version_id"]

    assert _run(_count("set_logs", uid)) == sets_before
    assert _run(_count("workout_completions", uid)) == completions_before
    profile = _run(_profile(uid))
    assert profile["current_session_day"] == 1          # cycle restarted
    assert profile["custom_program"]["sessions"][0]["label"] == "PERNAS"


def test_previous_plan_stays_recoverable():
    _, headers = _create_athlete("manual.versions@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200
    _parse(headers, EXAMPLE_LEGS, "Treino de pernas")
    assert _activate(headers).status_code == 200

    versions = requests.get(f"{MANUAL}/versions", headers=headers)
    assert versions.status_code == 200
    rows = versions.json()["versions"]
    assert len(rows) == 1 and rows[0]["days"] == 2

    restored = requests.post(f"{MANUAL}/versions/{rows[0]['id']}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["program"]["sessions"][0]["label"] == "SEGUNDA — PUSH"


def test_double_click_activates_once_and_archives_once():
    uid, headers = _create_athlete("manual.idempotent@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200          # first plan in place
    _parse(headers, EXAMPLE_LEGS, "Treino de pernas")

    token = uuid.uuid4().hex
    first = _activate(headers, token=token)
    second = _activate(headers, token=token)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["already_applied"] is False
    assert second.json()["already_applied"] is True
    # the second click archived nothing extra
    assert _run(_count("program_versions", uid)) == 1


# --- authorization -------------------------------------------------------------------

def test_athlete_cannot_reach_another_athletes_draft():
    uid_a, headers_a = _create_athlete("manual.owner.a@forge.test")
    _, headers_b = _create_athlete("manual.owner.b@forge.test")
    _parse(headers_a)

    # B asks for A's profile_id explicitly — the server resolves to B regardless
    r = requests.get(f"{MANUAL}/draft?profile_id={uid_a}", headers=headers_b)
    assert r.status_code == 200
    assert r.json()["draft"] is None


def test_athlete_cannot_activate_into_another_athletes_profile():
    uid_a, headers_a = _create_athlete("manual.owner.c@forge.test")
    _, headers_b = _create_athlete("manual.owner.d@forge.test")

    draft = _parse(headers_b, EXAMPLE_LEGS)["draft"]
    draft["profile_id"] = uid_a  # attempt to write into someone else's profile
    r = _activate(headers_b, draft=draft)
    assert r.status_code == 200

    profile_a = _run(_profile(uid_a))
    assert not profile_a.get("custom_program"), "A's plan must be untouched"


def test_manual_endpoints_require_authentication():
    for method, url, body in [
        ("post", f"{MANUAL}/parse", {"text": EXAMPLE_1}),
        ("get", f"{MANUAL}/draft", None),
        ("post", f"{MANUAL}/activate", {"activation_token": uuid.uuid4().hex}),
    ]:
        r = requests.request(method, url, json=body)
        assert r.status_code in (401, 403), f"{url} answered {r.status_code} without a token"
