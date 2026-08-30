"""Rotas de cobranca do FORGE — planos, checkout, webhook e assinatura do atleta."""
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

import billing
import mailer
from auth import AGUARDANDO_PAGAMENTO as AGUARDANDO_PAGAMENTO_CONTA
from auth import get_current_user, require_super_admin
from billing_plans import (
    FREQUENCIA, MOEDA, TIPO_DE_FREQUENCIA, catalogo_publico, mp_plan_id, plano_ativo,
    preco_em_reais,
)
from ratelimit import limitar
from entitlements import (
    ATIVA, CANCELADA, EM_ATRASO, ORIGEM_MERCADOPAGO, acesso_de, assinatura_do_usuario,
    cobranca_ativa,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

# Abrir o checkout de novo e legitimo (trocar de plano, cartao recusado, aba fechada).
# O teto so precisa impedir automacao.
MAX_CHECKOUTS_POR_JANELA = 10
JANELA_DO_CHECKOUT_MIN = 15

# Sobrescrevivel nos testes, para exercitar o fluxo inteiro sem rede nem credencial.
_cliente: Optional[billing.ClienteMercadoPago] = None


def definir_cliente(cliente) -> None:
    global _cliente
    _cliente = cliente


def cliente() -> billing.ClienteMercadoPago:
    return _cliente or billing.cliente_padrao()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def site_url() -> str:
    return (os.environ.get("FORGE_SITE_URL") or "https://forge.aiexec.com.br").rstrip("/")


class CheckoutIn(BaseModel):
    # SO o codigo do plano. Preco, moeda e preapproval_plan_id sao resolvidos no servidor:
    # aceitar qualquer um deles do navegador seria deixar alguem assinar o Elite pagando
    # o preco do Essencial.
    plan_code: str = Field(min_length=2, max_length=32)


DIAS_DE_ACESSO_PIX = 30


# ── Catalogo ─────────────────────────────────────────────────────────────────────────

@router.get("/plans")
async def listar_planos():
    """Publico: a pagina de planos precisa abrir sem login."""
    return {"plans": catalogo_publico(), "currency": MOEDA,
            "billing_enforced": cobranca_ativa()}


# ── Assinatura do atleta ─────────────────────────────────────────────────────────────

def _resumo(acesso: Dict[str, Any]) -> Dict[str, Any]:
    assinatura = acesso.get("subscription") or {}
    p = plano_ativo(acesso.get("plan_code"))
    return {
        "plan_code": acesso.get("plan_code"),
        "plan_name": p["nome"] if p else None,
        "para_quem": p["para_quem"] if p else None,
        "price": preco_em_reais(p) if p else None,
        "currency": MOEDA,
        "status": acesso.get("status"),
        "source": acesso.get("source"),
        "payment_method": ("pix" if acesso.get("source") == "mercadopago_pix" else
                           "card" if assinatura.get("provider_subscription_id") else None),
        "grandfathered": acesso.get("grandfathered"),
        "billing_enforced": acesso.get("billing_enforced"),
        "capabilities": acesso.get("capabilities"),
        "current_period_start": assinatura.get("current_period_start"),
        "current_period_end": assinatura.get("current_period_end"),
        "next_charge": assinatura.get("current_period_end"),
        "last_payment_status": assinatura.get("last_payment_status"),
        "cancel_at_period_end": assinatura.get("cancel_at_period_end", False),
        "provider_subscription_id": assinatura.get("provider_subscription_id"),
    }


@router.get("/me")
async def minha_assinatura(request: Request, user=Depends(get_current_user)):
    return _resumo(await acesso_de(request.app.state.db, user))


# ── Checkout ─────────────────────────────────────────────────────────────────────────

async def iniciar_assinatura(db, user_id: str, email: str, plan_code: str) -> Dict[str, Any]:
    """Cria a assinatura no Mercado Pago e devolve a URL do checkout hospedado.

    Compartilhado entre o checkout de quem ja tem conta e o cadastro publico, para a
    allow-list de plano e a referencia opaca existirem em um lugar so.

    O FORGE nunca ve numero de cartao, CVV nem token sensivel: o pagamento acontece
    inteiramente no ambiente do Mercado Pago."""
    p = plano_ativo(plan_code)
    if not p:
        raise HTTPException(400, "Plano inválido")

    # Contradicao de configuracao barra ANTES de qualquer chamada: e melhor recusar o
    # checkout do que abrir um que falha, ou pior, cobrar no ambiente errado.
    conflito = billing.conflito_de_credencial()
    if conflito:
        logger.error("checkout bloqueado por configuracao: %s", conflito)
        raise HTTPException(503, {
            "message": "A assinatura ainda não está disponível. Tente novamente em instantes.",
            "reason": "misconfigured"})

    # O id nao entra na requisicao (veja o corpo abaixo), mas continua sendo a prova de que
    # este plano foi provisionado na conta do Mercado Pago; sem isso o webhook tambem nao
    # teria contra o que conferir o `preapproval_plan_id` quando ele vier preenchido.
    plan_id = mp_plan_id(p)
    if not plan_id:
        logger.error("checkout bloqueado: %s sem id de plano configurado (%s)",
                     p["code"], p["env_plan_id"])
        raise HTTPException(503, {
            "message": "A assinatura ainda não está disponível. Tente novamente em instantes.",
            "reason": "plan_not_configured"})

    referencia = f"forge_{secrets.token_urlsafe(24)}"
    await db.subscription_attempts.insert_one({
        "reference": referencia, "user_id": user_id, "plan_code": p["code"],
        "amount_cents": p["preco_centavos"], "currency": MOEDA,
        "status": "created", "created_at": _agora(),
    })

    # Nao se manda `preapproval_plan_id` aqui. O Mercado Pago so aceita esse campo no POST
    # quando o cartao JA foi tokenizado — sem ele responde 400 "card_token_id is required" —
    # e tokenizar exigiria o FORGE encostar em dado de cartao, que e justamente o que este
    # desenho evita. O caminho do checkout hospedado e a assinatura nascer com o
    # `auto_recurring` explicito e `status: pending`: o Mercado Pago devolve o init_point,
    # so cobra quando o pagador conclui, e — o que a URL do plano nao faz — preserva o
    # `external_reference`, que e como o webhook descobre de quem e a assinatura.
    #
    # Valor e periodicidade continuam vindo da allow-list, nunca do navegador, e o webhook
    # reconfere os dois contra ela antes de liberar qualquer acesso.
    corpo = {
        "payer_email": email,
        "external_reference": referencia,
        "back_url": f"{site_url()}/assinatura/retorno",
        "reason": p["nome"],
        "status": "pending",
        "auto_recurring": {
            "frequency": FREQUENCIA,
            "frequency_type": TIPO_DE_FREQUENCIA,
            "transaction_amount": preco_em_reais(p),
            "currency_id": MOEDA,
        },
    }
    try:
        recurso = await cliente().criar_assinatura(corpo)
    except billing.ErroMercadoPago as e:
        logger.error("checkout falhou user=%s plano=%s status=%s", user_id, p["code"], e.status)
        await db.subscription_attempts.update_one(
            {"reference": referencia}, {"$set": {"status": "failed", "updated_at": _agora()}})
        raise HTTPException(502, {
            "message": "Não foi possível iniciar a assinatura agora. Tente novamente.",
            "reason": "provider_error"})

    await db.subscription_attempts.update_one(
        {"reference": referencia},
        {"$set": {"provider_subscription_id": recurso.get("id"), "updated_at": _agora()}})

    url = billing.url_de_checkout(recurso)
    if not url:
        raise HTTPException(502, {"message": "Checkout indisponível no momento.",
                                  "reason": "no_checkout_url"})
    logger.info("checkout criado user=%s plano=%s assinatura=%s sandbox=%s",
                user_id, p["code"], recurso.get("id"), billing.modo_sandbox())
    return {"checkout_url": url, "plan_code": p["code"],
            "sandbox": billing.modo_sandbox(), "reference": referencia}


@router.post("/checkout")
async def criar_checkout(payload: CheckoutIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    # Cada checkout cria uma assinatura de verdade na conta do Mercado Pago. Sem teto,
    # um laco deixaria centenas de pre-aprovacoes pendentes la — barulho num sistema
    # financeiro, e trabalho de limpeza que ninguem quer.
    await limitar(db, f"checkout:{user['id']}", MAX_CHECKOUTS_POR_JANELA, JANELA_DO_CHECKOUT_MIN,
                  mensagem="Muitas tentativas de pagamento. Aguarde alguns minutos.")

    p = plano_ativo(payload.plan_code)
    if not p:
        raise HTTPException(400, "Plano inválido")

    ja = await assinatura_do_usuario(db, user["id"])
    if ja and ja.get("status") in (ATIVA, EM_ATRASO):
        raise HTTPException(409, {
            "message": "Você já tem uma assinatura ativa. Gerencie seu plano em Minha assinatura.",
            "reason": "already_subscribed"})
    return await iniciar_assinatura(db, user["id"], user["email"], payload.plan_code)


async def iniciar_pix(db, user_id: str, email: str, plan_code: str) -> Dict[str, Any]:
    """Cria um pagamento PIX unico. O cartao recorrente continua em /checkout.

    Nenhum retorno do navegador libera acesso: somente o webhook, depois de consultar
    o pagamento na API do Mercado Pago e reconferir plano, valor, moeda e referencia.
    """
    p = plano_ativo(plan_code)
    if not p:
        raise HTTPException(400, "Plano inválido")
    conflito = billing.conflito_de_credencial()
    if conflito:
        logger.error("pix bloqueado por configuracao: %s", conflito)
        raise HTTPException(503, {"message": "O PIX ainda não está disponível.",
                                  "reason": "misconfigured"})

    referencia = f"forge_pix_{secrets.token_urlsafe(24)}"
    doc = {"reference": referencia, "user_id": user_id, "plan_code": p["code"],
           "amount_cents": p["preco_centavos"], "currency": MOEDA,
           "status": "created", "created_at": _agora()}
    await db.pix_attempts.insert_one(doc)
    corpo = {
        "transaction_amount": preco_em_reais(p),
        "description": f"{p['nome']} - acesso por {DIAS_DE_ACESSO_PIX} dias",
        "payment_method_id": "pix",
        "external_reference": referencia,
        "notification_url": f"{site_url()}/api/billing/webhook",
        "payer": {"email": email},
    }
    try:
        recurso = await cliente().criar_pagamento_pix(corpo)
    except billing.ErroMercadoPago as e:
        await db.pix_attempts.update_one({"reference": referencia},
            {"$set": {"status": "failed", "updated_at": _agora()}})
        logger.error("pix falhou user=%s plano=%s status=%s", user_id, p["code"], e.status)
        raise HTTPException(502, {"message": "Não foi possível gerar o PIX agora.",
                                  "reason": "provider_error"})

    transacao = (recurso.get("point_of_interaction") or {}).get("transaction_data") or {}
    url = transacao.get("ticket_url")
    await db.pix_attempts.update_one({"reference": referencia}, {"$set": {
        "provider_payment_id": str(recurso.get("id") or ""),
        "status": recurso.get("status") or "pending", "updated_at": _agora()}})
    if not url:
        raise HTTPException(502, {"message": "O Mercado Pago não devolveu o QR Code PIX.",
                                  "reason": "no_pix_url"})
    return {"checkout_url": url, "payment_method": "pix", "plan_code": p["code"],
            "reference": referencia, "expires_in_days": DIAS_DE_ACESSO_PIX}


@router.post("/pix")
async def criar_pix(payload: CheckoutIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await limitar(db, f"pix:{user['id']}", MAX_CHECKOUTS_POR_JANELA, JANELA_DO_CHECKOUT_MIN,
                  mensagem="Muitas tentativas de pagamento. Aguarde alguns minutos.")
    ja = await assinatura_do_usuario(db, user["id"])
    if ja and ja.get("status") == ATIVA:
        fim = ja.get("current_period_end")
        if fim and datetime.fromisoformat(str(fim).replace("Z", "+00:00")) > datetime.now(timezone.utc):
            raise HTTPException(409, {"message": "Seu plano ainda está ativo.",
                                      "reason": "already_subscribed"})
    return await iniciar_pix(db, user["id"], user["email"], payload.plan_code)


@router.post("/cancel")
async def cancelar(request: Request, user=Depends(get_current_user)):
    """Cancelamento direto, sem labirinto de telas."""
    db = request.app.state.db
    assinatura = await assinatura_do_usuario(db, user["id"])
    if not assinatura or assinatura.get("status") not in (ATIVA, EM_ATRASO):
        raise HTTPException(404, "Nenhuma assinatura ativa para cancelar")

    provider_id = assinatura.get("provider_subscription_id")
    if provider_id:
        try:
            await cliente().cancelar_assinatura(provider_id)
        except billing.ErroMercadoPago as e:
            logger.error("cancelamento falhou user=%s assinatura=%s status=%s",
                         user["id"], provider_id, e.status)
            raise HTTPException(502, {
                "message": "Não foi possível cancelar agora. Tente novamente em instantes.",
                "reason": "provider_error"})

    await db.subscriptions.update_one(
        {"user_id": user["id"]},
        {"$set": {"status": CANCELADA, "cancel_at_period_end": False,
                  "updated_at": _agora()}})
    logger.info("assinatura cancelada user=%s assinatura=%s", user["id"], provider_id)
    return _resumo(await acesso_de(db, user))


# ── Webhook ──────────────────────────────────────────────────────────────────────────

EVENTOS_DE_ASSINATURA = {"subscription_preapproval", "preapproval"}
EVENTOS_DE_PAGAMENTO = {"subscription_authorized_payment", "authorized_payment"}
EVENTOS_PIX = {"payment"}


def _periodo(recurso: Dict[str, Any]) -> Dict[str, Optional[str]]:
    return {"current_period_start": recurso.get("date_created"),
            "current_period_end": recurso.get("next_payment_date")}


def _confere_o_recurso(recurso: Dict[str, Any], tentativa: Dict[str, Any],
                       p: Dict[str, Any]) -> Optional[str]:
    """O corpo do webhook nao decide nada; quem decide e o recurso consultado na API. E
    ainda assim ele e conferido contra a allow-list: valor, moeda e periodicidade tem que
    bater com o plano que o atleta escolheu."""
    esperado = mp_plan_id(p)
    recebido = recurso.get("preapproval_plan_id")
    if esperado and recebido and recebido != esperado:
        return f"plano divergente: {recebido}"

    detalhes = recurso.get("auto_recurring") or {}
    valor = detalhes.get("transaction_amount")
    if valor is not None and round(float(valor) * 100) != p["preco_centavos"]:
        return f"valor divergente: {valor}"

    moeda = detalhes.get("currency_id")
    if moeda and moeda != MOEDA:
        return f"moeda divergente: {moeda}"

    if detalhes.get("frequency") not in (None, FREQUENCIA):
        return f"frequencia divergente: {detalhes.get('frequency')}"
    if detalhes.get("frequency_type") not in (None, TIPO_DE_FREQUENCIA):
        return f"periodicidade divergente: {detalhes.get('frequency_type')}"
    return None


async def _aplicar_assinatura(db, recurso: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    referencia = recurso.get("external_reference")
    tentativa = await db.subscription_attempts.find_one({"reference": referencia}, {"_id": 0})
    if not tentativa:
        logger.warning("webhook %s: referencia desconhecida %s", request_id, referencia)
        return {"resultado": "referencia_desconhecida"}

    p = plano_ativo(tentativa["plan_code"])
    if not p:
        return {"resultado": "plano_inativo"}

    divergencia = _confere_o_recurso(recurso, tentativa, p)
    if divergencia:
        logger.error("webhook %s: %s (user=%s)", request_id, divergencia, tentativa["user_id"])
        return {"resultado": "divergente", "detalhe": divergencia}

    estado = billing.estado_do_forge(recurso.get("status"))
    anterior = await db.subscriptions.find_one({"user_id": tentativa["user_id"]}, {"_id": 0})
    estado_anterior = (anterior or {}).get("status")

    doc = {
        "user_id": tentativa["user_id"],
        "plan_code": p["code"],
        "provider": ORIGEM_MERCADOPAGO,
        "provider_subscription_id": recurso.get("id"),
        "provider_plan_id": recurso.get("preapproval_plan_id"),
        "status": estado,
        "amount_cents": p["preco_centavos"],
        "currency": MOEDA,
        "reference": referencia,
        "updated_at": _agora(),
        **_periodo(recurso),
    }
    if estado_anterior != EM_ATRASO and estado == EM_ATRASO:
        doc["past_due_since"] = _agora()
    if estado == ATIVA:
        doc["past_due_since"] = None

    await db.subscriptions.update_one(
        {"user_id": tentativa["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": _agora()}}, upsert=True)
    await db.subscription_attempts.update_one(
        {"reference": referencia}, {"$set": {"status": estado, "updated_at": _agora()}})

    # Assinatura confirmada promove a conta que estava esperando pagamento. A condicao no
    # filtro importa: so sai de PENDING_PAYMENT quem estava nele. Um usuario de cortesia,
    # ou uma conta suspensa, nao pode ser reescrito por um evento de cobranca.
    if estado == ATIVA:
        promovido = await db.users.update_one(
            {"id": tentativa["user_id"], "status": AGUARDANDO_PAGAMENTO_CONTA},
            {"$set": {"status": "ACTIVE", "plan": p["code"], "activated_at": _agora()},
             "$unset": {"expires_at": ""}})
        if promovido.modified_count:
            await _semear_o_perfil(db, tentativa["user_id"])
            logger.info("webhook %s: conta liberada user=%s plano=%s", request_id,
                        tentativa["user_id"], p["code"])
        else:
            # PIX vencido pode migrar para cartao. Suspensao administrativa, porem,
            # continua soberana e um webhook nao pode desfaze-la.
            reativado = await db.users.update_one(
                {"id": tentativa["user_id"], "status": "EXPIRED"},
                {"$set": {"status": "ACTIVE", "plan": p["code"]},
                 "$unset": {"expires_at": ""}})
            if not reativado.modified_count:
                # Ja estava ativa (renovacao ou evento repetido): so atualiza o plano.
                await db.users.update_one({"id": tentativa["user_id"]},
                                          {"$set": {"plan": p["code"]}})
        # Se a pessoa saiu do PIX para o cartao, o documento nao pode continuar parecendo
        # um pagamento unico nem herdar o vencimento manual anterior.
        await db.subscriptions.update_one({"user_id": tentativa["user_id"]},
                                          {"$unset": {"provider_payment_id": ""}})

    logger.info("webhook %s: user=%s plano=%s %s -> %s", request_id,
                tentativa["user_id"], p["code"], estado_anterior, estado)
    return {"resultado": "aplicado", "de": estado_anterior, "para": estado,
            "user_id": tentativa["user_id"], "plan_code": p["code"]}


async def _semear_o_perfil(db, user_id: str) -> None:
    """Leva as respostas da pre-avaliacao para o perfil, na hora da liberacao.

    Sem isto o questionario completo comecaria em branco e pediria de novo objetivo,
    perfil, experiencia, dias e regioes — que a pessoa acabou de responder para ver a
    previa. Escreve so o que ainda nao existe: se por algum caminho o perfil ja tiver
    resposta, ela vale mais do que a pre-avaliacao."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "pre_assessment": 1})
    respostas = (user or {}).get("pre_assessment")
    if not respostas:
        return

    perfil = await db.profiles.find_one({"id": user_id}, {"_id": 0}) or {}
    campos = {}
    for chave in ("sex", "experience", "days", "goal"):
        if respostas.get(chave) is not None and not perfil.get(chave):
            campos[chave] = respostas[chave]
    if respostas.get("priorities") and not perfil.get("priorities"):
        campos["priorities"] = list(respostas["priorities"])

    # Objetivo e ritmo alimentares moram em nutrition_assessment, a mesma fonte que a
    # area de Alimentacao usa — um segundo campo concorrente faria as duas telas
    # discordarem entre si.
    nutricao = dict(perfil.get("nutrition_assessment") or {})
    if respostas.get("body_goal") and not nutricao.get("goal"):
        nutricao["goal"] = respostas["body_goal"]
        if respostas.get("goal_intensity"):
            nutricao["intensity"] = respostas["goal_intensity"]
        campos["nutrition_assessment"] = nutricao

    if not campos:
        return
    # O questionario completo continua necessario: faltam idade, altura, peso e o resto.
    campos["preassessment_applied_at"] = _agora()
    await db.profiles.update_one({"id": user_id}, {"$set": campos}, upsert=True)
    logger.info("pre-avaliacao aplicada ao perfil user=%s campos=%s",
                user_id, sorted(campos))


async def _aplicar_pagamento(db, pagamento: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Pagamento de uma renovacao. NAO confundir com assinatura ativa: um pagamento
    aprovado confirma o ciclo; a assinatura em si continua sendo o recurso canonico."""
    assinatura_id = pagamento.get("preapproval_id")
    if not assinatura_id:
        return {"resultado": "sem_assinatura_associada"}
    assinatura = await db.subscriptions.find_one(
        {"provider_subscription_id": assinatura_id}, {"_id": 0})
    if not assinatura:
        logger.warning("webhook %s: pagamento de assinatura desconhecida %s",
                       request_id, assinatura_id)
        return {"resultado": "assinatura_desconhecida"}

    status_pagamento = (pagamento.get("status") or "").lower()
    patch: Dict[str, Any] = {"last_payment_status": status_pagamento,
                             "last_payment_id": str(pagamento.get("id") or ""),
                             "updated_at": _agora()}
    if status_pagamento == "approved":
        patch["status"] = ATIVA
        patch["past_due_since"] = None
        if pagamento.get("next_retry_date") or pagamento.get("next_payment_date"):
            patch["current_period_end"] = (pagamento.get("next_payment_date")
                                           or assinatura.get("current_period_end"))
    elif status_pagamento in ("rejected", "cancelled"):
        # Renovacao falhou: entra em atraso e a tolerancia de tres dias comeca a contar.
        patch["status"] = EM_ATRASO
        if assinatura.get("status") != EM_ATRASO:
            patch["past_due_since"] = _agora()

    await db.subscriptions.update_one({"user_id": assinatura["user_id"]}, {"$set": patch})
    logger.info("webhook %s: pagamento %s user=%s -> %s", request_id, status_pagamento,
                assinatura["user_id"], patch.get("status", assinatura.get("status")))
    return {"resultado": "pagamento_aplicado", "status": status_pagamento,
            "user_id": assinatura["user_id"]}


async def _aplicar_pix(db, pagamento: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    referencia = pagamento.get("external_reference")
    tentativa = await db.pix_attempts.find_one({"reference": referencia}, {"_id": 0})
    if not tentativa:
        return {"resultado": "pix_desconhecido"}
    p = plano_ativo(tentativa.get("plan_code"))
    if not p:
        return {"resultado": "plano_inativo"}
    valor = pagamento.get("transaction_amount")
    moeda = pagamento.get("currency_id")
    metodo = pagamento.get("payment_method_id")
    if (valor is None or round(float(valor) * 100) != tentativa["amount_cents"]
            or moeda != MOEDA or metodo != "pix"):
        logger.error("webhook %s: PIX divergente reference=%s", request_id, referencia)
        return {"resultado": "divergente"}

    status = (pagamento.get("status") or "").lower()
    await db.pix_attempts.update_one({"reference": referencia}, {"$set": {
        "status": status, "provider_payment_id": str(pagamento.get("id") or ""),
        "updated_at": _agora()}})
    if status != "approved":
        return {"resultado": "pix_pendente", "status": status}

    inicio = datetime.now(timezone.utc)
    fim = inicio + timedelta(days=DIAS_DE_ACESSO_PIX)
    doc = {"user_id": tentativa["user_id"], "plan_code": p["code"],
           "provider": "mercadopago_pix", "provider_payment_id": str(pagamento.get("id")),
           "status": ATIVA, "amount_cents": p["preco_centavos"], "currency": MOEDA,
           "reference": referencia, "current_period_start": inicio.isoformat(),
           "current_period_end": fim.isoformat(), "last_payment_status": "approved",
           "updated_at": _agora()}
    await db.subscriptions.update_one({"user_id": tentativa["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": _agora()},
         "$unset": {"provider_subscription_id": "", "provider_plan_id": "",
                     "cancel_at_period_end": "", "past_due_since": ""}}, upsert=True)
    # Nao desfaz SUSPENDED: suspensao administrativa e superior ao pagamento. ACTIVE
    # entra no filtro porque o PIX pode vencer antes da proxima requisicao marcar EXPIRED.
    await db.users.update_one(
        {"id": tentativa["user_id"], "status": {"$in": [
            AGUARDANDO_PAGAMENTO_CONTA, "EXPIRED", "ACTIVE"]}},
        {"$set": {"status": "ACTIVE", "plan": p["code"],
                  "expires_at": fim.isoformat(), "activated_at": _agora()}})
    await _semear_o_perfil(db, tentativa["user_id"])
    logger.info("webhook %s: PIX aprovado user=%s plano=%s ate=%s", request_id,
                tentativa["user_id"], p["code"], fim.isoformat())
    return {"resultado": "pix_aplicado", "user_id": tentativa["user_id"],
            "plan_code": p["code"]}


@router.post("/webhook")
async def webhook(request: Request):
    """Webhook do Mercado Pago.

    Duas coisas que este endpoint NAO faz, de proposito, e que existiam na referencia:

      1. reconhecer um evento de assinatura e responder no-op — aqui o evento e aplicado;
      2. responder 200 quando o processamento falha por erro interno. Um 200 encerra a
         entrega e o atleta pagante ficaria sem acesso, sem nova tentativa. Erro
         transitorio devolve 503 para o Mercado Pago reenviar, e o evento fica
         registrado como pendente de reconciliacao.
    """
    inicio = time.time()
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    db = request.app.state.db

    corpo: Dict[str, Any] = {}
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}

    tipo = (corpo.get("type") or corpo.get("topic")
            or request.query_params.get("type") or request.query_params.get("topic") or "")
    data_id = ((corpo.get("data") or {}).get("id")
               or request.query_params.get("data.id") or request.query_params.get("id"))

    segredo = (os.environ.get("MP_WEBHOOK_SECRET") or "").strip()
    if not billing.validar_assinatura_do_webhook(
            segredo, request.headers.get("x-signature"), request_id, data_id):
        logger.warning("webhook %s recusado: assinatura invalida (tipo=%s)", request_id, tipo)
        raise HTTPException(401, "Assinatura inválida")

    if not data_id:
        return {"received": True, "resultado": "sem_id"}

    # Idempotencia em duas camadas. O indice unico em event_key e a garantia estrutural,
    # mas depender SO dele significa falhar em silencio se o indice nao existir no
    # ambiente — entao a checagem explicita vem antes.
    chave = f"{tipo}:{data_id}"
    ja_processado = await db.billing_events.find_one({"event_key": chave}, {"_id": 0, "status": 1})
    if (ja_processado or {}).get("status") == "done":
        logger.info("webhook %s: evento repetido %s, ignorado", request_id, chave)
        return {"received": True, "resultado": "duplicado"}
    try:
        await db.billing_events.insert_one({
            "event_key": chave, "type": tipo, "resource_id": str(data_id),
            "request_id": request_id, "status": "processing", "created_at": _agora()})
    except DuplicateKeyError:
        anterior = await db.billing_events.find_one({"event_key": chave}, {"_id": 0})
        if (anterior or {}).get("status") == "done":
            logger.info("webhook %s: evento repetido %s, ignorado", request_id, chave)
            return {"received": True, "resultado": "duplicado"}
        # Ficou em "processing": a tentativa anterior morreu no meio. Deixa reprocessar.
        await db.billing_events.update_one({"event_key": chave},
                                           {"$set": {"status": "processing"}})

    try:
        if tipo in EVENTOS_DE_ASSINATURA:
            recurso = await cliente().obter_assinatura(str(data_id))
            resultado = await _aplicar_assinatura(db, recurso, request_id)
        elif tipo in EVENTOS_DE_PAGAMENTO:
            pagamento = await cliente().obter_pagamento_autorizado(str(data_id))
            resultado = await _aplicar_pagamento(db, pagamento, request_id)
        elif tipo in EVENTOS_PIX:
            pagamento = await cliente().obter_pagamento(str(data_id))
            resultado = await _aplicar_pix(db, pagamento, request_id)
        else:
            resultado = {"resultado": "tipo_ignorado", "tipo": tipo}
    except billing.ErroMercadoPago as e:
        await db.billing_events.update_one(
            {"event_key": chave},
            {"$set": {"status": "pending_retry", "error_code": e.status,
                      "updated_at": _agora()}})
        if e.transitorio:
            # 503: o Mercado Pago reenvia. Nada de sucesso silencioso.
            logger.error("webhook %s: erro transitorio %s, pedindo reenvio", request_id, e.status)
            raise HTTPException(503, "Erro temporário ao consultar o Mercado Pago")
        logger.error("webhook %s: erro permanente %s", request_id, e.status)
        return {"received": True, "resultado": "erro_permanente"}
    except Exception:
        await db.billing_events.update_one(
            {"event_key": chave},
            {"$set": {"status": "pending_retry", "updated_at": _agora()}})
        logger.exception("webhook %s: falha ao processar %s", request_id, chave)
        raise HTTPException(503, "Erro temporário ao processar o evento")

    # O mesmo id de pagamento PIX pode ser notificado primeiro como pending e depois
    # como approved. So o estado terminal vira `done`; caso contrario, a proxima
    # notificacao com o mesmo id precisa consultar novamente a API, nao ser descartada
    # como duplicata.
    estado_evento = ("awaiting_payment"
                     if resultado.get("resultado") == "pix_pendente" else "done")
    await db.billing_events.update_one(
        {"event_key": chave},
        {"$set": {"status": estado_evento, "result": resultado.get("resultado"),
                  "updated_at": _agora(),
                  "duration_ms": int((time.time() - inicio) * 1000)}})
    return {"received": True, **resultado}


# ── Conferencia de configuracao (administrativa) ─────────────────────────────────────

# Variaveis cujo VALOR nunca sai daqui. As demais nao sao segredo: id de plano, URL,
# ambiente e flags aparecem porque conferir se estao certos e justamente o objetivo.
SEGREDOS = {"MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "RESEND_API_KEY"}

VARIAVEIS = ("MP_ENVIRONMENT", "MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET",
             "MP_ESSENTIAL_PLAN_ID", "MP_PRO_PLAN_ID", "MP_ELITE_PLAN_ID",
             "FORGE_SITE_URL", "RESEND_API_KEY", "FORGE_EMAIL_FROM",
             "BILLING_ENFORCED", "PUBLIC_SIGNUP_ENABLED", "BILLING_GRANDFATHER_BEFORE")


@router.get("/config-check")
async def conferir_configuracao(admin=Depends(require_super_admin)):
    """Diz o que o processo REALMENTE carregou, sem expor segredo.

    Serve para conferir o ambiente publicado depois de cadastrar as variaveis no painel
    de deploy: um valor colado com aspas, com espaco sobrando ou na variavel errada
    aparece aqui como tamanho estranho ou ausencia — em vez de virar um checkout que
    falha so quando um cliente tentar assinar.

    Segredo nunca e devolvido: apenas presenca e numero de caracteres."""
    estado: Dict[str, Any] = {}
    for nome in VARIAVEIS:
        bruto = os.environ.get(nome)
        if bruto is None:
            estado[nome] = {"present": False, "state": "ausente"}
        elif not bruto.strip():
            estado[nome] = {"present": False, "state": "vazia"}
        elif nome in SEGREDOS:
            estado[nome] = {"present": True, "state": "definida",
                            "length": len(bruto.strip())}
        else:
            estado[nome] = {"present": True, "state": "definida",
                            "value": bruto.strip()}

    faltando = [n for n in ("MP_ACCESS_TOKEN", "MP_WEBHOOK_SECRET", "MP_ESSENTIAL_PLAN_ID",
                            "MP_PRO_PLAN_ID", "MP_ELITE_PLAN_ID")
                if not estado[n]["present"]]
    conflito = billing.conflito_de_credencial()

    return {
        "variables": estado,
        "environment": billing.ambiente(),
        "sandbox": billing.modo_sandbox(),
        "email_provider": type(mailer.provedor()).__name__,
        "delivers_email": mailer.provedor().entrega_de_verdade,
        "checkout_ready": not faltando and not conflito,
        "missing_for_checkout": faltando,
        "credential_conflict": conflito,
        "billing_enforced": cobranca_ativa(),
        "public_signup_enabled": mailer.cadastro_publico_ativo(),
    }


@router.get("/events")
async def eventos_recebidos(request: Request, limit: int = 20,
                            admin=Depends(require_super_admin)):
    """Ultimos eventos de webhook recebidos.

    Existe para responder a pergunta que nenhum teste com duble responde: "a notificacao
    do Mercado Pago chegou mesmo no servidor publicado?". Sem isto, um teste de assinatura
    real vira adivinhacao — se o acesso nao liberar, nao da para saber se o webhook nao
    chegou, chegou e foi recusado, ou chegou e falhou.

    Nao devolve corpo de notificacao nem dado financeiro: so o tipo, o id do recurso, em
    que estado o processamento parou e quanto demorou."""
    db = request.app.state.db
    limite = max(1, min(int(limit or 20), 100))
    eventos = await db.billing_events.find(
        {}, {"_id": 0, "event_key": 1, "type": 1, "resource_id": 1, "status": 1,
             "result": 1, "error_code": 1, "created_at": 1, "updated_at": 1,
             "duration_ms": 1}
    ).sort("created_at", -1).to_list(limite)
    por_estado: Dict[str, int] = {}
    for e in eventos:
        por_estado[e.get("status", "?")] = por_estado.get(e.get("status", "?"), 0) + 1
    return {"events": eventos, "count": len(eventos), "by_status": por_estado,
            "pending_retry": await db.billing_events.count_documents({"status": "pending_retry"})}


# ── Reconciliacao (administrativa) ───────────────────────────────────────────────────

@router.post("/reconcile")
async def reconciliar(request: Request, admin=Depends(require_super_admin)):
    """Corrige estado local divergente consultando o Mercado Pago.

    Existe porque webhook se perde: entrega falha, evento fica em pending_retry, ou o
    estado local diverge do real. Nunca libera acesso sem confirmacao canonica — o estado
    aplicado vem sempre do recurso consultado na API."""
    db = request.app.state.db
    corrigidas, verificadas, falhas = [], 0, []
    async for assinatura in db.subscriptions.find({}, {"_id": 0}):
        provider_id = assinatura.get("provider_subscription_id")
        if not provider_id:
            continue
        verificadas += 1
        try:
            recurso = await cliente().obter_assinatura(provider_id)
        except billing.ErroMercadoPago as e:
            falhas.append({"subscription": provider_id, "status": e.status})
            continue
        real = billing.estado_do_forge(recurso.get("status"))
        if real != assinatura.get("status"):
            await db.subscriptions.update_one(
                {"user_id": assinatura["user_id"]},
                {"$set": {"status": real, "updated_at": _agora(), **_periodo(recurso)}})
            corrigidas.append({"user_id": assinatura["user_id"],
                               "de": assinatura.get("status"), "para": real})
    pendentes = await db.billing_events.count_documents({"status": "pending_retry"})
    logger.info("reconciliacao por admin=%s: %d verificadas, %d corrigidas, %d pendentes",
                admin["id"], verificadas, len(corrigidas), pendentes)
    return {"checked": verificadas, "fixed": corrigidas, "failed": falhas,
            "pending_events": pendentes}
