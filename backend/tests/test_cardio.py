# -*- coding: utf-8 -*-
"""Cardio: registrar o que foi feito na esteira, sem virar credito de comida.

O defeito que esta suite existe para nunca deixar voltar
--------------------------------------------------------
O cardio era montado em UM lugar so: `runtime_server.py`, que e o que o Dockerfile sobe.
`server.py`, que monta todos os outros routers do FORGE, nao montava esse.

Em producao a rota respondia. O estrago foi outro, e mais silencioso: `server:app` — a
aplicacao que ESTA SUITE INTEIRA importa, e toda suite do repositorio junto com ela — nao
tinha rota de cardio nenhuma. Uma feature inteira, com tela, modelo e duas rotas, sem um
unico teste possivel.

A prova de que isso importa: em 19/09/2026 eu apaguei `cardio.py` e `cardio_routes.py` e
escrevi outros dois por cima, achando que os arquivos eram meus. Nenhum teste ficou
vermelho, porque nao havia teste que pudesse ficar. O trabalho foi recuperado do git.

Por isso o primeiro teste daqui e chato de proposito: ele bate na rota pela aplicacao que
a suite importa.

A regra que a suite prende
--------------------------
`kcal_reported` nunca vira permissao para comer mais. O alvo calorico ja nasce de um TDEE
com fator de atividade, entao somar o numero do painel conta o mesmo gasto duas vezes — e
com um numero que a maquina ja inflou, porque ela reporta gasto BRUTO por formula
generica. O cardio entra como alavanca, e isso esta medido em `test_conselho.py`.
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

import cardio as motor  # noqa: E402
import server  # noqa: E402
from auth import create_token  # noqa: E402
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


def _hoje():
    return CalendarDate.today().isoformat()


def _dias_atras(n):
    return (CalendarDate.today() - timedelta(days=n)).isoformat()


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta(plano="essential"):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"cardio.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": _agora().isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(*ids):
    for uid in ids:
        for nome in ("users", "subscriptions", "profiles", "cardio_logs"):
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"profile_id": uid}]})


def _ficha(**extra):
    corpo = {"client_token": f"cardio-{uuid.uuid4().hex[:12]}", "kind": "moderate",
             "modality": "Esteira", "minutes": 30, "rpe": 5, "completed": True}
    corpo.update(extra)
    return corpo


# ── A rota existe na aplicacao ──────────────────────────────────────────────────────

@asincrono
async def test_a_aplicacao_de_PRODUCAO_continua_servindo_cardio():
    """O Dockerfile sobe `runtime_server:app`, e nao `server:app`.

    O cardio era montado la, e so la. Ao mover a montagem para `server.py` eu podia ter
    tirado a rota do ar sem nenhuma suite perceber, porque nenhuma delas importa o modulo
    que producao realmente executa. Este teste importa.
    """
    import runtime_server
    uid, h = await _atleta()
    try:
        async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=runtime_server.app),
                base_url="http://forge.test") as c:
            r = await c.post("/api/cardio", headers=h, json=_ficha())
        assert r.status_code == 200, f"producao perdeu a rota de cardio: {r.status_code}"
    finally:
        await _limpar(uid)


def test_o_cardio_e_montado_uma_vez_so():
    """Montar nos dois lugares registra a mesma rota duas vezes.

    Funciona — a primeira correspondencia vence — e por isso ninguem percebe. Mas e sinal
    de que a origem da montagem voltou a ser ambigua, que foi a causa de tudo isto.
    """
    import io as _io
    from pathlib import Path as _Path
    runtime = _io.open(_Path(__file__).parent.parent / "runtime_server.py",
                       encoding="utf-8").read()
    assert "include_router(cardio_router)" not in runtime, (
        "cardio montado em runtime_server E em server: rota duplicada")


@asincrono
async def test_a_rota_de_cardio_esta_montada_na_aplicacao_que_a_suite_importa():
    """Regressao do defeito real: o cardio so era montado em `runtime_server.py`.

    Em producao respondia. Mas `server:app`, que e o que a suite importa, nao tinha rota
    de cardio nenhuma — e por isso a feature ficou sem cobertura de teste desde que
    nasceu.
    """
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h, json=_ficha())
        assert r.status_code != 404, "o router de cardio voltou a ficar fora da aplicacao"
        assert r.status_code == 200, r.text
    finally:
        await _limpar(uid)


@asincrono
async def test_o_corpo_que_o_finalizador_de_treino_manda_continua_valendo():
    """`CardioFinisher.jsx` manda exatamente estes campos. Se o contrato mudar, o card que
    aparece depois do treino quebra, e ele nao tem teste de ponta a ponta para avisar."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h, json={
                "client_token": "cardio-1758200000000-a1b2c3d4",
                "kind": "recovery", "modality": "Bike", "minutes": 10, "rpe": 3,
                "session_label": "Legs", "completed": True})
            assert r.status_code == 200, r.text
            recentes = (await c.get("/api/cardio/recent", headers=h)).json()
        assert recentes["items"][0]["modality"] == "Bike"
        assert recentes["items"][0]["kind"] == "recovery"
    finally:
        await _limpar(uid)


# ── O que a aba acrescentou ─────────────────────────────────────────────────────────

@asincrono
async def test_registrar_o_que_o_painel_mostrou():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h,
                             json=_ficha(minutes=42, kcal_reported=388))
            assert r.status_code == 200, r.text
            assert r.json()["kcal_reported"] == 388
            lista = (await c.get("/api/cardio", headers=h)).json()
        assert lista["leitura"]["minutos"] == 42
        assert lista["leitura"]["kcal_reported"] == 388
    finally:
        await _limpar(uid)


@asincrono
async def test_quem_corre_na_rua_registra_sem_caloria_e_sem_rpe():
    """Nao ha painel para ler. Exigir o numero transformaria "registrei minha corrida" em
    "inventei uma caloria"."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h, json={
                "client_token": f"cardio-{uuid.uuid4().hex[:12]}",
                "modality": "Corrida", "minutes": 38})
            assert r.status_code == 200, r.text
            assert r.json()["kcal_reported"] is None
            assert r.json()["rpe"] is None
            lista = (await c.get("/api/cardio", headers=h)).json()
        assert lista["leitura"]["kcal_reported"] == 0
    finally:
        await _limpar(uid)


@asincrono
async def test_o_cardio_cai_no_dia_em_que_aconteceu_e_nao_no_dia_em_que_foi_digitado():
    """Quem registra a semana toda no domingo veria a media semanal mentir."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/cardio", headers=h,
                         json=_ficha(minutes=30, date=_dias_atras(3)))
            lista = (await c.get("/api/cardio", headers=h)).json()
        assert lista["sessoes"][0]["date"] == _dias_atras(3)
    finally:
        await _limpar(uid)


@asincrono
async def test_uma_pedalada_longa_nao_e_dedo_errado():
    """O teto antigo era 120 minutos, que era o teto do finalizador de treino. A aba
    registra a sessao inteira."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h, json=_ficha(minutes=150))
        assert r.status_code == 200, r.text
    finally:
        await _limpar(uid)


@pytest.mark.parametrize("campo,valor", [
    ("minutes", 0), ("minutes", 600), ("kcal_reported", -5),
    ("kcal_reported", 99999), ("rpe", 42),
])
@asincrono
async def test_numero_absurdo_e_recusado(campo, valor):
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/cardio", headers=h, json=_ficha(**{campo: valor}))
        assert r.status_code == 422
    finally:
        await _limpar(uid)


@asincrono
async def test_gravar_duas_vezes_com_o_mesmo_token_deixa_uma_sessao():
    """O `client_token` e a idempotencia: uma tentativa repetida nao pode virar duas
    sessoes de cardio no historico."""
    uid, h = await _atleta()
    try:
        corpo = _ficha()
        async with await _cliente() as c:
            for _ in range(5):
                await c.post("/api/cardio", headers=h, json=corpo)
            lista = (await c.get("/api/cardio", headers=h)).json()
        assert len(lista["sessoes"]) == 1
    finally:
        await _limpar(uid)


@asincrono
async def test_o_registro_errado_pode_ser_apagado():
    uid, h = await _atleta()
    try:
        corpo = _ficha()
        async with await _cliente() as c:
            await c.post("/api/cardio", headers=h, json=corpo)
            r = await c.delete(f"/api/cardio/{corpo['client_token']}", headers=h)
            assert r.status_code == 200
            lista = (await c.get("/api/cardio", headers=h)).json()
        assert lista["sessoes"] == []
    finally:
        await _limpar(uid)


@asincrono
async def test_um_atleta_nao_ve_nem_apaga_o_cardio_do_outro():
    meu, hm = await _atleta()
    outro, ho = await _atleta()
    try:
        corpo = _ficha()
        async with await _cliente() as c:
            await c.post("/api/cardio", headers=ho, json=corpo)
            assert (await c.delete(f"/api/cardio/{corpo['client_token']}",
                                   headers=hm)).status_code == 404
            minha = (await c.get("/api/cardio", headers=hm)).json()
            dele = (await c.get("/api/cardio", headers=ho)).json()
        assert minha["sessoes"] == []
        assert len(dele["sessoes"]) == 1
    finally:
        await _limpar(meu, outro)


@asincrono
async def test_a_tela_recebe_as_modalidades_do_servidor():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/cardio/modalities", headers=h)
        assert r.status_code == 200
        assert r.json()["modalities"] == motor.MODALITIES
        # As quatro do finalizador de treino continuam na lista: a aba e o card depois do
        # treino precisam falar a mesma lingua.
        for antiga in ("Caminhada", "Bike", "Elíptico", "Escada"):
            assert antiga in r.json()["modalities"]
    finally:
        await _limpar(uid)


# ── A leitura ───────────────────────────────────────────────────────────────────────

def test_a_media_semanal_nao_e_o_total_da_janela():
    """Quatro semanas de 60 minutos sao 60 por semana, e nao 240."""
    rows = [{"minutes": 60, "modality": "Bike"} for _ in range(4)]
    leitura = motor.cardio_reading(rows, 28)
    assert leitura["minutos"] == 240
    assert leitura["minutos_por_semana"] == 60


def test_a_semana_corrente_e_a_media_da_janela_sao_numeros_diferentes():
    """Medido no navegador: com 42 minutos registrados hoje, a tela mostrava "10 min por
    semana" em letra grande, porque 42 divididos por quatro semanas dao 10. Parecia que o
    aplicativo tinha perdido a sessao que a pessoa acabou de salvar.

    A media continua existindo, porque e ela que o Conselho usa: uma semana solta nao e
    habito, e o motor decide sobre habito. O que mudou foi qual dos dois a tela destaca.
    """
    hoje = CalendarDate(2026, 9, 19)                        # uma sexta-feira
    leitura = motor.cardio_reading(
        [{"minutes": 42, "date": "2026-09-19", "modality": "Esteira"}], 28, hoje)
    assert leitura["minutos_na_semana"] == 42
    assert leitura["minutos_por_semana"] == 10


def test_o_cardio_da_semana_passada_nao_conta_na_semana_corrente():
    hoje = CalendarDate(2026, 9, 19)
    leitura = motor.cardio_reading([
        {"minutes": 40, "date": "2026-09-19", "modality": "Esteira"},   # esta semana
        {"minutes": 60, "date": "2026-09-10", "modality": "Bike"},      # semana passada
    ], 28, hoje)
    assert leitura["minutos_na_semana"] == 40
    assert leitura["minutos"] == 100


def test_data_estragada_nao_derruba_a_leitura():
    """Linha gravada antes do campo `date` existir, ou com lixo: a semana corrente ignora,
    e o total continua somando o que da para somar."""
    leitura = motor.cardio_reading([
        {"minutes": 30, "date": "", "modality": "Bike"},
        {"minutes": 20, "date": "ontem", "modality": "Bike"},
    ], 28, CalendarDate(2026, 9, 19))
    assert leitura["minutos_na_semana"] == 0
    assert leitura["minutos"] == 50


def test_uma_caminhada_solta_nao_faz_de_alguem_quem_faz_cardio():
    assert motor.cardio_reading([{"minutes": 15}], 28)["faz_cardio"] is False


def test_o_passo_respeita_o_teto_de_desgaste():
    assert motor.cardio_step(motor.TETO_SEMANAL, +1) is None
    assert motor.cardio_step(motor.TETO_SEMANAL - 10, +1)["para"] == motor.TETO_SEMANAL


def test_nao_da_para_tirar_cardio_de_quem_nao_faz():
    assert motor.cardio_step(0, -1) is None
    assert motor.cardio_step(120, -1)["delta"] == -motor.PASSO_MINUTOS


def test_a_leitura_carrega_a_procedencia_do_numero():
    """`kcal_reported` e nao `kcal`: quem ler este dicionario daqui a um ano precisa saber
    que aquele numero veio do painel da maquina."""
    leitura = motor.cardio_reading([{"minutes": 30, "kcal_reported": 400}], 28)
    assert "kcal_reported" in leitura
    assert "kcal" not in leitura


# ── A ponte com o Conselho ──────────────────────────────────────────────────────────

@asincrono
async def test_o_conselho_le_o_cardio_pelo_mesmo_caminho_da_tela():
    """Dois totais diferentes para o mesmo cardio destruiriam a confianca nos dois."""
    from cardio_routes import ler_cardio
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/cardio", headers=h, json=_ficha(minutes=40))
            await c.post("/api/cardio", headers=h, json=_ficha(minutes=25))
            da_tela = (await c.get("/api/cardio?janela_dias=28", headers=h)).json()["leitura"]
        do_conselho = await ler_cardio(DB, uid, 28)
        assert da_tela["minutos"] == do_conselho["minutos"] == 65
        assert da_tela["minutos_por_semana"] == do_conselho["minutos_por_semana"]
    finally:
        await _limpar(uid)
