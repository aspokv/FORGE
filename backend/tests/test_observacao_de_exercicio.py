# -*- coding: utf-8 -*-
"""A observacao que o atleta escreve embaixo do exercicio.

Por que isto nao e `SetLog.note`
--------------------------------
O campo `note` existe em `SetLog` desde sempre e nunca foi usado: o frontend nunca mandou
esse campo em nenhuma chamada de `/sets`. Alem de morto, ele e da SERIE, e a observacao
que a pessoa quer escrever e do EXERCICIO naquele dia: "a maquina de triceps estava
ocupada, usei a polia alta" vale para as quatro series, nao para a terceira.

O que faz alguem escrever a segunda observacao
----------------------------------------------
A primeira qualquer um escreve. A segunda so aparece se a primeira voltar. Por isso
`GET /exercise-notes` devolve `anterior` junto de `hoje`: na proxima vez que o exercicio
cair na sessao, a tela mostra o que foi anotado da ultima vez. Sem isso, a observacao e um
diario, e diario a pessoa abandona na segunda semana.
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


async def _atleta():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"nota.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": _agora().isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": "essential", "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(*ids):
    for uid in ids:
        for nome in ("users", "subscriptions", "profiles", "exercise_notes"):
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"profile_id": uid}]})


async def _linhas(uid, exercicio=None):
    filtro = {"profile_id": uid}
    if exercicio:
        filtro["exercise_id"] = exercicio
    return await DB.exercise_notes.find(filtro, {"_id": 0}).to_list(None)


async def _garantir_indice():
    """O startup do FastAPI nao dispara sob transporte ASGI, e e ele que cria o indice
    unico (perfil, exercicio, dia). Sem o indice, salvar enquanto se digita criaria uma
    linha por toque — que e exatamente o que este arquivo mede."""
    await DB.exercise_notes.create_index(
        [("profile_id", 1), ("exercise_id", 1), ("date", 1)], unique=True)


@pytest.fixture(autouse=True, scope="module")
def indice():
    LOOP.run_until_complete(_garantir_indice())


# ── Escrever ────────────────────────────────────────────────────────────────────────

@asincrono
async def test_escrever_uma_observacao_guarda_o_texto():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "triceps-pushdown", "date": _hoje(), "session_day": 1,
                "texto": "A máquina estava ocupada, usei a polia alta."})
            assert r.status_code == 200, r.text
            assert r.json()["texto"] == "A máquina estava ocupada, usei a polia alta."
        linhas = await _linhas(uid)
        assert len(linhas) == 1
        assert linhas[0]["session_day"] == 1
    finally:
        await _limpar(uid)


@asincrono
async def test_salvar_dez_vezes_no_mesmo_dia_deixa_uma_linha_so():
    """A tela salva enquanto a pessoa digita. Sem idempotencia, uma observacao de vinte
    caracteres viraria vinte linhas."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            for i in range(10):
                await c.post("/api/exercise-note", headers=h, json={
                    "exercise_id": "bb-bench-press", "date": _hoje(),
                    "texto": "Banco" + "." * i})
        linhas = await _linhas(uid)
        assert len(linhas) == 1
        assert linhas[0]["texto"] == "Banco" + "." * 9      # a ultima vence
    finally:
        await _limpar(uid)


@asincrono
async def test_apagar_o_texto_apaga_a_observacao():
    """Guardar linha vazia encheria o historico de nada e faria "ultima observacao"
    devolver um branco."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "squat", "date": _hoje(), "texto": "Barra 20 kg"})
            r = await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "squat", "date": _hoje(), "texto": "   "})
            assert r.status_code == 200
        assert await _linhas(uid) == []
    finally:
        await _limpar(uid)


@asincrono
async def test_data_invalida_e_recusada():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "squat", "date": "ontem", "texto": "x"})
        assert r.status_code == 422
    finally:
        await _limpar(uid)


@asincrono
async def test_texto_gigante_e_recusado():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "squat", "date": _hoje(), "texto": "a" * 5000})
        assert r.status_code == 422
    finally:
        await _limpar(uid)


# ── Ler de volta, que e o que faz alguem escrever a proxima ─────────────────────────

@asincrono
async def test_a_observacao_da_ultima_vez_volta_na_proxima_sessao():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "triceps-pushdown", "date": _dias_atras(7),
                "texto": "Usei a polia do fundo, a corda da frente está rasgada."})
            r = await c.get("/api/exercise-notes?ids=triceps-pushdown", headers=h)
        assert r.status_code == 200
        corpo = r.json()
        assert corpo["hoje"] == {}
        assert corpo["anterior"]["triceps-pushdown"]["texto"].startswith("Usei a polia")
        assert corpo["anterior"]["triceps-pushdown"]["date"] == _dias_atras(7)
    finally:
        await _limpar(uid)


@asincrono
async def test_a_anterior_e_a_mais_recente_e_nao_a_primeira():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            for dias, texto in ((21, "muito antiga"), (7, "a mais recente"), (14, "do meio")):
                await c.post("/api/exercise-note", headers=h, json={
                    "exercise_id": "row", "date": _dias_atras(dias), "texto": texto})
            corpo = (await c.get("/api/exercise-notes?ids=row", headers=h)).json()
        assert corpo["anterior"]["row"]["texto"] == "a mais recente"
    finally:
        await _limpar(uid)


@asincrono
async def test_a_de_hoje_e_a_anterior_vem_separadas():
    """Se a de hoje viesse no lugar da anterior, editar a observacao apagaria da tela o
    que a pessoa anotou da ultima vez, que e a unica parte util."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "row", "date": _dias_atras(7), "texto": "semana passada"})
            await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "row", "date": _hoje(), "texto": "hoje"})
            corpo = (await c.get("/api/exercise-notes?ids=row", headers=h)).json()
        assert corpo["hoje"]["row"] == "hoje"
        assert corpo["anterior"]["row"]["texto"] == "semana passada"
    finally:
        await _limpar(uid)


@asincrono
async def test_a_sessao_inteira_vem_em_uma_requisicao_so():
    """Uma requisicao por exercicio deixaria oito chamadas na abertura de cada treino."""
    uid, h = await _atleta()
    try:
        ids = ["squat", "leg-press", "leg-curl"]
        async with await _cliente() as c:
            for i in ids:
                await c.post("/api/exercise-note", headers=h, json={
                    "exercise_id": i, "date": _hoje(), "texto": f"nota de {i}"})
            corpo = (await c.get(f"/api/exercise-notes?ids={','.join(ids)}", headers=h)).json()
        assert sorted(corpo["hoje"]) == sorted(ids)
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_ids_nao_varre_o_banco():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/exercise-note", headers=h, json={
                "exercise_id": "squat", "date": _hoje(), "texto": "x"})
            corpo = (await c.get("/api/exercise-notes", headers=h)).json()
        assert corpo == {"hoje": {}, "anterior": {}}
    finally:
        await _limpar(uid)


@asincrono
async def test_um_atleta_nao_le_a_observacao_do_outro():
    meu, hm = await _atleta()
    outro, ho = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post("/api/exercise-note", headers=ho, json={
                "exercise_id": "squat", "date": _hoje(), "texto": "segredo do outro"})
            minha = (await c.get("/api/exercise-notes?ids=squat", headers=hm)).json()
        assert minha == {"hoje": {}, "anterior": {}}
    finally:
        await _limpar(meu, outro)
