# -*- coding: utf-8 -*-
"""Periodização automática da dieta, de ponta a ponta (Elite).

O que esta suíte cobre que a de unidade não alcança: a porta do plano, a semana que vence
e é aplicada ao abrir a nutrição (meta E prato), a balança segurando o degrau, a
aplicação que não acontece duas vezes, e o Conselho saindo da frente da caloria.

As semanas passam mexendo no `inicio` gravado, e não no relógio: a aplicação lê o
calendário do dia, e voltar o início uma semana é exatamente "uma semana depois".
"""
import functools
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
sys.path.insert(0, str(Path(__file__).parent.parent))

import server  # noqa: E402
from auth import create_token  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402
from nutrition_import import draft_to_plan, parse_diet_text  # noqa: E402
from workout_calendar import calendar_today  # noqa: E402

APP = server.app
DB = server.db
DIETA = """Café da manhã
Aveia: 80 g
Banana: 150 g
Almoço
Peito de frango grelhado: 200 g
Batata inglesa: 250 g
Jantar
Carne bovina: 200 g
Arroz branco: 200 g
Ceia
Iogurte natural: 200 g
Whey: 30 g"""


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP), base_url="http://forge.test")


async def _atleta(plano="elite", objetivo="fat_loss"):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    agora = datetime.now(timezone.utc).isoformat()
    await DB.users.insert_one({
        "id": uid, "email": f"periodizacao.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": agora, "signup_source": "public",
        "archived_at": None, "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active", "provider": "courtesy",
        "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    await DB.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Atleta", "onboarding_required": False, "latest_weight": 83,
        "nutrition_assessment": {"weight_kg": 83, "height_cm": 180, "age": 30, "sex": "male",
                                 "goal": objetivo, "activity_level": "moderate", "training_days": 5,
                                 "meal_count": 3, "allergies": [], "dietary_restrictions": []}})
    await DB.nutrition_plans.insert_one({"profile_id": uid, "user_id": uid, "created_at": agora,
                                         "plan": draft_to_plan(parse_diet_text(DIETA))})
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(uid):
    for nome in ("users", "subscriptions", "profiles", "nutrition_plans", "nutrition_plan_versions",
                 "periodizacao_da_dieta", "nutrition_weight_logs", "conselho_semanal"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid}, {"profile_id": uid}]})


async def _passar_semanas(uid, n):
    doc = await DB.periodizacao_da_dieta.find_one({"profile_id": uid, "status": "ativa"})
    inicio = datetime.fromisoformat(doc["inicio"]).date() - timedelta(days=7 * n)
    await DB.periodizacao_da_dieta.update_one({"_id": doc["_id"]}, {"$set": {"inicio": inicio.isoformat()}})


async def _plano(uid):
    return (await DB.nutrition_plans.find_one({"profile_id": uid}))["plan"]


def _gramas(plano, food_id):
    return [f["grams"] for m in plano["meals"] for f in m["foods"] if f["food_id"] == food_id][0]


ATIVAR = {"fase": "corte", "semanas": 4, "ritmo": "moderado"}


@asincrono
async def test_so_o_elite_periodiza():
    uid, h = await _atleta("pro")
    try:
        async with await _cliente() as c:
            estado = (await c.get("/api/nutrition/periodizacao", headers=h)).json()
            previa = await c.post("/api/nutrition/periodizacao/previa", headers=h, json=ATIVAR)
            ativar = await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
        assert estado["liberado"] is False
        assert (previa.status_code, ativar.status_code) == (402, 402)
    finally:
        await _limpar(uid)


@asincrono
async def test_previa_mostra_as_semanas_e_o_prato_sem_mudar_nada():
    uid, h = await _atleta()
    try:
        antes = await _plano(uid)
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/periodizacao/previa", headers=h, json=ATIVAR)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert len(corpo["tabela"]) == 4 and corpo["tabela"][0]["kcal"] == corpo["base"]["kcal"]
        assert any(m["alimento"].startswith("Batata") for m in corpo["no_prato"])
        assert await _plano(uid) == antes
    finally:
        await _limpar(uid)


@asincrono
async def test_uma_semana_depois_a_meta_e_o_prato_descem_juntos():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            assert (await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)).status_code == 200
            semana1 = await _plano(uid)
            await _passar_semanas(uid, 1)
            plano = (await c.get("/api/nutrition/plan", headers=h)).json()
            estado = (await c.get("/api/nutrition/periodizacao", headers=h)).json()
        doc = estado["periodizacao"]
        assert plano["targets"]["carbs_g"] == doc["tabela"][1]["carbs_g"]
        assert plano["targets"]["goal_calories"] < semana1["targets"]["goal_calories"]
        assert plano["targets"]["protein_g"] == semana1["targets"]["protein_g"]
        assert _gramas(plano, "potato") < _gramas(semana1, "potato")
        assert _gramas(plano, "chicken-breast") == _gramas(semana1, "chicken-breast")
        ultima = doc["historico"][-1]
        # Sem pesagem o calendário segue — e a tela pede a pesagem de sexta.
        assert ultima["decisao"] == "avancar" and "sexta" in ultima["motivo"]
        # O plano de antes ficou guardado.
        assert await DB.nutrition_plan_versions.count_documents(
            {"profile_id": uid, "reason": "periodizacao_inicio"}) == 1
    finally:
        await _limpar(uid)


@asincrono
async def test_abrir_duas_vezes_nao_corta_duas_vezes():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
            await _passar_semanas(uid, 1)
            primeira = (await c.get("/api/nutrition/plan", headers=h)).json()
            segunda = (await c.get("/api/nutrition/plan", headers=h)).json()
        assert primeira["targets"] == segunda["targets"]
        assert _gramas(primeira, "potato") == _gramas(segunda, "potato")
    finally:
        await _limpar(uid)


@asincrono
async def test_perdendo_rapido_demais_a_balanca_segura_o_degrau():
    uid, h = await _atleta()
    try:
        hoje = calendar_today()
        # Quase 2 kg em duas semanas: mais de 1% do peso por semana.
        for dias, peso in ((14, 85.0), (7, 84.0), (0, 83.0)):
            await DB.nutrition_weight_logs.insert_one({"profile_id": uid, "user_id": uid, "weight_kg": peso,
                                                       "date": (hoje - timedelta(days=dias)).isoformat()})
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
            antes = await _plano(uid)
            await _passar_semanas(uid, 1)
            plano = (await c.get("/api/nutrition/plan", headers=h)).json()
            doc = (await c.get("/api/nutrition/periodizacao", headers=h)).json()["periodizacao"]
        assert doc["historico"][-1]["decisao"] == "segurar"
        assert plano["targets"]["goal_calories"] == antes["targets"]["goal_calories"]
        assert _gramas(plano, "potato") == _gramas(antes, "potato")
    finally:
        await _limpar(uid)


@asincrono
async def test_depois_da_ultima_semana_a_fase_termina_e_o_plano_fica():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json={**ATIVAR, "semanas": 2})
            await _passar_semanas(uid, 1)
            semana2 = (await c.get("/api/nutrition/plan", headers=h)).json()
            await _passar_semanas(uid, 1)
            depois = (await c.get("/api/nutrition/plan", headers=h)).json()
            estado = (await c.get("/api/nutrition/periodizacao", headers=h)).json()
        assert estado["periodizacao"]["status"] == "concluida"
        assert depois["targets"] == semana2["targets"]
    finally:
        await _limpar(uid)


@asincrono
async def test_encerrar_para_a_fase_e_nao_mexe_no_plano():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
            antes = await _plano(uid)
            assert (await c.post("/api/nutrition/periodizacao/encerrar", headers=h)).status_code == 200
            await DB.periodizacao_da_dieta.update_one({"profile_id": uid}, {"$set": {"inicio": "2020-01-01"}})
            plano = (await c.get("/api/nutrition/plan", headers=h)).json()
            outra = await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
        assert plano["targets"] == antes["targets"]
        assert outra.status_code == 200   # encerrada, dá para começar outra
    finally:
        await _limpar(uid)


@asincrono
async def test_duas_fases_ao_mesmo_tempo_nao():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
            r = await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
        assert r.status_code == 409
    finally:
        await _limpar(uid)


@asincrono
async def test_manutencao_precisa_dizer_a_fase():
    uid, h = await _atleta(objetivo="maintenance")
    try:
        async with await _cliente() as c:
            sem = await c.post("/api/nutrition/periodizacao/previa", headers=h, json={"semanas": 4, "ritmo": "moderado"})
            com = await c.post("/api/nutrition/periodizacao/previa", headers=h,
                               json={"fase": "ganho", "semanas": 4, "ritmo": "moderado"})
        assert sem.status_code == 422 and "corte ou de ganho" in sem.json()["detail"]
        assert com.status_code == 200
    finally:
        await _limpar(uid)


@asincrono
async def test_com_a_fase_em_andamento_o_conselho_nao_mexe_na_caloria():
    from conselho_routes import _respeitar_periodizacao
    uid, h = await _atleta()
    try:
        decisao = {"alavanca": "caloria", "motivo": "Corta.", "mudanca": {"tipo": "kcal", "de": 2000, "para": 1850}}
        assert (await _respeitar_periodizacao(DB, uid, decisao))["mudanca"] is not None
        async with await _cliente() as c:
            await c.post("/api/nutrition/periodizacao/ativar", headers=h, json=ATIVAR)
        ajustada = await _respeitar_periodizacao(DB, uid, decisao)
        assert ajustada["mudanca"] is None
        assert "periodização" in ajustada["motivo"]
        # O que não é caloria passa intacto.
        treino = {"alavanca": "treino", "mudanca": {"tipo": "volume"}}
        assert await _respeitar_periodizacao(DB, uid, treino) == treino
    finally:
        await _limpar(uid)


@asincrono
async def test_agressivo_no_corte_leva_o_carbo_perto_do_minimo_do_prato_sem_zerar():
    import periodizacao_automatica as pa
    from food_diary import DIARY_FOODS
    from nutrition_engine import FOOD_INDEX
    uid, h = await _atleta()
    try:
        plano = await _plano(uid)
        minimo = pa.carbo_minimo_do_prato(plano["meals"], FOOD_INDEX, DIARY_FOODS)
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/periodizacao/previa", headers=h,
                             json={"fase": "corte", "semanas": 12, "ritmo": "agressivo"})
            assert r.status_code == 200, r.text
            ligar = await c.post("/api/nutrition/periodizacao/ativar", headers=h,
                                 json={"fase": "corte", "semanas": 12, "ritmo": "agressivo"})
        tabela = r.json()["tabela"]
        assert min(l["carbs_g"] for l in tabela) >= max(minimo, 40) > 0
        assert tabela[-1]["carbs_g"] < tabela[0]["carbs_g"] / 2
        assert ligar.status_code == 200
    finally:
        await _limpar(uid)
