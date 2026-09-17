# -*- coding: utf-8 -*-
"""O painel administrativo concede plano de verdade.

O defeito que esta suite existe para nunca mais deixar passar: o painel tinha um campo
"plano" com as opcoes FORGE_ACCESS, FORGE_PRO e LIFETIME, nomes de antes de existir
cobranca. Ele gravava a escolha em `users.plan`, um campo que `resolver_acesso` NUNCA le.

O administrador escolhia um plano, a tela respondia "atualizado", e o acesso da pessoa
continuava exatamente o mesmo. Nao havia sequer como conceder o Elite, que e onde mora o
Conselho.

Entao o teste que importa aqui nao e "a rota devolveu 200". E: depois de conceder, a
pessoa CONSEGUE ABRIR a rota paga daquele plano. Cada caso termina batendo numa rota real
com o token do atleta.
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
    await DB.users.insert_one({
        "id": uid, "email": f"atleta.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": status, "created_at": _agora().isoformat(),
        "signup_source": "public",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(*ids):
    for uid in ids:
        await DB.users.delete_many({"id": uid})
        await DB.subscriptions.delete_many({"user_id": uid})
        await DB.profiles.delete_many({"id": uid})
        await DB.admin_audit_log.delete_many({"target_user_id": uid})


def _cobranca_ligada():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()


# ── O painel oferece os planos que existem ──────────────────────────────────────────

def test_o_painel_oferece_os_planos_que_existem_de_verdade():
    from admin_routes import PLANOS_DO_PAINEL
    assert PLANOS_DO_PAINEL == ["essential", "pro", "elite"]


def test_os_nomes_antigos_continuam_sendo_LIDOS_mas_nao_sao_mais_escritos():
    """Contas criadas antes ainda tem FORGE_ACCESS gravado; a ficha delas precisa abrir."""
    from admin_routes import PLANOS_LEGADOS, VALID_PLANS
    assert "FORGE_ACCESS" in VALID_PLANS
    assert "FORGE_ACCESS" not in __import__("admin_routes").PLANOS_DO_PAINEL
    assert PLANOS_LEGADOS


def test_o_campo_de_plano_saiu_da_edicao_de_ficha():
    """Ele prometia mudar o plano e nao mudava nada. Quem concede e a rota propria."""
    from admin_routes import UpdateAthlete
    assert "plan" not in UpdateAthlete.model_fields


# ── Conceder muda o ACESSO, e nao so um campo ───────────────────────────────────────

@asincrono
async def test_conceder_elite_abre_o_conselho_para_o_atleta():
    """O teste que prova o conserto: antes, 402; depois de conceder, 200."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, ht = await _atleta()
    try:
        async with await _cliente() as c:
            antes = await c.get("/api/conselho", headers=ht)
            assert antes.status_code == 402

            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "elite", "motivo": "conta do dono"},
                             headers=ha)
            assert r.status_code == 200, r.text
            assert r.json()["acesso"]["plan_code"] == "elite"
            assert "advanced_analytics" in r.json()["acesso"]["capabilities"]

            depois = await c.get("/api/conselho", headers=ht)
        assert depois.status_code == 200
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_conceder_pro_NAO_abre_o_conselho():
    """A concessao entrega as capacidades daquele plano, e nao o Elite disfarcado."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, ht = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/plano",
                         json={"plan_code": "pro", "motivo": "teste"}, headers=ha)
            conselho = await c.get("/api/conselho", headers=ht)
            nutricao = await c.get("/api/nutrition/plan", headers=ht)
        assert conselho.status_code == 402          # advanced_analytics e do Elite
        assert nutricao.status_code != 402          # mas alimentacao o Pro tem
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_revogar_tira_o_acesso_de_volta():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, ht = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/plano",
                         json={"plan_code": "elite", "motivo": "teste"}, headers=ha)
            assert (await c.get("/api/conselho", headers=ht)).status_code == 200

            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": None, "motivo": "fim do teste"}, headers=ha)
            assert r.status_code == 200
            assert (await c.get("/api/conselho", headers=ht)).status_code == 402
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_conceder_libera_quem_estava_aguardando_pagamento():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta(status="PENDING_PAYMENT")
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/plano",
                         json={"plan_code": "elite", "motivo": "cortesia"}, headers=ha)
        user = await DB.users.find_one({"id": uid})
        assert user["status"] == "ACTIVE"
    finally:
        await _limpar(admin_id, uid)


# ── As travas ───────────────────────────────────────────────────────────────────────

@asincrono
async def test_uma_assinatura_PAGA_nao_e_sobrescrita_por_acidente():
    """Trocar o plano de quem paga apagaria o vinculo com o Mercado Pago, e a cobranca
    seguiria correndo sem o FORGE saber de que plano ela e."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "plan_code": "pro", "status": "active",
            "provider": "mercadopago", "provider_subscription_id": "MP-123",
            "amount_cents": 6990, "currency": "BRL"}}, upsert=True)
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "elite", "motivo": "teste"}, headers=ha)
        assert r.status_code == 409
        assert r.json()["detail"]["reason"] == "paid_subscription"

        guardada = await DB.subscriptions.find_one({"user_id": uid})
        assert guardada["provider"] == "mercadopago"      # intacta
        assert guardada["plan_code"] == "pro"
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_a_substituicao_de_assinatura_paga_acontece_quando_e_explicita():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "plan_code": "pro", "status": "active",
            "provider": "mercadopago", "provider_subscription_id": "MP-123",
            "amount_cents": 6990, "currency": "BRL"}}, upsert=True)
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "elite", "motivo": "acordo comercial",
                                   "substituir_assinatura_paga": True}, headers=ha)
        assert r.status_code == 200
        guardada = await DB.subscriptions.find_one({"user_id": uid})
        assert guardada["provider"] == "courtesy"
        assert guardada["amount_cents"] == 0            # cortesia nao e receita
        assert "provider_subscription_id" not in guardada
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_cortesia_sem_motivo_e_recusada():
    """Dar acesso de graca e uma decisao com custo: ela deixa rastro de quem e por que."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "elite", "motivo": ""}, headers=ha)
        assert r.status_code == 400
        assert r.json()["detail"]["reason"] == "courtesy_reason_required"
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_plano_inexistente_e_recusado():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "LIFETIME", "motivo": "teste"}, headers=ha)
        assert r.status_code == 400
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_um_atleta_nao_concede_plano_para_si_mesmo():
    _cobranca_ligada()
    uid, ht = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post(f"/api/admin/athletes/{uid}/plano",
                             json={"plan_code": "elite", "motivo": "quero"}, headers=ht)
        assert r.status_code == 403
    finally:
        await _limpar(uid)


@asincrono
async def test_a_concessao_fica_registrada_na_auditoria():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/plano",
                         json={"plan_code": "elite", "motivo": "conta de demonstracao"},
                         headers=ha)
        registro = await DB.admin_audit_log.find_one(
            {"target_user_id": uid, "action": "athlete.courtesy_plan_granted"})
        assert registro
        assert registro["meta"]["plan_code"] == "elite"
        assert registro["meta"]["reason"] == "conta de demonstracao"
        assert registro["actor_id"] == admin_id
    finally:
        await _limpar(admin_id, uid)


# ── A lista mostra o que a pessoa VIVE ──────────────────────────────────────────────

@asincrono
async def test_a_lista_mostra_o_acesso_real_e_nao_o_campo_morto():
    """A tela dizia "vitalicio" para uma conta bloqueada por falta de pagamento."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta(status="PENDING_PAYMENT")
    try:
        # O campo legado, gravado como estava nas contas antigas.
        await DB.users.update_one({"id": uid}, {"$set": {"plan": "LIFETIME",
                                                         "signup_source": "public"}})
        async with await _cliente() as c:
            linhas = (await c.get("/api/admin/athletes", headers=ha)).json()["athletes"]
        linha = next(a for a in linhas if a["id"] == uid)
        assert linha["plan"] == "LIFETIME"              # o campo antigo continua ali
        assert linha["acesso"]["plan_code"] is None     # e o acesso real e nenhum
        assert linha["acesso"]["awaiting_payment"] is True
    finally:
        await _limpar(admin_id, uid)


@asincrono
async def test_a_ficha_individual_traz_o_acesso_e_os_planos_disponiveis():
    _cobranca_ligada()
    admin_id, ha = await _admin()
    uid, _ = await _atleta()
    try:
        async with await _cliente() as c:
            await c.post(f"/api/admin/athletes/{uid}/plano",
                         json={"plan_code": "pro", "motivo": "teste"}, headers=ha)
            ficha = (await c.get(f"/api/admin/athletes/{uid}", headers=ha)).json()
        assert ficha["acesso"]["plan_code"] == "pro"
        assert ficha["acesso"]["source"] == "courtesy"
        assert ficha["planos"] == ["essential", "pro", "elite"]
    finally:
        await _limpar(admin_id, uid)


# ── Criar atleta ────────────────────────────────────────────────────────────────────

@asincrono
async def test_criar_com_cortesia_concede_o_plano_ESCOLHIDO():
    """Antes, cortesia sempre resolvia Elite: nao havia como dar Essencial de graca."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    email = f"novo.{uuid.uuid4().hex[:8]}@example.com"
    criado = None
    try:
        async with await _cliente() as c:
            r = await c.post("/api/admin/athletes", json={
                "email": email, "name": "Convidado", "access_mode": "courtesy",
                "confirm_courtesy": True, "courtesy_reason": "parceria",
                "plan_code": "essential", "validity": "365"}, headers=ha)
        assert r.status_code == 200, r.text
        criado = r.json()["athlete"]["id"]
        assinatura = await DB.subscriptions.find_one({"user_id": criado})
        assert assinatura["plan_code"] == "essential"
        assert assinatura["provider"] == "courtesy"
        assert assinatura["amount_cents"] == 0
    finally:
        await _limpar(admin_id, *( [criado] if criado else [] ))


@asincrono
async def test_criar_com_cortesia_sem_escolher_plano_continua_dando_Elite():
    """Compatibilidade: era o comportamento antes desta tela saber escolher."""
    _cobranca_ligada()
    admin_id, ha = await _admin()
    email = f"novo.{uuid.uuid4().hex[:8]}@example.com"
    criado = None
    try:
        async with await _cliente() as c:
            r = await c.post("/api/admin/athletes", json={
                "email": email, "name": "Convidado", "access_mode": "courtesy",
                "confirm_courtesy": True, "courtesy_reason": "parceria"}, headers=ha)
        assert r.status_code == 200, r.text
        criado = r.json()["athlete"]["id"]
        assinatura = await DB.subscriptions.find_one({"user_id": criado})
        assert assinatura["plan_code"] == "elite"
    finally:
        await _limpar(admin_id, *( [criado] if criado else [] ))
