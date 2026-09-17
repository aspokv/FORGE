# -*- coding: utf-8 -*-
"""O Conselho de ponta a ponta: banco, portao do plano e aplicacao da mudanca.

A suite `test_conselho.py` prova a decisao sobre dados em memoria. Esta prova as tres
coisas que so aparecem quando existe um Mongo do outro lado:

  1. o portao do plano, porque o Conselho e o conteudo do Elite;
  2. a idempotencia semanal, porque o placar de previsoes vira ficcao se cada visita a
     tela criar uma aposta nova;
  3. a aplicacao, porque mexer no alvo calorico de alguem e a unica coisa aqui que
     escreve no plano de verdade.

Roda o app EM PROCESSO, como `test_billing_api.py`, contra o banco descartavel.
"""
import functools
import os
import sys
import uuid
from datetime import date as CalendarDate, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
sys.path.insert(0, str(Path(__file__).parent.parent))

import server  # noqa: E402
from auth import create_token  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402

APP = server.app
DB = server.db


def asincrono(fn):
    """O mesmo laco de `test_billing_api.py`.

    O cliente do Motor nasce preso ao laco em que foi criado. Cada teste com laco proprio
    faz o driver reclamar de "future attached to a different loop", e o modulo inteiro cai.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


def _agora():
    return datetime.now(timezone.utc)


def _dia(n):
    return (_agora().date() - timedelta(days=n)).isoformat()


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta(plano="elite"):
    uid = str(uuid.uuid4())
    email = f"conselho.{uid[:8]}@example.com"
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Conselho Test", "role": "ATHLETE",
        "status": "ACTIVE", "created_at": _agora().isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "mercadopago", "amount_cents": 1, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(uid):
    for colecao in (DB.users, DB.subscriptions, DB.profiles, DB.nutrition_plans,
                    DB.nutrition_adherence, DB.nutrition_weight_logs, DB.set_logs,
                    DB.recovery, DB.conselho_semanal):
        await colecao.delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                           {"profile_id": uid}]})


async def _semear_semana(uid, *, alvo_kcal=2000, kcal_do_dia=2000, dias=7,
                         kg_por_semana=0.0, peso=90.0, objetivo="fat_loss"):
    """Um atleta com a semana inteira registrada e o peso travado.

    Tudo aqui e o dado CRU que o produto grava no uso normal: refeicao concluida em
    `nutrition_adherence`, pesagem em `nutrition_weight_logs`, serie em `set_logs`. E o
    ponto do teste: provar que a leitura sai do que o FORGE ja guarda, e nao de um
    formato inventado para o Conselho.
    """
    await DB.profiles.update_one({"id": uid}, {"$set": {
        "id": uid, "goal": objetivo, "latest_weight": peso}}, upsert=True)

    refeicoes = [{"name": "Refeicao unica", "target_cal": alvo_kcal, "foods": []}]
    await DB.nutrition_plans.update_one({"profile_id": uid}, {"$set": {
        "profile_id": uid,
        "plan": {"goal": objetivo, "meals": refeicoes,
                 "targets": {"goal_calories": alvo_kcal, "protein_g": 150,
                             "carbs_g": 200, "fat_g": 60}}}}, upsert=True)

    for n in range(dias):
        await DB.nutrition_adherence.update_one(
            {"_id": f"meal:{uid}:{_dia(n)}:0"},
            {"$set": {"profile_id": uid, "date": _dia(n), "meal_index": 0,
                      "status": "completed", "created_at": _agora().isoformat(),
                      # `actual.totals`, aninhado: e o formato que a tela de Nutricao
                      # grava e que `_totais_do_dia` le. Semear o macro solto passava
                      # silenciosamente como dia sem consumo.
                      "actual": {"totals": {"kcal": kcal_do_dia, "protein_g": 150,
                                            "carbs_g": 200, "fat_g": 60}}}}, upsert=True)

    for n in range(21, -1, -3):
        avancado = (21 - n) / 7.0
        await DB.nutrition_weight_logs.insert_one({
            "profile_id": uid, "date": _dia(n),
            "weight_kg": round(peso + kg_por_semana * avancado, 2),
            "created_at": _agora().isoformat()})

    # Quatro semanas de treino estavel, cada uma num unico dia.
    for semana in range(4):
        data = _dia(7 * semana)
        for i in range(20):
            await DB.set_logs.insert_one({
                "id": str(uuid.uuid4()), "profile_id": uid,
                "exercise_id": ["incline-smith", "leg-press", "lat-pulldown",
                                "barbell-curl"][i % 4],
                "set_number": (i % 4) + 1, "weight": 100.0, "reps": 8, "rir": 2,
                "created_at": f"{data}T10:00:00+00:00"})


# ── O portao do plano ───────────────────────────────────────────────────────────────

@asincrono
async def test_o_conselho_e_do_elite():
    """Ele e o conteudo que faz o Elite existir. Pro nao alcanca."""
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid, h = await _atleta(plano="pro")
    try:
        async with await _cliente() as c:
            r = await c.get("/api/conselho", headers=h)
        assert r.status_code == 402
        assert r.json()["detail"]["capability"] == "advanced_analytics"
    finally:
        await _limpar(uid)


@asincrono
async def test_anonimo_nao_ve_conselho_de_ninguem():
    async with await _cliente() as c:
        r = await c.get("/api/conselho")
    assert r.status_code == 401


# ── A leitura sai do que o FORGE ja grava ───────────────────────────────────────────

@asincrono
async def test_a_semana_registrada_com_o_peso_travado_vira_corte():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            r = await c.get("/api/conselho", headers=h)
        assert r.status_code == 200
        corpo = r.json()

        assert corpo["decisao"]["alavanca"] == "caloria"
        assert corpo["decisao"]["mudanca"]["tipo"] == "kcal"
        assert corpo["decisao"]["mudanca"]["delta"] < 0
        # A leitura viaja junto: sem os numeros, o veredito e palpite com tipografia.
        assert corpo["estado"]["comida"]["dias_registrados"] == 7
        assert corpo["estado"]["peso"]["suficiente"] is True
        assert corpo["decisao"]["previsao"]["frase"]
    finally:
        await _limpar(uid)


@asincrono
async def test_quem_nao_registrou_a_semana_nao_tem_o_plano_mexido():
    """A trava que impede o Conselho de virar um cortador de calorias automatico."""
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, dias=2, kg_por_semana=0.0)
        async with await _cliente() as c:
            r = await c.get("/api/conselho", headers=h)
        corpo = r.json()
        assert corpo["decisao"]["alavanca"] == "aderencia"
        assert corpo["decisao"]["mudanca"] is None
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_dado_nenhum_o_conselho_diz_que_nao_sabe_em_vez_de_chutar():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/conselho", headers=h)
        assert r.status_code == 200
        assert r.json()["decisao"]["alavanca"] == "sem_leitura"
        assert r.json()["decisao"]["mudanca"] is None
    finally:
        await _limpar(uid)


# ── A semana e decidida uma vez ─────────────────────────────────────────────────────

@asincrono
async def test_abrir_a_tela_cinco_vezes_nao_cria_cinco_conselhos():
    """Um conselho que muda a cada toque nao e um conselho, e o placar viraria ficcao."""
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            corpos = [(await c.get("/api/conselho", headers=h)).json() for _ in range(5)]
        assert len({c["decisao"]["motivo"] for c in corpos}) == 1
        assert await DB.conselho_semanal.count_documents({"profile_id": uid}) == 1
    finally:
        await _limpar(uid)


# ── A aplicacao ─────────────────────────────────────────────────────────────────────

@asincrono
async def test_aplicar_move_a_meta_e_preserva_a_proteina():
    """Proteina e fixa em gramas, como em `nutrition_periodization`. Um motor automatico
    nao tem autoridade para mexer nela."""
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, alvo_kcal=2000, kcal_do_dia=2000, kg_por_semana=0.0)
        async with await _cliente() as c:
            antes = (await c.get("/api/conselho", headers=h)).json()
            aplicado = await c.post("/api/conselho/aplicar", json={"aceitar": True}, headers=h)

        assert aplicado.status_code == 200
        alvos = aplicado.json()["targets"]
        assert alvos["goal_calories"] == antes["decisao"]["mudanca"]["para"]
        assert alvos["protein_g"] == 150           # intocada
        assert alvos["carbs_g"] < 200              # o corte saiu do carboidrato

        guardado = await DB.nutrition_plans.find_one({"profile_id": uid})
        assert guardado["plan"]["targets"]["goal_calories"] == alvos["goal_calories"]
    finally:
        await _limpar(uid)


@asincrono
async def test_aplicar_duas_vezes_nao_corta_duas_vezes():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            await c.get("/api/conselho", headers=h)
            primeira = await c.post("/api/conselho/aplicar", json={"aceitar": True}, headers=h)
            segunda = await c.post("/api/conselho/aplicar", json={"aceitar": True}, headers=h)
        assert primeira.json()["status"] == "aplicada"
        assert segunda.json()["status"] == "ja_aplicada"

        guardado = await DB.nutrition_plans.find_one({"profile_id": uid})
        assert guardado["plan"]["targets"]["goal_calories"] == \
            primeira.json()["targets"]["goal_calories"]
    finally:
        await _limpar(uid)


@asincrono
async def test_recusar_e_uma_resposta_valida_e_nao_muda_nada():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            await c.get("/api/conselho", headers=h)
            r = await c.post("/api/conselho/aplicar", json={"aceitar": False}, headers=h)
        assert r.json()["status"] == "recusada"
        guardado = await DB.nutrition_plans.find_one({"profile_id": uid})
        assert guardado["plan"]["targets"]["goal_calories"] == 2000
    finally:
        await _limpar(uid)


@asincrono
async def test_conselho_sem_mudanca_nao_tem_o_que_aplicar():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, dias=2, kg_por_semana=0.0)   # cai em "aderencia"
        async with await _cliente() as c:
            await c.get("/api/conselho", headers=h)
            r = await c.post("/api/conselho/aplicar", json={"aceitar": True}, headers=h)
        assert r.status_code == 422
    finally:
        await _limpar(uid)


@asincrono
async def test_um_atleta_nao_ve_o_conselho_do_outro():
    os.environ["BILLING_ENFORCED"] = "true"
    uid_a, ha = await _atleta()
    uid_b, hb = await _atleta()
    try:
        await _semear_semana(uid_a, kg_por_semana=0.0)
        async with await _cliente() as c:
            a = (await c.get("/api/conselho", headers=ha)).json()
            b = (await c.get("/api/conselho", headers=hb)).json()
        assert a["decisao"]["alavanca"] == "caloria"
        assert b["decisao"]["alavanca"] == "sem_leitura"
        assert await DB.conselho_semanal.count_documents({"profile_id": uid_b}) == 1
    finally:
        await _limpar(uid_a)
        await _limpar(uid_b)


@asincrono
async def test_o_historico_devolve_o_placar():
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            await c.get("/api/conselho", headers=h)
            r = await c.get("/api/conselho/historico", headers=h)
        assert r.status_code == 200
        assert len(r.json()["semanas"]) == 1
        assert r.json()["retrospecto"]["julgadas"] == 0   # ainda nao houve o que julgar
    finally:
        await _limpar(uid)


# ── O mapa de musculos ──────────────────────────────────────────────────────────────

def test_o_mapa_de_exercicios_para_musculos_nao_vem_vazio():
    """Um mapa vazio nao quebra nada, e esse e o problema.

    `exercises.json` guarda `primary_muscle`; `server.EXERCISES` e a versao traduzida para
    a interface, onde o campo se chama `muscle`. Lendo o nome errado o mapa saia vazio,
    `volume_por_semana` descartava TODAS as series em silencio, e o Conselho dizia
    "poucas semanas de treino" para quem treinava havia um mes.
    """
    from conselho_routes import _musculo_por_exercicio
    mapa = _musculo_por_exercicio()
    assert len(mapa) > 100, f"mapa suspeito: {len(mapa)} exercicios"
    assert mapa.get("incline-smith")
    assert all(v for v in mapa.values())


@asincrono
async def test_o_volume_de_quem_treina_ha_um_mes_e_lido():
    """A regressao ponta a ponta do mapa vazio: quatro semanas de treino tem que virar
    leitura de volume, e nao "poucas semanas"."""
    os.environ["BILLING_ENFORCED"] = "true"
    uid, h = await _atleta()
    try:
        await _semear_semana(uid, kg_por_semana=0.0)
        async with await _cliente() as c:
            corpo = (await c.get("/api/conselho", headers=h)).json()
        volume = corpo["estado"]["volume"]
        assert volume["suficiente"] is True, volume.get("motivo")
        assert volume["series_agora"] > 0
        assert volume["por_musculo"]
    finally:
        await _limpar(uid)
