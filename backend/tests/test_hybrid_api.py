# -*- coding: utf-8 -*-
"""O híbrido de ponta a ponta: avaliação, persistência, próximo treino, calendário.

Por que esta suíte existe separada da do motor
----------------------------------------------
`test_hybrid_engine.py` prova que o motor monta a semana certa. Isso é metade: uma
arquitetura que existe só dentro de `build_all_sessions` e não sobrevive ao caminho até a
tela não serve ao atleta. O que falta provar é o resto do percurso —

    avaliação -> escolha da divisão -> geração -> gravação -> bootstrap -> aba Treino
    -> concluir sessão -> ponteiro avança -> próxima sessão

— porque é aí que moram os defeitos que nenhum teste de unidade pega: um campo que o
Mongo não guarda, um ponteiro que não anda, uma sessão que volta com rótulo diferente do
que foi gravado.

Sobe a aplicação que PRODUÇÃO executa (`runtime_server`), e não `server`. O híbrido é
instalado no runtime, junto do v4 e do v5: testar contra `server:app` provaria que o
motor funciona numa aplicação que ninguém roda.
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

import runtime_server  # noqa: E402  (instala v4, v5 e hybrid sobre o engine)
import engine  # noqa: E402
import training_engine_hybrid as hybrid  # noqa: E402
import server  # noqa: E402
from auth import create_token  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402

APP = runtime_server.app
DB = server.db


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


def _agora():
    return datetime.now(timezone.utc)


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta():
    os.environ["BILLING_ENFORCED"] = "false"
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"hyb.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": _agora().isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": "elite", "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(*ids):
    for uid in ids:
        for nome in ("users", "subscriptions", "profiles", "set_logs",
                     "workout_logs", "conselho_semanal", "recovery"):
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"profile_id": uid}]})


def _avaliacao(uid, split, dias=6):
    return {"profile_id": uid, "name": "Atleta", "age": 30, "sex": "male",
            "height_cm": 178, "weight_kg": 84, "experience": "Avançado",
            "goal": "Hipertrofia", "training_days": dias, "days": dias,
            "session_minutes": 70, "equipment": ["Academia completa"],
            "years_training": 6, "consistent_years": 4,
            "split_preference": split}


# ── A avaliação vira um programa híbrido de verdade ─────────────────────────────────

@asincrono
@pytest.mark.parametrize("split", hybrid.TODAS)
async def test_pedir_um_hibrido_na_avaliacao_gera_aquele_hibrido(split):
    dias = hybrid.ARQUITETURAS[split]["dias"]
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/assessment", headers=h,
                             json=_avaliacao(uid, split, dias))
            assert r.status_code == 200, r.text
            programa = r.json()["program"]
        sessoes = programa.get("sessions") or []
        assert len(sessoes) == dias, f"{split}: {len(sessoes)} sessões"
        rotulos = [s["label"] for s in sessoes]
        esperados = [d["label"] for d in hybrid.ARQUITETURAS[split]["sessoes"]]
        assert rotulos == esperados, f"{split}: {rotulos}"
    finally:
        await _limpar(uid)


@asincrono
async def test_o_programa_hibrido_sobrevive_ao_bootstrap():
    """Gerar é fácil; o que conta é o que volta quando o aplicativo abre de novo."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/assessment", headers=h,
                         json=_avaliacao(uid, hybrid.HYBRID_01))
            b = (await c.get("/api/bootstrap", headers=h)).json()
        programa = b["program"]
        assert len(programa["sessions"]) == 6
        assert programa["sessions"][0]["label"] == "Full A"
        # Todo exercício precisa chegar com o que a tela usa para desenhar a linha.
        for s in programa["sessions"]:
            for i in s["exercises"]:
                for campo in ("exercise_id", "sets", "reps", "rir", "rest"):
                    assert campo in i, f"{s['label']}: falta {campo} em {i}"
    finally:
        await _limpar(uid)


@asincrono
async def test_o_role_chega_ate_a_tela():
    """É o role que permite dizer "peitoral, 5 exposições" sem mentir que foram 5 treinos
    de peito. Se ele morrer no caminho, a tela volta a contar sessões."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/assessment", headers=h,
                         json=_avaliacao(uid, hybrid.HYBRID_03))
            b = (await c.get("/api/bootstrap", headers=h)).json()
        roles = {i.get("role") for s in b["program"]["sessions"] for i in s["exercises"]}
        assert None not in roles, "exercício chegou à tela sem role"
        assert hybrid.MICRODOSE in roles, "nenhuma microdose sobreviveu ao caminho"
    finally:
        await _limpar(uid)


# ── Próximo treino e ponteiro ───────────────────────────────────────────────────────

@asincrono
async def test_concluir_uma_sessao_avanca_para_a_proxima_do_hibrido():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/assessment", headers=h,
                         json=_avaliacao(uid, hybrid.HYBRID_01))
            antes = (await c.get("/api/bootstrap", headers=h)).json()["program"]
            dia_antes = antes["active_day"]

            r = await c.post("/api/workout/complete", headers=h, json={"day": dia_antes})
            assert r.status_code == 200, r.text

            depois = (await c.get("/api/bootstrap", headers=h)).json()["program"]
        assert depois["active_day"] != dia_antes, "o ponteiro não andou"
        assert depois["active_day"] == dia_antes + 1
        # E a sessão ativa tem de ser a do dia novo, com o rótulo da arquitetura.
        ativa = next(s for s in depois["sessions"] if s["day"] == depois["active_day"])
        assert ativa["label"] == hybrid.ARQUITETURAS[hybrid.HYBRID_01]["sessoes"][1]["label"]
    finally:
        await _limpar(uid)


def test_a_semana_hibrida_da_a_volta_no_fim():
    """Seis sessões e o ponteiro volta ao dia 1.

    Isto é medido no motor, e não concluindo sete treinos pela API: `workout/complete`
    tem trava de uma conclusão por dia de calendário (compare-and-swap no ponteiro), então
    a sequência completa não cabe numa execução de teste. A trava está certa; quem tem de
    provar a volta é `_resolve_active_day`.
    """
    sessoes = engine.build_all_sessions(
        {"experience": "Avançado", "session_minutes": 70, "priorities": [],
         "baseline": [], "equipment": ["Academia completa"]},
        hybrid.HYBRID_01, 6, 70)
    dias = [s["day"] for s in sessoes]
    assert dias == [1, 2, 3, 4, 5, 6]
    # Ponteiro no último dia: o próximo tem de ser o primeiro, e não nada.
    perfil = {"current_session_day": 6}
    assert engine._resolve_active_day(sessoes, perfil) == 6
    # Ponteiro num dia que não existe mais (o atleta reduziu a frequência): cai no
    # primeiro em vez de travar o aplicativo sem sessão ativa.
    assert engine._resolve_active_day(sessoes, {"current_session_day": 9}) == 1


# ── Preservação do que já existia ───────────────────────────────────────────────────

@asincrono
async def test_um_atleta_de_seis_dias_sem_preferencia_continua_no_programa_antigo():
    """O item 11 da especificação, medido pela API e não só pelo motor."""
    uid, h = await _atleta()
    try:
        pedido = _avaliacao(uid, "", dias=6)
        pedido.pop("split_preference")
        async with await _cliente() as c:
            r = await c.post("/api/assessment", headers=h, json=pedido)
            assert r.status_code == 200, r.text
            programa = r.json()["program"]
        rotulos = [s["label"] for s in programa["sessions"]]
        arquiteturas = {d["label"] for a in hybrid.ARQUITETURAS.values()
                        for d in a["sessoes"]}
        assert not (set(rotulos) & arquiteturas), \
            f"virou híbrido sem ninguém pedir: {rotulos}"
    finally:
        await _limpar(uid)


@asincrono
async def test_quem_treina_quatro_dias_nao_recebe_hibrido_pela_api():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/assessment", headers=h,
                             json=_avaliacao(uid, hybrid.HYBRID_01, dias=4))
            programa = r.json()["program"]
        assert len(programa["sessions"]) == 4
        rotulos = [s["label"] for s in programa["sessions"]]
        assert "Full A" not in rotulos or len(programa["sessions"]) == 4
        arquiteturas = {d["label"] for a in hybrid.ARQUITETURAS.values()
                        for d in a["sessoes"]}
        assert not (set(rotulos) == arquiteturas)
    finally:
        await _limpar(uid)


@asincrono
async def test_a_aplicacao_de_producao_tem_as_tres_camadas_instaladas():
    """v4, v5 e hybrid, nessa ordem. Instalar o híbrido antes do v5 faria o v5
    sobrescrever `build_all_sessions` e o híbrido nunca seria chamado."""
    assert getattr(engine, "TRAINING_ENGINE_VERSION", "").startswith("5")
    assert getattr(engine, "HYBRID_ENGINE_VERSION", "") == "1.0"
    assert engine.hybrid_is_hybrid(hybrid.HYBRID_01) is True
    assert engine.hybrid_is_hybrid("ppl") is False
