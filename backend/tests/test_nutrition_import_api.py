"""FORGE — importação de dieta e periodização: testes de API contra servidor + Mongo.

Mesmo padrão de fixture self-seeding de test_nutrition_guided_flow_api.py. O que estes
testes defendem: um atleta só alcança a própria dieta, a ativação substitui o plano sem
apagar peso/aderência, o plano importado é lido pelos endpoints que já existiam, e a
periodização respeita o piso de gordura inclusive quando a tabela é editada à mão.
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
NUT = f"{API}/nutrition"

TEST_PASSWORD = "DietImport2026!"

DIETA = """CAFÉ DA MANHÃ
2 ovos inteiros
50g de aveia
200ml de leite desnatado

ALMOÇO
150g de arroz branco
120g de peito de frango

LANCHE
1 scoop de whey
1 banana"""


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _reset(email: str):
    db = await _db()
    existing = await db.users.find_one({"email": email})
    if existing:
        uid = existing["id"]
        for col in ("users", "profiles", "nutrition_plans", "nutrition_import_drafts",
                    "nutrition_periodization", "nutrition_plan_versions",
                    "nutrition_weight_logs", "nutrition_adherence"):
            await db[col].delete_many({"profile_id": uid} if col != "users" else {"email": email})
        await db.profiles.delete_one({"id": uid})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Diet Test", "role": "ATHLETE", "status": "PENDING",
        "plan": "MONTHLY", "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite, "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    await db.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Diet Test", "onboarding_required": False,
        "nutrition_assessment": {"weight_kg": 80, "height_cm": 178, "age": 30, "sex": "male",
                                 "goal": "fat_loss", "activity_level": "moderate",
                                 "training_days": 4, "meal_count": 4,
                                 "allergies": [], "dietary_restrictions": []},
    })
    return uid, invite


def _athlete(email):
    uid, invite = _run(_reset(email))
    r = requests.post(f"{API}/auth/accept-invite",
                      json={"token": invite, "password": TEST_PASSWORD, "name": "Diet Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _parse(headers, text=DIETA):
    r = requests.post(f"{NUT}/import/parse", json={"text": text, "name": "Dieta importada"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _activate(headers, token=None):
    return requests.post(f"{NUT}/import/activate",
                         json={"activation_token": token or uuid.uuid4().hex}, headers=headers)


# --- catálogo e parse -----------------------------------------------------------------

def test_food_catalog_is_available_for_the_selects():
    _, headers = _athlete("diet.catalog@forge.test")
    r = requests.get(f"{NUT}/foods", headers=headers)
    assert r.status_code == 200
    foods = r.json()["foods"]
    assert len(foods) == 62
    assert all({"id", "name"} <= set(f) for f in foods)


def test_parse_recognizes_meals_and_computes_macros():
    _, headers = _athlete("diet.parse@forge.test")
    data = _parse(headers)
    draft = data["draft"]
    assert draft["stats"]["meals"] == 3
    assert draft["stats"]["items"] == 7
    assert draft["daily_totals"]["kcal"] > 500
    assert draft["daily_totals"]["protein_g"] > 40
    assert data["blocking_errors"] == []


def test_draft_survives_a_refresh():
    _, headers = _athlete("diet.refresh@forge.test")
    _parse(headers)
    r = requests.get(f"{NUT}/import/draft", headers=headers)
    assert r.status_code == 200
    assert r.json()["draft"]["stats"]["items"] == 7


def test_parse_rejects_empty_and_unstructured_text():
    _, headers = _athlete("diet.reject@forge.test")
    for bad in ["", "   ", "oi, quanto custa?"]:
        r = requests.post(f"{NUT}/import/parse", json={"text": bad}, headers=headers)
        assert r.status_code == 400, f"{bad!r} -> {r.status_code}"


def test_server_recomputes_macros_and_ignores_client_totals():
    _, headers = _athlete("diet.recompute@forge.test")
    draft = _parse(headers)["draft"]
    draft["daily_totals"] = {"kcal": 99999, "protein_g": 9999, "carbs_g": 0, "fat_g": 0}
    r = requests.put(f"{NUT}/import/draft", json={"draft": draft}, headers=headers)
    assert r.status_code == 200
    assert r.json()["draft"]["daily_totals"]["kcal"] < 5000


def test_food_outside_the_catalog_blocks_activation():
    _, headers = _athlete("diet.unknown@forge.test")
    data = _parse(headers, "JANTAR\n100g de bacalhau à lagareiro")
    assert data["draft"]["meals"][0]["items"][0]["food_id"] is None
    assert data["blocking_errors"]
    assert _activate(headers).status_code == 422


# --- ativação -------------------------------------------------------------------------

def test_activation_replaces_the_plan_and_keeps_it_readable_by_the_existing_endpoint():
    _, headers = _athlete("diet.activate@forge.test")
    _parse(headers)
    r = _activate(headers)
    assert r.status_code == 200, r.text
    assert r.json()["already_applied"] is False

    plano = requests.get(f"{NUT}/plan", headers=headers)
    assert plano.status_code == 200
    body = plano.json()
    assert len(body["meals"]) == 3
    assert body["meals"][0]["foods"], "as refeições precisam chegar no formato do plano gerado"


def test_activation_does_not_erase_weight_or_adherence():
    uid, headers = _athlete("diet.history@forge.test")
    assert requests.post(f"{NUT}/weight", json={"weight_kg": 81.5}, headers=headers).status_code == 200
    _parse(headers)
    assert _activate(headers).status_code == 200

    peso = requests.get(f"{NUT}/weight", headers=headers)
    assert peso.status_code == 200
    assert peso.json(), "histórico de peso não pode sumir na ativação"


def test_double_click_activates_once():
    _, headers = _athlete("diet.idempotent@forge.test")
    _parse(headers)
    token = uuid.uuid4().hex
    primeira, segunda = _activate(headers, token), _activate(headers, token)
    assert primeira.status_code == 200 and segunda.status_code == 200
    assert primeira.json()["already_applied"] is False
    assert segunda.json()["already_applied"] is True


# --- periodização ---------------------------------------------------------------------

def test_periodization_progresses_linearly_and_holds_protein():
    _, headers = _athlete("diet.period@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200

    r = requests.post(f"{NUT}/periodization/preview", json={"pct": -15, "weeks": 4}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    tabela = body["table"]
    assert len(tabela) == 4
    assert len({w["protein_g"] for w in tabela}) == 1        # proteína fixa
    assert all(w["fat_g"] >= body["fat_floor_g"] for w in tabela)
    assert tabela[-1]["kcal"] < tabela[0]["kcal"]            # é um corte


def test_periodization_requires_an_active_plan():
    _, headers = _athlete("diet.noplan@forge.test")
    r = requests.post(f"{NUT}/periodization/preview", json={"pct": -10, "weeks": 4}, headers=headers)
    assert r.status_code == 404


def test_saved_periodization_comes_back_and_manual_edit_cannot_break_the_fat_floor():
    _, headers = _athlete("diet.periodsave@forge.test")
    _parse(headers)
    assert _activate(headers).status_code == 200
    preview = requests.post(f"{NUT}/periodization/preview", json={"pct": -10, "weeks": 3}, headers=headers).json()

    tabela = preview["table"]
    tabela[0]["fat_g"] = 5          # edição manual furando o piso
    tabela[0]["kcal"] = 100         # e mentindo na kcal
    r = requests.post(f"{NUT}/periodization/save", json={"table": tabela, "weeks": 3}, headers=headers)
    assert r.status_code == 200, r.text
    salva = r.json()["periodization"]["table"]
    assert salva[0]["fat_g"] == preview["fat_floor_g"]
    assert salva[0]["kcal"] > 100   # recalculada a partir dos macros

    lida = requests.get(f"{NUT}/periodization", headers=headers)
    assert lida.status_code == 200
    assert lida.json()["periodization"]["table"][0]["fat_g"] == preview["fat_floor_g"]


# --- autorização ----------------------------------------------------------------------

def test_athlete_cannot_reach_another_athletes_diet_draft():
    _, headers_a = _athlete("diet.owner.a@forge.test")
    _, headers_b = _athlete("diet.owner.b@forge.test")
    _parse(headers_a)
    r = requests.get(f"{NUT}/import/draft", headers=headers_b)
    assert r.status_code == 200
    assert r.json()["draft"] is None


def test_diet_endpoints_require_authentication():
    for method, url, body in [
        ("post", f"{NUT}/import/parse", {"text": DIETA}),
        ("get", f"{NUT}/import/draft", None),
        ("post", f"{NUT}/periodization/preview", {"pct": -10, "weeks": 4}),
        ("get", f"{NUT}/foods", None),
    ]:
        r = requests.request(method, url, json=body)
        assert r.status_code in (401, 403), f"{url} respondeu {r.status_code} sem token"
