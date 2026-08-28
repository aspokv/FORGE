"""Funil publico de aquisicao: escolha do plano, e-mail, senha, pagamento e liberacao.

Roda o app em processo (transporte ASGI), com o Mercado Pago e o provedor de e-mail
substituidos por dubles. Nada de rede, credencial ou cobranca.

O que estes testes protegem, em uma frase: nenhum caminho que nao passe pelo webhook
com assinatura valida pode liberar acesso.
"""
import asyncio
import functools
import hashlib
import hmac
import os
import re
import sys
import time
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

SEGREDO = "segredo-do-webhook-de-teste"
os.environ["MP_WEBHOOK_SECRET"] = SEGREDO
os.environ["MP_ACCESS_TOKEN"] = "APP_USR-credencial-de-teste"
os.environ["MP_ENVIRONMENT"] = "sandbox"
os.environ["MP_ESSENTIAL_PLAN_ID"] = "plan-essential"
os.environ["MP_PRO_PLAN_ID"] = "plan-pro"
os.environ["MP_ELITE_PLAN_ID"] = "plan-elite"
os.environ["PUBLIC_SIGNUP_ENABLED"] = "true"   # so dentro do teste
os.environ["BILLING_ENFORCED"] = "false"       # o estado real da producao

import billing_routes  # noqa: E402
import mailer  # noqa: E402
import server  # noqa: E402
import signup_routes as sr  # noqa: E402

APP, DB = server.app, server.db
from loop_do_motor import LOOP  # noqa: E402

SENHA = "SenhaForte#2026"


def _agora():
    return datetime.now(timezone.utc)


def _iso(d):
    return d.isoformat()


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*a, **k):
        return LOOP.run_until_complete(fn(*a, **k))
    return wrapper


# ── Dubles ───────────────────────────────────────────────────────────────────────────

class CorreioFalso:
    """Guarda o que seria enviado. E assim que o teste le o codigo sem que ele apareca em
    log nenhum — que e justamente o que o codigo de producao garante."""

    entrega_de_verdade = True

    def __init__(self):
        self.enviados = []

    async def enviar(self, destino, assunto, corpo):
        self.enviados.append({"to": destino, "subject": assunto, "body": corpo})
        return True

    def ultimo_codigo(self):
        for m in reversed(self.enviados):
            achado = re.search(r"\b(\d{6})\b", m["body"])
            if achado:
                return achado.group(1)
        return None


class MercadoPagoFalso:
    def __init__(self):
        self.assinaturas, self.criadas = {}, []

    async def criar_assinatura(self, corpo):
        if corpo.get("preapproval_plan_id") and not corpo.get("card_token_id"):
            import billing
            raise billing.ErroMercadoPago(400, "card_token_id is required")
        sid = "mp-" + uuid.uuid4().hex[:10]
        self.assinaturas[sid] = {
            "id": sid, "status": "pending",
            "external_reference": corpo["external_reference"],
            "payer_email": corpo["payer_email"],
            "init_point": "https://mp/checkout/" + sid,
            "date_created": _iso(_agora()),
            "next_payment_date": _iso(_agora() + timedelta(days=30)),
            "auto_recurring": dict(corpo.get("auto_recurring") or {}),
        }
        self.criadas.append(corpo)
        return self.assinaturas[sid]

    def aprovar(self, sid):
        self.assinaturas[sid]["status"] = "authorized"

    async def obter_assinatura(self, sid):
        import billing
        if sid not in self.assinaturas:
            raise billing.ErroMercadoPago(404, "nao encontrada")
        return self.assinaturas[sid]

    async def cancelar_assinatura(self, sid):
        self.assinaturas[sid]["status"] = "cancelled"
        return self.assinaturas[sid]

    async def obter_pagamento_autorizado(self, pid):
        raise AssertionError("nao usado neste arquivo")


@pytest.fixture
def mp():
    falso = MercadoPagoFalso()
    billing_routes.definir_cliente(falso)
    yield falso
    billing_routes.definir_cliente(None)


@pytest.fixture
def correio():
    falso = CorreioFalso()
    mailer.definir_provedor(falso)
    yield falso
    mailer.definir_provedor(None)


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


def _assinar(data_id, request_id, ts=None):
    ts = ts or str(int(time.time() * 1000))
    manifest = "id:{};request-id:{};ts:{};".format(str(data_id).lower(), request_id, ts)
    v1 = hmac.new(SEGREDO.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": "ts={},v1={}".format(ts, v1), "x-request-id": request_id}


async def _limpar(email):
    u = await DB.users.find_one({"email": email})
    if u:
        for col in (DB.subscriptions, DB.subscription_attempts, DB.profiles):
            await col.delete_many({"user_id": u["id"]})
    await DB.users.delete_many({"email": email})
    await DB.signup_attempts.delete_many({"email": email})


async def _ate_a_senha(c, correio, email, plano="pro", senha=SENHA):
    """Percorre o funil ate a conta existir. Devolve (signup_token, jwt)."""
    await _limpar(email)
    r = await c.post("/api/signup/start", json={
        "name": "Amigo Teste", "email": email, "plan_code": plano, "accept_terms": True})
    assert r.status_code == 200, r.text
    codigo = correio.ultimo_codigo()
    r = await c.post("/api/signup/verify", json={"email": email, "code": codigo})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = await c.post("/api/signup/create-password",
                     json={"token": token, "password": senha})
    assert r.status_code == 200, r.text
    return token, r.json()["token"]


async def _pagar(c, mp, signup_token):
    """Abre o checkout, aprova no duble e entrega o evento pelo webhook."""
    r = await c.post("/api/signup/checkout", json={"token": signup_token})
    assert r.status_code == 200, r.text
    sid = list(mp.assinaturas)[-1]
    mp.aprovar(sid)
    corpo = {"type": "subscription_preapproval", "data": {"id": sid}}
    resp = await c.post("/api/billing/webhook", json=corpo,
                        headers=_assinar(sid, "req-" + uuid.uuid4().hex[:8]))
    return sid, resp


# ── Escolha do plano ─────────────────────────────────────────────────────────────────

@asincrono
async def test_a_pagina_publica_oferece_os_tres_planos_sem_login():
    async with await _cliente() as c:
        r = await c.get("/api/billing/plans")
    assert r.status_code == 200
    planos = r.json()["plans"]
    assert [p["code"] for p in planos] == ["essential", "pro", "elite"]
    assert [p["preco"] for p in planos] == [39.90, 69.90, 99.90]
    assert [p["nome"] for p in planos] == ["FORGE ESSENCIAL", "FORGE PRO", "FORGE ELITE"]
    assert [p["code"] for p in planos if p["recomendado"]] == ["pro"]
    for p in planos:
        assert p["para_quem"] and p["recursos"], p["code"]


@asincrono
async def test_o_plano_escolhido_sobrevive_ao_cadastro_inteiro(mp, correio):
    email = "escolha@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email, plano="elite")
        estado = await c.get("/api/signup/status?token=" + signup)
        assert estado.json()["plan_code"] == "elite"
        r = await c.post("/api/signup/checkout", json={"token": signup})
    assert r.json()["plan_code"] == "elite"
    assert mp.criadas[-1]["auto_recurring"]["transaction_amount"] == 99.90
    u = await DB.users.find_one({"email": email})
    assert u["plan_code_escolhido"] == "elite"
    await _limpar(email)


# ── Confirmacao de e-mail ────────────────────────────────────────────────────────────

@asincrono
async def test_o_codigo_e_enviado_e_nao_volta_na_resposta(correio):
    email = "codigo@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        r = await c.post("/api/signup/start", json={
            "name": "Alguem", "email": email, "plan_code": "pro", "accept_terms": True})
    assert r.status_code == 200
    assert correio.ultimo_codigo() is not None
    assert correio.ultimo_codigo() not in r.text
    await _limpar(email)


@asincrono
async def test_a_resposta_e_a_mesma_para_e_mail_existente_e_novo(correio):
    """Anti-enumeracao: a resposta nao pode revelar quem ja tem conta."""
    novo, existente = "novo.enum@example.com", "existe.enum@example.com"
    await _limpar(novo)
    await _limpar(existente)
    await DB.users.insert_one({"id": str(uuid.uuid4()), "email": existente,
                               "name": "Ja Existe", "role": "ATHLETE", "status": "ACTIVE",
                               "created_at": _iso(_agora())})
    async with await _cliente() as c:
        a = await c.post("/api/signup/start", json={
            "name": "Pessoa A", "email": novo, "plan_code": "pro", "accept_terms": True})
        b = await c.post("/api/signup/start", json={
            "name": "Pessoa B", "email": existente, "plan_code": "pro", "accept_terms": True})
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert await DB.users.count_documents({"email": novo}) == 0
    await _limpar(novo)
    await _limpar(existente)


@asincrono
async def test_codigo_incorreto_e_recusado_e_conta_tentativa(correio):
    email = "errado@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True})
        r = await c.post("/api/signup/verify", json={"email": email, "code": "000000"})
    assert r.status_code == 400
    t = await DB.signup_attempts.find_one({"email": email})
    assert t["attempts"] == 1
    await _limpar(email)


@asincrono
async def test_codigo_expirado_e_recusado(correio):
    email = "expirado@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True})
        codigo = correio.ultimo_codigo()
        await DB.signup_attempts.update_one(
            {"email": email},
            {"$set": {"code_expires_at": _iso(_agora() - timedelta(minutes=1))}})
        r = await c.post("/api/signup/verify", json={"email": email, "code": codigo})
    assert r.status_code == 400
    await _limpar(email)


@asincrono
async def test_o_codigo_e_de_uso_unico(correio):
    email = "reuso@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True})
        codigo = correio.ultimo_codigo()
        primeira = await c.post("/api/signup/verify", json={"email": email, "code": codigo})
        segunda = await c.post("/api/signup/verify", json={"email": email, "code": codigo})
    assert primeira.status_code == 200
    assert segunda.status_code == 400, "o mesmo codigo valeu duas vezes"
    await _limpar(email)


@asincrono
async def test_excesso_de_tentativas_trava(correio):
    email = "forca.bruta@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True})
        for _ in range(sr.MAX_TENTATIVAS):
            await c.post("/api/signup/verify", json={"email": email, "code": "111111"})
        r = await c.post("/api/signup/verify", json={"email": email, "code": "111111"})
    assert r.status_code == 429
    await _limpar(email)


@asincrono
async def test_excesso_de_reenvios_trava(correio):
    email = "reenvio@example.com"
    await _limpar(email)
    corpo = {"name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True}
    async with await _cliente() as c:
        # MAX_REENVIOS conta REENVIOS: o primeiro envio nao e reenvio, entao o bloqueio
        # cai no pedido seguinte ao ultimo reenvio permitido.
        for _ in range(sr.MAX_REENVIOS + 2):
            r = await c.post("/api/signup/start", json=corpo)
    assert r.status_code == 429
    await _limpar(email)


@asincrono
async def test_sem_aceite_dos_termos_nao_comeca(correio):
    email = "sem.termos@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        r = await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": False})
    assert r.status_code == 400
    assert correio.enviados == []
    await _limpar(email)


@asincrono
async def test_plano_inexistente_nao_comeca_cadastro(correio):
    email = "plano.falso@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        r = await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "gratuito", "accept_terms": True})
    assert r.status_code == 400
    assert correio.enviados == []
    await _limpar(email)


@asincrono
async def test_senha_so_e_aceita_depois_do_codigo(correio):
    """Pular a confirmacao do e-mail nao cria conta."""
    email = "pula.etapa@example.com"
    await _limpar(email)
    async with await _cliente() as c:
        await c.post("/api/signup/start", json={
            "name": "Teste", "email": email, "plan_code": "pro", "accept_terms": True})
        t = await DB.signup_attempts.find_one({"email": email})
        # ainda em email_verification_pending: nao ha signup_token para usar
        assert t.get("signup_token") is None
        r = await c.post("/api/signup/create-password",
                         json={"token": "x" * 32, "password": SENHA})
    assert r.status_code == 404
    assert await DB.users.count_documents({"email": email}) == 0
    await _limpar(email)


# ── Conta nasce sem acesso ───────────────────────────────────────────────────────────

@asincrono
async def test_a_conta_nasce_aguardando_pagamento(mp, correio):
    email = "nasce@example.com"
    async with await _cliente() as c:
        await _ate_a_senha(c, correio, email)
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT"
    assert u["signup_source"] == "public"
    assert u["plan"] is None
    assert await DB.subscriptions.count_documents({"user_id": u["id"]}) == 0
    await _limpar(email)


@asincrono
async def test_a_conta_pendente_nao_alcanca_nada_interno(mp, correio):
    email = "pendente@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email)
        h = {"Authorization": "Bearer " + jwt}
        for caminho in ("/api/bootstrap", "/api/nutrition/plan", "/api/weekly-report",
                        "/api/analytics", "/api/workout/session-draft"):
            r = await c.get(caminho, headers=h)
            assert r.status_code == 403, caminho + " -> " + str(r.status_code)
        for caminho in ("/api/assessment", "/api/recovery", "/api/sets",
                        "/api/nutrition/generate"):
            r = await c.post(caminho, json={}, headers=h)
            assert r.status_code == 403, caminho + " -> " + str(r.status_code)
    await _limpar(email)


@asincrono
async def test_a_conta_pendente_entra_e_continua_o_pagamento(mp, correio):
    """Item 9: fechar o navegador no meio nao pode custar a conta."""
    email = "retomada@example.com"
    async with await _cliente() as c:
        await _ate_a_senha(c, correio, email)
        entrada = await c.post("/api/auth/login",
                               json={"email": email, "password": SENHA})
        assert entrada.status_code == 200, entrada.text
        h = {"Authorization": "Bearer " + entrada.json()["token"]}
        r = await c.get("/api/billing/me", headers=h)
        assert r.status_code == 200
        assert r.json()["capabilities"] == []
        r = await c.post("/api/billing/checkout", json={"plan_code": "pro"}, headers=h)
        assert r.status_code == 200
    await _limpar(email)


@asincrono
async def test_trocar_de_plano_antes_de_pagar(mp, correio):
    email = "troca@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email, plano="essential")
        r = await c.post("/api/signup/change-plan",
                         json={"token": signup, "plan_code": "elite"})
        assert r.status_code == 200
        await c.post("/api/signup/checkout", json={"token": signup})
    assert mp.criadas[-1]["auto_recurring"]["transaction_amount"] == 99.90
    u = await DB.users.find_one({"email": email})
    assert u["plan_code_escolhido"] == "elite"
    await _limpar(email)


@asincrono
async def test_retomar_um_checkout_abandonado(mp, correio):
    email = "abandonado@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email)
        primeira = await c.post("/api/signup/checkout", json={"token": signup})
        segunda = await c.post("/api/signup/checkout", json={"token": signup})
    assert primeira.status_code == segunda.status_code == 200
    assert primeira.json()["checkout_url"] != segunda.json()["checkout_url"]
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT", "abandonar o checkout nao pode ativar"
    await _limpar(email)


# ── So o webhook libera ──────────────────────────────────────────────────────────────

@asincrono
async def test_voltar_do_checkout_nao_ativa_a_conta(mp, correio):
    """O retorno visual do Mercado Pago nao prova pagamento nenhum."""
    email = "retorno@example.com"
    async with await _cliente() as c:
        signup, jwt = await _ate_a_senha(c, correio, email)
        await c.post("/api/signup/checkout", json={"token": signup})
        for _ in range(3):
            r = await c.get("/api/signup/status?token=" + signup)
            assert r.json()["ready"] is False
        r = await c.get("/api/bootstrap", headers={"Authorization": "Bearer " + jwt})
    assert r.status_code == 403
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT"
    await _limpar(email)


@asincrono
async def test_webhook_com_assinatura_invalida_nao_ativa(mp, correio):
    email = "forjado@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email)
        await c.post("/api/signup/checkout", json={"token": signup})
        sid = list(mp.assinaturas)[-1]
        mp.aprovar(sid)
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": sid}},
                         headers={"x-signature": "ts=1,v1=forjado", "x-request-id": "r"})
    assert r.status_code == 401
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT"
    assert await DB.subscriptions.count_documents({"user_id": u["id"]}) == 0
    await _limpar(email)


@asincrono
async def test_webhook_valido_libera_exatamente_o_plano_pago(mp, correio):
    email = "liberado@example.com"
    async with await _cliente() as c:
        signup, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        sid, resp = await _pagar(c, mp, signup)
        assert resp.status_code == 200 and resp.json()["resultado"] == "aplicado"

        h = {"Authorization": "Bearer " + jwt}
        r = await c.get("/api/billing/me", headers=h)
        assert r.status_code == 200
        assert r.json()["plan_code"] == "pro"
        assert r.json()["status"] == "active"
        assert "nutrition" in r.json()["capabilities"]
        assert "aggressive_protocols" not in r.json()["capabilities"]
        assert (await c.get("/api/bootstrap", headers=h)).status_code != 403

    u = await DB.users.find_one({"email": email})
    assert u["status"] == "ACTIVE"
    assert u["plan"] == "pro"
    perfil = await DB.profiles.find_one({"user_id": u["id"]})
    assert perfil["onboarding_required"] is True, "deve cair na avaliacao inicial"
    a = await DB.subscriptions.find_one({"user_id": u["id"]})
    assert a["provider"] == "mercadopago"
    assert a["provider_subscription_id"] == sid
    assert a["amount_cents"] == 6990
    assert a["current_period_end"]
    await _limpar(email)


@asincrono
async def test_webhook_repetido_nao_duplica_assinatura(mp, correio):
    email = "duplicado@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email)
        sid, primeira = await _pagar(c, mp, signup)
        corpo = {"type": "subscription_preapproval", "data": {"id": sid}}
        segunda = await c.post("/api/billing/webhook", json=corpo,
                               headers=_assinar(sid, "req-repetido"))
    assert primeira.json()["resultado"] == "aplicado"
    assert segunda.json()["resultado"] == "duplicado"
    u = await DB.users.find_one({"email": email})
    assert await DB.subscriptions.count_documents({"user_id": u["id"]}) == 1
    await _limpar(email)


@asincrono
async def test_a_conta_ativada_nao_e_rebaixada_por_evento_repetido(mp, correio):
    email = "fora.de.ordem@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email)
        sid, _resp = await _pagar(c, mp, signup)
        u = await DB.users.find_one({"email": email})
        assert u["status"] == "ACTIVE"
        corpo = {"type": "subscription_preapproval", "data": {"id": sid}}
        await c.post("/api/billing/webhook", json=corpo,
                     headers=_assinar(sid, "req-outra-vez"))
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "ACTIVE"
    assert u["plan"] == "pro"
    await _limpar(email)


@asincrono
async def test_cadastro_publico_desligado_recusa_o_funil(correio):
    """Item 20: com a flag desligada o funil nao atende — mas os planos continuam."""
    os.environ["PUBLIC_SIGNUP_ENABLED"] = "false"
    try:
        async with await _cliente() as c:
            r = await c.post("/api/signup/start", json={
                "name": "Teste", "email": "flag@example.com", "plan_code": "pro",
                "accept_terms": True})
            planos = await c.get("/api/billing/plans")
            config = await c.get("/api/signup/config")
        assert r.status_code == 503
        assert r.json()["detail"]["reason"] == "public_signup_disabled"
        assert planos.status_code == 200
        assert config.json()["enabled"] is False
    finally:
        os.environ["PUBLIC_SIGNUP_ENABLED"] = "true"
