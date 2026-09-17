# -*- coding: utf-8 -*-
"""Arquivar e excluir atleta no painel administrativo.

Duas operacoes que parecem a mesma e nao sao:

  ARQUIVAR some da lista, mantem o banco, volta com um clique.
  EXCLUIR apaga a pessoa e o rastro dela, de trinta colecoes, sem volta.

O teste que sustenta a segunda e `test_nao_sobra_dado_orfao_em_colecao_nenhuma`. Ele nao
confere a lista de colecoes escrita em `remocao_de_atleta.py` — isso so provaria que o
codigo faz o que o codigo diz. Ele semeia dado em TODAS as colecoes do banco, exclui, e
varre TUDO procurando o id. Colecao esquecida hoje, ou criada daqui a seis meses por
outra funcionalidade, quebra aqui sozinha.

Dado orfao nao levanta erro em lugar nenhum: ele so fica no banco, com o nome, o peso e as
fotos de alguem que pediu para ser apagado.
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
from loop_do_motor import LOOP  # noqa: E402
from remocao_de_atleta import (COLECOES_DO_ATLETA, COLECOES_POR_EMAIL,  # noqa: E402
                               COLECOES_PRESERVADAS, orfaos)

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


async def _admin():
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"dono.{uid[:8]}@example.com", "name": "Dono",
        "role": "SUPER_ADMIN", "status": "ACTIVE", "created_at": _agora().isoformat()})
    return uid, {"Authorization": f"Bearer {create_token(uid, 'SUPER_ADMIN')}"}


async def _atleta(status="ACTIVE"):
    uid = str(uuid.uuid4())
    email = f"atleta.{uid[:8]}@example.com"
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Atleta", "role": "ATHLETE",
        "status": status, "created_at": _agora().isoformat(), "signup_source": "public",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    return uid, email


async def _limpar(*ids):
    for uid in ids:
        for nome in await DB.list_collection_names():
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"profile_id": uid},
                                                {"target_user_id": uid}, {"actor_id": uid}]})


def _cobranca_ligada():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()


# ── Arquivar ────────────────────────────────────────────────────────────────────────

@asincrono
async def test_arquivar_tira_da_lista_e_mantem_no_banco():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            antes = (await c.get("/api/admin/athletes", headers=ha)).json()["athletes"]
            assert any(a["id"] == uid for a in antes)

            r = await c.post(f"/api/admin/athletes/{uid}/arquivar",
                             json={"motivo": "nunca usou"}, headers=ha)
            assert r.status_code == 200

            depois = (await c.get("/api/admin/athletes", headers=ha)).json()["athletes"]
        assert not any(a["id"] == uid for a in depois)
        assert await DB.users.find_one({"id": uid})        # continua no banco
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_o_filtro_de_arquivados_mostra_so_eles():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    arquivado, _ = await _atleta()
    ativo, _ = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{arquivado}/arquivar", json={}, headers=ha)
            lista = (await c.get("/api/admin/athletes?status=ARCHIVED", headers=ha)).json()["athletes"]
        ids = {a["id"] for a in lista}
        assert arquivado in ids
        assert ativo not in ids
    finally:
        await _limpar(admin_id, arquivado, ativo)


@asincrono
async def test_desarquivar_traz_de_volta():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/arquivar", json={}, headers=ha)
            await c.post(f"/api/admin/athletes/{uid}/desarquivar", headers=ha)
            lista = (await c.get("/api/admin/athletes", headers=ha)).json()["athletes"]
        assert any(a["id"] == uid for a in lista)
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_arquivar_nao_muda_o_status_da_conta():
    """Arquivado e marca separada: a conta nao perde se estava ativa ou suspensa."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta(status="SUSPENDED")
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/arquivar", json={}, headers=ha)
        user = await DB.users.find_one({"id": uid})
        assert user["status"] == "SUSPENDED"
        assert user["archived_at"]
    finally:
        await _limpar(admin_id, uid)


# ── Excluir: o que precisa sumir ────────────────────────────────────────────────────

async def _semear_tudo(uid: str, email: str):
    """Um documento do atleta em TODA colecao do banco que nao seja preservada.

    A primeira versao disto percorria `COLECOES_DO_ATLETA` — a mesma lista que a remocao
    usa. Era circular, e eu medi: tirando `conselho_semanal` da lista, o teste continuou
    verde, porque deixou de semear justamente a colecao esquecida. Um teste que so prova
    que o codigo faz o que o codigo diz.

    Agora a lista sai do BANCO. Colecao que nao estiver em `COLECOES_DO_ATLETA` nem em
    `COLECOES_PRESERVADAS` recebe dado, sobrevive a exclusao e quebra o teste — que e a
    unica forma de a lista nao envelhecer sozinha.

    Cada documento leva `profile_id` E `user_id`, porque as duas convencoes convivem no
    banco e a remocao so precisa acertar uma delas. Os campos unicos vao preenchidos:
    varias colecoes tem indice unico (`subscription_attempts.reference`) e dois documentos
    com `null` no mesmo campo derrubariam a semeadura por DuplicateKeyError, fazendo o
    teste falhar por um motivo que nada tem a ver com o que ele mede.
    """
    semeadas = []
    for nome in await DB.list_collection_names():
        if nome in COLECOES_PRESERVADAS or nome == "users":
            continue
        doc = {"id": str(uuid.uuid4()), "reference": str(uuid.uuid4()),
               "event_key": str(uuid.uuid4()), "token_hash": str(uuid.uuid4()),
               "profile_id": uid, "user_id": uid, "email": email, "semeado": True}
        if nome == "profiles":
            doc["id"] = uid            # aqui a chave e o proprio id
        await DB[nome].insert_one(doc)
        semeadas.append(nome)
    return semeadas


@asincrono
async def test_nao_sobra_dado_orfao_em_colecao_nenhuma():
    """O teste que sustenta a exclusao.

    Varre TODAS as colecoes do banco, e nao a lista escrita no modulo: conferir a lista
    contra ela mesma so provaria que o codigo faz o que o codigo diz.
    """
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        await _semear_tudo(uid, email)
        # A semeadura tem de ter criado dado de verdade, senao o teste passa a toa.
        assert len(await orfaos(DB, uid, email)) >= 25

        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{uid}",
                                json={"confirmar_email": email, "motivo": "limpeza"},
                                headers=ha)
        assert r.status_code == 200, r.text
        assert r.json()["total"] >= 25

        sobrou = await orfaos(DB, uid, email)
        assert sobrou == [], f"dado orfao: {sobrou}"
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_a_auditoria_sobrevive_a_exclusao():
    """Apagar o rastro junto com a pessoa destruiria a prova de que a decisao existiu."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        async with await _cliente() as c:
            await c.request("DELETE", f"/api/admin/athletes/{uid}",
                            json={"confirmar_email": email, "motivo": "conta de teste"},
                            headers=ha)
        registro = await DB.admin_audit_log.find_one(
            {"target_user_id": uid, "action": "athlete.deleted"})
        assert registro
        assert registro["meta"]["email"] == email
        assert registro["meta"]["reason"] == "conta de teste"
        assert registro["actor_id"] == admin_id
        # A contagem do que saiu: sem ela, "excluido" e afirmacao sem prova.
        assert isinstance(registro["meta"]["removidos"], dict)
    finally:
        await _limpar(admin_id, uid)


def test_as_colecoes_preservadas_sao_decisao_e_nao_esquecimento():
    for nome, motivo in COLECOES_PRESERVADAS.items():
        assert len(motivo) > 40, f"{nome} sem motivo escrito"
    assert "admin_audit_log" in COLECOES_PRESERVADAS
    assert "billing_events" in COLECOES_PRESERVADAS


# ── Excluir: as travas ──────────────────────────────────────────────────────────────

@asincrono
async def test_email_errado_nao_exclui():
    """Uma linha errada numa lista de 1.600 e um clique de distancia, e nao ha desfazer."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{uid}",
                                json={"confirmar_email": "outro@example.com"}, headers=ha)
        assert r.status_code == 400
        assert r.json()["detail"]["reason"] == "email_mismatch"
        assert await DB.users.find_one({"id": uid})
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_email_confere_ignorando_maiuscula_e_espaco():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{uid}",
                                json={"confirmar_email": f"  {email.upper()} "}, headers=ha)
        assert r.status_code == 200
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_assinatura_paga_ativa_barra_a_exclusao():
    """Apagar a conta nao cancela a cobranca: sobraria cobranca sem ninguem."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "plan_code": "pro", "status": "active",
            "provider": "mercadopago", "provider_subscription_id": "MP-9",
            "amount_cents": 6990, "currency": "BRL"}}, upsert=True)
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{uid}",
                                json={"confirmar_email": email}, headers=ha)
        assert r.status_code == 409
        assert r.json()["detail"]["reason"] == "paid_subscription"
        assert await DB.users.find_one({"id": uid})
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_cortesia_NAO_barra_a_exclusao():
    """Cortesia nao tem cobranca correndo: nao ha o que cancelar antes."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, email = await _atleta()
    try:
        await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "plan_code": "elite", "status": "active",
            "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{uid}",
                                json={"confirmar_email": email}, headers=ha)
        assert r.status_code == 200
        assert await DB.subscriptions.find_one({"user_id": uid}) is None
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_administrador_nao_e_excluido_por_esta_tela():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    outro_id, _ = await _admin()
    try:
        alvo = await DB.users.find_one({"id": outro_id})
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{outro_id}",
                                json={"confirmar_email": alvo["email"]}, headers=ha)
        assert r.status_code == 403
        assert r.json()["detail"]["reason"] == "not_an_athlete"
        assert await DB.users.find_one({"id": outro_id})
    finally:
        await _limpar(admin_id, outro_id)


@asincrono
async def test_um_atleta_nao_exclui_ninguem():
    _cobranca_ligada()
    vitima_id, vitima_email = await _atleta()
    ladrao_id, _ = await _atleta()
    token = {"Authorization": f"Bearer {create_token(ladrao_id, 'ATHLETE')}"}
    try:
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{vitima_id}",
                                json={"confirmar_email": vitima_email}, headers=token)
        assert r.status_code == 403
        assert await DB.users.find_one({"id": vitima_id})
    finally:
        await _limpar(vitima_id, ladrao_id)


@asincrono
async def test_atleta_inexistente_devolve_404():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    try:
        async with await _cliente() as c:
            r = await c.request("DELETE", "/api/admin/athletes/nao-existe",
                                json={"confirmar_email": "x@y.com"}, headers=ha)
        assert r.status_code == 404
    finally:
        await _limpar(admin_id)


@asincrono
async def test_um_atleta_nao_arquiva_ninguem():
    _cobranca_ligada()
    uid, _ = await _atleta()
    token = {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}
    try:
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/arquivar", json={}, headers=token)
        assert r.status_code == 403
    finally:
        await _limpar(uid)


@asincrono
async def test_excluir_nao_leva_junto_o_dado_de_outro_atleta():
    """A varredura por id e ampla; um filtro frouxo levaria o vizinho."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    alvo, email_alvo = await _atleta()
    vizinho, email_vizinho = await _atleta()
    try:
        await _semear_tudo(alvo, email_alvo)
        await _semear_tudo(vizinho, email_vizinho)
        async with await _cliente() as c:
            r = await c.request("DELETE", f"/api/admin/athletes/{alvo}",
                                json={"confirmar_email": email_alvo}, headers=ha)
        assert r.status_code == 200
        assert await orfaos(DB, alvo, email_alvo) == []
        assert len(await orfaos(DB, vizinho, email_vizinho)) >= 25   # intacto
    finally:
        await _limpar(admin_id, alvo, vizinho)
