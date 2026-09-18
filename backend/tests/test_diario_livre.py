# -*- coding: utf-8 -*-
"""Diário livre: registrar o que se comeu de verdade, por refeição.

O FORGE ja guardava consumo fora do plano, mas de um jeito que ninguem usava: o registro
nao dizia de QUE refeicao era, entao voltava para a tela como "Extra · 320 kcal",
empilhado embaixo do plano. Sem o nome da refeicao, nao da para somar por refeicao nem
comparar com o que estava previsto.

Duas regras que estes testes prendem:

1. A refeicao vem do MESMO vocabulario do motor de nutricao (`breakfast`, `lunch`,
   `snack`...). Duas taxonomias de refeicao no mesmo produto viram dois relatorios que
   nao batem.

2. O diario NOMEADO e do Elite; o extra ANONIMO continua no Pro. Ninguem perde o que ja
   usava — o Pro segue registrando como sempre registrou, e o Elite ganha o nome, a soma
   por refeicao e, um dia, a leitura semanal olhando para isso.
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
from nutrition_routes import REFEICOES_DO_DIARIO  # noqa: E402

APP = server.app
DB = server.db


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


def _agora():
    return datetime.now(timezone.utc)


def _hoje():
    return CalendarDate.today().isoformat()


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta(plano="elite"):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"diario.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": _agora().isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(uid):
    for nome in ("users", "subscriptions", "profiles", "nutrition_consumed_extras",
                 "nutrition_adherence", "nutrition_plans", "conselho_semanal"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                            {"profile_id": uid}]})


def _registro(refeicao=None, food_id="egg", grams=100):
    corpo = {"date": _hoje(), "entry_id": str(uuid.uuid4()),
             "foods": [{"food_id": food_id, "grams": grams}]}
    if refeicao:
        corpo["refeicao"] = refeicao
    return corpo


async def _um_alimento_valido():
    """Um id que o catalogo do diario aceita, lido do proprio catalogo."""
    from food_diary import DIARY_FOODS
    return next(iter(DIARY_FOODS))


# ── O vocabulario ───────────────────────────────────────────────────────────────────

def test_as_refeicoes_do_diario_sao_as_do_motor_de_nutricao():
    """Duas taxonomias de refeicao no mesmo produto viram dois relatorios que nao batem."""
    from nutrition_engine import _REFEICAO_PARA_TAGS
    do_motor = set(_REFEICAO_PARA_TAGS)
    do_diario = set(REFEICOES_DO_DIARIO)
    # "supper" (ceia) e do diario e nao do gerador: o plano nao monta ceia, mas gente come.
    assert do_diario - do_motor <= {"supper"}
    assert do_motor - do_diario == set(), f"o motor tem refeicao que o diario nao aceita: {do_motor - do_diario}"


def test_toda_refeicao_tem_nome_em_portugues():
    for chave, nome in REFEICOES_DO_DIARIO.items():
        assert nome and nome[0].isupper(), f"{chave} sem nome apresentavel"
        assert "_" not in nome


@asincrono
async def test_a_tela_recebe_a_lista_do_servidor():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/nutrition/refeicoes-do-diario", headers=h)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()["refeicoes"]]
        assert ids == list(REFEICOES_DO_DIARIO)      # a ordem do dia, e nao alfabetica
        assert r.json()["refeicoes"][0]["nome"] == "Café da manhã"
    finally:
        await _limpar(uid)


# ── O registro com nome de refeicao ─────────────────────────────────────────────────

@asincrono
async def test_registrar_o_almoco_guarda_a_refeicao_e_soma():
    uid, h = await _atleta()
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/consumed-meal", headers=h,
                             json=_registro("lunch", alimento))
            assert r.status_code == 200, r.text
            assert r.json()["actual"]["totals"]["kcal"] > 0

            dia = (await c.get(f"/api/nutrition/adherence/{_hoje()}", headers=h)).json()
        extras = dia["extras"]
        assert len(extras) == 1
        assert extras[0]["refeicao"] == "lunch"
        assert extras[0]["refeicao_nome"] == "Almoço"
        assert extras[0]["actual"]["totals"]["kcal"] > 0
    finally:
        await _limpar(uid)


@asincrono
async def test_varias_refeicoes_no_mesmo_dia_ficam_separadas():
    """Cafe da manha e almoco sao duas linhas, e nao uma soma anonima."""
    uid, h = await _atleta()
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            for refeicao in ("breakfast", "lunch", "dinner"):
                await c.post("/api/nutrition/consumed-meal", headers=h,
                             json=_registro(refeicao, alimento))
            dia = (await c.get(f"/api/nutrition/adherence/{_hoje()}", headers=h)).json()
        nomes = sorted(e["refeicao"] for e in dia["extras"])
        assert nomes == ["breakfast", "dinner", "lunch"]
    finally:
        await _limpar(uid)


@asincrono
async def test_refeicao_inventada_e_recusada():
    uid, h = await _atleta()
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/consumed-meal", headers=h,
                             json=_registro("brunch", alimento))
        assert r.status_code == 422
    finally:
        await _limpar(uid)


@asincrono
async def test_o_registro_pode_ser_removido():
    uid, h = await _atleta()
    try:
        alimento = await _um_alimento_valido()
        corpo = _registro("snack", alimento)
        async with await _cliente() as c:
            await c.post("/api/nutrition/consumed-meal", headers=h, json=corpo)
            r = await c.delete(f"/api/nutrition/consumed-extra/{corpo['entry_id']}", headers=h)
            assert r.status_code == 200
            dia = (await c.get(f"/api/nutrition/adherence/{_hoje()}", headers=h)).json()
        assert dia["extras"] == []
    finally:
        await _limpar(uid)


# ── O portao, sem tirar nada de ninguem ─────────────────────────────────────────────

@asincrono
async def test_o_diario_nomeado_e_do_elite():
    uid, h = await _atleta(plano="pro")
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/consumed-meal", headers=h,
                             json=_registro("lunch", alimento))
        assert r.status_code == 402
        assert r.json()["detail"]["capability"] == "free_food_log"
    finally:
        await _limpar(uid)


@asincrono
async def test_o_extra_ANONIMO_continua_valendo_no_pro():
    """Ninguem perde o que ja usava: o Pro registra como sempre registrou."""
    uid, h = await _atleta(plano="pro")
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/consumed-meal", headers=h,
                             json=_registro(None, alimento))
            assert r.status_code == 200, r.text
            dia = (await c.get(f"/api/nutrition/adherence/{_hoje()}", headers=h)).json()
        assert len(dia["extras"]) == 1
        assert "refeicao" not in dia["extras"][0]
    finally:
        await _limpar(uid)


def test_a_capacidade_esta_no_elite_e_so_nele():
    import billing_plans as bp
    assert bp.DIARIO_LIVRE in bp.capacidades_do_plano("elite")
    assert bp.DIARIO_LIVRE not in bp.capacidades_do_plano("pro")
    assert bp.DIARIO_LIVRE not in bp.capacidades_do_plano("essential")


def test_o_elite_anuncia_o_diario_livre():
    """Recurso que esta no ar e nao esta escrito no plano nao vende."""
    import billing_plans as bp
    elite = bp.PLANOS_POR_CODIGO["elite"]
    assert any("iário livre" in r for r in elite["recursos"])


@asincrono
async def test_um_atleta_nao_ve_o_diario_do_outro():
    meu, hm = await _atleta()
    outro, ho = await _atleta()
    try:
        alimento = await _um_alimento_valido()
        async with await _cliente() as c:
            await c.post("/api/nutrition/consumed-meal", headers=ho,
                         json=_registro("lunch", alimento))
            dia = (await c.get(f"/api/nutrition/adherence/{_hoje()}", headers=hm)).json()
        assert dia["extras"] == []
    finally:
        await _limpar(meu)
        await _limpar(outro)
