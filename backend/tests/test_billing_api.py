"""Cobranca ponta a ponta: checkout, webhook, idempotencia e permissoes.

Roda o app EM PROCESSO (transporte ASGI do httpx), o que permite injetar um Mercado
Pago falso: o webhook, os estados, a tolerancia e a idempotencia sao exercitados de
verdade, sem rede, sem credencial e sem cobranca real.
"""
import asyncio
import functools
import hashlib
import json
import hmac
import os
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

import billing_routes  # noqa: E402
import server  # noqa: E402
from auth import create_token  # noqa: E402

APP = server.app
DB = server.db


def _agora():
    return datetime.now(timezone.utc)


def _iso(d):
    return d.isoformat()


# ── Mercado Pago falso ───────────────────────────────────────────────────────────────

class MercadoPagoFalso:
    """Duble do provedor. Guarda o que foi criado e permite dirigir o estado — e assim
    que se testa "pagamento aprovado libera acesso" sem pagar nada."""

    def __init__(self):
        self.assinaturas = {}
        self.pagamentos = {}
        self.criadas = []
        self.erro = None

    async def criar_assinatura(self, corpo):
        if self.erro:
            raise self.erro
        sid = f"mp-{uuid.uuid4().hex[:10]}"
        recurso = {
            "id": sid, "status": "pending",
            "preapproval_plan_id": corpo["preapproval_plan_id"],
            "external_reference": corpo["external_reference"],
            "payer_email": corpo["payer_email"],
            "init_point": f"https://mp/checkout/{sid}",
            "sandbox_init_point": f"https://mp/sandbox/{sid}",
            "date_created": _iso(_agora()),
            "next_payment_date": _iso(_agora() + timedelta(days=30)),
            "auto_recurring": {"frequency": 1, "frequency_type": "months",
                                "transaction_amount": 69.90, "currency_id": "BRL"},
        }
        self.assinaturas[sid] = recurso
        self.criadas.append(corpo)
        return recurso

    async def obter_assinatura(self, sid):
        if self.erro:
            raise self.erro
        if sid not in self.assinaturas:
            import billing
            raise billing.ErroMercadoPago(404, "nao encontrada")
        return self.assinaturas[sid]

    async def cancelar_assinatura(self, sid):
        self.assinaturas[sid]["status"] = "cancelled"
        return self.assinaturas[sid]

    async def obter_pagamento_autorizado(self, pid):
        if self.erro:
            raise self.erro
        return self.pagamentos[pid]

    def aprovar(self, sid, valor=69.90, plano="plan-pro"):
        self.assinaturas[sid].update({"status": "authorized"})
        self.assinaturas[sid]["auto_recurring"].update(
            {"transaction_amount": valor, "currency_id": "BRL"})
        self.assinaturas[sid]["preapproval_plan_id"] = plano


@pytest.fixture
def mp():
    falso = MercadoPagoFalso()
    billing_routes.definir_cliente(falso)
    yield falso
    billing_routes.definir_cliente(None)


@pytest.fixture(autouse=True)
def ambiente():
    anterior = {k: os.environ.get(k) for k in
                ("BILLING_ENFORCED", "BILLING_GRANDFATHER_BEFORE", "PUBLIC_SIGNUP_ENABLED",
                 "MP_ENVIRONMENT")}
    yield
    for k, v in anterior.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# Um unico event loop para o modulo inteiro: o cliente Motor se prende ao loop em que
# nasce, e abrir um loop por teste faria o await estourar com "different loop". Tambem
# evita adicionar pytest-asyncio so para isto.
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def asincrono(fn):
    """Deixa o pytest enxergar uma funcao sincrona e roda o corpo async no loop do modulo."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


async def _garantir_indices():
    """O evento de startup do FastAPI nao dispara sob transporte ASGI, entao os indices
    unicos que ele cria sao criados aqui — sao eles que sustentam a idempotencia.

    As colecoes de cobranca sao zeradas antes: execucoes anteriores a existencia do
    indice podem ter deixado duplicata, e ai a criacao do indice falha. So roda contra o
    banco LOCAL de teste — a guarda abaixo impede qualquer acidente com o Atlas."""
    url = os.environ.get("MONGO_URL", "")
    assert "localhost" in url or "127.0.0.1" in url, f"recusando limpar banco nao-local: {url[:30]}"
    assert "mongodb+srv" not in url, "recusando limpar Atlas"
    for colecao in ("subscriptions", "subscription_attempts", "billing_events",
                    "signup_attempts"):
        await DB[colecao].delete_many({})
    await DB.billing_events.create_index("event_key", unique=True)
    await DB.subscriptions.create_index("user_id", unique=True)
    await DB.subscription_attempts.create_index("reference", unique=True)
    await DB.signup_attempts.create_index("email", unique=True)


LOOP.run_until_complete(_garantir_indices())


async def _criar_atleta(email=None, role="ATHLETE", criado_em=None, signup_source=None):
    uid = str(uuid.uuid4())
    email = email or f"bill.{uid[:8]}@example.com"
    doc = {"id": uid, "email": email, "name": "Billing Test", "role": role,
           "status": "ACTIVE", "created_at": criado_em or _iso(_agora()),
           "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True}
    if signup_source:
        doc["signup_source"] = signup_source
    await DB.users.delete_many({"email": email})
    await DB.users.insert_one(doc)
    await DB.subscriptions.delete_many({"user_id": uid})
    await DB.subscription_attempts.delete_many({"user_id": uid})
    return uid, {"Authorization": f"Bearer {create_token(uid, role)}"}


def cabecalho_valido(data_id, request_id):
    ts = str(int(time.time() * 1000))
    manifest = f"id:{str(data_id).lower()};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(SEGREDO.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


# ── Catalogo ─────────────────────────────────────────────────────────────────────────

@asincrono
async def test_pagina_de_planos_e_publica():
    async with await _cliente() as c:
        r = await c.get("/api/billing/plans")
    assert r.status_code == 200
    planos = r.json()["plans"]
    assert [p["code"] for p in planos] == ["essential", "pro", "elite"]
    assert [p["preco"] for p in planos] == [39.90, 69.90, 99.90]


# ── Checkout ─────────────────────────────────────────────────────────────────────────

@asincrono
async def test_checkout_exige_autenticacao():
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", json={"plan_code": "pro"})
    assert r.status_code in (401, 403)


@asincrono
async def test_checkout_recusa_plano_inexistente(mp):
    _, h = await _criar_atleta()
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", json={"plan_code": "gratuito"}, headers=h)
    assert r.status_code == 400
    assert mp.criadas == []


@asincrono
async def test_o_preco_vem_da_allow_list_e_nao_do_cliente(mp):
    """O navegador manda preco, valor e id de plano — tudo isso e ignorado."""
    _, h = await _criar_atleta()
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", headers=h, json={
            "plan_code": "elite", "price": 1, "amount": 1, "preco": 0.01,
            "preapproval_plan_id": "plan-do-atacante", "currency": "USD"})
    assert r.status_code == 200
    enviado = mp.criadas[-1]
    assert enviado["preapproval_plan_id"] == "plan-elite"
    tentativa = await DB.subscription_attempts.find_one({"reference": enviado["external_reference"]})
    assert tentativa["amount_cents"] == 9990
    assert tentativa["currency"] == "BRL"


@asincrono
async def test_a_referencia_e_opaca(mp):
    uid, h = await _criar_atleta(email="opaca@example.com")
    async with await _cliente() as c:
        await c.post("/api/billing/checkout", json={"plan_code": "pro"}, headers=h)
    ref = mp.criadas[-1]["external_reference"]
    assert ref.startswith("forge_") and len(ref) > 24
    assert uid not in ref and "opaca@example.com" not in ref


@asincrono
async def test_sandbox_devolve_a_url_de_sandbox(mp):
    _, h = await _criar_atleta()
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", json={"plan_code": "pro"}, headers=h)
    assert r.json()["sandbox"] is True
    assert "/sandbox/" in r.json()["checkout_url"]


@asincrono
async def test_plano_sem_id_configurado_nao_cobra(mp):
    anterior = os.environ.pop("MP_PRO_PLAN_ID", None)
    try:
        _, h = await _criar_atleta()
        async with await _cliente() as c:
            r = await c.post("/api/billing/checkout", json={"plan_code": "pro"}, headers=h)
        assert r.status_code == 503
        assert r.json()["detail"]["reason"] == "plan_not_configured"
    finally:
        if anterior:
            os.environ["MP_PRO_PLAN_ID"] = anterior


# ── Webhook ──────────────────────────────────────────────────────────────────────────

async def _checkout(mp, headers, plano="pro"):
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", json={"plan_code": plano}, headers=headers)
    assert r.status_code == 200, r.text
    return mp.criadas[-1]["external_reference"], list(mp.assinaturas)[-1]


@asincrono
async def test_webhook_recusa_assinatura_invalida(mp):
    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": "x"}},
                         headers={"x-signature": "ts=1,v1=falso", "x-request-id": "r"})
    assert r.status_code == 401


@asincrono
async def test_webhook_sem_cabecalho_e_recusado(mp):
    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": "x"}})
    assert r.status_code == 401


@asincrono
async def test_assinatura_autorizada_libera_acesso(mp):
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid)

    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": sid}},
                         headers=cabecalho_valido(sid, "req-ativa"))
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "aplicado"

    assinatura = await DB.subscriptions.find_one({"user_id": uid})
    assert assinatura["status"] == "active"
    assert assinatura["plan_code"] == "pro"
    assert assinatura["amount_cents"] == 6990


@asincrono
async def test_pendente_nao_libera_acesso(mp):
    """O retorno visual do checkout nao confirma nada."""
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    async with await _cliente() as c:
        await c.post("/api/billing/webhook",
                     json={"type": "subscription_preapproval", "data": {"id": sid}},
                     headers=cabecalho_valido(sid, "req-pend"))
    assinatura = await DB.subscriptions.find_one({"user_id": uid})
    assert assinatura["status"] == "pending"


@asincrono
async def test_webhook_repetido_nao_duplica(mp):
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid)
    corpo = {"type": "subscription_preapproval", "data": {"id": sid}}

    async with await _cliente() as c:
        primeira = await c.post("/api/billing/webhook", json=corpo,
                                headers=cabecalho_valido(sid, "req-1"))
        segunda = await c.post("/api/billing/webhook", json=corpo,
                               headers=cabecalho_valido(sid, "req-2"))
    assert primeira.json()["resultado"] == "aplicado"
    assert segunda.json()["resultado"] == "duplicado"
    assert await DB.subscriptions.count_documents({"user_id": uid}) == 1


@asincrono
async def test_valor_divergente_e_recusado(mp):
    """Se o recurso no Mercado Pago nao bate com o plano da allow-list, nao libera."""
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid, valor=1.00)
    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": sid}},
                         headers=cabecalho_valido(sid, "req-valor"))
    assert r.json()["resultado"] == "divergente"
    assert await DB.subscriptions.find_one({"user_id": uid}) is None


@asincrono
async def test_plano_divergente_e_recusado(mp):
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid, plano="plan-elite")
    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": sid}},
                         headers=cabecalho_valido(sid, "req-plano"))
    assert r.json()["resultado"] == "divergente"


@asincrono
async def test_erro_transitorio_pede_reenvio_em_vez_de_confirmar(mp):
    """A limitacao da referencia: um erro interno acked com 200 deixaria o pagante sem
    acesso e sem nova tentativa."""
    import billing
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.erro = billing.ErroMercadoPago(503, "indisponivel")
    async with await _cliente() as c:
        r = await c.post("/api/billing/webhook",
                         json={"type": "subscription_preapproval", "data": {"id": sid}},
                         headers=cabecalho_valido(sid, "req-erro"))
    assert r.status_code == 503
    evento = await DB.billing_events.find_one({"event_key": f"subscription_preapproval:{sid}"})
    assert evento["status"] == "pending_retry"

    # e o reenvio, com o provedor de volta, aplica normalmente
    mp.erro = None
    mp.aprovar(sid)
    async with await _cliente() as c:
        r2 = await c.post("/api/billing/webhook",
                          json={"type": "subscription_preapproval", "data": {"id": sid}},
                          headers=cabecalho_valido(sid, "req-erro-2"))
    assert r2.json()["resultado"] == "aplicado"
    assert (await DB.subscriptions.find_one({"user_id": uid}))["status"] == "active"


@asincrono
async def test_renovacao_recusada_entra_em_atraso_com_tolerancia(mp):
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid)
    async with await _cliente() as c:
        await c.post("/api/billing/webhook",
                     json={"type": "subscription_preapproval", "data": {"id": sid}},
                     headers=cabecalho_valido(sid, "req-a"))

    mp.pagamentos["pay-1"] = {"id": "pay-1", "preapproval_id": sid, "status": "rejected"}
    async with await _cliente() as c:
        await c.post("/api/billing/webhook",
                     json={"type": "subscription_authorized_payment", "data": {"id": "pay-1"}},
                     headers=cabecalho_valido("pay-1", "req-b"))

    assinatura = await DB.subscriptions.find_one({"user_id": uid})
    assert assinatura["status"] == "past_due"
    assert assinatura["past_due_since"]

    import entitlements as ent
    assert ent.assinatura_da_acesso(assinatura) is True     # dentro da tolerancia


# ── Permissoes ───────────────────────────────────────────────────────────────────────

async def _com_assinatura(uid, plano):
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "mercadopago", "amount_cents": 1, "currency": "BRL"}}, upsert=True)


@asincrono
async def test_essencial_nao_acessa_alimentacao():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=1))
    uid, h = await _criar_atleta(criado_em=_iso(_agora()))
    await _com_assinatura(uid, "essential")
    async with await _cliente() as c:
        r = await c.get("/api/nutrition/plan", headers=h)
    assert r.status_code == 402
    assert r.json()["detail"]["capability"] == "nutrition"


@asincrono
async def test_pro_acessa_alimentacao_mas_nao_o_agressivo():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=1))
    uid, h = await _criar_atleta(criado_em=_iso(_agora()))
    await _com_assinatura(uid, "pro")
    corpo = {"weight_kg": 80, "height_cm": 175, "age": 30, "sex": "male",
             "goal": "fat_loss", "activity_level": "moderate", "training_days": 4,
             "meal_count": 4, "cooking_time": "medium"}
    async with await _cliente() as c:
        permitido = await c.post("/api/nutrition/assessment", json=corpo, headers=h)
        bloqueado = await c.post("/api/nutrition/assessment",
                                 json={**corpo, "intensity": "agressivo"}, headers=h)
    assert permitido.status_code == 200
    assert bloqueado.status_code == 402
    assert bloqueado.json()["detail"]["capability"] == "aggressive_protocols"


@asincrono
async def test_elite_acessa_o_protocolo_agressivo():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=1))
    uid, h = await _criar_atleta(criado_em=_iso(_agora()))
    await _com_assinatura(uid, "elite")
    async with await _cliente() as c:
        r = await c.post("/api/nutrition/assessment", headers=h, json={
            "weight_kg": 80, "height_cm": 175, "age": 30, "sex": "male",
            "goal": "fat_loss", "intensity": "agressivo", "activity_level": "moderate",
            "training_days": 4, "meal_count": 4, "cooking_time": "medium"})
    assert r.status_code == 200


@asincrono
async def test_admin_nao_e_bloqueado_pela_cobranca():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() + timedelta(days=1))
    uid, h = await _criar_atleta(role="SUPER_ADMIN", criado_em=_iso(_agora()))
    async with await _cliente() as c:
        r = await c.get("/api/billing/me", headers=h)
    assert r.status_code == 200
    assert r.json()["source"] == "admin"
    assert "aggressive_protocols" in r.json()["capabilities"]


@asincrono
async def test_usuario_antigo_nao_perde_acesso():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora())
    uid, h = await _criar_atleta(criado_em=_iso(_agora() - timedelta(days=90)))
    async with await _cliente() as c:
        r = await c.get("/api/billing/me", headers=h)
    assert r.json()["grandfathered"] is True
    assert "nutrition" in r.json()["capabilities"]


@asincrono
async def test_minha_assinatura_persiste_entre_sessoes(mp):
    uid, h = await _criar_atleta(email="persist.bill@example.com")
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid)
    async with await _cliente() as c:
        await c.post("/api/billing/webhook",
                     json={"type": "subscription_preapproval", "data": {"id": sid}},
                     headers=cabecalho_valido(sid, "req-persist"))
    # token novo = sessao nova
    novo = {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}
    async with await _cliente() as c:
        r = await c.get("/api/billing/me", headers=novo)
    assert r.json()["plan_code"] == "pro"
    assert r.json()["status"] == "active"


@asincrono
async def test_nao_permite_segunda_assinatura_ativa(mp):
    uid, h = await _criar_atleta()
    await _com_assinatura(uid, "pro")
    async with await _cliente() as c:
        r = await c.post("/api/billing/checkout", json={"plan_code": "elite"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["reason"] == "already_subscribed"


@asincrono
async def test_cancelamento_remove_o_acesso(mp):
    uid, h = await _criar_atleta()
    _, sid = await _checkout(mp, h)
    mp.aprovar(sid)
    async with await _cliente() as c:
        await c.post("/api/billing/webhook",
                     json={"type": "subscription_preapproval", "data": {"id": sid}},
                     headers=cabecalho_valido(sid, "req-cancel"))
        r = await c.post("/api/billing/cancel", headers=h)
    assert r.status_code == 200
    assinatura = await DB.subscriptions.find_one({"user_id": uid})
    assert assinatura["status"] == "cancelled"

    import entitlements as ent
    assert ent.assinatura_da_acesso(assinatura) is False


# ── Cadastro publico ─────────────────────────────────────────────────────────────────

@asincrono
async def test_cadastro_publico_desligado_por_padrao():
    os.environ.pop("PUBLIC_SIGNUP_ENABLED", None)
    async with await _cliente() as c:
        cfg = await c.get("/api/signup/config")
        r = await c.post("/api/signup/start", json={
            "name": "Novo", "email": "novo@example.com", "plan_code": "pro"})
    assert cfg.json()["enabled"] is False
    assert r.status_code == 503


@asincrono
async def test_cadastro_publico_nao_revela_conta_existente():
    os.environ["PUBLIC_SIGNUP_ENABLED"] = "true"
    email = f"existe.{uuid.uuid4().hex[:8]}@example.com"
    await _criar_atleta(email=email)
    async with await _cliente() as c:
        existente = await c.post("/api/signup/start", json={
            "name": "Xavier", "email": email, "plan_code": "pro"})
        novo = await c.post("/api/signup/start", json={
            "name": "Yasmin", "email": f"novo.{uuid.uuid4().hex[:8]}@example.com",
            "plan_code": "pro"})
    assert existente.status_code == novo.status_code == 200
    assert existente.json() == novo.json()      # resposta identica: nao vaza existencia
    assert await DB.users.count_documents({"email": email}) == 1


# ── Conferencia de configuracao ──────────────────────────────────────────────────────

@asincrono
async def test_config_check_exige_super_admin():
    _, atleta = await _criar_atleta(role="ATHLETE")
    async with await _cliente() as c:
        sem_login = await c.get("/api/billing/config-check")
        como_atleta = await c.get("/api/billing/config-check", headers=atleta)
    assert sem_login.status_code in (401, 403)
    assert como_atleta.status_code == 403


@asincrono
async def test_config_check_nunca_devolve_o_valor_de_um_segredo():
    """O endpoint existe para conferir configuracao publicada; se ele vazasse o token,
    seria pior que o problema que resolve."""
    _, admin = await _criar_atleta(role="SUPER_ADMIN")
    async with await _cliente() as c:
        r = await c.get("/api/billing/config-check", headers=admin)
    assert r.status_code == 200
    corpo = r.json()
    bruto = json.dumps(corpo)

    for nome in ("MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "RESEND_API_KEY"):
        info = corpo["variables"][nome]
        assert "value" not in info, f"{nome} devolveu o valor"
        if info["present"]:
            assert isinstance(info["length"], int)
            assert os.environ[nome].strip() not in bruto, f"{nome} vazou no corpo"


@asincrono
async def test_config_check_aponta_o_que_falta_para_o_checkout():
    _, admin = await _criar_atleta(role="SUPER_ADMIN")
    anterior = os.environ.pop("MP_PRO_PLAN_ID", None)
    try:
        async with await _cliente() as c:
            r = await c.get("/api/billing/config-check", headers=admin)
        corpo = r.json()
        assert "MP_PRO_PLAN_ID" in corpo["missing_for_checkout"]
        assert corpo["checkout_ready"] is False
    finally:
        if anterior:
            os.environ["MP_PRO_PLAN_ID"] = anterior


@asincrono
async def test_config_check_mostra_id_de_plano_que_nao_e_segredo():
    """Id de plano precisa aparecer: e conferindo ele que se descobre um valor colado
    na variavel errada."""
    _, admin = await _criar_atleta(role="SUPER_ADMIN")
    async with await _cliente() as c:
        r = await c.get("/api/billing/config-check", headers=admin)
    assert r.json()["variables"]["MP_PRO_PLAN_ID"]["value"] == os.environ["MP_PRO_PLAN_ID"]


@asincrono
async def test_lista_de_eventos_exige_admin_e_nao_expoe_payload():
    """A lista existe para provar que a notificacao chegou — nao para guardar dado
    financeiro."""
    _, atleta = await _criar_atleta(role="ATHLETE")
    _, admin = await _criar_atleta(role="SUPER_ADMIN")
    async with await _cliente() as c:
        negado = await c.get("/api/billing/events", headers=atleta)
        r = await c.get("/api/billing/events", headers=admin)
    assert negado.status_code == 403
    assert r.status_code == 200
    corpo = r.json()
    assert "events" in corpo and "by_status" in corpo
    for e in corpo["events"]:
        for proibido in ("payload", "body", "signature", "token", "card"):
            assert proibido not in e
