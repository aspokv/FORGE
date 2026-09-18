# -*- coding: utf-8 -*-
"""A leitura semanal e gravada para TODO atleta, veja ele o Conselho ou nao.

Por que isto existe
-------------------
Cada semana gravada e um experimento completo:

    estado    -> a condicao antes (aderencia, peso, volume, falhas, prontidao)
    decisao   -> a intervencao que o motor escolheu
    previsao  -> a aposta falsificavel
    aplicada  -> se a pessoa fez
    conferido -> o que aconteceu de verdade, medido na semana seguinte

Com isso da para responder, sobre a base inteira, se os limiares do motor estao certos:
`PASSO_CALORICO` de 8%, `QUEDA_DE_VOLUME` de 15%, as faixas de `RITMO_ESPERADO`. Hoje
esses numeros sao julgamento, e o motor aposta neles toda semana sem nunca conferir se a
aposta e boa.

A decisao so APARECE para quem tem `advanced_analytics`. Gravar so para quem ve seria
aprender com a fatia que paga mais, e comecar a contar o tempo do zero no dia em que
alguem resolvesse medir. Por isso a gravacao e separada da exibicao, e estes testes
prendem essa separacao.

O campo `visivel` tambem nao e enfeite: quem nao ve nunca aplica, quem ve escolhe. Sao
tres grupos, e misturar os tres numa media transforma a analise futura em correlacao
disfarcada de causa. E nao da para reconstruir isso depois, porque o plano da pessoa muda.
"""
import functools
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
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
from conselho_routes import _semana_de, registrar_semana  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402

APP = server.app
DB = server.db


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


def _agora():
    return datetime.now(timezone.utc)


def _semana_atual():
    return _semana_de(_agora())


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta(plano="essential"):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"reg.{uid[:8]}@example.com", "name": "Atleta", "role": "ATHLETE",
        "status": "ACTIVE", "created_at": _agora().isoformat(), "signup_source": "public",
        "archived_at": None, "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _dono():
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"dono.{uid[:8]}@example.com", "name": "Dono",
        "role": "SUPER_ADMIN", "status": "ACTIVE", "created_at": _agora().isoformat()})
    return uid, {"Authorization": f"Bearer {create_token(uid, 'SUPER_ADMIN')}"}


async def _limpar(*ids):
    for uid in ids:
        for nome in ("users", "subscriptions", "profiles", "conselho_semanal"):
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"profile_id": uid}]})


async def _semanas(uid):
    return await DB.conselho_semanal.find({"profile_id": uid}, {"_id": 0}).to_list(None)


async def _garantir_indice():
    """O evento de startup do FastAPI nao dispara sob transporte ASGI, e e ele que cria o
    indice unico (profile_id, semana). Sem o indice, a corrida do bootstrap grava a mesma
    semana varias vezes — que e exatamente o que este arquivo mede."""
    await DB.conselho_semanal.create_index([("profile_id", 1), ("semana", 1)], unique=True)


@pytest.fixture(autouse=True, scope="module")
def indice():
    LOOP.run_until_complete(_garantir_indice())


# ── A gravacao nao depende do plano ─────────────────────────────────────────────────

@asincrono
async def test_o_essencial_tambem_tem_a_semana_gravada():
    """Ele nunca vera o Conselho. A semana dele vale igual para medir o metodo."""
    uid, h = await _atleta(plano="essential")
    try:
        async with await _cliente() as c:
            assert (await c.get("/api/conselho", headers=h)).status_code == 402
            await c.get("/api/bootstrap", headers=h)
        # O bootstrap dispara a gravacao em segundo plano; ela termina no mesmo laco.
        for _ in range(50):
            if await _semanas(uid):
                break
            await __import__("asyncio").sleep(0.05)
        semanas = await _semanas(uid)
        assert len(semanas) == 1
        assert semanas[0]["semana"] == _semana_atual()
        assert semanas[0]["decisao"]["alavanca"]
        assert semanas[0]["estado"]
    finally:
        await _limpar(uid)


@asincrono
async def test_quem_nao_ve_fica_marcado_como_nao_visivel():
    """Sem essa marca, a analise futura mistura quem nunca viu com quem viu e ignorou."""
    essencial, _ = await _atleta(plano="essential")
    elite, he = await _atleta(plano="elite")
    try:
        await registrar_semana(DB, essencial, visivel=False)
        async with await _cliente() as c:
            await c.get("/api/conselho", headers=he)

        assert (await _semanas(essencial))[0]["visivel"] is False
        assert (await _semanas(elite))[0]["visivel"] is True
    finally:
        await _limpar(essencial, elite)


@asincrono
async def test_virar_elite_no_meio_da_semana_passa_a_ver_o_que_ja_estava_gravado():
    uid, h = await _atleta(plano="pro")
    try:
        await registrar_semana(DB, uid, visivel=False)
        gravado = (await _semanas(uid))[0]
        assert gravado["visivel"] is False

        await DB.subscriptions.update_one({"user_id": uid}, {"$set": {"plan_code": "elite"}})
        async with await _cliente() as c:
            r = await c.get("/api/conselho", headers=h)
        assert r.status_code == 200
        # A MESMA semana, e nao uma nova: a decisao da semana nao muda porque o plano mudou.
        semanas = await _semanas(uid)
        assert len(semanas) == 1
        assert semanas[0]["visivel"] is True
        assert semanas[0]["criado_em"] == gravado["criado_em"]
    finally:
        await _limpar(uid)


# ── Uma por semana, e so uma ────────────────────────────────────────────────────────

@asincrono
async def test_abrir_o_aplicativo_dez_vezes_grava_uma_semana_so():
    """O bootstrap e a primeira requisicao de toda sessao. Sem idempotencia, cada abertura
    criaria uma linha e o historico viraria lixo."""
    uid, h = await _atleta(plano="pro")
    try:
        async with await _cliente() as c:
            for _ in range(10):
                await c.get("/api/bootstrap", headers=h)
        for _ in range(50):
            if await _semanas(uid):
                break
            await __import__("asyncio").sleep(0.05)
        assert len(await _semanas(uid)) == 1
    finally:
        await _limpar(uid)


@asincrono
async def test_registrar_duas_vezes_devolve_o_mesmo_documento():
    uid, _ = await _atleta()
    try:
        primeiro = await registrar_semana(DB, uid, visivel=False)
        segundo = await registrar_semana(DB, uid, visivel=True)
        assert primeiro["id"] == segundo["id"]
        assert len(await _semanas(uid)) == 1
    finally:
        await _limpar(uid)


# ── A abertura do aplicativo nao pode quebrar por causa disto ───────────────────────

@asincrono
async def test_o_bootstrap_responde_mesmo_se_a_gravacao_falhar(monkeypatch=None):
    """Registrar o que aconteceu vale menos do que o aplicativo abrir."""
    import conselho_routes
    uid, h = await _atleta()
    original = conselho_routes.registrar_semana

    async def explode(*a, **k):
        raise RuntimeError("banco caiu")

    conselho_routes.registrar_semana = explode
    try:
        async with await _cliente() as c:
            r = await c.get("/api/bootstrap", headers=h)
        assert r.status_code == 200
        assert r.json()["program"]
    finally:
        conselho_routes.registrar_semana = original
        await _limpar(uid)


# ── A varredura, para quem nao abriu o aplicativo ───────────────────────────────────

@asincrono
async def test_a_varredura_grava_quem_nao_apareceu():
    """Quem some por duas semanas deixa dois buracos na serie — e sumir e justamente o
    dado mais interessante."""
    dono_id, hd = await _dono()
    sumido, _ = await _atleta()
    try:
        assert await _semanas(sumido) == []
        async with await _cliente() as c:
            r = await c.post("/api/conselho/varrer", headers=hd)
        assert r.status_code == 200
        assert r.json()["gravadas"] >= 1
        assert len(await _semanas(sumido)) == 1
    finally:
        await _limpar(dono_id, sumido)


@asincrono
async def test_a_varredura_nao_duplica_quem_ja_tinha():
    dono_id, hd = await _dono()
    uid, _ = await _atleta()
    try:
        await registrar_semana(DB, uid, visivel=False)
        async with await _cliente() as c:
            r = await c.post("/api/conselho/varrer", headers=hd)
        assert r.json()["ja_tinham"] >= 1
        assert len(await _semanas(uid)) == 1
    finally:
        await _limpar(dono_id, uid)


@asincrono
async def test_atleta_nao_varre_a_base():
    uid, h = await _atleta(plano="elite")
    try:
        async with await _cliente() as c:
            r = await c.post("/api/conselho/varrer", headers=h)
        assert r.status_code == 403
    finally:
        await _limpar(uid)


# ── O que cada semana precisa ter para servir de experimento ────────────────────────

@asincrono
async def test_a_semana_gravada_tem_tudo_que_um_experimento_precisa():
    uid, _ = await _atleta()
    try:
        doc = await registrar_semana(DB, uid, visivel=False)
        for campo in ("estado", "decisao", "previsao", "aplicada", "conferido",
                      "visivel", "semana", "criado_em", "profile_id"):
            assert campo in doc, f"falta {campo}"
        # A condicao ANTES, que e o que permite segmentar depois.
        for leitura in ("comida", "peso", "volume", "falhas", "prontidao", "objetivo"):
            assert leitura in doc["estado"], f"falta estado.{leitura}"
    finally:
        await _limpar(uid)
