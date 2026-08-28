"""Cadastro publico do FORGE.

O FORGE nasceu por convite manual: o admin cria o usuario e entrega a URL por fora.
Esse fluxo continua intacto — este arquivo ADICIONA um caminho publico para quem nunca
teve conta, sem remover nada.

Estado do cadastro, na ordem: email_verification_pending -> payment_pending -> active.
Um cadastro pendente nao acessa nada pago; so o webhook, apos confirmacao canonica no
Mercado Pago, promove para active. O retorno visual do checkout nao ativa conta.
"""
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

import mailer
from auth import create_token, hash_password, sanitize, verify_password
from billing_plans import plano_ativo
from billing_routes import iniciar_assinatura

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signup", tags=["signup"])

VALIDADE_DO_CODIGO_MIN = 15
MAX_TENTATIVAS = 5
MAX_REENVIOS = 3
VALIDADE_DO_CADASTRO_H = 48
VALIDADE_DO_TOKEN_DE_ATIVACAO_MIN = 60

AGUARDANDO_EMAIL = "email_verification_pending"
AGUARDANDO_PAGAMENTO = "payment_pending"
ATIVO = "active"
PAGAMENTO_RECUSADO = "payment_failed"
EXPIRADO = "expired"

# Resposta unica de /start. Nunca revela se o e-mail ja tem conta: variar a resposta
# transformaria o endpoint num verificador de quem e cliente do FORGE.
RESPOSTA_NEUTRA = {
    "ok": True,
    "message": "Se o e-mail estiver disponível, enviamos um código de verificação.",
}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


def _quando(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _exigir_ativo():
    if not mailer.cadastro_publico_ativo():
        raise HTTPException(503, {
            "message": "O cadastro público ainda não está disponível.",
            "reason": "public_signup_disabled"})


def _novo_codigo() -> str:
    # 6 digitos, aleatoriedade criptografica. Guardado com hash, nunca em claro.
    return f"{secrets.randbelow(1_000_000):06d}"


class StartIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    plan_code: str = Field(min_length=2, max_length=32)
    accept_terms: bool = True


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class TokenIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class ActivateIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    password: str = Field(min_length=8, max_length=128)


@router.get("/config")
async def configuracao():
    """A interface precisa saber se o cadastro publico esta ligado antes de oferece-lo."""
    return {"enabled": mailer.cadastro_publico_ativo(),
            "delivers_email": mailer.provedor().entrega_de_verdade}


@router.post("/start")
async def iniciar(payload: StartIn, request: Request):
    """Envia o codigo de verificacao. Responde sempre igual, exista o e-mail ou nao."""
    _exigir_ativo()
    db = request.app.state.db
    email = payload.email.lower().strip()

    if not plano_ativo(payload.plan_code):
        raise HTTPException(400, "Plano inválido")
    if not payload.accept_terms:
        raise HTTPException(400, "É necessário aceitar os termos para continuar")

    # E-mail com conta: nada de segunda conta e nada de vazar a existencia dela. O aviso
    # vai por e-mail, onde so o dono ve.
    if await db.users.find_one({"email": email}):
        await mailer.provedor().enviar(
            email, "Sua conta FORGE já existe",
            "Recebemos um pedido de cadastro com este e-mail, mas ele já tem conta no "
            "FORGE.\nEntre com sua senha e escolha seu plano dentro do aplicativo.")
        logger.info("cadastro publico para e-mail ja existente (nenhuma conta criada)")
        return RESPOSTA_NEUTRA

    anterior = await db.signup_attempts.find_one({"email": email}, {"_id": 0})
    if anterior and anterior.get("status") == ATIVO:
        return RESPOSTA_NEUTRA
    if anterior and int(anterior.get("resends", 0)) >= MAX_REENVIOS:
        logger.warning("cadastro publico: limite de reenvios atingido")
        raise HTTPException(429, {
            "message": "Muitos reenvios. Tente novamente mais tarde.",
            "reason": "too_many_resends"})

    codigo = _novo_codigo()
    doc = {
        "email": email,
        "name": payload.name.strip(),
        "plan_code": payload.plan_code,
        "status": AGUARDANDO_EMAIL,
        "code_hash": hash_password(codigo),
        "code_expires_at": _iso(_agora() + timedelta(minutes=VALIDADE_DO_CODIGO_MIN)),
        "attempts": 0,
        "resends": int((anterior or {}).get("resends", 0)) + (1 if anterior else 0),
        "expires_at": _iso(_agora() + timedelta(hours=VALIDADE_DO_CADASTRO_H)),
        "updated_at": _iso(_agora()),
    }
    await db.signup_attempts.update_one(
        {"email": email}, {"$set": doc, "$setOnInsert": {"created_at": _iso(_agora())}},
        upsert=True)
    await mailer.enviar_codigo(email, codigo)
    return RESPOSTA_NEUTRA


@router.post("/verify")
async def verificar(payload: VerifyIn, request: Request):
    """Confere o codigo e cria o usuario PENDENTE."""
    _exigir_ativo()
    db = request.app.state.db
    email = payload.email.lower().strip()
    tentativa = await db.signup_attempts.find_one({"email": email})
    generico = HTTPException(400, "Código inválido ou expirado")

    if not tentativa or tentativa.get("status") not in (AGUARDANDO_EMAIL,):
        raise generico
    if int(tentativa.get("attempts", 0)) >= MAX_TENTATIVAS:
        raise HTTPException(429, {"message": "Muitas tentativas. Peça um novo código.",
                                  "reason": "too_many_attempts"})
    expira = _quando(tentativa.get("code_expires_at"))
    if not expira or _agora() > expira:
        raise generico

    if not verify_password(payload.code, tentativa.get("code_hash") or ""):
        await db.signup_attempts.update_one({"email": email}, {"$inc": {"attempts": 1}})
        raise generico

    # Corrida: se dois pedidos chegarem juntos, o indice unico em users.email decide.
    ja = await db.users.find_one({"email": email})
    if ja:
        uid = ja["id"]
    else:
        uid = str(secrets.token_hex(16))
        await db.users.insert_one({
            "id": uid, "email": email, "name": tentativa["name"],
            "role": "ATHLETE", "status": "PENDING", "plan": None,
            "signup_source": "public",
            "created_at": _iso(_agora()),
            "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
        })
        await db.profiles.insert_one({
            "id": uid, "user_id": uid, "name": tentativa["name"],
            "automation_mode": "FORGE_ASSISTED", "assessment": {}, "priorities": [],
            "onboarding_required": True})

    token = secrets.token_urlsafe(32)
    await db.signup_attempts.update_one({"email": email}, {"$set": {
        "status": AGUARDANDO_PAGAMENTO, "user_id": uid, "signup_token": token,
        "code_hash": None, "code_expires_at": None,   # uso unico: o codigo morre aqui
        "updated_at": _iso(_agora())}})
    logger.info("cadastro publico: e-mail verificado, usuario pendente criado")
    return {"token": token, "status": AGUARDANDO_PAGAMENTO,
            "plan_code": tentativa["plan_code"]}


async def _por_token(db, token: str) -> Dict[str, Any]:
    tentativa = await db.signup_attempts.find_one({"signup_token": token}, {"_id": 0})
    if not tentativa:
        raise HTTPException(404, "Cadastro não encontrado")
    limite = _quando(tentativa.get("expires_at"))
    if limite and _agora() > limite and tentativa.get("status") != ATIVO:
        raise HTTPException(410, {"message": "Seu cadastro expirou. Comece novamente.",
                                  "reason": "expired"})
    return tentativa


@router.post("/checkout")
async def checkout(payload: TokenIn, request: Request):
    """Inicia o pagamento do cadastro pendente. Tambem serve para RETOMAR um checkout
    abandonado: enquanto o cadastro nao expira, da para tentar de novo."""
    _exigir_ativo()
    db = request.app.state.db
    tentativa = await _por_token(db, payload.token)
    if tentativa.get("status") == ATIVO:
        raise HTTPException(409, "Este cadastro já está ativo. Faça login.")
    saida = await iniciar_assinatura(db, tentativa["user_id"], tentativa["email"],
                                     tentativa["plan_code"])
    await db.signup_attempts.update_one(
        {"signup_token": payload.token},
        {"$set": {"reference": saida["reference"], "updated_at": _iso(_agora())}})
    return saida


class TrocarPlanoIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    plan_code: str = Field(min_length=2, max_length=32)


@router.post("/change-plan")
async def trocar_plano(payload: TrocarPlanoIn, request: Request):
    """Trocar de plano antes de pagar — util para quem abandonou o checkout."""
    _exigir_ativo()
    db = request.app.state.db
    tentativa = await _por_token(db, payload.token)
    if tentativa.get("status") == ATIVO:
        raise HTTPException(409, "Este cadastro já está ativo.")
    if not plano_ativo(payload.plan_code):
        raise HTTPException(400, "Plano inválido")
    await db.signup_attempts.update_one(
        {"signup_token": payload.token},
        {"$set": {"plan_code": payload.plan_code, "updated_at": _iso(_agora())}})
    return {"ok": True, "plan_code": payload.plan_code}


@router.get("/status")
async def estado(token: str, request: Request):
    """Consultado pela tela "estamos confirmando sua assinatura". A conta so vira ativa
    pelo webhook — este endpoint apenas LE o estado, nunca o promove."""
    db = request.app.state.db
    tentativa = await _por_token(db, token)
    assinatura = None
    if tentativa.get("user_id"):
        assinatura = await db.subscriptions.find_one(
            {"user_id": tentativa["user_id"]}, {"_id": 0})

    pronto = bool(assinatura and assinatura.get("status") == "active")
    if pronto and tentativa.get("status") != ATIVO:
        # O webhook ja confirmou: liberamos a criacao de senha com token de uso unico.
        ativacao = secrets.token_urlsafe(32)
        await db.signup_attempts.update_one({"signup_token": token}, {"$set": {
            "status": ATIVO, "activation_token": ativacao,
            "activation_expires_at": _iso(
                _agora() + timedelta(minutes=VALIDADE_DO_TOKEN_DE_ATIVACAO_MIN)),
            "updated_at": _iso(_agora())}})
        tentativa = await db.signup_attempts.find_one({"signup_token": token}, {"_id": 0})

    return {"status": tentativa.get("status"),
            "plan_code": tentativa.get("plan_code"),
            "subscription_status": (assinatura or {}).get("status"),
            "activation_token": tentativa.get("activation_token") if pronto else None,
            "message": ("Estamos confirmando sua assinatura com o Mercado Pago."
                        if tentativa.get("status") == AGUARDANDO_PAGAMENTO else None)}


@router.post("/activate")
async def ativar(payload: ActivateIn, request: Request):
    """Cria a senha e entra. O token e curto, de uso unico e expira — e invalidado aqui
    mesmo, para um link vazado depois nao valer nada."""
    db = request.app.state.db
    tentativa = await db.signup_attempts.find_one({"activation_token": payload.token})
    if not tentativa or tentativa.get("status") != ATIVO:
        raise HTTPException(400, "Link de ativação inválido ou já utilizado")
    limite = _quando(tentativa.get("activation_expires_at"))
    if not limite or _agora() > limite:
        raise HTTPException(410, "Link de ativação expirado. Peça um novo.")

    assinatura = await db.subscriptions.find_one({"user_id": tentativa["user_id"]}, {"_id": 0})
    if not assinatura or assinatura.get("status") != "active":
        # Cinto e suspensorio: sem assinatura confirmada, nao ha ativacao.
        raise HTTPException(409, "Assinatura ainda não confirmada")

    await db.users.update_one({"id": tentativa["user_id"]}, {"$set": {
        "password_hash": hash_password(payload.password),
        "status": "ACTIVE",
        "plan": assinatura.get("plan_code"),
        "activated_at": _iso(_agora())}})
    await db.signup_attempts.update_one(
        {"activation_token": payload.token},
        {"$set": {"activation_token": None, "activated_at": _iso(_agora())}})

    user = await db.users.find_one({"id": tentativa["user_id"]})
    logger.info("cadastro publico concluido user=%s plano=%s",
                user["id"], assinatura.get("plan_code"))
    return {"token": create_token(user["id"], user["role"]), "user": sanitize(user)}
