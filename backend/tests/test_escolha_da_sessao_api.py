# -*- coding: utf-8 -*-
"""Escolher qual sessão treinar hoje, de ponta a ponta.

O caso real: um atleta adiantou o treino do fim de semana e, no dia seguinte, o FORGE
ofereceu de novo a sessão que ele acabara de fazer — a rotação não sabia que ele tinha
treinado fora da ordem. Ele quis fazer a seguinte e não teve como: a tela mostra UMA
sessão, a do ponteiro, e não havia onde escolher outra. Sem escolher, não dá para registrar
carga; sem registro, o treino não existe para o motor.

O que esta suíte cobre que a de unidade não alcança
---------------------------------------------------
A CONCLUSÃO. O `compare-and-swap` do ponteiro só deixa concluir quem tem o ponteiro parado
na sessão sendo concluída — e quem escolheu outra sessão tem o ponteiro legitimamente
noutro lugar. Sem tratar isso, o atleta escolheria, treinaria, e seria recusado na hora de
concluir: depois do treino feito, que é o pior lugar possível para descobrir.
"""
import functools
import os
import sys
import uuid
from datetime import datetime, timezone
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
from workout_calendar import calendar_today  # noqa: E402

APP, DB = server.app, server.db
EXS = ["bb-bench-press", "lat-pulldown", "hack-squat"]


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        return LOOP.run_until_complete(fn(*a, **k))
    return wrapper


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta_ppl():
    """Programa SEM dia da semana: ponteiro puro, que é o caso do relato."""
    os.environ["BILLING_ENFORCED"] = "false"
    uid = str(uuid.uuid4())
    sessoes = [{"day": d, "label": rot,
                "exercises": [{"exercise_id": e, "sets": 3, "reps": "8–12"} for e in EXS]}
               for d, rot in ((1, "Push"), (2, "Pull"), (3, "Legs"))]
    await DB.users.insert_one({
        "id": uid, "email": "escolha." + uid[:8] + "@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Atleta", "days": 3, "goal": "Hipertrofia",
        "experience": "Avançado", "session_minutes": 60, "automation_mode": "FORGE_PRO",
        "onboarding_required": False, "current_session_day": 1,
        "custom_program": {"name": "PPL", "sessions": sessoes}})
    return uid, {"Authorization": "Bearer " + create_token(uid, "ATHLETE")}


async def _limpar(uid):
    for nome in ("users", "profiles", "workout_completions", "subscriptions"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                            {"profile_id": uid}]})


@asincrono
async def test_a_tela_recebe_todas_as_sessoes_para_escolher():
    """Era isto que faltava: a tela mostrava uma sessão e não havia onde ver as outras."""
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/workout/sessoes-do-dia", headers=h)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert [s["label"] for s in corpo["sessoes"]] == ["Push", "Pull", "Legs"]
        assert corpo["escolhida"] is None
        assert corpo["ativa"] == 1
        assert all(s["exercicios"] == 3 for s in corpo["sessoes"])
    finally:
        await _limpar(uid)


@asincrono
async def test_escolher_troca_a_sessao_do_dia():
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/escolher-sessao", headers=h, json={"day": 3})
            assert r.status_code == 200, r.text
            programa = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert programa["active_day"] == 3
        assert programa["session"] == "Legs"
    finally:
        await _limpar(uid)


# O teste que justifica a suíte existir: sem tratar o CAS, isto vira "já concluído" —
# depois de o treino ter acontecido.
@asincrono
async def test_da_para_CONCLUIR_a_sessao_escolhida():
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            await c.post("/api/workout/escolher-sessao", headers=h, json={"day": 3})
            r = await c.post("/api/workout/complete", headers=h, json={"day": 3})
        assert r.status_code == 200, "concluir a escolhida falhou: " + r.text
        assert r.json().get("already_completed") is not True
        assert r.json()["completed_day"] == 3, "concluiu a sessao errada"
    finally:
        await _limpar(uid)


# Quem fez o Pull hoje recebe o Legs amanhã: a rotação segue do que foi FEITO, e não de
# onde o ponteiro estava parado. É o que qualquer pessoa espera.
@asincrono
async def test_a_rotacao_segue_a_partir_do_que_foi_feito():
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            await c.post("/api/workout/escolher-sessao", headers=h, json={"day": 2})
            r = await c.post("/api/workout/complete", headers=h, json={"day": 2})
        assert r.status_code == 200, r.text
        assert r.json()["next_day"] == 3, "não seguiu do Pull para o Legs"
        perfil = await DB.profiles.find_one({"id": uid}, {"_id": 0, "current_session_day": 1})
        assert perfil["current_session_day"] == 3
    finally:
        await _limpar(uid)


@asincrono
async def test_desfazer_devolve_a_sessao_do_programa():
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            await c.post("/api/workout/escolher-sessao", headers=h, json={"day": 3})
            r = await c.delete("/api/workout/escolher-sessao", headers=h)
            assert r.status_code == 200, r.text
            programa = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert r.json()["escolhida"] is None
        assert programa["active_day"] == 1, "não voltou para o ponteiro"
    finally:
        await _limpar(uid)


@asincrono
async def test_sessao_que_nao_existe_e_recusada():
    """Aceitar deixaria a tela sem sessão nenhuma, que é pior que recusar."""
    uid, h = await _atleta_ppl()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/escolher-sessao", headers=h, json={"day": 99})
        assert r.status_code == 422
        assert "programa" in r.json()["detail"].lower()
    finally:
        await _limpar(uid)


# A escolha é do dia. Amanhã o programa volta a mandar, senão o atleta abriria o aplicativo
# e receberia a sessão que escolheu ontem.
@asincrono
async def test_escolha_de_ontem_nao_vale_hoje():
    uid, h = await _atleta_ppl()
    try:
        await DB.profiles.update_one({"id": uid}, {"$set": {
            "sessao_do_dia": {"data": "2020-01-01", "day": 3}}})
        async with await _cliente() as c:
            programa = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert programa["active_day"] == 1, "a escolha de ontem sobreviveu"
    finally:
        await _limpar(uid)


@asincrono
async def test_escolha_apontando_para_sessao_removida_nao_quebra():
    """Quem escolheu o dia 9 e depois trocou para uma divisão de três dias."""
    uid, h = await _atleta_ppl()
    try:
        await DB.profiles.update_one({"id": uid}, {"$set": {
            "sessao_do_dia": {"data": calendar_today().isoformat(), "day": 9}}})
        async with await _cliente() as c:
            r = await c.get("/api/bootstrap", headers=h)
        assert r.status_code == 200
        assert r.json()["program"]["active_day"] == 1
    finally:
        await _limpar(uid)


@asincrono
async def test_as_rotas_exigem_login():
    async with await _cliente() as c:
        assert (await c.get("/api/workout/sessoes-do-dia")).status_code == 401
        assert (await c.post("/api/workout/escolher-sessao",
                             json={"day": 1})).status_code == 401
