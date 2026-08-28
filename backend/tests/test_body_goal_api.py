"""Objetivo corporal separado do objetivo de treino, ponta a ponta.

A secao "Objetivo" do onboarding passou a tratar so do corpo (ganhar / emagrecer /
manter). Ela grava em nutrition_assessment.goal e .intensity — os campos que ja
existiam — e nao cria enum novo nem segunda selecao de regioes.
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
SENHA = "BodyGoalTest2026!"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _find_one(collection, query, projection=None):
    return await _db()[collection].find_one(query, projection)


async def _reset(email):
    db = _db()
    existing = await db.users.find_one({"email": email})
    if existing:
        uid = existing["id"]
        for col in ("profiles", "nutrition_plans", "nutrition_assessments"):
            await db[col].delete_many({"profile_id": uid})
        await db.users.delete_one({"email": email})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid = str(uuid.uuid4())
    invite = secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Body Goal Test", "role": "ATHLETE",
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
                      json={"token": invite, "password": SENHA, "name": "Body Goal Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _onboarding(uid, body_goal=None, ritmo=None, goal_treino="Hipertrofia"):
    corpo = {"profile_id": uid, "name": "Body Goal Test", "age": 30, "sex": "Feminino",
             "height_cm": 178, "weight_kg": 85, "experience": "Intermediario",
             "goal": goal_treino, "days": 4, "session_minutes": 60,
             "assessment": {"Peitoral superior": {"development": "proporcional",
                                                  "priority": "normal"}},
             "priorities": [], "automation_mode": "FORGE_ASSISTED"}
    if body_goal is not None:
        corpo["body_goal"] = body_goal
    if ritmo is not None:
        corpo["goal_intensity"] = ritmo
    return corpo


def _questionario(headers, goal):
    corpo = {"weight_kg": 85, "height_cm": 178, "age": 30, "sex": "male", "goal": goal,
             "activity_level": "moderate", "training_days": 4, "meal_count": 4,
             "cooking_time": "medium"}
    assert requests.post(f"{API}/nutrition/assessment", json=corpo,
                         headers=headers).status_code == 200


def _na(uid):
    return (_run(_find_one("profiles", {"id": uid})) or {}).get("nutrition_assessment") or {}


# --- catalogo -----------------------------------------------------------------------

def test_catalogo_traz_so_os_tres_objetivos_corporais():
    _, headers = _athlete("body.catalog@example.com")
    r = requests.get(f"{API}/nutrition/goal-catalog", headers=headers)
    assert r.status_code == 200, r.text
    metas = r.json()["goals"]
    assert [g["id"] for g in metas] == ["muscle_gain", "fat_loss", "maintenance"]

    rotulos = " | ".join(g["label"] for g in metas).lower()
    assert "desempenho" not in rotulos   # objetivo de treino saiu desta secao
    assert "regi" not in rotulos         # prioridade muscular tem etapa propria

    por_id = {g["id"]: g for g in metas}
    assert por_id["muscle_gain"]["default_intensity"] == "controlado"
    assert por_id["fat_loss"]["default_intensity"] == "moderado"
    assert por_id["maintenance"]["intensities"] == []
    for g in metas:
        assert g["default_intensity"] != "agressivo"
    agr = next(i for i in por_id["muscle_gain"]["intensities"] if i["id"] == "agressivo")
    assert agr["advanced"] is True and agr["warning"]


def test_endpoint_antigo_de_cutting_continua_respondendo():
    """A area de Alimentacao ja consome /cutting-intensities; ele nao pode sumir."""
    _, headers = _athlete("body.oldendpoint@example.com")
    r = requests.get(f"{API}/nutrition/cutting-intensities", headers=headers)
    assert r.status_code == 200, r.text
    opcoes = r.json()["options"]
    assert [o["id"] for o in opcoes] == ["leve", "moderado", "agressivo"]
    assert next(o for o in opcoes if o["id"] == "agressivo")["deficit_pct"] == 30


# --- ganho de massa -----------------------------------------------------------------

def test_ritmo_de_ganho_chega_na_geracao_alimentar():
    uid, headers = _athlete("body.bulk@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "muscle_gain", "agressivo"),
                         headers=headers).status_code == 200
    na = _na(uid)
    assert na["goal"] == "muscle_gain" and na["intensity"] == "agressivo"

    _questionario(headers, "muscle_gain")
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    metas = r.json()["targets"]
    assert metas["cut_protocol"]["intensity"] == "agressivo"
    assert metas["cut_protocol"]["goal_key"] == "muscle_gain"
    assert 15 <= (metas["goal_calories"] / metas["tdee"] - 1) * 100 <= 20


def test_cada_ritmo_de_ganho_produz_seu_superavit():
    valores = {}
    for ritmo in ("controlado", "moderado", "agressivo"):
        uid, headers = _athlete(f"body.bulk.{ritmo}@example.com")
        assert requests.post(f"{API}/assessment",
                             json=_onboarding(uid, "muscle_gain", ritmo),
                             headers=headers).status_code == 200
        _questionario(headers, "muscle_gain")
        r = requests.post(f"{API}/nutrition/generate", headers=headers)
        assert r.status_code == 200, r.text
        valores[ritmo] = r.json()["targets"]["goal_calories"]
    assert valores["controlado"] < valores["moderado"] < valores["agressivo"]


# --- manter e recompor --------------------------------------------------------------

def test_manter_e_recompor_nao_guarda_ritmo():
    uid, headers = _athlete("body.maint@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "maintenance", "agressivo"),
                         headers=headers).status_code == 200
    na = _na(uid)
    assert na["goal"] == "maintenance"
    assert na["intensity"] is None

    _questionario(headers, "maintenance")
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    metas = r.json()["targets"]
    assert "cut_protocol" not in metas
    assert abs(metas["goal_calories"] - metas["tdee"]) < 1


# --- transicoes ---------------------------------------------------------------------

def test_trocar_de_emagrecimento_para_ganho_nao_deixa_cutting_ativo():
    uid, headers = _athlete("body.switch1@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "fat_loss", "agressivo"),
                         headers=headers).status_code == 200
    assert _na(uid)["intensity"] == "agressivo"

    # troca para ganho levando junto um ritmo que so existe no emagrecimento
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "muscle_gain", "leve"),
                         headers=headers).status_code == 200
    na = _na(uid)
    assert na["goal"] == "muscle_gain"
    assert na["intensity"] is None, "ritmo de emagrecimento sobreviveu a troca para ganho"


def test_trocar_de_ganho_para_emagrecimento_nao_deixa_superavit_ativo():
    uid, headers = _athlete("body.switch2@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "muscle_gain", "agressivo"),
                         headers=headers).status_code == 200
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "fat_loss", "controlado"),
                         headers=headers).status_code == 200
    na = _na(uid)
    assert na["goal"] == "fat_loss"
    assert na["intensity"] is None, "ritmo de ganho sobreviveu a troca para emagrecimento"


# --- cutting intacto ----------------------------------------------------------------

def test_emagrecimento_agressivo_segue_com_20_a_50g_de_carboidrato():
    uid, headers = _athlete("body.cutintact@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "fat_loss", "agressivo"),
                         headers=headers).status_code == 200
    _questionario(headers, "fat_loss")
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    assert 20 <= r.json()["targets"]["carbs_g"] <= 50
    assert r.json()["plan"]["daily_totals"]["carbs_g"] <= 50


# --- persistencia e compatibilidade -------------------------------------------------

def test_escolha_corporal_persiste_apos_novo_login():
    email = "body.persist@example.com"
    uid, headers = _athlete(email)
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "muscle_gain", "moderado"),
                         headers=headers).status_code == 200
    r = requests.get(f"{API}/nutrition/assessment", headers=_login(email))
    assert r.status_code == 200
    assert r.json()["assessment"]["goal"] == "muscle_gain"
    assert r.json()["assessment"]["intensity"] == "moderado"


def test_objetivo_de_treino_legado_nao_e_convertido_em_silencio():
    """Performance sumiu da selecao mas continua valido: nenhuma logica ramifica nele e
    o perfil antigo nao pode ser reescrito sozinho."""
    uid, headers = _athlete("body.legacygoal@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, goal_treino="Performance"),
                         headers=headers).status_code == 200
    perfil = _run(_find_one("profiles", {"id": uid}))
    assert perfil["goal"] == "Performance"
    assert perfil.get("nutrition_assessment") is None
    boot = requests.get(f"{API}/bootstrap", headers=headers)
    assert boot.status_code == 200 and boot.json()["program"]["sessions"]


def test_cliente_antigo_enviando_cut_intensity_continua_funcionando():
    """Aba aberta durante o deploy ainda manda o nome anterior do transporte."""
    uid, headers = _athlete("body.oldclient@example.com")
    corpo = _onboarding(uid, goal_treino="Recomposicao")
    corpo["cut_intensity"] = "leve"
    assert requests.post(f"{API}/assessment", json=corpo, headers=headers).status_code == 200
    na = _na(uid)
    assert na["goal"] == "fat_loss" and na["intensity"] == "leve"


def test_body_goal_invalido_nao_grava_nada():
    uid, headers = _athlete("body.invalid@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, "turbo", "agressivo"),
                         headers=headers).status_code == 200
    perfil = _run(_find_one("profiles", {"id": uid}))
    assert perfil.get("nutrition_assessment") is None
    # e os transportes nao viraram campos do perfil
    assert "body_goal" not in perfil and "goal_intensity" not in perfil
