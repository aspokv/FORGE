"""Cadastro publico do FORGE.

O FORGE nasceu por convite manual: o admin cria o usuario e entrega a URL por fora.
Esse fluxo continua intacto — este arquivo ADICIONA um caminho publico para quem nunca
teve conta, sem remover nada.

Estado do cadastro, na ordem:
    email_verification_pending -> email_verified -> payment_pending -> active.
Um cadastro pendente nao acessa nada pago; so o webhook, apos confirmacao canonica no
Mercado Pago, promove para active. O retorno visual do checkout nao ativa conta.
"""
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

import mailer
from auth import (
    AGUARDANDO_PAGAMENTO as AGUARDANDO_PAGAMENTO_CONTA, create_token, hash_password,
    require_super_admin, sanitize, verify_password,
)
from billing_plans import plano_ativo
from billing_routes import iniciar_assinatura
from entitlements import ORIGEM_CADASTRO_PUBLICO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/signup", tags=["signup"])

VALIDADE_DO_CODIGO_MIN = 15
MAX_TENTATIVAS = 5
MAX_REENVIOS = 3
VALIDADE_DO_CADASTRO_H = 48

AGUARDANDO_EMAIL = "email_verification_pending"
EMAIL_VERIFICADO = "email_verified"
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


@router.get("/config")
async def configuracao():
    """A interface precisa saber se o cadastro publico esta ligado antes de oferece-lo."""
    return {"enabled": mailer.cadastro_publico_ativo(),
            "delivers_email": mailer.provedor().entrega_de_verdade}


class TesteDeEmailIn(BaseModel):
    to: EmailStr


@router.post("/test-email")
async def testar_email(payload: TesteDeEmailIn, admin=Depends(require_super_admin)):
    """Envia uma mensagem de teste. Administrativo e deliberadamente separado do
    cadastro publico: e assim que se confirma que o Resend entrega ANTES de ligar
    PUBLIC_SIGNUP_ENABLED — nada de descobrir que o e-mail nao sai com gente real
    tentando se cadastrar."""
    p = mailer.provedor()
    entregue = await p.enviar(
        payload.to, "Teste de envio do FORGE",
        "Se você recebeu esta mensagem, o envio de e-mail do FORGE está funcionando.\n"
        "Nenhuma ação é necessária.")
    logger.info("teste de e-mail por admin=%s provedor=%s entregue=%s",
                admin["id"], type(p).__name__, entregue)
    return {"sent": entregue, "provider": type(p).__name__,
            "delivers_email": p.entrega_de_verdade,
            "note": ("Provedor console: a mensagem foi só para o log do servidor."
                     if not p.entrega_de_verdade else
                     "Verifique a caixa de entrada do destinatário.")}


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
    """Confere o codigo. NAO cria a conta ainda — a conta nasce junto com a senha.

    Separar os dois passos evita a conta orfa: se a pessoa fecha o navegador aqui, nao
    sobra um usuario sem senha no banco, que ninguem consegue usar nem recuperar."""
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

    token = secrets.token_urlsafe(32)
    await db.signup_attempts.update_one({"email": email}, {"$set": {
        "status": EMAIL_VERIFICADO, "signup_token": token,
        "code_hash": None, "code_expires_at": None,   # uso unico: o codigo morre aqui
        "updated_at": _iso(_agora())}})
    logger.info("cadastro publico: e-mail verificado")
    return {"token": token, "status": EMAIL_VERIFICADO,
            "plan_code": tentativa["plan_code"]}


class CriarSenhaIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)
    password: str = Field(min_length=8, max_length=128)


@router.post("/create-password")
async def criar_senha(payload: CriarSenhaIn, request: Request):
    """Cria a conta com a senha, ja no estado de quem ainda nao pagou.

    A conta existe ANTES do pagamento de proposito: e o que permite fechar o navegador no
    meio do checkout, voltar depois, entrar com a senha e continuar de onde parou. O que
    ela nao tem e acesso — `PENDING_PAYMENT` e barrado no backend, em `get_current_user`.
    """
    _exigir_ativo()
    db = request.app.state.db
    tentativa = await _por_token(db, payload.token)
    if tentativa.get("status") == ATIVO:
        raise HTTPException(409, "Este cadastro já está ativo. Faça login.")
    if tentativa.get("status") not in (EMAIL_VERIFICADO, AGUARDANDO_PAGAMENTO):
        raise HTTPException(400, "Confirme seu e-mail antes de criar a senha")

    email = tentativa["email"]
    uid = tentativa.get("user_id")
    if not uid:
        # Corrida: se dois pedidos chegarem juntos, o indice unico em users.email decide.
        ja = await db.users.find_one({"email": email})
        if ja:
            uid = ja["id"]
        else:
            uid = str(secrets.token_hex(16))
            await db.users.insert_one({
                "id": uid, "email": email, "name": tentativa["name"],
                "role": "ATHLETE", "status": AGUARDANDO_PAGAMENTO_CONTA, "plan": None,
                "signup_source": ORIGEM_CADASTRO_PUBLICO,
                "plan_code_escolhido": tentativa["plan_code"],
                "created_at": _iso(_agora()),
                "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True,
            })
            await db.profiles.insert_one({
                "id": uid, "user_id": uid, "name": tentativa["name"],
                "automation_mode": "FORGE_ASSISTED", "assessment": {}, "priorities": [],
                "onboarding_required": True})

    await db.users.update_one({"id": uid}, {"$set": {
        "password_hash": hash_password(payload.password),
        "plan_code_escolhido": tentativa["plan_code"]}})
    await db.signup_attempts.update_one({"signup_token": payload.token}, {"$set": {
        "status": AGUARDANDO_PAGAMENTO, "user_id": uid, "updated_at": _iso(_agora())}})

    user = await db.users.find_one({"id": uid})
    logger.info("cadastro publico: conta criada aguardando pagamento user=%s", uid)
    # Ja devolve sessao: a pessoa entra na tela de pagamento autenticada, e se abandonar,
    # consegue voltar pelo login normal.
    return {"token": create_token(uid, user["role"]), "user": sanitize(user),
            "signup_token": payload.token, "status": AGUARDANDO_PAGAMENTO,
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
    if not tentativa.get("user_id"):
        raise HTTPException(400, "Crie sua senha antes de continuar para o pagamento")
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
    if tentativa.get("user_id"):
        await db.users.update_one({"id": tentativa["user_id"]},
                                  {"$set": {"plan_code_escolhido": payload.plan_code}})
    return {"ok": True, "plan_code": payload.plan_code}


@router.get("/status")
async def estado(token: str, request: Request):
    """Consultado pela tela "estamos confirmando sua assinatura".

    Apenas LE o estado. Quem promove a conta e o webhook, depois de conferir a assinatura
    na API do Mercado Pago: voltar do checkout, sozinho, nao prova pagamento nenhum."""
    db = request.app.state.db
    tentativa = await _por_token(db, token)
    assinatura = None
    if tentativa.get("user_id"):
        assinatura = await db.subscriptions.find_one(
            {"user_id": tentativa["user_id"]}, {"_id": 0})

    pronto = bool(assinatura and assinatura.get("status") == "active")
    if pronto and tentativa.get("status") != ATIVO:
        await db.signup_attempts.update_one(
            {"signup_token": token},
            {"$set": {"status": ATIVO, "updated_at": _iso(_agora())}})
        tentativa = await db.signup_attempts.find_one({"signup_token": token}, {"_id": 0})

    return {"status": tentativa.get("status"),
            "plan_code": tentativa.get("plan_code"),
            "subscription_status": (assinatura or {}).get("status"),
            "ready": pronto,
            "message": ("Estamos confirmando sua assinatura com o Mercado Pago."
                        if tentativa.get("status") == AGUARDANDO_PAGAMENTO else None)}
