"""FORGE — autosave do preenchimento do treino em andamento.

O que estes testes defendem: o que foi digitado volta depois de um refresh, o rascunho
NÃO se mistura com outro dia nem ressuscita de um ciclo antigo, e nada disso interfere
em POST /sets nem em POST /workout/complete, que continuam sendo os donos do registro
real e do ponteiro do programa.
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
DRAFT = f"{API}/workout/session-draft"

TEST_PASSWORD = "SessionDraft2026!"

INPUTS = {"bb-bench-press-0": {"weight": "82.5", "reps": "8"},
          "bb-bench-press-1": {"weight": "80", "reps": "7"}}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _reset(email: str):
    db = await _db()
    existing = await db.users.find_one({"email": email})
    if existing:
        uid = existing["id"]
        await db.users.delete_one({"email": email})
        await db.profiles.delete_one({"id": uid})
        await db.workout_session_drafts.delete_many({"profile_id": uid})
        await db.set_logs.delete_many({"profile_id": uid})
        await db.workout_completions.delete_many({"profile_id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Draft Test", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Draft Test", "days": 3, "session_minutes": 60,
        "experience": "Intermediário", "goal": "Hipertrofia", "assessment": {},
        "priorities": [], "onboarding_required": False,
    })
    return uid, invite


def _athlete(email):
    uid, invite = _run(_reset(email))
    r = requests.post(f"{API}/auth/accept-invite",
                      json={"token": invite, "password": TEST_PASSWORD, "name": "Draft Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


async def _age_draft(profile_id: str, hours: float):
    db = await _db()
    velho = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    await db.workout_session_drafts.update_one({"profile_id": profile_id},
                                               {"$set": {"updated_at": velho}})


# --- ida e volta ----------------------------------------------------------------------

def test_typed_values_come_back_after_a_refresh():
    _, headers = _athlete("draft.refresh@forge.test")
    r = requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["entries"] == 2

    voltou = requests.get(DRAFT, params={"day": 1}, headers=headers)
    assert voltou.status_code == 200
    assert voltou.json()["inputs"] == INPUTS
    assert voltou.json()["saved_at"]


def test_empty_draft_when_nothing_was_typed():
    _, headers = _athlete("draft.empty@forge.test")
    r = requests.get(DRAFT, params={"day": 1}, headers=headers)
    assert r.status_code == 200
    assert r.json()["inputs"] == {}


def test_saving_again_replaces_the_previous_draft():
    _, headers = _athlete("draft.replace@forge.test")
    requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers)
    novo = {"bb-bench-press-0": {"weight": "90", "reps": "6"}}
    requests.put(DRAFT, json={"day": 1, "inputs": novo}, headers=headers)
    assert requests.get(DRAFT, params={"day": 1}, headers=headers).json()["inputs"] == novo


# --- isolamento por sessão ------------------------------------------------------------

def test_draft_from_another_day_is_not_restored():
    """Rascunho do Push não pode aparecer pré-preenchido no Pull."""
    _, headers = _athlete("draft.otherday@forge.test")
    requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers)
    r = requests.get(DRAFT, params={"day": 2}, headers=headers)
    assert r.json()["inputs"] == {}
    assert r.json().get("reason") == "other_day"


def test_stale_draft_from_a_previous_cycle_is_not_restored():
    """Mesmo dia do split, semana passada: não pode ressuscitar carga velha por cima
    da sugestão de progressão."""
    uid, headers = _athlete("draft.stale@forge.test")
    requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers)
    _run(_age_draft(uid, 30))
    r = requests.get(DRAFT, params={"day": 1}, headers=headers)
    assert r.json()["inputs"] == {}
    assert r.json().get("reason") == "expired"


def test_recent_draft_is_still_restored():
    uid, headers = _athlete("draft.recent@forge.test")
    requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers)
    _run(_age_draft(uid, 2))
    assert requests.get(DRAFT, params={"day": 1}, headers=headers).json()["inputs"] == INPUTS


# --- sanitização e limites ------------------------------------------------------------

def test_oversized_payload_is_trimmed_not_stored_raw():
    _, headers = _athlete("draft.big@forge.test")
    enorme = {f"ex-{i}": {"weight": "1" * 200, "reps": "9" * 200} for i in range(900)}
    r = requests.put(DRAFT, json={"day": 1, "inputs": enorme}, headers=headers)
    assert r.status_code == 200
    assert r.json()["entries"] <= 400
    valores = requests.get(DRAFT, params={"day": 1}, headers=headers).json()["inputs"]
    assert all(len(v["weight"]) <= 12 and len(v["reps"]) <= 12 for v in valores.values())


def test_garbage_shapes_are_discarded():
    _, headers = _athlete("draft.garbage@forge.test")
    r = requests.put(DRAFT, json={"day": 1, "inputs": {
        "ok-0": {"weight": "80", "reps": "8"},
        "lixo-1": "nao e dicionario",
        "lixo-2": ["tambem nao"],
    }}, headers=headers)
    assert r.status_code == 200
    assert set(requests.get(DRAFT, params={"day": 1}, headers=headers).json()["inputs"]) == {"ok-0"}


# --- não interfere no fluxo existente -------------------------------------------------

def test_draft_does_not_log_sets_nor_move_the_program_pointer():
    uid, headers = _athlete("draft.isolation@forge.test")
    antes = requests.get(f"{API}/bootstrap", headers=headers).json()["program"]["active_day"]
    requests.put(DRAFT, json={"day": antes, "inputs": INPUTS}, headers=headers)

    depois = requests.get(f"{API}/bootstrap", headers=headers).json()["program"]["active_day"]
    assert depois == antes, "autosave nao pode mexer no ponteiro do programa"

    db_sets = _run(_count_sets(uid))
    assert db_sets == 0, "autosave nao registra serie — quem faz isso e POST /sets"


async def _count_sets(profile_id):
    db = await _db()
    return await db.set_logs.count_documents({"profile_id": profile_id})


def test_completing_the_workout_still_works_with_a_draft_open():
    _, headers = _athlete("draft.complete@forge.test")
    dia = requests.get(f"{API}/bootstrap", headers=headers).json()["program"]["active_day"]
    requests.put(DRAFT, json={"day": dia, "inputs": INPUTS}, headers=headers)
    r = requests.post(f"{API}/workout/complete", json={}, headers=headers)
    assert r.status_code == 200
    assert r.json()["next_day"] != r.json()["completed_day"]


# --- autorização ----------------------------------------------------------------------

def test_athlete_cannot_read_another_athletes_draft():
    uid_a, headers_a = _athlete("draft.owner.a@forge.test")
    _, headers_b = _athlete("draft.owner.b@forge.test")
    requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}, headers=headers_a)
    r = requests.get(DRAFT, params={"day": 1, "profile_id": uid_a}, headers=headers_b)
    assert r.json()["inputs"] == {}


def test_draft_endpoints_require_authentication():
    assert requests.get(DRAFT, params={"day": 1}).status_code in (401, 403)
    assert requests.put(DRAFT, json={"day": 1, "inputs": INPUTS}).status_code in (401, 403)
