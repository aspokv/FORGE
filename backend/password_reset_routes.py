"""Recuperacao de senha.

Tres decisoes que moldam o resto do arquivo:

  - a resposta e SEMPRE a mesma, exista a conta ou nao. Um "e-mail nao encontrado" seria
    um oraculo de quem tem conta no FORGE, e quem descobre isso descobre tambem uma lista
    de alvos. Ate o limite por conta devolve a resposta neutra, porque um 429 so para
    e-mails existentes recriaria o mesmo oraculo;

  - o token vai por e-mail em claro, mas e guardado com HASH. Se o banco vazar, os tokens
    la dentro nao servem para nada — mesma razao de nao guardar senha em claro;

  - trocar a senha derruba as sessoes antigas. Uma conta invadida so volta a ser da pessoa
    quando o acesso de quem invadiu acaba, e isso nao acontece se o token roubado continua
    valendo por doze horas.

Nada de token, senha ou corpo do e-mail entra em log.
"""
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

import mailer
from auth import hash_password, senha_fraca, verify_password
from ratelimit import limitar

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

VALIDADE_MINUTOS = 30
MAX_POR_IP_POR_HORA = 12
MAX_POR_CONTA_POR_HORA = 3
MAX_TENTATIVAS_DE_USO = 5

# Uma resposta so, para qualquer entrada. Nunca varie este texto por caso.
RESPOSTA_NEUTRA = {
    "ok": True,
    "message": ("Se existir uma conta com esse e-mail, enviamos um link para redefinir "
                "a senha. Verifique também o spam."),
}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


def _quando(valor) -> Optional[datetime]:
    if not valor:
        return None
    try:
        d = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def _ip(request: Request) -> str:
    # Atras do nginx o IP real vem no X-Forwarded-For; o primeiro da lista e o cliente.
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:45]
    return (request.client.host if request.client else "desconhecido")[:45]


def site_url() -> str:
    import os
    return (os.environ.get("FORGE_SITE_URL") or "https://forge.aiexec.com.br").rstrip("/")


class PedidoIn(BaseModel):
    email: EmailStr


class TrocaIn(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=1, max_length=200)


async def _achar_pedido(db, token: str) -> Optional[Dict[str, Any]]:
    """Encontra o pedido correspondente ao token em claro.

    O token e guardado com hash, entao nao da para consultar por igualdade: percorremos os
    pedidos vivos e conferimos o hash. A lista e curta — sao apenas os pedidos nao usados
    e nao expirados — e a alternativa (guardar em claro) e pior."""
    agora = _iso(_agora())
    candidatos = await db.password_resets.find(
        {"used_at": None, "expires_at": {"$gt": agora}}).to_list(200)
    for p in candidatos:
        if int(p.get("attempts", 0)) >= MAX_TENTATIVAS_DE_USO:
            continue
        if verify_password(token, p.get("token_hash") or ""):
            return p
    return None


@router.post("/forgot-password")
async def pedir_recuperacao(payload: PedidoIn, request: Request):
    """Envia o link. Responde igual exista a conta ou nao."""
    db = request.app.state.db
    email = payload.email.lower().strip()

    # Limite por IP: este pode responder 429, porque nao revela nada sobre conta nenhuma.
    await limitar(db, f"forgot:ip:{_ip(request)}", MAX_POR_IP_POR_HORA, 60,
                  mensagem="Muitos pedidos. Tente novamente mais tarde.")

    user = await db.users.find_one({"email": email})
    if not user:
        logger.info("recuperacao pedida para e-mail sem conta (nada enviado)")
        return RESPOSTA_NEUTRA

    # Conta suspensa nao recupera senha por conta propria.
    if user.get("status") == "SUSPENDED":
        logger.info("recuperacao pedida para conta suspensa (nada enviado)")
        return RESPOSTA_NEUTRA

    # Limite por conta: se estourar, devolve a MESMA resposta neutra em vez de 429. Um
    # 429 que so aparece para e-mail existente diria exatamente o que se quer esconder.
    try:
        await limitar(db, f"forgot:conta:{user['id']}", MAX_POR_CONTA_POR_HORA, 60)
    except HTTPException:
        logger.warning("recuperacao: limite por conta atingido (nada enviado)")
        return RESPOSTA_NEUTRA

    agora = _agora()
    # Invalida os pedidos anteriores ANTES de criar o novo: dois links validos ao mesmo
    # tempo so ampliam a janela de quem interceptar um deles.
    await db.password_resets.update_many(
        {"user_id": user["id"], "used_at": None},
        {"$set": {"superseded": True}})

    token = secrets.token_urlsafe(32)
    await db.password_resets.insert_one({
        "id": secrets.token_hex(16),
        "user_id": user["id"],
        # Hash, nunca o token. Quem ler o banco nao consegue redefinir senha de ninguem.
        "token_hash": hash_password(token),
        "created_at": _iso(agora),
        "expires_at": _iso(agora + timedelta(minutes=VALIDADE_MINUTOS)),
        "used_at": None,
        "attempts": 0,
        "requested_ip": _ip(request),
        "superseded": False,
    })

    enviado = await mailer.enviar_recuperacao(email, f"{site_url()}/recuperar/{token}")
    # O token nao aparece aqui, nem o link. So o resultado.
    logger.info("recuperacao enviada=%s user=%s", enviado, user["id"])
    return RESPOSTA_NEUTRA


@router.get("/reset-password/{token}")
async def conferir_token(token: str, request: Request):
    """A tela pergunta se vale a pena mostrar o formulario."""
    db = request.app.state.db
    pedido = await _achar_pedido(db, token)
    if not pedido or pedido.get("superseded"):
        raise HTTPException(410, {
            "message": "Este link expirou ou já foi usado. Peça um novo.",
            "reason": "reset_token_invalid"})
    return {"valid": True, "expires_at": pedido["expires_at"]}


@router.post("/reset-password")
async def trocar_senha(payload: TrocaIn, request: Request):
    """Troca a senha, consome o link e derruba as sessoes anteriores."""
    db = request.app.state.db
    await limitar(db, f"reset:ip:{_ip(request)}", MAX_POR_IP_POR_HORA, 60,
                  mensagem="Muitas tentativas. Tente novamente mais tarde.")

    pedido = await _achar_pedido(db, payload.token)
    if not pedido or pedido.get("superseded"):
        raise HTTPException(410, {
            "message": "Este link expirou ou já foi usado. Peça um novo.",
            "reason": "reset_token_invalid"})

    user = await db.users.find_one({"id": pedido["user_id"]})
    if not user:
        raise HTTPException(410, {"message": "Este link não é mais válido.",
                                  "reason": "reset_token_invalid"})

    problema = senha_fraca(payload.password, user.get("email", ""))
    if problema:
        # Conta a tentativa mesmo assim: senao o link viraria um alvo com tentativas
        # ilimitadas, bastando mandar senha invalida.
        await db.password_resets.update_one({"id": pedido["id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, {"message": problema, "reason": "weak_password"})

    agora = _agora()
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "password_hash": hash_password(payload.password),
        # Marca que derruba todo token emitido antes deste instante.
        "password_changed_at": _iso(agora),
    }})
    # Uso unico: o link morre aqui, e os irmaos dele tambem.
    await db.password_resets.update_one(
        {"id": pedido["id"]}, {"$set": {"used_at": _iso(agora)}})
    await db.password_resets.update_many(
        {"user_id": user["id"], "used_at": None}, {"$set": {"superseded": True}})
    # Zera o bloqueio de login desta conta: quem acabou de provar o controle do e-mail
    # nao deve continuar travado pelas tentativas que motivaram a recuperacao.
    await db.login_attempts.delete_many(
        {"identifier": {"$regex": ":" + re.escape(user.get("email", "")) + "$"}})

    logger.info("senha redefinida user=%s (sessoes anteriores revogadas)", user["id"])
    return {"ok": True,
            "message": "Senha alterada. Entre com a nova senha.",
            "sessions_revoked": True}
