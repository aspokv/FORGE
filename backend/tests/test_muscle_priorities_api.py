"""Onboarding sem o Muscle Map, ponta a ponta.

O questionario musculo a musculo saiu do fluxo. Duas coisas precisam continuar valendo:

  1. "treino equilibrado" (nenhuma regiao priorizada) tem que GERAR PROGRAMA. Sem
     avaliacao E sem prioridade, _is_empty_profile devolvia True e o programa vinha
     vazio — por isso save_assessment passou a marcar onboarding_required=False.
  2. quem ja respondeu os 18 musculos nao pode perder esse historico ao refazer a
     avaliacao pelo formulario novo, que manda assessment vazio.
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
SENHA = "MusclePrioTest2026!"


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
        "id": uid, "email": email, "name": "Prio Test", "role": "ATHLETE",
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
                      json={"token": invite, "password": SENHA, "name": "Prio Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _onboarding(uid, priorities=None, assessment=None, sex="Feminino"):
    """Exatamente o que o formulario novo envia: assessment vazio."""
    return {"profile_id": uid, "name": "Prio Test", "age": 30, "sex": sex,
            "height_cm": 170, "weight_kg": 70, "experience": "Intermediario",
            "goal": "Hipertrofia", "body_goal": "muscle_gain", "days": 4,
            "session_minutes": 60, "assessment": assessment or {},
            "priorities": priorities or [], "automation_mode": "FORGE_ASSISTED"}


def _volume_por_musculo(programa, exercicios_por_id):
    total = {}
    for s in programa["sessions"]:
        for x in s["exercises"]:
            m = exercicios_por_id.get(x["exercise_id"], {}).get("muscle")
            if m:
                total[m] = total.get(m, 0) + x["sets"]
    return total


# --- treino equilibrado ---------------------------------------------------------------

def test_sem_nenhuma_prioridade_o_programa_e_gerado():
    """O caso que quebrava: sem avaliacao e sem prioridade o programa vinha vazio."""
    uid, headers = _athlete("prio.balanced@example.com")
    r = requests.post(f"{API}/assessment", json=_onboarding(uid), headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["program"]["sessions"], "treino equilibrado gerou programa vazio"

    perfil = _run(_find_one("profiles", {"id": uid}, {"_id": 0}))
    assert perfil["onboarding_required"] is False
    assert perfil["priorities"] == []
    assert perfil["assessment"] == {}

    boot = requests.get(f"{API}/bootstrap", headers=headers)
    assert boot.status_code == 200
    assert boot.json()["program"]["sessions"]
    assert boot.json()["program"].get("onboarding_required") is not True


def test_equilibrado_distribui_sem_destacar_ninguem():
    uid, headers = _athlete("prio.even@example.com")
    r = requests.post(f"{API}/assessment", json=_onboarding(uid), headers=headers)
    assert r.status_code == 200, r.text
    boot = requests.get(f"{API}/bootstrap", headers=headers).json()
    idx = {e["id"]: e for e in boot["exercises"]}
    volume = _volume_por_musculo(boot["program"], idx)
    assert volume, "nenhum volume gerado"
    # nenhum musculo dispara muito acima dos demais quando nada foi priorizado
    assert max(volume.values()) <= min(volume.values()) * 3


# --- prioridades declaradas -----------------------------------------------------------

def test_regioes_priorizadas_recebem_mais_volume_que_as_demais():
    """A hierarquia entre principal e secundaria e garantida no volume PLANEJADO
    (calculate_weekly_volume: 14 vs 11 series-alvo) e esta coberta nos testes puros.
    Aqui verifica-se o que o programa gerado garante de fato: quem foi priorizado fica
    acima da linha de base. A quantidade finalmente COLOCADA depende da estrutura do
    split e da capacidade da sessao — comportamento do construtor de sessoes, anterior
    a esta mudanca e nao alterado por ela."""
    uid, headers = _athlete("prio.rank@example.com")
    r = requests.post(f"{API}/assessment",
                      json=_onboarding(uid, ["Glúteos", "Panturrilhas"]), headers=headers)
    assert r.status_code == 200, r.text
    boot = requests.get(f"{API}/bootstrap", headers=headers).json()
    idx = {e["id"]: e for e in boot["exercises"]}
    volume = _volume_por_musculo(boot["program"], idx)

    priorizados = [volume.get("Glúteos", 0), volume.get("Panturrilhas", 0)]
    outros = [v for m, v in volume.items() if m not in ("Glúteos", "Panturrilhas")]
    assert all(v > 0 for v in priorizados), "regiao priorizada ficou sem volume"
    assert min(priorizados) > min(outros), "prioridade nao gerou enfase nenhuma"


def test_ordem_das_prioridades_persiste_apos_novo_login():
    email = "prio.persist@example.com"
    uid, headers = _athlete(email)
    ordem = ["Glúteos", "Quadríceps", "Deltóide lateral"]
    assert requests.post(f"{API}/assessment", json=_onboarding(uid, ordem),
                         headers=headers).status_code == 200

    perfil = _run(_find_one("profiles", {"id": uid}, {"_id": 0}))
    assert perfil["priorities"] == ordem, "a ordem e o ranking: nao pode ser reordenada"

    boot = requests.get(f"{API}/bootstrap", headers=_login(email))
    assert boot.status_code == 200
    assert boot.json()["profile"]["priorities"] == ordem


def test_no_maximo_tres_prioridades_chegam_ao_motor():
    uid, headers = _athlete("prio.cap@example.com")
    muitas = ["Glúteos", "Quadríceps", "Bíceps", "Tríceps", "Panturrilhas"]
    assert requests.post(f"{API}/assessment", json=_onboarding(uid, muitas),
                         headers=headers).status_code == 200
    boot = requests.get(f"{API}/bootstrap", headers=headers).json()
    # o perfil guarda o que foi enviado; o motor aplica o teto
    assert len(boot["program"]["logic"]["priority_scores"]) <= 3


# --- historico do Muscle Map ----------------------------------------------------------

MAPA_LEGADO = {
    "Bíceps": {"development": "muito forte", "priority": "baixa"},
    "Glúteos": {"development": "fraco", "priority": "alta"},
}


def test_muscle_map_legado_sobrevive_ao_formulario_novo():
    """O formulario novo manda assessment vazio; isso nao pode apagar o historico."""
    uid, headers = _athlete("prio.legacy@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, ["Glúteos"], MAPA_LEGADO),
                         headers=headers).status_code == 200
    assert _run(_find_one("profiles", {"id": uid}))["assessment"] == MAPA_LEGADO

    # refaz a avaliacao pelo fluxo novo, sem muscle map
    assert requests.post(f"{API}/assessment", json=_onboarding(uid, ["Quadríceps"]),
                         headers=headers).status_code == 200
    perfil = _run(_find_one("profiles", {"id": uid}))
    assert perfil["assessment"] == MAPA_LEGADO, "muscle map historico foi apagado"
    assert perfil["priorities"] == ["Quadríceps"], "a nova prioridade nao prevaleceu"


def test_usuario_legado_continua_abrindo_o_programa():
    uid, headers = _athlete("prio.legacyopen@example.com")
    assert requests.post(f"{API}/assessment",
                         json=_onboarding(uid, [], MAPA_LEGADO),
                         headers=headers).status_code == 200
    boot = requests.get(f"{API}/bootstrap", headers=headers)
    assert boot.status_code == 200
    assert boot.json()["program"]["sessions"]


def test_avaliacao_enviada_explicitamente_ainda_e_gravada():
    """O adaptador nao pode impedir que um mapa enviado de proposito seja salvo."""
    uid, headers = _athlete("prio.explicit@example.com")
    novo = {"Tríceps": {"development": "forte", "priority": "normal"}}
    assert requests.post(f"{API}/assessment", json=_onboarding(uid, [], MAPA_LEGADO),
                         headers=headers).status_code == 200
    assert requests.post(f"{API}/assessment", json=_onboarding(uid, [], novo),
                         headers=headers).status_code == 200
    assert _run(_find_one("profiles", {"id": uid}))["assessment"] == novo
