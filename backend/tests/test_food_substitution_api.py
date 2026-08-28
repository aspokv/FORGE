"""Substituicao de alimentos ponta a ponta: aplicar, persistir e nao duplicar.

O que se valida aqui e o que o endpoint GRAVA — nao adianta a validacao aprovar uma
porcao se o que fica salvo e outra coisa.
"""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
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
SENHA = "SubsApiTest2026!"
OVOS = {"eggs-whole", "egg-whites", "chicken-egg-omelet"}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _find_one(collection, query, projection=None):
    return await _db()[collection].find_one(query, projection)


async def _reset(email):
    db = _db()
    antigo = await db.users.find_one({"email": email})
    if antigo:
        for col in ("profiles", "nutrition_plans", "nutrition_plan_drafts"):
            await db[col].delete_many({"profile_id": antigo["id"]})
        await db.users.delete_one({"email": email})
        await db.login_attempts.delete_many({"identifier": {"$regex": email}})
    uid, invite = str(uuid.uuid4()), secrets.token_urlsafe(32)
    await db.users.insert_one({
        "id": uid, "email": email, "name": "Subs Test", "role": "ATHLETE",
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
                      json={"token": invite, "password": SENHA, "name": "Subs Test"})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _login(email):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _plano(headers, intensidade="moderado", goal="fat_loss", alergias=None):
    corpo = {"weight_kg": 85, "height_cm": 178, "age": 30, "sex": "male", "goal": goal,
             "intensity": intensidade, "activity_level": "moderate", "training_days": 4,
             "meal_count": 4, "cooking_time": "medium", "allergies": alergias or []}
    assert requests.post(f"{API}/nutrition/assessment", json=corpo,
                         headers=headers).status_code == 200
    r = requests.post(f"{API}/nutrition/generate", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _opcoes(headers, mi, fid):
    r = requests.post(f"{API}/nutrition/substitute", headers=headers,
                      json={"meal_index": mi, "food_id": fid})
    assert r.status_code == 200, r.text
    return r.json()


def _primeira_proteina(plano):
    for mi, meal in enumerate(plano["meals"]):
        for item in meal["foods"]:
            if (item.get("food") or {}).get("category") == "PROTEIN":
                return mi, item
    raise AssertionError("nenhuma proteina no plano")


# --- opcoes ricas -------------------------------------------------------------------

def test_alimento_comum_oferece_varias_opcoes_com_macros_e_selo():
    _, headers = _athlete("subs.rich@example.com")
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    corpo = _opcoes(headers, mi, item["food_id"])

    opts = corpo["options"]
    assert len(opts) >= 4, f"apenas {len(opts)} opcoes para {item['food_id']}"
    assert corpo["original_macros"]["kcal"] > 0
    for o in opts:
        assert o["grams"] > 0
        for macro in ("kcal", "protein_g", "carbs_g", "fat_g"):
            assert macro in o["macros"]
        assert "delta_kcal" in o
        assert o["food_id"] != item["food_id"]
    assert any(o.get("badge") == "Mais equivalente" for o in opts)
    # o campo interno de dimensionamento nao vaza para a interface
    assert all("_sim" not in o for o in opts)


def test_nenhuma_proteina_do_plano_fica_sem_opcao():
    _, headers = _athlete("subs.nonempty@example.com")
    plano = _plano(headers)["plan"]
    vazios = []
    for mi, meal in enumerate(plano["meals"]):
        for item in meal["foods"]:
            if (item.get("food") or {}).get("category") != "PROTEIN":
                continue
            if not _opcoes(headers, mi, item["food_id"])["options"]:
                vazios.append((meal["name"], item["food_id"]))
    assert not vazios, f"sem opcao: {vazios}"


# --- aplicar e persistir ------------------------------------------------------------

def test_substituicao_aplicada_persiste_apos_refresh_e_novo_login():
    email = "subs.persist@example.com"
    uid, headers = _athlete(email)
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    escolha = _opcoes(headers, mi, item["food_id"])["options"][0]

    r = requests.post(f"{API}/nutrition/substitute", headers=headers, json={
        "meal_index": mi, "food_id": item["food_id"],
        "substitute_food_id": escolha["food_id"]})
    assert r.status_code == 200, r.text

    def ids_da_refeicao(p):
        return [x["food_id"] for x in p["meals"][mi]["foods"]]

    assert escolha["food_id"] in ids_da_refeicao(r.json()["plan"])
    assert item["food_id"] not in ids_da_refeicao(r.json()["plan"])

    # refresh
    depois = requests.get(f"{API}/nutrition/plan", headers=headers).json()
    assert escolha["food_id"] in ids_da_refeicao(depois)
    # outro aparelho
    outro = requests.get(f"{API}/nutrition/plan", headers=_login(email)).json()
    assert escolha["food_id"] in ids_da_refeicao(outro)
    # e no banco
    doc = _run(_find_one("nutrition_plans", {"profile_id": uid}, {"_id": 0}))
    assert escolha["food_id"] in [x["food_id"] for x in doc["plan"]["meals"][mi]["foods"]]


def test_o_total_diario_e_recalculado_apos_a_troca():
    _, headers = _athlete("subs.totals@example.com")
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    escolha = _opcoes(headers, mi, item["food_id"])["options"][0]
    r = requests.post(f"{API}/nutrition/substitute", headers=headers, json={
        "meal_index": mi, "food_id": item["food_id"],
        "substitute_food_id": escolha["food_id"]})
    novos = r.json()["plan"]["daily_totals"]
    soma = sum(sum(f["food"]["kcal"] * f["grams"] / max(1, f["food"]["grams"])
                   for f in m["foods"]) for m in r.json()["plan"]["meals"])
    assert abs(novos["kcal"] - soma) <= 2, "daily_totals nao bate com as refeicoes"


def test_dois_cliques_seguidos_nao_duplicam_a_troca():
    _, headers = _athlete("subs.double@example.com")
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    antes = len(plano["meals"][mi]["foods"])
    escolha = _opcoes(headers, mi, item["food_id"])["options"][0]

    corpo = {"meal_index": mi, "food_id": item["food_id"],
             "substitute_food_id": escolha["food_id"]}
    primeira = requests.post(f"{API}/nutrition/substitute", headers=headers, json=corpo)
    assert primeira.status_code == 200
    # o segundo clique chega com o alimento antigo, que ja nao esta na refeicao
    segunda = requests.post(f"{API}/nutrition/substitute", headers=headers, json=corpo)
    assert segunda.status_code == 404, f"esperado 404 idempotente, veio {segunda.status_code}"

    final = requests.get(f"{API}/nutrition/plan", headers=headers).json()
    ids = [x["food_id"] for x in final["meals"][mi]["foods"]]
    assert len(ids) == antes, "a refeicao mudou de tamanho"
    assert ids.count(escolha["food_id"]) == 1, "o substituto entrou duas vezes"


def test_as_outras_refeicoes_nao_sao_alteradas():
    _, headers = _athlete("subs.isolated@example.com")
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    outras_antes = {j: [x["food_id"] for x in m["foods"]]
                    for j, m in enumerate(plano["meals"]) if j != mi}
    escolha = _opcoes(headers, mi, item["food_id"])["options"][0]
    requests.post(f"{API}/nutrition/substitute", headers=headers, json={
        "meal_index": mi, "food_id": item["food_id"],
        "substitute_food_id": escolha["food_id"]})
    depois = requests.get(f"{API}/nutrition/plan", headers=headers).json()
    outras_depois = {j: [x["food_id"] for x in m["foods"]]
                     for j, m in enumerate(depois["meals"]) if j != mi}
    assert outras_antes == outras_depois


# --- protecoes ----------------------------------------------------------------------

def test_alergia_em_portugues_bloqueia_no_endpoint():
    _, headers = _athlete("subs.alergia@example.com")
    plano = _plano(headers, alergias=["ovo"])["plan"]
    oferecidos = set()
    for mi, meal in enumerate(plano["meals"]):
        for item in meal["foods"]:
            oferecidos |= {o["food_id"] for o in _opcoes(headers, mi, item["food_id"])["options"]}
    assert oferecidos, "nenhuma opcao em nenhum alimento"
    assert not (oferecidos & OVOS)


@pytest.mark.parametrize("intensidade", ["agressivo", "moderado"])
def test_aplicar_qualquer_opcao_nunca_estoura_o_teto_do_protocolo(intensidade):
    _, headers = _athlete(f"subs.teto.{intensidade}@example.com")
    gerado = _plano(headers, intensidade)
    teto = gerado["targets"].get("carb_ceiling_g")
    plano = gerado["plan"]
    for mi, meal in enumerate(plano["meals"]):
        for item in list(meal["foods"]):
            opts = _opcoes(headers, mi, item["food_id"])["options"]
            if not opts:
                continue
            r = requests.post(f"{API}/nutrition/substitute", headers=headers, json={
                "meal_index": mi, "food_id": item["food_id"],
                "substitute_food_id": opts[0]["food_id"]})
            if r.status_code != 200:
                continue
            if teto is not None:
                assert r.json()["plan"]["daily_totals"]["carbs_g"] <= teto + 0.5


def test_substituto_invalido_e_recusado_com_mensagem():
    _, headers = _athlete("subs.invalid@example.com")
    plano = _plano(headers)["plan"]
    mi, item = _primeira_proteina(plano)
    r = requests.post(f"{API}/nutrition/substitute", headers=headers, json={
        "meal_index": mi, "food_id": item["food_id"], "substitute_food_id": "rice-white"})
    assert r.status_code == 400
    assert "nao permitida" in r.json()["detail"].lower()
