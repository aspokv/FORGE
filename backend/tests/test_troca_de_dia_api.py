# -*- coding: utf-8 -*-
"""Trocar o dia de treino, de ponta a ponta.

O caso real: um atleta ia viajar no fim de semana e quis adiantar o treino de sábado para
a quinta, que na agenda dele é descanso. A tela de descanso não tem sessão, nem lista de
exercícios, nem botão de iniciar — e o único caminho oferecido, a Biblioteca, SUBSTITUI a
sessão ativa. Resolver uma semana atípica exigia mexer no programa.

O que esta suíte cobre que a de unidade não alcança
---------------------------------------------------
A de unidade prova que o calendário aplica a troca. Esta prova que o PRODUTO inteiro
respeita: o programa montado, a rota que grava, e principalmente a CONCLUSÃO — que recusa
com 409 uma sessão que não bate com o calendário do dia. Sem a troca chegar lá, o atleta
treinaria no dia adiantado e seria impedido de concluir, que é o pior lugar possível para
descobrir o problema.

As datas são calculadas a partir de HOJE, e não escritas à mão: a validação da troca só
aceita datas da semana que vem, então uma data fixa faria a suíte passar hoje e reprovar
amanhã.
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
import troca_de_dia  # noqa: E402
from auth import create_token  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402
from workout_calendar import calendar_today  # noqa: E402

APP = server.app
DB = server.db

DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta_com_descanso_hoje():
    """Um atleta cujo programa dá descanso HOJE e treino AMANHÃ.

    Montado relativo a hoje de propósito: é exatamente a situação que motivou a feature, e
    fixar dias da semana faria a suíte cobrir o caso só uma vez por semana.
    """
    os.environ["BILLING_ENFORCED"] = "false"
    uid = str(uuid.uuid4())
    hoje = calendar_today()
    hoje_wd, amanha_wd = hoje.weekday(), (hoje + timedelta(days=1)).weekday()
    sessoes = [
        {"day": i + 1, "label": f"{DIAS[wd]} · Sessão {i + 1}",
         "exercises": [{"exercise_id": "bb-bench-press", "sets": 3, "reps": "8–12"}]}
        for i, wd in enumerate(w for w in range(7) if w != hoje_wd)
    ]
    await DB.users.insert_one({
        "id": uid, "email": f"troca.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Atleta", "days": 6,
        "goal": "Hipertrofia", "experience": "Avançado", "session_minutes": 60,
        "automation_mode": "FORGE_PRO", "onboarding_required": False,
        "custom_program": {"name": "Programa da semana", "sessions": sessoes}})
    cabecalho = {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}
    amanha_dia = next(s["day"] for s in sessoes if s["label"].startswith(DIAS[amanha_wd]))
    return uid, cabecalho, hoje, amanha_dia


async def _limpar(uid):
    for nome in ("users", "profiles", "workout_completions", "subscriptions"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                            {"profile_id": uid}]})


@asincrono
async def test_hoje_e_descanso_antes_da_troca():
    uid, h, _, _ = await _atleta_com_descanso_hoje()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/bootstrap", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["program"]["rest_day"] is True
    finally:
        await _limpar(uid)


@asincrono
async def test_trocar_traz_o_treino_de_amanha_para_hoje():
    """O pedido em uma frase: quero treinar hoje e descansar amanhã."""
    uid, h, hoje, amanha_dia = await _atleta_com_descanso_hoje()
    try:
        amanha = (hoje + timedelta(days=1)).isoformat()
        async with await _cliente() as c:
            r = await c.post("/api/workout/trocar-dia", headers=h,
                             json={"treinar_em": hoje.isoformat(), "descansar_em": amanha})
            assert r.status_code == 200, r.text
            programa = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert programa.get("rest_day") is not True, "hoje continuou como descanso"
        assert programa["active_day"] == amanha_dia, "não trouxe a sessão de amanhã"
        assert programa["sessions"], "sem sessões para treinar"
    finally:
        await _limpar(uid)


# A ponta que falta quebra o volume da semana em silêncio: sem ela o atleta faria a mesma
# sessão duas vezes, hoje e amanhã.
@asincrono
async def test_o_dia_de_origem_vira_descanso():
    uid, h, hoje, _ = await _atleta_com_descanso_hoje()
    try:
        amanha = (hoje + timedelta(days=1)).isoformat()
        async with await _cliente() as c:
            await c.post("/api/workout/trocar-dia", headers=h,
                         json={"treinar_em": hoje.isoformat(), "descansar_em": amanha})
            r = await c.get("/api/workout/trocas-de-dia", headers=h)
        dias = {d["data"]: d for d in r.json()["dias"]}
        assert dias[hoje.isoformat()]["treino"] is True
        assert dias[amanha]["treino"] is False
    finally:
        await _limpar(uid)


# O pior lugar para descobrir um defeito: o atleta treina e não consegue concluir.
@asincrono
async def test_da_para_CONCLUIR_o_treino_no_dia_trocado():
    uid, h, hoje, amanha_dia = await _atleta_com_descanso_hoje()
    try:
        amanha = (hoje + timedelta(days=1)).isoformat()
        async with await _cliente() as c:
            await c.post("/api/workout/trocar-dia", headers=h,
                         json={"treinar_em": hoje.isoformat(), "descansar_em": amanha})
            r = await c.post("/api/workout/complete", headers=h,
                             json={"local_date": hoje.isoformat(), "day": amanha_dia})
        assert r.status_code == 200, f"concluir no dia trocado falhou: {r.status_code} {r.text}"
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_a_troca_concluir_no_descanso_e_recusado():
    """A guarda continua valendo para quem NÃO trocou — ela existe por um motivo."""
    uid, h, hoje, amanha_dia = await _atleta_com_descanso_hoje()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/complete", headers=h,
                             json={"local_date": hoje.isoformat(), "day": amanha_dia})
        assert r.status_code == 409
    finally:
        await _limpar(uid)


@asincrono
async def test_desfazer_devolve_a_agenda_do_programa():
    uid, h, hoje, _ = await _atleta_com_descanso_hoje()
    try:
        amanha = (hoje + timedelta(days=1)).isoformat()
        async with await _cliente() as c:
            await c.post("/api/workout/trocar-dia", headers=h,
                         json={"treinar_em": hoje.isoformat(), "descansar_em": amanha})
            r = await c.delete("/api/workout/trocar-dia", headers=h)
            assert r.status_code == 200, r.text
            programa = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert r.json()["trocas"] == []
        assert programa["rest_day"] is True, "desfazer não devolveu o descanso de hoje"
    finally:
        await _limpar(uid)


@asincrono
async def test_nao_da_para_descansar_num_dia_que_ja_e_descanso():
    """Não há treino ali para mover, e aceitar daria a impressão de que algo aconteceu."""
    uid, h, hoje, _ = await _atleta_com_descanso_hoje()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/trocar-dia", headers=h,
                             json={"treinar_em": (hoje + timedelta(days=1)).isoformat(),
                                   "descansar_em": hoje.isoformat()})
        assert r.status_code == 409
        assert "descanso" in r.json()["detail"].lower()
    finally:
        await _limpar(uid)


@asincrono
async def test_data_invalida_explica_o_que_fazer():
    uid, h, hoje, _ = await _atleta_com_descanso_hoje()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/trocar-dia", headers=h,
                             json={"treinar_em": (hoje - timedelta(days=2)).isoformat(),
                                   "descansar_em": (hoje + timedelta(days=1)).isoformat()})
        assert r.status_code == 422
        assert "passou" in r.json()["detail"]
    finally:
        await _limpar(uid)


@asincrono
async def test_a_rota_exige_login():
    async with await _cliente() as c:
        assert (await c.get("/api/workout/trocas-de-dia")).status_code == 401
        assert (await c.post("/api/workout/trocar-dia",
                             json={"treinar_em": "2026-09-24",
                                   "descansar_em": "2026-09-26"})).status_code == 401


@asincrono
async def test_um_atleta_nao_troca_o_dia_do_outro():
    uid, h, hoje, _ = await _atleta_com_descanso_hoje()
    outro, h2, _, _ = await _atleta_com_descanso_hoje()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/workout/trocar-dia", headers=h2,
                             json={"treinar_em": hoje.isoformat(),
                                   "descansar_em": (hoje + timedelta(days=1)).isoformat(),
                                   "profile_id": uid})
        # `owned_profile_id` ignora o `profile_id` do corpo para ATHLETE e usa o do token:
        # o pedido é aceito, mas quem muda é quem pediu. O que importa medir é a VÍTIMA.
        assert r.status_code == 200, r.text
        perfil = await DB.profiles.find_one({"id": uid}, {"_id": 0, "trocas_de_dia": 1})
        assert not (perfil or {}).get("trocas_de_dia"), "trocou o dia do vizinho"
        vizinho = await DB.profiles.find_one({"id": outro}, {"_id": 0, "trocas_de_dia": 1})
        assert (vizinho or {}).get("trocas_de_dia"), "a troca não foi para quem pediu"
    finally:
        await _limpar(uid)
        await _limpar(outro)


def test_o_alcance_esta_declarado_e_e_curto():
    """Mover para fora da semana não é mover: é mudar o programa sem o motor recalcular."""
    assert troca_de_dia.ALCANCE_EM_DIAS == 7
