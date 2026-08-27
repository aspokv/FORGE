"""Persistencia das escolhas de personalizacao, ponta a ponta.

A escolha nao pode viver so no estado do frontend: depois de refresh, logout/login ou
troca de aparelho, intensidade de emagrecimento, metas calculadas e regioes prioritarias
tem que ser reconstruidas corretamente a partir do banco.
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
SENHA = "PersonalizationTest2026!"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _db():
    """Sempre um cliente novo, e sempre criado dentro da coroutine que o usa: um cliente
    Motor fica ligado ao event loop em que nasceu, e cada _run() abre um loop novo."""
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _find_one(collection, query, projection=None):
    return await _db()[collection].find_one(query, projection)


async def _count(collection, query):
    return await _db()[collection].count_documents(query)


async def _reset(email):
    db = _db()
    existing = await db.users.find_one({"email": email})
    if existing:
        uid = existing["id"]
        for col in ("profiles", "nutrition_plans", "nutrition_assessments",
                    "set_logs", "workout_completions"):
            await db[col].delete_many({"profile_id": uid})
        await db.users.delete_one({"email": email})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Personalization Test", "role": "ATHLETE",
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
                      json={"token": invite, "password": SENHA, "name": "Personalization Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _assessment(intensity=None, goal="fat_loss"):
    corpo = {"weight_kg": 85, "height_cm": 178, "age": 30, "sex": "male", "goal": goal,
             "activity_level": "moderate", "training_days": 4, "meal_count": 4,
             "cooking_time": "medium"}
    if intensity is not None:
        corpo["intensity"] = intensity
    return corpo


# --- catalogo -----------------------------------------------------------------------

def test_catalogo_de_intensidades_e_servido_para_a_interface():
    _, headers = _athlete("pers.catalog@example.com")
    r = requests.get(f"{API}/nutrition/cutting-intensities", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [o["id"] for o in body["options"]] == ["leve", "moderado", "agressivo"]
    assert body["default"] == "moderado"
    agressivo = next(o for o in body["options"] if o["id"] == "agressivo")
    assert agressivo["advanced"] is True
    assert agressivo["warning"], "o modo extremo precisa expor aviso para a interface"
    assert agressivo["carb_range_g"] == [20, 50]
    assert next(o for o in body["options"] if o["id"] == "moderado")["recommended"] is True


# --- alimentacao: intensidade muda o resultado e persiste ---------------------------

def test_intensidade_muda_as_metas_geradas():
    alvos = {}
    for intensidade in ("leve", "moderado", "agressivo"):
        _, headers = _athlete(f"pers.{intensidade}@example.com")
        assert requests.post(f"{API}/nutrition/assessment", json=_assessment(intensidade),
                             headers=headers).status_code == 200
        r = requests.post(f"{API}/nutrition/generate", headers=headers)
        assert r.status_code == 200, r.text
        alvos[intensidade] = r.json()["targets"]

    assert (alvos["leve"]["goal_calories"] > alvos["moderado"]["goal_calories"]
            > alvos["agressivo"]["goal_calories"])
    assert alvos["leve"]["carbs_g"] > alvos["moderado"]["carbs_g"]
    assert 20 <= alvos["agressivo"]["carbs_g"] <= 50


def test_plano_agressivo_persiste_com_protocolo_e_sobrevive_a_reload_e_novo_login():
    email = "pers.persist@example.com"
    uid, headers = _athlete(email)
    assert requests.post(f"{API}/nutrition/assessment", json=_assessment("agressivo"),
                         headers=headers).status_code == 200
    gerado = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert gerado.status_code == 200, gerado.text
    metas = gerado.json()["targets"]

    # "refresh": releitura do plano salvo
    lido = requests.get(f"{API}/nutrition/plan", headers=headers)
    assert lido.status_code == 200
    assert lido.json()["targets"]["carbs_g"] == metas["carbs_g"]
    assert lido.json()["targets"]["cut_protocol"]["intensity"] == "agressivo"
    assert lido.json()["daily_totals"]["carbs_g"] <= 50

    # "outro aparelho": autenticacao nova
    de_novo = requests.get(f"{API}/nutrition/plan", headers=_login(email))
    assert de_novo.status_code == 200
    assert de_novo.json()["targets"]["cut_protocol"]["intensity"] == "agressivo"

    doc = _run(_find_one("nutrition_plans", {"profile_id": uid}, {"_id": 0}))
    assert doc["intensity"] == "agressivo"
    assert doc["cut_protocol"]["protocol_version"]
    perfil = _run(_find_one("profiles", {"id": uid}))
    assert perfil["nutrition_assessment"]["intensity"] == "agressivo"


def test_dois_envios_rapidos_nao_duplicam_o_plano():
    email = "pers.double@example.com"
    uid, headers = _athlete(email)
    requests.post(f"{API}/nutrition/assessment", json=_assessment("moderado"), headers=headers)
    for _ in range(3):
        assert requests.post(f"{API}/nutrition/generate", headers=headers).status_code == 200
    assert _run(_count("nutrition_plans", {"profile_id": uid})) == 1


def test_usuario_antigo_sem_intensidade_continua_gerando():
    email = "pers.legacy@example.com"
    _, headers = _athlete(email)
    assert requests.post(f"{API}/nutrition/assessment", json=_assessment(None),
                         headers=headers).status_code == 200
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    metas = r.json()["targets"]
    assert metas["goal_calories"] > 0
    # sem escolha declarada nao existe protocolo: o calculo legado e preservado
    assert "cut_protocol" not in metas
    assert requests.get(f"{API}/nutrition/plan", headers=headers).status_code == 200


def test_intensidade_invalida_nao_derruba_a_geracao():
    _, headers = _athlete("pers.invalid@example.com")
    assert requests.post(f"{API}/nutrition/assessment", json=_assessment("turbo"),
                         headers=headers).status_code == 200
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    assert "cut_protocol" not in r.json()["targets"]


# --- treino: perfil e prioridades persistem e mudam o programa ----------------------

def _deep_assessment(uid, sex, priorities):
    corpo = {"profile_id": uid, "name": "Personalization Test", "age": 30,
             "height_cm": 178, "weight_kg": 85, "experience": "Intermediario",
             "goal": "Hipertrofia", "days": 4, "session_minutes": 60,
             "assessment": {}, "priorities": priorities,
             "automation_mode": "FORGE_ASSISTED"}
    if sex is not None:
        corpo["sex"] = sex
    return corpo


def test_perfil_e_prioridades_persistem_e_mudam_o_programa():
    email = "pers.training@example.com"
    uid, headers = _athlete(email)
    r = requests.post(f"{API}/assessment",
                      json=_deep_assessment(uid, "Feminino", ["Gluteos", "Posteriores"]),
                      headers=headers)
    assert r.status_code == 200, r.text

    salvo = _run(_find_one("profiles", {"id": uid}, {"_id": 0}))
    assert salvo["sex"] == "Feminino"
    assert salvo["priorities"][:2] == ["Gluteos", "Posteriores"]

    # sobrevive a refresh e a novo login
    boot = requests.get(f"{API}/bootstrap", headers=_login(email))
    assert boot.status_code == 200
    assert boot.json()["program"]["sessions"]


def test_atleta_antigo_sem_sexo_e_sem_prioridade_continua_abrindo_o_plano():
    """Perfil anterior a esta feature: tem avaliacao muscular, mas nao tem sexo nem
    prioridade declarada. Tem que continuar gerando programa normalmente."""
    email = "pers.oldathlete@example.com"
    uid, headers = _athlete(email)
    antigo = _deep_assessment(uid, None, [])
    antigo["assessment"] = {"Peitoral superior": {"development": "proporcional",
                                                  "priority": "normal"}}
    assert requests.post(f"{API}/assessment", json=antigo,
                         headers=headers).status_code == 200
    boot = requests.get(f"{API}/bootstrap", headers=headers)
    assert boot.status_code == 200
    assert boot.json()["program"]["sessions"]
