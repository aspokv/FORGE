"""Regeneracao do plano alimentar ("Refazer plano").

Tres coisas que quebravam ou mentiam:

  1. /plan/reset nao passava a intensidade para compute_macro_targets, entao refazer o
     plano recalculava pelo caminho legado e descartava o protocolo escolhido — a tela
     dizia "Agressivo" sobre metas que nao eram.
  2. o fluxo guiado nao aplicava o filtro low-carb, entao oferecia arroz e pao a quem
     escolheu o protocolo agressivo.
  3. perfil com plano mas sem questionario (o "Refazer avaliacao" de versoes anteriores
     apagava nutrition_assessment) recebia 400 sem motivo no log, e o frontend virava um
     beco sem saida.
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

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"
SENHA = "RegenerateTest2026!"

CARBO_DENSO = {"rice-white", "rice-brown", "pasta", "pasta-whole", "oats", "bread-white",
               "bread-whole", "tapioca", "cassava", "sweet-potato", "corn-flour"}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _find_one(collection, query, projection=None):
    return await _db()[collection].find_one(query, projection)


async def _apagar_assessment(uid):
    await _db().profiles.update_one({"id": uid}, {"$unset": {"nutrition_assessment": ""}})


async def _reset(email):
    db = _db()
    antigo = await db.users.find_one({"email": email})
    if antigo:
        uid = antigo["id"]
        for col in ("profiles", "nutrition_plans", "nutrition_plan_drafts",
                    "nutrition_assessments"):
            await db[col].delete_many({"profile_id": uid})
        await db.users.delete_one({"email": email})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid, invite = str(uuid.uuid4()), secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Regen Test", "role": "ATHLETE",
        "status": "PENDING", "plan": "MONTHLY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "invite_token": invite,
        "invite_expires": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
    })
    return uid, invite


def _athlete(email):
    uid, invite = _run(_reset(email))
    r = requests.post(f"{API}/auth/accept-invite",
                      json={"token": invite, "password": SENHA, "name": "Regen Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _questionario(headers, intensidade, goal="fat_loss"):
    r = requests.post(f"{API}/nutrition/assessment", headers=headers, json={
        "weight_kg": 85, "height_cm": 178, "age": 30, "sex": "male", "goal": goal,
        "intensity": intensidade, "activity_level": "moderate", "training_days": 4,
        "meal_count": 4, "cooking_time": "medium"})
    assert r.status_code == 200, r.text


# --- 1. refazer usa a avaliacao atual, com o protocolo ------------------------------

def test_refazer_plano_preserva_a_intensidade_escolhida():
    _, headers = _athlete("regen.intensity@example.com")
    _questionario(headers, "agressivo")
    gerado = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert gerado.status_code == 200, gerado.text
    alvo_generate = gerado.json()["targets"]

    r = requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    assert r.status_code == 200, r.text
    alvo_reset = r.json()["targets"]

    assert alvo_reset["carbs_g"] == alvo_generate["carbs_g"]
    assert alvo_reset["goal_calories"] == alvo_generate["goal_calories"]
    assert alvo_reset["cut_protocol"]["intensity"] == "agressivo"
    assert 20 <= alvo_reset["carbs_g"] <= 50


def test_refazer_plano_reflete_troca_de_intensidade():
    """Trocar de agressivo para leve tem que mudar as metas do rascunho."""
    _, headers = _athlete("regen.switch@example.com")
    _questionario(headers, "agressivo")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    agressivo = requests.post(f"{API}/nutrition/plan/reset", headers=headers).json()["targets"]

    _questionario(headers, "leve")
    leve = requests.post(f"{API}/nutrition/plan/reset", headers=headers).json()["targets"]

    assert leve["carbs_g"] > agressivo["carbs_g"]
    assert leve["cut_protocol"]["intensity"] == "leve"


def test_refazer_plano_de_ganho_usa_o_superavit():
    _, headers = _athlete("regen.bulk@example.com")
    _questionario(headers, "agressivo", goal="muscle_gain")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    alvos = requests.post(f"{API}/nutrition/plan/reset", headers=headers).json()["targets"]
    assert alvos["cut_protocol"]["goal_key"] == "muscle_gain"
    assert 15 <= (alvos["goal_calories"] / alvos["tdee"] - 1) * 100 <= 20


# --- 2. o fluxo guiado respeita o protocolo -----------------------------------------

def test_opcoes_guiadas_nao_oferecem_carboidrato_denso_no_agressivo():
    _, headers = _athlete("regen.lowcarb@example.com")
    _questionario(headers, "agressivo")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    assert requests.post(f"{API}/nutrition/plan/reset", headers=headers).status_code == 200

    r = requests.post(f"{API}/nutrition/plan/draft/options", headers=headers,
                      json={"meal_index": 0})
    assert r.status_code == 200, r.text
    usados = {f["food_id"] for op in r.json()["options"] for f in op["foods"]}
    assert usados, "nenhuma opcao oferecida"
    assert not (usados & CARBO_DENSO), f"protocolo agressivo ofereceu {usados & CARBO_DENSO}"


def test_opcoes_guiadas_seguem_livres_fora_do_protocolo_capped():
    """O filtro nao pode vazar para quem nao escolheu low-carb."""
    _, headers = _athlete("regen.freecarb@example.com")
    _questionario(headers, "leve")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    assert requests.post(f"{API}/nutrition/plan/reset", headers=headers).status_code == 200
    r = requests.post(f"{API}/nutrition/plan/draft/options", headers=headers,
                      json={"meal_index": 1})
    assert r.status_code == 200, r.text
    assert r.json()["options"], "emagrecimento leve ficou sem opcoes"


# --- 3. questionario ausente: erro tratavel, plano preservado -----------------------

def test_perfil_com_plano_e_sem_questionario_recebe_400_e_mantem_o_plano():
    """Cenario real: 'Refazer avaliacao' de versoes anteriores apagava o
    nutrition_assessment, deixando o plano visivel e a regeneracao recusada."""
    uid, headers = _athlete("regen.wiped@example.com")
    _questionario(headers, "moderado")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    _run(_apagar_assessment(uid))

    # o plano antigo continua intacto
    assert requests.get(f"{API}/nutrition/plan", headers=headers).status_code == 200

    r = requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    assert r.status_code == 400, f"esperado 400 tratavel, veio {r.status_code}: {r.text[:200]}"
    assert "question" in r.json()["detail"].lower()

    # e nada foi destruido pela tentativa
    assert requests.get(f"{API}/nutrition/plan", headers=headers).status_code == 200
    assert _run(_find_one("nutrition_plans", {"profile_id": uid})) is not None


def test_o_estado_e_recuperavel_refazendo_o_questionario():
    """Depois do 400 o atleta refaz o questionario e volta a conseguir regenerar."""
    uid, headers = _athlete("regen.recover@example.com")
    _questionario(headers, "moderado")
    assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    _run(_apagar_assessment(uid))
    assert requests.post(f"{API}/nutrition/plan/reset", headers=headers).status_code == 400

    _questionario(headers, "leve")
    r = requests.post(f"{API}/nutrition/plan/reset", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["targets"]["cut_protocol"]["intensity"] == "leve"
