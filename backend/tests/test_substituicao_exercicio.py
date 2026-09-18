# -*- coding: utf-8 -*-
"""Substituir exercicio: trocar de novo, desfazer, e nao oferecer o que nao serve.

Existe uma suite anterior, `test_exercise_substitution.py`, que documenta a primeira
versao deste defeito. Ela fala com um servidor HTTP de verdade e por isso NAO esta nos
`paths:` do CI — o que explica como os defeitos abaixo chegaram a producao sem nenhum
teste reclamar. Esta roda em processo e entra no CI.

Os tres defeitos, medidos antes de mexer:

1. TROCAR DUAS VEZES O MESMO LUGAR nao fazia nada. `_apply_exercise_substitutions`
   percorre cada exercicio do programa UMA vez: `dip` virava `incline-smith` e parava
   ali. A segunda troca gravava `incline-smith -> db-incline-press`, entrada que nunca
   disparava porque nenhum exercicio GERADO se chama `incline-smith`. A rota devolvia
   200, a troca ficava salva, e o programa voltava igual. Do lado do atleta: "nao salva".

2. ALTERNATIVA INVENTADA. Sem par de mesmo musculo e mesmo padrao, o motor oferecia o
   primeiro exercicio do catalogo. Medido: 12 dos 134 caiam nisso, e os 12 ofereciam
   "Supino inclinado Smith" — inclusive "Cadeira abdutora". A prescricao (series, reps,
   descanso, RIR) e mantida intacta na troca JUSTAMENTE porque o substituto tem o mesmo
   alvo; sem isso, a troca entrega treino errado com a conta do treino certo.

3. DUPLICATA NA SESSAO. Trocar "Barra fixa pronada" por "Barra fixa neutra" num dia que
   ja tinha as duas deixava a sessao com o mesmo exercicio duas vezes.
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
from engine import EXERCISE_INDEX, FRONTEND_EXERCISE_LIST  # noqa: E402
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


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta():
    """Atleta com programa gerado, pronto para trocar exercicio."""
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"sub.{uid[:8]}@example.com", "name": "Atleta", "role": "ATHLETE",
        "status": "ACTIVE", "created_at": _agora().isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": "elite", "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    cabecalho = {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}
    async with await _cliente() as c:
        await c.post("/api/assessment", json={
            "profile_id": uid, "name": "Atleta", "age": 31, "sex": "male",
            "height_cm": 178, "weight_kg": 92, "experience": "intermediate",
            "goal": "fat_loss", "training_days": 4, "session_minutes": 60,
            "equipment": ["full_gym"], "years_training": 4, "consistent_years": 2},
            headers=cabecalho)
    return uid, cabecalho


async def _limpar(uid):
    for nome in ("users", "subscriptions", "profiles", "set_logs"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid}, {"profile_id": uid}]})


async def _sessao_do_dia(c, cabecalho, dia=0):
    r = await c.get("/api/bootstrap", headers=cabecalho)
    return [e["exercise_id"] for e in r.json()["program"]["sessions"][dia]["exercises"]]


# ── 1. Trocar duas vezes o mesmo lugar ──────────────────────────────────────────────

@asincrono
async def test_trocar_duas_vezes_o_mesmo_lugar_vale_a_ultima_escolha():
    """O defeito relatado: a segunda troca devolvia 200 e nao mudava nada."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            antes = await _sessao_do_dia(c, h)
            original = antes[0]

            alts = (await c.get(f"/api/exercises/{original}/alternatives", headers=h)).json()
            if len(alts["alternatives"]) < 2:
                pytest.skip("este programa abriu com exercicio de poucas alternativas")
            primeira, segunda = alts["alternatives"][0]["id"], alts["alternatives"][1]["id"]

            r1 = await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": original, "new_exercise_id": primeira})
            assert r1.status_code == 200
            assert (await _sessao_do_dia(c, h))[0] == primeira

            # A segunda troca parte do que ESTA na tela agora.
            r2 = await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": primeira, "new_exercise_id": segunda})
            assert r2.status_code == 200, r2.text
            depois = await _sessao_do_dia(c, h)

        assert depois[0] == segunda, "a segunda troca nao chegou ao programa"
        # O mapa continua PLANO: a origem e sempre o exercicio gerado, nunca um elo novo.
        perfil = await DB.profiles.find_one({"id": uid})
        assert perfil["exercise_substitutions"] == {original: segunda}
    finally:
        await _limpar(uid)


@asincrono
async def test_voltar_ao_exercicio_original_desfaz_a_troca():
    """Desfazer nao pode virar um mapeamento de um exercicio para ele mesmo."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            original = (await _sessao_do_dia(c, h))[0]
            alts = (await c.get(f"/api/exercises/{original}/alternatives", headers=h)).json()
            if not alts["alternatives"]:
                pytest.skip("exercicio sem alternativa")
            novo = alts["alternatives"][0]["id"]

            await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": original, "new_exercise_id": novo})
            r = await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": novo, "new_exercise_id": original})
            assert r.status_code == 200
            assert (await _sessao_do_dia(c, h))[0] == original

        perfil = await DB.profiles.find_one({"id": uid})
        assert perfil["exercise_substitutions"] == {}
    finally:
        await _limpar(uid)


@asincrono
async def test_a_troca_preserva_series_reps_descanso_e_rir():
    """A prescricao sobrevive porque o substituto tem o mesmo alvo e o mesmo padrao."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.get("/api/bootstrap", headers=h)
            item = r.json()["program"]["sessions"][0]["exercises"][0]
            original = item["exercise_id"]
            alts = (await c.get(f"/api/exercises/{original}/alternatives", headers=h)).json()
            if not alts["alternatives"]:
                pytest.skip("exercicio sem alternativa")
            await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": original, "new_exercise_id": alts["alternatives"][0]["id"]})
            depois = (await c.get("/api/bootstrap", headers=h)).json()
            novo_item = depois["program"]["sessions"][0]["exercises"][0]

        for campo in ("sets", "reps", "rir", "rest", "technique", "technique_id"):
            assert novo_item[campo] == item[campo], f"{campo} mudou na troca"
    finally:
        await _limpar(uid)


# ── 2. Nada de alternativa inventada ────────────────────────────────────────────────

def test_toda_alternativa_oferecida_tem_o_mesmo_alvo_e_o_mesmo_padrao():
    """A garantia que sustenta preservar a prescricao. Sem ela, a troca entrega treino
    errado com a conta do treino certo."""
    problemas = []
    for ex in FRONTEND_EXERCISE_LIST:
        origem = EXERCISE_INDEX[ex["id"]]
        for aid in ex["alternative_ids"]:
            alvo = EXERCISE_INDEX[aid]
            if (alvo["primary_muscle"] != origem["primary_muscle"]
                    or alvo.get("movement_pattern") != origem.get("movement_pattern")):
                problemas.append(f"{ex['name']} -> {alvo['name']}")
    assert problemas == [], f"alternativas que mudam o treino: {problemas[:5]}"


def test_exercicio_sem_par_no_catalogo_nao_oferece_nada():
    """Havia um recuo que devolvia o primeiro exercicio do catalogo. Medido: 12 dos 134
    caiam nele, e todos ofereciam "Supino inclinado Smith" — inclusive a Cadeira
    abdutora. Nao oferecer e a resposta honesta."""
    sem_par = [ex for ex in FRONTEND_EXERCISE_LIST
               if not any(EXERCISE_INDEX[o["id"]]["primary_muscle"] == EXERCISE_INDEX[ex["id"]]["primary_muscle"]
                          and EXERCISE_INDEX[o["id"]].get("movement_pattern") == EXERCISE_INDEX[ex["id"]].get("movement_pattern")
                          for o in FRONTEND_EXERCISE_LIST if o["id"] != ex["id"])]
    assert sem_par, "o catalogo mudou: ninguem mais esta sem par"
    for ex in sem_par:
        assert ex["alternative_ids"] == [], f"{ex['name']} inventou alternativa"


@asincrono
async def test_a_rota_devolve_lista_vazia_para_quem_nao_tem_substituto():
    uid, h = await _atleta()
    try:
        sem_par = next(ex for ex in FRONTEND_EXERCISE_LIST if not ex["alternative_ids"])
        async with await _cliente() as c:
            r = await c.get(f"/api/exercises/{sem_par['id']}/alternatives", headers=h)
        assert r.status_code == 200
        assert r.json()["alternatives"] == []
    finally:
        await _limpar(uid)


# ── 3. Nada de exercicio repetido na sessao ─────────────────────────────────────────

@asincrono
async def test_o_que_ja_esta_na_sessao_nao_e_oferecido():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            na_sessao = await _sessao_do_dia(c, h)
            r = await c.get(f"/api/exercises/{na_sessao[0]}/alternatives", headers=h)
            oferecidos = {a["id"] for a in r.json()["alternatives"]}
        assert not (oferecidos & set(na_sessao[1:])), \
            f"ofereceu algo que ja esta na sessao: {oferecidos & set(na_sessao[1:])}"
    finally:
        await _limpar(uid)


@asincrono
async def test_forcar_a_duplicata_pela_api_e_recusado():
    """A trava vive no servidor, e nao so na listagem: quem chamar a rota direto passaria
    por cima dela."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            na_sessao = await _sessao_do_dia(c, h)
            origem = na_sessao[0]
            # Um vizinho da sessao que TAMBEM seja alternativa valida da origem.
            candidatos = [i for i in na_sessao[1:]
                          if i in EXERCISE_INDEX and i in next(
                              e["alternative_ids"] for e in FRONTEND_EXERCISE_LIST if e["id"] == origem)]
            if not candidatos:
                pytest.skip("esta sessao nao tem vizinho que seja alternativa da origem")
            r = await c.post("/api/exercises/substitute", headers=h, json={
                "original_exercise_id": origem, "new_exercise_id": candidatos[0]})
        assert r.status_code == 409
        assert r.json()["detail"]["reason"] == "duplicate_in_session"
    finally:
        await _limpar(uid)


# ── O texto que o atleta le ─────────────────────────────────────────────────────────

@asincrono
async def test_o_motivo_nao_vaza_identificador_nem_repete_a_mesma_frase():
    """A frase era igual nas tres opcoes e trazia o padrao cru: "Mantém Tríceps e o padrão
    elbow_extension". Nome de campo do banco no meio de um texto em portugues, e tres
    opcoes dizendo a mesma coisa nao ajudam ninguem a escolher."""
    uid, h = await _atleta()
    try:
        alvo = next(e for e in FRONTEND_EXERCISE_LIST if len(e["alternative_ids"]) >= 2)
        async with await _cliente() as c:
            r = await c.get(f"/api/exercises/{alvo['id']}/alternatives", headers=h)
        motivos = [a["reason"] for a in r.json()["alternatives"]]

        for m in motivos:
            assert "_" not in m, f"identificador cru no texto: {m!r}"
            assert m.endswith("."), f"frase sem ponto final: {m!r}"
        assert len(set(motivos)) == len(motivos), "as opcoes repetem a mesma frase"
    finally:
        await _limpar(uid)


@asincrono
async def test_outro_atleta_nao_altera_meu_programa():
    meu, hm = await _atleta()
    outro, ho = await _atleta()
    try:
        async with await _cliente() as c:
            minha = await _sessao_do_dia(c, hm)
            alts = (await c.get(f"/api/exercises/{minha[0]}/alternatives", headers=ho)).json()
            if not alts["alternatives"]:
                pytest.skip("exercicio sem alternativa")
            await c.post("/api/exercises/substitute", headers=ho, json={
                "original_exercise_id": minha[0],
                "new_exercise_id": alts["alternatives"][0]["id"]})
            depois = await _sessao_do_dia(c, hm)
        assert depois == minha, "a troca de outro atleta vazou para o meu programa"
    finally:
        await _limpar(meu)
        await _limpar(outro)
